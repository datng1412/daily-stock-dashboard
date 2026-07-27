from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from threading import Lock
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import stocks
from src.services.vietnam_foreign_flow_service import (
    VietnamForeignFlowBatchService,
    VietnamForeignFlowService,
    normalize_vietnam_foreign_flow_tickers,
    reset_vietnam_foreign_flow_state,
)


def _row(index: int, *, net_value: int | None = 10, anomaly: bool = False):
    return {
        "trading_date": f"2026-06-{index + 1:02d}" if index < 29 else f"2026-07-{index - 28:02d}",
        "foreign_buy_volume": 20 if net_value is not None else None,
        "foreign_sell_volume": 5 if net_value is not None else None,
        "foreign_net_volume": 15 if net_value is not None else None,
        "foreign_buy_value": 30 if net_value is not None else None,
        "foreign_sell_value": 20 if net_value is not None else None,
        "foreign_net_value": net_value,
        "suspicious_zero_session": anomaly,
        "anomaly_code": "all_foreign_gross_fields_explicit_zero" if anomaly else None,
    }


def _history(
    ticker: str,
    *,
    count: int = 60,
    net_values: list[int | None] | None = None,
    state: str = "ready",
    failure_class: str | None = None,
):
    values = net_values if net_values is not None else [10] * count
    rows = [_row(index, net_value=value, anomaly=value == 0) for index, value in enumerate(values)]
    return {
        "ticker": ticker,
        "source": "ssi_fastconnect",
        "source_endpoint": "daily_stock_price",
        "provider_version": "v3",
        "data_state": state,
        "freshness": "stale" if state == "stale" else "fresh",
        "rows": rows if state in {"ready", "stale"} else [],
        "latest_row": rows[-1] if rows and state in {"ready", "stale"} else None,
        "fetched_at": "2026-07-21T09:00:00+00:00",
        "cache_state": "hit",
        "cache_age_seconds": 12.5,
        "failure_class": failure_class,
    }


class _SymbolService:
    def __init__(self, histories):
        self.histories = histories
        self.calls: list[tuple[str, dict]] = []

    def get_symbol_history(self, ticker, **kwargs):
        self.calls.append((ticker, kwargs))
        value = self.histories[ticker]
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    return TestClient(app)


def test_watchlist_normalization_bounds_and_no_default():
    requested, normalized = normalize_vietnam_foreign_flow_tickers([" fpt ", "FPT.VN", "ssi"])
    assert requested == ["fpt", "FPT.VN", "ssi"]
    assert normalized == ["FPT", "SSI"]

    with pytest.raises(ValueError):
        normalize_vietnam_foreign_flow_tickers([])
    with pytest.raises(ValueError):
        normalize_vietnam_foreign_flow_tickers(["F PT"])
    with pytest.raises(ValueError):
        normalize_vietnam_foreign_flow_tickers([f"A{index:02d}" for index in range(31)])
    assert len(normalize_vietnam_foreign_flow_tickers([f"A{index:02d}" for index in range(30)])[1]) == 30


def test_watchlist_returns_all_windows_streaks_anomalies_and_preserves_order():
    fpt_values = [10] * 57 + [0, 10, 10]
    service = _SymbolService({
        "SSI": _history("SSI", net_values=[-10] * 60),
        "FPT": _history("FPT", net_values=fpt_values),
    })
    payload = VietnamForeignFlowBatchService(service, max_concurrency=1).get_watchlist(
        ["ssi", "FPT", "SSI"],
        sessions=60,
    )

    assert payload["status"] == "ready"
    assert payload["duplicate_tickers_removed"] == 1
    assert [item["ticker"] for item in payload["items"]] == ["SSI", "FPT"]
    fpt = payload["items"][1]
    assert fpt["buy_value_1d"] == 30
    assert fpt["sell_value_5d"] == 100
    assert fpt["net_value_20d"] == 190
    assert fpt["net_volume_60d"] == 900
    assert fpt["buy_streak"] == 2
    assert fpt["sell_streak"] == 0
    assert fpt["streak_metric_basis"] == "foreign_net_value"
    assert fpt["contains_provider_anomaly"] is True
    assert fpt["anomaly_count"] == 1
    assert service.calls == [
        ("SSI", {"limit": 60, "force_refresh": False}),
        ("FPT", {"limit": 60, "force_refresh": False}),
    ]


def test_ten_symbol_watchlist_loads_each_unique_history_once():
    tickers = [f"A{index:02d}" for index in range(10)]
    service = _SymbolService({
        ticker: _history(ticker)
        for ticker in tickers
    })

    payload = VietnamForeignFlowBatchService(service).get_watchlist(
        [tickers[0].lower(), *tickers, tickers[-1]],
        sessions=60,
    )

    assert payload["normalized_tickers"] == tickers
    assert len(service.calls) == 10
    assert sorted(ticker for ticker, _kwargs in service.calls) == tickers
    assert all(
        kwargs == {"limit": 60, "force_refresh": False}
        for _ticker, kwargs in service.calls
    )


