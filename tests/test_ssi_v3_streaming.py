"""Deterministic tests for the retained SSI V3 trade/quote stream contract."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Callable, Dict, List
from zoneinfo import ZoneInfo

import pytest

from data_provider.ssi_streaming_realtime import SsiStreamingRealtimeManager, TradeTapeEventCache
from data_provider.ssi_v3_adapter import SsiV3RestSettings
from data_provider.ssi_v3_streaming import (
    OfficialSsiV3RealtimeStreamClient,
    build_v3_streaming_realtime_manager,
    normalize_v3_streaming_messages,
)


def _settings() -> SsiV3RestSettings:
    return SsiV3RestSettings(
        enabled=True,
        api_key="<api-key>",
        api_secret="<api-secret>",
    )


def test_raw_trade_is_normalized_for_snapshot_and_tape_without_fake_sequence() -> None:
    rows = normalize_v3_streaming_messages(
        [
            {
                "channel": "DATA",
                "topic": "trade.FPT",
                "data": {"t": "09:15:01", "s": "fpt", "p": "123.4", "q": "50", "v": "500", "si": "B"},
            }
        ],
        ["FPT"],
    )

    assert [row["stream_data_type"] for row in rows] == ["X-TRADE", "X"]
    assert all(row["price"] == 123.4 for row in rows)
    assert all(row["last_volume"] == 50 for row in rows)
    assert rows[0]["sequence_if_available"] is None


def test_quote_arrays_and_scalar_levels_share_the_provider_neutral_ladder() -> None:
    rows = normalize_v3_streaming_messages(
        [
            {
                "topic": "quote.FPT",
                "data": {"t": "09:16:00", "s": "FPT", "bp1": "123", "bq1": "10", "ap1": "124", "aq1": "20"},
            },
            {
                "topic": "quote.SSI",
                "data": {"t": "09:16:01", "s": "SSI", "bids": [[30, 100]], "asks": [{"price": 30.1, "volume": 200}]},
            },
        ],
        ["FPT", "SSI"],
    )

    assert rows[0]["bids"] == [{"level": 1, "price": 123.0, "volume": 10.0}]
    assert rows[0]["asks"] == [{"level": 1, "price": 124.0, "volume": 20.0}]
    assert rows[1]["bids"] == [{"level": 1, "price": 30.0, "volume": 100.0}]
    assert rows[1]["asks"] == [{"level": 1, "price": 30.1, "volume": 200.0}]


def test_invalid_or_incomplete_stream_numbers_are_not_coerced_to_zero() -> None:
    rows = normalize_v3_streaming_messages(
        [
            {"topic": "trade.FPT", "data": {"t": "09:17:00", "s": "FPT", "p": "bad", "q": "10"}},
            {"topic": "quote.FPT", "data": {"t": "09:17:01", "s": "FPT", "bp1": None, "bq1": 0}},
        ],
        ["FPT"],
    )
    assert len(rows) == 1
    assert rows[0]["stream_data_type"] == "X-TRADE-DIAGNOSTIC"
    assert rows[0]["trade_message_classification"] == "malformed_trade_message"


def test_foreign_room_aliases_preserve_zero_and_keep_update_semantics_unproven() -> None:
    rows = normalize_v3_streaming_messages(
        [{
            "topic": "room.FPT",
            "data": {
                "t": "09:17:00",
                "s": "FPT",
                "tr": "1000",
                "cr": "900",
                "bq": "0",
                "bv": "0",
                "sq": "5",
                "sv": "500",
            },
        }],
        ["FPT"],
    )

    assert rows == [{
        "ticker": "FPT",
        "symbol": "FPT",
        "total_room": 1000,
        "current_room": 900,
        "foreign_buy_volume": 0,
        "foreign_buy_value": 0.0,
        "foreign_sell_volume": 5,
        "foreign_sell_value": 500.0,
        "stream_timestamp": "09:17:00",
        "time": "09:17:00",
        "event_market_session": "continuous_morning",
        "stream_data_type": "R",
        "r_type": "R",
        "update_semantics": "unproven",
        "value_semantics_status": "needs_semantics_proof",
        "source": "SSI FastConnect V3 WebSocket room stream",
    }]


class _FakeAuth:
    def __init__(self) -> None:
        self.authenticate_calls = 0
        self.close_calls = 0
        self.config = object()

    def authenticate(self) -> None:
        self.authenticate_calls += 1

    def close(self) -> None:
        self.close_calls += 1


class _RejectingAuth(_FakeAuth):
    def authenticate(self) -> None:
        self.authenticate_calls += 1
        raise RuntimeError("403 authorization denied")


class _FakeWebSocket:
    def __init__(self) -> None:
        self.handlers: Dict[str, Callable[[Any], None]] = {}
        self.sent: List[Dict[str, Any]] = []
        self.connected = threading.Event()
        self.sent_event = threading.Event()
        self.disconnect_calls = 0
        self.is_connected = False

    def on(self, channel: str, handler: Callable[[Any], None]) -> None:
        self.handlers[channel] = handler

    def connect(self) -> None:
        self.is_connected = True
        self.connected.set()

    def send(self, payload: Dict[str, Any]) -> None:
        self.sent.append(payload)
        self.sent_event.set()

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.is_connected = False


def test_client_start_is_nonblocking_and_uses_one_deduplicated_connection() -> None:
    auth = _FakeAuth()
    websocket = _FakeWebSocket()
    opened: List[str] = []
    errors: List[Any] = []
    client = OfficialSsiV3RealtimeStreamClient(
        _settings(),
        auth_factory=lambda _settings: auth,
        websocket_factory=lambda _auth: websocket,
    )

    started = time.perf_counter()
    client.start(
        lambda _message: None,
        errors.append,
        ["X:FPT", "X-TRADE:FPT", "X-QUOTE:FPT"],
        on_open=opened.append,
    )
    assert time.perf_counter() - started < 0.2
    assert websocket.sent_event.wait(1.0)

    assert auth.authenticate_calls == 1
    assert websocket.sent == [
        {
            "method": "subscribe",
            "channel": "DATA",
            "topics": ["trade.FPT", "quote.FPT"],
        }
    ]
    assert opened == ["X:FPT", "X-TRADE:FPT", "X-QUOTE:FPT"]
    assert errors == []

    client.stop()
    client.stop()
    assert websocket.disconnect_calls >= 1
    assert auth.close_calls == 1


def test_preopen_authorization_failure_reports_one_cohort_failure() -> None:
    auth = _RejectingAuth()
    errors: List[Any] = []
    subscription_errors: List[tuple[str, Any]] = []
    completed = threading.Event()
    client = OfficialSsiV3RealtimeStreamClient(
        _settings(),
        auth_factory=lambda _settings: auth,
        websocket_factory=lambda _auth: pytest.fail("websocket must not open after auth rejection"),
    )

    client.start(
        lambda _message: None,
        lambda error: (errors.append(error), completed.set()),
        ["X:FPT", "X-TRADE:FPT", "X-QUOTE:FPT", "R:FPT"],
        on_subscription_error=lambda channel, error: subscription_errors.append((channel, error)),
    )

    assert completed.wait(1.0)
    assert auth.authenticate_calls == 1
    assert len(subscription_errors) == 1
    assert subscription_errors[0][0] == "X:FPT"
    assert len(errors) == 1

    client.stop()
    assert auth.close_calls == 1


def test_trade_tape_cache_preserves_unsequenced_executions_and_deduplicates_provider_sequence() -> None:
    cache = TradeTapeEventCache(max_rows_per_symbol=5, time_func=lambda: 100.0)
    event = {
        "ticker": "FPT",
        "price": 123.4,
        "volume": 50,
        "timestamp": "09:15:01",
        "side_if_available": "B",
        "sequence_if_available": None,
    }
    assert cache.put_rows([event]) == 1
    assert cache.put_rows([event]) == 1
    assert cache.get("FPT")["buffer_row_count"] == 2

    sequenced = {**event, "timestamp": "09:15:02", "sequence_if_available": "42"}
    corrected_duplicate = {**sequenced, "price": 125.0}
    assert cache.put_rows([sequenced]) == 1
    assert cache.put_rows([corrected_duplicate]) == 0
    assert cache.get("FPT")["buffer_row_count"] == 3


def test_zero_auction_trade_is_diagnostic_only() -> None:
    rows = normalize_v3_streaming_messages(
        [{"topic": "trade.FPT", "data": {"t": "09:05:00", "s": "FPT", "p": 0, "q": 0}}],
        ["FPT"],
    )

    assert len(rows) == 1
    assert rows[0]["trade_message_classification"] == "auction_no_match_state"
    assert rows[0]["zero_price"] is True
    assert rows[0]["zero_volume"] is True
    assert rows[0]["event_market_session"] == "ato"


@pytest.mark.parametrize(
    ("payload", "classification"),
    [
        ({"t": "09:16:00", "s": "FPT", "q": 10}, "malformed_trade_message"),
        ({"t": "09:16:00", "s": "FPT", "p": 10}, "malformed_trade_message"),
        ({"t": "09:16:00", "s": "FPT", "p": -1, "q": 10}, "malformed_trade_message"),
        ({"t": "09:16:00", "s": "FPT", "p": "NaN", "q": 10}, "malformed_trade_message"),
        ({"s": "FPT", "p": 10, "q": 10}, "missing_timestamp"),
    ],
)
def test_incomplete_or_invalid_trade_facts_are_diagnostic_only(payload, classification) -> None:
    rows = normalize_v3_streaming_messages(
        [{"topic": "trade.FPT", "data": payload}],
        ["FPT"],
    )

    assert len(rows) == 1
    assert rows[0]["trade_message_classification"] == classification


def test_ato_zero_messages_keep_symbol_waiting_until_first_valid_execution() -> None:
    vn_tz = timezone(timedelta(hours=7))
    now = datetime(2026, 7, 20, 9, 5, tzinfo=vn_tz).timestamp()

    class _Client:
        def start(self, on_message: Any, _on_error: Any, _channels: List[str], **_kwargs: Any) -> None:
            self.on_message = on_message

        def stop(self) -> None:
            return None

    manager = SsiStreamingRealtimeManager(
        enabled=True,
        parser=normalize_v3_streaming_messages,
        client_factory=_Client,
        foreign_room_enabled=False,
        market_index_enabled=False,
        session_status_enabled=False,
        time_func=lambda: now,
    )
    manager.start(["FPT"])
    manager.handle_message(
        {"topic": "trade.FPT", "data": {"t": "09:05:01", "s": "FPT", "p": 0, "q": 0}}
    )

    snapshot = manager.snapshot(["FPT"])
    tape = manager.trade_tape("FPT")
    status = manager.status()
    assert snapshot["status"] == "unavailable"
    assert snapshot["symbol_data_health"] == "auction_waiting_for_match"
    assert snapshot["quotes"] == []
    assert tape["status"] == "unavailable"
    assert tape["symbol_data_health"] == "auction_waiting_for_match"
    assert tape["trades"] == []
    assert status["raw_trade_messages_observed"] == 1
    assert status["valid_trade_rows_observed"] == 0
    assert status["zero_price_trade_rows_dropped"] == 1
    assert status["zero_volume_trade_rows_dropped"] == 1

    manager.handle_message(
        {"topic": "trade.FPT", "data": {"t": "09:14:59", "s": "FPT", "p": 123.4, "q": 50}}
    )
    assert manager.snapshot(["FPT"])["symbol_data_health"] == "live"
    assert manager.trade_tape("FPT")["trades"][0]["event_market_session"] == "ato"


def test_atc_rejects_zero_control_rows_and_preserves_equal_unsequenced_executions() -> None:
    cache = TradeTapeEventCache(max_rows_per_symbol=5, time_func=lambda: 100.0)
    rows = normalize_v3_streaming_messages(
        [
            {"topic": "trade.FPT", "data": {"t": "14:35:00", "s": "FPT", "p": 0, "q": 0}},
            {"topic": "trade.FPT", "data": {"t": "14:44:59", "s": "FPT", "p": 123.4, "q": 50}},
            {"topic": "trade.FPT", "data": {"t": "14:44:59", "s": "FPT", "p": 123.4, "q": 50}},
        ],
        ["FPT"],
    )
    valid_rows = [
        {
            "ticker": row["ticker"],
            "price": row["price"],
            "volume": row["last_volume"],
            "timestamp": row["stream_timestamp"],
            "event_market_session": row["event_market_session"],
        }
        for row in rows
        if row.get("stream_data_type") == "X-TRADE"
    ]

    assert rows[0]["trade_message_classification"] == "auction_no_match_state"
    assert len(valid_rows) == 2
    assert all(row["event_market_session"] == "atc" for row in valid_rows)
    assert cache.put_rows(valid_rows) == 2
    assert cache.get("FPT")["buffer_row_count"] == 2


def test_trade_tape_cache_reports_max_provider_timestamp_not_receive_order() -> None:
    clock = [100.0]
    cache = TradeTapeEventCache(
        max_rows_per_symbol=5,
        time_func=lambda: clock[0],
    )
    assert cache.put_rows(
        [
            {
                "ticker": "FPT",
                "price": 123.4,
                "volume": 50,
                "timestamp": "2026-07-23T09:16:00+07:00",
            }
        ]
    ) == 1
    clock[0] = 101.0
    assert cache.put_rows(
        [
            {
                "ticker": "FPT",
                "price": 123.5,
                "volume": 25,
                "timestamp": "2026-07-23T09:15:00+07:00",
            }
        ]
    ) == 1
    clock[0] = 102.0

    result = cache.get("FPT")

    assert result["latest_trade_timestamp"] == "2026-07-23T09:16:00+07:00"


def test_v3_manager_subscribes_only_retained_trade_and_quote_contexts() -> None:
    clients: List[Any] = []

    class _RecordingClient:
        def __init__(self) -> None:
            self.channels: List[str] = []

        def start(self, _message: Any, _error: Any, channels: List[str], **kwargs: Any) -> None:
            self.channels = list(channels)
            for channel in channels:
                kwargs["on_open"](channel)

        def stop(self) -> None:
            return None

    def factory() -> Any:
        client = _RecordingClient()
        clients.append(client)
        return client

    config = SimpleNamespace(
        ssi_v3_rest_enabled=True,
        ssi_v3_api_key="<api-key>",
        ssi_v3_api_secret="<api-secret>",
        ssi_streaming_realtime_enabled=True,
        ssi_fastconnect_trade_tape_enabled=True,
    )
    manager = build_v3_streaming_realtime_manager(config, client_factory=factory)
    status = manager.start(["FPT"])

    assert status["manager_state"] == "running"
    assert clients[0].channels == ["X:FPT", "X-QUOTE:FPT", "R:FPT", "X-TRADE:FPT"]
    assert manager.foreign_room_enabled is True
    assert manager.market_index_enabled is False
    assert manager.session_status_enabled is False
