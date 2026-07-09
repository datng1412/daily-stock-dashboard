# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import pytest

from data_provider.ssi_fastconnect_fetcher import SsiFastConnectFetcher
from data_provider.ssi_streaming_realtime import (
    ForeignRoomCache,
    MANAGER_ERRORED,
    MANAGER_RUNNING,
    MarketIndexPulseCache,
    OfficialSsiRealtimeStreamClient,
    OrderBookCache,
    RealtimeSnapshotCache,
    RUNTIME_RECONNECTING,
    RUNTIME_RUNNING_IDLE,
    SessionStatusCache,
    SsiStreamingRealtimeManager,
    SSI_STREAMING_REALTIME_CACHE_EMPTY_REASON,
    SSI_STREAMING_REALTIME_CACHE_STALE_REASON,
    SSI_STREAMING_REALTIME_CONFIG_INCOMPLETE_REASON,
    SSI_STREAMING_REALTIME_DISABLED_REASON,
    SSI_STREAMING_REALTIME_MANAGER_ERROR_REASON,
    SSI_STREAMING_REALTIME_NOT_STARTED_REASON,
    SSI_STREAMING_REALTIME_PACKAGE_UNAVAILABLE_REASON,
    TradeTapeEventCache,
    build_foreign_room_channel,
    build_market_index_channel,
    build_order_book_channel,
    build_session_status_channel,
    build_streaming_channels,
    build_symbol_channel,
    build_trade_tape_channel,
)
from src.services.vietnam_market_service import VietnamDashboardConfig, VietnamMarketService, clear_vietnam_cache


SECRET_TOKEN = "SECRET_STREAM_TOKEN_DO_NOT_EXPOSE"
VIETNAM_TZ = timezone(timedelta(hours=7))


def _vn_epoch(year: int, month: int, day: int, hour: int, minute: int = 0) -> float:
    return datetime(year, month, day, hour, minute, tzinfo=VIETNAM_TZ).timestamp()


class NoNetworkSession:
    def __init__(self):
        self.calls = []

    def post(self, *args, **kwargs):  # pragma: no cover - failure path
        self.calls.append(("POST", args, kwargs))
        raise AssertionError("Realtime streaming cache reads must not request REST tokens.")

    def get(self, *args, **kwargs):  # pragma: no cover - failure path
        self.calls.append(("GET", args, kwargs))
        raise AssertionError("Realtime streaming cache reads must not probe REST endpoints.")


class FakeStreamClient:
    def __init__(self, *, fail_start: bool = False):
        self.fail_start = fail_start
        self.channels = []
        self.started = False
        self.stop_calls = 0
        self.on_message = None
        self.on_error = None

    def start(self, on_message, on_error, channels):
        if self.fail_start:
            raise RuntimeError(f"Authorization: Bearer {SECRET_TOKEN}; consumerSecret={SECRET_TOKEN}")
        self.started = True
        self.on_message = on_message
        self.on_error = on_error
        self.channels = list(channels)

    def stop(self):
        self.stop_calls += 1


class FakeOfficialClient:
    instances = []

    def __init__(self, config):
        self.config = config
        FakeOfficialClient.instances.append(self)


class FakeOfficialTransport:
    def __init__(self):
        self.stop_calls = 0

    def stop(self):
        self.stop_calls += 1


class FakeOfficialStream:
    instances = []

    def __init__(self, config, client):
        self.config = config
        self.client = client
        self.transport = FakeOfficialTransport()
        self.connection = SimpleNamespace()
        setattr(self.connection, "_Connection__transport", self.transport)
        self.started_channels = []
        FakeOfficialStream.instances.append(self)

    def start(self, on_message, on_error, channel):
        print(f"Authorization: Bearer {SECRET_TOKEN}")
        self.on_message = on_message
        self.on_error = on_error
        self.started_channels.append(channel)


def _fake_official_import(name):
    if name == "ssi_fc_data.fc_md_client":
        return SimpleNamespace(MarketDataClient=FakeOfficialClient)
    if name == "ssi_fc_data.fc_md_stream":
        return SimpleNamespace(MarketDataStream=FakeOfficialStream)
    raise ImportError(name)


class FakeMarketFetcher:
    def __init__(self, realtime_fetcher: SsiFastConnectFetcher):
        self.realtime_fetcher = realtime_fetcher

    def get_daily_ohlcv(self, symbol: str, **kwargs):
        rows = []
        for index in range(30):
            close = 101 + index
            rows.append(
                {
                    "date": f"2026-06-{index + 1:02d}",
                    "open": close - 1,
                    "high": close + 1,
                    "low": close - 2,
                    "close": close,
                    "volume": 1_000_000 + index,
                    "value": close * 1_000_000,
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
                    "source": "SSI",
                }
            ],
        }

    def get_intraday_ohlcv(self, symbol: str, **kwargs):
        return {"status": "unavailable", "source": "SSI", "reason": "SSI intraday unavailable", "rows": []}

    def get_realtime_snapshot(self, symbols):
        return self.realtime_fetcher.get_realtime_snapshot(symbols)

    def get_order_book(self, symbol: str):
        return self.realtime_fetcher.get_order_book(symbol)

    def get_foreign_room(self, symbol: str):
        return self.realtime_fetcher.get_foreign_room(symbol)

    def get_trade_tape(self, symbol: str, **kwargs):
        return self.realtime_fetcher.get_trade_tape(symbol, **kwargs)

    def get_session_status(self, symbol: str):
        return self.realtime_fetcher.get_session_status(symbol)

    def get_securities_details(self, **kwargs):
        symbol = kwargs.get("symbol") or "FPT"
        return {"status": "ok", "source": "SSI", "rows": [{"symbol": symbol, "exchange": "HOSE", "market": "HOSE", "source": "SSI"}]}

    def get_securities(self, **kwargs):
        return self.get_securities_details(symbol="FPT")


def _fetcher(**kwargs) -> SsiFastConnectFetcher:
    defaults = {
        "enabled": True,
        "base_url": "https://example.test/Market",
        "consumer_id": "test-consumer",
        "consumer_secret": "test-secret",
        "cache_ttl_seconds": 0,
        "session": NoNetworkSession(),
        "config": SimpleNamespace(),
    }
    defaults.update(kwargs)
    return SsiFastConnectFetcher(**defaults)


def _manager(
    *,
    enabled: bool = True,
    client: FakeStreamClient | None = None,
    now=None,
    **overrides,
) -> SsiStreamingRealtimeManager:
    parser_fetcher = _fetcher()
    time_func = (lambda: now[0]) if now is not None else None
    kwargs = {
        "enabled": enabled,
        "parser": parser_fetcher.normalize_streaming_realtime_messages,
        "client_factory": (lambda: client) if client is not None else None,
    }
    if time_func is not None:
        kwargs["cache"] = RealtimeSnapshotCache(15, time_func=time_func)
        kwargs["order_book_cache"] = OrderBookCache(15, time_func=time_func)
        kwargs["foreign_room_cache"] = ForeignRoomCache(15, time_func=time_func)
        kwargs["market_index_cache"] = MarketIndexPulseCache(15, time_func=time_func)
        kwargs["session_status_cache"] = SessionStatusCache(15, time_func=time_func)
        kwargs["time_func"] = time_func
    kwargs.update(overrides)
    return SsiStreamingRealtimeManager(**kwargs)


