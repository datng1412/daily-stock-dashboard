from __future__ import annotations

from datetime import date, timedelta

from data_provider.ssi_fastconnect_fetcher import REALTIME_STREAMING_NOT_IMPLEMENTED_REASON
from src.services.vietnam_market_service import (
    VietnamDashboardConfig,
    VietnamMarketService,
    build_vietnam_data_quality_summary,
    clear_vietnam_cache,
)


class ExplodingManager:
    def _get_fetcher_by_name(self, name: str):  # pragma: no cover - failure path
        raise AssertionError(f"Legacy provider must not be requested in VN realtime path: {name}")

    def get_daily_data(self, *args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("Legacy daily data must not be requested in VN realtime path")


class FakeSsiFetcher:
    def __init__(
        self,
        realtime_payload=None,
        order_book_payload=None,
        foreign_room_payload=None,
        market_index_payload=None,
        trade_payload=None,
        session_status_payload=None,
    ):
        self.realtime_payload = realtime_payload
        self.order_book_payload = order_book_payload
        self.foreign_room_payload = foreign_room_payload
        self.market_index_payload = market_index_payload
        self.trade_payload = trade_payload
        self.session_status_payload = session_status_payload
        self.realtime_calls = 0
        self.order_book_calls = 0
        self.foreign_room_calls = 0
        self.market_index_calls = 0
        self.trade_calls = 0
        self.session_status_calls = 0

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
                    "timestamp": "2026-06-30T10:00:00+07:00",
                    "timestamp_display": "10:00:00",
                    "price": 130.5,
                    "volume": 1000,
                    "value": 130_500_000,
                    "side_if_available": "BU",
                    "sequence_if_available": "1",
                    "raw_type": "X-TRADE",
                    "source": "SSI",
                }
            ],
        }

    def get_order_book(self, symbol: str):
        self.order_book_calls += 1
        if self.order_book_payload is not None:
            return self.order_book_payload
        return {
            "status": "unavailable",
            "source": "SSI",
            "symbol": symbol,
            "reason": "SSI X-QUOTE stream cache empty.",
            "order_book": None,
            "streaming_status": "subscribed_no_event",
            "cache_status": "empty",
            "diagnostics": {
                "streaming_status": "subscribed_no_event",
                "cache_status": "empty",
                "manager_state": "running",
                "order_book_channels": [f"X-QUOTE:{symbol}"],
            },
        }

    def get_foreign_room(self, symbol: str):
        self.foreign_room_calls += 1
        if self.foreign_room_payload is not None:
            return self.foreign_room_payload
        return {
            "status": "unavailable",
            "source": "SSI",
            "symbol": symbol,
            "reason": "SSI R foreign-room stream cache empty.",
            "foreign_room": None,
            "streaming_status": "subscribed_no_event",
            "cache_status": "empty",
            "diagnostics": {
                "streaming_status": "subscribed_no_event",
                "cache_status": "empty",
                "manager_state": "running",
                "foreign_room_channels": [f"R:{symbol}"],
            },
        }

    def get_session_status(self, symbol: str):
        self.session_status_calls += 1
        if self.session_status_payload is not None:
            return self.session_status_payload
        return {
            "status": "unavailable",
            "source": "SSI",
            "symbol": symbol,
            "reason": "SSI F stream cache empty.",
            "session_status": None,
            "streaming_status": "subscribed_no_event",
            "cache_status": "empty",
            "diagnostics": {
                "streaming_status": "subscribed_no_event",
                "cache_status": "empty",
                "manager_state": "running",
                "session_status_channels": [f"F:{symbol}"],
            },
        }

    def get_market_index_pulse(self, index_codes):
        self.market_index_calls += 1
        if self.market_index_payload is not None:
            return self.market_index_payload
        return {
            "status": "unavailable",
            "source": "SSI",
            "requested_index_codes": index_codes,
            "reason": "SSI MI market-index stream cache empty.",
            "market_index_pulse": [],
            "streaming_status": "subscribed_no_event",
            "cache_status": "empty",
            "channel_format_status": "needs_live_proof",
            "diagnostics": {
                "streaming_status": "subscribed_no_event",
                "cache_status": "empty",
                "manager_state": "running",
                "market_index_channels": [f"MI:{code}" for code in index_codes],
                "requested_index_codes": index_codes,
            },
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
            ssi_streaming_realtime_enabled=realtime_enabled,
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
    assert item["realtime_source"] == "SSI realtime contract"
    assert item["realtime_status"]["status"] == "ok"
    assert item["realtime_status"]["source"] == "SSI realtime contract"
    assert item["realtime_snapshot"]["source"] == "SSI realtime contract"
    assert item["realtime_snapshot"]["price"] == 130.5
    assert item["realtime_snapshot"]["bid_levels"][0]["price"] == 130.4
    assert fetcher.realtime_calls == 1


def test_ssi_realtime_failure_is_separate_from_daily_row():
    fetcher = FakeSsiFetcher(
        realtime_payload={
            "status": "unavailable",
            "source": "SSI",
            "reason": REALTIME_STREAMING_NOT_IMPLEMENTED_REASON,
            "rest_candidate_endpoints": ["RealtimeQuote", "RealtimePrice", "RealtimeSnapshot", "SecuritiesRealtime"],
            "discovery_status": "streaming_adapter_not_implemented",
            "streaming_status": "not_implemented",
            "rest_status": "unsupported",
            "requested_tickers": ["FPT"],
            "quotes": [],
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["daily_stock_price"]["status"] == "ok"
    assert item["realtime_source"] == "SSI realtime contract"
    assert item["realtime_status"]["status"] == "unavailable"
    assert item["realtime_snapshot"] is None
    assert item["realtime_status"]["message"] == "SSI realtime unavailable."
    assert item["realtime_status"]["reason_code"] == "unknown"
    assert "RealtimeQuote" not in item["realtime_status"]["message"]
    assert "diagnostics" not in item["realtime_status"]
    assert item["diagnostics"]["realtime"]["provider_message"] == REALTIME_STREAMING_NOT_IMPLEMENTED_REASON


class IntradayAvailableRealtimeUnavailableFetcher(FakeSsiFetcher):
    def get_intraday_ohlcv(self, symbol: str, **kwargs):
        return {
            "status": "ok",
            "source": "SSI",
            "rows": [
                {
                    "date_time": "2026-06-30T10:00:00+07:00",
                    "open": 129.0,
                    "high": 131.0,
                    "low": 128.0,
                    "close": 130.0,
                    "volume": 12_000,
                    "source": "SSI",
                }
            ],
        }

class ZeroReferenceTradeTapeFetcher(FakeSsiFetcher):
    def get_daily_stock_price(self, symbol: str, **kwargs):
        payload = super().get_daily_stock_price(symbol, **kwargs)
        payload["rows"][0]["reference_price"] = 0
        return payload


def test_realtime_unavailable_is_not_inferred_from_intraday_or_daily_ohlcv():
    fetcher = IntradayAvailableRealtimeUnavailableFetcher(
        realtime_payload={
            "status": "unavailable",
            "source": "SSI",
            "reason": "SSI realtime endpoint returned no quote rows.",
            "quotes": [],
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["latest_price"] == 130.0
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["intraday_status"]["status"] == "ok"
    assert item["intraday_pulse"] is not None
    assert item["realtime_status"]["status"] == "unavailable"
    assert item["realtime_snapshot"] is None


def test_ssi_trade_tape_success_returns_normalized_trades():
    fetcher = FakeSsiFetcher()

    service = _service(fetcher)
    endpoint_payload = service.build_trade_tape("FPT", force_refresh=True)
    item = service.build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert endpoint_payload["status"] == "ok"
    assert endpoint_payload["source"] == "SSI trade-tape contract"
    assert endpoint_payload["trades"][0]["price"] == 130.5
    assert endpoint_payload["trades"][0]["source"] == "SSI trade-tape contract"
    assert endpoint_payload["trades"][0]["value"] == 130_500_000
    assert endpoint_payload["trades"][0]["side"] == "buy"
    assert endpoint_payload["trades"][0]["side_label"] == "Buy"
    assert endpoint_payload["trades"][0]["side_if_available"] == "BU"
    assert endpoint_payload["trades"][0]["change"] == 1.5
    assert endpoint_payload["trades"][0]["change_pct"] == 1.16
    assert item["trade_tape_source"] == "SSI trade-tape contract"
    assert item["trade_tape_status"]["status"] == "ok"
    assert item["trade_tape_status"]["source"] == "SSI trade-tape contract"
    assert item["trade_tape"][0]["source"] == "SSI trade-tape contract"
    assert item["trade_tape"][0]["timestamp"] == "2026-06-30T10:00:00+07:00"
    assert item["trade_tape"][0]["sequence_if_available"] == "1"
    assert item["trade_tape"][0]["side"] == "buy"
    assert item["trade_tape"][0]["side_if_available"] == "BU"
    assert item["trade_tape"][0]["change"] == 1.5
    assert item["trade_tape"][0]["change_pct"] == 1.16


def test_ssi_order_book_success_is_separate_from_daily_price_and_live_contexts():
    fetcher = FakeSsiFetcher(
        order_book_payload={
            "status": "ok",
            "source": "SSI",
            "symbol": "FPT",
            "order_book": {
                "ticker": "FPT",
                "symbol": "FPT",
                "exchange": "HOSE",
                "bids": [
                    {"level": 1, "price": 130.4, "volume": 1000},
                    {"level": 2, "price": 130.3, "volume": 2500},
                ],
                "asks": [
                    {"level": 1, "price": 130.6, "volume": 2000},
                ],
                "trading_date": "2026-06-30",
                "time": "10:00:00",
                "stream_timestamp": "2026-06-30T10:00:00",
                "stream_data_type": "X-QUOTE",
                "r_type": "X-QUOTE",
                "age_seconds": 0,
                "cached_at": "2026-06-30T03:00:00+00:00",
                "cache_ttl_seconds": 5,
            },
            "streaming_status": "cache_hit",
            "cache_status": "hit",
            "diagnostics": {
                "streaming_status": "cache_hit",
                "cache_status": "hit",
                "manager_state": "running",
                "order_book_channels": ["X-QUOTE:FPT"],
                "order_book_rows_observed": 1,
            },
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["realtime_status"]["status"] == "ok"
    assert item["trade_tape_status"]["status"] == "ok"
    assert item["order_book_source"] == "SSI X-QUOTE order-book stream"
    assert item["order_book_status"]["status"] == "ok"
    assert item["order_book_status"]["reason_code"] == "cache_hit"
    assert item["order_book"]["stream_data_type"] == "X-QUOTE"
    assert item["order_book"]["bids"][0] == {"level": 1, "price": 130.4, "volume": 1000.0}
    assert item["order_book"]["asks"][0] == {"level": 1, "price": 130.6, "volume": 2000.0}
    assert item["diagnostics"]["order_book"]["streaming_status"] == "cache_hit"
    assert item["diagnostics"]["order_book"]["order_book_channels"] == ["X-QUOTE:FPT"]
    assert fetcher.order_book_calls == 1


def test_ssi_order_book_cache_empty_is_optional_unavailable():
    fetcher = FakeSsiFetcher(
        order_book_payload={
            "status": "unavailable",
            "source": "SSI",
            "symbol": "FPT",
            "reason": "SSI X-QUOTE stream cache empty.",
            "order_book": None,
            "streaming_status": "subscribed_no_event",
            "cache_status": "empty",
            "diagnostics": {
                "streaming_status": "subscribed_no_event",
                "cache_status": "empty",
                "manager_state": "running",
                "order_book_channels": ["X-QUOTE:FPT"],
            },
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["order_book_source"] == "SSI X-QUOTE order-book stream"
    assert item["order_book"] is None
    assert item["order_book_status"]["status"] == "unavailable"
    assert item["order_book_status"]["reason_code"] == "stream_cache_empty"
    assert item["order_book_status"]["message"] == "SSI order book unavailable."
    assert item["diagnostics"]["order_book"]["streaming_status"] == "subscribed_no_event"
    assert any(issue["code"] == "order_book_stream_cache_empty" for issue in item["data_quality_summary"]["issues"])


def test_ssi_foreign_room_success_is_separate_from_daily_price_and_daily_stock_price():
    fetcher = FakeSsiFetcher(
        foreign_room_payload={
            "status": "ok",
            "source": "SSI",
            "symbol": "FPT",
            "foreign_room": {
                "ticker": "FPT",
                "symbol": "FPT",
                "exchange": "HOSE",
                "total_room": 123456789,
                "current_room": 123000000,
                "foreign_buy_volume": 100000,
                "foreign_sell_volume": 50000,
                "foreign_buy_value": 7200000000,
                "foreign_sell_value": 3600000000,
                "trading_date": "2026-06-30",
                "time": "10:00:00",
                "stream_timestamp": "2026-06-30T10:00:00",
                "stream_data_type": "R",
                "r_type": "R",
                "age_seconds": 0,
                "cached_at": "2026-06-30T03:00:00+00:00",
                "cache_ttl_seconds": 5,
                "value_semantics_status": "needs_semantics_proof",
            },
            "streaming_status": "cache_hit",
            "cache_status": "hit",
            "diagnostics": {
                "streaming_status": "cache_hit",
                "cache_status": "hit",
                "manager_state": "running",
                "foreign_room_channels": ["R:FPT"],
                "foreign_room_rows_observed": 1,
            },
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["daily_stock_price"]["foreign_net_volume"] == 20000.0
    assert item["foreign_room_source"] == "SSI R foreign-room stream"
    assert item["foreign_room_status"]["status"] == "ok"
    assert item["foreign_room_status"]["reason_code"] == "cache_hit"
    assert item["foreign_room"]["stream_data_type"] == "R"
    assert item["foreign_room"]["total_room"] == 123456789.0
    assert item["foreign_room"]["current_room"] == 123000000.0
    assert item["foreign_room"]["foreign_buy_volume"] == 100000.0
    assert item["foreign_room"]["foreign_sell_value"] == 3600000000.0
    assert item["foreign_room"]["value_semantics_status"] == "needs_semantics_proof"
    assert item["diagnostics"]["foreign_room"]["streaming_status"] == "cache_hit"
    assert item["diagnostics"]["foreign_room"]["foreign_room_channels"] == ["R:FPT"]
    assert fetcher.foreign_room_calls == 1


def test_ssi_foreign_room_cache_empty_is_optional_unavailable():
    fetcher = FakeSsiFetcher(
        foreign_room_payload={
            "status": "unavailable",
            "source": "SSI",
            "symbol": "FPT",
            "reason": "SSI R foreign-room stream cache empty.",
            "foreign_room": None,
            "streaming_status": "subscribed_no_event",
            "cache_status": "empty",
            "diagnostics": {
                "streaming_status": "subscribed_no_event",
                "cache_status": "empty",
                "manager_state": "running",
                "foreign_room_channels": ["R:FPT"],
            },
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["foreign_room_source"] == "SSI R foreign-room stream"
    assert item["foreign_room"] is None
    assert item["foreign_room_status"]["status"] == "unavailable"
    assert item["foreign_room_status"]["reason_code"] == "stream_cache_empty"
    assert item["foreign_room_status"]["message"] == "SSI foreign room unavailable."
    assert item["diagnostics"]["foreign_room"]["streaming_status"] == "subscribed_no_event"
    assert any(issue["code"] == "foreign_room_stream_cache_empty" for issue in item["data_quality_summary"]["issues"])


def test_ssi_market_index_pulse_success_is_separate_from_stock_rows_and_daily_index():
    fetcher = FakeSsiFetcher(
        market_index_payload={
            "status": "ok",
            "source": "SSI",
            "requested_index_codes": ["VNINDEX"],
            "market_index_pulse": [
                {
                    "index_code": "VNINDEX",
                    "exchange": "HOSE",
                    "index_value": 1234.56,
                    "estimated_index_value": 1234.50,
                    "change": 5.67,
                    "change_pct": 0.46,
                    "total_trades": 123456,
                    "total_volume": 123456789,
                    "total_value": 1234567890000,
                    "advances": 200,
                    "unchanged": 50,
                    "declines": 180,
                    "trading_date": "2026-06-30",
                    "time": "10:00:00",
                    "stream_timestamp": "2026-06-30T10:00:00",
                    "stream_data_type": "MI",
                    "r_type": "MI",
                    "age_seconds": 0,
                    "cached_at": "2026-06-30T03:00:00+00:00",
                    "cache_ttl_seconds": 5,
                    "channel_format_status": "needs_live_proof",
                    "value_semantics_status": "needs_live_proof",
                }
            ],
            "streaming_status": "cache_hit",
            "cache_status": "hit",
            "channel_format_status": "needs_live_proof",
            "diagnostics": {
                "streaming_status": "cache_hit",
                "cache_status": "hit",
                "manager_state": "running",
                "market_index_channels": ["MI:VNINDEX"],
                "market_index_rows_observed": 1,
                "requested_index_codes": ["VNINDEX"],
            },
        }
    )
    service = _service(fetcher)

    pulse = service.build_market_index_pulse(["VNINDEX"])
    item = service.build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert pulse["status"] == "ok"
    assert pulse["source"] == "SSI MI market-index stream"
    assert pulse["market_index_pulse_status"]["status"] == "ok"
    assert pulse["market_index_pulse_status"]["reason_code"] == "cache_hit"
    assert pulse["market_index_pulse"][0]["index_code"] == "VNINDEX"
    assert pulse["market_index_pulse"][0]["index_value"] == 1234.56
    assert pulse["market_index_pulse"][0]["channel_format_status"] == "needs_live_proof"
    assert pulse["diagnostics"]["market_index_pulse"]["market_index_channels"] == ["MI:VNINDEX"]
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert "market_index_pulse" not in item
    assert fetcher.market_index_calls == 1


def test_ssi_market_index_pulse_cache_empty_is_explicit_unavailable():
    fetcher = FakeSsiFetcher(
        market_index_payload={
            "status": "unavailable",
            "source": "SSI",
            "requested_index_codes": ["VNINDEX"],
            "reason": "SSI MI market-index stream cache empty.",
            "market_index_pulse": [],
            "streaming_status": "subscribed_no_event",
            "cache_status": "empty",
            "channel_format_status": "needs_live_proof",
            "diagnostics": {
                "streaming_status": "subscribed_no_event",
                "cache_status": "empty",
                "manager_state": "running",
                "market_index_channels": ["MI:VNINDEX"],
            },
        }
    )

    pulse = _service(fetcher).build_market_index_pulse(["VNINDEX"])

    assert pulse["status"] == "unavailable"
    assert pulse["market_index_pulse"] == []
    assert pulse["market_index_pulse_status"]["status"] == "unavailable"
    assert pulse["market_index_pulse_status"]["reason_code"] == "stream_cache_empty"
    assert pulse["market_index_pulse_status"]["message"] == "SSI market-index pulse unavailable."
    assert pulse["diagnostics"]["market_index_pulse"]["streaming_status"] == "subscribed_no_event"


def test_ssi_session_status_success_is_separate_from_daily_price():
    fetcher = FakeSsiFetcher(
        session_status_payload={
            "status": "ok",
            "source": "SSI",
            "symbol": "FPT",
            "session_status": {
                "ticker": "FPT",
                "symbol": "FPT",
                "exchange": "HOSE",
                "trading_date": "2026-06-30",
                "time": "10:00:00",
                "trading_session": "CONTINUOUS",
                "trading_status": "OPEN",
                "stream_timestamp": "2026-06-30T10:00:00",
                "stream_data_type": "F",
                "r_type": "F",
                "age_seconds": 0,
                "cached_at": "2026-06-30T03:00:00+00:00",
                "cache_ttl_seconds": 60,
            },
            "streaming_status": "cache_hit",
            "cache_status": "hit",
            "diagnostics": {
                "streaming_status": "cache_hit",
                "cache_status": "hit",
                "manager_state": "running",
                "session_status_channels": ["F:FPT"],
                "session_status_rows_observed": 1,
            },
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["session_status_source"] == "SSI F trading session/status stream"
    assert item["session_status_status"]["status"] == "ok"
    assert item["session_status_status"]["reason_code"] == "cache_hit"
    assert item["session_status"]["trading_session"] == "CONTINUOUS"
    assert item["session_status"]["trading_status"] == "OPEN"
    assert item["session_status"]["stream_data_type"] == "F"
    assert item["diagnostics"]["session_status"]["streaming_status"] == "cache_hit"
    assert item["diagnostics"]["session_status"]["session_status_channels"] == ["F:FPT"]


def test_ssi_session_status_cache_empty_is_optional_unavailable():
    fetcher = FakeSsiFetcher(
        session_status_payload={
            "status": "unavailable",
            "source": "SSI",
            "symbol": "FPT",
            "reason": "SSI F stream cache empty.",
            "session_status": None,
            "streaming_status": "subscribed_no_event",
            "cache_status": "empty",
            "diagnostics": {
                "streaming_status": "subscribed_no_event",
                "cache_status": "empty",
                "manager_state": "running",
                "session_status_channels": ["F:FPT"],
            },
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["session_status_source"] == "SSI F trading session/status stream"
    assert item["session_status"] is None
    assert item["session_status_status"]["status"] == "unavailable"
    assert item["session_status_status"]["reason_code"] == "stream_cache_empty"
    assert item["session_status_status"]["message"] == "SSI trading session/status unavailable."
    assert item["diagnostics"]["session_status"]["streaming_status"] == "subscribed_no_event"


def test_ssi_trade_tape_sd_remains_sell_with_positive_change():
    fetcher = FakeSsiFetcher(
        trade_payload={
            "status": "ok",
            "source": "SSI",
            "symbol": "FPT",
            "trades": [
                {
                    "time": "10:15:00",
                    "timestamp": "2026-06-30T10:15:00+07:00",
                    "timestamp_display": "10:15:00",
                    "price": 130.5,
                    "volume": 1000,
                    "value": 130_500_000,
                    "side_if_available": "SD",
                    "sequence_if_available": "2",
                    "raw_type": "X-TRADE",
                    "source": "SSI",
                }
            ],
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["trade_tape"][0]["side"] == "sell"
    assert item["trade_tape"][0]["side_label"] == "Sell"
    assert item["trade_tape"][0]["side_if_available"] == "SD"
    assert item["trade_tape"][0]["change"] == 1.5
    assert item["trade_tape"][0]["change_pct"] == 1.16


def test_ssi_trade_tape_bu_remains_buy_with_negative_change():
    fetcher = FakeSsiFetcher(
        trade_payload={
            "status": "ok",
            "source": "SSI",
            "symbol": "FPT",
            "trades": [
                {
                    "time": "10:15:01",
                    "timestamp": "2026-06-30T10:15:01+07:00",
                    "timestamp_display": "10:15:01",
                    "price": 128.0,
                    "volume": 1000,
                    "value": 128_000_000,
                    "side_if_available": "BU",
                    "sequence_if_available": "3",
                    "raw_type": "X-TRADE",
                    "source": "SSI",
                }
            ],
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["trade_tape"][0]["side"] == "buy"
    assert item["trade_tape"][0]["side_label"] == "Buy"
    assert item["trade_tape"][0]["side_if_available"] == "BU"
    assert item["trade_tape"][0]["change"] == -1.0
    assert item["trade_tape"][0]["change_pct"] == -0.78


def test_ssi_trade_tape_change_is_null_when_reference_unavailable():
    item = _service(ZeroReferenceTradeTapeFetcher()).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["trade_tape_status"]["status"] == "ok"
    assert item["trade_tape"][0]["price"] == 130.5
    assert item["trade_tape"][0]["side"] == "buy"
    assert item["trade_tape"][0]["change"] is None
    assert item["trade_tape"][0]["change_pct"] is None


def test_ssi_trade_tape_stale_buffer_rows_remain_public_and_daily_stays_ok():
    fetcher = FakeSsiFetcher(
        trade_payload={
            "status": "ok",
            "source": "SSI",
            "symbol": "FPT",
            "reason": "Buffered SSI X-TRADE rows available.",
            "streaming_status": "cache_stale",
            "cache_status": "stale",
            "trades": [
                {
                    "ticker": "FPT",
                    "symbol": "FPT",
                    "time": "11:29:58",
                    "timestamp": "2026-06-30T11:29:58+07:00",
                    "timestamp_display": "11:29:58",
                    "price": 130.5,
                    "volume": 5000,
                    "value": 652_500_000,
                    "sequence_if_available": "4776",
                    "raw_type": "X-TRADE",
                    "source": "SSI",
                    "is_stale": True,
                }
            ],
            "diagnostics": {
                "streaming_status": "cache_stale",
                "cache_status": "stale",
                "trade_tape_subscription_status": "subscribed",
                "trade_tape_buffer_row_count": 50,
                "trade_tape_returned_row_count": 1,
            },
        }
    )

    endpoint_payload = _service(fetcher).build_trade_tape("FPT", force_refresh=True)
    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert endpoint_payload["status"] == "ok"
    assert endpoint_payload["trades"][0]["timestamp"] == "2026-06-30T11:29:58+07:00"
    assert endpoint_payload["reason_code"] == "buffered_rows_available"
    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["trade_tape_status"]["status"] == "ok"
    assert item["trade_tape_status"]["reason_code"] == "buffered_rows_available"
    assert item["trade_tape"][0]["price"] == 130.5
    assert item["trade_tape"][0]["volume"] == 5000.0
    assert item["trade_tape"][0]["side"] is None
    assert item["trade_tape"][0]["change"] == 1.5
    assert item["trade_tape"][0]["change_pct"] == 1.16
    assert item["diagnostics"]["trade_tape"]["streaming_status"] == "cache_stale"
    assert item["diagnostics"]["trade_tape"]["trade_tape_returned_row_count"] == 1


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
    assert item["trade_tape_source"] == "SSI trade-tape contract"
    assert item["trade_tape"] == []
    assert item["trade_tape_status"]["status"] == "unavailable"
    assert item["trade_tape_status"]["message"] == "SSI trade tape unavailable."
    assert item["trade_tape_status"]["reason_code"] == "latest_trade_stream_only"
    assert "TradeTape" not in item["trade_tape_status"]["message"]
    assert "diagnostics" not in item["trade_tape_status"]
    assert "TradeTape" in item["diagnostics"]["trade_tape"]["provider_message"]


def test_live_status_messages_are_short_and_diagnostics_are_sanitized():
    secret = "SECRET_LIVE_CONTRACT_VALUE"
    fetcher = FakeSsiFetcher(
        realtime_payload={
            "status": "unavailable",
            "source": "SSI",
            "reason": f"Authorization Bearer {secret} failed at https://provider.example/realtime",
            "quotes": [],
            "diagnostics": {
                "endpoint": "RealtimeQuote",
                "http_status": 403,
                "failure_class": "permission_denied",
                "latest_error": f"Bearer {secret}",
                "raw_payload": {"accessToken": secret},
            },
        },
        trade_payload={
            "status": "unavailable",
            "source": "SSI",
            "symbol": "FPT",
            "reason": f"Cookie={secret} https://provider.example/TradeTape",
            "attempted_endpoints": ["TradeTape", "MatchedTrades"],
            "endpoint": "TradeTape",
            "http_status": 429,
            "failure_class": "rate_limited",
            "trades": [],
        },
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["realtime_snapshot"] is None
    assert item["trade_tape"] == []
    assert item["realtime_status"]["message"] == "SSI realtime unavailable."
    assert item["trade_tape_status"]["message"] == "SSI trade tape unavailable."
    assert len(item["realtime_status"]["message"]) < 80
    assert len(item["trade_tape_status"]["message"]) < 80
    assert "diagnostics" not in item["realtime_status"]
    assert "diagnostics" not in item["trade_tape_status"]
    assert item["diagnostics"]["realtime"]["endpoint"] == "RealtimeQuote"
    assert item["diagnostics"]["realtime"]["http_status"] == 403
    assert item["diagnostics"]["realtime"]["provider_message"] == "[redacted]"
    assert item["diagnostics"]["trade_tape"]["attempted_endpoints"] == ["TradeTape", "MatchedTrades"]
    assert item["diagnostics"]["trade_tape"]["http_status"] == 429
    assert item["diagnostics"]["trade_tape"]["retryable"] is True
    assert secret not in str(item)
    assert "raw_payload" not in str(item["diagnostics"])


def test_standalone_live_contract_keeps_messages_safe_and_details_in_diagnostics():
    secret = "SECRET_STANDALONE_LIVE_VALUE"
    fetcher = FakeSsiFetcher(
        realtime_payload={
            "status": "unavailable",
            "source": "SSI",
            "reason": f"Bearer {secret} from https://provider.example/realtime",
            "quotes": [],
            "diagnostics": {
                "endpoint": "RealtimeQuote",
                "http_status": 403,
                "failure_class": "permission_denied",
            },
        },
        trade_payload={
            "status": "unavailable",
            "source": "SSI",
            "symbol": "FPT",
            "reason": f"Authorization {secret} at https://provider.example/trades",
            "attempted_endpoints": ["TradeTape", "MatchedTrades"],
            "http_status": 429,
            "failure_class": "rate_limited",
            "trades": [],
        },
    )
    service = _service(fetcher)

    realtime = service.build_realtime_snapshot(["FPT"], force_refresh=True)
    trade_tape = service.build_trade_tape("FPT", force_refresh=True)

    assert realtime["status"] == "unavailable"
    assert realtime["status_message"] == "SSI realtime unavailable."
    assert realtime["error"] == realtime["status_message"]
    assert realtime["error_detail"] == realtime["status_message"]
    assert realtime["diagnostics"]["endpoint"] == "RealtimeQuote"
    assert realtime["diagnostics"]["provider_message"] == "[redacted]"
    assert trade_tape["status"] == "unavailable"
    assert trade_tape["trades"] == []
    assert trade_tape["status_message"] == "SSI trade tape unavailable."
    assert trade_tape["error"] == trade_tape["status_message"]
    assert trade_tape["error_detail"] == trade_tape["status_message"]
    assert trade_tape["diagnostics"]["attempted_endpoints"] == ["TradeTape", "MatchedTrades"]
    assert trade_tape["diagnostics"]["http_status"] == 429
    assert trade_tape["diagnostics"]["retryable"] is True
    assert secret not in str(realtime)
    assert secret not in str(trade_tape)


def test_ssi_realtime_running_idle_reason_is_exposed_without_daily_downgrade():
    fetcher = FakeSsiFetcher(
        realtime_payload={
            "status": "unavailable",
            "source": "SSI",
            "reason": "SSI streaming realtime cache empty.",
            "streaming_status": "cache_empty",
            "cache_status": "empty",
            "manager_state": "running",
            "requested_tickers": ["FPT"],
            "quotes": [],
            "diagnostics": {
                "runtime_status": "running_idle",
                "streaming_status": "cache_empty",
                "cache_status": "empty",
                "manager_state": "running",
                "bootstrap_symbols": ["FPT", "HPG", "SSI"],
            },
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]
    summary = item["data_quality_summary"]

    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["realtime_snapshot"] is None
    assert item["realtime_status"]["status"] == "unavailable"
    assert item["realtime_status"]["reason_code"] == "running_idle"
    assert item["realtime_status"]["message"] == "SSI realtime cache miss."
    assert summary["checks"]["daily_ohlc"] == "ok"
    assert any(issue["code"] == "realtime_running_idle" for issue in summary["issues"])


def test_ssi_realtime_ticker_not_bootstrapped_reason_is_exposed():
    fetcher = FakeSsiFetcher(
        realtime_payload={
            "status": "unavailable",
            "source": "SSI",
            "reason": "SSI streaming realtime cache empty.",
            "streaming_status": "cache_empty",
            "cache_status": "empty",
            "manager_state": "running",
            "requested_tickers": ["FPT"],
            "quotes": [],
            "diagnostics": {
                "runtime_status": "running",
                "streaming_status": "cache_empty",
                "cache_status": "empty",
                "manager_state": "running",
                "bootstrap_symbols": ["HPG", "SSI"],
            },
        }
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["realtime_status"]["reason_code"] == "ticker_not_bootstrapped"
    assert item["realtime_status"]["message"] == "SSI realtime cache miss."


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
    assert item["trade_tape"] == []
    assert item["trade_tape_status"]["status"] == "disabled"
    assert fetcher.realtime_calls == 0
    assert fetcher.trade_calls == 0


class MismatchedDailyStockPriceFetcher(FakeSsiFetcher):
    def get_daily_stock_price(self, symbol: str, **kwargs):
        payload = super().get_daily_stock_price(symbol, **kwargs)
        payload["rows"][0]["close"] = 131.0
        return payload


def _issue_codes(summary):
    return {issue["code"] for issue in summary.get("issues", [])}


def test_data_quality_summary_has_no_mismatch_when_daily_sources_match():
    item = _service(FakeSsiFetcher()).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    summary = item["data_quality_summary"]

    assert summary["canonical_price_source"] == "SSI DailyOhlc"
    assert summary["checks"]["daily_ohlc"] == "ok"
    assert summary["checks"]["daily_stock_price"] == "partial"
    assert "daily_ohlc_vs_daily_stock_price_mismatch" not in _issue_codes(summary)
    assert item["latest_price"] == 130.0
    assert item["latest_price_source"] == "SSI DailyOhlc"


def test_data_quality_summary_keeps_valid_ssi_daily_ok_when_optional_live_unavailable():
    summary = build_vietnam_data_quality_summary(
        {
            "status": "partial",
            "latest_price": 70_600.0,
            "daily_close": 70_600.0,
            "ohlcv_close": 70_600.0,
            "latest_price_date": "2026-06-22",
            "ohlcv_date": "2026-06-22",
            "latest_price_source": "SSI DailyOhlc",
            "actual_source": "SSI",
            "source": "SSI",
            "daily_stock_price": {
                "status": "ok",
                "date": "2026-06-22",
                "close": 70_600.0,
            },
            "intraday_status": {"status": "unavailable"},
            "realtime_status": {"status": "unavailable"},
            "trade_tape_status": {"status": "unavailable"},
            "news_status": {"status": "disabled"},
            "symbol_metadata": {"status": "ok", "exchange": "HOSE"},
        }
    )

    assert summary["overall_status"] == "partial"
    assert summary["checks"]["daily_ohlc"] == "ok"
    assert summary["checks"]["daily_stock_price"] == "ok"
    assert summary["checks"]["intraday"] == "unavailable"
    assert summary["checks"]["realtime"] == "unavailable"
    assert summary["checks"]["trade_tape"] == "unavailable"


def test_data_quality_summary_marks_missing_daily_close_unavailable():
    summary = build_vietnam_data_quality_summary(
        {
            "status": "ok",
            "latest_price": None,
            "daily_close": None,
            "ohlcv_close": None,
            "latest_price_date": "2026-06-22",
            "latest_price_source": "SSI DailyOhlc",
            "actual_source": "SSI",
            "source": "SSI",
            "intraday_status": {"status": "disabled"},
            "realtime_status": {"status": "disabled"},
            "trade_tape_status": {"status": "disabled"},
            "news_status": {"status": "disabled"},
        }
    )

    assert summary["overall_status"] == "unavailable"
    assert summary["checks"]["daily_ohlc"] == "unavailable"
    assert "daily_ohlc_unavailable" in _issue_codes(summary)


def test_data_quality_summary_warns_on_same_date_daily_source_mismatch():
    item = _service(MismatchedDailyStockPriceFetcher()).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    summary = item["data_quality_summary"]
    mismatch = next(issue for issue in summary["issues"] if issue["code"] == "daily_ohlc_vs_daily_stock_price_mismatch")

    assert summary["overall_status"] == "partial"
    assert summary["checks"]["daily_ohlc"] == "ok"
    assert mismatch["severity"] == "warning"
    assert mismatch["fields"] == {
        "daily_ohlc_close": 130.0,
        "daily_stock_price_close": 131.0,
        "date": "2026-06-30",
        "daily_ohlc_source": "SSI DailyOhlc",
        "daily_stock_price_source": "SSI DailyStockPrice",
    }
    assert item["latest_price"] == 130.0
    assert item["latest_price_source"] == "SSI DailyOhlc"


def test_data_quality_summary_marks_profile_partial_without_failing_daily_row():
    item = _service(FakeSsiFetcher()).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    summary = item["data_quality_summary"]
    profile_issue = next(issue for issue in summary["issues"] if issue["code"] == "profile_partial")

    assert item["status"] == "ok"
    assert summary["checks"]["profile"] == "partial"
    assert profile_issue["severity"] == "info"
    assert "name" in profile_issue["fields"]["missing_fields"]
    assert "industry" in profile_issue["fields"]["missing_fields"]


def test_data_quality_summary_keeps_optional_live_unavailable_out_of_daily_status():
    fetcher = FakeSsiFetcher(
        realtime_payload={"status": "unavailable", "source": "SSI", "reason": "attempted endpoint dump must stay out", "quotes": []},
        trade_payload={"status": "unavailable", "source": "SSI", "symbol": "FPT", "reason": "TradeTape endpoint dump must stay out", "trades": []},
    )

    item = _service(fetcher).build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]
    summary = item["data_quality_summary"]

    assert item["status"] == "ok"
    assert summary["checks"]["daily_ohlc"] == "ok"
    assert summary["checks"]["realtime"] == "unavailable"
    assert summary["checks"]["trade_tape"] == "unavailable"
    summary_text = str(summary)
    assert "endpoint dump" not in summary_text
    assert "TradeTape" not in summary_text
