from __future__ import annotations

from datetime import date, timedelta

import pytest

from api.v1.schemas.stocks import VietnamForeignFlowSymbolHistoryResponse
from src.services.vietnam_foreign_flow_service import (
    VietnamForeignFlowService,
    reset_vietnam_foreign_flow_state,
)


class Fetcher:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def get_daily_stock_price(self, ticker, **kwargs):
        self.calls += 1
        return {"status": "ok", "rows": self.rows}


def row(index: int, value, volume=None):
    trading_date = date(2026, 1, 1) + timedelta(days=index)
    missing = value is None
    return {
        "date": trading_date.isoformat(),
        "foreign_buy_value": 1_000,
        "foreign_sell_value": None if missing else 500,
        "foreign_net_value": value,
        "foreign_buy_volume": 100,
        "foreign_sell_volume": 50,
        "foreign_net_volume": value if volume is None else volume,
    }


@pytest.fixture(autouse=True)
def reset_state():
    reset_vietnam_foreign_flow_state()
    yield
    reset_vietnam_foreign_flow_state()


def test_symbol_analytics_are_bounded_aligned_and_statistically_deterministic():
    values = [-500, *range(2, 60), 1_000]
    service = VietnamForeignFlowService(Fetcher([row(index, value) for index, value in enumerate(values)]))

    payload = service.get_symbol_history("FPT", limit=60)
    typed = VietnamForeignFlowSymbolHistoryResponse(**payload)
    analytics = payload["analytics"]
    value = analytics["value"]

    assert len(payload["rows"]) == analytics["observed_sessions"] == len(analytics["rolling_series"]) == 60
    assert typed.analytics is not None
    assert analytics["max_sessions"] == 60
    assert analytics["basis"] == "accepted_provider_rows"
    assert value["latest"] == {"value": 1_000, "trading_date": payload["rows"][-1]["trading_date"]}
    assert value["windows"]["5"]["net_sum"] == sum([56, 57, 58, 59, 1_000])
    assert value["windows"]["20"]["complete"] is True
    assert value["windows"]["60"]["covered_sessions"] == 60
    assert value["windows"]["60"]["net_buy_session_count"] == 59
    assert value["windows"]["60"]["net_sell_session_count"] == 1
    assert value["windows"]["60"]["max_net_buy"]["value"] == 1_000
    assert value["windows"]["60"]["max_net_sell"]["value"] == -500
    assert value["current_streak"]["direction"] == "net_buy"
    assert value["current_streak"]["sessions"] == 59
    assert value["latest_reversal"]["from_direction"] == "net_sell"
    assert value["latest_reversal"]["to_direction"] == "net_buy"
    comparison = value["comparison"]
    assert comparison["signed_percentile_60d"] == 100
    assert comparison["absolute_percentile_60d"] == 100
    assert comparison["z_score_60d"] is not None
    assert comparison["unusual_flow_state"] == "elevated"
    assert "absolute_percentile_60d_gte_90" in comparison["unusual_flow_basis"]
    assert analytics["rolling_series"][-1]["rolling_net_5d_value"] == sum([56, 57, 58, 59, 1_000])
    assert analytics["rolling_series"][18]["rolling_net_20d_value"] is None
    assert analytics["rolling_series"][19]["rolling_net_20d_value"] is not None


def test_null_and_zero_are_not_fabricated_and_break_streak_reversal_and_rolling_windows():
    values = [4, 0, -3, None, -2, -1]
    payload = VietnamForeignFlowService(Fetcher([row(index, value) for index, value in enumerate(values)])).get_symbol_history("FPT", limit=6)
    value = payload["analytics"]["value"]

    window = value["windows"]["5"]
    assert window["observed_sessions"] == 5
    assert window["covered_sessions"] == 4
    assert window["complete"] is False
    assert window["zero_session_count"] == 1
    assert window["unavailable_session_count"] == 1
    assert window["net_sum"] == -6
    assert value["current_streak"]["direction"] == "net_sell"
    assert value["current_streak"]["sessions"] == 2
    assert value["latest_reversal"] is None
    assert payload["analytics"]["rolling_series"][-1]["rolling_net_5d_value"] is None
    assert payload["rows"][1]["foreign_net_value"] == 0
    assert payload["rows"][3]["foreign_net_value"] is None


def test_short_and_constant_samples_return_null_comparison_statistics():
    payload = VietnamForeignFlowService(Fetcher([row(index, 7) for index in range(4)])).get_symbol_history("FPT", limit=4)
    comparison = payload["analytics"]["value"]["comparison"]

    assert comparison["signed_percentile_20d"] is None
    assert comparison["absolute_percentile_60d"] is None
    assert comparison["z_score_20d"] is None
    assert comparison["unusual_flow_state"] == "unavailable"
    assert comparison["unusual_flow_basis"] == ["insufficient_finite_history"]