def _x_trade(symbol: str = "FPT", price: str = "130.5", side: str | None = None):
    content = {
        "RType": "X-TRADE",
        "TradingDate": "25/06/2026",
        "Time": "10:01:02",
        "Symbol": symbol,
        "LastPrice": price,
        "LastVol": "1000",
        "TotalVol": "123456",
    }
    if side is not None:
        content["Side"] = side
    return {
        "DataType": "X-TRADE",
        "Content": content,
    }


def _x_quote(symbol: str = "FPT"):
    return {
        "DataType": "X-QUOTE",
        "Content": {
            "RType": "X-QUOTE",
            "TradingDate": "25/06/2026",
            "Time": "10:01:03",
            "Symbol": symbol,
            "RefPrice": "129",
            "BidPrice1": "130.4",
            "BidVol1": "1000",
            "AskPrice1": "130.6",
            "AskVol1": "2000",
        },
    }


def _x_combined(symbol: str = "FPT"):
    payload = _x_quote(symbol)
    payload["DataType"] = "X"
    payload["Content"]["RType"] = "X"
    payload["Content"]["LastPrice"] = "130.7"
    return payload


def _r_foreign_room(symbol: str = "FPT", current_room: str = "123000000"):
    return {
        "DataType": "R",
        "Content": {
            "RType": "R",
            "TradingDate": "25/06/2026",
            "Time": "10:01:04",
            "Symbol": symbol,
            "Exchange": "HOSE",
            "TotalRoom": "123456789",
            "CurrentRoom": current_room,
            "FBuyVol": "100000",
            "FSellVol": "50000",
            "FBuyVal": "7200000000",
            "FSellVal": "3600000000",
        },
    }


def _mi_index(index_code: str = "VNINDEX", index_value: str = "1234.56"):
    return {
        "DataType": "MI",
        "Content": {
            "RType": "MI",
            "TradingDate": "25/06/2026",
            "Time": "10:01:05",
            "IndexCode": index_code,
            "Exchange": "HOSE",
            "IndexValue": index_value,
            "IndexValEst": "1234.50",
            "Change": "5.67",
            "RatioChange": "0.46",
            "TotalTrade": "123456",
            "TotalQtty": "123456789",
            "TotalValue": "1234567890000",
            "Advances": "200",
            "Nochanges": "50",
            "Declines": "180",
        },
    }


def _f_status(symbol: str = "FPT", *, session: str = "CONTINUOUS", status: str = "OPEN"):
    return {
        "DataType": "F",
        "Content": {
            "RType": "F",
            "TradingDate": "25/06/2026",
            "Time": "10:01:04",
            "Symbol": symbol,
            "Exchange": "HOSE",
            "TradingSession": session,
            "TradingStatus": status,
        },
    }


def _service_with_fetcher(fetcher, *, streaming_enabled: bool = True) -> VietnamMarketService:
    clear_vietnam_cache()
    return VietnamMarketService(
        config=VietnamDashboardConfig(
            daily_data_provider="ssi",
            chart_data_provider="ssi",
            daily_stock_price_provider="ssi",
            index_data_provider="ssi",
            intraday_data_provider="ssi",
            ssi_intraday_enabled=True,
            realtime_data_provider="ssi",
            trade_tape_provider="ssi",
            ssi_realtime_enabled=True,
            ssi_streaming_realtime_enabled=streaming_enabled,
            ssi_trade_tape_enabled=True,
            kbs_enabled=False,
            allow_legacy_kbs_provider=False,
            news_provider="disabled",
            mozyfin_enabled=False,
            mozyfin_news_enabled=False,
        ),
        ssi_fetcher=fetcher,
    )


def test_streaming_manager_default_disabled_returns_unavailable_and_does_not_start_client():
    calls = {"factory": 0}

    def factory():
        calls["factory"] += 1
        return FakeStreamClient()

    manager = SsiStreamingRealtimeManager(enabled=False, client_factory=factory)

    start_status = manager.start(["FPT"])
    payload = manager.snapshot(["FPT"])

    assert start_status["manager_state"] == "disabled"
    assert payload["status"] == "unavailable"
    assert payload["reason"] == SSI_STREAMING_REALTIME_DISABLED_REASON
    assert calls["factory"] == 0


def test_importing_streaming_module_does_not_import_official_client_or_start_network():
    sys.modules.pop("ssi_fc_data.fc_md_stream", None)

    module = importlib.reload(importlib.import_module("data_provider.ssi_streaming_realtime"))

    assert "ssi_fc_data.fc_md_stream" not in sys.modules
    assert not hasattr(module, "STREAMING_MANAGER")
    assert not hasattr(module, "STREAMING_CLIENT")


def test_streaming_channel_builder_includes_realtime_order_book_trade_tape_and_session_channels_without_duplicates():
    channels = build_streaming_channels(["fpt", "FPT"])

    assert channels == [
        "X:FPT",
        "X-QUOTE:FPT",
        "R:FPT",
        "X-TRADE:FPT",
        "F:FPT",
        "MI:VNINDEX",
        "MI:VN30",
        "MI:HNX",
        "MI:UPCOM",
    ]
    assert len(channels) == len(set(channels))
    assert all("ALL" not in channel for channel in channels)


def test_streaming_channel_builder_can_disable_trade_tape_channel():
    assert build_streaming_channels(["fpt"], trade_tape_enabled=False) == [
        "X:FPT",
        "X-QUOTE:FPT",
        "R:FPT",
        "F:FPT",
        "MI:VNINDEX",
        "MI:VN30",
        "MI:HNX",
        "MI:UPCOM",
    ]
    assert build_order_book_channel("fpt") == "X-QUOTE:FPT"
    assert build_foreign_room_channel("fpt") == "R:FPT"
    assert build_market_index_channel("vnindex") == "MI:VNINDEX"
    assert build_trade_tape_channel("fpt") == "X-TRADE:FPT"
    assert build_session_status_channel("fpt") == "F:FPT"


def test_manager_start_uses_symbol_scoped_realtime_and_trade_tape_channels():
    client = FakeStreamClient()
    manager = _manager(client=client)

    status = manager.start(["fpt"])

    assert status["manager_state"] == MANAGER_RUNNING
    assert client.started is True
    assert client.channels == [
        "X:FPT",
        "X-QUOTE:FPT",
        "R:FPT",
        "X-TRADE:FPT",
        "F:FPT",
        "MI:VNINDEX",
        "MI:VN30",
        "MI:HNX",
        "MI:UPCOM",
    ]
    assert status["realtime_channels"] == ["X:FPT"]
    assert status["order_book_channels"] == ["X-QUOTE:FPT"]
    assert status["order_book_subscription_status"] == "subscribed"
    assert status["foreign_room_channels"] == ["R:FPT"]
    assert status["foreign_room_subscription_status"] == "subscribed"
    assert status["trade_tape_channels"] == ["X-TRADE:FPT"]
    assert status["trade_tape_subscription_status"] == "subscribed"
    assert status["session_status_channels"] == ["F:FPT"]
    assert status["session_status_subscription_status"] == "subscribed"
    assert status["market_index_channels"] == ["MI:VNINDEX", "MI:VN30", "MI:HNX", "MI:UPCOM"]
    assert status["market_index_subscription_status"] == "subscribed"
    assert all("ALL" not in channel for channel in client.channels)


def test_explicit_old_space_channel_template_remains_respected():
    assert build_symbol_channel("fpt", "X: {symbol}") == "X: FPT"


def test_manager_rejects_all_channel_subscription_without_starting_client():
    client = FakeStreamClient()
    manager = _manager(client=client)

    status = manager.start(["ALL"])

    assert status["manager_state"] == MANAGER_ERRORED
    assert client.started is False
    assert "ALL channel" in str(status["latest_error"])


