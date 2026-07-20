from __future__ import annotations

from copy import deepcopy
from threading import Lock
import time

import pytest

from src.services.vietnam_foreign_flow_service import (
    VietnamForeignFlowBatchService,
    VietnamForeignFlowService,
    reset_vietnam_foreign_flow_state,
    vietnam_foreign_flow_observability_snapshot,
)


def _window(size: int, value: int | None, covered: int | None = None):
    actual = size if covered is None else covered
    return {
        "requested_sessions": size,
        "covered_sessions": actual,
        "complete": actual == size,
        "start_date": "2026-06-01",
        "end_date": "2026-07-17",
        "cumulative_foreign_net_volume": None if value is None else value // 10,
        "cumulative_foreign_net_value": value,
        "net_volume_contributing_sessions": actual if value is not None else 0,
        "net_value_contributing_sessions": actual if value is not None else 0,
        "positive_net_volume_sessions": 0,
        "negative_net_volume_sessions": 0,
        "zero_net_volume_sessions": 0,
        "null_net_volume_sessions": 0 if value is not None else actual,
        "positive_net_value_sessions": 0,
        "negative_net_value_sessions": 0,
        "zero_net_value_sessions": 0,
        "null_net_value_sessions": 0 if value is not None else actual,
    }


def _history(
    ticker: str,
    latest_value: int | None = 100,
    value_5d: int | None = 500,
    value_20d: int | None = 2_000,
    *,
    state: str = "ready",
    freshness: str = "fresh",
    covered_5d: int = 5,
    covered_20d: int = 20,
):
    usable = state in {"ready", "stale"}
    latest = {
        "trading_date": "2026-07-17",
        "foreign_buy_volume": 10,
        "foreign_sell_volume": 4,
        "foreign_net_volume": 6,
        "foreign_buy_value": 140,
        "foreign_sell_value": 40,
        "foreign_net_value": latest_value,
    } if usable else None
    return {
        "ticker": ticker,
        "source": "ssi_fastconnect",
        "source_endpoint": "daily_stock_price",
        "volume_unit": "shares",
        "value_unit": "VND",
        "finality": "daily_available",
        "data_state": state,
        "freshness": freshness,
        "rows": [latest] if latest else [],
        "latest_row": latest,
        "windows": {
            "5": _window(5, value_5d if usable else None, covered_5d if usable else 0),
            "20": _window(20, value_20d if usable else None, covered_20d if usable else 0),
            "60": _window(60, None, 0),
        },
        "requested": {"mode": "recent_sessions", "requested_limit": 20, "returned_session_count": covered_20d if usable else 0},
        "coverage": {"requested_sessions": 20, "covered_sessions": covered_20d if usable else 0, "complete": covered_20d == 20 if usable else False},
        "fetched_at": "2026-07-17T10:00:00+00:00",
        "stale_reason": "cached" if state == "stale" else None,
        "failure_class": "network_error" if state == "unavailable" else None,
    }


class _SymbolService:
    def __init__(self, histories):
        self.histories = histories
        self.calls = []

    def get_symbol_history(self, ticker, **kwargs):
        self.calls.append((ticker, kwargs))
        value = self.histories[ticker]
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)


@pytest.fixture(autouse=True)
def _reset():
    reset_vietnam_foreign_flow_state()
    yield
    reset_vietnam_foreign_flow_state()


def test_batch_normalizes_composes_once_and_preserves_request_order():
    symbol_service = _SymbolService({"FPT": _history("FPT"), "VCB": _history("VCB", -200, -700, -2_700)})
    payload = VietnamForeignFlowBatchService(symbol_service, max_concurrency=1).get_batch(
        [" fpt ", "FPT.VN", "vcb"],
        top_n=5,
        force_refresh=True,
    )

    assert payload["requested_tickers"] == ["fpt", "FPT.VN", "vcb"]
    assert payload["normalized_tickers"] == ["FPT", "VCB"]
    assert [row["ticker"] for row in payload["rows"]] == ["FPT", "VCB"]
    assert payload["requested_count"] == 3
    assert payload["normalized_count"] == payload["returned_count"] == 2
    assert payload["coverage_ratio"] == 1
    assert payload["data_state"] == "ready"
    assert payload["rows"][0]["foreign_net_value_5d"] == 500
    assert payload["rows"][0]["foreign_net_value_20d"] == 2_000
    assert "rows" not in payload["rows"][0]
    assert symbol_service.calls == [
        ("FPT", {"limit": 20, "force_refresh": True}),
        ("VCB", {"limit": 20, "force_refresh": True}),
    ]


