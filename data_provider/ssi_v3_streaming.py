"""SSI FastConnect V3 streaming transport and provider-neutral normalization.

The module is import-safe: official SDK imports, authentication, threads, and
network connections are deferred until ``OfficialSsiV3RealtimeStreamClient``
is started by the FastAPI lifecycle.
"""

from __future__ import annotations

import threading
import time
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

from data_provider.ssi_streaming_realtime import (
    DEFAULT_ORDER_BOOK_TTL_SECONDS,
    DEFAULT_STREAMING_REALTIME_CACHE_TTL_SECONDS,
    DEFAULT_STREAMING_REALTIME_IDLE_TIMEOUT_SECONDS,
    DEFAULT_STREAMING_REALTIME_RECONNECT_INITIAL_DELAY_SECONDS,
    DEFAULT_STREAMING_REALTIME_RECONNECT_MAX_DELAY_SECONDS,
    DEFAULT_TRADE_TAPE_BUFFER_SIZE,
    DEFAULT_TRADE_TAPE_TTL_SECONDS,
    OrderBookCache,
    RealtimeSnapshotCache,
    SsiRealtimeStreamClient,
    SsiStreamingRealtimeManager,
    TradeTapeEventCache,
    vietnam_market_session_from_provider_timestamp,
)
from data_provider.ssi_v3_adapter import SsiV3RestSettings, _default_auth_factory


V3_DATA_CHANNEL = "DATA"
V3_HEARTBEAT_CHANNEL = "HEARTBEAT"
V3_HEARTBEAT_INTERVAL_SECONDS = 30.0


def _optional_number(value: Any, *, integer: bool = False) -> Optional[Any]:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not parsed.is_finite():
        return None
    if integer:
        if parsed != parsed.to_integral_value():
            return None
        return int(parsed)
    return float(parsed)


def _raw_numeric_state(data: Mapping[str, Any], key: str) -> str:
    """Classify raw provider presence before SDK/model defaults can mask it."""

    if key not in data:
        return "missing"
    value = data.get(key)
    if value is None:
        return "null"
    if isinstance(value, str) and not value.strip():
        return "blank"
    number = _optional_number(value)
    if number is None or number < 0:
        return "malformed"
    return "explicit_zero" if number == 0 else "nonzero"


def _symbol(value: Any) -> Optional[str]:
    text = str(value or "").strip().upper()
    return text or None


def _levels(data: Mapping[str, Any], side: str) -> List[Dict[str, Any]]:
    plural = "bids" if side == "bid" else "asks"
    raw_levels = data.get(plural)
    rows: List[Dict[str, Any]] = []
    if isinstance(raw_levels, list):
        for position, raw in enumerate(raw_levels[:10], start=1):
            if isinstance(raw, Mapping):
                price = _optional_number(raw.get("price", raw.get("p")))
                volume = _optional_number(raw.get("volume", raw.get("q")))
                level = _optional_number(raw.get("level"), integer=True) or position
            elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
                price = _optional_number(raw[0])
                volume = _optional_number(raw[1])
                level = position
            else:
                continue
            if price is None or volume is None:
                continue
            rows.append({"level": level, "price": price, "volume": volume})
        return rows

    prefix = "b" if side == "bid" else "a"
    for level in range(1, 11):
        price = _optional_number(data.get(f"{prefix}p{level}"))
        volume = _optional_number(data.get(f"{prefix}q{level}"))
        if price is None or volume is None:
            continue
        rows.append({"level": level, "price": price, "volume": volume})
    return rows


