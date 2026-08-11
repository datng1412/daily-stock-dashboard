from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi import HTTPException

from api.v1.endpoints import stocks as stocks_endpoint
from api.v1.schemas.stocks import VietnamSectorStrengthResponse
from src.services.vietnam_sector_strength_service import (
    SECTOR_STRENGTH_MAX_CONCURRENCY,
    VietnamSectorStrengthService,
    calculate_sector_groups,
)


def _symbols() -> list[str]:
    return [f"S{index:02d}" for index in range(30)]


def _breadth(symbols: list[str], *, status: str = "ready") -> dict:
    items = []
    for index, symbol in enumerate(symbols):
        current = 101.0 if index % 3 == 0 else 99.0 if index % 3 == 1 else 100.0
        items.append({
            "symbol": symbol,
            "current_close": current,
            "previous_close": 100.0,
            "direction": "advance" if current > 100 else "decline" if current < 100 else "unchanged",
            "above_ma20": index % 2 == 0,
            "above_ma50": index % 4 == 0,
        })
    return {
        "status": status,
        "data_state": status,
        "usable": status != "unavailable",
        "provider_session_date": "2026-08-10",
        "finality": "completed_daily",
        "membership": {
            "status": "ready" if len(symbols) == 30 else "unavailable",
            "symbols": symbols,
            "cache_status": "hit",
        },
        "items": items,
        "diagnostics": {
            "provider_call_count": 0,
            "cache_hit_count": len(symbols),
            "cache_miss_count": 0,
        },
    }


def _flow_rows(count: int = 20, *, value: int = 10, anomaly_index: int | None = None) -> list[dict]:
    rows = []
    for index in range(count):
        rows.append({
            "trading_date": f"2026-07-{index + 1:02d}",
            "complete": True,
            "suspicious_zero_session": index == anomaly_index,
            "foreign_net_value": value,
        })
    return rows


def test_group_calculation_reconciles_members_and_uses_equal_weight_return():
    symbols = ["ADV", "DEC", "FLAT", "MISS"]
    classifications = {
        symbol: {"icb_code": "8300", "icb_name": "Banks"} for symbol in symbols
    }
    items = [
        {"symbol": "ADV", "current_close": 110, "previous_close": 100, "direction": "advance", "above_ma20": True, "above_ma50": True},
        {"symbol": "DEC", "current_close": 90, "previous_close": 100, "direction": "decline", "above_ma20": False, "above_ma50": False},
        {"symbol": "FLAT", "current_close": 100, "previous_close": 100, "direction": "unchanged", "above_ma20": False, "above_ma50": None},
        {"symbol": "MISS", "current_close": None, "previous_close": None, "direction": None, "above_ma20": None, "above_ma50": None},
    ]
    flow = {symbol: _flow_rows(value=0 if symbol == "FLAT" else 10) for symbol in symbols}

    group = calculate_sector_groups(
        member_symbols=symbols,
        classifications=classifications,
        breadth_items=items,
        accepted_flow_history=flow,
    )[0]

    assert group["member_symbols"] == symbols
    assert group["return_1d"] == {
        "value": pytest.approx(0.0),
        "usable_count": 3,
        "missing_count": 1,
        "method": "equal_weight_mean_member_close_return",
    }
    assert group["direction"] == {"advances": 1, "declines": 1, "unchanged": 1, "usable_count": 3}
    assert group["ma20"]["usable_count"] == 3
    assert group["ma20"]["above_count"] == 1
    assert group["ma50"]["usable_count"] == 2


def test_grouping_excludes_unclassified_and_never_duplicates_members():
    symbols = ["AAA", "BBB", "CCC"]
    groups = calculate_sector_groups(
        member_symbols=symbols,
        classifications={
            "AAA": {"icb_code": "1", "icb_name": "One"},
            "BBB": {"icb_code": "2", "icb_name": "Two"},
        },
        breadth_items=[],
        accepted_flow_history={},
    )
    flattened = [symbol for group in groups for symbol in group["member_symbols"]]
    assert sorted(flattened) == ["AAA", "BBB"]
    assert len(flattened) == len(set(flattened))


def test_completed_flow_windows_preserve_zero_and_exclude_anomaly_or_missing():
    symbols = ["ZERO", "ANOMALY", "MISSING"]
    group = calculate_sector_groups(
        member_symbols=symbols,
        classifications={symbol: {"icb_code": "1", "icb_name": "One"} for symbol in symbols},
        breadth_items=[],
        accepted_flow_history={
            "ZERO": _flow_rows(value=0),
            "ANOMALY": _flow_rows(value=10, anomaly_index=0),
            "MISSING": _flow_rows(count=4, value=10),
        },
    )[0]
    one_day = group["foreign_flow"]["windows"]["1"]
    five_day = group["foreign_flow"]["windows"]["5"]
    twenty_day = group["foreign_flow"]["windows"]["20"]
    assert one_day["usable_member_count"] == 3
    assert one_day["net_value"] == 20
    assert five_day["usable_member_count"] == 2
    assert five_day["net_value"] == 50
    assert twenty_day["usable_member_count"] == 1
    assert twenty_day["net_value"] == 0
    assert twenty_day["complete"] is False


