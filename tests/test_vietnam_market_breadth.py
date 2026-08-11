from __future__ import annotations

import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pandas as pd
import pytest
from fastapi import HTTPException

from api.v1.endpoints import stocks as stocks_endpoint
from api.v1.schemas.stocks import VietnamMarketBreadthResponse
from src.services.vietnam_market_breadth_service import (
    VN30_BREADTH_MAX_WORKERS,
    VietnamMarketBreadthService,
    calculate_vn30_breadth,
    normalize_vn30_members,
)
from src.services.vietnam_market_service import VietnamMarketService, clear_vietnam_cache


def _history(
    *,
    count: int = 55,
    end: date = date(2026, 8, 7),
    previous: float = 100.0,
    current: float | None = 101.0,
) -> pd.DataFrame:
    rows = []
    for index in range(count):
        close = 100.0
        if index == count - 2:
            close = previous
        if index == count - 1:
            close = current
        rows.append(
            {
                "date": end - timedelta(days=count - index - 1),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 1_000,
            }
        )
    return pd.DataFrame(rows)


def _payload(frame: pd.DataFrame, cache_status: str = "hit") -> dict:
    return {
        "status": "ok",
        "dataframe": frame,
        "cache_status": cache_status,
        "provider_meta": {
            "diagnostics": {
                "freshness_status": "fresh",
                "latest_completed_session": "2026-08-07",
            }
        },
    }


def test_normalize_members_is_unique_deterministic_and_never_falls_back():
    result = normalize_vn30_members(
        [{"symbol": " hpg "}, {"symbol": "FPT"}, {"symbol": "HPG"}, {"symbol": "!"}]
    )
    assert result == {
        "symbols": ["FPT", "HPG"],
        "duplicate_symbols": ["HPG"],
        "duplicate_count": 1,
        "invalid_count": 1,
    }


def test_calculation_reconciles_direction_ma_and_participation_with_equal_not_above():
    symbols = ["ADV", "DEC", "FLAT"]
    histories = {
        "ADV": _payload(_history(previous=100, current=110)),
        "DEC": _payload(_history(previous=100, current=90)),
        "FLAT": _payload(_history(previous=100, current=100)),
    }
    result = calculate_vn30_breadth(symbols, histories)
    assert result["provider_session_date"] == "2026-08-07"
    assert result["direction"] == {"advances": 1, "declines": 1, "unchanged": 1, "usable_count": 3}
    assert result["participation"]["ratio"] == pytest.approx(2 / 3)
    assert result["ma20"]["above_count"] == 1
    assert result["ma20"]["not_above_count"] == 2
    assert result["ma20"]["usable_count"] == 3
    assert result["ma50"]["above_count"] == 1
    assert result["ma50"]["not_above_count"] == 2
    assert result["ma50"]["usable_count"] == 3


def test_session_mismatch_is_excluded_without_forward_fill_and_missing_is_not_zero():
    symbols = ["CURRENT", "STALE", "MISSING"]
    histories = {
        "CURRENT": _payload(_history()),
        "STALE": _payload(_history(end=date(2026, 8, 6))),
        "MISSING": _payload(pd.DataFrame()),
    }
    result = calculate_vn30_breadth(symbols, histories)
    assert result["coverage"]["observed_count"] == 2
    assert result["coverage"]["aligned_count"] == 1
    assert result["coverage"]["session_mismatch_symbols"] == ["STALE"]
    assert result["coverage"]["missing_symbols"] == ["STALE", "MISSING"]
    stale = next(item for item in result["items"] if item["symbol"] == "STALE")
    assert stale["direction"] is None
    assert stale["current_close"] is None


def test_independent_ma_denominators_and_zero_denominators_return_null_not_nan():
    symbols = ["SHORT", "INVALID"]
    histories = {
        "SHORT": _payload(_history(count=25)),
        "INVALID": _payload(_history(count=25, current=None)),
    }
    result = calculate_vn30_breadth(symbols, histories)
    assert result["coverage"]["direction_usable_count"] == 1
    assert result["coverage"]["ma20_usable_count"] == 1
    assert result["coverage"]["ma50_usable_count"] == 0
    assert result["ma50"]["percent_above"] is None
    assert result["participation"]["ratio"] == 1
    assert not any(
        isinstance(value, float) and (math.isnan(value) or math.isinf(value))
        for block in (result["participation"], result["ma20"], result["ma50"])
        for value in block.values()
    )