def test_manager_stop_is_idempotent():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.stop()
    manager.stop()

    assert client.stop_calls == 1


def test_manager_start_error_is_sanitized():
    client = FakeStreamClient(fail_start=True)
    manager = _manager(client=client)

    status = manager.start(["FPT"])
    payload = manager.snapshot(["FPT"])

    assert status["manager_state"] == MANAGER_ERRORED
    assert payload["reason"] == SSI_STREAMING_REALTIME_MANAGER_ERROR_REASON
    assert SECRET_TOKEN not in str(status)
    assert SECRET_TOKEN not in str(payload)
    assert "<redacted>" in str(status)


def test_x_trade_message_updates_snapshot_and_trade_tape_buffer():
    now = [_vn_epoch(2026, 6, 8, 9, 20)]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now)
    manager.start(["FPT"])

    manager.handle_message(_x_trade())
    payload = manager.snapshot(["FPT"])
    trade_payload = manager.trade_tape("FPT", limit=10)

    assert payload["status"] == "ok"
    assert payload["streaming_status"] == "cache_hit"
    assert payload["quotes"][0]["ticker"] == "FPT"
    assert payload["quotes"][0]["stream_data_type"] == "X-TRADE"
    assert payload["quotes"][0]["price"] == 130.5
    assert payload["quotes"][0]["has_last_trade"] is True
    assert "trades" not in payload["quotes"][0]
    assert trade_payload["status"] == "ok"
    assert trade_payload["streaming_status"] == "cache_hit"
    assert trade_payload["trades"][0]["ticker"] == "FPT"
    assert trade_payload["trades"][0]["price"] == 130.5
    assert trade_payload["trades"][0]["volume"] == 1000.0
    assert trade_payload["trades"][0]["timestamp"] == "2026-06-25T10:01:02"
    assert trade_payload["trades"][0]["raw_type"] == "X-TRADE"
    assert trade_payload["diagnostics"]["trade_tape_returned_row_count"] == 1


def test_f_session_status_message_updates_dedicated_session_status_cache_only():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.handle_message(_f_status(session="ATO", status="OPEN"))
    session_payload = manager.session_status("FPT")
    quote_payload = manager.snapshot(["FPT"])

    assert session_payload["status"] == "ok"
    assert session_payload["streaming_status"] == "cache_hit"
    assert session_payload["session_status"]["ticker"] == "FPT"
    assert session_payload["session_status"]["stream_data_type"] == "F"
    assert session_payload["session_status"]["trading_session"] == "ATO"
    assert session_payload["session_status"]["trading_status"] == "OPEN"
    assert session_payload["session_status"]["trading_date"] == "2026-06-25"
    assert session_payload["diagnostics"]["session_status_rows_observed"] == 1
    assert quote_payload["status"] == "unavailable"
    assert quote_payload["cache_status"] == "empty"
    assert quote_payload["quotes"] == []


def test_f_session_status_malformed_message_is_dropped_without_fake_state():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.handle_message({"DataType": "F", "Content": {"RType": "F", "Symbol": "FPT"}})
    payload = manager.session_status("FPT")

    assert payload["status"] == "unavailable"
    assert payload["streaming_status"] == "subscribed_no_event"
    assert payload["cache_status"] == "empty"
    assert payload["session_status"] is None
    assert payload["diagnostics"]["session_status_rows_observed"] == 0


def test_f_session_status_reports_stale_without_returning_live_row():
    now = [1000.0]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now)
    manager.start(["FPT"])
    manager.handle_message(_f_status(status="OPEN"))

    now[0] += 16
    payload = manager.session_status("FPT")

    assert payload["status"] == "unavailable"
    assert payload["streaming_status"] == "cache_stale"
    assert payload["cache_status"] == "stale"
    assert payload["session_status"] is None
    assert payload["diagnostics"]["latest_session_age_seconds"] == 16


def test_f_session_status_reports_channel_not_subscribed():
    client = FakeStreamClient()
    manager = _manager(client=client, session_status_enabled=False)
    manager.start(["FPT"])

    payload = manager.session_status("FPT")

    assert payload["status"] == "unavailable"
    assert payload["streaming_status"] == "f_disabled"
    assert payload["cache_status"] == "disabled"
    assert payload["session_status"] is None


@pytest.mark.parametrize(
    ("raw_side", "expected_side", "expected_label"),
    [
        ("B", "buy", "Buy"),
        ("BU", "buy", "Buy"),
        (" bu ", "buy", "Buy"),
        ("BUY", "buy", "Buy"),
        ("MUA", "buy", "Buy"),
        ("1", "buy", "Buy"),
        ("S", "sell", "Sell"),
        ("SD", "sell", "Sell"),
        (" sd ", "sell", "Sell"),
        ("SELL", "sell", "Sell"),
        ("BAN", "sell", "Sell"),
        ("BÁN", "sell", "Sell"),
        ("2", "sell", "Sell"),
        ("matched", None, None),
        ("XX", None, None),
    ],
)
def test_x_trade_side_normalizes_only_explicit_side_values(raw_side, expected_side, expected_label):
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.handle_message(_x_trade(side=raw_side))
    trade = manager.trade_tape("FPT", limit=10)["trades"][0]

    assert trade["side"] == expected_side
    assert trade["side_label"] == expected_label
    assert trade["side_if_available"] == raw_side


def test_x_trade_side_is_not_inferred_from_price_move():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.handle_message(_x_trade(price="138.0", side=None))
    trade = manager.trade_tape("FPT", limit=10)["trades"][0]

    assert trade["price"] == 138.0
    assert trade["side"] is None
    assert trade["side_label"] is None


def test_x_quote_message_updates_order_book_context_without_inventing_realtime_or_trade_rows():
    now = [_vn_epoch(2026, 6, 8, 9, 20)]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now)
    manager.start(["FPT"])

    manager.handle_message(_x_quote())
    snapshot_payload = manager.snapshot(["FPT"])
    order_book_payload = manager.order_book("FPT")

    assert snapshot_payload["status"] == "unavailable"
    assert snapshot_payload["quotes"] == []
    assert order_book_payload["status"] == "ok"
    assert order_book_payload["streaming_status"] == "cache_hit"
    assert order_book_payload["order_book"]["ticker"] == "FPT"
    assert order_book_payload["order_book"]["stream_data_type"] == "X-QUOTE"
    assert order_book_payload["order_book"]["bids"][0] == {"level": 1, "price": 130.4, "volume": 1000.0}
    assert order_book_payload["order_book"]["asks"][0] == {"level": 1, "price": 130.6, "volume": 2000.0}
    assert order_book_payload["diagnostics"]["order_book_rows_observed"] == 1
    assert manager.trade_tape("FPT")["trades"] == []