def normalize_v3_streaming_messages(
    messages: List[Any],
    requested_symbols: List[str],
) -> List[Dict[str, Any]]:
    """Normalize retained raw V3 ``trade.*`` and ``quote.*`` messages."""

    allowed = {_symbol(value) for value in requested_symbols}
    rows: List[Dict[str, Any]] = []
    for message in messages or []:
        if not isinstance(message, Mapping):
            continue
        topic = str(message.get("topic") or "").strip().lower()
        raw_data = message.get("data")
        payloads = raw_data if isinstance(raw_data, list) else [raw_data]
        for data in payloads:
            if not isinstance(data, Mapping):
                continue
            symbol = _symbol(data.get("s") or data.get("symbol"))
            if not symbol or symbol not in allowed:
                continue
            timestamp = str(data.get("t") or data.get("time") or "").strip() or None
            if topic.startswith("trade."):
                price = _optional_number(data.get("p"))
                last_volume = _optional_number(data.get("q"), integer=True)
                event_market_session = vietnam_market_session_from_provider_timestamp(timestamp)
                classification = "valid_trade_execution"
                if not timestamp:
                    classification = "missing_timestamp"
                elif event_market_session is None or price is None or last_volume is None:
                    classification = "malformed_trade_message"
                elif price < 0 or last_volume < 0:
                    classification = "malformed_trade_message"
                elif price == 0 or last_volume == 0:
                    classification = "auction_no_match_state"
                if classification != "valid_trade_execution":
                    rows.append(
                        {
                            "ticker": symbol,
                            "symbol": symbol,
                            "stream_data_type": "X-TRADE-DIAGNOSTIC",
                            "r_type": "X-TRADE-DIAGNOSTIC",
                            "trade_message_observed": True,
                            "trade_message_classification": classification,
                            "zero_price": price == 0,
                            "zero_volume": last_volume == 0,
                            "missing_timestamp": not bool(timestamp),
                            "stream_timestamp": timestamp,
                            "event_market_session": event_market_session,
                            "source": "SSI FastConnect V3 WebSocket",
                        }
                    )
                    continue
                base = {
                    "ticker": symbol,
                    "symbol": symbol,
                    "price": price,
                    "realtime_price": price,
                    "snapshot_price": price,
                    "last_volume": last_volume,
                    "volume": _optional_number(data.get("v"), integer=True),
                    "side_if_available": data.get("si"),
                    "sequence_if_available": data.get("sequence") or data.get("seq"),
                    "stream_timestamp": timestamp,
                    "time": timestamp,
                    "has_last_trade": True,
                    "trade_message_observed": True,
                    "trade_message_classification": classification,
                    "event_market_session": event_market_session,
                    "source": "SSI FastConnect V3 WebSocket",
                }
                rows.append(
                    {**base, "stream_data_type": "X-TRADE", "r_type": "X-TRADE"}
                )
                rows.append({**base, "trade_message_observed": False, "stream_data_type": "X", "r_type": "X"})
            elif topic.startswith("quote."):
                bids = _levels(data, "bid")
                asks = _levels(data, "ask")
                if not bids and not asks:
                    continue
                rows.append(
                    {
                        "ticker": symbol,
                        "symbol": symbol,
                        "bids": bids,
                        "asks": asks,
                        "bid_levels": bids,
                        "ask_levels": asks,
                        "stream_timestamp": timestamp,
                        "time": timestamp,
                        "stream_data_type": "X-QUOTE",
                        "r_type": "X-QUOTE",
                        "source": "SSI FastConnect V3 WebSocket",
                    }
                )
            elif topic.startswith("room."):
                if not timestamp:
                    continue
                event_market_session = vietnam_market_session_from_provider_timestamp(timestamp)
                if event_market_session is None:
                    continue
                raw_presence = {
                    "foreign_buy_volume": _raw_numeric_state(data, "bq"),
                    "foreign_sell_volume": _raw_numeric_state(data, "sq"),
                    "foreign_buy_value": _raw_numeric_state(data, "bv"),
                    "foreign_sell_value": _raw_numeric_state(data, "sv"),
                    "total_room": _raw_numeric_state(data, "tr"),
                    "current_room": _raw_numeric_state(data, "cr"),
                }
                flow_values = {
                    "foreign_buy_volume": _optional_number(data.get("bq"), integer=True),
                    "foreign_sell_volume": _optional_number(data.get("sq"), integer=True),
                    "foreign_buy_value": _optional_number(data.get("bv")),
                    "foreign_sell_value": _optional_number(data.get("sv")),
                }
                for field, state in raw_presence.items():
                    if state not in {"explicit_zero", "nonzero"} and field in flow_values:
                        flow_values[field] = None
                complete_volume_pair = all(
                    flow_values[field] is not None
                    for field in ("foreign_buy_volume", "foreign_sell_volume")
                )
                complete_value_pair = all(
                    flow_values[field] is not None
                    for field in ("foreign_buy_value", "foreign_sell_value")
                )
                rows.append(
                    {
                        "ticker": symbol,
                        "symbol": symbol,
                        "total_room": _optional_number(data.get("tr"), integer=True),
                        "current_room": _optional_number(data.get("cr"), integer=True),
                        **flow_values,
                        "foreign_net_volume": (
                            flow_values["foreign_buy_volume"]
                            - flow_values["foreign_sell_volume"]
                            if complete_volume_pair
                            else None
                        ),
                        "foreign_net_value": (
                            flow_values["foreign_buy_value"]
                            - flow_values["foreign_sell_value"]
                            if complete_value_pair
                            else None
                        ),
                        "raw_field_presence": raw_presence,
                        "flow_message_usable": complete_volume_pair or complete_value_pair,
                        "stream_timestamp": timestamp,
                        "time": timestamp,
                        "event_market_session": event_market_session,
                        "stream_data_type": "R",
                        "r_type": "R",
                        "update_semantics": "cumulative_replacement_snapshot",
                        "value_semantics_status": "provisional_current_session",
                        "finality": "current_session_provisional",
                        "source": "SSI FastConnect V3 ForeignRoomMessage",
                    }
                )
    return rows


