# -*- coding: utf-8 -*-
"""Safe SSI streaming realtime manager skeleton.

This module is intentionally side-effect free: importing it does not import the
official SSI streaming package, create clients, start threads, or open network
connections.
"""

from __future__ import annotations

import logging
import math
import random
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple

from data_provider.ssi_streaming_snapshot_store import SNAPSHOT_SCHEMA_VERSION, SsiStreamingSnapshotStore


logger = logging.getLogger(__name__)


SSI_STREAMING_REALTIME_DISABLED_REASON = "SSI streaming realtime manager disabled."
SSI_STREAMING_REALTIME_NOT_STARTED_REASON = "SSI streaming realtime manager not started."
SSI_STREAMING_REALTIME_CACHE_EMPTY_REASON = "SSI streaming realtime cache empty."
SSI_STREAMING_REALTIME_CACHE_STALE_REASON = "SSI streaming realtime cache stale."
SSI_STREAMING_REALTIME_MANAGER_ERROR_REASON = "SSI streaming realtime manager errored."
SSI_STREAMING_REALTIME_LIVE_ADAPTER_DISABLED_REASON = "SSI streaming realtime live adapter not enabled."
SSI_STREAMING_REALTIME_ALL_CHANNEL_FORBIDDEN_REASON = "SSI streaming realtime refuses ALL channel subscriptions."
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
DEFAULT_MARKET_INDEX_TTL_SECONDS = 5
DEFAULT_TRADE_TAPE_BUFFER_SIZE = 50
DEFAULT_TRADE_TAPE_TTL_SECONDS = 60
ORDER_BOOK_CHANNEL_PREFIX = "X-QUOTE"
FOREIGN_ROOM_CHANNEL_PREFIX = "R"
MARKET_INDEX_CHANNEL_PREFIX = "MI"
TRADE_TAPE_CHANNEL_PREFIX = "X-TRADE"
DEFAULT_SESSION_STATUS_TTL_SECONDS = 60
SESSION_STATUS_CHANNEL_PREFIX = "F"
DEFAULT_MARKET_INDEX_CODES = ("VNINDEX", "VN30", "HNX", "UPCOM")
VIETNAM_MARKET_TIMEZONE = timezone(timedelta(hours=7), "ICT")
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

TRANSPORT_STOPPED = "stopped"
TRANSPORT_CONNECTING = "connecting"
TRANSPORT_CONNECTED = "connected"
TRANSPORT_RECONNECTING = "reconnecting"
TRANSPORT_CLOSING = "closing"
TRANSPORT_CLOSED = "closed"
TRANSPORT_FAILED = "failed"

CONTEXT_DISABLED = "disabled"
CONTEXT_AWAITING_SUBSCRIPTION = "awaiting_subscription"
CONTEXT_RECOVERING = "recovering"
CONTEXT_READY = "ready"
CONTEXT_STALE = "stale"
CONTEXT_UNAVAILABLE = "unavailable"
CONTEXT_CLOSED = "closed"
CONTEXT_FAILED = "failed"

STREAM_CONTEXTS = ("x", "x_quote", "x_trade", "f", "r", "mi")
RETRYABLE_STREAM_ERROR_CLASSES = {
    "authentication",
    "authorization",
    "network_closed",
    "timeout",
    "dns",
    "tls",
    "sdk_error",
    "unknown",
}
NON_RETRYABLE_STREAM_ERROR_CLASSES = {
    "configuration",
    "entitlement_rejected",
    "subscription_failure",
}
DEFAULT_RECONNECT_BACKOFF_SEQUENCE = (2, 5, 10, 20, 30)
DEFAULT_STREAMING_RECOVERY_REQUEST_COOLDOWN_SECONDS = 5


def vietnam_market_session_from_epoch(epoch_seconds: float) -> Dict[str, Any]:
    """Return a small HOSE-like Vietnam session classifier.

    This helper is intentionally holiday-unaware. It exists only to avoid
    treating normal after-hours stream silence as a transport failure.
    """

    local_dt = datetime.fromtimestamp(float(epoch_seconds), timezone.utc).astimezone(VIETNAM_MARKET_TIMEZONE)
    minutes = local_dt.hour * 60 + local_dt.minute
    weekday = local_dt.weekday()

    def session(code: str, label: str, *, active: bool, auction: bool = False, continuous: bool = False) -> Dict[str, Any]:
        return {
            "market_session": code,
            "market_session_label": label,
            "market_session_active": active,
            "market_session_is_auction": auction,
            "market_session_is_continuous": continuous,
            "market_session_holiday_aware": False,
        }

    if weekday >= 5:
        return session("weekend_closed", "Weekend / closed", active=False)
    if minutes < 9 * 60:
        return session("pre_open", "Pre-open", active=False)
    if minutes < 9 * 60 + 15:
        return session("ato", "ATO opening auction", active=True, auction=True)
    if minutes < 11 * 60 + 30:
        return session("continuous_morning", "Continuous morning", active=True, continuous=True)
    if minutes < 13 * 60:
        return session("lunch_break", "Lunch break", active=False)
    if minutes < 14 * 60 + 30:
        return session("continuous_afternoon", "Continuous afternoon", active=True, continuous=True)
    if minutes < 14 * 60 + 45:
        return session("atc", "ATC closing auction", active=True, auction=True)
    if minutes < 15 * 60:
        return session("post_close", "Post-close", active=False)
    return session("closed", "Closed", active=False)


def vietnam_market_session_from_provider_timestamp(value: Any) -> Optional[str]:
    """Resolve event-session provenance without replacing provider time."""

    text = str(value or "").strip()
    if not text:
        return None
    parsed: Optional[datetime] = None
    if "T" in text or " " in text:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=VIETNAM_MARKET_TIMEZONE)
        except ValueError:
            for fmt in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M:%S.%f"):
                try:
                    parsed = datetime.strptime(text, fmt).replace(
                        tzinfo=VIETNAM_MARKET_TIMEZONE
                    )
                    break
                except ValueError:
                    continue
    else:
        try:
            time_part = datetime.strptime(text, "%H:%M:%S").time()
            parsed = datetime(2026, 7, 20, time_part.hour, time_part.minute, time_part.second, tzinfo=VIETNAM_MARKET_TIMEZONE)
        except ValueError:
            parsed = None
    if parsed is None:
        return None
    return str(vietnam_market_session_from_epoch(parsed.timestamp())["market_session"])


def _positive_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) and float(value) > 0

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


def _provider_timestamp_sort_key(value: Any) -> Tuple[float, str]:
    text = str(value or "").strip()
    if not text:
        return (float("-inf"), "")
    parsed: Optional[datetime] = None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        for fmt in (
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
        ):
            try:
                parsed = datetime.strptime(text, fmt).replace(
                    tzinfo=VIETNAM_MARKET_TIMEZONE
                )
                break
            except ValueError:
                continue
    if parsed is None:
        return (float("-inf"), text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=VIETNAM_MARKET_TIMEZONE)
    return (parsed.timestamp(), text)


class SsiRealtimeStreamClient(Protocol):
    """Small stream-client interface used by the background manager."""

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
        """Start streaming for symbol-scoped channels."""

    def stop(self) -> None:
        """Stop streaming idempotently."""

    def ensure_channels(self, channels: Sequence[str]) -> None:
        """Add channels to the existing shared transport without reconnecting."""


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
    session_date: str
    foreign_room: Dict[str, Any]
    received_at: float


@dataclass(frozen=True)
class CachedSessionStatus:
    symbol: str
    status: Dict[str, Any]
    received_at: float


@dataclass(frozen=True)
class CachedMarketIndexPulse:
    index_code: str
    pulse: Dict[str, Any]
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