def test_r_foreign_room_message_updates_dedicated_cache_only():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.handle_message(_r_foreign_room())
    snapshot_payload = manager.snapshot(["FPT"])
    foreign_room_payload = manager.foreign_room("FPT")

    assert snapshot_payload["status"] == "unavailable"
    assert snapshot_payload["quotes"] == []
    assert foreign_room_payload["status"] == "ok"
    assert foreign_room_payload["streaming_status"] == "cache_hit"
    assert foreign_room_payload["foreign_room"]["ticker"] == "FPT"
    assert foreign_room_payload["foreign_room"]["stream_data_type"] == "R"
    assert foreign_room_payload["foreign_room"]["total_room"] == 123456789.0
    assert foreign_room_payload["foreign_room"]["current_room"] == 123000000.0
    assert foreign_room_payload["foreign_room"]["foreign_buy_volume"] == 100000.0
    assert foreign_room_payload["foreign_room"]["foreign_sell_volume"] == 50000.0
    assert foreign_room_payload["foreign_room"]["foreign_buy_value"] == 7200000000.0
    assert foreign_room_payload["foreign_room"]["foreign_sell_value"] == 3600000000.0
    assert foreign_room_payload["foreign_room"]["value_semantics_status"] == "needs_semantics_proof"
    assert foreign_room_payload["diagnostics"]["foreign_room_rows_observed"] == 1
    assert manager.order_book("FPT")["order_book"] is None
    assert manager.trade_tape("FPT")["trades"] == []
    assert manager.session_status("FPT")["session_status"] is None


def test_r_foreign_room_drops_malformed_numeric_fields_without_fake_row():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.handle_message(
        {
            "DataType": "R",
            "Content": {
                "RType": "R",
                "TradingDate": "25/06/2026",
                "Time": "10:01:04",
                "Symbol": "FPT",
                "TotalRoom": "bad",
                "CurrentRoom": "-1",
                "FBuyVol": "--",
                "FSellVol": "-5",
                "FBuyVal": "nan",
                "FSellVal": "",
            },
        }
    )

    payload = manager.foreign_room("FPT")

    assert payload["status"] == "unavailable"
    assert payload["streaming_status"] == "subscribed_no_event"
    assert payload["foreign_room"] is None
    assert payload["diagnostics"]["foreign_room_rows_observed"] == 0


def test_r_foreign_room_reports_stale_without_returning_live_row():
    now = [1000.0]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now)
    manager.start(["FPT"])
    manager.handle_message(_r_foreign_room())

    now[0] += 16
    payload = manager.foreign_room("FPT")

    assert payload["status"] == "unavailable"
    assert payload["streaming_status"] == "cache_stale"
    assert payload["cache_status"] == "stale"
    assert payload["foreign_room"] is None
    assert payload["diagnostics"]["latest_foreign_room_age_seconds"] == 16


def test_r_foreign_room_reports_not_subscribed_when_channel_is_missing():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])
    with manager._lock:
        manager._channels = ["X:FPT", "X-QUOTE:FPT", "X-TRADE:FPT", "F:FPT"]

    payload = manager.foreign_room("FPT")

    assert payload["status"] == "unavailable"
    assert payload["streaming_status"] == "r_not_subscribed"
    assert payload["cache_status"] == "not_subscribed"
    assert payload["foreign_room"] is None
    assert payload["diagnostics"]["foreign_room_channels"] == []


def test_mi_market_index_message_updates_dedicated_cache_only():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.handle_message(_mi_index())
    pulse_payload = manager.market_index_pulse(["VNINDEX"])

    assert pulse_payload["status"] == "ok"
    assert pulse_payload["streaming_status"] == "cache_hit"
    assert pulse_payload["market_index_pulse"][0]["index_code"] == "VNINDEX"
    assert pulse_payload["market_index_pulse"][0]["stream_data_type"] == "MI"
    assert pulse_payload["market_index_pulse"][0]["index_value"] == 1234.56
    assert pulse_payload["market_index_pulse"][0]["estimated_index_value"] == 1234.50
    assert pulse_payload["market_index_pulse"][0]["change"] == 5.67
    assert pulse_payload["market_index_pulse"][0]["change_pct"] == 0.46
    assert pulse_payload["market_index_pulse"][0]["total_volume"] == 123456789.0
    assert pulse_payload["market_index_pulse"][0]["advances"] == 200.0
    assert pulse_payload["diagnostics"]["market_index_rows_observed"] == 1
    assert manager.snapshot(["FPT"])["quotes"] == []
    assert manager.order_book("FPT")["order_book"] is None
    assert manager.foreign_room("FPT")["foreign_room"] is None
    assert manager.trade_tape("FPT")["trades"] == []
    assert manager.session_status("FPT")["session_status"] is None


def test_mi_market_index_drops_malformed_numeric_fields_without_fake_row():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.handle_message(_mi_index(index_value="bad"))
    payload = manager.market_index_pulse(["VNINDEX"])

    assert payload["status"] == "ok"
    assert payload["market_index_pulse"][0]["index_value"] is None
    assert payload["market_index_pulse"][0]["change"] == 5.67

    manager.handle_message(
        {
            "DataType": "MI",
            "Content": {"RType": "MI", "IndexCode": "VN30", "IndexValue": "bad", "TotalQtty": "-1"},
        }
    )
    empty_payload = manager.market_index_pulse(["VN30"])
    assert empty_payload["status"] == "unavailable"
    assert empty_payload["market_index_pulse"] == []


def test_mi_market_index_reports_stale_without_returning_live_row():
    now = [1000.0]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now)
    manager.start(["FPT"])
    manager.handle_message(_mi_index())

    now[0] = 1016.0
    payload = manager.market_index_pulse(["VNINDEX"])

    assert payload["status"] == "unavailable"
    assert payload["streaming_status"] == "cache_stale"
    assert payload["market_index_pulse"] == []
    assert payload["diagnostics"]["latest_market_index_age_seconds"] == 16


def test_mi_market_index_reports_not_subscribed_when_channel_is_missing():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])
    with manager._lock:
        manager._channels = ["X:FPT", "X-QUOTE:FPT", "R:FPT", "X-TRADE:FPT", "F:FPT"]

    payload = manager.market_index_pulse(["VNINDEX"])

    assert payload["status"] == "unavailable"
    assert payload["streaming_status"] == "mi_not_subscribed"
    assert payload["market_index_pulse"] == []
    assert payload["diagnostics"]["market_index_channels"] == []


def test_mi_market_index_disabled_does_not_subscribe_channel():
    client = FakeStreamClient()
    manager = _manager(client=client, market_index_enabled=False)

    status = manager.start(["FPT"])
    payload = manager.market_index_pulse(["VNINDEX"])

    assert "MI:VNINDEX" not in client.channels
    assert status["market_index_channels"] == []
    assert status["market_index_subscription_status"] == "disabled"
    assert payload["streaming_status"] == "mi_disabled"
    assert payload["market_index_pulse"] == []


def test_x_quote_drops_malformed_order_book_levels_without_fake_rows():
    now = [_vn_epoch(2026, 6, 8, 9, 20)]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now)
    manager.start(["FPT"])

    manager.handle_message({
        "DataType": "X-QUOTE",
        "Content": {
            "RType": "X-QUOTE",
            "TradingDate": "25/06/2026",
            "Time": "10:01:03",
            "Symbol": "FPT",
            "BidPrice1": "0",
            "BidVol1": "1000",
            "BidPrice2": "130.3",
            "BidVol2": "-1",
            "AskPrice1": "bad",
            "AskVol1": "2000",
        },
    })

    payload = manager.order_book("FPT")

    assert payload["status"] == "unavailable"
    assert payload["streaming_status"] == "subscribed_no_event"
    assert payload["order_book"] is None
    assert payload["diagnostics"]["order_book_rows_observed"] == 0


