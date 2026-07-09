# -*- coding: utf-8 -*-
"""Safe SSI streaming realtime manager skeleton.

This module is intentionally side-effect free: importing it does not import the
official SSI streaming package, create clients, start threads, or open network
connections.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple


SSI_STREAMING_REALTIME_DISABLED_REASON = "SSI streaming realtime manager disabled."
SSI_STREAMING_REALTIME_NOT_STARTED_REASON = "SSI streaming realtime manager not started."
SSI_STREAMING_REALTIME_CACHE_EMPTY_REASON = "SSI streaming realtime cache empty."
SSI_STREAMING_REALTIME_CACHE_STALE_REASON = "SSI streaming realtime cache stale."
SSI_STREAMING_REALTIME_MANAGER_ERROR_REASON = "SSI streaming realtime manager errored."
SSI_STREAMING_REALTIME_LIVE_ADAPTER_DISABLED_REASON = "SSI streaming realtime live adapter not enabled."
SSI_STREAMING_REALTIME_ALL_CHANNEL_FORBIDDEN_REASON = "SSI streaming realtime refuses ALL channel subscriptions."
SSI_STREAMING_REALTIME_CONFIG_INCOMPLETE_REASON = "SSI streaming realtime configuration incomplete."
SSI_STREAMING_REALTIME_PACKAGE_UNAVAILABLE_REASON = "SSI streaming realtime package unavailable."
SSI_STREAMING_REALTIME_BOOTSTRAP_EMPTY_REASON = "SSI streaming realtime bootstrap symbols empty."

MANAGER_DISABLED = "disabled"
MANAGER_STOPPED = "stopped"
MANAGER_STARTING = "starting"
MANAGER_RUNNING = "running"
MANAGER_ERRORED = "errored"

DEFAULT_STREAMING_REALTIME_CACHE_TTL_SECONDS = 15
DEFAULT_STREAMING_REALTIME_CHANNEL_TEMPLATE = "X:{symbol}"
DEFAULT_STREAMING_REALTIME_STREAM_URL = "https://fc-datahub.ssi.com.vn/"
DEFAULT_STREAMING_REALTIME_IDLE_TIMEOUT_SECONDS = 45
DEFAULT_STREAMING_REALTIME_RECONNECT_INITIAL_DELAY_SECONDS = 2
DEFAULT_STREAMING_REALTIME_RECONNECT_MAX_DELAY_SECONDS = 30
DEFAULT_ORDER_BOOK_TTL_SECONDS = 5
DEFAULT_ORDER_BOOK_MAX_LEVELS = 10
DEFAULT_FOREIGN_ROOM_TTL_SECONDS = 5
DEFAULT_TRADE_TAPE_BUFFER_SIZE = 50
DEFAULT_TRADE_TAPE_TTL_SECONDS = 60
ORDER_BOOK_CHANNEL_PREFIX = "X-QUOTE"
FOREIGN_ROOM_CHANNEL_PREFIX = "R"
TRADE_TAPE_CHANNEL_PREFIX = "X-TRADE"
DEFAULT_SESSION_STATUS_TTL_SECONDS = 60
SESSION_STATUS_CHANNEL_PREFIX = "F"
_TRADE_SIDE_BUY_VALUES = {"B", "BU", "BUY", "1", "MUA"}
_TRADE_SIDE_SELL_VALUES = {"S", "SD", "SELL", "2", "BAN", "BÁN"}

RUNTIME_DISABLED = "disabled"
RUNTIME_NOT_STARTED = "not_started"
RUNTIME_STARTING = "starting"
RUNTIME_RUNNING = "running"
RUNTIME_RUNNING_IDLE = "running_idle"
RUNTIME_RECONNECTING = "reconnecting"
RUNTIME_ERRORED = "errored"
RUNTIME_STOPPED = "stopped"
RUNTIME_SHUTDOWN = "shutdown"

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)(access[_-]?token\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(consumer[_-]?id\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(consumer[_-]?secret\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(private[_-]?key\s*[:=]\s*)[^\s,;]+"),
)


def normalize_trade_side(value: Any) -> Optional[str]:
    """Normalize explicit SSI X-TRADE side/aggressor values.

    Unknown values intentionally return ``None``. Trade side must not be
    inferred from price/reference color.
    """

    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.upper()
    if normalized in _TRADE_SIDE_BUY_VALUES:
        return "buy"
    if normalized in _TRADE_SIDE_SELL_VALUES:
        return "sell"
    return None


class SsiRealtimeStreamClient(Protocol):
    """Small stream-client interface used by the background manager."""

    def start(self, on_message: Callable[[Any], None], on_error: Callable[[Any], None], channels: Sequence[str]) -> None:
        """Start streaming for symbol-scoped channels."""

    def stop(self) -> None:
        """Stop streaming idempotently."""


class DisabledOfficialSsiRealtimeStreamClient:
    """Deferred official-client wrapper.

    The installed official `ssi-fc-data` client currently needs a safety wrapper
    before live use because its negotiation path can print auth headers and its
    close path does not match the available transport stop method. This sentinel
    keeps the mockable interface explicit without instantiating the official
    client.
    """

    def start(self, on_message: Callable[[Any], None], on_error: Callable[[Any], None], channels: Sequence[str]) -> None:
        raise RuntimeError(SSI_STREAMING_REALTIME_LIVE_ADAPTER_DISABLED_REASON)

    def stop(self) -> None:
        return None


def _trailing_slash(value: str) -> str:
    text = str(value or "").strip()
    return text.rstrip("/") + "/" if text else ""


def _official_rest_root(base_url: str) -> str:
    text = str(base_url or "").strip().rstrip("/")
    suffix = "/api/v2/Market"
    if text.lower().endswith(suffix.lower()):
        text = text[: -len(suffix)]
    return _trailing_slash(text)


class OfficialSsiRealtimeStreamClient:
    """Lazy, secret-safe wrapper around the official SSI FC Data stream client.

    The official package is imported only when `start` is called. Its
    negotiation path prints headers, so stdout is redirected only for the
    official start call and discarded.
    """

    def __init__(
        self,
        *,
        consumer_id: Optional[str],
        consumer_secret: Optional[str],
        base_url: str,
        stream_url: str = DEFAULT_STREAMING_REALTIME_STREAM_URL,
        auth_type: str = "Bearer",
        import_module: Callable[[str], Any] = importlib.import_module,
    ) -> None:
        self.consumer_id = (consumer_id or "").strip()
        self.consumer_secret = (consumer_secret or "").strip()
        self.base_url = _official_rest_root(base_url)
        self.stream_url = _trailing_slash(stream_url or DEFAULT_STREAMING_REALTIME_STREAM_URL)
        self.auth_type = (auth_type or "Bearer").strip() or "Bearer"
        self._import_module = import_module
        self._streams: List[Any] = []
        self._lock = threading.RLock()

    def start(self, on_message: Callable[[Any], None], on_error: Callable[[Any], None], channels: Sequence[str]) -> None:
        if not self.consumer_id or not self.consumer_secret or not self.base_url or not self.stream_url:
            raise RuntimeError(SSI_STREAMING_REALTIME_CONFIG_INCOMPLETE_REASON)
        safe_channels = [str(channel or "").strip() for channel in channels or [] if str(channel or "").strip()]
        if not safe_channels:
            raise RuntimeError("At least one streaming channel is required.")
        if any(re.search(r":\s*ALL\b", channel, flags=re.IGNORECASE) for channel in safe_channels):
            raise RuntimeError(SSI_STREAMING_REALTIME_ALL_CHANNEL_FORBIDDEN_REASON)

        try:
            client_module = self._import_module("ssi_fc_data.fc_md_client")
            stream_module = self._import_module("ssi_fc_data.fc_md_stream")
        except Exception as exc:
            raise RuntimeError(SSI_STREAMING_REALTIME_PACKAGE_UNAVAILABLE_REASON) from exc

        config = SimpleNamespace(
            auth_type=self.auth_type,
            consumerID=self.consumer_id,
            consumerSecret=self.consumer_secret,
            url=self.base_url,
            stream_url=self.stream_url,
        )
        started_streams: List[Any] = []
        try:
            for channel in safe_channels:
                client = client_module.MarketDataClient(config)
                stream = stream_module.MarketDataStream(config, client)
                with contextlib.redirect_stdout(io.StringIO()):
                    stream.start(on_message, on_error, channel)
                started_streams.append(stream)
        except Exception:
            for stream in started_streams:
                self._stop_stream(stream)
            raise
        with self._lock:
            self._streams.extend(started_streams)

    def stop(self) -> None:
        with self._lock:
            streams = list(self._streams)
            self._streams.clear()
        first_error: Optional[Exception] = None
        for stream in streams:
            try:
                self._stop_stream(stream)
            except Exception as exc:  # pragma: no cover - defensive path
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error

    @staticmethod
    def _stop_stream(stream: Any) -> None:
        connection = getattr(stream, "connection", None)
        transport = getattr(connection, "_Connection__transport", None)
        if transport is not None and callable(getattr(transport, "stop", None)):
            transport.stop()
            return
        if connection is not None and callable(getattr(connection, "close", None)):
            try:
                connection.close()
            except AttributeError:
                return


@dataclass(frozen=True)
class CachedRealtimeSnapshot:
    symbol: str
    snapshot: Dict[str, Any]
    received_at: float


@dataclass(frozen=True)
class CachedTradeTapeEvent:
    symbol: str
    trade: Dict[str, Any]
    received_at: float


@dataclass(frozen=True)
class CachedOrderBook:
    symbol: str
    order_book: Dict[str, Any]
    received_at: float


@dataclass(frozen=True)
class CachedForeignRoom:
    symbol: str
    foreign_room: Dict[str, Any]
    received_at: float


@dataclass(frozen=True)
class CachedSessionStatus:
    symbol: str
    status: Dict[str, Any]
    received_at: float


def sanitize_streaming_error(value: Any, *, max_length: int = 240) -> str:
    """Return a bounded, secret-safe error summary."""
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r"\1<redacted>", text)
    if len(text) > max_length:
        text = text[: max_length - 3].rstrip() + "..."
    return text or "unknown streaming error"


def _utc_iso_from_epoch(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def normalize_streaming_symbols(symbols: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for symbol in symbols or []:
        text = str(symbol or "").strip().upper()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def build_symbol_channel(symbol: str, template: str = DEFAULT_STREAMING_REALTIME_CHANNEL_TEMPLATE) -> str:
    normalized = str(symbol or "").strip().upper()
    if not normalized:
        raise ValueError("Streaming symbol is required.")
    if normalized == "ALL":
        raise ValueError(SSI_STREAMING_REALTIME_ALL_CHANNEL_FORBIDDEN_REASON)
    channel_template = (template or DEFAULT_STREAMING_REALTIME_CHANNEL_TEMPLATE).strip()
    if "{symbol}" not in channel_template:
        raise ValueError("SSI streaming realtime channel template must include {symbol}.")
    channel = channel_template.format(symbol=normalized).strip()
    if re.search(r":\s*ALL\b", channel, flags=re.IGNORECASE):
        raise ValueError(SSI_STREAMING_REALTIME_ALL_CHANNEL_FORBIDDEN_REASON)
    return channel


def build_trade_tape_channel(symbol: str) -> str:
    normalized = str(symbol or "").strip().upper()
    if not normalized:
        raise ValueError("Streaming symbol is required.")
    if normalized == "ALL":
        raise ValueError(SSI_STREAMING_REALTIME_ALL_CHANNEL_FORBIDDEN_REASON)
    channel = f"{TRADE_TAPE_CHANNEL_PREFIX}:{normalized}"
    if re.search(r":\s*ALL\b", channel, flags=re.IGNORECASE):
        raise ValueError(SSI_STREAMING_REALTIME_ALL_CHANNEL_FORBIDDEN_REASON)
    return channel


def build_order_book_channel(symbol: str) -> str:
    normalized = str(symbol or "").strip().upper()
    if not normalized:
        raise ValueError("Streaming symbol is required.")
    if normalized == "ALL":
        raise ValueError(SSI_STREAMING_REALTIME_ALL_CHANNEL_FORBIDDEN_REASON)
    channel = f"{ORDER_BOOK_CHANNEL_PREFIX}:{normalized}"
    if re.search(r":\s*ALL\b", channel, flags=re.IGNORECASE):
        raise ValueError(SSI_STREAMING_REALTIME_ALL_CHANNEL_FORBIDDEN_REASON)
    return channel


def build_foreign_room_channel(symbol: str) -> str:
    normalized = str(symbol or "").strip().upper()
    if not normalized:
        raise ValueError("Streaming symbol is required.")
    if normalized == "ALL":
        raise ValueError(SSI_STREAMING_REALTIME_ALL_CHANNEL_FORBIDDEN_REASON)
    channel = f"{FOREIGN_ROOM_CHANNEL_PREFIX}:{normalized}"
    if re.search(r":\s*ALL\b", channel, flags=re.IGNORECASE):
        raise ValueError(SSI_STREAMING_REALTIME_ALL_CHANNEL_FORBIDDEN_REASON)
    return channel


def build_session_status_channel(symbol: str) -> str:
    normalized = str(symbol or "").strip().upper()
    if not normalized:
        raise ValueError("Streaming symbol is required.")
    if normalized == "ALL":
        raise ValueError(SSI_STREAMING_REALTIME_ALL_CHANNEL_FORBIDDEN_REASON)
    channel = f"{SESSION_STATUS_CHANNEL_PREFIX}:{normalized}"
    if re.search(r":\s*ALL\b", channel, flags=re.IGNORECASE):
        raise ValueError(SSI_STREAMING_REALTIME_ALL_CHANNEL_FORBIDDEN_REASON)
    return channel


def is_trade_tape_channel(channel: Any) -> bool:
    text = str(channel or "").strip().upper()
    return text.startswith(f"{TRADE_TAPE_CHANNEL_PREFIX}:")


def is_order_book_channel(channel: Any) -> bool:
    text = str(channel or "").strip().upper()
    return text.startswith(f"{ORDER_BOOK_CHANNEL_PREFIX}:")


def is_foreign_room_channel(channel: Any) -> bool:
    text = str(channel or "").strip().upper()
    return text.startswith(f"{FOREIGN_ROOM_CHANNEL_PREFIX}:")


def is_session_status_channel(channel: Any) -> bool:
    text = str(channel or "").strip().upper()
    return text.startswith(f"{SESSION_STATUS_CHANNEL_PREFIX}:")


def build_streaming_channels(
    symbols: Iterable[str],
    *,
    realtime_template: str = DEFAULT_STREAMING_REALTIME_CHANNEL_TEMPLATE,
    order_book_enabled: bool = True,
    foreign_room_enabled: bool = True,
    trade_tape_enabled: bool = True,
    session_status_enabled: bool = True,
) -> List[str]:
    channels: List[str] = []
    seen = set()
    for symbol in normalize_streaming_symbols(symbols):
        for channel in (
            build_symbol_channel(symbol, realtime_template),
            build_order_book_channel(symbol) if order_book_enabled else None,
            build_foreign_room_channel(symbol) if foreign_room_enabled else None,
            build_trade_tape_channel(symbol) if trade_tape_enabled else None,
            build_session_status_channel(symbol) if session_status_enabled else None,
        ):
            if not channel or channel in seen:
                continue
            channels.append(channel)
            seen.add(channel)
    return channels


class RealtimeSnapshotCache:
    """Thread-safe latest realtime snapshot cache keyed by VN ticker."""

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_STREAMING_REALTIME_CACHE_TTL_SECONDS,
        *,
        time_func: Callable[[], float] = time.time,
    ) -> None:
        self.ttl_seconds = max(1, int(ttl_seconds or DEFAULT_STREAMING_REALTIME_CACHE_TTL_SECONDS))
        self._time_func = time_func
        self._lock = threading.RLock()
        self._rows: Dict[str, CachedRealtimeSnapshot] = {}

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()

    def put_rows(self, rows: Iterable[Dict[str, Any]]) -> int:
        now = float(self._time_func())
        written = 0
        with self._lock:
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                symbol = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                snapshot = dict(row)
                snapshot["ticker"] = symbol
                snapshot.setdefault("symbol", symbol)
                snapshot["cached_at"] = _utc_iso_from_epoch(now)
                snapshot["cache_ttl_seconds"] = self.ttl_seconds
                self._rows[symbol] = CachedRealtimeSnapshot(symbol=symbol, snapshot=snapshot, received_at=now)
                written += 1
        return written

    def get(self, symbol: str) -> Tuple[Optional[Dict[str, Any]], str, Optional[float]]:
        normalized = str(symbol or "").strip().upper()
        now = float(self._time_func())
        with self._lock:
            entry = self._rows.get(normalized)
            if entry is None:
                return None, "empty", None
            age_seconds = max(0.0, now - entry.received_at)
            snapshot = dict(entry.snapshot)
            snapshot["age_seconds"] = int(age_seconds)
            snapshot["is_stale"] = age_seconds > self.ttl_seconds
            if snapshot["is_stale"]:
                snapshot["stale_reason"] = SSI_STREAMING_REALTIME_CACHE_STALE_REASON
                return snapshot, "stale", age_seconds
            return snapshot, "hit", age_seconds

    def get_many(self, symbols: Iterable[str]) -> Dict[str, Any]:
        normalized_symbols = normalize_streaming_symbols(symbols)
        rows: List[Dict[str, Any]] = []
        stale_symbols: List[str] = []
        empty_symbols: List[str] = []
        ages: Dict[str, int] = {}
        for symbol in normalized_symbols:
            row, status, age_seconds = self.get(symbol)
            if age_seconds is not None:
                ages[symbol] = int(age_seconds)
            if status == "hit" and row is not None:
                rows.append(row)
            elif status == "stale":
                stale_symbols.append(symbol)
            else:
                empty_symbols.append(symbol)
        return {
            "rows": rows,
            "hit_count": len(rows),
            "stale_count": len(stale_symbols),
            "empty_count": len(empty_symbols),
            "stale_symbols": stale_symbols,
            "empty_symbols": empty_symbols,
            "ages_seconds": ages,
        }


class TradeTapeEventCache:
    """Thread-safe bounded X-TRADE event buffer keyed by VN ticker."""

    def __init__(
        self,
        max_rows_per_symbol: int = DEFAULT_TRADE_TAPE_BUFFER_SIZE,
        ttl_seconds: int = DEFAULT_TRADE_TAPE_TTL_SECONDS,
        *,
        time_func: Callable[[], float] = time.time,
    ) -> None:
        self.max_rows_per_symbol = max(1, int(max_rows_per_symbol or DEFAULT_TRADE_TAPE_BUFFER_SIZE))
        self.ttl_seconds = max(1, int(ttl_seconds or DEFAULT_TRADE_TAPE_TTL_SECONDS))
        self._time_func = time_func
        self._lock = threading.RLock()
        self._rows: Dict[str, List[CachedTradeTapeEvent]] = {}

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()

    def put_rows(self, rows: Iterable[Dict[str, Any]]) -> int:
        now = float(self._time_func())
        written = 0
        with self._lock:
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                symbol = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
                price = row.get("price")
                volume = row.get("volume")
                timestamp = str(row.get("timestamp") or "").strip()
                if not symbol or price is None or volume is None or not timestamp:
                    continue
                trade = dict(row)
                trade["ticker"] = symbol
                trade.setdefault("symbol", symbol)
                trade["cached_at"] = _utc_iso_from_epoch(now)
                trade["cache_ttl_seconds"] = self.ttl_seconds
                events = self._rows.setdefault(symbol, [])
                events.insert(0, CachedTradeTapeEvent(symbol=symbol, trade=trade, received_at=now))
                del events[self.max_rows_per_symbol :]
                written += 1
        return written

    def get(self, symbol: str, limit: int = DEFAULT_TRADE_TAPE_BUFFER_SIZE) -> Dict[str, Any]:
        normalized = str(symbol or "").strip().upper()
        safe_limit = max(1, min(int(limit or self.max_rows_per_symbol), self.max_rows_per_symbol))
        now = float(self._time_func())
        with self._lock:
            events = list(self._rows.get(normalized) or [])

        if not events:
            return {
                "rows": [],
                "status": "empty",
                "row_count": 0,
                "buffer_row_count": 0,
                "latest_trade_timestamp": None,
                "latest_trade_age_seconds": None,
            }

        rows: List[Dict[str, Any]] = []
        for event in events[:safe_limit]:
            age_seconds = max(0.0, now - event.received_at)
            trade = dict(event.trade)
            trade["age_seconds"] = int(age_seconds)
            trade["is_stale"] = age_seconds > self.ttl_seconds
            rows.append(trade)

        newest_age = max(0.0, now - events[0].received_at)
        latest_trade_timestamp = events[0].trade.get("timestamp")
        return {
            "rows": rows,
            "status": "stale" if newest_age > self.ttl_seconds else "hit",
            "row_count": len(rows),
            "buffer_row_count": len(events),
            "latest_trade_timestamp": latest_trade_timestamp,
            "latest_trade_age_seconds": int(newest_age),
        }


class OrderBookCache:
    """Thread-safe latest X-QUOTE order-book cache keyed by VN ticker."""

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_ORDER_BOOK_TTL_SECONDS,
        max_levels: int = DEFAULT_ORDER_BOOK_MAX_LEVELS,
        *,
        time_func: Callable[[], float] = time.time,
    ) -> None:
        self.ttl_seconds = max(1, int(ttl_seconds or DEFAULT_ORDER_BOOK_TTL_SECONDS))
        self.max_levels = max(1, int(max_levels or DEFAULT_ORDER_BOOK_MAX_LEVELS))
        self._time_func = time_func
        self._lock = threading.RLock()
        self._rows: Dict[str, CachedOrderBook] = {}

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()

    def put_rows(self, rows: Iterable[Dict[str, Any]]) -> int:
        now = float(self._time_func())
        written = 0
        with self._lock:
            for row in rows or []:
                order_book = self._normalize_order_book(row, now)
                if not order_book:
                    continue
                symbol = str(order_book.get("ticker") or order_book.get("symbol") or "").strip().upper()
                self._rows[symbol] = CachedOrderBook(
                    symbol=symbol,
                    order_book=order_book,
                    received_at=now,
                )
                written += 1
        return written

    def get(self, symbol: str) -> Dict[str, Any]:
        normalized = str(symbol or "").strip().upper()
        now = float(self._time_func())
        with self._lock:
            entry = self._rows.get(normalized)

        if entry is None:
            return {
                "status": "empty",
                "row": None,
                "latest_order_book_timestamp": None,
                "latest_order_book_age_seconds": None,
            }

        age_seconds = max(0.0, now - entry.received_at)
        row = dict(entry.order_book)
        row["age_seconds"] = int(age_seconds)
        row["is_stale"] = age_seconds > self.ttl_seconds
        if row["is_stale"]:
            row["stale_reason"] = SSI_STREAMING_REALTIME_CACHE_STALE_REASON
        return {
            "status": "stale" if row["is_stale"] else "hit",
            "row": row,
            "latest_order_book_timestamp": row.get("stream_timestamp") or row.get("time"),
            "latest_order_book_age_seconds": int(age_seconds),
        }

    def _normalize_order_book(self, row: Any, now: float) -> Optional[Dict[str, Any]]:
        if not isinstance(row, dict):
            return None
        symbol = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
        if not symbol:
            return None
        bids = self._normalize_levels(row.get("bids") or row.get("bid_levels") or [])
        asks = self._normalize_levels(row.get("asks") or row.get("ask_levels") or [])
        if not bids and not asks:
            return None
        cached_at = _utc_iso_from_epoch(now)
        return {
            "ticker": symbol,
            "symbol": symbol,
            "exchange": self._safe_text(row.get("exchange")),
            "bids": bids,
            "asks": asks,
            "trading_date": self._safe_text(row.get("trading_date")),
            "time": self._safe_text(row.get("time")),
            "stream_timestamp": self._safe_text(row.get("stream_timestamp")),
            "stream_data_type": ORDER_BOOK_CHANNEL_PREFIX,
            "r_type": self._safe_text(row.get("r_type")) or ORDER_BOOK_CHANNEL_PREFIX,
            "source": "SSI X-QUOTE order-book stream",
            "received_at": cached_at,
            "cached_at": cached_at,
            "cache_ttl_seconds": self.ttl_seconds,
        }

    def _normalize_levels(self, levels: Any) -> List[Dict[str, Any]]:
        if not isinstance(levels, list):
            return []
        normalized: List[Dict[str, Any]] = []
        seen_levels = set()
        for index, level in enumerate(levels[: self.max_levels], start=1):
            if not isinstance(level, dict):
                continue
            level_number = self._to_int(
                self._first_value(level, "level", "Level", "position", "Position")
            )
            if level_number is None:
                level_number = index
            if level_number < 1 or level_number in seen_levels:
                continue
            price = self._to_float(self._first_value(level, "price", "Price"))
            volume = self._to_float(
                self._first_value(level, "volume", "Volume", "vol", "Vol")
            )
            if price is None or price <= 0 or volume is None or volume < 0:
                continue
            seen_levels.add(level_number)
            normalized.append(
                {
                    "level": level_number,
                    "price": price,
                    "volume": volume,
                }
            )
        return sorted(normalized, key=lambda item: item["level"])

    @staticmethod
    def _first_value(row: Dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in row and row.get(key) not in (None, ""):
                return row.get(key)
        return None

    @staticmethod
    def _safe_text(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        text = str(value).replace("\r", " ").replace("\n", " ").strip()
        return text[:120] if text else None

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            return float(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            return None

    @classmethod
    def _to_int(cls, value: Any) -> Optional[int]:
        number = cls._to_float(value)
        if number is None:
            return None
        return int(number)


class ForeignRoomCache:
    """Thread-safe latest R foreign-room cache keyed by VN ticker."""

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_FOREIGN_ROOM_TTL_SECONDS,
        *,
        time_func: Callable[[], float] = time.time,
    ) -> None:
        self.ttl_seconds = max(1, int(ttl_seconds or DEFAULT_FOREIGN_ROOM_TTL_SECONDS))
        self._time_func = time_func
        self._lock = threading.RLock()
        self._rows: Dict[str, CachedForeignRoom] = {}

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()

    def put_rows(self, rows: Iterable[Dict[str, Any]]) -> int:
        now = float(self._time_func())
        written = 0
        with self._lock:
            for row in rows or []:
                foreign_room = self._normalize_foreign_room(row, now)
                if not foreign_room:
                    continue
                symbol = str(foreign_room.get("ticker") or foreign_room.get("symbol") or "").strip().upper()
                self._rows[symbol] = CachedForeignRoom(
                    symbol=symbol,
                    foreign_room=foreign_room,
                    received_at=now,
                )
                written += 1
        return written

    def get(self, symbol: str) -> Dict[str, Any]:
        normalized = str(symbol or "").strip().upper()
        now = float(self._time_func())
        with self._lock:
            entry = self._rows.get(normalized)

        if entry is None:
            return {
                "status": "empty",
                "row": None,
                "latest_foreign_room_timestamp": None,
                "latest_foreign_room_age_seconds": None,
            }

        age_seconds = max(0.0, now - entry.received_at)
        row = dict(entry.foreign_room)
        row["age_seconds"] = int(age_seconds)
        row["is_stale"] = age_seconds > self.ttl_seconds
        if row["is_stale"]:
            row["stale_reason"] = SSI_STREAMING_REALTIME_CACHE_STALE_REASON
        return {
            "status": "stale" if row["is_stale"] else "hit",
            "row": row,
            "latest_foreign_room_timestamp": row.get("stream_timestamp") or row.get("time"),
            "latest_foreign_room_age_seconds": int(age_seconds),
        }

    def _normalize_foreign_room(self, row: Any, now: float) -> Optional[Dict[str, Any]]:
        if not isinstance(row, dict):
            return None
        symbol = str(
            self._first_value(row, "ticker", "symbol", "Symbol", "Ticker", "StockCode", "SecurityCode", "Code")
            or ""
        ).strip().upper()
        if not symbol:
            return None

        numeric_fields = {
            "total_room": self._to_nonnegative_float(
                self._first_value(row, "total_room", "TotalRoom", "totalRoom")
            ),
            "current_room": self._to_nonnegative_float(
                self._first_value(row, "current_room", "CurrentRoom", "currentRoom")
            ),
            "foreign_buy_volume": self._to_nonnegative_float(
                self._first_value(row, "foreign_buy_volume", "FBuyVol", "fBuyVol", "f_buy_vol")
            ),
            "foreign_sell_volume": self._to_nonnegative_float(
                self._first_value(row, "foreign_sell_volume", "FSellVol", "fSellVol", "f_sell_vol")
            ),
            "foreign_buy_value": self._to_nonnegative_float(
                self._first_value(row, "foreign_buy_value", "FBuyVal", "fBuyVal", "f_buy_val")
            ),
            "foreign_sell_value": self._to_nonnegative_float(
                self._first_value(row, "foreign_sell_value", "FSellVal", "fSellVal", "f_sell_val")
            ),
        }
        if not any(value is not None for value in numeric_fields.values()):
            return None

        cached_at = _utc_iso_from_epoch(now)
        foreign_room = {
            "ticker": symbol,
            "symbol": symbol,
            "exchange": self._safe_text(self._first_value(row, "exchange", "Exchange", "Market", "market")),
            "trading_date": self._safe_text(
                self._first_value(row, "trading_date", "TradingDate", "Date", "date")
            ),
            "time": self._safe_text(self._first_value(row, "time", "Time", "TradingTime", "tradingTime")),
            "stream_timestamp": self._safe_text(self._first_value(row, "stream_timestamp", "streamTimestamp")),
            "stream_data_type": FOREIGN_ROOM_CHANNEL_PREFIX,
            "r_type": self._safe_text(self._first_value(row, "r_type", "RType", "rtype")) or FOREIGN_ROOM_CHANNEL_PREFIX,
            "source": "SSI R foreign-room stream",
            "received_at": cached_at,
            "cached_at": cached_at,
            "cache_ttl_seconds": self.ttl_seconds,
            "value_semantics_status": "needs_semantics_proof",
        }
        foreign_room.update(numeric_fields)
        return foreign_room

    @staticmethod
    def _clean_key(key: Any) -> str:
        return "".join(ch for ch in str(key or "").strip().lower() if ch.isalnum())

    @classmethod
    def _first_value(cls, row: Dict[str, Any], *keys: str) -> Any:
        normalized = {cls._clean_key(k): v for k, v in row.items()}
        for key in keys:
            value = normalized.get(cls._clean_key(key))
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _safe_text(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        text = str(value).replace("\r", " ").replace("\n", " ").strip()
        return text[:120] if text else None

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            text = str(value).replace(",", "").strip()
            if text.lower() in {"nan", "none", "null"} or text in {"-", "--"}:
                return None
            return float(text)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _to_nonnegative_float(cls, value: Any) -> Optional[float]:
        number = cls._to_float(value)
        if number is None or number < 0:
            return None
        return number


class SessionStatusCache:
    """Thread-safe latest F stream session/status cache keyed by VN ticker."""

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_SESSION_STATUS_TTL_SECONDS,
        *,
        time_func: Callable[[], float] = time.time,
    ) -> None:
        self.ttl_seconds = max(1, int(ttl_seconds or DEFAULT_SESSION_STATUS_TTL_SECONDS))
        self._time_func = time_func
        self._lock = threading.RLock()
        self._rows: Dict[str, CachedSessionStatus] = {}

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()

    def put_rows(self, rows: Iterable[Dict[str, Any]]) -> int:
        now = float(self._time_func())
        written = 0
        with self._lock:
            for row in rows or []:
                if not isinstance(row, dict):
                    continue
                symbol = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                session_row = dict(row)
                session_row["ticker"] = symbol
                session_row.setdefault("symbol", symbol)
                session_row["cached_at"] = _utc_iso_from_epoch(now)
                session_row["cache_ttl_seconds"] = self.ttl_seconds
                self._rows[symbol] = CachedSessionStatus(
                    symbol=symbol,
                    status=session_row,
                    received_at=now,
                )
                written += 1
        return written

    def get(self, symbol: str) -> Dict[str, Any]:
        normalized = str(symbol or "").strip().upper()
        now = float(self._time_func())
        with self._lock:
            entry = self._rows.get(normalized)

        if entry is None:
            return {
                "status": "empty",
                "row": None,
                "latest_session_timestamp": None,
                "latest_session_age_seconds": None,
            }

        age_seconds = max(0.0, now - entry.received_at)
        row = dict(entry.status)
        row["age_seconds"] = int(age_seconds)
        row["is_stale"] = age_seconds > self.ttl_seconds
        if row["is_stale"]:
            row["stale_reason"] = SSI_STREAMING_REALTIME_CACHE_STALE_REASON
        return {
            "status": "stale" if row["is_stale"] else "hit",
            "row": row,
            "latest_session_timestamp": row.get("stream_timestamp") or row.get("time"),
            "latest_session_age_seconds": int(age_seconds),
        }


class SsiStreamingRealtimeManager:
    """Owns SSI realtime streaming lifecycle and cache handoff.

    The manager does not start itself. Runtime code must call `start` from a
    controlled background lifecycle, and request handlers should only read
    `snapshot`.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        cache: Optional[RealtimeSnapshotCache] = None,
        order_book_cache: Optional[OrderBookCache] = None,
        foreign_room_cache: Optional[ForeignRoomCache] = None,
        trade_tape_cache: Optional[TradeTapeEventCache] = None,
        session_status_cache: Optional[SessionStatusCache] = None,
        parser: Optional[Callable[[List[Any], List[str]], List[Dict[str, Any]]]] = None,
        client_factory: Optional[Callable[[], SsiRealtimeStreamClient]] = None,
        channel_template: str = DEFAULT_STREAMING_REALTIME_CHANNEL_TEMPLATE,
        idle_timeout_seconds: int = DEFAULT_STREAMING_REALTIME_IDLE_TIMEOUT_SECONDS,
        reconnect_enabled: bool = True,
        reconnect_initial_delay_seconds: int = DEFAULT_STREAMING_REALTIME_RECONNECT_INITIAL_DELAY_SECONDS,
        reconnect_max_delay_seconds: int = DEFAULT_STREAMING_REALTIME_RECONNECT_MAX_DELAY_SECONDS,
        reconnect_max_attempts: int = 0,
        order_book_enabled: bool = True,
        foreign_room_enabled: bool = True,
        trade_tape_enabled: bool = True,
        session_status_enabled: bool = True,
        time_func: Callable[[], float] = time.time,
    ) -> None:
        self.enabled = bool(enabled)
        self.cache = cache or RealtimeSnapshotCache(time_func=time_func)
        self.order_book_cache = order_book_cache or OrderBookCache(time_func=time_func)
        self.foreign_room_cache = foreign_room_cache or ForeignRoomCache(time_func=time_func)
        self.trade_tape_cache = trade_tape_cache or TradeTapeEventCache(time_func=time_func)
        self.session_status_cache = session_status_cache or SessionStatusCache(time_func=time_func)
        self._parser = parser or (lambda messages, symbols: [])
        self._client_factory = client_factory
        self.channel_template = channel_template or DEFAULT_STREAMING_REALTIME_CHANNEL_TEMPLATE
        self.idle_timeout_seconds = max(1, int(idle_timeout_seconds or DEFAULT_STREAMING_REALTIME_IDLE_TIMEOUT_SECONDS))
        self.reconnect_enabled = bool(reconnect_enabled)
        self.reconnect_initial_delay_seconds = max(
            1,
            int(reconnect_initial_delay_seconds or DEFAULT_STREAMING_REALTIME_RECONNECT_INITIAL_DELAY_SECONDS),
        )
        self.reconnect_max_delay_seconds = max(
            self.reconnect_initial_delay_seconds,
            int(reconnect_max_delay_seconds or DEFAULT_STREAMING_REALTIME_RECONNECT_MAX_DELAY_SECONDS),
        )
        self.reconnect_max_attempts = max(0, int(reconnect_max_attempts or 0))
        self.order_book_enabled = bool(order_book_enabled)
        self.foreign_room_enabled = bool(foreign_room_enabled)
        self.trade_tape_enabled = bool(trade_tape_enabled)
        self.session_status_enabled = bool(session_status_enabled)
        self._time_func = time_func
        self._lock = threading.RLock()
        self._client: Optional[SsiRealtimeStreamClient] = None
        self._requested_symbols: List[str] = []
        self._channels: List[str] = []
        self._state = MANAGER_DISABLED if not self.enabled else MANAGER_STOPPED
        self._latest_error: Optional[str] = None
        self._last_error_at: Optional[str] = None
        self._last_message_at: Optional[str] = None
        self._last_message_epoch: Optional[float] = None
        self._started_at_epoch: Optional[float] = None
        self._messages_observed = 0
        self._parser_rows_observed = 0
        self._order_book_rows_observed = 0
        self._foreign_room_rows_observed = 0
        self._trade_rows_observed = 0
        self._session_status_rows_observed = 0
        self._bootstrap_status: Optional[str] = None
        self._bootstrap_reason: Optional[str] = None
        self._bootstrap_symbols: List[str] = []
        self._bootstrap_rejected_symbols: List[str] = []
        self._bootstrap_started_by_lifecycle = False
        self._is_idle = False
        self._idle_since: Optional[str] = None
        self._idle_since_epoch: Optional[float] = None
        self._reconnect_attempt_count = 0
        self._last_reconnect_at: Optional[str] = None
        self._last_reconnect_epoch: Optional[float] = None
        self._next_reconnect_at: Optional[str] = None
        self._next_reconnect_epoch: Optional[float] = None
        self._reconnect_backoff_seconds = self.reconnect_initial_delay_seconds
        self._last_reconnect_reason: Optional[str] = None
        self._last_reconnect_error: Optional[str] = None
        self._reconnect_in_progress = False
        self._shutdown_requested = False

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def start(self, symbols: Iterable[str]) -> Dict[str, Any]:
        normalized_symbols = normalize_streaming_symbols(symbols)
        with self._lock:
            if not self.enabled:
                self._state = MANAGER_DISABLED
                return self.status()
            if self._state == MANAGER_RUNNING:
                return self.status()
            self._state = MANAGER_STARTING
            self._latest_error = None
            self._requested_symbols = normalized_symbols
            self._channels = []

        try:
            channels = build_streaming_channels(
                normalized_symbols,
                realtime_template=self.channel_template,
                order_book_enabled=self.order_book_enabled,
                foreign_room_enabled=self.foreign_room_enabled,
                trade_tape_enabled=self.trade_tape_enabled,
                session_status_enabled=self.session_status_enabled,
            )
            if not channels:
                raise ValueError("At least one streaming symbol is required.")
            if self._client_factory is None:
                raise RuntimeError(SSI_STREAMING_REALTIME_LIVE_ADAPTER_DISABLED_REASON)
            client = self._client_factory()
            client.start(self.handle_message, self.handle_error, channels)
        except Exception as exc:
            self._record_error(exc, set_errored=True)
            return self.status()

        with self._lock:
            self._client = client
            self._channels = channels
            self._state = MANAGER_RUNNING
            started_at = float(self._time_func())
            self._started_at_epoch = started_at
            self._is_idle = False
            self._idle_since = None
            self._idle_since_epoch = None
            self._next_reconnect_at = None
            self._next_reconnect_epoch = None
            self._reconnect_backoff_seconds = self.reconnect_initial_delay_seconds
            self._last_reconnect_error = None
            self._shutdown_requested = False
            return self.status()

    def set_bootstrap_context(
        self,
        *,
        status: Optional[str],
        reason: Optional[str] = None,
        symbols: Optional[Iterable[str]] = None,
        rejected_symbols: Optional[Iterable[str]] = None,
        started_by_lifecycle: bool = False,
    ) -> None:
        """Attach backend lifecycle bootstrap diagnostics to manager status."""
        with self._lock:
            self._bootstrap_status = str(status).strip() if status else None
            self._bootstrap_reason = sanitize_streaming_error(reason) if reason else None
            self._bootstrap_symbols = normalize_streaming_symbols(symbols or [])
            self._bootstrap_rejected_symbols = normalize_streaming_symbols(rejected_symbols or [])
            self._bootstrap_started_by_lifecycle = bool(started_by_lifecycle)

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            client = self._client
            self._client = None
            self._next_reconnect_at = None
            self._next_reconnect_epoch = None
        if client is not None:
            try:
                client.stop()
            except Exception as exc:
                self._record_error(exc, set_errored=True)
        with self._lock:
            if not self.enabled:
                self._state = MANAGER_DISABLED
                self._channels = []
            elif self._state != MANAGER_ERRORED:
                self._state = MANAGER_STOPPED
                self._channels = []
            return self.status()

    def handle_message(self, message: Any) -> None:
        with self._lock:
            if self._state != MANAGER_RUNNING:
                return
            requested_symbols = list(self._requested_symbols)
        try:
            rows = self._parser([message], requested_symbols)
            requested_set = set(requested_symbols)
            filtered_rows = [
                row
                for row in rows or []
                if isinstance(row, dict)
                and str(row.get("ticker") or row.get("symbol") or "").strip().upper() in requested_set
            ]
            session_rows = [row for row in filtered_rows if self._is_session_status_row(row)]
            order_book_rows = [row for row in filtered_rows if self._is_order_book_row(row)]
            foreign_room_rows = [row for row in filtered_rows if self._is_foreign_room_row(row)]
            snapshot_rows = [
                row
                for row in filtered_rows
                if not self._is_session_status_row(row)
                and not self._is_order_book_row(row)
                and not self._is_foreign_room_row(row)
            ]
            written = self.cache.put_rows(snapshot_rows)
            order_book_written = self.order_book_cache.put_rows(order_book_rows)
            foreign_room_written = self.foreign_room_cache.put_rows(foreign_room_rows)
            trade_written = self.trade_tape_cache.put_rows(
                self._trade_events_from_streaming_rows(snapshot_rows)
            )
            session_written = self.session_status_cache.put_rows(session_rows)
            with self._lock:
                self._messages_observed += 1
                self._parser_rows_observed += written
                self._order_book_rows_observed += order_book_written
                self._foreign_room_rows_observed += foreign_room_written
                self._trade_rows_observed += trade_written
                self._session_status_rows_observed += session_written
                now = float(self._time_func())
                self._last_message_epoch = now
                self._last_message_at = _utc_iso_from_epoch(now)
                self._is_idle = False
                self._idle_since = None
                self._idle_since_epoch = None
        except Exception as exc:
            self._record_error(exc, set_errored=False)

    @staticmethod
    def _is_session_status_row(row: Dict[str, Any]) -> bool:
        raw_type = str(row.get("stream_data_type") or row.get("r_type") or "").strip().upper()
        return raw_type == SESSION_STATUS_CHANNEL_PREFIX

    @staticmethod
    def _is_order_book_row(row: Dict[str, Any]) -> bool:
        raw_type = str(row.get("stream_data_type") or row.get("r_type") or "").strip().upper()
        return raw_type == ORDER_BOOK_CHANNEL_PREFIX

    @staticmethod
    def _is_foreign_room_row(row: Dict[str, Any]) -> bool:
        raw_type = str(row.get("stream_data_type") or row.get("r_type") or "").strip().upper()
        return raw_type == FOREIGN_ROOM_CHANNEL_PREFIX

    @staticmethod
    def _trade_events_from_streaming_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            raw_type = str(row.get("stream_data_type") or row.get("r_type") or "").strip().upper()
            if raw_type != "X-TRADE" or not row.get("has_last_trade"):
                continue
            symbol = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
            price = row.get("price")
            volume = row.get("last_volume")
            timestamp = row.get("stream_timestamp")
            if not symbol or price is None or volume is None or not timestamp:
                continue
            raw_side = row.get("side_if_available")
            side = normalize_trade_side(raw_side)
            event = {
                "ticker": symbol,
                "symbol": symbol,
                "price": price,
                "volume": volume,
                "value": row.get("last_value"),
                "side": side,
                "side_label": "Buy" if side == "buy" else "Sell" if side == "sell" else None,
                "side_if_available": raw_side,
                "timestamp": timestamp,
                "timestamp_display": row.get("time"),
                "time": row.get("time"),
                "source": "SSI trade-tape contract",
                "sequence": row.get("sequence_if_available"),
                "sequence_if_available": row.get("sequence_if_available"),
                "raw_type": raw_type,
                "match_type": raw_side,
                "id": row.get("sequence_if_available"),
            }
            events.append(event)
        return events

    def handle_error(self, error: Any) -> None:
        self._record_error(error, set_errored=True)

    def snapshot(self, symbols: Iterable[str]) -> Dict[str, Any]:
        requested = normalize_streaming_symbols(symbols)
        base = {
            "source": "SSI",
            "requested_tickers": requested,
            "quotes": [],
            "count": 0,
            "attempted_endpoints": [],
            "candidate_endpoints": [],
            "rest_status": "unsupported",
            "streaming_data_types": ["X"],
        }
        status = self.status()
        manager_state = status["manager_state"]
        diagnostics = dict(status)
        diagnostics["cache_ttl_seconds"] = self.cache.ttl_seconds

        if not self.enabled:
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_DISABLED_REASON,
                "streaming_status": "disabled",
                "cache_status": "disabled",
                "manager_state": MANAGER_DISABLED,
                "parsed_streaming_rows": diagnostics["parser_rows_observed"],
                "diagnostics": diagnostics,
            }
        if manager_state == MANAGER_ERRORED:
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_MANAGER_ERROR_REASON,
                "streaming_status": "manager_error",
                "cache_status": "unavailable",
                "manager_state": manager_state,
                "parsed_streaming_rows": diagnostics["parser_rows_observed"],
                "diagnostics": diagnostics,
            }
        if manager_state != MANAGER_RUNNING:
            reason = SSI_STREAMING_REALTIME_NOT_STARTED_REASON
            streaming_status = "manager_not_started"
            cache_status = "not_started"
            if diagnostics.get("bootstrap_status") == "symbols_empty":
                reason = SSI_STREAMING_REALTIME_BOOTSTRAP_EMPTY_REASON
                streaming_status = "bootstrap_symbols_empty"
                cache_status = "bootstrap_symbols_empty"
            return {
                **base,
                "status": "unavailable",
                "reason": reason,
                "streaming_status": streaming_status,
                "cache_status": cache_status,
                "manager_state": manager_state,
                "parsed_streaming_rows": diagnostics["parser_rows_observed"],
                "diagnostics": diagnostics,
            }

        cache_result = self.cache.get_many(requested)
        diagnostics.update(
            {
                "cache_hit_count": cache_result["hit_count"],
                "cache_stale_count": cache_result["stale_count"],
                "cache_empty_count": cache_result["empty_count"],
                "cache_stale_symbols": cache_result["stale_symbols"],
                "cache_empty_symbols": cache_result["empty_symbols"],
                "cache_ages_seconds": cache_result["ages_seconds"],
            }
        )
        if cache_result["rows"]:
            return {
                **base,
                "status": "ok",
                "reason": None,
                "quotes": cache_result["rows"],
                "count": len(cache_result["rows"]),
                "streaming_status": "cache_hit",
                "cache_status": "hit",
                "manager_state": manager_state,
                "parsed_streaming_rows": diagnostics["parser_rows_observed"],
                "diagnostics": diagnostics,
            }
        if cache_result["stale_count"] > 0:
            reason = SSI_STREAMING_REALTIME_CACHE_STALE_REASON
            streaming_status = "cache_stale"
            cache_status = "stale"
        else:
            reason = SSI_STREAMING_REALTIME_CACHE_EMPTY_REASON
            streaming_status = "cache_empty"
            cache_status = "empty"
        return {
            **base,
            "status": "unavailable",
            "reason": reason,
            "streaming_status": streaming_status,
            "cache_status": cache_status,
            "manager_state": manager_state,
            "parsed_streaming_rows": diagnostics["parser_rows_observed"],
            "diagnostics": diagnostics,
        }

    def order_book(self, symbol: str) -> Dict[str, Any]:
        requested_symbol = str(symbol or "").strip().upper()
        status = self.status()
        diagnostics = dict(status)
        diagnostics.update(
            {
                "streaming_status": "order_book_buffer",
                "cache_ttl_seconds": self.order_book_cache.ttl_seconds,
                "order_book_ttl_seconds": self.order_book_cache.ttl_seconds,
                "order_book_max_levels": self.order_book_cache.max_levels,
                "channel_type": ORDER_BOOK_CHANNEL_PREFIX,
                "order_book_rows_observed": self._order_book_rows_observed,
            }
        )
        base = {
            "source": "SSI",
            "symbol": requested_symbol,
            "order_book": None,
            "count": 0,
            "streaming_data_types": [ORDER_BOOK_CHANNEL_PREFIX],
            "attempted_endpoints": [],
            "candidate_endpoints": [],
            "rest_status": "unsupported",
        }

        if not requested_symbol:
            diagnostics["failure_class"] = "missing_symbol"
            return {
                **base,
                "status": "unavailable",
                "reason": "No symbol requested",
                "streaming_status": "missing_symbol",
                "cache_status": "unavailable",
                "manager_state": status["manager_state"],
                "diagnostics": diagnostics,
            }
        if not self.enabled:
            diagnostics.update({"streaming_status": "disabled", "cache_status": "disabled"})
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_DISABLED_REASON,
                "streaming_status": "disabled",
                "cache_status": "disabled",
                "manager_state": MANAGER_DISABLED,
                "diagnostics": diagnostics,
            }

        manager_state = status["manager_state"]
        if not self.order_book_enabled:
            diagnostics.update({"streaming_status": "xquote_disabled", "cache_status": "disabled"})
            return {
                **base,
                "status": "unavailable",
                "reason": "SSI X-QUOTE stream channel disabled.",
                "streaming_status": "xquote_disabled",
                "cache_status": "disabled",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        if manager_state == MANAGER_ERRORED:
            diagnostics.update({"streaming_status": "manager_error", "cache_status": "unavailable"})
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_MANAGER_ERROR_REASON,
                "streaming_status": "manager_error",
                "cache_status": "unavailable",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }
        if manager_state != MANAGER_RUNNING:
            reason = SSI_STREAMING_REALTIME_NOT_STARTED_REASON
            streaming_status = "manager_not_started"
            cache_status = "not_started"
            if diagnostics.get("bootstrap_status") == "symbols_empty":
                reason = SSI_STREAMING_REALTIME_BOOTSTRAP_EMPTY_REASON
                streaming_status = "bootstrap_symbols_empty"
                cache_status = "bootstrap_symbols_empty"
            diagnostics.update({"streaming_status": streaming_status, "cache_status": cache_status})
            return {
                **base,
                "status": "unavailable",
                "reason": reason,
                "streaming_status": streaming_status,
                "cache_status": cache_status,
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        configured_symbols = set(normalize_streaming_symbols(status.get("requested_symbols") or []))
        bootstrap_symbols = set(normalize_streaming_symbols(status.get("bootstrap_symbols") or []))
        membership_symbols = configured_symbols or bootstrap_symbols
        if membership_symbols and requested_symbol not in membership_symbols:
            diagnostics.update(
                {
                    "streaming_status": "ticker_not_bootstrapped",
                    "cache_status": "not_bootstrapped",
                    "bootstrap_membership": "not_bootstrapped",
                }
            )
            return {
                **base,
                "status": "unavailable",
                "reason": "SSI X-QUOTE stream not bootstrapped.",
                "streaming_status": "ticker_not_bootstrapped",
                "cache_status": "not_bootstrapped",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        if requested_symbol and build_order_book_channel(requested_symbol) not in set(status.get("order_book_channels") or []):
            diagnostics.update(
                {
                    "streaming_status": "xquote_not_subscribed",
                    "cache_status": "not_subscribed",
                    "bootstrap_membership": "bootstrapped",
                }
            )
            return {
                **base,
                "status": "unavailable",
                "reason": "SSI X-QUOTE stream channel not subscribed.",
                "streaming_status": "xquote_not_subscribed",
                "cache_status": "not_subscribed",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        cache_result = self.order_book_cache.get(requested_symbol)
        cache_status = cache_result["status"]
        diagnostics.update(
            {
                "streaming_status": "cache_hit" if cache_status == "hit" else f"cache_{cache_status}",
                "cache_status": cache_status,
                "latest_order_book_timestamp": cache_result["latest_order_book_timestamp"],
                "latest_order_book_age_seconds": cache_result["latest_order_book_age_seconds"],
            }
        )
        if cache_status == "hit" and cache_result["row"]:
            return {
                **base,
                "status": "ok",
                "reason": None,
                "order_book": cache_result["row"],
                "count": 1,
                "streaming_status": "cache_hit",
                "cache_status": "hit",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        reason = (
            "SSI X-QUOTE stream cache stale."
            if cache_status == "stale"
            else "SSI X-QUOTE stream cache empty."
        )
        streaming_status = "cache_stale" if cache_status == "stale" else "subscribed_no_event"
        diagnostics.update({"streaming_status": streaming_status})
        return {
            **base,
            "status": "unavailable",
            "reason": reason,
            "streaming_status": streaming_status,
            "cache_status": cache_status,
            "manager_state": manager_state,
            "diagnostics": diagnostics,
        }

    def foreign_room(self, symbol: str) -> Dict[str, Any]:
        requested_symbol = str(symbol or "").strip().upper()
        status = self.status()
        diagnostics = dict(status)
        diagnostics.update(
            {
                "streaming_status": "foreign_room_buffer",
                "cache_ttl_seconds": self.foreign_room_cache.ttl_seconds,
                "foreign_room_ttl_seconds": self.foreign_room_cache.ttl_seconds,
                "channel_type": FOREIGN_ROOM_CHANNEL_PREFIX,
                "foreign_room_rows_observed": self._foreign_room_rows_observed,
            }
        )
        base = {
            "source": "SSI",
            "symbol": requested_symbol,
            "foreign_room": None,
            "count": 0,
            "streaming_data_types": [FOREIGN_ROOM_CHANNEL_PREFIX],
            "attempted_endpoints": [],
            "candidate_endpoints": [],
            "rest_status": "unsupported",
        }

        if not requested_symbol:
            diagnostics["failure_class"] = "missing_symbol"
            return {
                **base,
                "status": "unavailable",
                "reason": "No symbol requested",
                "streaming_status": "missing_symbol",
                "cache_status": "unavailable",
                "manager_state": status["manager_state"],
                "diagnostics": diagnostics,
            }
        if not self.enabled:
            diagnostics.update({"streaming_status": "disabled", "cache_status": "disabled"})
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_DISABLED_REASON,
                "streaming_status": "disabled",
                "cache_status": "disabled",
                "manager_state": MANAGER_DISABLED,
                "diagnostics": diagnostics,
            }

        manager_state = status["manager_state"]
        if not self.foreign_room_enabled:
            diagnostics.update({"streaming_status": "r_disabled", "cache_status": "disabled"})
            return {
                **base,
                "status": "unavailable",
                "reason": "SSI R foreign-room stream channel disabled.",
                "streaming_status": "r_disabled",
                "cache_status": "disabled",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        if manager_state == MANAGER_ERRORED:
            diagnostics.update({"streaming_status": "manager_error", "cache_status": "unavailable"})
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_MANAGER_ERROR_REASON,
                "streaming_status": "manager_error",
                "cache_status": "unavailable",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }
        if manager_state != MANAGER_RUNNING:
            reason = SSI_STREAMING_REALTIME_NOT_STARTED_REASON
            streaming_status = "manager_not_started"
            cache_status = "not_started"
            if diagnostics.get("bootstrap_status") == "symbols_empty":
                reason = SSI_STREAMING_REALTIME_BOOTSTRAP_EMPTY_REASON
                streaming_status = "bootstrap_symbols_empty"
                cache_status = "bootstrap_symbols_empty"
            diagnostics.update({"streaming_status": streaming_status, "cache_status": cache_status})
            return {
                **base,
                "status": "unavailable",
                "reason": reason,
                "streaming_status": streaming_status,
                "cache_status": cache_status,
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        configured_symbols = set(normalize_streaming_symbols(status.get("requested_symbols") or []))
        bootstrap_symbols = set(normalize_streaming_symbols(status.get("bootstrap_symbols") or []))
        membership_symbols = configured_symbols or bootstrap_symbols
        if membership_symbols and requested_symbol not in membership_symbols:
            diagnostics.update(
                {
                    "streaming_status": "ticker_not_bootstrapped",
                    "cache_status": "not_bootstrapped",
                    "bootstrap_membership": "not_bootstrapped",
                }
            )
            return {
                **base,
                "status": "unavailable",
                "reason": "SSI R foreign-room stream not bootstrapped.",
                "streaming_status": "ticker_not_bootstrapped",
                "cache_status": "not_bootstrapped",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        if requested_symbol and build_foreign_room_channel(requested_symbol) not in set(status.get("foreign_room_channels") or []):
            diagnostics.update(
                {
                    "streaming_status": "r_not_subscribed",
                    "cache_status": "not_subscribed",
                    "bootstrap_membership": "bootstrapped",
                }
            )
            return {
                **base,
                "status": "unavailable",
                "reason": "SSI R foreign-room stream channel not subscribed.",
                "streaming_status": "r_not_subscribed",
                "cache_status": "not_subscribed",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        cache_result = self.foreign_room_cache.get(requested_symbol)
        cache_status = cache_result["status"]
        diagnostics.update(
            {
                "streaming_status": "cache_hit" if cache_status == "hit" else f"cache_{cache_status}",
                "cache_status": cache_status,
                "latest_foreign_room_timestamp": cache_result["latest_foreign_room_timestamp"],
                "latest_foreign_room_age_seconds": cache_result["latest_foreign_room_age_seconds"],
            }
        )
        if cache_status == "hit" and cache_result["row"]:
            return {
                **base,
                "status": "ok",
                "reason": None,
                "foreign_room": cache_result["row"],
                "count": 1,
                "streaming_status": "cache_hit",
                "cache_status": "hit",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        reason = (
            "SSI R foreign-room stream cache stale."
            if cache_status == "stale"
            else "SSI R foreign-room stream cache empty."
        )
        streaming_status = "cache_stale" if cache_status == "stale" else "subscribed_no_event"
        diagnostics.update({"streaming_status": streaming_status})
        return {
            **base,
            "status": "unavailable",
            "reason": reason,
            "streaming_status": streaming_status,
            "cache_status": cache_status,
            "manager_state": manager_state,
            "diagnostics": diagnostics,
        }

    def trade_tape(self, symbol: str, limit: int = DEFAULT_TRADE_TAPE_BUFFER_SIZE) -> Dict[str, Any]:
        requested_symbol = str(symbol or "").strip().upper()
        safe_limit = max(1, min(int(limit or DEFAULT_TRADE_TAPE_BUFFER_SIZE), self.trade_tape_cache.max_rows_per_symbol))
        status = self.status()
        diagnostics = dict(status)
        diagnostics.update(
            {
                "streaming_status": "trade_tape_buffer",
                "cache_ttl_seconds": self.trade_tape_cache.ttl_seconds,
                "trade_tape_ttl_seconds": self.trade_tape_cache.ttl_seconds,
                "trade_tape_buffer_size": self.trade_tape_cache.max_rows_per_symbol,
                "channel_type": TRADE_TAPE_CHANNEL_PREFIX,
                "trade_rows_observed": self._trade_rows_observed,
            }
        )
        base = {
            "source": "SSI",
            "symbol": requested_symbol,
            "trades": [],
            "count": 0,
            "streaming_data_types": ["X-TRADE"],
            "attempted_endpoints": [],
            "candidate_endpoints": [],
            "rest_status": "unsupported",
        }

        if not requested_symbol:
            diagnostics["failure_class"] = "missing_symbol"
            return {
                **base,
                "status": "unavailable",
                "reason": "No symbol requested",
                "streaming_status": "missing_symbol",
                "cache_status": "unavailable",
                "manager_state": status["manager_state"],
                "diagnostics": diagnostics,
            }
        if not self.enabled:
            diagnostics.update({"streaming_status": "disabled", "cache_status": "disabled"})
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_DISABLED_REASON,
                "streaming_status": "disabled",
                "cache_status": "disabled",
                "manager_state": MANAGER_DISABLED,
                "diagnostics": diagnostics,
            }
        manager_state = status["manager_state"]
        if not self.trade_tape_enabled:
            diagnostics.update({"streaming_status": "xtrade_disabled", "cache_status": "disabled"})
            return {
                **base,
                "status": "unavailable",
                "reason": "SSI X-TRADE stream channel disabled.",
                "streaming_status": "xtrade_disabled",
                "cache_status": "disabled",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        if manager_state == MANAGER_ERRORED:
            diagnostics.update({"streaming_status": "manager_error", "cache_status": "unavailable"})
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_MANAGER_ERROR_REASON,
                "streaming_status": "manager_error",
                "cache_status": "unavailable",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }
        if manager_state != MANAGER_RUNNING:
            reason = SSI_STREAMING_REALTIME_NOT_STARTED_REASON
            streaming_status = "manager_not_started"
            cache_status = "not_started"
            if diagnostics.get("bootstrap_status") == "symbols_empty":
                reason = SSI_STREAMING_REALTIME_BOOTSTRAP_EMPTY_REASON
                streaming_status = "bootstrap_symbols_empty"
                cache_status = "bootstrap_symbols_empty"
            diagnostics.update({"streaming_status": streaming_status, "cache_status": cache_status})
            return {
                **base,
                "status": "unavailable",
                "reason": reason,
                "streaming_status": streaming_status,
                "cache_status": cache_status,
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        configured_symbols = set(normalize_streaming_symbols(status.get("requested_symbols") or []))
        bootstrap_symbols = set(normalize_streaming_symbols(status.get("bootstrap_symbols") or []))
        membership_symbols = configured_symbols or bootstrap_symbols
        if membership_symbols and requested_symbol not in membership_symbols:
            diagnostics.update(
                {
                    "streaming_status": "ticker_not_bootstrapped",
                    "cache_status": "not_bootstrapped",
                    "bootstrap_membership": "not_bootstrapped",
                }
            )
            return {
                **base,
                "status": "unavailable",
                "reason": "SSI trade tape stream not bootstrapped.",
                "streaming_status": "ticker_not_bootstrapped",
                "cache_status": "not_bootstrapped",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        if requested_symbol and build_trade_tape_channel(requested_symbol) not in set(status.get("trade_tape_channels") or []):
            diagnostics.update(
                {
                    "streaming_status": "xtrade_not_subscribed",
                    "cache_status": "not_subscribed",
                    "bootstrap_membership": "bootstrapped",
                }
            )
            return {
                **base,
                "status": "unavailable",
                "reason": "SSI X-TRADE stream channel not subscribed.",
                "streaming_status": "xtrade_not_subscribed",
                "cache_status": "not_subscribed",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        cache_result = self.trade_tape_cache.get(requested_symbol, safe_limit)
        diagnostics.update(
            {
                "streaming_status": "cache_hit" if cache_result["status"] == "hit" else f"cache_{cache_result['status']}",
                "cache_status": cache_result["status"],
                "trade_tape_buffer_row_count": cache_result["buffer_row_count"],
                "trade_tape_returned_row_count": cache_result["row_count"],
                "latest_trade_timestamp": cache_result["latest_trade_timestamp"],
                "latest_trade_age_seconds": cache_result["latest_trade_age_seconds"],
            }
        )
        if cache_result["rows"]:
            streaming_status = "cache_stale" if cache_result["status"] == "stale" else "cache_hit"
            return {
                **base,
                "status": "ok",
                "reason": "Buffered SSI X-TRADE rows available." if cache_result["status"] == "stale" else None,
                "trades": cache_result["rows"],
                "count": len(cache_result["rows"]),
                "streaming_status": streaming_status,
                "cache_status": cache_result["status"],
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        reason = (
            "SSI trade tape stream buffer stale."
            if cache_result["status"] == "stale"
            else "SSI trade tape stream buffer empty."
        )
        return {
            **base,
            "status": "unavailable",
            "reason": reason,
            "streaming_status": diagnostics["streaming_status"],
            "cache_status": cache_result["status"],
            "manager_state": manager_state,
            "diagnostics": diagnostics,
        }

    def session_status(self, symbol: str) -> Dict[str, Any]:
        requested_symbol = str(symbol or "").strip().upper()
        status = self.status()
        diagnostics = dict(status)
        diagnostics.update(
            {
                "streaming_status": "session_status_buffer",
                "cache_ttl_seconds": self.session_status_cache.ttl_seconds,
                "session_status_ttl_seconds": self.session_status_cache.ttl_seconds,
                "channel_type": SESSION_STATUS_CHANNEL_PREFIX,
                "session_status_rows_observed": self._session_status_rows_observed,
            }
        )
        base = {
            "source": "SSI",
            "symbol": requested_symbol,
            "session_status": None,
            "count": 0,
            "streaming_data_types": [SESSION_STATUS_CHANNEL_PREFIX],
            "attempted_endpoints": [],
            "candidate_endpoints": [],
            "rest_status": "unsupported",
        }

        if not requested_symbol:
            diagnostics["failure_class"] = "missing_symbol"
            return {
                **base,
                "status": "unavailable",
                "reason": "No symbol requested",
                "streaming_status": "missing_symbol",
                "cache_status": "unavailable",
                "manager_state": status["manager_state"],
                "diagnostics": diagnostics,
            }
        if not self.enabled:
            diagnostics.update({"streaming_status": "disabled", "cache_status": "disabled"})
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_DISABLED_REASON,
                "streaming_status": "disabled",
                "cache_status": "disabled",
                "manager_state": MANAGER_DISABLED,
                "diagnostics": diagnostics,
            }

        manager_state = status["manager_state"]
        if not self.session_status_enabled:
            diagnostics.update({"streaming_status": "f_disabled", "cache_status": "disabled"})
            return {
                **base,
                "status": "unavailable",
                "reason": "SSI F stream channel disabled.",
                "streaming_status": "f_disabled",
                "cache_status": "disabled",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        if manager_state == MANAGER_ERRORED:
            diagnostics.update({"streaming_status": "manager_error", "cache_status": "unavailable"})
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_MANAGER_ERROR_REASON,
                "streaming_status": "manager_error",
                "cache_status": "unavailable",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }
        if manager_state != MANAGER_RUNNING:
            reason = SSI_STREAMING_REALTIME_NOT_STARTED_REASON
            streaming_status = "manager_not_started"
            cache_status = "not_started"
            if diagnostics.get("bootstrap_status") == "symbols_empty":
                reason = SSI_STREAMING_REALTIME_BOOTSTRAP_EMPTY_REASON
                streaming_status = "bootstrap_symbols_empty"
                cache_status = "bootstrap_symbols_empty"
            diagnostics.update({"streaming_status": streaming_status, "cache_status": cache_status})
            return {
                **base,
                "status": "unavailable",
                "reason": reason,
                "streaming_status": streaming_status,
                "cache_status": cache_status,
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        configured_symbols = set(normalize_streaming_symbols(status.get("requested_symbols") or []))
        bootstrap_symbols = set(normalize_streaming_symbols(status.get("bootstrap_symbols") or []))
        membership_symbols = configured_symbols or bootstrap_symbols
        if membership_symbols and requested_symbol not in membership_symbols:
            diagnostics.update(
                {
                    "streaming_status": "ticker_not_bootstrapped",
                    "cache_status": "not_bootstrapped",
                    "bootstrap_membership": "not_bootstrapped",
                }
            )
            return {
                **base,
                "status": "unavailable",
                "reason": "SSI F stream not bootstrapped.",
                "streaming_status": "ticker_not_bootstrapped",
                "cache_status": "not_bootstrapped",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        if requested_symbol and build_session_status_channel(requested_symbol) not in set(status.get("session_status_channels") or []):
            diagnostics.update(
                {
                    "streaming_status": "f_not_subscribed",
                    "cache_status": "not_subscribed",
                    "bootstrap_membership": "bootstrapped",
                }
            )
            return {
                **base,
                "status": "unavailable",
                "reason": "SSI F stream channel not subscribed.",
                "streaming_status": "f_not_subscribed",
                "cache_status": "not_subscribed",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        cache_result = self.session_status_cache.get(requested_symbol)
        cache_status = cache_result["status"]
        diagnostics.update(
            {
                "streaming_status": "cache_hit" if cache_status == "hit" else f"cache_{cache_status}",
                "cache_status": cache_status,
                "latest_session_timestamp": cache_result["latest_session_timestamp"],
                "latest_session_age_seconds": cache_result["latest_session_age_seconds"],
            }
        )
        if cache_status == "hit" and cache_result["row"]:
            return {
                **base,
                "status": "ok",
                "reason": None,
                "session_status": cache_result["row"],
                "count": 1,
                "streaming_status": "cache_hit",
                "cache_status": "hit",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        reason = (
            "SSI F stream cache stale."
            if cache_status == "stale"
            else "SSI F stream cache empty."
        )
        streaming_status = "cache_stale" if cache_status == "stale" else "subscribed_no_event"
        diagnostics.update({"streaming_status": streaming_status})
        return {
            **base,
            "status": "unavailable",
            "reason": reason,
            "streaming_status": streaming_status,
            "cache_status": cache_status,
            "manager_state": manager_state,
            "diagnostics": diagnostics,
        }

    def status(self) -> Dict[str, Any]:
        with self._lock:
            self._refresh_idle_state_locked()
            realtime_channels = [
                channel
                for channel in self._channels
                if not is_order_book_channel(channel)
                and not is_foreign_room_channel(channel)
                and not is_trade_tape_channel(channel)
                and not is_session_status_channel(channel)
            ]
            order_book_channels = [channel for channel in self._channels if is_order_book_channel(channel)]
            foreign_room_channels = [channel for channel in self._channels if is_foreign_room_channel(channel)]
            trade_tape_channels = [channel for channel in self._channels if is_trade_tape_channel(channel)]
            session_status_channels = [channel for channel in self._channels if is_session_status_channel(channel)]
            order_book_subscription_status = (
                "disabled"
                if not self.order_book_enabled
                else ("subscribed" if order_book_channels else "not_subscribed")
            )
            foreign_room_subscription_status = (
                "disabled"
                if not self.foreign_room_enabled
                else ("subscribed" if foreign_room_channels else "not_subscribed")
            )
            trade_tape_subscription_status = (
                "disabled"
                if not self.trade_tape_enabled
                else ("subscribed" if trade_tape_channels else "not_subscribed")
            )
            session_status_subscription_status = (
                "disabled"
                if not self.session_status_enabled
                else ("subscribed" if session_status_channels else "not_subscribed")
            )
            return {
                "enabled": self.enabled,
                "manager_state": self._state,
                "requested_symbols": list(self._requested_symbols),
                "channels": list(self._channels),
                "realtime_channels": realtime_channels,
                "order_book_channels": order_book_channels,
                "order_book_channel_type": ORDER_BOOK_CHANNEL_PREFIX,
                "order_book_subscription_status": order_book_subscription_status,
                "foreign_room_channels": foreign_room_channels,
                "foreign_room_channel_type": FOREIGN_ROOM_CHANNEL_PREFIX,
                "foreign_room_subscription_status": foreign_room_subscription_status,
                "trade_tape_channels": trade_tape_channels,
                "trade_tape_channel_type": TRADE_TAPE_CHANNEL_PREFIX,
                "trade_tape_subscription_status": trade_tape_subscription_status,
                "session_status_channels": session_status_channels,
                "session_status_channel_type": SESSION_STATUS_CHANNEL_PREFIX,
                "session_status_subscription_status": session_status_subscription_status,
                "live_adapter_status": "enabled" if self._client_factory is not None else "not_enabled",
                "latest_error": self._latest_error,
                "last_error_at": self._last_error_at,
                "last_message_at": self._last_message_at,
                "messages_observed": self._messages_observed,
                "parser_rows_observed": self._parser_rows_observed,
                "order_book_rows_observed": self._order_book_rows_observed,
                "foreign_room_rows_observed": self._foreign_room_rows_observed,
                "trade_rows_observed": self._trade_rows_observed,
                "session_status_rows_observed": self._session_status_rows_observed,
                "bootstrap_status": self._bootstrap_status,
                "bootstrap_reason": self._bootstrap_reason,
                "bootstrap_symbols": list(self._bootstrap_symbols),
                "bootstrap_rejected_symbols": list(self._bootstrap_rejected_symbols),
                "bootstrap_started_by_lifecycle": self._bootstrap_started_by_lifecycle,
                "idle_timeout_seconds": self.idle_timeout_seconds,
                "is_idle": self._is_idle,
                "idle_since": self._idle_since,
                "reconnect_enabled": self.reconnect_enabled,
                "reconnect_attempt_count": self._reconnect_attempt_count,
                "last_reconnect_at": self._last_reconnect_at,
                "next_reconnect_at": self._next_reconnect_at,
                "reconnect_backoff_seconds": self._reconnect_backoff_seconds,
                "last_reconnect_reason": self._last_reconnect_reason,
                "last_reconnect_error": self._last_reconnect_error,
                "runtime_status": self._runtime_status_locked(),
            }

    def _record_error(self, error: Any, *, set_errored: bool) -> None:
        with self._lock:
            self._latest_error = sanitize_streaming_error(error)
            self._last_error_at = _utc_iso_from_epoch(float(self._time_func()))
            if set_errored:
                self._state = MANAGER_ERRORED

    def mark_shutdown(self) -> None:
        """Mark the manager as shutting down so monitor ticks cannot revive it."""
        with self._lock:
            self._shutdown_requested = True
            self._next_reconnect_at = None
            self._next_reconnect_epoch = None

    def monitor_tick(self, *, wants_streaming: bool) -> Dict[str, Any]:
        """Run one deterministic idle/reconnect monitor iteration."""
        action = self._prepare_reconnect_action(wants_streaming=bool(wants_streaming))
        if action is None:
            return self.status()

        symbols, reason = action
        reconnect_error: Optional[str] = None
        try:
            self._stop_client_for_reconnect()
            status = self.start(symbols)
            if status.get("manager_state") == MANAGER_RUNNING:
                with self._lock:
                    self._next_reconnect_at = None
                    self._next_reconnect_epoch = None
                    self._reconnect_backoff_seconds = self.reconnect_initial_delay_seconds
                    self._last_reconnect_error = None
                    self._last_reconnect_reason = reason
                return self.status()
            reconnect_error = status.get("latest_error") or "reconnect attempt failed"
        except Exception as exc:  # pragma: no cover - defensive path
            reconnect_error = sanitize_streaming_error(exc)
            self._record_error(exc, set_errored=True)
        finally:
            with self._lock:
                self._reconnect_in_progress = False

        with self._lock:
            self._last_reconnect_error = sanitize_streaming_error(reconnect_error)
            if self.reconnect_max_attempts > 0 and self._reconnect_attempt_count >= self.reconnect_max_attempts:
                self._next_reconnect_at = None
                self._next_reconnect_epoch = None
            else:
                self._schedule_reconnect_locked(reason=reason, from_now=True)
        return self.status()

    def _prepare_reconnect_action(self, *, wants_streaming: bool) -> Optional[Tuple[List[str], str]]:
        with self._lock:
            self._refresh_idle_state_locked()
            if (
                not self.enabled
                or not wants_streaming
                or self._shutdown_requested
                or self._reconnect_in_progress
                or not self.reconnect_enabled
            ):
                return None
            symbols = list(self._requested_symbols or self._bootstrap_symbols)
            if not symbols:
                return None

            reason = self._reconnect_reason_locked()
            if reason is None:
                return None
            if self.reconnect_max_attempts > 0 and self._reconnect_attempt_count >= self.reconnect_max_attempts:
                self._next_reconnect_at = None
                self._next_reconnect_epoch = None
                self._last_reconnect_reason = reason
                self._last_reconnect_error = "reconnect max attempts reached"
                return None
            now = float(self._time_func())
            if self._next_reconnect_epoch is None:
                self._schedule_reconnect_locked(reason=reason, from_now=True)
                return None
            if now < self._next_reconnect_epoch:
                return None

            self._reconnect_in_progress = True
            self._reconnect_attempt_count += 1
            self._last_reconnect_epoch = now
            self._last_reconnect_at = _utc_iso_from_epoch(now)
            self._last_reconnect_reason = reason
            self._next_reconnect_at = None
            self._next_reconnect_epoch = None
            return symbols, reason

    def _reconnect_reason_locked(self) -> Optional[str]:
        if self._state == MANAGER_ERRORED:
            return "stream_error" if self._messages_observed > 0 else "start_error"
        if self._state == MANAGER_STOPPED and self._bootstrap_started_by_lifecycle:
            return "unexpected_stopped"
        # Without a market-hours utility in this project, idle is reported as a
        # diagnostic state only. This avoids off-hours reconnect loops.
        return None

    def _schedule_reconnect_locked(self, *, reason: str, from_now: bool) -> None:
        now = float(self._time_func())
        delay = max(1, int(self._reconnect_backoff_seconds or self.reconnect_initial_delay_seconds))
        self._next_reconnect_epoch = now + delay if from_now else now
        self._next_reconnect_at = _utc_iso_from_epoch(self._next_reconnect_epoch)
        self._last_reconnect_reason = reason
        self._reconnect_backoff_seconds = min(delay * 2, self.reconnect_max_delay_seconds)

    def _stop_client_for_reconnect(self) -> None:
        with self._lock:
            client = self._client
            self._client = None
            self._channels = []
            if self._state != MANAGER_DISABLED:
                self._state = MANAGER_STOPPED
        if client is not None:
            client.stop()

    def _refresh_idle_state_locked(self) -> None:
        if self._state != MANAGER_RUNNING:
            self._is_idle = False
            self._idle_since = None
            self._idle_since_epoch = None
            return
        baseline = self._last_message_epoch if self._last_message_epoch is not None else self._started_at_epoch
        if baseline is None:
            return
        now = float(self._time_func())
        is_idle = now - baseline >= self.idle_timeout_seconds
        if is_idle and not self._is_idle:
            self._idle_since_epoch = now
            self._idle_since = _utc_iso_from_epoch(now)
        if not is_idle:
            self._idle_since_epoch = None
            self._idle_since = None
        self._is_idle = is_idle

    def _runtime_status_locked(self) -> str:
        if self._shutdown_requested:
            return RUNTIME_SHUTDOWN
        if not self.enabled or self._state == MANAGER_DISABLED:
            return RUNTIME_DISABLED
        if self._reconnect_in_progress or self._next_reconnect_epoch is not None:
            return RUNTIME_RECONNECTING
        if self._state == MANAGER_STARTING:
            return RUNTIME_STARTING
        if self._state == MANAGER_RUNNING:
            return RUNTIME_RUNNING_IDLE if self._is_idle else RUNTIME_RUNNING
        if self._state == MANAGER_ERRORED:
            return RUNTIME_ERRORED
        if self._state == MANAGER_STOPPED:
            return RUNTIME_NOT_STARTED if not self._requested_symbols else RUNTIME_STOPPED
        return RUNTIME_STOPPED