def test_rankings_are_null_zero_incomplete_and_tie_aware():
    symbol_service = _SymbolService({
        "AAA": _history("AAA", 100, 10, 500, covered_5d=3),
        "BBB": _history("BBB", 100, 0, -500),
        "CCC": _history("CCC", -100, None, None, state="stale", freshness="stale"),
        "DDD": _history("DDD", None, -10, 0),
    })
    payload = VietnamForeignFlowBatchService(symbol_service).get_batch(["DDD", "CCC", "BBB", "AAA"], top_n=2)

    latest = payload["rankings"]["latest_net_value"]
    assert [entry["ticker"] for entry in latest["top_buy"]] == ["AAA", "BBB"]
    assert latest["top_sell"] == [{
        "ticker": "CCC",
        "value": -100,
        "trading_date": "2026-07-17",
        "covered_sessions": 1,
        "complete": True,
        "data_state": "stale",
    }]
    five = payload["rankings"]["net_value_5d"]
    assert five["top_buy"][0]["ticker"] == "AAA"
    assert five["top_buy"][0]["complete"] is False
    assert five["top_buy"][0]["covered_sessions"] == 3
    assert [entry["ticker"] for entry in five["top_sell"]] == ["DDD"]


@pytest.mark.parametrize(
    ("histories", "state", "coverage", "complete"),
    [
        ({"FPT": _history("FPT"), "VCB": _history("VCB", state="stale", freshness="stale")}, "partial", 1.0, False),
        ({"FPT": _history("FPT", state="stale", freshness="stale"), "VCB": _history("VCB", state="stale", freshness="stale")}, "stale", 1.0, False),
        ({"FPT": _history("FPT", state="empty", freshness="empty"), "VCB": _history("VCB", state="empty", freshness="empty")}, "empty", 0.0, False),
        ({"FPT": _history("FPT", state="unavailable", freshness="unavailable"), "VCB": _history("VCB", state="empty", freshness="empty")}, "unavailable", 0.0, False),
    ],
)
def test_batch_state_precedence(histories, state, coverage, complete):
    payload = VietnamForeignFlowBatchService(_SymbolService(histories)).get_batch(["FPT", "VCB"])
    assert payload["data_state"] == state
    assert payload["coverage_ratio"] == coverage
    assert payload["complete"] is complete


def test_one_symbol_exception_is_isolated():
    service = _SymbolService({"FPT": _history("FPT"), "VCB": RuntimeError("secret provider detail")})
    payload = VietnamForeignFlowBatchService(service).get_batch(["FPT", "VCB"])

    assert payload["data_state"] == "partial"
    assert payload["usable_count"] == 1
    assert payload["unavailable_count"] == 1
    assert payload["rows"][1]["failure_class"] == "provider_exception"
    assert "secret provider detail" not in str(payload)


def test_concurrency_is_bounded_and_active_metrics_are_cleaned_up():
    lock = Lock()
    active = 0
    maximum = 0

    class BlockingService:
        def get_symbol_history(self, ticker, **kwargs):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            return _history(ticker)

    tickers = [f"A{index:02d}" for index in range(30)]
    payload = VietnamForeignFlowBatchService(BlockingService(), max_concurrency=3).get_batch(tickers)
    metrics = vietnam_foreign_flow_observability_snapshot()

    assert len(payload["rows"]) == 30
    assert [row["ticker"] for row in payload["rows"]] == tickers
    assert 1 < maximum <= 3
    assert metrics["batch_requests"] == 1
    assert metrics["batch_normalized_symbols"] == 30
    assert metrics["batch_active_requests"] == 0
    assert metrics["batch_max_active_requests"] == 1
    assert metrics["ranking_build_count"] == 1


def test_repeat_batch_reuses_authoritative_per_symbol_cache_without_ranking_fetches():
    class Fetcher:
        def __init__(self):
            self.calls = []

        def get_daily_stock_price(self, ticker, **kwargs):
            self.calls.append((ticker, kwargs))
            return {
                "status": "ok",
                "rows": [{
                    "date": "2026-07-17",
                    "foreign_buy_volume": 10,
                    "foreign_sell_volume": 4,
                    "foreign_net_volume": 6,
                    "foreign_buy_value": 100,
                    "foreign_sell_value": 40,
                    "foreign_net_value": 60,
                }],
            }

    fetcher = Fetcher()
    batch = VietnamForeignFlowBatchService(VietnamForeignFlowService(fetcher), max_concurrency=1)

    first = batch.get_batch(["FPT", "VCB"])
    second = batch.get_batch(["FPT", "VCB"])
    metrics = vietnam_foreign_flow_observability_snapshot()

    assert first["rankings"] == second["rankings"]
    assert [call[0] for call in fetcher.calls] == ["FPT", "FPT", "FPT", "VCB", "VCB", "VCB"]
    assert metrics["provider_calls"] == 6
    assert metrics["cache_hits"] == 2
    assert metrics["ranking_build_count"] == 2


@pytest.mark.parametrize(
    "tickers",
    [[], ["*"], ["ALL"], [f"A{index:02d}" for index in range(31)]],
)
def test_invalid_batches_are_rejected(tickers):
    with pytest.raises(ValueError):
        VietnamForeignFlowBatchService(_SymbolService({})).get_batch(tickers)


@pytest.mark.parametrize("top_n", [0, 11])
def test_invalid_top_n_is_rejected(top_n):
    with pytest.raises(ValueError):
        VietnamForeignFlowBatchService(_SymbolService({"FPT": _history("FPT")})).get_batch(["FPT"], top_n=top_n)
