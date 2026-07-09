# -*- coding: utf-8 -*-

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from api.v1.endpoints.stocks import (
    _get_vietnam_realtime_quotes_impl,
    get_vietnam_observability,
    get_vietnam_realtime_quotes,
    get_vietnam_realtime_trades,
)
from data_provider import vnstock_realtime_fetcher as kbs_provider
from data_provider.vnstock_realtime_fetcher import VnstockRealtimeFetcher, clear_vnstock_realtime_cache
from src.services import vietnam_market_service as vn_service
from src.services.vietnam_market_service import VietnamDashboardConfig, VietnamMarketService, clear_vietnam_cache
from src.services.vietnam_observability import reset_vietnam_observability


@pytest.fixture(autouse=True)
def _reset_state():
    clear_vietnam_cache()
    clear_vnstock_realtime_cache()
    reset_vietnam_observability()
    yield
    clear_vietnam_cache()
    clear_vnstock_realtime_cache()
    reset_vietnam_observability()


class _StubFetcher:
    fixture_dir = Path("__missing_fixture_dir__")

    def get_foreign_trading(self, symbol):
        return {"buy": 10, "sell": 5, "net": 5}

    def get_intraday_ohlcv(self, symbol, timeframe="1h", limit=8):
        return pd.DataFrame(
            [
                {"timestamp": 1, "date_time": "2026-06-11T03:00:00+00:00", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
                {"timestamp": 2, "date_time": "2026-06-11T04:00:00+00:00", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1100},
                {"timestamp": 3, "date_time": "2026-06-11T05:00:00+00:00", "open": 101, "high": 103, "low": 100, "close": 102, "volume": 1200},
            ]
        )

    def get_news(self, symbol, limit=3):
        return []


class _StubManager:
    def __init__(self):
        self.fetcher = _StubFetcher()

    def get_daily_data(self, stock_code, days=30):
        return pd.DataFrame(
            [
                {"date": f"2026-05-{day:02d}", "open": 10 + day, "high": 11 + day, "low": 9 + day, "close": 10 + day, "volume": 1000 + day}
                for day in range(1, 22)
            ]
        ), "MozyfinFetcher"

    def _get_fetcher_by_name(self, name):
        return self.fetcher if name == "MozyfinFetcher" else None


class _FakeTrading:
    def __init__(self, source=""):
        self.source = source

    def price_board(self, tickers):
        return pd.DataFrame(
            [
                {
                    "symbol": "FPT",
                    "time": "2026-06-11 10:00:00",
                    "close_price": 100,
                }
            ]
        )


class _FakeEquity:
    def __init__(self, symbol):
        self.symbol = symbol

    def trades(self):
        return pd.DataFrame([{"time": "10:00:01", "price": 100, "volume": 100, "match_type": "buy", "id": 1}])


class _FakeMarket:
    def equity(self, symbol):
        return _FakeEquity(symbol)


class _UnavailableTrading:
    def __init__(self, source=""):
        self.source = source

    def price_board(self, tickers):
        raise RuntimeError("secret-token-123 upstream timeout")


def _fake_load_classes(self):
    return _FakeTrading, _FakeMarket


def _unavailable_load_classes(self):
    return _UnavailableTrading, _FakeMarket


def test_observability_endpoint_returns_default_counters_without_prior_requests():
    payload = get_vietnam_observability().model_dump()

    assert payload["market"] == "VN"
    assert payload["status"] == "ok"
    assert payload["mozyfin"] == {
        "status": "disabled",
        "source": "legacy",
        "reason": "Mozyfin is disabled for VN dashboard runtime.",
    }
    assert payload["dashboard_runtime"]["watchlist_requests_total"] == 0
    assert payload["dashboard_runtime"]["watchlist_cache_hits_total"] == 0
    assert payload["kbs"]["status"] == "disabled"
    assert payload["kbs"]["enabled"] is False
    assert payload["kbs"]["legacy_allowed"] is False
    assert payload["kbs"]["quote_requests_total"] == 0
    assert payload["kbs"]["trade_requests_total"] == 0
    assert payload["ssi_core"]["source"] == "SSI"
    assert payload["ssi_core"]["status"] in {"disabled", "ok", "unavailable"}
    assert payload["ssi_intraday"]["source"] == "SSI"
    assert payload["ssi_intraday"]["status"] in {"disabled", "ok", "unavailable"}
    assert payload["ssi_realtime"]["source"] == "SSI"
    assert payload["ssi_trade_tape"]["source"] == "SSI"


def test_observability_endpoint_does_not_construct_mozyfin_manager(monkeypatch):
    def fail_manager(*args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("Observability must not construct VN data providers")

    monkeypatch.setattr(vn_service, "DataFetcherManager", fail_manager)

    payload = get_vietnam_observability().model_dump()

    assert payload["status"] == "ok"
    assert payload["mozyfin"]["status"] == "disabled"


def test_watchlist_request_updates_provider_neutral_observability_counters(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    service = VietnamMarketService(manager=_StubManager(), config=VietnamDashboardConfig(history_days=30, news_limit=1))

    service.build_watchlist(["FPT"])
    payload = get_vietnam_observability().model_dump()

    assert payload["mozyfin"]["status"] == "disabled"
    assert "watchlist_requests_total" not in payload["mozyfin"]
    assert payload["dashboard_runtime"]["watchlist_requests_total"] == 1
    assert payload["dashboard_runtime"]["watchlist_cache_misses_total"] >= 1
    assert payload["dashboard_runtime"]["last_watchlist_request_at"]
    assert payload["dashboard_runtime"]["last_fetch_at"]
    assert payload["dashboard_runtime"]["last_tickers_count"] == 1
    assert payload["dashboard_runtime"]["last_fetch_duration_ms"] is not None


def test_realtime_endpoints_default_to_ssi_and_do_not_call_kbs(monkeypatch):
    class StubVietnamMarketService:
        config = SimpleNamespace(allow_legacy_kbs_provider=False, kbs_enabled=False)

        def build_realtime_snapshot(self, symbols):
            return {
                "market": "VN",
                "source": "SSI",
                "status": "ok",
                "requested_tickers": symbols,
                "quotes": [{"symbol": "FPT", "ticker": "FPT", "source": "SSI", "status": "ok", "price": 100}],
                "cache": {},
            }

        def build_trade_tape(self, symbol, *, limit=100):
            return {
                "market": "VN",
                "source": "SSI",
                "symbol": symbol,
                "status": "ok",
                "trades": [{"time": "10:00:00", "price": 100, "volume": 100, "source": "SSI"}],
                "cache": {},
            }

    def fail_kbs(*args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("KBS must not be called when legacy mode is disabled")

    monkeypatch.setattr("api.v1.endpoints.stocks.VietnamMarketService", StubVietnamMarketService)
    monkeypatch.setattr(VnstockRealtimeFetcher, "fetch_quotes", fail_kbs)
    monkeypatch.setattr(VnstockRealtimeFetcher, "fetch_trades", fail_kbs)

    quote_response = _get_vietnam_realtime_quotes_impl("FPT")
    trade_response = get_vietnam_realtime_trades("FPT", limit=100)
    payload = get_vietnam_observability().model_dump()

    assert quote_response.source == "SSI"
    assert quote_response.quotes[0].source == "SSI"
    assert trade_response.source == "SSI"
    assert trade_response.trades[0].source == "SSI"
    assert payload["kbs"]["quote_requests_total"] == 0
    assert payload["kbs"]["trade_requests_total"] == 0


def test_observability_does_not_return_raw_full_provider_errors():
    payload = get_vietnam_observability().model_dump()

    assert payload["kbs"]["status"] == "disabled"
    assert "secret-token-123" not in str(payload)
    assert "raw_error" not in payload["kbs"]


def test_observability_endpoint_does_not_crash_when_realtime_is_unavailable():
    payload = get_vietnam_observability().model_dump()

    assert payload["status"] == "ok"
    assert payload["ssi_core"]["status"] in {"unavailable", "disabled", "not_implemented", "ok", "error"}
    assert payload["ssi_intraday"]["status"] in {"unavailable", "disabled", "not_implemented", "ok", "error"}
    assert payload["ssi_realtime"]["status"] in {"unavailable", "disabled", "not_implemented", "ok", "error"}


def test_observability_update_failure_does_not_break_watchlist(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)

    def fail_observe(*args, **kwargs):
        raise RuntimeError("observability failed")

    monkeypatch.setattr(vn_service, "observe_mozyfin_watchlist_request", fail_observe)
    monkeypatch.setattr(vn_service, "observe_mozyfin_cache_result", fail_observe)

    service = VietnamMarketService(manager=_StubManager(), config=VietnamDashboardConfig(history_days=30, news_limit=1))
    payload = service.build_watchlist(["FPT", "FPT"])

    assert payload["market"] == "VN"
    assert [item["ticker"] for item in payload["watchlist"]] == ["FPT"]
