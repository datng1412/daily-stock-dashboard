"""Bounded, user-safe persistence for normalized SSI streaming cache rows.

The store deliberately has no knowledge of the SSI transport, subscriptions, or
HTTP routes. Callers provide already-normalized context rows; this module
allowlists their public fields again before atomically writing one small JSON
snapshot.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional


SNAPSHOT_SCHEMA_VERSION = 2
SNAPSHOT_PROVIDER = "SSI"
_CONTEXT_NAMES = ("realtime", "order_book", "trades", "foreign_room", "market_index", "session")
_MAX_TRADE_LIMIT = 50
_MAX_SYMBOLS_LIMIT = 512
_MAX_AGE_DAYS_LIMIT = 31

_COMMON_FIELDS = {
    "ticker", "symbol", "index_code", "exchange", "trading_date", "time", "stream_timestamp",
    "stream_data_type", "r_type", "source", "received_at", "cached_at", "cache_ttl_seconds",
}
_CONTEXT_FIELDS = {
    "realtime": _COMMON_FIELDS | {
        "price", "open", "high", "low", "change", "change_pct", "volume", "value", "reference_price",
        "ceiling_price", "floor_price", "previous_close", "last_volume", "last_value", "has_last_trade",
        "sequence_if_available", "side_if_available",
        "event_market_session",
    },
    "order_book": _COMMON_FIELDS | {"bids", "asks"},
    "trades": {
        "ticker", "symbol", "price", "volume", "value", "side", "side_label", "side_if_available",
        "timestamp", "timestamp_display", "time", "source", "sequence", "sequence_if_available",
        "raw_type", "match_type", "id",
        "event_market_session",
    },
    "foreign_room": _COMMON_FIELDS | {
        "total_room", "current_room", "foreign_buy_volume", "foreign_sell_volume", "foreign_buy_value",
        "foreign_sell_value", "value_semantics_status",
    },
    "market_index": _COMMON_FIELDS | {
        "index_name", "index_value", "estimated_index_value", "change", "change_pct", "total_trades",
        "total_volume", "total_value", "advances", "unchanged", "declines", "channel_format_status",
        "value_semantics_status",
    },
    "session": _COMMON_FIELDS | {"trading_session", "trading_status"},
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_aware_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _normalized_key(value: Any) -> Optional[str]:
    text = str(value or "").strip().upper()
    if not text or text == "ALL" or len(text) > 32:
        return None
    return text if all(char.isalnum() or char in "._-" for char in text) else None


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value.replace("\r", " ").replace("\n", " ").strip()[:160]
    return None


def _safe_levels(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    levels: List[Dict[str, Any]] = []
    for raw in value[:20]:
        if not isinstance(raw, dict):
            continue
        level = raw.get("level")
        price = raw.get("price")
        volume = raw.get("volume")
        if not isinstance(level, (int, float)) or not isinstance(price, (int, float)) or not isinstance(volume, (int, float)):
            continue
        if int(level) < 1 or price <= 0 or volume < 0:
            continue
        levels.append({"level": int(level), "price": float(price), "volume": float(volume)})
    return levels


def _safe_row(context: str, row: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(row, dict):
        return None
    allowed = _CONTEXT_FIELDS[context]
    cleaned: Dict[str, Any] = {}
    for field in allowed:
        if field not in row:
            continue
        if field in {"bids", "asks"}:
            cleaned[field] = _safe_levels(row[field])
        else:
            value = _safe_scalar(row[field])
            if value is not None:
                cleaned[field] = value
    key = _normalized_key(cleaned.get("index_code") if context == "market_index" else cleaned.get("ticker") or cleaned.get("symbol"))
    if key is None:
        return None
    if context == "market_index":
        cleaned["index_code"] = key
    else:
        cleaned["ticker"] = key
        cleaned.setdefault("symbol", key)
    if context == "trades":
        if (
            not isinstance(cleaned.get("price"), (int, float))
            or not math.isfinite(float(cleaned["price"]))
            or cleaned["price"] <= 0
            or not isinstance(cleaned.get("volume"), (int, float))
            or not math.isfinite(float(cleaned["volume"]))
            or cleaned["volume"] <= 0
            or not cleaned.get("timestamp")
        ):
            return None
    elif context == "order_book":
        if not cleaned.get("bids") and not cleaned.get("asks"):
            return None
    elif context == "realtime":
        if (
            not isinstance(cleaned.get("price"), (int, float))
            or not math.isfinite(float(cleaned["price"]))
            or cleaned["price"] <= 0
            or cleaned.get("has_last_trade") is not True
            or not isinstance(cleaned.get("last_volume"), (int, float))
            or not math.isfinite(float(cleaned["last_volume"]))
            or cleaned["last_volume"] <= 0
            or not cleaned.get("stream_timestamp")
        ):
            return None
    elif context == "foreign_room":
        if not any(isinstance(cleaned.get(field), (int, float)) for field in _CONTEXT_FIELDS[context] - _COMMON_FIELDS):
            return None
    elif context == "market_index":
        if not isinstance(cleaned.get("index_value"), (int, float)):
            return None
    elif context == "session":
        if not cleaned.get("trading_session") and not cleaned.get("trading_status"):
            return None
    return cleaned


class SsiStreamingSnapshotStore:
    """Debounced JSON snapshot store with strict validation and diagnostics."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        path: str = "runtime/ssi_streaming_last_known.v1.json",
        write_interval_seconds: int = 5,
        trade_limit: int = 50,
        max_symbols: int = 128,
        max_age_days: int = 7,
        now_func: Callable[[], datetime] = _utcnow,
    ) -> None:
        self.enabled = bool(enabled)
        self.path = Path(path or "runtime/ssi_streaming_last_known.v1.json")
        self.write_interval_seconds = max(1, int(write_interval_seconds or 5))
        self.trade_limit = max(1, min(int(trade_limit or _MAX_TRADE_LIMIT), _MAX_TRADE_LIMIT))
        self.max_symbols = max(1, min(int(max_symbols or 128), _MAX_SYMBOLS_LIMIT))
        self.max_age_days = max(1, min(int(max_age_days or 7), _MAX_AGE_DAYS_LIMIT))
        self._now_func = now_func
        self._lock = threading.RLock()
        self._dirty = False
        self._closed = False
        self._last_write_at: Optional[str] = None
        self._last_write_epoch: Optional[float] = None
        self._write_count = 0
        self._write_error_count = 0
        self._restore_error_count = 0
        self._loaded = False
        self._status = "disabled" if not self.enabled else "missing"
        self._captured_at: Optional[str] = None
        self._trading_date: Optional[str] = None
        self._context_counts: Dict[str, int] = {name: 0 for name in _CONTEXT_NAMES}

    def mark_dirty(self) -> None:
        with self._lock:
            if self.enabled and not self._closed:
                self._dirty = True

    def load(self) -> Dict[str, Any]:
        if not self.enabled:
            return self._empty_snapshot()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            with self._lock:
                self._status = "missing"
            return self._empty_snapshot()
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            with self._lock:
                self._status = "invalid"
                self._restore_error_count += 1
            return self._empty_snapshot()
        snapshot = self._validate_snapshot(raw)
        with self._lock:
            self._loaded = snapshot is not None
            if snapshot is None:
                self._restore_error_count += 1
                return self._empty_snapshot()
            self._status = "loaded"
            self._captured_at = snapshot["captured_at"]
            self._trading_date = snapshot["trading_date"]
            self._context_counts = self._context_counts_for(snapshot["contexts"])
        return snapshot

    def flush_if_due(self, snapshot_factory: Callable[[], Dict[str, Any]]) -> bool:
        with self._lock:
            if not self.enabled or self._closed or not self._dirty:
                return False
            now_epoch = self._now_func().timestamp()
            if self._last_write_epoch is not None and now_epoch - self._last_write_epoch < self.write_interval_seconds:
                return False
        return self.flush_now(snapshot_factory)

    def flush_now(self, snapshot_factory: Callable[[], Dict[str, Any]]) -> bool:
        with self._lock:
            if not self.enabled or self._closed or not self._dirty:
                return False
        try:
            snapshot = self._build_snapshot(snapshot_factory())
            self._atomic_write(snapshot)
        except (OSError, TypeError, ValueError):
            with self._lock:
                self._write_error_count += 1
                self._status = "write_error"
            return False
        with self._lock:
            now = self._now_func()
            self._dirty = False
            self._last_write_at = _iso(now)
            self._last_write_epoch = now.timestamp()
            self._write_count += 1
            self._status = "loaded"
            self._captured_at = snapshot["captured_at"]
            self._trading_date = snapshot["trading_date"]
            self._context_counts = self._context_counts_for(snapshot["contexts"])
        return True

    def close(self, snapshot_factory: Optional[Callable[[], Dict[str, Any]]] = None) -> bool:
        flushed = self.flush_now(snapshot_factory) if snapshot_factory is not None else False
        with self._lock:
            self._closed = True
        return flushed

    def diagnostics(self) -> Dict[str, Any]:
        with self._lock:
            now = self._now_func()
            age_seconds = None
            captured = _parse_aware_datetime(self._captured_at)
            if captured is not None:
                age_seconds = max(0, int((now - captured.astimezone(timezone.utc)).total_seconds()))
            return {
                "snapshot_enabled": self.enabled,
                "snapshot_loaded": self._loaded,
                "snapshot_status": self._status,
                "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
                "snapshot_captured_at": self._captured_at,
                "snapshot_trading_date": self._trading_date,
                "snapshot_age_seconds": age_seconds,
                "snapshot_context_counts": dict(self._context_counts),
                "snapshot_last_write_at": self._last_write_at,
                "snapshot_write_count": self._write_count,
                "snapshot_write_error_count": self._write_error_count,
                "snapshot_restore_error_count": self._restore_error_count,
            }

    def _empty_snapshot(self) -> Dict[str, Any]:
        return {"schema_version": SNAPSHOT_SCHEMA_VERSION, "provider": SNAPSHOT_PROVIDER, "captured_at": None, "trading_date": None, "contexts": {name: {} for name in _CONTEXT_NAMES}}

    def _build_snapshot(self, contexts: Any) -> Dict[str, Any]:
        now = self._now_func()
        return {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "provider": SNAPSHOT_PROVIDER,
            "captured_at": _iso(now),
            "trading_date": now.date().isoformat(),
            "contexts": self._sanitize_contexts(contexts),
        }

    def _validate_snapshot(self, raw: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(raw, dict):
            self._status = "invalid"
            return None
        if raw.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
            self._status = "unsupported_version"
            return None
        if raw.get("provider") != SNAPSHOT_PROVIDER:
            self._status = "invalid"
            return None
        captured = _parse_aware_datetime(raw.get("captured_at"))
        trading_date = raw.get("trading_date")
        if captured is None or not isinstance(trading_date, str):
            self._status = "invalid"
            return None
        now = self._now_func().astimezone(timezone.utc)
        captured_utc = captured.astimezone(timezone.utc)
        if captured_utc > now + timedelta(minutes=5) or now - captured_utc > timedelta(days=self.max_age_days):
            self._status = "expired"
            return None
        try:
            datetime.fromisoformat(trading_date).date()
        except ValueError:
            self._status = "invalid"
            return None
        contexts = self._sanitize_contexts(raw.get("contexts"))
        return {"schema_version": SNAPSHOT_SCHEMA_VERSION, "provider": SNAPSHOT_PROVIDER, "captured_at": _iso(captured), "trading_date": trading_date, "contexts": contexts}

    def _sanitize_contexts(self, contexts: Any) -> Dict[str, Any]:
        raw_contexts = contexts if isinstance(contexts, dict) else {}
        cleaned: Dict[str, Any] = {name: {} for name in _CONTEXT_NAMES}
        for context in _CONTEXT_NAMES:
            raw_rows = raw_contexts.get(context)
            if not isinstance(raw_rows, dict):
                continue
            for key, raw_row in list(raw_rows.items())[: self.max_symbols]:
                normalized_key = _normalized_key(key)
                if normalized_key is None:
                    continue
                if context == "trades":
                    if not isinstance(raw_row, list):
                        continue
                    rows = []
                    seen = set()
                    for item in raw_row[: self.trade_limit]:
                        row = _safe_row(context, item)
                        if row is None or row["ticker"] != normalized_key:
                            continue
                        identity = row.get("id") or row.get("sequence") or row.get("sequence_if_available")
                        if identity not in (None, ""):
                            identity_key = str(identity)
                            if identity_key in seen:
                                continue
                            seen.add(identity_key)
                        rows.append(row)
                    if rows:
                        cleaned[context][normalized_key] = rows
                else:
                    row = _safe_row(context, raw_row)
                    if row is None:
                        continue
                    row_key = row.get("index_code") if context == "market_index" else row.get("ticker")
                    if row_key == normalized_key:
                        cleaned[context][normalized_key] = row
        return cleaned

    def _atomic_write(self, snapshot: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, prefix=f"{self.path.name}.", suffix=".tmp", delete=False) as handle:
                temp_path = handle.name
                json.dump(snapshot, handle, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
            temp_path = None
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    @staticmethod
    def _context_counts_for(contexts: Dict[str, Any]) -> Dict[str, int]:
        return {
            name: sum(len(value) if isinstance(value, list) else 1 for value in (contexts.get(name) or {}).values())
            for name in _CONTEXT_NAMES
        }
