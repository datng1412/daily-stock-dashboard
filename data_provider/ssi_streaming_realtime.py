# -*- coding: utf-8 -*-
"""Safe SSI streaming realtime manager skeleton.

This module is intentionally side-effect free: importing it does not import the
official SSI streaming package, create clients, start threads, or open network
connections.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple


SSI_STREAMING_REALTIME_DISABLED_REASON = "SSI streaming realtime manager disabled."
SSI_STREAMING_REALTIME_NOT_STARTED_REASON = "SSI streaming realtime manager not started."
SSI_STREAMING_REALTIME_CACHE_EMPTY_REASON = "SSI streaming realtime cache empty."
SSI_STREAMING_REALTIME_CACHE_STALE_REASON = "SSI streaming realtime cache stale."
SSI_STREAMING_REALTIME_MANAGER_ERROR_REASON = "SSI streaming realtime manager errored."
SSI_STREAMING_REALTIME_LIVE_ADAPTER_DISABLED_REASON = "SSI streaming realtime live adapter not enabled."
SSI_STREAMING_REALTIME_ALL_CHANNEL_FORBIDDEN_REASON = "SSI streaming realtime refuses ALL channel subscriptions."

MANAGER_DISABLED = "disabled"
MANAGER_STOPPED = "stopped"
MANAGER_STARTING = "starting"
MANAGER_RUNNING = "running"
MANAGER_ERRORED = "errored"

DEFAULT_STREAMING_REALTIME_CACHE_TTL_SECONDS = 15
DEFAULT_STREAMING_REALTIME_CHANNEL_TEMPLATE = "X: {symbol}"

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)(access[_-]?token\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(consumer[_-]?id\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(consumer[_-]?secret\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(private[_-]?key\s*[:=]\s*)[^\s,;]+"),
)


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


@dataclass(frozen=True)
class CachedRealtimeSnapshot:
    symbol: str
    snapshot: Dict[str, Any]
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
        parser: Optional[Callable[[List[Any], List[str]], List[Dict[str, Any]]]] = None,
        client_factory: Optional[Callable[[], SsiRealtimeStreamClient]] = None,
        channel_template: str = DEFAULT_STREAMING_REALTIME_CHANNEL_TEMPLATE,
        time_func: Callable[[], float] = time.time,
    ) -> None:
        self.enabled = bool(enabled)
        self.cache = cache or RealtimeSnapshotCache(time_func=time_func)
        self._parser = parser or (lambda messages, symbols: [])
        self._client_factory = client_factory
        self.channel_template = channel_template or DEFAULT_STREAMING_REALTIME_CHANNEL_TEMPLATE
        self._time_func = time_func
        self._lock = threading.RLock()
        self._client: Optional[SsiRealtimeStreamClient] = None
        self._requested_symbols: List[str] = []
        self._channels: List[str] = []
        self._state = MANAGER_DISABLED if not self.enabled else MANAGER_STOPPED
        self._latest_error: Optional[str] = None
        self._last_error_at: Optional[str] = None
        self._last_message_at: Optional[str] = None
        self._messages_observed = 0
        self._parser_rows_observed = 0

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
            channels = [build_symbol_channel(symbol, self.channel_template) for symbol in normalized_symbols]
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
            return self.status()

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            client = self._client
            self._client = None
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
            written = self.cache.put_rows(filtered_rows)
            with self._lock:
                self._messages_observed += 1
                self._parser_rows_observed += written
                self._last_message_at = _utc_iso_from_epoch(float(self._time_func()))
        except Exception as exc:
            self._record_error(exc, set_errored=False)

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
            "streaming_data_types": ["X", "X-QUOTE", "X-TRADE"],
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
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_NOT_STARTED_REASON,
                "streaming_status": "manager_not_started",
                "cache_status": "not_started",
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

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "enabled": self.enabled,
                "manager_state": self._state,
                "requested_symbols": list(self._requested_symbols),
                "channels": list(self._channels),
                "live_adapter_status": "enabled" if self._client_factory is not None else "not_enabled",
                "latest_error": self._latest_error,
                "last_error_at": self._last_error_at,
                "last_message_at": self._last_message_at,
                "messages_observed": self._messages_observed,
                "parser_rows_observed": self._parser_rows_observed,
            }

    def _record_error(self, error: Any, *, set_errored: bool) -> None:
        with self._lock:
            self._latest_error = sanitize_streaming_error(error)
            self._last_error_at = _utc_iso_from_epoch(float(self._time_func()))
            if set_errored:
                self._state = MANAGER_ERRORED