def _copy_persisted_snapshot_metadata(target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only lifecycle-added persisted markers through cache normalizers."""
    if source.get("snapshot_source") != "persisted":
        return target
    target.update(
        {
            "snapshot_source": "persisted",
            "snapshot_captured_at": source.get("snapshot_captured_at"),
            "snapshot_trading_date": source.get("snapshot_trading_date"),
            "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
            "cache_status": "persisted_stale",
            "is_stale": True,
        }
    )
    return target


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


def build_market_index_channel(index_code: str) -> str:
    normalized = str(index_code or "").strip().upper()
    if not normalized:
        raise ValueError("Streaming index code is required.")
    if normalized == "ALL":
        raise ValueError(SSI_STREAMING_REALTIME_ALL_CHANNEL_FORBIDDEN_REASON)
    channel = f"{MARKET_INDEX_CHANNEL_PREFIX}:{normalized}"
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


def is_market_index_channel(channel: Any) -> bool:
    text = str(channel or "").strip().upper()
    return text.startswith(f"{MARKET_INDEX_CHANNEL_PREFIX}:")


def build_streaming_channels(
    symbols: Iterable[str],
    *,
    market_indexes: Optional[Iterable[str]] = None,
    realtime_template: str = DEFAULT_STREAMING_REALTIME_CHANNEL_TEMPLATE,
    order_book_enabled: bool = True,
    foreign_room_enabled: bool = True,
    trade_tape_enabled: bool = True,
    session_status_enabled: bool = True,
    market_index_enabled: bool = True,
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
    if market_index_enabled:
        for index_code in normalize_streaming_symbols(market_indexes or DEFAULT_MARKET_INDEX_CODES):
            channel = build_market_index_channel(index_code)
            if channel in seen:
                continue
            channels.append(channel)
            seen.add(channel)
    return channels


def stream_context_for_channel(channel: Any) -> Optional[str]:
    text = str(channel or "").strip().upper()
    if text.startswith(f"{ORDER_BOOK_CHANNEL_PREFIX}:"):
        return "x_quote"
    if text.startswith(f"{TRADE_TAPE_CHANNEL_PREFIX}:"):
        return "x_trade"
    if text.startswith(f"{FOREIGN_ROOM_CHANNEL_PREFIX}:"):
        return "r"
    if text.startswith(f"{SESSION_STATUS_CHANNEL_PREFIX}:"):
        return "f"
    if text.startswith(f"{MARKET_INDEX_CHANNEL_PREFIX}:"):
        return "mi"
    if text.startswith("X:"):
        return "x"
    return None


def classify_streaming_error(error: Any) -> str:
    """Map transport/provider failures to bounded, credential-safe classes."""
    if isinstance(error, TimeoutError):
        return "timeout"
    text = str(error or "").lower()
    name = type(error).__name__.lower()
    combined = f"{name} {text}"
    if any(marker in combined for marker in ("401", "unauthorized", "authentication", "invalid token")):
        return "authentication"
    if any(marker in combined for marker in ("not entitled", "entitlement rejected")):
        return "entitlement_rejected"
    if any(marker in combined for marker in ("403", "forbidden", "permission denied")):
        return "authorization"
    if any(marker in combined for marker in ("configuration incomplete", "config incomplete", "missing credential", "at least one streaming channel")):
        return "configuration"
    if any(marker in combined for marker in ("subscription", "switchchannels", "invalid channel")):
        return "subscription_failure"
    if any(marker in combined for marker in ("certificate", "ssl", "tls")):
        return "tls"
    if any(marker in combined for marker in ("name or service not known", "getaddrinfo", "dns")):
        return "dns"
    if any(marker in combined for marker in ("timeout", "timed out")):
        return "timeout"
    if any(marker in combined for marker in ("connection closed", "connection lost", "remote host", "websocketconnectionclosed", "broken pipe", "connection reset")):
        return "network_closed"
    if isinstance(error, (ConnectionError, OSError)):
        return "network_closed"
    if "shutdown" in combined or "stopped" in combined:
        return "shutdown"
    if isinstance(error, Exception):
        return "sdk_error"
    return "unknown"


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
                price = row.get("snapshot_price", row.get("realtime_price", row.get("price")))
                last_volume = row.get("last_volume")
                claimed_trade = "has_last_trade" in row or "trade_message_classification" in row
                if (
                    not symbol
                    or not _positive_finite_number(price)
                    or (
                        claimed_trade
                        and (
                            not row.get("has_last_trade")
                            or not _positive_finite_number(last_volume)
                            or not str(row.get("stream_timestamp") or "").strip()
                        )
                    )
                ):
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
            snapshot["is_stale"] = snapshot.get("snapshot_source") == "persisted" or age_seconds > self.ttl_seconds
            if snapshot["is_stale"]:
                snapshot["stale_reason"] = SSI_STREAMING_REALTIME_CACHE_STALE_REASON
                return snapshot, "persisted_stale" if snapshot.get("snapshot_source") == "persisted" else "stale", age_seconds
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
            elif status in {"stale", "persisted_stale"}:
                stale_symbols.append(symbol)
                if row is not None:
                    rows.append(row)
            else:
                empty_symbols.append(symbol)
        return {
            "rows": rows,
            "hit_count": sum(not bool(row.get("is_stale")) for row in rows),
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
        self._dedup_keys: Dict[str, set[Tuple[Any, ...]]] = {}

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()
            self._dedup_keys.clear()

    @staticmethod
    def _dedup_key(trade: Dict[str, Any]) -> Optional[Tuple[Any, ...]]:
        sequence = trade.get("sequence_if_available") or trade.get("sequence") or trade.get("id")
        if sequence not in (None, ""):
            return ("sequence", str(sequence))
        return None

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
                if not symbol or not _positive_finite_number(price) or not _positive_finite_number(volume) or not timestamp:
                    continue
                trade = dict(row)
                trade["ticker"] = symbol
                trade.setdefault("symbol", symbol)
                trade["cached_at"] = _utc_iso_from_epoch(now)
                trade["cache_ttl_seconds"] = self.ttl_seconds
                events = self._rows.setdefault(symbol, [])
                dedup_key = self._dedup_key(trade)
                keys = self._dedup_keys.setdefault(symbol, set())
                if dedup_key is not None and dedup_key in keys:
                    continue
                events.insert(0, CachedTradeTapeEvent(symbol=symbol, trade=trade, received_at=now))
                del events[self.max_rows_per_symbol :]
                keys.clear()
                keys.update(key for event in events if (key := self._dedup_key(event.trade)) is not None)
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
            trade["is_stale"] = trade.get("snapshot_source") == "persisted" or age_seconds > self.ttl_seconds
            if trade.get("snapshot_source") == "persisted":
                trade["cache_status"] = "persisted_stale"
            rows.append(trade)

        newest_age = max(0.0, now - events[0].received_at)
        latest_trade_timestamp = max(
            (
                event.trade.get("timestamp")
                for event in events[:safe_limit]
                if event.trade.get("timestamp")
            ),
            key=_provider_timestamp_sort_key,
            default=None,
        )
        persisted_only = bool(events) and all(event.trade.get("snapshot_source") == "persisted" for event in events[:safe_limit])
        return {
            "rows": rows,
            "status": "persisted_stale" if persisted_only else "stale" if newest_age > self.ttl_seconds else "hit",
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
        row["is_stale"] = row.get("snapshot_source") == "persisted" or age_seconds > self.ttl_seconds
        if row["is_stale"]:
            row["stale_reason"] = SSI_STREAMING_REALTIME_CACHE_STALE_REASON
        return {
            "status": "persisted_stale" if row.get("snapshot_source") == "persisted" else "stale" if row["is_stale"] else "hit",
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
        return _copy_persisted_snapshot_metadata({
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
        }, row)

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
    """Thread-safe replacement snapshots keyed by VN ticker and session."""

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_FOREIGN_ROOM_TTL_SECONDS,
        *,
        time_func: Callable[[], float] = time.time,
    ) -> None:
        self.ttl_seconds = max(1, int(ttl_seconds or DEFAULT_FOREIGN_ROOM_TTL_SECONDS))
        self._time_func = time_func
        self._lock = threading.RLock()
        self._rows: Dict[Tuple[str, str], CachedForeignRoom] = {}
        self._latest_session_by_symbol: Dict[str, str] = {}

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()
            self._latest_session_by_symbol.clear()

    def put_rows(self, rows: Iterable[Dict[str, Any]]) -> int:
        now = float(self._time_func())
        written = 0
        with self._lock:
            for row in rows or []:
                foreign_room = self._normalize_foreign_room(row, now)
                if not foreign_room:
                    continue
                symbol = str(foreign_room.get("ticker") or foreign_room.get("symbol") or "").strip().upper()
                session_date = str(foreign_room.get("provider_session_date") or "").strip()
                if not session_date:
                    continue
                self._rows[(symbol, session_date)] = CachedForeignRoom(
                    symbol=symbol,
                    session_date=session_date,
                    foreign_room=foreign_room,
                    received_at=now,
                )
                self._latest_session_by_symbol[symbol] = max(
                    session_date,
                    self._latest_session_by_symbol.get(symbol, session_date),
                )
                written += 1
        return written

    def get(self, symbol: str, session_date: Optional[str] = None) -> Dict[str, Any]:
        normalized = str(symbol or "").strip().upper()
        now = float(self._time_func())
        with self._lock:
            requested_session = str(session_date or "").strip()
            resolved_session = (
                requested_session
                or self._latest_session_by_symbol.get(normalized)
                or ""
            )
            entry = self._rows.get((normalized, resolved_session))

        if entry is None:
            return {
                "status": "empty",
                "row": None,
                "session_date": requested_session or None,
                "latest_foreign_room_timestamp": None,
                "latest_foreign_room_age_seconds": None,
            }

        age_seconds = max(0.0, now - entry.received_at)
        row = dict(entry.foreign_room)
        row["age_seconds"] = int(age_seconds)
        row["is_stale"] = row.get("snapshot_source") == "persisted" or age_seconds > self.ttl_seconds
        if row["is_stale"]:
            row["stale_reason"] = SSI_STREAMING_REALTIME_CACHE_STALE_REASON
        return {
            "status": "persisted_stale" if row.get("snapshot_source") == "persisted" else "stale" if row["is_stale"] else "hit",
            "row": row,
            "session_date": entry.session_date,
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

        provider_session_date = self._safe_text(
            self._first_value(
                row,
                "provider_session_date",
                "trading_date",
                "TradingDate",
                "snapshot_trading_date",
            )
        )
        if not provider_session_date:
            return None
        cached_at = _utc_iso_from_epoch(now)
        foreign_room = {
            "ticker": symbol,
            "symbol": symbol,
            "exchange": self._safe_text(self._first_value(row, "exchange", "Exchange", "Market", "market")),
            "trading_date": provider_session_date,
            "provider_session_date": provider_session_date,
            "session_date_source": self._safe_text(
                self._first_value(row, "session_date_source")
            )
            or "unknown",
            "time": self._safe_text(self._first_value(row, "time", "Time", "TradingTime", "tradingTime")),
            "stream_timestamp": self._safe_text(self._first_value(row, "stream_timestamp", "streamTimestamp")),
            "stream_data_type": FOREIGN_ROOM_CHANNEL_PREFIX,
            "r_type": self._safe_text(self._first_value(row, "r_type", "RType", "rtype")) or FOREIGN_ROOM_CHANNEL_PREFIX,
            "source": "SSI FastConnect V3 ForeignRoomMessage",
            "received_at": cached_at,
            "cached_at": cached_at,
            "cache_ttl_seconds": self.ttl_seconds,
            "update_semantics": "cumulative_replacement_snapshot",
            "value_semantics_status": "provisional_current_session",
            "finality": "current_session_provisional",
            "raw_field_presence": dict(row.get("raw_field_presence") or {}),
        }
        foreign_room.update(numeric_fields)
        foreign_room["foreign_net_volume"] = (
            numeric_fields["foreign_buy_volume"] - numeric_fields["foreign_sell_volume"]
            if numeric_fields["foreign_buy_volume"] is not None
            and numeric_fields["foreign_sell_volume"] is not None
            else None
        )
        foreign_room["foreign_net_value"] = (
            numeric_fields["foreign_buy_value"] - numeric_fields["foreign_sell_value"]
            if numeric_fields["foreign_buy_value"] is not None
            and numeric_fields["foreign_sell_value"] is not None
            else None
        )
        return _copy_persisted_snapshot_metadata(foreign_room, row)

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


class MarketIndexPulseCache:
    """Thread-safe latest MI market-index pulse cache keyed by index code."""

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_MARKET_INDEX_TTL_SECONDS,
        *,
        time_func: Callable[[], float] = time.time,
    ) -> None:
        self.ttl_seconds = max(1, int(ttl_seconds or DEFAULT_MARKET_INDEX_TTL_SECONDS))
        self._time_func = time_func
        self._lock = threading.RLock()
        self._rows: Dict[str, CachedMarketIndexPulse] = {}

    def clear(self) -> None:
        with self._lock:
            self._rows.clear()

    def put_rows(self, rows: Iterable[Dict[str, Any]]) -> int:
        now = float(self._time_func())
        written = 0
        with self._lock:
            for row in rows or []:
                pulse = self._normalize_market_index(row, now)
                if not pulse:
                    continue
                index_code = str(pulse.get("index_code") or "").strip().upper()
                self._rows[index_code] = CachedMarketIndexPulse(
                    index_code=index_code,
                    pulse=pulse,
                    received_at=now,
                )
                written += 1
        return written

    def get_many(self, index_codes: Iterable[str]) -> Dict[str, Any]:
        requested = normalize_streaming_symbols(index_codes)
        now = float(self._time_func())
        rows: List[Dict[str, Any]] = []
        stale_rows: List[Dict[str, Any]] = []
        latest_timestamp = None
        latest_age_seconds = None
        with self._lock:
            entries = {code: self._rows.get(code) for code in requested}

        for code in requested:
            entry = entries.get(code)
            if entry is None:
                continue
            age_seconds = max(0.0, now - entry.received_at)
            row = dict(entry.pulse)
            row["age_seconds"] = int(age_seconds)
            row["is_stale"] = row.get("snapshot_source") == "persisted" or age_seconds > self.ttl_seconds
            if row.get("snapshot_source") == "persisted":
                rows.append(row)
            elif row["is_stale"]:
                row["stale_reason"] = SSI_STREAMING_REALTIME_CACHE_STALE_REASON
                stale_rows.append(row)
            else:
                rows.append(row)
            if latest_age_seconds is None or age_seconds < latest_age_seconds:
                latest_age_seconds = int(age_seconds)
                latest_timestamp = row.get("stream_timestamp") or row.get("time")

        if rows:
            status = "persisted_stale" if all(row.get("snapshot_source") == "persisted" for row in rows) else "hit"
        elif stale_rows:
            status = "stale"
        else:
            status = "empty"
        return {
            "status": status,
            "rows": rows,
            "stale_rows": stale_rows,
            "latest_market_index_timestamp": latest_timestamp,
            "latest_market_index_age_seconds": latest_age_seconds,
        }

    def _normalize_market_index(self, row: Any, now: float) -> Optional[Dict[str, Any]]:
        if not isinstance(row, dict):
            return None
        index_code = str(
            self._first_value(row, "index_code", "IndexCode", "IndexId", "IndexID", "Code")
            or ""
        ).strip().upper()
        if not index_code:
            return None

        def signed(value: Any) -> Optional[float]:
            return self._to_float(value)

        def nonnegative(value: Any) -> Optional[float]:
            number = self._to_float(value)
            if number is None or number < 0:
                return None
            return number

        numeric_fields = {
            "index_value": nonnegative(self._first_value(row, "index_value", "IndexValue", "IndexVal")),
            "estimated_index_value": nonnegative(
                self._first_value(row, "estimated_index_value", "IndexValEst", "EstimatedIndexValue")
            ),
            "change": signed(self._first_value(row, "change", "Change")),
            "change_pct": signed(self._first_value(row, "change_pct", "RatioChange")),
            "total_trades": nonnegative(self._first_value(row, "total_trades", "TotalTrade")),
            "total_volume": nonnegative(self._first_value(row, "total_volume", "TotalQtty", "TotalVolume")),
            "total_value": nonnegative(self._first_value(row, "total_value", "TotalValue")),
            "advances": nonnegative(self._first_value(row, "advances", "Advances")),
            "unchanged": nonnegative(self._first_value(row, "unchanged", "Nochanges", "NoChanges")),
            "declines": nonnegative(self._first_value(row, "declines", "Declines")),
        }
        if not any(value is not None for value in numeric_fields.values()):
            return None

        cached_at = _utc_iso_from_epoch(now)
        pulse = {
            "index_code": index_code,
            "exchange": self._safe_text(self._first_value(row, "exchange", "Exchange", "Market", "market")),
            "trading_date": self._safe_text(
                self._first_value(row, "trading_date", "TradingDate", "Date", "date")
            ),
            "time": self._safe_text(self._first_value(row, "time", "Time", "TradingTime", "tradingTime")),
            "stream_timestamp": self._safe_text(self._first_value(row, "stream_timestamp", "streamTimestamp")),
            "stream_data_type": MARKET_INDEX_CHANNEL_PREFIX,
            "r_type": self._safe_text(self._first_value(row, "r_type", "RType", "rtype")) or MARKET_INDEX_CHANNEL_PREFIX,
            "source": "SSI MI market-index stream",
            "received_at": cached_at,
            "cached_at": cached_at,
            "cache_ttl_seconds": self.ttl_seconds,
            "channel_format_status": "needs_live_proof",
            "value_semantics_status": "needs_live_proof",
        }
        pulse.update(numeric_fields)
        return _copy_persisted_snapshot_metadata(pulse, row)

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
        row["is_stale"] = row.get("snapshot_source") == "persisted" or age_seconds > self.ttl_seconds
        if row["is_stale"]:
            row["stale_reason"] = SSI_STREAMING_REALTIME_CACHE_STALE_REASON
        return {
            "status": "persisted_stale" if row.get("snapshot_source") == "persisted" else "stale" if row["is_stale"] else "hit",
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
        market_index_cache: Optional[MarketIndexPulseCache] = None,
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
        market_index_enabled: bool = True,
        market_index_codes: Optional[Iterable[str]] = None,
        trade_tape_enabled: bool = True,
        session_status_enabled: bool = True,
        snapshot_store: Optional[SsiStreamingSnapshotStore] = None,
        time_func: Callable[[], float] = time.time,
        jitter_func: Optional[Callable[[float], float]] = None,
    ) -> None:
        self.enabled = bool(enabled)
        self.cache = cache or RealtimeSnapshotCache(time_func=time_func)
        self.order_book_cache = order_book_cache or OrderBookCache(time_func=time_func)
        self.foreign_room_cache = foreign_room_cache or ForeignRoomCache(time_func=time_func)
        self.market_index_cache = market_index_cache or MarketIndexPulseCache(time_func=time_func)
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
        self.market_index_enabled = bool(market_index_enabled)
        self.market_index_codes = normalize_streaming_symbols(market_index_codes or DEFAULT_MARKET_INDEX_CODES)
        self.trade_tape_enabled = bool(trade_tape_enabled)
        self.session_status_enabled = bool(session_status_enabled)
        self._snapshot_store = snapshot_store
        self._time_func = time_func
        self._jitter_func = jitter_func or (lambda delay: random.uniform(-0.2 * delay, 0.2 * delay))
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
        self._market_index_rows_observed = 0
        self._trade_rows_observed = 0
        self._raw_trade_messages_observed = 0
        self._valid_trade_rows_observed = 0
        self._zero_price_trade_rows_dropped = 0
        self._zero_volume_trade_rows_dropped = 0
        self._non_trade_messages_dropped = 0
        self._malformed_trade_rows_dropped = 0
        self._missing_timestamp_rows_dropped = 0
        self._last_raw_trade_message_at: Optional[str] = None
        self._last_valid_trade_at: Optional[str] = None
        self._symbol_trade_health: Dict[str, str] = {}
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
        self._transport_state = TRANSPORT_STOPPED if self.enabled else TRANSPORT_CLOSED
        self._connected = False
        self._generation = 0
        self._start_count = 0
        self._connect_count = 0
        self._disconnect_count = 0
        self._reconnect_scheduled_count = 0
        self._reconnect_tasks_created = 0
        self._reconnect_success_count = 0
        self._reconnect_failure_count = 0
        self._current_reconnect_attempt_number = 0
        self._stale_generation_callbacks_ignored = 0
        self._subscription_restore_attempt_count = 0
        self._subscription_restore_success_count = 0
        self._subscription_restore_failure_count = 0
        self._readiness_transition_count = 0
        self._shutdown_count = 0
        self._last_connected_at: Optional[str] = None
        self._last_disconnected_at: Optional[str] = None
        self._last_transition_at: Optional[str] = None
        self._last_error_class: Optional[str] = None
        self._retry_blocked = False
        self._recovery_request_cooldown_seconds = max(
            float(DEFAULT_STREAMING_RECOVERY_REQUEST_COOLDOWN_SECONDS),
            float(self.reconnect_initial_delay_seconds),
        )
        self._recovery_request_count = 0
        self._recovery_request_suppressed_count = 0
        self._last_recovery_request_at: Optional[str] = None
        self._last_recovery_request_epoch: Optional[float] = None
        self._last_recovery_trigger: Optional[str] = None
        self._opened_channels: set[str] = set()
        self._suppressed_close_generations: set[int] = set()
        self._reconnect_success_generations: set[int] = set()
        self._session_date = self._vietnam_date_from_epoch(float(self._time_func()))
        self._backoff_sequence = self._build_backoff_sequence()
        self._backoff_index = 0
        self._context_lifecycle = self._initial_context_lifecycle()

    def _initial_context_lifecycle(self) -> Dict[str, Dict[str, Any]]:
        enabled = {
            "x": True,
            "x_quote": self.order_book_enabled,
            "x_trade": self.trade_tape_enabled,
            "f": self.session_status_enabled,
            "r": self.foreign_room_enabled,
            "mi": self.market_index_enabled,
        }
        return {
            context: {
                "state": CONTEXT_UNAVAILABLE if is_enabled else CONTEXT_DISABLED,
                "enabled": is_enabled,
                "subscribed_generation": None,
                "last_event_generation": None,
                "last_event_at": None,
                "last_event_epoch": None,
                "last_fresh_event_at": None,
                "accepted_event_count": 0,
                "ignored_old_generation_event_count": 0,
                "subscription_restoration_count": 0,
                "subscription_failure_count": 0,
                "stale_reason": None,
                "last_error_class": None,
            }
            for context, is_enabled in enabled.items()
        }

    def _build_backoff_sequence(self) -> Tuple[float, ...]:
        candidates = (self.reconnect_initial_delay_seconds, 5, 10, 20, self.reconnect_max_delay_seconds)
        sequence: List[float] = []
        for value in candidates:
            delay = float(min(max(self.reconnect_initial_delay_seconds, value), self.reconnect_max_delay_seconds))
            if not sequence or delay > sequence[-1]:
                sequence.append(delay)
        return tuple(sequence or [float(self.reconnect_initial_delay_seconds)])

    @staticmethod
    def _vietnam_date_from_epoch(epoch_seconds: float) -> str:
        return datetime.fromtimestamp(epoch_seconds, timezone.utc).astimezone(VIETNAM_MARKET_TIMEZONE).date().isoformat()

    @staticmethod
    def _event_trading_date(row: Dict[str, Any]) -> Optional[str]:
        value = (
            row.get("trading_date")
            or row.get("TradingDate")
            or row.get("provider_session_date")
            or row.get("date")
            or row.get("stream_timestamp")
        )
        text = str(value or "").strip()
        if not text:
            return None
        for fmt in ("%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(text[:10], fmt).date().isoformat()
            except ValueError:
                continue
        return None

    def _transition_transport_locked(self, state: str) -> None:
        if self._transport_state == state:
            return
        self._transport_state = state
        self._last_transition_at = _utc_iso_from_epoch(float(self._time_func()))

    def _transition_context_locked(self, context: str, state: str, *, stale_reason: Optional[str] = None) -> None:
        lifecycle = self._context_lifecycle.get(context)
        if lifecycle is None or not lifecycle["enabled"]:
            return
        if lifecycle["state"] != state:
            lifecycle["state"] = state
            self._readiness_transition_count += 1
        lifecycle["stale_reason"] = stale_reason

    def _reset_contexts_for_generation_locked(self, generation: int, channels: Sequence[str]) -> None:
        self._opened_channels.clear()
        contexts_present = {stream_context_for_channel(channel) for channel in channels}
        for context, lifecycle in self._context_lifecycle.items():
            if not lifecycle["enabled"]:
                lifecycle["state"] = CONTEXT_DISABLED
                continue
            lifecycle["subscribed_generation"] = None
            lifecycle["last_error_class"] = None
            if context in contexts_present:
                self._transition_context_locked(context, CONTEXT_AWAITING_SUBSCRIPTION)
            else:
                self._transition_context_locked(context, CONTEXT_UNAVAILABLE, stale_reason="not_subscribed")

    def _ignore_stale_callback_locked(self, generation: int, *, context: Optional[str] = None) -> None:
        self._stale_generation_callbacks_ignored += 1
        if context and context in self._context_lifecycle:
            self._context_lifecycle[context]["ignored_old_generation_event_count"] += 1

    def _context_channels_locked(self, context: str) -> List[str]:
        return [channel for channel in self._channels if stream_context_for_channel(channel) == context]

    def _mark_context_subscription_open_locked(self, context: str) -> None:
        lifecycle = self._context_lifecycle[context]
        expected = self._context_channels_locked(context)
        opened = [channel for channel in expected if channel in self._opened_channels]
        if expected and len(opened) == len(expected):
            if lifecycle["subscribed_generation"] != self._generation:
                lifecycle["subscribed_generation"] = self._generation
                lifecycle["subscription_restoration_count"] += 1
                self._subscription_restore_success_count += len(expected)
            self._transition_context_locked(context, CONTEXT_RECOVERING)

    def _mark_legacy_client_started_locked(self) -> None:
        """Record best available evidence for old test/client interfaces."""
        self._connected = True
        self._connect_count += 1
        self._last_connected_at = _utc_iso_from_epoch(float(self._time_func()))
        self._transition_transport_locked(TRANSPORT_CONNECTED)
        self._opened_channels.update(self._channels)
        for context in STREAM_CONTEXTS:
            self._mark_context_subscription_open_locked(context)

    def set_snapshot_store(self, store: Optional[SsiStreamingSnapshotStore]) -> None:
        """Attach the lifecycle-owned store; request handlers never call it."""
        with self._lock:
            self._snapshot_store = store

    def restore_persisted_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, int]:
        """Restore validated rows into empty process-local caches as persisted stale data."""
        contexts = snapshot.get("contexts") if isinstance(snapshot, dict) else None
        if not isinstance(contexts, dict):
            return {"realtime": 0, "order_book": 0, "trades": 0, "foreign_room": 0, "market_index": 0, "session": 0}
        metadata = {
            "snapshot_source": "persisted",
            "snapshot_captured_at": snapshot.get("captured_at"),
            "snapshot_trading_date": snapshot.get("trading_date"),
            "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
            "is_stale": True,
            "cache_status": "persisted_stale",
        }
        restored = {"realtime": 0, "order_book": 0, "trades": 0, "foreign_room": 0, "market_index": 0, "session": 0}
        for key, row in (contexts.get("realtime") or {}).items():
            if self.cache.get(key)[0] is None and isinstance(row, dict):
                restored["realtime"] += self.cache.put_rows([{**row, **metadata}])
        for key, row in (contexts.get("order_book") or {}).items():
            if self.order_book_cache.get(key).get("row") is None and isinstance(row, dict):
                restored["order_book"] += self.order_book_cache.put_rows([{**row, **metadata}])
        for key, rows in (contexts.get("trades") or {}).items():
            if not self.trade_tape_cache.get(key, 1).get("rows") and isinstance(rows, list):
                restored["trades"] += self.trade_tape_cache.put_rows([{**row, **metadata} for row in rows if isinstance(row, dict)])
        for key, row in (contexts.get("foreign_room") or {}).items():
            if self.foreign_room_cache.get(key).get("row") is None and isinstance(row, dict):
                restored["foreign_room"] += self.foreign_room_cache.put_rows([{**row, **metadata}])
        for key, row in (contexts.get("market_index") or {}).items():
            if not self.market_index_cache.get_many([key]).get("rows") and isinstance(row, dict):
                restored["market_index"] += self.market_index_cache.put_rows([{**row, **metadata}])
        for key, row in (contexts.get("session") or {}).items():
            if self.session_status_cache.get(key).get("row") is None and isinstance(row, dict):
                restored["session"] += self.session_status_cache.put_rows([{**row, **metadata}])
        return restored

    def flush_streaming_snapshot_if_due(self) -> bool:
        store = self._snapshot_store
        return bool(store and store.flush_if_due(self._snapshot_contexts))

    def flush_streaming_snapshot_now(self) -> bool:
        store = self._snapshot_store
        return bool(store and store.flush_now(self._snapshot_contexts))

    def close_streaming_snapshot_store(self) -> bool:
        store = self._snapshot_store
        return bool(store and store.close(self._snapshot_contexts))

    def _snapshot_contexts(self) -> Dict[str, Any]:
        with self._lock:
            symbols = list(self._requested_symbols or self._bootstrap_symbols)
            indexes = list(self.market_index_codes)
        contexts: Dict[str, Any] = {"realtime": {}, "order_book": {}, "trades": {}, "foreign_room": {}, "market_index": {}, "session": {}}
        for symbol in symbols:
            realtime, _, _ = self.cache.get(symbol)
            if realtime:
                contexts["realtime"][symbol] = realtime
            order_book = self.order_book_cache.get(symbol).get("row")
            if order_book:
                contexts["order_book"][symbol] = order_book
            trades = self.trade_tape_cache.get(symbol, self.trade_tape_cache.max_rows_per_symbol).get("rows") or []
            if trades:
                contexts["trades"][symbol] = trades
            foreign_room = self.foreign_room_cache.get(symbol).get("row")
            if foreign_room:
                contexts["foreign_room"][symbol] = foreign_room
            session = self.session_status_cache.get(symbol).get("row")
            if session:
                contexts["session"][symbol] = session
        for index_code in indexes:
            rows = self.market_index_cache.get_many([index_code]).get("rows") or []
            if rows:
                contexts["market_index"][index_code] = rows[0]
        return contexts

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def start(self, symbols: Iterable[str]) -> Dict[str, Any]:
        normalized_symbols = normalize_streaming_symbols(symbols)
        with self._lock:
            if not self.enabled:
                self._state = MANAGER_DISABLED
                self._transition_transport_locked(TRANSPORT_CLOSED)
                return self.status()
            if self._shutdown_requested:
                return self.status()
            if self._client is not None and self._state in {MANAGER_STARTING, MANAGER_RUNNING}:
                return self.status()

        try:
            channels = build_streaming_channels(
                normalized_symbols,
                market_indexes=self.market_index_codes,
                realtime_template=self.channel_template,
                order_book_enabled=self.order_book_enabled,
                foreign_room_enabled=self.foreign_room_enabled,
                trade_tape_enabled=self.trade_tape_enabled,
                session_status_enabled=self.session_status_enabled,
                market_index_enabled=self.market_index_enabled,
            )
            if not channels:
                raise ValueError("At least one streaming symbol is required.")
            if self._client_factory is None:
                raise RuntimeError(SSI_STREAMING_REALTIME_LIVE_ADAPTER_DISABLED_REASON)
            with self._lock:
                if self._shutdown_requested:
                    return self.status()
                self._generation += 1
                generation = self._generation
                self._start_count += 1
                self._state = MANAGER_STARTING
                self._requested_symbols = normalized_symbols
                self._channels = list(channels)
                self._connected = False
                self._retry_blocked = False
                self._transition_transport_locked(
                    TRANSPORT_RECONNECTING if generation > 1 else TRANSPORT_CONNECTING
                )
                self._reset_contexts_for_generation_locked(generation, channels)
                self._subscription_restore_attempt_count += len(channels)
            logger.info(
                "vn_stream_start transport=ssi_market_data_channel_cohort generation=%s subscription_count=%s",
                generation,
                len(channels),
            )
            client = self._client_factory()
            used_lifecycle_callbacks = True
            try:
                client.start(
                    lambda message, owned_generation=generation: self.handle_message(
                        message,
                        generation=owned_generation,
                    ),
                    lambda error, owned_generation=generation: self.handle_error(
                        error,
                        generation=owned_generation,
                    ),
                    channels,
                    on_open=lambda channel, owned_generation=generation: self.handle_transport_open(
                        channel,
                        generation=owned_generation,
                    ),
                    on_close=lambda channel, owned_generation=generation: self.handle_transport_close(
                        channel,
                        generation=owned_generation,
                    ),
                    on_subscription_error=lambda channel, error, owned_generation=generation: self.handle_subscription_error(
                        channel,
                        error,
                        generation=owned_generation,
                    ),
                )
            except TypeError as exc:
                if "unexpected keyword" not in str(exc) and "positional argument" not in str(exc):
                    raise
                used_lifecycle_callbacks = False
                client.start(
                    lambda message, owned_generation=generation: self.handle_message(
                        message,
                        generation=owned_generation,
                    ),
                    lambda error, owned_generation=generation: self.handle_error(
                        error,
                        generation=owned_generation,
                    ),
                    channels,
                )
        except Exception as exc:
            self._record_error(exc, set_errored=True)
            error_class = classify_streaming_error(exc)
            with self._lock:
                if error_class in NON_RETRYABLE_STREAM_ERROR_CLASSES:
                    self._retry_blocked = True
                    for context, lifecycle in self._context_lifecycle.items():
                        if lifecycle["enabled"]:
                            lifecycle["last_error_class"] = error_class
                            self._transition_context_locked(context, CONTEXT_FAILED, stale_reason=error_class)
            return self.status()

        with self._lock:
            if self._shutdown_requested:
                stop_after_start = True
            else:
                stop_after_start = False
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
                self._last_reconnect_error = None
                if not used_lifecycle_callbacks:
                    self._mark_legacy_client_started_locked()
        if stop_after_start:
            try:
                client.stop()
            except Exception as exc:  # pragma: no cover - defensive shutdown path
                self._record_error(exc, set_errored=False)
        return self.status()

    def ensure_symbol_subscription(
        self,
        symbol: str,
        *,
        recovery_trigger: str = "route_touch",
    ) -> Dict[str, Any]:
        """Idempotently add one symbol to the lifecycle-owned stream cohort."""

        result = self.ensure_symbol_subscriptions(
            [symbol],
            recovery_trigger=recovery_trigger,
        )
        symbols = list(result.get("symbols") or [])
        return {
            **result,
            "symbol": symbols[0] if symbols else None,
            "subscription_added": bool(result.get("subscription_added_count")),
        }

    def ensure_symbol_subscriptions(
        self,
        symbols: Iterable[str],
        *,
        recovery_trigger: str = "route_touch",
    ) -> Dict[str, Any]:
        """Idempotently extend the shared transport with one bounded symbol cohort."""

        normalized_symbols = normalize_streaming_symbols(symbols)
        if not normalized_symbols:
            return {
                "status": "unavailable",
                "symbols": [],
                "subscription_added_count": 0,
                "reason": "A valid symbol is required.",
            }
        with self._lock:
            if (
                self._shutdown_requested
                or self._state != MANAGER_RUNNING
                or not self._connected
                or self._client is None
            ):
                if (
                    not self._shutdown_requested
                ):
                    # Record the cohort before recovery so the lifecycle-owned
                    # rebuild restores every requested symbol in one transport.
                    for requested_symbol in normalized_symbols:
                        if requested_symbol not in self._requested_symbols:
                            self._requested_symbols.append(requested_symbol)
                recovery = self.request_recovery(trigger=recovery_trigger)
                return {
                    "status": "unavailable",
                    "symbols": normalized_symbols,
                    "subscription_added_count": 0,
                    "reason": "The shared SSI streaming transport is not connected.",
                    "recovery_requested": bool(recovery.get("recovery_requested")),
                    "recovery_status": recovery.get("status"),
                }
            pending_symbols = [
                symbol
                for symbol in normalized_symbols
                if symbol not in self._requested_symbols
            ]
            if not pending_symbols:
                return {
                    "status": "ok",
                    "symbols": normalized_symbols,
                    "subscription_added_count": 0,
                    "reason": None,
                }
            ensure_channels = getattr(self._client, "ensure_channels", None)
            if not callable(ensure_channels):
                return {
                    "status": "unavailable",
                    "symbols": normalized_symbols,
                    "subscription_added_count": 0,
                    "reason": "The active SSI streaming client cannot extend its subscription.",
                }

            pending_symbol_channels = build_streaming_channels(
                pending_symbols,
                realtime_template=self.channel_template,
                order_book_enabled=self.order_book_enabled,
                foreign_room_enabled=self.foreign_room_enabled,
                trade_tape_enabled=self.trade_tape_enabled,
                session_status_enabled=self.session_status_enabled,
                market_index_enabled=False,
            )
            pending_channels = [
                channel
                for channel in pending_symbol_channels
                if channel not in self._channels
            ]
            try:
                ensure_channels(pending_channels)
            except Exception as exc:  # noqa: BLE001 - retain typed degradation.
                safe_error = sanitize_streaming_error(exc)
                logger.warning(
                    "vn_stream_symbol_subscription_failed symbol_count=%s error=%s",
                    len(pending_symbols),
                    safe_error,
                )
                return {
                    "status": "unavailable",
                    "symbols": normalized_symbols,
                    "subscription_added_count": 0,
                    "reason": safe_error,
                }

            self._requested_symbols.extend(pending_symbols)
            self._channels.extend(pending_channels)
            self._opened_channels.update(pending_channels)
            self._subscription_restore_attempt_count += len(pending_channels)
            for context in {
                stream_context_for_channel(channel)
                for channel in pending_channels
            }:
                if context:
                    self._mark_context_subscription_open_locked(context)
            return {
                "status": "ok",
                "symbols": normalized_symbols,
                "subscription_added_count": len(pending_symbols),
                "reason": None,
            }

    def request_recovery(self, *, trigger: str = "route_touch") -> Dict[str, Any]:
        """Schedule one lifecycle-owned reconnect with single-flight cooldown."""

        safe_trigger = str(trigger or "route_touch").strip()[:64] or "route_touch"
        with self._lock:
            if not self.enabled:
                return {"status": "disabled", "recovery_requested": False}
            if self._shutdown_requested:
                return {"status": "shutdown", "recovery_requested": False}
            if not self.reconnect_enabled:
                return {"status": "reconnect_disabled", "recovery_requested": False}
            if (
                self._state == MANAGER_RUNNING
                and self._connected
                and self._client is not None
                and self._transport_state == TRANSPORT_CONNECTED
            ):
                return {"status": "connected", "recovery_requested": False}
            symbols = list(self._requested_symbols or self._bootstrap_symbols)
            if not symbols:
                return {"status": "symbols_empty", "recovery_requested": False}
            if self._last_error_class in NON_RETRYABLE_STREAM_ERROR_CLASSES:
                return {
                    "status": "non_retryable",
                    "recovery_requested": False,
                    "failure_class": self._last_error_class,
                }
            if self._reconnect_in_progress or self._next_reconnect_epoch is not None:
                self._recovery_request_suppressed_count += 1
                return {"status": "already_scheduled", "recovery_requested": False}

            now = float(self._time_func())
            cooldown_until = (
                float(self._last_recovery_request_epoch)
                + self._recovery_request_cooldown_seconds
                if self._last_recovery_request_epoch is not None
                else now
            )
            self._retry_blocked = False
            self._recovery_request_count += 1
            self._last_recovery_request_epoch = now
            self._last_recovery_request_at = _utc_iso_from_epoch(now)
            self._last_recovery_trigger = safe_trigger
            self._last_reconnect_reason = safe_trigger
            if cooldown_until > now:
                self._next_reconnect_epoch = cooldown_until
                self._next_reconnect_at = _utc_iso_from_epoch(cooldown_until)
                self._reconnect_scheduled_count += 1
                self._reconnect_tasks_created += 1
                self._transition_transport_locked(TRANSPORT_RECONNECTING)
            else:
                self._schedule_reconnect_locked(reason=safe_trigger, from_now=False)
            return {
                "status": "scheduled",
                "recovery_requested": True,
                "next_reconnect_at": self._next_reconnect_at,
            }

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
            self._suppressed_close_generations.add(self._generation)
            self._transition_transport_locked(TRANSPORT_CLOSING)
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
            self._connected = False
            self._transition_transport_locked(TRANSPORT_CLOSED if self._shutdown_requested else TRANSPORT_STOPPED)
            for context, lifecycle in self._context_lifecycle.items():
                if lifecycle["enabled"]:
                    self._transition_context_locked(
                        context,
                        CONTEXT_CLOSED if self._shutdown_requested else CONTEXT_STALE,
                        stale_reason="shutdown" if self._shutdown_requested else "stopped",
                    )
            return self.status()

    def handle_message(self, message: Any, *, generation: Optional[int] = None) -> None:
        with self._lock:
            owned_generation = self._generation if generation is None else int(generation)
            if owned_generation != self._generation or self._shutdown_requested:
                self._ignore_stale_callback_locked(owned_generation)
                return
            if self._state not in {MANAGER_STARTING, MANAGER_RUNNING}:
                return
            requested_symbols = list(self._requested_symbols)
            requested_market_indexes = list(self.market_index_codes)
        try:
            rows = self._parser([message], requested_symbols + requested_market_indexes)
            requested_set = set(requested_symbols + requested_market_indexes)
            filtered_rows = [
                row
                for row in rows or []
                if isinstance(row, dict)
                and str(row.get("ticker") or row.get("symbol") or row.get("index_code") or "").strip().upper() in requested_set
            ]
            diagnostic_trade_rows = [
                row for row in filtered_rows
                if row.get("trade_message_observed")
                and str(row.get("trade_message_classification") or "") != "valid_trade_execution"
            ]
            market_rows = [row for row in filtered_rows if row not in diagnostic_trade_rows]
            session_rows = [row for row in market_rows if self._is_session_status_row(row)]
            order_book_rows = [row for row in market_rows if self._is_order_book_row(row)]
            foreign_room_rows = [row for row in market_rows if self._is_foreign_room_row(row)]
            market_index_rows = [row for row in market_rows if self._is_market_index_row(row)]
            snapshot_rows = [
                row
                for row in market_rows
                if not self._is_session_status_row(row)
                and not self._is_order_book_row(row)
                and not self._is_foreign_room_row(row)
                and not self._is_market_index_row(row)
            ]
            rows_by_context = {
                "f": session_rows,
                "x_quote": order_book_rows,
                "r": foreign_room_rows,
                "mi": market_index_rows,
                "x_trade": [
                    row
                    for row in snapshot_rows
                    if str(row.get("stream_data_type") or row.get("r_type") or "").strip().upper() == TRADE_TAPE_CHANNEL_PREFIX
                ],
                "x": [
                    row
                    for row in snapshot_rows
                    if str(row.get("stream_data_type") or row.get("r_type") or "").strip().upper() != TRADE_TAPE_CHANNEL_PREFIX
                ],
            }
            with self._lock:
                if owned_generation != self._generation or self._shutdown_requested:
                    self._ignore_stale_callback_locked(owned_generation)
                    return
                valid_trade_rows = rows_by_context["x_trade"]
                written = self.cache.put_rows(rows_by_context["x"])
                order_book_written = self.order_book_cache.put_rows(order_book_rows)
                session_written = self.session_status_cache.put_rows(session_rows)
                session_aware_foreign_room_rows: List[Dict[str, Any]] = []
                for row in foreign_room_rows:
                    symbol = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
                    provider_status = self.session_status_cache.get(symbol).get("row") if symbol else None
                    provider_status_date = self._event_trading_date(provider_status or {})
                    if provider_status_date != self._session_date:
                        provider_status_date = None
                    event_date = self._event_trading_date(row)
                    provider_session_date = provider_status_date or event_date
                    if not provider_session_date:
                        # A time-only event cannot establish a provider date.
                        # Do not assign the local calendar date to provider data.
                        continue
                    session_aware_foreign_room_rows.append(
                        {
                            **row,
                            "provider_session_date": provider_session_date,
                            "session_date_source": (
                                "provider_market_status"
                                if provider_status_date
                                else "provider_event"
                            ),
                        }
                    )
                foreign_room_written = self.foreign_room_cache.put_rows(
                    session_aware_foreign_room_rows
                )
                market_index_written = self.market_index_cache.put_rows(market_index_rows)
                trade_written = self.trade_tape_cache.put_rows(
                    self._trade_events_from_streaming_rows(valid_trade_rows)
                )
                if any((written, order_book_written, foreign_room_written, market_index_written, trade_written, session_written)):
                    store = self._snapshot_store
                    if store is not None and not self._shutdown_requested:
                        store.mark_dirty()
                self._messages_observed += 1
                self._parser_rows_observed += written
                self._order_book_rows_observed += order_book_written
                self._foreign_room_rows_observed += foreign_room_written
                self._market_index_rows_observed += market_index_written
                self._trade_rows_observed += trade_written
                raw_trade_rows = [
                    row for row in filtered_rows
                    if row.get("trade_message_observed")
                ]
                self._raw_trade_messages_observed += len(raw_trade_rows)
                self._valid_trade_rows_observed += trade_written
                self._zero_price_trade_rows_dropped += sum(bool(row.get("zero_price")) for row in diagnostic_trade_rows)
                self._zero_volume_trade_rows_dropped += sum(bool(row.get("zero_volume")) for row in diagnostic_trade_rows)
                self._missing_timestamp_rows_dropped += sum(bool(row.get("missing_timestamp")) for row in diagnostic_trade_rows)
                self._malformed_trade_rows_dropped += sum(
                    str(row.get("trade_message_classification") or "") == "malformed_trade_message"
                    for row in diagnostic_trade_rows
                )
                self._non_trade_messages_dropped += sum(
                    str(row.get("trade_message_classification") or "") in {
                        "auction_no_match_state", "control_or_heartbeat_message", "quote_without_execution",
                    }
                    for row in diagnostic_trade_rows
                )
                self._session_status_rows_observed += session_written
                now = float(self._time_func())
                self._last_message_epoch = now
                self._last_message_at = _utc_iso_from_epoch(now)
                if raw_trade_rows:
                    self._last_raw_trade_message_at = self._last_message_at
                if trade_written:
                    self._last_valid_trade_at = self._last_message_at
                current_session = vietnam_market_session_from_epoch(now)
                for row in diagnostic_trade_rows:
                    symbol = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
                    if symbol:
                        self._symbol_trade_health[symbol] = (
                            "auction_waiting_for_match"
                            if current_session.get("market_session_is_auction")
                            else "waiting_for_first_valid_trade"
                        )
                for row in valid_trade_rows:
                    symbol = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
                    if symbol:
                        self._symbol_trade_health[symbol] = "live"
                self._is_idle = False
                self._idle_since = None
                self._idle_since_epoch = None
                self._connected = True
                self._transition_transport_locked(TRANSPORT_CONNECTED)
                for context, context_rows in rows_by_context.items():
                    if not context_rows:
                        continue
                    lifecycle = self._context_lifecycle[context]
                    lifecycle["accepted_event_count"] += len(context_rows)
                    lifecycle["last_event_generation"] = owned_generation
                    lifecycle["last_event_at"] = self._last_message_at
                    lifecycle["last_event_epoch"] = now
                    event_is_current_session = any(
                        self._event_trading_date(row) in {None, self._session_date}
                        for row in context_rows
                    )
                    if (
                        event_is_current_session
                        and lifecycle["subscribed_generation"] == owned_generation
                    ):
                        became_ready = lifecycle["state"] != CONTEXT_READY
                        lifecycle["last_fresh_event_at"] = self._last_message_at
                        self._transition_context_locked(context, CONTEXT_READY)
                        self._confirm_generation_recovery_locked(owned_generation)
                        if became_ready:
                            logger.info(
                                "vn_stream_context_ready transport=ssi_market_data_channel_cohort generation=%s context=%s fresh_event=true",
                                owned_generation,
                                context,
                            )
        except Exception as exc:
            self._record_error(exc, set_errored=False)

    def handle_transport_open(self, channel: str, *, generation: int) -> None:
        context = stream_context_for_channel(channel)
        first_open_for_generation = False
        with self._lock:
            if generation != self._generation or self._shutdown_requested:
                self._ignore_stale_callback_locked(generation, context=context)
                return
            first_open_for_generation = not self._connected
            self._connected = True
            self._opened_channels.add(str(channel))
            if first_open_for_generation:
                self._connect_count += 1
                self._last_connected_at = _utc_iso_from_epoch(float(self._time_func()))
                self._latest_error = None
                self._last_error_at = None
                self._last_error_class = None
                self._retry_blocked = False
            self._transition_transport_locked(TRANSPORT_CONNECTED)
            if context:
                self._mark_context_subscription_open_locked(context)
        if first_open_for_generation:
            logger.info(
                "vn_stream_connected transport=ssi_market_data_channel_cohort generation=%s",
                generation,
            )

    def handle_transport_close(self, channel: str, *, generation: int) -> None:
        context = stream_context_for_channel(channel)
        with self._lock:
            if generation != self._generation or self._shutdown_requested:
                self._ignore_stale_callback_locked(generation, context=context)
                return
            if generation in self._suppressed_close_generations or self._reconnect_in_progress:
                return
            should_log = self._connected or self._next_reconnect_epoch is None
            self._disconnect_count += 1
            self._connected = False
            self._last_disconnected_at = _utc_iso_from_epoch(float(self._time_func()))
            market_session = vietnam_market_session_from_epoch(float(self._time_func()))
            active = bool(market_session["market_session_active"])
            self._transition_transport_locked(TRANSPORT_RECONNECTING if active else TRANSPORT_CLOSED)
            for lifecycle_context, lifecycle in self._context_lifecycle.items():
                if not lifecycle["enabled"]:
                    continue
                state = CONTEXT_RECOVERING if active else CONTEXT_CLOSED
                if lifecycle["last_event_at"]:
                    state = CONTEXT_STALE
                self._transition_context_locked(
                    lifecycle_context,
                    state,
                    stale_reason="transport_disconnected" if active else "market_closed",
                )
            if active:
                self._schedule_reconnect_locked(reason="transport_disconnected", from_now=True)
        if should_log:
            logger.warning(
                "vn_stream_disconnected transport=ssi_market_data_channel_cohort generation=%s context=%s session=%s",
                generation,
                context or "unknown",
                market_session["market_session"],
            )

    def handle_subscription_error(self, channel: str, error: Any, *, generation: int) -> None:
        context = stream_context_for_channel(channel)
        error_class = classify_streaming_error(error)
        with self._lock:
            if generation != self._generation or self._shutdown_requested:
                self._ignore_stale_callback_locked(generation, context=context)
                return
            self._subscription_restore_failure_count += 1
            if context and context in self._context_lifecycle:
                lifecycle = self._context_lifecycle[context]
                lifecycle["subscription_failure_count"] += 1
                lifecycle["last_error_class"] = error_class
                self._transition_context_locked(
                    context,
                    CONTEXT_FAILED,
                    stale_reason="subscription_failure",
                )
        logger.warning(
            "vn_stream_subscription_restore transport=ssi_market_data_channel_cohort generation=%s context=%s state=failed error_class=%s",
            generation,
            context or "unknown",
            error_class,
        )

    def _confirm_generation_recovery_locked(self, generation: int) -> None:
        if generation <= 1 or generation in self._reconnect_success_generations:
            return
        self._reconnect_success_generations.add(generation)
        self._reconnect_success_count += 1
        self._current_reconnect_attempt_number = 0
        self._backoff_index = 0
        self._reconnect_backoff_seconds = self.reconnect_initial_delay_seconds
        self._next_reconnect_at = None
        self._next_reconnect_epoch = None
        self._last_reconnect_error = None

    def _context_status_metadata(self, context: str) -> Dict[str, Any]:
        with self._lock:
            lifecycle = self._context_lifecycle[context]
            last_event_epoch = lifecycle.get("last_event_epoch")
            return {
                "stream_state": lifecycle["state"],
                "last_event_at": lifecycle["last_event_at"],
                "event_age_seconds": (
                    max(0, int(float(self._time_func()) - float(last_event_epoch)))
                    if last_event_epoch is not None
                    else None
                ),
                "generation": self._generation,
            }

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
    def _is_market_index_row(row: Dict[str, Any]) -> bool:
        raw_type = str(row.get("stream_data_type") or row.get("r_type") or "").strip().upper()
        return raw_type == MARKET_INDEX_CHANNEL_PREFIX

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
                "event_market_session": row.get("event_market_session")
                or vietnam_market_session_from_provider_timestamp(timestamp),
            }
            events.append(event)
        return events

    def handle_error(self, error: Any, *, generation: Optional[int] = None) -> None:
        error_class = classify_streaming_error(error)
        with self._lock:
            owned_generation = self._generation if generation is None else int(generation)
            if owned_generation != self._generation or self._shutdown_requested:
                self._ignore_stale_callback_locked(owned_generation)
                return
        self._record_error(error, set_errored=True)
        with self._lock:
            self._last_error_class = error_class
            self._connected = False
            if error_class in NON_RETRYABLE_STREAM_ERROR_CLASSES:
                self._retry_blocked = True
                self._transition_transport_locked(TRANSPORT_FAILED)
                for context, lifecycle in self._context_lifecycle.items():
                    if lifecycle["enabled"]:
                        lifecycle["last_error_class"] = error_class
                        self._transition_context_locked(context, CONTEXT_FAILED, stale_reason=error_class)
                return
            market_session = vietnam_market_session_from_epoch(float(self._time_func()))
            if market_session["market_session_active"]:
                self._transition_transport_locked(TRANSPORT_RECONNECTING)
                self._schedule_reconnect_locked(reason="stream_error", from_now=True)

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
            **self._context_status_metadata("x"),
            "streaming_data_types": ["X"],
        }
        status = self.status()
        requested_health = {
            symbol: self._symbol_trade_health.get(symbol, "waiting_for_first_valid_trade")
            for symbol in requested
        }
        symbol_data_health = (
            next(iter(requested_health.values()))
            if len(requested_health) == 1
            else "live"
            if requested_health and all(value == "live" for value in requested_health.values())
            else "partial"
        )
        base.update(
            {
                "transport_health": "healthy" if status.get("connected") else "unavailable",
                "parser_health": "healthy" if not status.get("latest_error") else "degraded",
                "symbol_data_health": symbol_data_health,
                "current_market_session": status.get("market_session"),
                "last_valid_trade_at": status.get("last_valid_trade_at"),
                "dropped_invalid_row_count": status.get("dropped_invalid_row_count", 0),
            }
        )
        manager_state = status["manager_state"]
        diagnostics = dict(status)
        diagnostics.update(self._context_status_metadata("x"))
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
            persisted_only = all(row.get("snapshot_source") == "persisted" for row in cache_result["rows"])
            stale_rows_present = any(bool(row.get("is_stale")) for row in cache_result["rows"])
            after_hours = not diagnostics.get("market_session_active")
            reason = (
                "Market closed — showing last known data."
                if stale_rows_present and after_hours
                else "Waiting for live SSI updates — showing last known data."
                if stale_rows_present
                else None
            )
            return {
                **base,
                "symbol_data_health": "after_hours_stale" if stale_rows_present and after_hours else "stale" if stale_rows_present else "live",
                "status": "stale" if stale_rows_present else "ok",
                "reason": reason,
                "quotes": cache_result["rows"],
                "count": len(cache_result["rows"]),
                "streaming_status": "after_hours_stale" if stale_rows_present and after_hours else "persisted_stale" if persisted_only else "cache_stale" if stale_rows_present else "cache_hit",
                "cache_status": "persisted_stale" if persisted_only else "stale" if stale_rows_present else "hit",
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
        if diagnostics.get("stream_health") in {"market_closed", "idle_market_closed", "after_hours_stale"}:
            reason = (
                "Market closed — showing last known data."
                if cache_result["stale_count"] > 0
                else "Market closed — no live realtime snapshot expected."
            )
            streaming_status = "after_hours_stale" if cache_result["stale_count"] > 0 else diagnostics.get("stream_health")
            base["symbol_data_health"] = "after_hours_stale"
        elif diagnostics.get("market_session_is_auction") and any(
            self._symbol_trade_health.get(symbol) == "auction_waiting_for_match"
            for symbol in requested
        ):
            reason = "Waiting for auction match."
            streaming_status = "ato_waiting_for_match" if diagnostics.get("market_session") == "ato" else "atc_waiting_for_match"
            base["symbol_data_health"] = "auction_waiting_for_match"
        diagnostics["streaming_status"] = streaming_status
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
        diagnostics.update(self._context_status_metadata("x_quote"))
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
            **self._context_status_metadata("x_quote"),
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
        if cache_status in {"hit", "stale", "persisted_stale"} and cache_result["row"]:
            after_hours = not diagnostics.get("market_session_active")
            streaming_status = (
                "market_closed"
                if after_hours and cache_status == "hit"
                else "after_hours_stale"
                if after_hours
                else "cache_hit"
                if cache_status == "hit"
                else "cache_stale"
            )
            order_book_row = dict(cache_result["row"])
            if after_hours:
                order_book_row["is_stale"] = True
                order_book_row["stale_reason"] = "Market closed — showing last known data."
            diagnostics["streaming_status"] = streaming_status
            return {
                **base,
                "status": "stale" if after_hours or cache_status in {"stale", "persisted_stale"} else "ok",
                "reason": "Market closed — showing last known data." if after_hours else "Waiting for live SSI updates — showing last known data." if cache_status == "persisted_stale" else None if cache_status == "hit" else "SSI X-QUOTE stream cache stale.",
                "order_book": order_book_row,
                "count": 1,
                "streaming_status": streaming_status,
                "cache_status": cache_status,
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        reason = (
            "SSI X-QUOTE stream cache stale."
            if cache_status == "stale"
            else "SSI X-QUOTE stream cache empty."
        )
        streaming_status = "cache_stale" if cache_status == "stale" else "subscribed_no_event"
        if diagnostics.get("stream_health") in {"market_closed", "idle_market_closed", "after_hours_stale"}:
            reason = (
                "Market closed — showing last known data."
                if cache_status == "stale"
                else "Market closed — no live order-book rows expected."
            )
            streaming_status = "after_hours_stale" if cache_status == "stale" else diagnostics.get("stream_health")
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
        diagnostics.update(self._context_status_metadata("r"))
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
            **self._context_status_metadata("r"),
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
        if cache_status in {"hit", "persisted_stale"} and cache_result["row"]:
            return {
                **base,
                "status": "ok",
                "reason": "Market closed — showing last known data." if not diagnostics.get("market_session_active") and cache_status == "persisted_stale" else "Waiting for live SSI updates — showing last known data." if cache_status == "persisted_stale" else None,
                "foreign_room": cache_result["row"],
                "count": 1,
                "streaming_status": "persisted_stale" if cache_status == "persisted_stale" else "cache_hit",
                "cache_status": cache_status,
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

    def current_foreign_flow(self, symbol: str) -> Dict[str, Any]:
        """Return the current-session provisional R snapshot without blending REST."""

        requested_symbol = str(symbol or "").strip().upper()
        status = self.status()
        session_date = str(status.get("session_date") or self._session_date)
        market_active = bool(status.get("market_session_active"))
        room_status = self.foreign_room(requested_symbol)
        cache_result = self.foreign_room_cache.get(requested_symbol, session_date)
        row = cache_result.get("row")
        has_volume_pair = bool(
            row
            and row.get("foreign_buy_volume") is not None
            and row.get("foreign_sell_volume") is not None
        )
        has_value_pair = bool(
            row
            and row.get("foreign_buy_value") is not None
            and row.get("foreign_sell_value") is not None
        )
        usable = has_volume_pair or has_value_pair

        stream_status = str(room_status.get("streaming_status") or "unavailable")
        transport_connected = bool(
            status.get("connected")
            and status.get("transport_state") == TRANSPORT_CONNECTED
            and status.get("manager_state") == MANAGER_RUNNING
        )
        failure_class: Optional[str] = None
        if row and usable:
            if not market_active:
                data_state = "market_closed"
                reason = "Market closed — showing last known current-session provisional flow."
            elif not transport_connected:
                data_state = "stale"
                failure_class = self._current_flow_failure_class(
                    status.get("last_error_class")
                )
                reason = "Current-session foreign flow connection was lost; showing the last received snapshot."
            elif cache_result.get("status") in {"stale", "persisted_stale"}:
                data_state = "stale"
                reason = "Current-session foreign flow snapshot is stale."
            else:
                data_state = "ready"
                reason = None
        elif stream_status == "manager_error":
            data_state = "unavailable"
            failure_class = self._current_flow_failure_class(
                (room_status.get("diagnostics") or {}).get("last_error_class")
                or status.get("last_error_class")
            )
            reason = str(room_status.get("reason") or "SSI streaming manager error.")
        elif stream_status in {
            "disabled",
            "r_disabled",
            "manager_not_started",
            "bootstrap_symbols_empty",
            "ticker_not_bootstrapped",
            "r_not_subscribed",
        }:
            data_state = "unavailable"
            failure_class = stream_status
            reason = str(room_status.get("reason") or "Current foreign flow unavailable.")
        elif not market_active:
            data_state = "market_closed"
            reason = "Market closed — no current-session foreign room message was received."
            usable = False
        else:
            data_state = "waiting"
            reason = "Waiting for the first SSI ForeignRoomMessage for this session."

        return {
            "status": "ok" if data_state == "ready" else "partial" if usable else "unavailable",
            "data_state": data_state,
            "usable": bool(usable),
            "failure_class": failure_class,
            "symbol": requested_symbol,
            "provider_session_date": session_date,
            "is_current_session": bool(row and row.get("provider_session_date") == session_date),
            "is_provisional": bool(row),
            "current": dict(row) if row and usable else None,
            "stream_status": stream_status,
            "stream_reason": reason,
            "cache": {
                "status": cache_result.get("status"),
                "age_seconds": cache_result.get("latest_foreign_room_age_seconds"),
                "ttl_seconds": self.foreign_room_cache.ttl_seconds,
            },
            "market_session": {
                key: status.get(key)
                for key in (
                    "market_session",
                    "market_session_label",
                    "market_session_active",
                    "market_session_is_auction",
                    "market_session_is_continuous",
                )
            },
            "diagnostics": {
                "manager_state": room_status.get("manager_state"),
                "subscription_count": status.get("subscription_count", 0),
                "foreign_room_subscription_count": len(
                    status.get("foreign_room_channels") or []
                ),
                "foreign_room_rows_observed": status.get("foreign_room_rows_observed", 0),
                "session_date_source": (
                    row.get("session_date_source") if row else "manager_vietnam_session"
                ),
                "raw_field_presence": dict(row.get("raw_field_presence") or {}) if row else {},
                "replacement_snapshot": True,
                "transport_connected": transport_connected,
                "recovery_request_count": status.get("recovery_request_count", 0),
                "recovery_request_suppressed_count": status.get(
                    "recovery_request_suppressed_count", 0
                ),
                "last_recovery_request_at": status.get("last_recovery_request_at"),
                "last_recovery_trigger": status.get("last_recovery_trigger"),
            },
        }

    @staticmethod
    def _current_flow_failure_class(error_class: Any) -> Optional[str]:
        mapping = {
            "configuration": "credentials_missing",
            "authentication": "authentication_failed_retryable",
            "authorization": "authentication_failed_retryable",
            "entitlement_rejected": "explicit_entitlement_rejected",
            "subscription_failure": "subscription_failed",
            "network_closed": "connection_failed",
            "timeout": "connection_failed",
            "dns": "connection_failed",
            "tls": "connection_failed",
            "sdk_error": "provider_unavailable",
            "unknown": "unexpected_internal_error",
        }
        return mapping.get(str(error_class or "").strip()) or None

    def market_index_pulse(self, index_codes: Iterable[str]) -> Dict[str, Any]:
        requested_indexes = normalize_streaming_symbols(index_codes)
        if not requested_indexes:
            requested_indexes = list(self.market_index_codes)
        status = self.status()
        diagnostics = dict(status)
        diagnostics.update(self._context_status_metadata("mi"))
        diagnostics.update(
            {
                "streaming_status": "market_index_buffer",
                "cache_ttl_seconds": self.market_index_cache.ttl_seconds,
                "market_index_ttl_seconds": self.market_index_cache.ttl_seconds,
                "channel_type": MARKET_INDEX_CHANNEL_PREFIX,
                "market_index_rows_observed": self._market_index_rows_observed,
                "requested_index_codes": requested_indexes,
            }
        )
        base = {
            "source": "SSI",
            "requested_index_codes": requested_indexes,
            "market_index_pulse": [],
            "count": 0,
            "streaming_data_types": [MARKET_INDEX_CHANNEL_PREFIX],
            "attempted_endpoints": [],
            "candidate_endpoints": [],
            "rest_status": "unsupported",
            "channel_format_status": "needs_live_proof",
            **self._context_status_metadata("mi"),
        }

        if not requested_indexes:
            diagnostics["failure_class"] = "missing_index_codes"
            return {
                **base,
                "status": "unavailable",
                "reason": "No index codes requested",
                "streaming_status": "missing_index_codes",
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
        if not self.market_index_enabled:
            diagnostics.update({"streaming_status": "mi_disabled", "cache_status": "disabled"})
            return {
                **base,
                "status": "unavailable",
                "reason": "SSI MI market-index stream channel disabled.",
                "streaming_status": "mi_disabled",
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

        configured_indexes = set(normalize_streaming_symbols(status.get("market_index_codes") or []))
        missing_bootstrap = [code for code in requested_indexes if configured_indexes and code not in configured_indexes]
        if missing_bootstrap:
            diagnostics.update(
                {
                    "streaming_status": "index_not_bootstrapped",
                    "cache_status": "not_bootstrapped",
                    "bootstrap_membership": "not_bootstrapped",
                    "missing_index_codes": missing_bootstrap,
                }
            )
            return {
                **base,
                "status": "unavailable",
                "reason": "SSI MI market-index stream not bootstrapped.",
                "streaming_status": "index_not_bootstrapped",
                "cache_status": "not_bootstrapped",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        subscribed_channels = set(status.get("market_index_channels") or [])
        missing_channels = [
            build_market_index_channel(code)
            for code in requested_indexes
            if build_market_index_channel(code) not in subscribed_channels
        ]
        if missing_channels:
            diagnostics.update(
                {
                    "streaming_status": "mi_not_subscribed",
                    "cache_status": "not_subscribed",
                    "bootstrap_membership": "bootstrapped",
                    "missing_channels": missing_channels,
                }
            )
            return {
                **base,
                "status": "unavailable",
                "reason": "SSI MI market-index stream channel not subscribed.",
                "streaming_status": "mi_not_subscribed",
                "cache_status": "not_subscribed",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        cache_result = self.market_index_cache.get_many(requested_indexes)
        cache_status = cache_result["status"]
        rows = cache_result["rows"]
        diagnostics.update(
            {
                "streaming_status": "cache_hit" if cache_status == "hit" else f"cache_{cache_status}",
                "cache_status": cache_status,
                "latest_market_index_timestamp": cache_result["latest_market_index_timestamp"],
                "latest_market_index_age_seconds": cache_result["latest_market_index_age_seconds"],
                "stale_market_index_row_count": len(cache_result["stale_rows"]),
            }
        )
        if rows:
            persisted_only = cache_status == "persisted_stale"
            return {
                **base,
                "status": "ok" if len(rows) == len(requested_indexes) else "partial",
                "reason": "Market closed — showing last known data." if persisted_only and not diagnostics.get("market_session_active") else "Waiting for live SSI updates — showing last known data." if persisted_only else None if len(rows) == len(requested_indexes) else "Some SSI MI market-index rows unavailable.",
                "market_index_pulse": rows,
                "count": len(rows),
                "streaming_status": "after_hours_stale" if persisted_only and not diagnostics.get("market_session_active") else "persisted_stale" if persisted_only else "cache_hit",
                "cache_status": "persisted_stale" if persisted_only else "hit",
                "manager_state": manager_state,
                "diagnostics": diagnostics,
            }

        reason = (
            "SSI MI market-index stream cache stale."
            if cache_status == "stale"
            else "SSI MI market-index stream cache empty."
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
        diagnostics.update(self._context_status_metadata("x_trade"))
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
            **self._context_status_metadata("x_trade"),
            "transport_health": "healthy" if status.get("connected") else "unavailable",
            "parser_health": "healthy" if not status.get("latest_error") else "degraded",
            "symbol_data_health": self._symbol_trade_health.get(requested_symbol, "waiting_for_first_valid_trade"),
            "current_market_session": status.get("market_session"),
            "last_valid_trade_at": status.get("last_valid_trade_at"),
            "dropped_invalid_row_count": status.get("dropped_invalid_row_count", 0),
        }

        if not requested_symbol:
            diagnostics["failure_class"] = "missing_symbol"
            return {
                **base,
                "symbol_data_health": "after_hours_stale" if after_hours else "stale" if persisted_only or cache_result["status"] == "stale" else "live",
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
            after_hours = not diagnostics.get("market_session_active")
            persisted_only = cache_result["status"] == "persisted_stale"
            streaming_status = (
                "market_closed"
                if after_hours and cache_result["status"] == "hit"
                else "after_hours_stale"
                if after_hours or persisted_only
                else "cache_stale"
                if cache_result["status"] == "stale"
                else "cache_hit"
            )
            diagnostics["streaming_status"] = streaming_status
            return {
                **base,
                "status": (
                    "stale"
                    if after_hours
                    or persisted_only
                    or cache_result["status"] == "stale"
                    else "ok"
                ),
                "reason": "Market closed — showing last known data." if after_hours else "Waiting for live SSI updates — showing last known data." if persisted_only else "Buffered SSI X-TRADE rows available." if cache_result["status"] == "stale" else None,
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
        if diagnostics.get("stream_health") in {"market_closed", "idle_market_closed", "after_hours_stale"}:
            reason = (
                "Market closed — showing last known data."
                if cache_result["status"] == "stale"
                else "Market closed — no live trade rows expected."
            )
            diagnostics["streaming_status"] = "after_hours_stale" if cache_result["status"] == "stale" else diagnostics.get("stream_health")
            base["symbol_data_health"] = "after_hours_stale"
        elif diagnostics.get("market_session_is_auction") and self._symbol_trade_health.get(requested_symbol) == "auction_waiting_for_match":
            reason = "Waiting for auction match."
            diagnostics["streaming_status"] = "ato_waiting_for_match" if diagnostics.get("market_session") == "ato" else "atc_waiting_for_match"
            base["symbol_data_health"] = "auction_waiting_for_match"
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
        diagnostics.update(self._context_status_metadata("f"))
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
            **self._context_status_metadata("f"),
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
        if cache_status in {"hit", "persisted_stale"} and cache_result["row"]:
            return {
                **base,
                "status": "ok",
                "reason": "Market closed — showing last known data." if not diagnostics.get("market_session_active") and cache_status == "persisted_stale" else "Waiting for live SSI updates — showing last known data." if cache_status == "persisted_stale" else None,
                "session_status": cache_result["row"],
                "count": 1,
                "streaming_status": "persisted_stale" if cache_status == "persisted_stale" else "cache_hit",
                "cache_status": cache_status,
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

    def lifecycle_snapshot(self) -> Dict[str, Any]:
        """Return a bounded, read-only, process-local lifecycle snapshot."""
        with self._lock:
            self._refresh_session_date_locked()
            now = float(self._time_func())
            contexts: Dict[str, Dict[str, Any]] = {}
            for context, lifecycle in self._context_lifecycle.items():
                last_event_epoch = lifecycle.get("last_event_epoch")
                contexts[context] = {
                    "state": lifecycle["state"],
                    "enabled": lifecycle["enabled"],
                    "subscribed_generation": lifecycle["subscribed_generation"],
                    "last_event_generation": lifecycle["last_event_generation"],
                    "last_event_at": lifecycle["last_event_at"],
                    "last_fresh_event_at": lifecycle["last_fresh_event_at"],
                    "event_age_seconds": (
                        max(0, int(now - float(last_event_epoch)))
                        if last_event_epoch is not None
                        else None
                    ),
                    "accepted_event_count": lifecycle["accepted_event_count"],
                    "ignored_old_generation_event_count": lifecycle["ignored_old_generation_event_count"],
                    "subscription_restoration_count": lifecycle["subscription_restoration_count"],
                    "subscription_failure_count": lifecycle["subscription_failure_count"],
                    "stale_reason": lifecycle["stale_reason"],
                    "last_error_class": lifecycle["last_error_class"],
                }
            overall_state = self._overall_lifecycle_state_locked(contexts)
            return {
                "scope": "process_local",
                "overall_state": overall_state,
                "transports": [
                    {
                        "name": "ssi_market_data_channel_cohort",
                        "state": self._transport_state,
                        "connected": self._connected,
                        "generation": self._generation,
                        "start_count": self._start_count,
                        "connect_count": self._connect_count,
                        "disconnect_count": self._disconnect_count,
                        "reconnect_scheduled_count": self._reconnect_scheduled_count,
                        "reconnect_task_count": self._reconnect_tasks_created,
                        "reconnect_attempt_count": self._reconnect_attempt_count,
                        "reconnect_success_count": self._reconnect_success_count,
                        "reconnect_failure_count": self._reconnect_failure_count,
                        "stale_generation_callbacks_ignored": self._stale_generation_callbacks_ignored,
                        "subscription_restore_attempt_count": self._subscription_restore_attempt_count,
                        "subscription_restore_success_count": self._subscription_restore_success_count,
                        "subscription_restore_failure_count": self._subscription_restore_failure_count,
                        "readiness_transition_count": self._readiness_transition_count,
                        "shutdown_count": self._shutdown_count,
                        "physical_transport_count": len(self._opened_channels),
                        "subscription_count": len(self._channels),
                        "last_connected_at": self._last_connected_at,
                        "last_disconnected_at": self._last_disconnected_at,
                        "last_transition_at": self._last_transition_at,
                        "last_error_class": self._last_error_class,
                        "reconnect_attempt_number": self._current_reconnect_attempt_number,
                        "next_retry_at": self._next_reconnect_at,
                        "in_flight_reconnect": self._reconnect_in_progress,
                        "shutdown_requested": self._shutdown_requested,
                        "recovery_request_count": self._recovery_request_count,
                        "recovery_request_suppressed_count": self._recovery_request_suppressed_count,
                        "last_recovery_request_at": self._last_recovery_request_at,
                        "last_recovery_trigger": self._last_recovery_trigger,
                    }
                ],
                "contexts": contexts,
                "session": {
                    **vietnam_market_session_from_epoch(now),
                    "trading_date": self._session_date,
                },
                "multi_worker_note": "Each worker owns an independent SSI connection cohort and process-local metrics.",
            }

    def _overall_lifecycle_state_locked(self, contexts: Dict[str, Dict[str, Any]]) -> str:
        if self._shutdown_requested:
            return "closed"
        if not self.enabled:
            return "closed"
        if self._retry_blocked or self._transport_state == TRANSPORT_FAILED:
            return "failed"
        if self._generation == 0:
            return "unknown"
        if self._transport_state == TRANSPORT_CONNECTING:
            return "connecting"
        enabled_states = [item["state"] for item in contexts.values() if item["enabled"]]
        if enabled_states and all(state == CONTEXT_READY for state in enabled_states):
            return "ready"
        if self._transport_state in {TRANSPORT_RECONNECTING, TRANSPORT_CONNECTING}:
            return "recovering"
        if any(state in {CONTEXT_FAILED, CONTEXT_STALE} for state in enabled_states):
            return "degraded"
        if any(state in {CONTEXT_AWAITING_SUBSCRIPTION, CONTEXT_RECOVERING} for state in enabled_states):
            return "recovering"
        if self._transport_state in {TRANSPORT_CLOSED, TRANSPORT_CLOSING, TRANSPORT_STOPPED}:
            return "closed"
        return "degraded"

    def _refresh_session_date_locked(self) -> None:
        current_date = self._vietnam_date_from_epoch(float(self._time_func()))
        if current_date == self._session_date:
            return
        self._session_date = current_date
        for context, lifecycle in self._context_lifecycle.items():
            if not lifecycle["enabled"]:
                continue
            if lifecycle["last_event_at"]:
                self._transition_context_locked(context, CONTEXT_STALE, stale_reason="date_rollover")
            else:
                self._transition_context_locked(context, CONTEXT_RECOVERING, stale_reason="date_rollover")

    def status(self) -> Dict[str, Any]:
        with self._lock:
            self._refresh_session_date_locked()
            self._refresh_idle_state_locked()
            realtime_channels = [
                channel
                for channel in self._channels
                if not is_order_book_channel(channel)
                and not is_foreign_room_channel(channel)
                and not is_market_index_channel(channel)
                and not is_trade_tape_channel(channel)
                and not is_session_status_channel(channel)
            ]
            order_book_channels = [channel for channel in self._channels if is_order_book_channel(channel)]
            foreign_room_channels = [channel for channel in self._channels if is_foreign_room_channel(channel)]
            market_index_channels = [channel for channel in self._channels if is_market_index_channel(channel)]
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
            market_index_subscription_status = (
                "disabled"
                if not self.market_index_enabled
                else ("subscribed" if market_index_channels else "not_subscribed")
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
            try:
                expected_channels = build_streaming_channels(
                    self._requested_symbols or self._bootstrap_symbols,
                    realtime_template=self.channel_template,
                    order_book_enabled=self.order_book_enabled,
                    foreign_room_enabled=self.foreign_room_enabled,
                    trade_tape_enabled=self.trade_tape_enabled,
                    session_status_enabled=self.session_status_enabled,
                    market_index_enabled=self.market_index_enabled,
                    market_indexes=self.market_index_codes,
                )
            except ValueError:
                expected_channels = []
            last_message_age_seconds = self._last_message_age_seconds_locked()
            market_session = vietnam_market_session_from_epoch(float(self._time_func()))
            stream_health = self._stream_health_locked(last_message_age_seconds, market_session)
            snapshot_diagnostics = self._snapshot_store.diagnostics() if self._snapshot_store is not None else {
                "snapshot_enabled": False,
                "snapshot_loaded": False,
                "snapshot_status": "disabled",
                "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
                "snapshot_captured_at": None,
                "snapshot_trading_date": None,
                "snapshot_age_seconds": None,
                "snapshot_context_counts": {},
                "snapshot_last_write_at": None,
                "snapshot_write_count": 0,
                "snapshot_write_error_count": 0,
                "snapshot_restore_error_count": 0,
            }
            return {
                "enabled": self.enabled,
                "manager_state": self._state,
                "stream_health": stream_health,
                **market_session,
                "requested_symbols": list(self._requested_symbols),
                "channels": list(self._channels),
                "subscription_count": len(self._channels),
                "expected_subscription_count": len(expected_channels),
                "realtime_channels": realtime_channels,
                "order_book_channels": order_book_channels,
                "order_book_channel_type": ORDER_BOOK_CHANNEL_PREFIX,
                "order_book_subscription_status": order_book_subscription_status,
                "foreign_room_channels": foreign_room_channels,
                "foreign_room_channel_type": FOREIGN_ROOM_CHANNEL_PREFIX,
                "foreign_room_subscription_status": foreign_room_subscription_status,
                "market_index_channels": market_index_channels,
                "market_index_channel_type": MARKET_INDEX_CHANNEL_PREFIX,
                "market_index_subscription_status": market_index_subscription_status,
                "market_index_codes": list(self.market_index_codes),
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
                "last_message_age_seconds": last_message_age_seconds,
                "messages_observed": self._messages_observed,
                "parser_rows_observed": self._parser_rows_observed,
                "order_book_rows_observed": self._order_book_rows_observed,
                "foreign_room_rows_observed": self._foreign_room_rows_observed,
                "market_index_rows_observed": self._market_index_rows_observed,
                "trade_rows_observed": self._trade_rows_observed,
                "raw_trade_messages_observed": self._raw_trade_messages_observed,
                "valid_trade_rows_observed": self._valid_trade_rows_observed,
                "zero_price_trade_rows_dropped": self._zero_price_trade_rows_dropped,
                "zero_volume_trade_rows_dropped": self._zero_volume_trade_rows_dropped,
                "non_trade_messages_dropped": self._non_trade_messages_dropped,
                "malformed_trade_rows_dropped": self._malformed_trade_rows_dropped,
                "missing_timestamp_rows_dropped": self._missing_timestamp_rows_dropped,
                "last_raw_trade_message_at": self._last_raw_trade_message_at,
                "last_valid_trade_at": self._last_valid_trade_at,
                "dropped_invalid_row_count": (
                    self._non_trade_messages_dropped
                    + self._malformed_trade_rows_dropped
                    + self._missing_timestamp_rows_dropped
                ),
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
                "reconnect_attempt_number": self._current_reconnect_attempt_number,
                "reconnect_count": self._reconnect_attempt_count,
                "last_reconnect_at": self._last_reconnect_at,
                "next_reconnect_at": self._next_reconnect_at,
                "reconnect_backoff_seconds": self._reconnect_backoff_seconds,
                "last_reconnect_reason": self._last_reconnect_reason,
                "last_reconnect_error": self._last_reconnect_error,
                "runtime_status": self._runtime_status_locked(),
                "transport_state": self._transport_state,
                "connected": self._connected,
                "generation": self._generation,
                "last_error_class": self._last_error_class,
                "recovery_request_count": self._recovery_request_count,
                "recovery_request_suppressed_count": self._recovery_request_suppressed_count,
                "last_recovery_request_at": self._last_recovery_request_at,
                "last_recovery_trigger": self._last_recovery_trigger,
                "recovery_request_cooldown_seconds": self._recovery_request_cooldown_seconds,
                "reconnect_scheduled_count": self._reconnect_scheduled_count,
                "reconnect_success_count": self._reconnect_success_count,
                "reconnect_failure_count": self._reconnect_failure_count,
                "stale_generation_callbacks_ignored": self._stale_generation_callbacks_ignored,
                **snapshot_diagnostics,
            }

    def _record_error(self, error: Any, *, set_errored: bool) -> None:
        with self._lock:
            self._latest_error = sanitize_streaming_error(error)
            self._last_error_class = classify_streaming_error(error)
            self._last_error_at = _utc_iso_from_epoch(float(self._time_func()))
            if set_errored:
                self._state = MANAGER_ERRORED
                self._transition_transport_locked(TRANSPORT_FAILED)

    def mark_shutdown(self) -> None:
        """Mark the manager as shutting down so monitor ticks cannot revive it."""
        with self._lock:
            self._shutdown_requested = True
            self._shutdown_count += 1
            self._connected = False
            self._transition_transport_locked(TRANSPORT_CLOSING)
            self._next_reconnect_at = None
            self._next_reconnect_epoch = None
        logger.info(
            "vn_stream_shutdown transport=ssi_market_data_channel_cohort generation=%s",
            self._generation,
        )

    def monitor_tick(self, *, wants_streaming: bool) -> Dict[str, Any]:
        """Run one deterministic idle/reconnect monitor iteration."""
        self.flush_streaming_snapshot_if_due()
        action = self._prepare_reconnect_action(wants_streaming=bool(wants_streaming))
        if action is None:
            return self.status()

        symbols, reason = action
        reconnect_error: Optional[str] = None
        try:
            logger.warning(
                "vn_stream_reconnect_attempt transport=ssi_market_data_channel_cohort generation=%s attempt=%s reason=%s",
                self._generation,
                self._current_reconnect_attempt_number,
                reason,
            )
            self._stop_client_for_reconnect()
            status = self.start(symbols)
            if status.get("manager_state") == MANAGER_RUNNING:
                with self._lock:
                    self._next_reconnect_at = None
                    self._next_reconnect_epoch = None
                    self._last_reconnect_error = None
                    self._last_reconnect_reason = reason
                    self._reconnect_in_progress = False
                return self.status()
            reconnect_error = status.get("latest_error") or "reconnect attempt failed"
        except Exception as exc:  # pragma: no cover - defensive path
            reconnect_error = sanitize_streaming_error(exc)
            self._record_error(exc, set_errored=True)
        finally:
            with self._lock:
                self._reconnect_in_progress = False

        with self._lock:
            self._reconnect_failure_count += 1
            self._last_reconnect_error = sanitize_streaming_error(reconnect_error)
            if self.reconnect_max_attempts > 0 and self._current_reconnect_attempt_number >= self.reconnect_max_attempts:
                self._next_reconnect_at = None
                self._next_reconnect_epoch = None
            else:
                self._schedule_reconnect_locked(reason=reason, from_now=True)
        return self.status()

    def _prepare_reconnect_action(self, *, wants_streaming: bool) -> Optional[Tuple[List[str], str]]:
        with self._lock:
            self._refresh_idle_state_locked()
            market_session = vietnam_market_session_from_epoch(float(self._time_func()))
            if (
                not self.enabled
                or not wants_streaming
                or self._shutdown_requested
                or self._reconnect_in_progress
                or not self.reconnect_enabled
                or self._retry_blocked
            ):
                return None
            symbols = list(self._requested_symbols or self._bootstrap_symbols)
            if not symbols:
                return None

            reason = (
                self._last_reconnect_reason
                if self._next_reconnect_epoch is not None and self._last_reconnect_reason
                else self._reconnect_reason_locked(market_session)
            )
            if reason is None:
                if self._state == MANAGER_RUNNING and not market_session["market_session_active"]:
                    self._next_reconnect_at = None
                    self._next_reconnect_epoch = None
                return None
            if self.reconnect_max_attempts > 0 and self._current_reconnect_attempt_number >= self.reconnect_max_attempts:
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
            self._current_reconnect_attempt_number += 1
            self._last_reconnect_epoch = now
            self._last_reconnect_at = _utc_iso_from_epoch(now)
            self._last_reconnect_reason = reason
            self._next_reconnect_at = None
            self._next_reconnect_epoch = None
            return symbols, reason

    def _reconnect_reason_locked(self, market_session: Dict[str, Any]) -> Optional[str]:
        if not market_session["market_session_active"]:
            return None
        if self._state == MANAGER_ERRORED:
            return "stream_error" if self._messages_observed > 0 else "start_error"
        if self._state == MANAGER_STOPPED and self._bootstrap_started_by_lifecycle:
            return "unexpected_stopped"
        if self._state == MANAGER_RUNNING and self._is_idle and market_session["market_session_active"]:
            return "stream_stale"
        return None

    def _schedule_reconnect_locked(self, *, reason: str, from_now: bool) -> None:
        if self._shutdown_requested or self._retry_blocked or not self.reconnect_enabled:
            return
        if self._next_reconnect_epoch is not None:
            return
        now = float(self._time_func())
        base_delay = self._backoff_sequence[min(self._backoff_index, len(self._backoff_sequence) - 1)]
        jitter = float(self._jitter_func(base_delay))
        jitter_limit = 0.2 * base_delay
        delay = max(0.1, min(self.reconnect_max_delay_seconds, base_delay + max(-jitter_limit, min(jitter, jitter_limit))))
        self._next_reconnect_epoch = now + delay if from_now else now
        self._next_reconnect_at = _utc_iso_from_epoch(self._next_reconnect_epoch)
        self._last_reconnect_reason = reason
        self._reconnect_backoff_seconds = delay
        self._reconnect_scheduled_count += 1
        self._reconnect_tasks_created += 1
        self._backoff_index = min(self._backoff_index + 1, len(self._backoff_sequence) - 1)
        self._transition_transport_locked(TRANSPORT_RECONNECTING)
        logger.warning(
            "vn_stream_reconnect_scheduled transport=ssi_market_data_channel_cohort generation=%s attempt=%s delay=%.3f reason=%s",
            self._generation,
            self._backoff_index,
            delay,
            reason,
        )

    def _stop_client_for_reconnect(self) -> None:
        with self._lock:
            client = self._client
            self._client = None
            self._suppressed_close_generations.add(self._generation)
            self._channels = []
            self._connected = False
            self._opened_channels.clear()
            self._transition_transport_locked(TRANSPORT_RECONNECTING)
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

    def _last_message_age_seconds_locked(self) -> Optional[int]:
        if self._last_message_epoch is None:
            return None
        return max(0, int(float(self._time_func()) - self._last_message_epoch))

    def _stream_health_locked(self, last_message_age_seconds: Optional[int], market_session: Dict[str, Any]) -> str:
        if self._shutdown_requested:
            return "not_started"
        if not self.enabled or self._state == MANAGER_DISABLED:
            return "disabled"
        if self._state == MANAGER_ERRORED:
            return "failed"
        if self._reconnect_in_progress or self._next_reconnect_epoch is not None:
            return "reconnecting"
        if self._state in {MANAGER_STOPPED, MANAGER_STARTING}:
            return "not_started"
        if self._state == MANAGER_RUNNING:
            if not market_session["market_session_active"]:
                if self._is_idle and last_message_age_seconds is not None:
                    return "after_hours_stale"
                if self._is_idle:
                    return "idle_market_closed"
                return "market_closed"
            if self._is_idle:
                return "stale"
            if last_message_age_seconds is None:
                return "idle"
            return "healthy"
        return "not_started"