def test_x_quote_order_book_returns_stale_last_known_ladder():
    now = [_vn_epoch(2026, 6, 8, 9, 20)]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now)
    manager.start(["FPT"])
    manager.handle_message(_x_quote())

    now[0] += 16
    payload = manager.order_book("FPT")

    assert payload["status"] == "stale"
    assert payload["streaming_status"] == "cache_stale"
    assert payload["cache_status"] == "stale"
    assert payload["order_book"]["ticker"] == "FPT"
    assert payload["order_book"]["is_stale"] is True
    assert payload["order_book"]["stale_reason"] == "SSI streaming realtime cache stale."
    assert payload["order_book"]["bids"][0] == {"level": 1, "price": 130.4, "volume": 1000.0}
    assert payload["order_book"]["asks"][0] == {"level": 1, "price": 130.6, "volume": 2000.0}
    assert payload["diagnostics"]["latest_order_book_age_seconds"] == 16


def test_x_quote_order_book_after_hours_preserves_last_known_ladder_with_market_closed_label():
    now = [_vn_epoch(2026, 6, 8, 14, 44)]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now)
    manager.start(["FPT"])
    manager.handle_message(_x_quote())

    now[0] = _vn_epoch(2026, 6, 8, 16, 0)
    payload = manager.order_book("FPT")

    assert payload["status"] == "stale"
    assert payload["streaming_status"] == "after_hours_stale"
    assert payload["cache_status"] == "stale"
    assert payload["reason"] == "Market closed — showing last known data."
    assert payload["order_book"]["ticker"] == "FPT"
    assert payload["order_book"]["is_stale"] is True
    assert payload["order_book"]["stale_reason"] == "Market closed — showing last known data."
    assert payload["diagnostics"]["stream_health"] == "after_hours_stale"
    assert payload["diagnostics"]["market_session_active"] is False


def test_x_quote_order_book_reports_not_subscribed_when_channel_is_missing():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])
    with manager._lock:
        manager._channels = ["X:FPT", "X-TRADE:FPT", "F:FPT"]

    payload = manager.order_book("FPT")

    assert payload["status"] == "unavailable"
    assert payload["streaming_status"] == "xquote_not_subscribed"
    assert payload["cache_status"] == "not_subscribed"
    assert payload["order_book"] is None
    assert payload["diagnostics"]["order_book_channels"] == []


def test_x_message_updates_snapshot_when_fields_exist():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.handle_message(_x_combined())
    payload = manager.snapshot(["FPT"])

    assert payload["status"] == "ok"
    assert payload["quotes"][0]["stream_data_type"] == "X"
    assert payload["quotes"][0]["price"] == 130.7
    assert payload["quotes"][0]["ask_levels"][0] == {"price": 130.6, "volume": 2000.0}
    assert manager.trade_tape("FPT")["trades"] == []


def test_malformed_message_does_not_crash_manager():
    now = [_vn_epoch(2026, 6, 8, 9, 20)]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now)
    manager.start(["FPT"])

    manager.handle_message({"DataType": "X-TRADE", "Content": '{"RType":"X-TRADE",'})
    payload = manager.snapshot(["FPT"])

    assert manager.state == MANAGER_RUNNING
    assert payload["status"] == "unavailable"
    assert payload["reason"] == SSI_STREAMING_REALTIME_CACHE_EMPTY_REASON


def test_message_for_unrequested_symbol_is_ignored():
    now = [_vn_epoch(2026, 6, 8, 9, 20)]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now)
    manager.start(["FPT"])

    manager.handle_message(_x_trade("SSI", "32"))
    payload = manager.snapshot(["FPT"])

    assert payload["status"] == "unavailable"
    assert payload["reason"] == SSI_STREAMING_REALTIME_CACHE_EMPTY_REASON


def test_empty_and_stale_cache_return_unavailable():
    now = [_vn_epoch(2026, 6, 8, 9, 20)]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now)
    manager.start(["FPT"])

    assert manager.snapshot(["FPT"])["reason"] == SSI_STREAMING_REALTIME_CACHE_EMPTY_REASON
    manager.handle_message(_x_trade())
    now[0] += 20.0
    stale_payload = manager.snapshot(["FPT"])

    assert stale_payload["status"] == "unavailable"
    assert stale_payload["reason"] == SSI_STREAMING_REALTIME_CACHE_STALE_REASON
    assert stale_payload["cache_status"] == "stale"
    assert manager.trade_tape("FPT")["status"] == "ok"
    now[0] += 50.0
    stale_trades = manager.trade_tape("FPT")
    assert stale_trades["status"] == "ok"
    assert stale_trades["trades"][0]["ticker"] == "FPT"
    assert stale_trades["trades"][0]["price"] == 130.5
    assert stale_trades["trades"][0]["volume"] == 1000.0
    assert stale_trades["trades"][0]["timestamp"] == "2026-06-25T10:01:02"
    assert stale_trades["trades"][0]["is_stale"] is True
    assert stale_trades["streaming_status"] == "cache_stale"
    assert stale_trades["cache_status"] == "stale"
    assert stale_trades["diagnostics"]["trade_tape_buffer_row_count"] == 1
    assert stale_trades["diagnostics"]["trade_tape_returned_row_count"] == 1


def test_after_hours_trade_tape_preserves_stale_rows_with_market_closed_label():
    now = [_vn_epoch(2026, 6, 8, 14, 44)]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now)
    manager.start(["FPT"])
    manager.handle_message(_x_trade())

    now[0] = _vn_epoch(2026, 6, 8, 16, 0)
    payload = manager.trade_tape("FPT")

    assert payload["status"] == "ok"
    assert payload["streaming_status"] == "after_hours_stale"
    assert payload["reason"] == "Market closed — showing last known data."
    assert payload["trades"][0]["ticker"] == "FPT"
    assert payload["diagnostics"]["stream_health"] == "after_hours_stale"
    assert payload["diagnostics"]["market_session_active"] is False


def test_trade_tape_skips_xtrade_rows_missing_required_trade_fields():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.handle_message({
        "DataType": "X-TRADE",
        "Content": {
            "RType": "X-TRADE",
            "TradingDate": "25/06/2026",
            "Time": "10:01:02",
            "Symbol": "FPT",
            "LastPrice": "130.5",
        },
    })
    manager.handle_message({
        "DataType": "X-TRADE",
        "Content": {
            "RType": "X-TRADE",
            "TradingDate": "25/06/2026",
            "Time": "10:01:03",
            "Symbol": "FPT",
            "LastVol": "1000",
        },
    })

    payload = manager.trade_tape("FPT")

    assert payload["status"] == "unavailable"
    assert payload["trades"] == []
    assert payload["diagnostics"]["trade_tape_buffer_row_count"] == 0


def test_trade_tape_for_non_bootstrapped_symbol_is_unavailable_without_subscription():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    payload = manager.trade_tape("SSI")

    assert payload["status"] == "unavailable"
    assert payload["trades"] == []
    assert payload["streaming_status"] == "ticker_not_bootstrapped"
    assert payload["diagnostics"]["bootstrap_membership"] == "not_bootstrapped"
    assert client.channels == [
        "X:FPT",
        "X-QUOTE:FPT",
        "R:FPT",
        "X-TRADE:FPT",
        "F:FPT",
        "MI:VNINDEX",
        "MI:VN30",
        "MI:HNX",
        "MI:UPCOM",
    ]


def test_trade_tape_disabled_does_not_subscribe_xtrade_channel():
    client = FakeStreamClient()
    manager = _manager(client=client, trade_tape_enabled=False)

    status = manager.start(["FPT"])
    payload = manager.trade_tape("FPT")

    assert status["realtime_channels"] == ["X:FPT"]
    assert status["order_book_channels"] == ["X-QUOTE:FPT"]
    assert status["trade_tape_channels"] == []
    assert status["trade_tape_subscription_status"] == "disabled"
    assert client.channels == [
        "X:FPT",
        "X-QUOTE:FPT",
        "R:FPT",
        "F:FPT",
        "MI:VNINDEX",
        "MI:VN30",
        "MI:HNX",
        "MI:UPCOM",
    ]
    assert payload["status"] == "unavailable"
    assert payload["streaming_status"] == "xtrade_disabled"
    assert payload["trades"] == []


