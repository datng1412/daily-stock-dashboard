"""Deterministic tests for the retained SSI V3 trade/quote stream contract."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from typing import Any, Callable, Dict, List

from data_provider.ssi_streaming_realtime import TradeTapeEventCache
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
    assert rows == []


class _FakeAuth:
    def __init__(self) -> None:
        self.authenticate_calls = 0
        self.close_calls = 0
        self.config = object()

    def authenticate(self) -> None:
        self.authenticate_calls += 1

    def close(self) -> None:
        self.close_calls += 1


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


def test_trade_tape_cache_deduplicates_content_when_sequence_is_absent() -> None:
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
    assert cache.put_rows([event]) == 0
    assert cache.get("FPT")["buffer_row_count"] == 1

    sequenced = {**event, "timestamp": "09:15:02", "sequence_if_available": "42"}
    corrected_duplicate = {**sequenced, "price": 125.0}
    assert cache.put_rows([sequenced]) == 1
    assert cache.put_rows([corrected_duplicate]) == 0
    assert cache.get("FPT")["buffer_row_count"] == 2


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
    assert clients[0].channels == ["X:FPT", "X-QUOTE:FPT", "X-TRADE:FPT"]
    assert manager.foreign_room_enabled is False
    assert manager.market_index_enabled is False
    assert manager.session_status_enabled is False
