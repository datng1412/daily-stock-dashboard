from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Event, Lock

import pytest

from src.services.vietnam_foreign_flow_service import (
    MAX_DATE_RANGE_DAYS,
    VietnamForeignFlowService,
    reset_vietnam_foreign_flow_state,
    vietnam_foreign_flow_observability_snapshot,
)


def _row(day: int, **overrides):
    row = {
        "date": f"2026-06-{day:02d}",
        "foreign_buy_volume": day * 100,
        "foreign_sell_volume": day * 40,
        "foreign_net_volume": day * 60,
        "foreign_buy_value": day * 1_000,
        "foreign_sell_value": day * 400,
        "foreign_net_value": day * 600,
    }
    row.update(overrides)
    return row


class _Fetcher:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def get_daily_stock_price(self, ticker, **kwargs):
        self.calls.append((ticker, kwargs))
        item = self.results[min(len(self.calls) - 1, len(self.results) - 1)]
        return item() if callable(item) else item


@pytest.fixture(autouse=True)
def _reset():
    reset_vietnam_foreign_flow_state()
    yield
    reset_vietnam_foreign_flow_state()


def test_normalizes_sorts_deduplicates_and_preserves_direct_net_mismatch():
    fetcher = _Fetcher(
        [{
            "status": "ok",
            "rows": [
                _row(3),
                {"date": "bad", "foreign_net_volume": 10},
                _row(1, foreign_net_volume=None, foreign_net_value=None),
                _row(2),
                _row(2, foreign_net_volume=999, foreign_net_value=9999),
                {"date": "2026-06-04", "foreign_buy_volume": True},
            ],
        }]
    )

    payload = VietnamForeignFlowService(fetcher).get_symbol_history("fpt", limit=3)

    assert payload["ticker"] == "FPT"
    assert [row["trading_date"] for row in payload["rows"]] == ["2026-06-01", "2026-06-02", "2026-06-03"]
    assert payload["rows"][0]["foreign_net_volume"] == 60
    assert payload["rows"][0]["foreign_net_value"] == 600
    assert payload["rows"][1]["foreign_net_volume"] == 999
    assert payload["latest_row"] == payload["rows"][-1]
    metrics = vietnam_foreign_flow_observability_snapshot()
    assert metrics["duplicate_date_count"] == 1
    assert metrics["rejected_rows"] == 2
    assert metrics["net_volume_fallback_count"] == 1
    assert metrics["net_value_fallback_count"] == 1
    assert metrics["net_volume_mismatch_count"] == 1
    assert metrics["net_value_mismatch_count"] == 1


def test_window_summaries_are_latest_session_based_null_aware_and_incomplete():
    rows = [
        _row(1, foreign_net_volume=10, foreign_net_value=None, foreign_buy_value=None, foreign_sell_value=None),
        _row(2, foreign_net_volume=-2, foreign_net_value=0),
        _row(3, foreign_net_volume=0, foreign_net_value=30),
        _row(4, foreign_net_volume=None, foreign_buy_volume=None, foreign_sell_volume=None, foreign_net_value=-4),
    ]
    payload = VietnamForeignFlowService(_Fetcher([{"status": "ok", "rows": rows}])).get_symbol_history("FPT", limit=4)

    window = payload["windows"]["5"]
    assert window["covered_sessions"] == 4
    assert window["complete"] is False
    assert window["start_date"] == "2026-06-01"
    assert window["end_date"] == "2026-06-04"
    assert window["cumulative_foreign_net_volume"] == 8
    assert window["cumulative_foreign_net_value"] == 26
    assert window["net_volume_contributing_sessions"] == 3
    assert window["null_net_volume_sessions"] == 1
    assert window["positive_net_volume_sessions"] == 1
    assert window["negative_net_volume_sessions"] == 1
    assert window["zero_net_volume_sessions"] == 1
    assert payload["windows"]["20"]["complete"] is False
    assert payload["windows"]["60"]["complete"] is False


def test_recent_mode_expands_calendar_lookback_and_caps_rows():
    first = {"status": "ok", "rows": [_row(day) for day in range(1, 6)]}
    second = {"status": "ok", "rows": [_row(day) for day in range(1, 31)]}
    fetcher = _Fetcher([first, second])

    payload = VietnamForeignFlowService(fetcher).get_symbol_history("FPT", limit=20)

    assert len(fetcher.calls) == 2
    assert len(payload["rows"]) == 20
    assert payload["rows"][0]["trading_date"] == "2026-06-11"
    assert payload["coverage"] == {
        "requested_sessions": 20,
        "covered_sessions": 20,
        "complete": True,
        "start_date": "2026-06-11",
        "end_date": "2026-06-30",
    }


@pytest.mark.parametrize(
    "kwargs,message",
    [
        ({"from_date": "2026-01-01"}, "provided together"),
        ({"from_date": "2026-01-01", "to_date": "2026-01-02", "limit": 5}, "cannot be combined"),
        ({"from_date": "2026-02-01", "to_date": "2026-01-01"}, "on or before"),
        ({"from_date": "not-a-date", "to_date": "2026-01-01"}, "YYYY-MM-DD"),
    ],
)
def test_rejects_invalid_query_shapes(kwargs, message):
    with pytest.raises(ValueError, match=message):
        VietnamForeignFlowService(_Fetcher([])).get_symbol_history("FPT", **kwargs)