def test_foreign_room_disabled_does_not_subscribe_r_channel():
    client = FakeStreamClient()
    manager = _manager(client=client, foreign_room_enabled=False)

    status = manager.start(["FPT"])
    payload = manager.foreign_room("FPT")

    assert status["realtime_channels"] == ["X:FPT"]
    assert status["foreign_room_channels"] == []
    assert status["foreign_room_subscription_status"] == "disabled"
    assert client.channels == [
        "X:FPT",
        "X-QUOTE:FPT",
        "X-TRADE:FPT",
        "F:FPT",
        "MI:VNINDEX",
        "MI:VN30",
        "MI:HNX",
        "MI:UPCOM",
    ]
    assert payload["status"] == "unavailable"
    assert payload["streaming_status"] == "r_disabled"
    assert payload["foreign_room"] is None


def test_trade_tape_reports_not_subscribed_when_xtrade_channel_is_missing():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])
    with manager._lock:
        manager._channels = ["X:FPT"]

    payload = manager.trade_tape("FPT")

    assert payload["status"] == "unavailable"
    assert payload["streaming_status"] == "xtrade_not_subscribed"
    assert payload["cache_status"] == "not_subscribed"
    assert payload["trades"] == []
    assert payload["diagnostics"]["trade_tape_channels"] == []


def test_running_manager_with_no_messages_past_idle_timeout_reports_idle():
    now = [_vn_epoch(2026, 6, 8, 9, 20)]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now, idle_timeout_seconds=10)
    manager.start(["FPT"])

    now[0] += 11.0
    status = manager.status()
    payload = manager.snapshot(["FPT"])

    assert status["is_idle"] is True
    assert status["runtime_status"] == RUNTIME_RUNNING_IDLE
    assert status["stream_health"] == "stale"
    assert status["market_session"] == "continuous_morning"
    assert status["market_session_active"] is True
    assert status["last_message_age_seconds"] is None
    assert payload["diagnostics"]["is_idle"] is True
    assert payload["diagnostics"]["runtime_status"] == RUNTIME_RUNNING_IDLE


def test_running_manager_with_recent_message_reports_not_idle():
    now = [_vn_epoch(2026, 6, 8, 9, 20)]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now, idle_timeout_seconds=10)
    manager.start(["FPT"])
    now[0] += 5.0
    manager.handle_message(_x_trade())
    now[0] += 7.0

    status = manager.status()

    assert status["is_idle"] is False
    assert status["runtime_status"] == MANAGER_RUNNING
    assert status["stream_health"] == "healthy"
    assert status["last_message_age_seconds"] == 7
    assert status["subscription_count"] == status["expected_subscription_count"]


def test_closed_market_idle_stream_does_not_schedule_stale_reconnect():
    now = [_vn_epoch(2026, 6, 8, 16, 0)]
    client = FakeStreamClient()
    manager = _manager(
        client=client,
        now=now,
        idle_timeout_seconds=10,
        reconnect_enabled=True,
    )
    manager.start(["FPT"])
    now[0] += 20.0

    status = manager.monitor_tick(wants_streaming=True)

    assert status["is_idle"] is True
    assert status["stream_health"] == "idle_market_closed"
    assert status["market_session"] == "closed"
    assert status["market_session_active"] is False
    assert status["last_reconnect_reason"] is None
    assert status["next_reconnect_at"] is None
    assert status["reconnect_attempt_count"] == 0
    assert client.stop_calls == 0


def test_closed_market_stream_before_idle_reports_market_closed_without_reconnect():
    now = [_vn_epoch(2026, 6, 8, 16, 0)]
    client = FakeStreamClient()
    manager = _manager(
        client=client,
        now=now,
        idle_timeout_seconds=10,
        reconnect_enabled=True,
    )
    manager.start(["FPT"])

    status = manager.monitor_tick(wants_streaming=True)
    snapshot = manager.snapshot(["FPT"])
    order_book = manager.order_book("FPT")
    trade_tape = manager.trade_tape("FPT")

    assert status["stream_health"] == "market_closed"
    assert status["market_session"] == "closed"
    assert status["last_reconnect_reason"] is None
    assert status["next_reconnect_at"] is None
    assert status["reconnect_attempt_count"] == 0
    assert client.stop_calls == 0
    assert snapshot["streaming_status"] == "market_closed"
    assert snapshot["reason"] == "Market closed — no live realtime snapshot expected."
    assert order_book["streaming_status"] == "market_closed"
    assert order_book["reason"] == "Market closed — no live order-book rows expected."
    assert trade_tape["streaming_status"] == "market_closed"
    assert trade_tape["reason"] == "Market closed — no live trade rows expected."


def test_stale_running_stream_schedules_debounced_reconnect_once():
    now = [_vn_epoch(2026, 6, 8, 9, 20)]
    clients = [FakeStreamClient()]
    manager = _manager(
        client=clients[0],
        now=now,
        idle_timeout_seconds=10,
        reconnect_enabled=True,
    )
    manager.start(["FPT"])
    now[0] += 20.0

    status = manager.monitor_tick(wants_streaming=True)

    assert status["is_idle"] is True
    assert status["runtime_status"] == RUNTIME_RECONNECTING
    assert status["stream_health"] == "reconnecting"
    assert status["reconnect_attempt_count"] == 0
    assert status["reconnect_count"] == 0
    assert status["last_reconnect_reason"] == "stream_stale"
    assert status["next_reconnect_at"] is not None
    assert clients[0].stop_calls == 0

    again = manager.monitor_tick(wants_streaming=True)

    assert again["reconnect_attempt_count"] == 0
    assert clients[0].stop_calls == 0


def test_stale_running_stream_reconnects_and_preserves_existing_buffers():
    now = [_vn_epoch(2026, 6, 8, 9, 20)]
    clients = [FakeStreamClient(), FakeStreamClient()]

    def factory():
        return clients.pop(0)

    parser_fetcher = _fetcher()
    manager = SsiStreamingRealtimeManager(
        enabled=True,
        parser=parser_fetcher.normalize_streaming_realtime_messages,
        client_factory=factory,
        cache=RealtimeSnapshotCache(15, time_func=lambda: now[0]),
        order_book_cache=OrderBookCache(15, time_func=lambda: now[0]),
        idle_timeout_seconds=10,
        reconnect_initial_delay_seconds=2,
        time_func=lambda: now[0],
    )
    manager.start(["FPT"])
    first_client = manager._client
    first_channels = list(first_client.channels)
    manager.handle_message(_x_trade())
    manager.handle_message(_x_quote())
    assert manager.trade_tape("FPT")["count"] == 1
    assert manager.order_book("FPT")["count"] == 1

    now[0] += 20.0
    scheduled = manager.monitor_tick(wants_streaming=True)
    assert scheduled["last_reconnect_reason"] == "stream_stale"
    assert scheduled["reconnect_attempt_count"] == 0
    now[0] += 2.0

    status = manager.monitor_tick(wants_streaming=True)

    assert status["manager_state"] == MANAGER_RUNNING
    assert status["stream_health"] == "stale"
    assert status["reconnect_attempt_count"] == 1
    assert status["reconnect_count"] == 1
    assert status["last_reconnect_reason"] == "stream_stale"
    assert first_client.stop_calls == 1
    assert manager._client.channels == first_channels
    assert len(manager._client.channels) == len(set(manager._client.channels))
    assert manager.trade_tape("FPT")["count"] == 1
    assert manager.order_book("FPT")["count"] == 1