def test_extrema_ties_choose_the_most_recent_provider_date():
    values = [10, -5, 10, -5, 0]
    payload = VietnamForeignFlowService(Fetcher([row(index, value) for index, value in enumerate(values)])).get_symbol_history("FPT", limit=5)
    window = payload["analytics"]["value"]["windows"]["5"]

    assert window["max_net_buy"]["trading_date"] == payload["rows"][2]["trading_date"]
    assert window["max_net_sell"]["trading_date"] == payload["rows"][3]["trading_date"]
    assert window["zero_session_count"] == 1


def test_empty_provider_result_returns_bounded_empty_analytics():
    fetcher = Fetcher([])
    payload = VietnamForeignFlowService(fetcher).get_symbol_history("FPT", limit=60)

    assert payload["data_state"] == "empty"
    assert payload["analytics"]["observed_sessions"] == 0
    assert payload["analytics"]["rolling_series"] == []
    assert payload["analytics"]["value"]["latest"] is None
    assert payload["analytics"]["value"]["current_streak"]["direction"] == "unavailable"


@pytest.mark.parametrize(
    ("latest", "expected"),
    [(10, "accumulating"), (-10, "distributing"), (0, "neutral"), (None, "unavailable")],
)
def test_completed_direction_signals_preserve_zero_and_missing(latest, expected):
    values = [1] * 19 + [latest]
    signals = VietnamForeignFlowService(
        Fetcher([row(index, value) for index, value in enumerate(values)])
    ).get_symbol_history("FPT", limit=20)["analytics"]["signals"]

    assert signals["direction_1d"]["state"] == expected
    assert signals["direction_1d"]["net_value"] == latest
    expected_5d = None if latest is None else 4 + latest
    expected_20d = None if latest is None else 19 + latest
    classify = lambda value: (
        "unavailable" if value is None else "accumulating" if value > 0
        else "distributing" if value < 0 else "neutral"
    )
    assert signals["direction_5d"]["state"] == classify(expected_5d)
    assert signals["direction_5d"]["net_value"] == expected_5d
    assert signals["direction_20d"]["state"] == classify(expected_20d)
    assert signals["direction_20d"]["net_value"] == (
        expected_20d
    )


@pytest.mark.parametrize(
    ("previous", "recent", "expected"),
    [
        (10, 20, "accelerating"),
        (20, 10, "decelerating"),
        (-10, -20, "accelerating"),
        (-20, -10, "decelerating"),
        (10, 10, "stable"),
        (10, -10, "reversal"),
        (-10, 10, "reversal"),
        (0, 10, "stable"),
    ],
)
def test_momentum_uses_two_non_overlapping_numeric_five_session_averages(
    previous, recent, expected
):
    values = [previous] * 5 + [recent] * 5
    momentum = VietnamForeignFlowService(
        Fetcher([row(index, value) for index, value in enumerate(values)])
    ).get_symbol_history("FPT", limit=10)["analytics"]["signals"]["momentum"]

    assert momentum["state"] == expected
    assert momentum["previous_5_average"] == previous
    assert momentum["recent_5_average"] == recent
    assert momentum["covered_sessions"] == 10
    assert momentum["complete"] is True


def test_signal_reversal_intensity_and_incomplete_coverage_reuse_analytics():
    values = [10] * 55 + [-10, -10, -10, -10, -1_000]
    payload = VietnamForeignFlowService(
        Fetcher([row(index, value) for index, value in enumerate(values)])
    ).get_symbol_history("FPT", limit=60)
    signals = payload["analytics"]["signals"]

    assert signals["momentum"]["state"] == "reversal"
    assert signals["reversal"] == {
        "detected": True,
        "from_direction": "accumulating",
        "to_direction": "distributing",
        "previous_date": payload["rows"][54]["trading_date"],
        "current_date": payload["rows"][55]["trading_date"],
        "previous_value": 10,
        "current_value": -10,
    }
    assert signals["intensity"]["state"] == "elevated"
    assert signals["intensity"]["absolute_percentile_60d"] == 100
    assert signals["intensity"]["z_score_60d"] is not None
    assert signals["intensity"]["threshold_basis"]

    incomplete = VietnamForeignFlowService(
        Fetcher([row(index, 1 if index != 5 else None) for index in range(10)])
    ).get_symbol_history("SSI", limit=10)["analytics"]["signals"]
    assert incomplete["momentum"]["state"] == "unavailable"
    assert incomplete["momentum"]["recent_5_average"] is None
    assert incomplete["momentum"]["covered_sessions"] == 9


def test_zero_standard_deviation_keeps_intensity_traceable_without_fake_z_score():
    signals = VietnamForeignFlowService(
        Fetcher([row(index, 0) for index in range(60)])
    ).get_symbol_history("FPT", limit=60)["analytics"]["signals"]

    assert signals["intensity"]["state"] == "elevated"
    assert signals["intensity"]["absolute_percentile_60d"] == 100
    assert signals["intensity"]["z_score_60d"] is None
    assert signals["direction_20d"]["state"] == "neutral"