def test_watchlist_incomplete_and_null_windows_remain_null_but_real_zero_survives():
    service = _SymbolService({
        "FPT": _history("FPT", count=5, net_values=[10, 10, None, 10, 0]),
    })
    payload = VietnamForeignFlowBatchService(service).get_watchlist(["FPT"], sessions=60)
    item = payload["items"][0]

    assert payload["status"] == "partial"
    assert item["availability"] == "partial"
    assert item["actual_session_count"] == 5
    assert item["complete"] is False
    assert item["net_value_1d"] == 0
    assert item["net_value_5d"] is None
    assert item["net_value_20d"] is None
    assert item["net_value_60d"] is None
    assert item["buy_streak"] == item["sell_streak"] == 0


@pytest.mark.parametrize(
    ("failure", "public_failure"),
    [
        ("auth_failed", "authentication"),
        ("permission_denied", "authorization"),
        ("timeout", "timeout"),
        ("network_error", "provider_unavailable"),
    ],
)
def test_watchlist_failure_class_is_truthful_not_unsupported(failure, public_failure):
    service = _SymbolService({
        "FPT": _history("FPT", state="unavailable", failure_class=failure),
    })
    payload = VietnamForeignFlowBatchService(service).get_watchlist(["FPT"])
    assert payload["status"] == "unavailable"
    assert payload["items"][0]["failure_class"] == public_failure
    assert payload["items"][0]["failure_class"] != "unsupported"


def test_one_failure_isolated_and_observed_session_lag_is_not_calendar_filled():
    newer = _history("FPT")
    older = _history("SSI")
    older["rows"][-1]["trading_date"] = "2026-07-18"
    payload = VietnamForeignFlowBatchService(_SymbolService({
        "FPT": newer,
        "SSI": older,
        "HPG": RuntimeError("private provider detail"),
    })).get_watchlist(["FPT", "SSI", "HPG"], sessions=60)

    assert payload["status"] == "partial"
    assert payload["ready_symbol_count"] == 2
    assert payload["unavailable_symbol_count"] == 1
    assert payload["items"][0]["source_session_lag"] == 0
    assert payload["items"][1]["source_session_lag"] == 1
    assert "private provider detail" not in str(payload)


def test_watchlist_concurrency_and_total_timeout_are_bounded():
    lock = Lock()
    active = maximum = 0

    class SlowService:
        def get_symbol_history(self, ticker, **kwargs):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.08 if ticker == "SLOW" else 0.01)
            with lock:
                active -= 1
            return _history(ticker)

    service = VietnamForeignFlowBatchService(
        SlowService(),
        max_concurrency=2,
        per_ticker_timeout_seconds=0.03,
        total_timeout_seconds=0.04,
    )
    started = time.perf_counter()
    payload = service.get_watchlist(["FPT", "SLOW", "SSI"], sessions=60)
    elapsed = time.perf_counter() - started

    assert 1 < maximum <= 2
    assert elapsed < 0.2
    assert [item["ticker"] for item in payload["items"]] == ["FPT", "SLOW", "SSI"]
    assert next(item for item in payload["items"] if item["ticker"] == "SLOW")["failure_class"] == "timeout"


def test_watchlist_api_validates_and_returns_typed_payload(monkeypatch):
    class FakeBatch:
        def get_watchlist(self, tickers, **kwargs):
            return VietnamForeignFlowBatchService(
                _SymbolService({"FPT": _history("FPT")}),
                max_concurrency=1,
            ).get_watchlist(tickers, **kwargs)

    monkeypatch.setattr(stocks, "VietnamForeignFlowBatchService", FakeBatch)
    client = _client()
    response = client.get(
        "/api/v1/stocks/vn/foreign-flow/watchlist",
        params={"tickers": " fpt ,FPT", "sessions": 60},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["normalized_tickers"] == ["FPT"]
    assert body["items"][0]["net_value_60d"] == 600
    assert "rows" not in body["items"][0]

    assert client.get("/api/v1/stocks/vn/foreign-flow/watchlist").status_code == 400
    assert client.get(
        "/api/v1/stocks/vn/foreign-flow/watchlist",
        params={"tickers": "FPT", "sessions": 2},
    ).status_code == 400


def test_watchlist_reuses_raw_history_cache_and_force_refresh_is_scoped():
    reset_vietnam_foreign_flow_state()

    class Fetcher:
        def __init__(self):
            self.calls: list[str] = []

        def get_daily_stock_price(self, ticker, **_kwargs):
            self.calls.append(ticker)
            start = date(2026, 4, 1)
            return {
                "status": "ok",
                "rows": [{
                    "date": (start + timedelta(days=index)).isoformat(),
                    "foreign_buy_volume": 20,
                    "foreign_sell_volume": 5,
                    "foreign_net_volume": 15,
                    "foreign_buy_value": 30,
                    "foreign_sell_value": 20,
                    "foreign_net_value": 10,
                } for index in range(60)],
            }

    fetcher = Fetcher()
    service = VietnamForeignFlowBatchService(
        VietnamForeignFlowService(fetcher),
        max_concurrency=1,
    )
    first = service.get_watchlist(["FPT", "FPT"], sessions=60)
    second = service.get_watchlist(["FPT"], sessions=60)
    refreshed = service.get_watchlist(["FPT"], sessions=60, force_refresh=True)

    assert fetcher.calls == ["FPT", "FPT"]
    assert first["items"][0]["cache_state"] == "miss"
    assert second["items"][0]["cache_state"] == "hit"
    assert refreshed["items"][0]["cache_state"] == "refresh"
    assert first["items"][0]["net_value_60d"] == 600