def test_stale_running_stream_reconnect_failure_is_reported_without_crashing():
    now = [_vn_epoch(2026, 6, 8, 9, 20)]
    clients = [FakeStreamClient(), FakeStreamClient(fail_start=True)]

    def factory():
        return clients.pop(0)

    parser_fetcher = _fetcher()
    manager = SsiStreamingRealtimeManager(
        enabled=True,
        parser=parser_fetcher.normalize_streaming_realtime_messages,
        client_factory=factory,
        idle_timeout_seconds=10,
        reconnect_initial_delay_seconds=2,
        reconnect_max_delay_seconds=5,
        time_func=lambda: now[0],
    )
    manager.start(["FPT"])
    now[0] += 20.0
    manager.monitor_tick(wants_streaming=True)
    now[0] += 2.0

    status = manager.monitor_tick(wants_streaming=True)

    assert status["manager_state"] == MANAGER_ERRORED
    assert status["stream_health"] == "failed"
    assert status["runtime_status"] == RUNTIME_RECONNECTING
    assert status["last_reconnect_reason"] == "stream_stale"
    assert SECRET_TOKEN not in str(status["last_reconnect_error"])
    assert "<redacted>" in str(status["last_reconnect_error"])
    assert status["reconnect_attempt_count"] == 1


def test_running_idle_realtime_does_not_make_daily_data_invalid():
    now = [100.0]
    client = FakeStreamClient()
    parser_fetcher = _fetcher(streaming_realtime_enabled=True)
    manager = SsiStreamingRealtimeManager(
        enabled=True,
        cache=RealtimeSnapshotCache(15, time_func=lambda: now[0]),
        parser=parser_fetcher.normalize_streaming_realtime_messages,
        client_factory=lambda: client,
        idle_timeout_seconds=10,
        time_func=lambda: now[0],
    )
    manager.start(["FPT"])
    now[0] = 120.0
    fetcher = _fetcher(
        streaming_realtime_enabled=True,
        streaming_realtime_manager=manager,
    )
    service = _service_with_fetcher(FakeMarketFetcher(fetcher))

    item = service.build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["realtime_status"]["status"] == "unavailable"
    assert item["diagnostics"]["realtime"]["runtime_status"] == RUNTIME_RUNNING_IDLE
    assert item["data_quality_summary"]["checks"]["daily_ohlc"] == "ok"


def test_reconnect_enabled_schedules_reconnect_after_start_failure():
    now = [100.0]
    manager = _manager(
        client=FakeStreamClient(fail_start=True),
        now=now,
        reconnect_initial_delay_seconds=2,
        reconnect_max_delay_seconds=10,
    )
    manager.start(["FPT"])

    status = manager.monitor_tick(wants_streaming=True)

    assert status["manager_state"] == MANAGER_ERRORED
    assert status["runtime_status"] == RUNTIME_RECONNECTING
    assert status["reconnect_attempt_count"] == 0
    assert status["last_reconnect_reason"] == "start_error"
    assert status["next_reconnect_at"] is not None


def test_reconnect_backoff_increases_and_caps_after_failed_attempts():
    now = [100.0]
    clients = []

    def factory():
        client = FakeStreamClient(fail_start=True)
        clients.append(client)
        return client

    parser_fetcher = _fetcher()
    manager = SsiStreamingRealtimeManager(
        enabled=True,
        parser=parser_fetcher.normalize_streaming_realtime_messages,
        client_factory=factory,
        idle_timeout_seconds=10,
        reconnect_initial_delay_seconds=2,
        reconnect_max_delay_seconds=5,
        time_func=lambda: now[0],
    )
    manager.start(["FPT"])
    first = manager.monitor_tick(wants_streaming=True)
    assert first["reconnect_backoff_seconds"] == 4

    now[0] = 102.0
    second = manager.monitor_tick(wants_streaming=True)
    assert second["reconnect_attempt_count"] == 1
    assert second["reconnect_backoff_seconds"] == 5

    now[0] = 106.0
    third = manager.monitor_tick(wants_streaming=True)
    assert third["reconnect_attempt_count"] == 2
    assert third["reconnect_backoff_seconds"] == 5
    assert len(clients) == 3


def test_reconnect_max_attempts_positive_stops_after_attempt_limit():
    now = [100.0]
    manager = _manager(
        client=FakeStreamClient(fail_start=True),
        now=now,
        reconnect_initial_delay_seconds=2,
        reconnect_max_attempts=1,
    )
    manager.start(["FPT"])
    manager.monitor_tick(wants_streaming=True)
    now[0] = 102.0

    status = manager.monitor_tick(wants_streaming=True)

    assert status["reconnect_attempt_count"] == 1
    assert status["next_reconnect_at"] is None
    assert status["last_reconnect_error"] is not None


def test_reconnect_max_attempts_zero_allows_unlimited_attempts():
    now = [100.0]
    manager = _manager(
        client=FakeStreamClient(fail_start=True),
        now=now,
        reconnect_initial_delay_seconds=1,
        reconnect_max_attempts=0,
    )
    manager.start(["FPT"])
    for expected_attempts in range(1, 4):
        manager.monitor_tick(wants_streaming=True)
        now[0] += manager.status()["reconnect_backoff_seconds"]
        status = manager.monitor_tick(wants_streaming=True)
        assert status["reconnect_attempt_count"] == expected_attempts


def test_reconnect_stops_previous_stream_before_starting_new_one():
    now = [100.0]
    clients = [FakeStreamClient(), FakeStreamClient()]

    def factory():
        return clients.pop(0)

    parser_fetcher = _fetcher()
    manager = SsiStreamingRealtimeManager(
        enabled=True,
        parser=parser_fetcher.normalize_streaming_realtime_messages,
        client_factory=factory,
        reconnect_initial_delay_seconds=2,
        time_func=lambda: now[0],
    )
    manager.start(["FPT"])
    first_client = manager._client
    manager.handle_error("stream transport error")
    manager.monitor_tick(wants_streaming=True)
    now[0] = 102.0

    status = manager.monitor_tick(wants_streaming=True)

    assert status["manager_state"] == MANAGER_RUNNING
    assert first_client.stop_calls == 1
    assert status["reconnect_attempt_count"] == 1


def test_repeated_monitor_ticks_before_due_do_not_create_parallel_streams():
    now = [100.0]
    clients = [FakeStreamClient(fail_start=True)]
    manager = _manager(
        client=clients[0],
        now=now,
        reconnect_initial_delay_seconds=5,
    )
    manager.start(["FPT"])

    manager.monitor_tick(wants_streaming=True)
    manager.monitor_tick(wants_streaming=True)
    manager.monitor_tick(wants_streaming=True)

    assert manager.status()["reconnect_attempt_count"] == 0


def test_fetcher_config_off_returns_unavailable_even_if_manager_cache_has_data():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])
    manager.handle_message(_x_trade())
    fetcher = _fetcher(
        streaming_realtime_enabled=False,
        streaming_realtime_manager=manager,
    )

    payload = fetcher.get_realtime_snapshot(["FPT"])

    assert payload["status"] == "unavailable"
    assert payload["reason"] == SSI_STREAMING_REALTIME_DISABLED_REASON
    assert payload["quotes"] == []