def _topic_for_channel(channel: str) -> Optional[str]:
    prefix, separator, value = str(channel or "").strip().partition(":")
    if not separator or not value:
        return None
    normalized_prefix = prefix.upper()
    symbol = value.strip().upper()
    if normalized_prefix in {"X", "X-TRADE"}:
        return f"trade.{symbol}"
    if normalized_prefix == "X-QUOTE":
        return f"quote.{symbol}"
    if normalized_prefix == "R":
        return f"room.{symbol}"
    return None


class OfficialSsiV3RealtimeStreamClient:
    """Non-blocking one-connection wrapper over the official V3 transport."""

    def __init__(
        self,
        settings: SsiV3RestSettings,
        *,
        auth_factory: Callable[[SsiV3RestSettings], Any] = _default_auth_factory,
        websocket_factory: Optional[Callable[[Any], Any]] = None,
        heartbeat_interval_seconds: float = V3_HEARTBEAT_INTERVAL_SECONDS,
    ) -> None:
        self._settings = settings
        self._auth_factory = auth_factory
        self._websocket_factory = websocket_factory or self._default_websocket_factory
        self._heartbeat_interval_seconds = max(1.0, float(heartbeat_interval_seconds))
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._auth: Any = None
        self._websocket: Any = None
        self._closed_notified = False
        self._subscribed_channels: set[str] = set()

    @staticmethod
    def _default_websocket_factory(auth: Any) -> Any:
        from ssi_sdk.transport.websocket_client import WebSocketClient

        websocket = WebSocketClient(auth.config)
        token = getattr(getattr(auth, "token_manager", None), "access_token", None)
        if token:
            websocket.set_token(token)
        return websocket

    def start(
        self,
        on_message: Callable[[Any], None],
        on_error: Callable[[Any], None],
        channels: Sequence[str],
        *,
        on_open: Optional[Callable[[str], None]] = None,
        on_close: Optional[Callable[[str], None]] = None,
        on_subscription_error: Optional[Callable[[str, Any], None]] = None,
    ) -> None:
        safe_channels = list(dict.fromkeys(str(value or "").strip() for value in channels))
        safe_channels = [value for value in safe_channels if value]
        topics = list(dict.fromkeys(filter(None, (_topic_for_channel(value) for value in safe_channels))))
        unsupported = [value for value in safe_channels if _topic_for_channel(value) is None]
        if unsupported:
            raise ValueError("V3 stream received a channel outside the retained product contract")
        if not topics:
            raise ValueError("At least one V3 streaming topic is required")
        if not self._settings.enabled:
            raise ValueError("SSI V3 streaming is disabled")
        if self._settings.missing_required_names:
            raise ValueError("SSI V3 streaming configuration incomplete")
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._closed_notified = False
            self._thread = threading.Thread(
                target=self._run,
                args=(
                    on_message,
                    on_error,
                    safe_channels,
                    topics,
                    on_open,
                    on_close,
                    on_subscription_error,
                ),
                name="ssi-v3-streaming-connect",
                daemon=True,
            )
            self._thread.start()

    def _run(
        self,
        on_message: Callable[[Any], None],
        on_error: Callable[[Any], None],
        channels: List[str],
        topics: List[str],
        on_open: Optional[Callable[[str], None]],
        on_close: Optional[Callable[[str], None]],
        on_subscription_error: Optional[Callable[[str, Any], None]],
    ) -> None:
        opened = False
        try:
            auth = self._auth_factory(self._settings)
            with self._lock:
                self._auth = auth
            auth.authenticate()
            if self._stop_event.is_set():
                return
            websocket = self._websocket_factory(auth)
            with self._lock:
                self._websocket = websocket
            websocket.on(V3_DATA_CHANNEL, on_message)
            websocket.connect()
            if self._stop_event.is_set():
                return
            websocket.send(
                {"method": "subscribe", "channel": V3_DATA_CHANNEL, "topics": topics}
            )
            with self._lock:
                self._subscribed_channels.update(channels)
            opened = True
            if on_open is not None:
                for channel in channels:
                    on_open(channel)
            while not self._stop_event.wait(self._heartbeat_interval_seconds):
                if not bool(getattr(websocket, "is_connected", False)):
                    break
                websocket.send(
                    {"method": "ping_pong", "channel": V3_HEARTBEAT_CHANNEL, "topics": []}
                )
        except Exception as exc:  # noqa: BLE001 - converted by manager taxonomy.
            if not self._stop_event.is_set():
                if not opened and on_subscription_error is not None:
                    # V3 uses one transport and one cohort subscription. A
                    # pre-open failure (including authorization) therefore
                    # represents one failed restore attempt, not one failure
                    # per requested channel. The manager's transport error
                    # callback marks every enabled context unavailable.
                    on_subscription_error(channels[0], exc)
                on_error(exc)
        finally:
            if opened and not self._stop_event.is_set() and on_close is not None:
                self._notify_close(on_close, channels[0])
            self._close_resources()

    def _notify_close(self, callback: Callable[[str], None], channel: str) -> None:
        with self._lock:
            if self._closed_notified:
                return
            self._closed_notified = True
        callback(channel)

    def _close_resources(self) -> None:
        with self._lock:
            websocket, auth = self._websocket, self._auth
            self._websocket = None
            self._auth = None
            self._subscribed_channels.clear()
        if websocket is not None:
            try:
                websocket.disconnect()
            except Exception:
                pass
        if auth is not None:
            close = getattr(auth, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    def stop(self) -> None:
        self._stop_event.set()
        self._close_resources()
        with self._lock:
            thread = self._thread
            self._thread = None
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def ensure_channels(self, channels: Sequence[str]) -> None:
        """Subscribe new topics on the already-connected shared V3 transport."""

        safe_channels = list(
            dict.fromkeys(str(value or "").strip() for value in channels)
        )
        safe_channels = [value for value in safe_channels if value]
        unsupported = [
            value for value in safe_channels if _topic_for_channel(value) is None
        ]
        if unsupported:
            raise ValueError(
                "V3 stream received a channel outside the retained product contract"
            )
        with self._lock:
            pending_channels = [
                value
                for value in safe_channels
                if value not in self._subscribed_channels
            ]
            if not pending_channels:
                return
            websocket = self._websocket
            if websocket is None or not bool(
                getattr(websocket, "is_connected", False)
            ):
                raise RuntimeError("SSI V3 shared WebSocket is not connected")
            pending_topics = [
                topic
                for topic in (
                    _topic_for_channel(value) for value in pending_channels
                )
                if topic
            ]
            websocket.send(
                {
                    "method": "subscribe",
                    "channel": V3_DATA_CHANNEL,
                    "topics": pending_topics,
                }
            )
            self._subscribed_channels.update(pending_channels)


def build_v3_streaming_realtime_manager(
    config: Any,
    *,
    client_factory: Optional[Callable[[], SsiRealtimeStreamClient]] = None,
) -> SsiStreamingRealtimeManager:
    settings = SsiV3RestSettings.from_config(config)
    factory = client_factory or (lambda: OfficialSsiV3RealtimeStreamClient(settings))
    return SsiStreamingRealtimeManager(
        enabled=bool(getattr(config, "ssi_streaming_realtime_enabled", False)),
        cache=RealtimeSnapshotCache(
            int(
                getattr(
                    config,
                    "ssi_streaming_realtime_cache_ttl_seconds",
                    DEFAULT_STREAMING_REALTIME_CACHE_TTL_SECONDS,
                )
            )
        ),
        order_book_cache=OrderBookCache(DEFAULT_ORDER_BOOK_TTL_SECONDS),
        trade_tape_cache=TradeTapeEventCache(
            int(getattr(config, "ssi_trade_tape_buffer_size", DEFAULT_TRADE_TAPE_BUFFER_SIZE)),
            int(getattr(config, "ssi_trade_tape_ttl_seconds", DEFAULT_TRADE_TAPE_TTL_SECONDS)),
        ),
        parser=normalize_v3_streaming_messages,
        client_factory=factory,
        idle_timeout_seconds=int(
            getattr(
                config,
                "ssi_streaming_realtime_idle_timeout_seconds",
                DEFAULT_STREAMING_REALTIME_IDLE_TIMEOUT_SECONDS,
            )
        ),
        reconnect_enabled=bool(
            getattr(config, "ssi_streaming_realtime_reconnect_enabled", True)
        ),
        reconnect_initial_delay_seconds=int(
            getattr(
                config,
                "ssi_streaming_realtime_reconnect_initial_delay_seconds",
                DEFAULT_STREAMING_REALTIME_RECONNECT_INITIAL_DELAY_SECONDS,
            )
        ),
        reconnect_max_delay_seconds=int(
            getattr(
                config,
                "ssi_streaming_realtime_reconnect_max_delay_seconds",
                DEFAULT_STREAMING_REALTIME_RECONNECT_MAX_DELAY_SECONDS,
            )
        ),
        reconnect_max_attempts=int(
            getattr(config, "ssi_streaming_realtime_reconnect_max_attempts", 0)
        ),
        order_book_enabled=True,
        trade_tape_enabled=bool(
            getattr(config, "ssi_fastconnect_trade_tape_enabled", True)
        ),
        foreign_room_enabled=True,
        market_index_enabled=False,
        market_index_codes=[],
        session_status_enabled=False,
    )


class SsiStreamingRealtimeReader:
    """Small cache-only facade used by V3 services without constructing V2."""

    def __init__(self, manager: SsiStreamingRealtimeManager) -> None:
        self.streaming_realtime_manager = manager

    def get_realtime_snapshot(self, symbols: Iterable[str]) -> Dict[str, Any]:
        return dict(self.streaming_realtime_manager.snapshot(symbols))

    def get_trade_tape(self, symbol: str, limit: int = 50) -> Dict[str, Any]:
        return dict(self.streaming_realtime_manager.trade_tape(symbol, limit))

    def get_order_book(self, symbol: str) -> Dict[str, Any]:
        return dict(self.streaming_realtime_manager.order_book(symbol))

    def get_foreign_room(self, symbol: str) -> Dict[str, Any]:
        return dict(self.streaming_realtime_manager.foreign_room(symbol))

    def get_current_foreign_flow(self, symbol: str) -> Dict[str, Any]:
        return dict(self.streaming_realtime_manager.current_foreign_flow(symbol))

    def ensure_current_foreign_flow(
        self,
        symbol: str,
        *,
        recovery_trigger: str = "route_touch",
    ) -> Dict[str, Any]:
        return dict(
            self.streaming_realtime_manager.ensure_symbol_subscription(
                symbol,
                recovery_trigger=recovery_trigger,
            )
        )

    def ensure_current_foreign_flow_cohort(
        self,
        symbols: Iterable[str],
        *,
        recovery_trigger: str = "route_touch",
    ) -> Dict[str, Any]:
        return dict(
            self.streaming_realtime_manager.ensure_symbol_subscriptions(
                symbols,
                recovery_trigger=recovery_trigger,
            )
        )

    def get_session_status(self, symbol: str) -> Dict[str, Any]:
        return dict(self.streaming_realtime_manager.session_status(symbol))

    def get_market_index_pulse(self, indexes: Iterable[str]) -> Dict[str, Any]:
        return dict(self.streaming_realtime_manager.market_index_pulse(indexes))