def test_rejects_invalid_ticker_and_overlong_date_range():
    service = VietnamForeignFlowService(_Fetcher([]))
    with pytest.raises(ValueError, match="ticker"):
        service.get_symbol_history("FPT!")
    start = date(2026, 1, 1)
    end = start + timedelta(days=MAX_DATE_RANGE_DAYS)
    with pytest.raises(ValueError, match="cannot exceed"):
        service.get_symbol_history("FPT", from_date=start.isoformat(), to_date=end.isoformat())


def test_positive_empty_and_negative_cache_classes_are_distinct():
    positive = _Fetcher([{"status": "ok", "rows": [_row(1)]}])
    service = VietnamForeignFlowService(positive)
    assert service.get_symbol_history("FPT", limit=1)["data_state"] == "ready"
    assert service.get_symbol_history("FPT", limit=1)["data_state"] == "ready"
    assert len(positive.calls) == 1
    assert vietnam_foreign_flow_observability_snapshot()["cache_hits"] == 1

    empty = _Fetcher([{"status": "unavailable", "failure_class": "empty_response", "rows": []}])
    empty_service = VietnamForeignFlowService(empty)
    assert empty_service.get_symbol_history("HPG")["data_state"] == "empty"
    assert empty_service.get_symbol_history("HPG")["data_state"] == "empty"
    assert vietnam_foreign_flow_observability_snapshot()["empty_cache_hits"] == 1

    failed = _Fetcher([{"status": "unavailable", "failure_class": "rate_limited", "rows": []}])
    failed_service = VietnamForeignFlowService(failed)
    result = failed_service.get_symbol_history("SSI")
    assert result["data_state"] == "unavailable"
    assert result["rows"] == []
    assert failed_service.get_symbol_history("SSI")["data_state"] == "unavailable"
    assert vietnam_foreign_flow_observability_snapshot()["negative_cache_hits"] == 1


def test_provider_failure_class_is_sanitized():
    fetcher = _Fetcher([{"status": "unavailable", "failure_class": "secret-token-upstream", "rows": []}])

    payload = VietnamForeignFlowService(fetcher).get_symbol_history("FPT")

    assert payload["failure_class"] == "provider_unavailable"
    assert "secret-token-upstream" not in str(payload)
    assert vietnam_foreign_flow_observability_snapshot()["last_failure_class"] == "provider_unavailable"


def test_failed_force_refresh_preserves_positive_rows_as_stale():
    fetcher = _Fetcher(
        [
            {"status": "ok", "rows": [_row(1), _row(2)]},
            {"status": "unavailable", "failure_class": "network_error", "rows": []},
        ]
    )
    service = VietnamForeignFlowService(fetcher)
    original = service.get_symbol_history("FPT", limit=1)
    stale = service.get_symbol_history("FPT", limit=1, force_refresh=True)

    assert stale["data_state"] == "stale"
    assert stale["freshness"] == "stale"
    assert stale["rows"] == original["rows"]
    assert stale["fetched_at"] == original["fetched_at"]
    assert stale["failure_class"] == "network_error"
    assert vietnam_foreign_flow_observability_snapshot()["stale_recoveries"] == 1


def test_cache_key_separates_ticker_limit_and_date_range():
    fetcher = _Fetcher([{"status": "ok", "rows": [_row(day) for day in range(1, 21)]}])
    service = VietnamForeignFlowService(fetcher)
    service.get_symbol_history("FPT", limit=5)
    service.get_symbol_history("FPT", limit=20)
    service.get_symbol_history("HPG", limit=5)
    service.get_symbol_history("FPT", from_date="2026-06-01", to_date="2026-06-02")
    assert len(fetcher.calls) == 4


def test_identical_force_and_normal_requests_share_one_provider_fetch():
    started = Event()
    release = Event()
    calls_lock = Lock()
    calls = 0

    class BlockingFetcher:
        def get_daily_stock_price(self, ticker, **kwargs):
            nonlocal calls
            with calls_lock:
                calls += 1
            started.set()
            assert release.wait(timeout=3)
            return {"status": "ok", "rows": [_row(1)]}

    service = VietnamForeignFlowService(BlockingFetcher())
    with ThreadPoolExecutor(max_workers=2) as executor:
        owner = executor.submit(service.get_symbol_history, "FPT", limit=1)
        assert started.wait(timeout=3)
        waiter = executor.submit(service.get_symbol_history, "FPT", limit=1, force_refresh=True)
        release.set()
        assert owner.result(timeout=3)["rows"] == waiter.result(timeout=3)["rows"]

    metrics = vietnam_foreign_flow_observability_snapshot()
    assert calls == 1
    assert metrics["coalesced_waiters"] == 1
    assert metrics["active_in_flight"] == 0