def test_service_config_off_returns_unavailable_even_if_fetcher_cache_has_data():
    client = FakeStreamClient()
    parser_fetcher = _fetcher(streaming_realtime_enabled=True)
    manager = SsiStreamingRealtimeManager(
        enabled=True,
        parser=parser_fetcher.normalize_streaming_realtime_messages,
        client_factory=lambda: client,
    )
    manager.start(["FPT"])
    manager.handle_message(_x_trade(price="131.5"))
    fetcher = _fetcher(
        streaming_realtime_enabled=True,
        streaming_realtime_manager=manager,
    )
    service = _service_with_fetcher(FakeMarketFetcher(fetcher), streaming_enabled=False)

    payload = service.build_realtime_snapshot(["FPT"], force_refresh=True)

    assert payload["status"] == "unavailable"
    assert payload["error"] == "SSI realtime manager disabled."
    assert payload["quotes"] == []
    assert payload["streaming_status"] == "disabled"


def test_fetcher_does_not_probe_rest_when_streaming_manager_not_started():
    fetcher = _fetcher(streaming_realtime_enabled=True)

    payload = fetcher.get_realtime_snapshot(["FPT"])

    assert payload["status"] == "unavailable"
    assert payload["reason"] == SSI_STREAMING_REALTIME_NOT_STARTED_REASON
    assert fetcher.session.calls == []


def test_official_client_factory_is_not_called_when_streaming_config_is_off():
    calls = {"factory": 0}

    def factory():
        calls["factory"] += 1
        return FakeStreamClient()

    fetcher = _fetcher(
        streaming_realtime_enabled=False,
        streaming_realtime_client_factory=factory,
    )

    payload = fetcher.get_realtime_snapshot(["FPT"])

    assert payload["reason"] == SSI_STREAMING_REALTIME_DISABLED_REASON
    assert calls["factory"] == 0


def test_fetcher_config_off_does_not_check_or_import_official_package(monkeypatch):
    def fail_find_spec(name):  # pragma: no cover - should not be called
        raise AssertionError("official package lookup must not run when streaming is disabled")

    monkeypatch.setattr("data_provider.ssi_fastconnect_fetcher.importlib.util.find_spec", fail_find_spec)
    fetcher = _fetcher(streaming_realtime_enabled=False)

    payload = fetcher.get_realtime_snapshot(["FPT"])

    assert payload["reason"] == SSI_STREAMING_REALTIME_DISABLED_REASON


def test_fetcher_config_on_missing_streaming_config_fails_closed():
    fetcher = _fetcher(
        streaming_realtime_enabled=True,
        consumer_id="",
        consumer_secret="",
    )

    payload = fetcher.get_realtime_snapshot(["FPT"])

    assert payload["status"] == "unavailable"
    assert payload["reason"] == SSI_STREAMING_REALTIME_CONFIG_INCOMPLETE_REASON
    assert payload["diagnostics"]["live_adapter_status"] == "configuration_incomplete"


def test_fetcher_config_on_missing_official_package_fails_closed(monkeypatch):
    monkeypatch.setattr("data_provider.ssi_fastconnect_fetcher.importlib.util.find_spec", lambda name: None)
    fetcher = _fetcher(streaming_realtime_enabled=True)

    payload = fetcher.get_realtime_snapshot(["FPT"])

    assert payload["status"] == "unavailable"
    assert payload["reason"] == SSI_STREAMING_REALTIME_PACKAGE_UNAVAILABLE_REASON
    assert payload["diagnostics"]["live_adapter_status"] == "package_unavailable"


def test_official_adapter_starts_symbol_channel_without_leaking_headers(capsys):
    FakeOfficialClient.instances.clear()
    FakeOfficialStream.instances.clear()
    adapter = OfficialSsiRealtimeStreamClient(
        consumer_id="test-consumer",
        consumer_secret="test-secret",
        base_url="https://fc-data.ssi.com.vn/api/v2/Market",
        stream_url="https://fc-datahub.ssi.com.vn/",
        import_module=_fake_official_import,
    )

    adapter.start(lambda message: None, lambda error: None, ["X:FPT"])
    captured = capsys.readouterr()

    assert SECRET_TOKEN not in captured.out
    assert SECRET_TOKEN not in captured.err
    assert FakeOfficialClient.instances[0].config.url == "https://fc-data.ssi.com.vn/"
    assert FakeOfficialClient.instances[0].config.stream_url == "https://fc-datahub.ssi.com.vn/"
    assert FakeOfficialStream.instances[0].started_channels == ["X:FPT"]
    adapter.stop()
    assert FakeOfficialStream.instances[0].transport.stop_calls == 1


def test_official_adapter_missing_package_fails_closed():
    adapter = OfficialSsiRealtimeStreamClient(
        consumer_id="test-consumer",
        consumer_secret="test-secret",
        base_url="https://fc-data.ssi.com.vn/api/v2/Market",
        import_module=lambda name: (_ for _ in ()).throw(ImportError(name)),
    )

    with pytest.raises(RuntimeError, match=SSI_STREAMING_REALTIME_PACKAGE_UNAVAILABLE_REASON):
        adapter.start(lambda message: None, lambda error: None, ["X:FPT"])


def test_manager_start_instantiates_official_wrapper_only_when_enabled():
    calls = {"factory": 0}

    def factory():
        calls["factory"] += 1
        return FakeStreamClient()

    disabled = SsiStreamingRealtimeManager(enabled=False, client_factory=factory)
    enabled = SsiStreamingRealtimeManager(enabled=True, client_factory=factory)

    disabled.start(["FPT"])
    assert calls["factory"] == 0
    enabled.start(["FPT"])
    assert calls["factory"] == 1


def test_realtime_service_reads_cache_hit_without_overwriting_daily_latest_price():
    now = [_vn_epoch(2026, 6, 8, 9, 20)]
    client = FakeStreamClient()
    parser_fetcher = _fetcher(streaming_realtime_enabled=True)
    manager = SsiStreamingRealtimeManager(
        enabled=True,
        cache=RealtimeSnapshotCache(15, time_func=lambda: now[0]),
        trade_tape_cache=TradeTapeEventCache(time_func=lambda: now[0]),
        parser=parser_fetcher.normalize_streaming_realtime_messages,
        client_factory=lambda: client,
        time_func=lambda: now[0],
    )
    manager.start(["FPT"])
    manager.handle_message(_x_trade(price="131.5"))
    fetcher = _fetcher(
        streaming_realtime_enabled=True,
        streaming_realtime_manager=manager,
    )
    service = _service_with_fetcher(FakeMarketFetcher(fetcher))

    endpoint_payload = service.build_realtime_snapshot(["FPT"], force_refresh=True)
    item = service.build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert endpoint_payload["status"] == "ok"
    assert endpoint_payload["quotes"][0]["price"] == 131.5
    assert endpoint_payload["streaming_status"] == "cache_hit"
    assert item["realtime_status"]["status"] == "ok"
    assert item["realtime_snapshot"]["price"] == 131.5
    assert item["latest_price"] == item["daily_close"]
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["trade_tape_status"]["status"] == "ok"
    assert item["trade_tape_status"]["reason_code"] == "streaming_trade_tape_supported"
    assert item["trade_tape"][0]["ticker"] == "FPT"
    assert item["trade_tape"][0]["price"] == 131.5
    assert item["diagnostics"]["trade_tape"]["channel_type"] == "X-TRADE"
    assert item["diagnostics"]["trade_tape"]["trade_tape_channels"] == ["X-TRADE:FPT"]
