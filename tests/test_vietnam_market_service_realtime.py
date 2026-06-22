from __future__ import annotations

from datetime import date, timedelta

from src.services.vietnam_market_service import (
    VietnamDashboardConfig,
    VietnamMarketService,
    clear_vietnam_cache,
)


class ExplodingManager:
    def _get_fetcher_by_name(self, name: str):  # pragma: no cover - failure path
        raise AssertionError(f"Legacy provider must not be requested in VN realtime path: {name}")

    def get_daily_data(self, *args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("Legacy daily data must not be requested in VN realtime path")


class FakeSsiFetcher:
    def __init__(self, realtime_payload=None, trade_payload=None):
        self.realtime_payload = realtime_payload
        self.trade_payload = trade_payload
        self.realtime_calls = 0
        self.trade_calls = 0

    def get_daily_ohlcv(self, symbol: str, **kwargs):
        start = date(2026, 6, 1)
        rows = []
        for index in range(30):
            rows.append(
                {
                    "date": (start + timedelta(days=index)).isoformat(),
                    "open": 100 + index,
                    "high": 102 + index,
                    "low": 99 + index,
                    "close": 101 + index,
                    "volume": 1_000_000 + index,
                    "value": 101_000_000 + index,
                    "source": "SSI",
                }
            )
        return {"status": "ok", "source": "SSI", "rows": rows}

    def get_daily_stock_price(self, symbol: str, **kwargs):
        return {
            "status": "ok",
            "source": "SSI",
            "rows": [
                {
                    "symbol": symbol,
                    "date": "2026-06-30",
                    "reference_price": 129.0,
                    "ceiling_price": 138.0,
                    "floor_price": 120.0,
                    "close": 130.0,
                    "matched_volume": 1_234_567,
                    "matched_value": 123_456_789_000,
                    "foreign_net_volume": 20_000,
                    "foreign_net_value": 2_000_000_000,
                    "source": "SSI",
                }
            ],
        }

    def get_intraday_ohlcv(self, symbol: str, **kwargs):
        return {"status": "unavailable", "source": "SSI", "reason": "SSI intraday unavailable", "rows": []}

    def get_realtime_snapshot(self, symbols):
        self.realtime_calls += 1
        if self.realtime_payload is not None:
            return self.realtime_payload
        symbol = symbols[0]
        return {
            "status": "ok",
            "source": "SSI",
            "requested_tickers": symbols,
            "quotes": [
                {
                    "ticker": symbol,
                    "source": "SSI",
                    "fetched_at": "2026-06-30T04:00:00+00:00",
                    "price": 130.5,
                    "change": 1.5,
                    "change_pct": 1.16,
                    "reference_price": 129.0,
                    "ceiling_price": 138.0,
                    "floor_price": 120.0,
                    "open": 129.5,
                    "high": 132.0,
                    "low": 128.0,
                    "volume": 1_234_567,
                    "value": 123_456_789_000,
                    "bid_levels": [{"price": 130.4, "volume": 1000}],
                    "ask_levels": [{"price": 130.6, "volume": 2000}],
                    "status": "ok",
                }
            ],
        }

    def get_trade_tape(self, symbol: str, **kwargs):
        self.trade_calls += 1
        if self.trade_payload is not None:
            return self.trade_payload
        return {
            "status": "ok",
            "source": "SSI",
            "symbol": symbol,
            "trades": [
                {
                    "time": "10:00:00",
                    "price": 130.5,
                    "volume": 1000,
                    "value": 130_500_000,
                    "side_if_available": "matched",
                    "sequence_if_available": "1",
                    "source": "SSI",
                }
            ],
        }

    def get_securities_details(self, **kwargs):
        symbol = kwargs.get("symbol") or "FPT"
        return {"status": "ok", "source": "SSI", "rows": [{"symbol": symbol, "exchange": "HOSE", "market": "HOSE", "source": "SSI"}]}

    def get_securities(self, **kwargs):
        return self.get_securities_details(symbol="FPT")


def _service(fetcher: FakeSsiFetcher, *, realtime_enabled: bool = True, trade_tape_enabled: bool = True) -> VietnamMarketService:
    clear_vietnam_cache()
    return VietnamMarketService(
        manager=ExplodingManager(),
        config=VietnamDashboardConfig(
            daily_data_provider="ssi",
            chart_data_provider="ssi",
            daily_stock_price_provider="ssi",
            index_data_provider="ssi",
            intraday_data_provider="ssi",
            ssi_intraday_enabled=True,
            realtime_data_provider="ssi",
            trade_tape_provider="ssi",
            ssi_realtime_enabled=realtime_enabled,
            ssi_trade_tape_enabled=trade_tape_enabled,
            kbs_enabled=False,
            allow_legacy_kbs_provider=False,
            include_intraday=True,
            news_provider="disabled",
            mozyfin_enabled=False,
            mozyfin_news_enabled=False,
        ),
        ssi_fetcher=fetcher,
    )


def test_ssi_realtime_success_returns_normalized_snapshot_and_daily_stays_ok(monkeypatch):
    monkeypatch.setenv("KBS_ENABLED", "true")
    fetcher = FakeSsiFetcher()

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["source"] == "SSI"
    assert item["actual_source"] == "SSI"
    assert item["fallback_used"] is False
    assert item["realtime_source"] == "SSI"
    assert item["realtime_status"]["status"] == "ok"
    assert item["realtime_snapshot"]["price"] == 130.5
    assert item["realtime_snapshot"]["bid_levels"][0]["price"] == 130.4
    assert fetcher.realtime_calls == 1


def test_ssi_realtime_failure_is_separate_from_daily_row():
    fetcher = FakeSsiFetcher(
        realtime_payload={
            "status": "unavailable",
            "source": "SSI",
            "reason": "SSI FastConnect realtime snapshot unavailable (attempted endpoints: RealtimeQuote, RealtimePrice). Last error: SSI FastConnect request failed",
            "requested_tickers": ["FPT"],
            "quotes": [],
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["daily_stock_price"]["status"] == "ok"
    assert item["realtime_source"] == "SSI"
    assert item["realtime_status"]["status"] == "unavailable"
    assert "realtime snapshot unavailable" in item["realtime_status"]["message"]
    assert "RealtimeQuote" in item["realtime_status"]["message"]


def test_ssi_trade_tape_success_returns_normalized_trades():
    fetcher = FakeSsiFetcher()

    service = _service(fetcher)
    endpoint_payload = service.build_trade_tape("FPT", force_refresh=True)
    item = service.build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert endpoint_payload["status"] == "ok"
    assert endpoint_payload["source"] == "SSI"
    assert endpoint_payload["trades"][0]["price"] == 130.5
    assert endpoint_payload["trades"][0]["value"] == 130_500_000
    assert item["trade_tape_source"] == "SSI"
    assert item["trade_tape_status"]["status"] == "ok"
    assert item["trade_tape"]["trades"][0]["sequence_if_available"] == "1"


def test_ssi_trade_tape_failure_is_separate_from_daily_row():
    fetcher = FakeSsiFetcher(
        trade_payload={
            "status": "unavailable",
            "source": "SSI",
            "symbol": "FPT",
            "reason": "SSI FastConnect trade tape unavailable (attempted endpoints: TradeTape, MatchedTrades). Last error: SSI FastConnect request failed",
            "trades": [],
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["trade_tape_source"] == "SSI"
    assert item["trade_tape_status"]["status"] == "unavailable"
    assert "trade tape unavailable" in item["trade_tape_status"]["message"]
    assert "TradeTape" in item["trade_tape_status"]["message"]


def test_realtime_and_trade_tape_can_be_disabled_without_kbs_fallback():
    fetcher = FakeSsiFetcher()

    item = _service(fetcher, realtime_enabled=False, trade_tape_enabled=False).build_watchlist(
        ["FPT"],
        force_refresh=True,
    )["watchlist"][0]

    assert item["status"] == "ok"
    assert item["realtime_source"] is None
    assert item["realtime_status"]["status"] == "disabled"
    assert item["trade_tape_source"] is None
    assert item["trade_tape_status"]["status"] == "disabled"
    assert fetcher.realtime_calls == 0
    assert fetcher.trade_calls == 0