class _BreadthService:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = []

    def build(self, **kwargs):
        self.calls.append(kwargs)
        return deepcopy(self.payload)


class _MarketService:
    def __init__(self, symbols: list[str], *, omit: str | None = None):
        self.symbols = symbols
        self.omit = omit
        self.calls = []

    def build_index_components(self, index_code, force_refresh=False):
        self.calls.append((index_code, force_refresh))
        return {
            "status": "ok",
            "rows": [
                {
                    "symbol": symbol,
                    "icb_code": "8300" if index < 15 else "9500",
                    "icb_name": "Banks" if index < 15 else "Technology",
                }
                for index, symbol in enumerate(self.symbols)
                if symbol != self.omit
            ],
            "diagnostics": {"cache_status": "hit"},
        }


class _FlowBatchService:
    def __init__(self):
        self.calls = []

    def get_watchlist(self, tickers, *, sessions, force_refresh):
        self.calls.append((list(tickers), sessions, force_refresh))
        return {
            "data_state": "ready",
            "items": [{"ticker": ticker, "cache_state": "hit"} for ticker in tickers],
        }


def _service(*, member_count: int = 30, omit: str | None = None):
    symbols = _symbols()[:member_count]
    breadth = _BreadthService(_breadth(symbols))
    market = _MarketService(symbols, omit=omit)
    flow = _FlowBatchService()
    metrics = iter([{"provider_calls": 5}, {"provider_calls": 5}])
    service = VietnamSectorStrengthService(
        market_service=market,
        breadth_service=breadth,
        flow_batch_service=flow,
        accepted_history_reader=lambda requested: {symbol: _flow_rows() for symbol in requested},
        flow_metrics_reader=lambda: next(metrics),
    )
    return service, breadth, market, flow


def test_service_reuses_breadth_cache_and_completed_flow_without_watchlist_hydration():
    service, breadth, market, flow = _service(omit="S29")
    result = service.build()
    assert result["status"] == "partial"
    assert result["membership"]["member_count"] == 30
    assert result["membership"]["classified_count"] == 29
    assert result["membership"]["unclassified_symbols"] == ["S29"]
    assert sum(group["member_count"] for group in result["groups"]) + 1 == 30
    assert market.calls == [("VN30", False)]
    assert breadth.calls == [{"index_code": "VN30", "force_refresh": False}]
    assert len(flow.calls) == 1
    assert result["diagnostics"]["daily_ohlc_provider_call_count"] == 0
    assert result["diagnostics"]["daily_ohlc_cache_hit_count"] == 30
    assert result["diagnostics"]["full_watchlist_hydration_used"] is False
    assert result["diagnostics"]["current_foreign_flow_included"] is False
    assert result["diagnostics"]["max_concurrency"] == SECTOR_STRENGTH_MAX_CONCURRENCY
    VietnamSectorStrengthResponse(**result)


def test_inexact_membership_stops_before_foreign_flow_calls():
    service, _breadth_service, _market, flow = _service(member_count=29)
    result = service.build()
    assert result["status"] == "unavailable"
    assert result["groups"] == []
    assert flow.calls == []
    assert result["diagnostics"]["foreign_flow_provider_call_count"] == 0


def test_price_and_completed_flow_dates_remain_independently_visible():
    service, *_ = _service()
    result = service.build()
    assert result["price_session_date"] == "2026-08-10"
    assert result["foreign_flow_latest_completed_date"] == "2026-07-20"
    assert result["usable"] is True


def test_route_serializes_and_rejects_unsupported_scope(monkeypatch):
    payload = _service()[0].build()

    class _RouteService:
        def build(self, **kwargs):
            if kwargs["index_code"] != "VN30":
                raise ValueError("VN-SECTOR-1 supports index_code=VN30 only")
            return payload

    monkeypatch.setattr(stocks_endpoint, "VietnamSectorStrengthService", _RouteService)
    response = stocks_endpoint.get_vietnam_sector_strength("VN30", False)
    assert response.membership.member_count == 30
    assert response.official_sector_index_return is False
    with pytest.raises(HTTPException) as error:
        stocks_endpoint.get_vietnam_sector_strength("HOSE", False)
    assert error.value.status_code == 422