class _FakeMarketService:
    def __init__(self, member_count: int = 30, histories: dict | None = None, delay: float = 0.0):
        self.symbols = [f"S{index:02d}" for index in range(member_count)]
        self.histories = histories or {symbol: _payload(_history()) for symbol in self.symbols}
        self.calls = []
        self.delay = delay
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def build_index_components(self, index_code, force_refresh=False):
        return {
            "status": "ok",
            "rows": [{"symbol": symbol} for symbol in self.symbols],
            "diagnostics": {"cache_status": "hit", "cache_fetched_at": "2026-08-07T10:00:00Z"},
        }

    def read_daily_ohlcv_history(self, symbol, **kwargs):
        self.calls.append((symbol, kwargs))
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                time.sleep(self.delay)
            return self.histories[symbol]
        finally:
            with self.lock:
                self.active -= 1


def test_service_requires_exact_authoritative_membership_before_history_fanout():
    fake = _FakeMarketService(member_count=29)
    result = VietnamMarketBreadthService(fake).build()
    assert result["status"] == "unavailable"
    assert result["usable"] is False
    assert result["items"] == []
    assert fake.calls == []
    assert result["diagnostics"]["fallback_used"] is False


def test_service_uses_minimal_history_cache_path_and_bounded_concurrency():
    fake = _FakeMarketService(delay=0.005)
    result = VietnamMarketBreadthService(fake).build()
    assert result["status"] == "ready"
    assert len(fake.calls) == 30
    assert all(call[1]["limit"] == 55 for call in fake.calls)
    assert fake.max_active <= VN30_BREADTH_MAX_WORKERS
    assert result["diagnostics"]["full_watchlist_hydration_used"] is False
    assert result["diagnostics"]["provider_call_count"] == 0
    assert result["diagnostics"]["cache_hit_count"] == 30
    assert result["coverage"]["direction_usable_count"] == 30
    VietnamMarketBreadthResponse(**result)


def test_service_rejects_non_vn30_scope():
    with pytest.raises(ValueError, match="VN30 only"):
        VietnamMarketBreadthService(_FakeMarketService()).build("HOSE")


def test_api_route_serializes_service_contract(monkeypatch):
    payload = VietnamMarketBreadthService(_FakeMarketService()).build()

    class _RouteService:
        def build(self, **kwargs):
            assert kwargs == {"index_code": "VN30", "force_refresh": False}
            return payload

    monkeypatch.setattr(stocks_endpoint, "VietnamMarketBreadthService", _RouteService)
    response = stocks_endpoint.get_vietnam_market_breadth("VN30", False)
    assert response.index_code == "VN30"
    assert response.direction.usable_count == 30
    assert response.diagnostics["fallback_used"] is False


def test_api_route_rejects_unsupported_scope(monkeypatch):
    class _RouteService:
        def build(self, **kwargs):
            raise ValueError("VN-BREADTH-1 supports index_code=VN30 only")

    monkeypatch.setattr(stocks_endpoint, "VietnamMarketBreadthService", _RouteService)
    with pytest.raises(HTTPException) as error:
        stocks_endpoint.get_vietnam_market_breadth("HOSE", False)
    assert error.value.status_code == 422


def test_minimal_daily_history_reader_reuses_cache_and_coalesces_same_key():
    clear_vietnam_cache()

    class _DailyProvider:
        def __init__(self):
            self.calls = 0
            self.lock = threading.Lock()

        def get_daily_ohlcv(self, symbol, **kwargs):
            with self.lock:
                self.calls += 1
            time.sleep(0.01)
            return {
                "status": "ok",
                "rows": _history().assign(date=lambda frame: frame["date"].astype(str)).to_dict("records"),
                "diagnostics": {
                    "freshness_status": "fresh",
                    "latest_completed_session": "2026-08-07",
                },
            }

    provider = _DailyProvider()
    service = VietnamMarketService(ssi_rest_provider=provider)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: service.read_daily_ohlcv_history("FPT"), range(4)))
    assert provider.calls == 1
    assert sum(result["cache_status"] == "hit" for result in results) == 3
    assert all(len(result["dataframe"]) == 55 for result in results)
    clear_vietnam_cache()
