# -*- coding: utf-8 -*-

import importlib
from datetime import datetime

import pandas as pd
import pytest

from api.v1.endpoints.stocks import get_vietnam_realtime_quotes, get_vietnam_realtime_trades
from data_provider import vnstock_realtime_fetcher as provider
from data_provider.vnstock_realtime_fetcher import (
    VnstockRealtimeFetcher,
    clear_vnstock_realtime_cache,
)


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():
    clear_vnstock_realtime_cache()
    yield
    clear_vnstock_realtime_cache()


class _FakeTrading:
    def __init__(self, source=""):
        self.source = source

    def price_board(self, tickers):
        return pd.DataFrame(
            [
                {
                    "symbol": "FPT",
                    "time": "10:00:01",
                    "close_price": 123.4,
                    "reference_price": 120.0,
                    "open_price": 121.0,
                    "high_price": 124.0,
                    "low_price": 119.0,
                    "average_price": 122.0,
                    "price_change": 3.4,
                    "percent_change": 2.83,
                    "volume_accumulated": 1000,
                    "total_value": 123400,
                    "bid_price_1": 123.3,
                    "bid_vol_1": 100,
                    "ask_price_1": 123.5,
                    "ask_vol_1": 200,
                    "foreign_buy_volume": 10,
                    "foreign_sell_volume": 5,
                    "foreign_room": 100000,
                }
            ]
        )


class _FakeEquity:
    def __init__(self, symbol):
        self.symbol = symbol

    def trades(self):
        return pd.DataFrame(
            [
                {
                    "time": "10:00:02",
                    "price": 123.5,
                    "volume": 300,
                    "match_type": "buy",
                    "id": 1,
                }
            ]
        )


class _FakeMarket:
    def equity(self, symbol):
        return _FakeEquity(symbol)


def _fake_load_classes(self):
    return _FakeTrading, _FakeMarket


def test_vnstock_realtime_maps_close_price_to_separate_realtime_price(monkeypatch):
    monkeypatch.setattr(VnstockRealtimeFetcher, "_load_classes", _fake_load_classes)

    payload = VnstockRealtimeFetcher().fetch_quotes(["FPT"])
    quote = payload["quotes"][0]

    assert payload["source"] == "vnstock_kbs"
    assert payload["status"] == "ok"
    assert quote["symbol"] == "FPT"
    assert quote["realtime_price"] == 123.4
    assert quote["source"] == "vnstock_kbs"
    assert "latest_price" not in quote


def test_epoch_milliseconds_timestamp_maps_to_display_and_age(monkeypatch):
    row = {
        "symbol": "FPT",
        "time": 1781150988189,
        "close_price": 123.4,
    }
    fetcher = VnstockRealtimeFetcher()
    monkeypatch.setattr(
        provider,
        "_vn_now",
        lambda: datetime.fromisoformat("2026-06-11T11:10:00+07:00"),
    )

    quote = fetcher._map_quote("FPT", row)

    assert quote["realtime_time"] == "1781150988189"
    assert quote["realtime_time_display"].startswith("2026-06-11T11:09:48")
    assert quote["age_seconds"] == 11
    assert quote["is_stale"] is False
    assert quote["stale_reason"] is None


def test_datetime_string_timestamp_maps_to_display(monkeypatch):
    row = {
        "symbol": "FPT",
        "time": "2026-06-11 11:09:32",
        "close_price": 123.4,
    }
    fetcher = VnstockRealtimeFetcher()
    monkeypatch.setattr(
        provider,
        "_vn_now",
        lambda: datetime.fromisoformat("2026-06-11T11:10:00+07:00"),
    )

    quote = fetcher._map_quote("FPT", row)

    assert quote["realtime_time_display"] == "2026-06-11T11:09:32+07:00"
    assert quote["age_seconds"] == 28
    assert quote["is_stale"] is False


def test_missing_timestamp_does_not_crash(monkeypatch):
    fetcher = VnstockRealtimeFetcher()

    quote = fetcher._map_quote("FPT", {"symbol": "FPT", "close_price": 123.4})

    assert quote["realtime_time"] is None
    assert quote["age_seconds"] is None
    assert quote["is_stale"] is None
    assert quote["stale_reason"] == "timestamp_unparseable"


def test_stale_quote_is_marked_stale(monkeypatch):
    row = {
        "symbol": "FPT",
        "time": "2026-06-11 11:00:00",
        "close_price": 123.4,
    }
    fetcher = VnstockRealtimeFetcher()
    monkeypatch.setattr(
        provider,
        "_vn_now",
        lambda: datetime.fromisoformat("2026-06-11T11:10:00+07:00"),
    )

    quote = fetcher._map_quote("FPT", row)

    assert quote["age_seconds"] == 600
    assert quote["is_stale"] is True
    assert quote["stale_reason"] == "age_gt_60s"


def test_vnstock_missing_returns_unavailable(monkeypatch):
    original_import_module = importlib.import_module

    def fake_import_module(name, package=None):
        if name == "vnstock":
            raise ImportError("missing vnstock")
        return original_import_module(name, package)

    monkeypatch.setattr(provider.importlib, "import_module", fake_import_module)

    payload = VnstockRealtimeFetcher().fetch_quotes(["FPT", "ACB"])

    assert payload["status"] == "unavailable"
    assert payload["error"] == "vnstock is not installed"
    assert [quote["status"] for quote in payload["quotes"]] == ["unavailable", "unavailable"]


def test_vnstock_trades_mapping(monkeypatch):
    monkeypatch.setattr(VnstockRealtimeFetcher, "_load_classes", _fake_load_classes)

    payload = VnstockRealtimeFetcher().fetch_trades("FPT", limit=100)

    assert payload["status"] == "ok"
    assert payload["symbol"] == "FPT"
    assert payload["trades"] == [
        {
            "time": "10:00:02",
            "price": 123.5,
            "volume": 300.0,
            "match_type": "buy",
            "id": "1",
            "source": "vnstock_kbs",
        }
    ]


def test_realtime_endpoint_maps_quotes(monkeypatch):
    monkeypatch.setattr(VnstockRealtimeFetcher, "_load_classes", _fake_load_classes)

    response = get_vietnam_realtime_quotes("fpt")

    assert response.status == "ok"
    assert response.requested_tickers == ["FPT"]
    assert response.quotes[0].realtime_price == 123.4


def test_trades_endpoint_maps_trade_rows(monkeypatch):
    monkeypatch.setattr(VnstockRealtimeFetcher, "_load_classes", _fake_load_classes)

    response = get_vietnam_realtime_trades("fpt", limit=100)

    assert response.status == "ok"
    assert response.symbol == "FPT"
    assert response.trades[0].price == 123.5
