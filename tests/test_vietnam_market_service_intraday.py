from __future__ import annotations

from datetime import date, timedelta

from src.services.vietnam_market_service import (
    VietnamDashboardConfig,
    VietnamMarketService,
    clear_vietnam_cache,
)


class ExplodingManager:
    def _get_fetcher_by_name(self, name: str):  # pragma: no cover - failure path
        raise AssertionError(f"Mozyfin must not be requested in VN intraday path: {name}")

    def get_daily_data(self, *args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("Mozyfin daily data must not be requested in VN intraday path")


class FakeSsiFetcher:
    def __init__(self, intraday_payload=None):
        self.intraday_payload = intraday_payload
        self.intraday_calls = 0

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
        self.intraday_calls += 1
        if self.intraday_payload is not None:
            return self.intraday_payload
        return {
            "status": "ok",
            "source": "SSI",
            "rows": [
                {
                    "date_time": "2026-06-30T10:00:00+07:00",
                    "timestamp": 1782788400,
                    "open": 131.0,
                    "high": 132.0,
                    "low": 130.5,
                    "close": 131.5,
                    "volume": 2000,
                    "ticker": symbol,
                    "source": "SSI",
                },
                {
                    "date_time": "2026-06-30T09:00:00+07:00",
                    "timestamp": 1782784800,
                    "open": 130.0,
                    "high": 131.0,
                    "low": 129.5,
                    "close": 130.5,
                    "volume": 1000,
                    "ticker": symbol,
                    "source": "SSI",
                },
                {
                    "date_time": "2026-06-30T11:00:00+07:00",
                    "timestamp": 1782792000,
                    "open": 131.5,
                    "high": 133.0,
                    "low": 131.0,
                    "close": 132.5,
                    "volume": 3000,
                    "ticker": symbol,
                    "source": "SSI",
                },
            ],
        }

    def get_realtime_snapshot(self, symbols):
        return {
            "status": "unavailable",
            "source": "SSI",
            "reason": "SSI realtime unavailable",
            "requested_tickers": symbols,
            "quotes": [],
        }

    def get_trade_tape(self, symbol: str, **kwargs):
        return {
            "status": "unavailable",
            "source": "SSI",
            "symbol": symbol,
            "reason": "SSI trade tape unavailable",
            "trades": [],
        }

    def get_securities_details(self, **kwargs):
        symbol = kwargs.get("symbol") or "FPT"
        return {
            "status": "ok",
            "source": "SSI",
            "rows": [{"symbol": symbol, "exchange": "HOSE", "market": "HOSE", "source": "SSI"}],
        }

    def get_securities(self, **kwargs):
        return self.get_securities_details(symbol="FPT")


def _service(fetcher: FakeSsiFetcher, *, intraday_enabled: bool = True) -> VietnamMarketService:
    clear_vietnam_cache()
    return VietnamMarketService(
        manager=ExplodingManager(),
        config=VietnamDashboardConfig(
            daily_data_provider="ssi",
            chart_data_provider="ssi",
            daily_stock_price_provider="ssi",
            index_data_provider="ssi",
            intraday_data_provider="ssi",
            ssi_intraday_enabled=intraday_enabled,
            realtime_data_provider="ssi",
            trade_tape_provider="ssi",
            ssi_realtime_enabled=True,
            ssi_trade_tape_enabled=True,
            kbs_enabled=False,
            allow_legacy_kbs_provider=False,
            include_intraday=True,
            news_provider="disabled",
            mozyfin_enabled=False,
            mozyfin_news_enabled=False,
        ),
        ssi_fetcher=fetcher,
    )


def test_ssi_intraday_success_returns_sorted_candles_and_daily_stays_ok(monkeypatch):
    monkeypatch.setenv("MOZYFIN_API_KEY", "unused")
    fetcher = FakeSsiFetcher()

    payload = _service(fetcher).build_watchlist(["FPT"], force_refresh=True, include_intraday=True)
    item = payload["watchlist"][0]

    assert item["status"] == "ok"
    assert item["source"] == "SSI"
    assert item["actual_source"] == "SSI"
    assert item["fallback_used"] is False
    assert item["intraday_source"] == "SSI IntradayOhlc"
    assert item["intraday_status"]["status"] == "ok"
    assert item["intraday_requested_timeframe"] == "1h"
    assert item["intraday_actual_granularity"] == "1h"
    assert [candle["date_time"] for candle in item["intraday_candles"]] == sorted(
        candle["date_time"] for candle in item["intraday_candles"]
    )
    assert item["intraday_candles"][-1]["close"] == 132.5
    assert item["intraday_pulse"]["latest_1h_close"] == 132.5
    assert item["intraday_pulse"]["latest_intraday_close"] == 132.5
    assert item["intraday_status"]["date_match"] == "matched"
    assert item["cache_status"]["intraday_cache"] in {"miss", "refresh"}
    assert fetcher.intraday_calls == 1


def test_ssi_intraday_date_mismatch_is_unavailable_without_downgrading_daily_row():
    fetcher = FakeSsiFetcher(
        {
            "status": "ok",
            "source": "SSI",
            "rows": [
                {
                    "date_time": "2026-06-29T10:00:00+07:00",
                    "open": 131.0,
                    "high": 132.0,
                    "low": 130.5,
                    "close": 131.5,
                    "volume": 2000,
                    "ticker": "FPT",
                    "source": "SSI",
                },
                {
                    "date_time": "2026-06-29T10:01:00+07:00",
                    "open": 131.5,
                    "high": 133.0,
                    "low": 131.0,
                    "close": 132.5,
                    "volume": 3000,
                    "ticker": "FPT",
                    "source": "SSI",
                },
            ],
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True, include_intraday=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["daily_stock_price"]["status"] == "ok"
    assert item["intraday_source"] == "SSI IntradayOhlc"
    assert item["intraday_status"]["status"] == "unavailable"
    assert item["intraday_status"]["message"] == "SSI IntradayOhlc latest candle date does not match latest daily trading date."
    assert item["intraday_status"]["intraday_latest_date"] == "2026-06-29"
    assert item["intraday_status"]["daily_price_date"] == "2026-06-30"
    assert item["intraday_status"]["date_match"] == "mismatched"
    assert item["intraday_requested_timeframe"] == "1h"
    assert item["intraday_actual_granularity"] == "1m"
    assert item["intraday_status"]["intraday_requested_timeframe"] == "1h"
    assert item["intraday_status"]["intraday_actual_granularity"] == "1m"
    assert item["intraday_candles"] == []
    assert item["intraday_pulse"] is None
    assert item["intraday_labels"] == []


def test_ssi_intraday_detects_provider_returned_minute_granularity():
    fetcher = FakeSsiFetcher(
        {
            "status": "ok",
            "source": "SSI",
            "rows": [
                {
                    "date_time": "2026-06-30T10:00:00+07:00",
                    "open": 131.0,
                    "high": 132.0,
                    "low": 130.5,
                    "close": 131.5,
                    "volume": 2000,
                    "ticker": "FPT",
                    "source": "SSI",
                },
                {
                    "date_time": "2026-06-30T10:01:00+07:00",
                    "open": 131.5,
                    "high": 133.0,
                    "low": 131.0,
                    "close": 132.5,
                    "volume": 3000,
                    "ticker": "FPT",
                    "source": "SSI",
                },
                {
                    "date_time": "2026-06-30T10:02:00+07:00",
                    "open": 132.5,
                    "high": 133.5,
                    "low": 132.0,
                    "close": 133.0,
                    "volume": 4000,
                    "ticker": "FPT",
                    "source": "SSI",
                },
            ],
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True, include_intraday=True)["watchlist"][0]

    assert item["intraday_status"]["status"] == "ok"
    assert item["intraday_requested_timeframe"] == "1h"
    assert item["intraday_granularity"] == "1m"
    assert item["intraday_actual_granularity"] == "1m"
    assert item["intraday_timeframe"] == "1h"
    assert item["intraday_status"]["intraday_granularity"] == "1m"
    assert item["intraday_status"]["intraday_actual_granularity"] == "1m"
    assert item["intraday_pulse"]["intraday_granularity"] == "1m"
    assert item["intraday_pulse"]["intraday_actual_granularity"] == "1m"
    assert item["intraday_pulse"]["latest_intraday_close"] == 133.0
    assert item["intraday_pulse"]["intraday_change"] == 0.5
    assert not any("1H" in detail["reason"] for detail in item["intraday_details"])


def test_ssi_intraday_failure_does_not_downgrade_daily_row():
    fetcher = FakeSsiFetcher(
        {
            "status": "unavailable",
            "source": "SSI",
            "reason": "SSI FastConnect request failed",
            "failure_class": "rate_limited",
            "diagnostics": {
                "failure_class": "rate_limited",
                "endpoint": "IntradayOhlc",
                "http_status": "200",
                "provider_code": "429",
                "error_type": "ssi_error",
                "pageSize": "1000",
                "public_limit": "8",
            },
            "rows": [],
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True, include_intraday=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["daily_stock_price"]["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["intraday_source"] == "SSI IntradayOhlc"
    assert item["intraday_status"]["status"] == "unavailable"
    assert item["intraday_status"]["message"] == "SSI FastConnect request failed"
    assert item["intraday_status"]["failure_class"] == "rate_limited"
    assert item["intraday_status"]["diagnostics"]["failure_class"] == "rate_limited"
    assert item["intraday_status"]["diagnostics"]["endpoint"] == "IntradayOhlc"
    assert item["intraday_status"]["diagnostics"]["provider_code"] == "429"
    assert item["intraday_status"]["diagnostics"]["pageSize"] == "1000"
    assert item["intraday_candles"] == []
    assert item["intraday_pulse"] is None


def test_ssi_intraday_empty_rows_are_optional_and_do_not_fake_daily_data():
    fetcher = FakeSsiFetcher(
        {
            "status": "ok",
            "source": "SSI",
            "rows": [],
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True, include_intraday=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["daily_stock_price"]["status"] == "ok"
    assert item["intraday_status"]["status"] == "unavailable"
    assert item["intraday_status"]["message"] == "SSI IntradayOhlc returned no candles."
    assert item["intraday_candles"] == []
    assert item["intraday_pulse"] is None
    assert item["realtime_snapshot"] is None
    assert item["trade_tape"] == []


def test_ssi_intraday_malformed_rows_are_unavailable_without_daily_fallback():
    fetcher = FakeSsiFetcher(
        {
            "status": "ok",
            "source": "SSI",
            "rows": [
                {
                    "date_time": None,
                    "open": None,
                    "high": None,
                    "low": None,
                    "close": None,
                    "volume": None,
                    "ticker": "FPT",
                    "source": "SSI",
                }
            ],
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True, include_intraday=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["latest_price"] == item["daily_close"]
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["intraday_status"]["status"] == "unavailable"
    assert item["intraday_status"]["message"] == "SSI IntradayOhlc returned no candles."
    assert item["intraday_candles"] == []
    assert item["intraday_pulse"] is None
    assert item["intraday_labels"] == []


def test_ssi_intraday_can_be_disabled_without_mozyfin_fallback():
    fetcher = FakeSsiFetcher()

    item = _service(fetcher, intraday_enabled=False).build_watchlist(
        ["FPT"],
        force_refresh=True,
        include_intraday=True,
    )["watchlist"][0]

    assert item["status"] == "ok"
    assert item["intraday_source"] == "SSI IntradayOhlc"
    assert item["intraday_status"]["status"] == "disabled"
    assert item["intraday_candles"] == []
    assert item["intraday_pulse"] is None
    assert fetcher.intraday_calls == 0
