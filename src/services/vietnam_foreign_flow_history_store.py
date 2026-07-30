"""Durable, bounded storage for accepted completed SSI foreign-flow history.

Only normalized DailyStockPrice rows belong here. Current-session streaming
snapshots have a separate lifecycle and must never be written by this store.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, Mapping, Optional


SCHEMA_VERSION = 1
PROVIDER = "SSI"
SOURCE_ENDPOINT = "daily_stock_price"
ACCEPTED_SOURCE = "ssi_fastconnect"
ACCEPTED_FINALITY = "daily_available"
DEFAULT_FILENAME = "vietnam_foreign_flow_accepted.v1.json"
DEFAULT_MAX_SYMBOLS = 128
DEFAULT_MAX_ROWS_PER_SYMBOL = 120
_ROW_NUMERIC_FIELDS = (
    "foreign_buy_volume",
    "foreign_sell_volume",
    "foreign_net_volume",
    "foreign_buy_value",
    "foreign_sell_value",
    "foreign_net_value",
)
_ROW_FIELDS = {
    "trading_date",
    *_ROW_NUMERIC_FIELDS,
    "field_presence",
    "suspicious_zero_session",
    "anomaly_code",
}


def resolve_vietnam_foreign_flow_history_path(path: Optional[str | Path] = None) -> Path:
    """Resolve the store below the repository-approved data cache directory."""

    if path is not None:
        return Path(path).expanduser().resolve()
    repository_root = Path(__file__).resolve().parents[2]
    cache_dir = Path(os.environ.get("DATA_CACHE_DIR") or "data/cache").expanduser()
    if not cache_dir.is_absolute():
        cache_dir = repository_root / cache_dir
    return (cache_dir / DEFAULT_FILENAME).resolve()


def _aware_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_symbol(value: Any) -> Optional[str]:
    symbol = str(value or "").strip().upper()
    if not symbol or len(symbol) > 16:
        return None
    return symbol if symbol.isalnum() else None


def _safe_date(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed.isoformat()


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _safe_field_presence(value: Any) -> Dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    result: Dict[str, str] = {}
    for field in _ROW_NUMERIC_FIELDS:
        status = value.get(field)
        if isinstance(status, str) and 0 < len(status) <= 64:
            result[field] = status
    return result


def _safe_row(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, Mapping):
        return None
    trading_date = _safe_date(value.get("trading_date"))
    if trading_date is None:
        return None
    row: Dict[str, Any] = {"trading_date": trading_date}
    for field in _ROW_NUMERIC_FIELDS:
        row[field] = _safe_int(value.get(field))
    if not any(row[field] is not None for field in _ROW_NUMERIC_FIELDS):
        return None
    row["field_presence"] = _safe_field_presence(value.get("field_presence"))
    row["suspicious_zero_session"] = value.get("suspicious_zero_session") is True
    anomaly_code = value.get("anomaly_code")
    row["anomaly_code"] = (
        anomaly_code
        if isinstance(anomaly_code, str) and 0 < len(anomaly_code) <= 80
        else None
    )
    return row


class VietnamForeignFlowHistoryStore:
    """Small atomic JSON store for accepted completed provider rows."""

    def __init__(
        self,
        path: Optional[str | Path] = None,
        *,
        max_symbols: int = DEFAULT_MAX_SYMBOLS,
        max_rows_per_symbol: int = DEFAULT_MAX_ROWS_PER_SYMBOL,
    ) -> None:
        self.path = resolve_vietnam_foreign_flow_history_path(path)
        self.max_symbols = max(1, min(int(max_symbols), DEFAULT_MAX_SYMBOLS))
        self.max_rows_per_symbol = max(
            1,
            min(int(max_rows_per_symbol), DEFAULT_MAX_ROWS_PER_SYMBOL),
        )
        self.status = "not_loaded"
        self.last_error: Optional[str] = None

    @property
    def identity(self) -> str:
        return str(self.path)

    def load(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.status = "missing"
            self.last_error = None
            return {}
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            self.status = "invalid"
            self.last_error = "invalid_cache"
            return {}
        history = self._validate_document(raw)
        if history is None:
            self.status = "invalid"
            self.last_error = "schema_mismatch"
            return {}
        self.status = "loaded"
        self.last_error = None
        return history

    def write(self, history: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> bool:
        document = self._build_document(history)
        try:
            self._atomic_write(document)
        except (OSError, TypeError, ValueError):
            self.status = "write_error"
            self.last_error = "write_error"
            return False
        self.status = "written"
        self.last_error = None
        return True

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "last_error": self.last_error,
            "schema_version": SCHEMA_VERSION,
            "max_symbols": self.max_symbols,
            "max_rows_per_symbol": self.max_rows_per_symbol,
        }

    def _validate_document(
        self,
        raw: Any,
    ) -> Optional[Dict[str, Dict[str, Dict[str, Any]]]]:
        if not isinstance(raw, Mapping):
            return None
        if (
            raw.get("schema_version") != SCHEMA_VERSION
            or raw.get("provider") != PROVIDER
            or raw.get("source_endpoint") != SOURCE_ENDPOINT
            or raw.get("scope") != "symbol"
            or not isinstance(raw.get("symbols"), Mapping)
        ):
            return None
        for rows in raw["symbols"].values():
            if not isinstance(rows, Mapping):
                return None
            for persisted_row in rows.values():
                if (
                    not isinstance(persisted_row, Mapping)
                    or persisted_row.get("accepted_source") != ACCEPTED_SOURCE
                    or persisted_row.get("accepted_finality") != ACCEPTED_FINALITY
                    or not isinstance(persisted_row.get("persisted_at"), str)
                ):
                    return None
        return self._sanitize_history(raw["symbols"])

    def _build_document(
        self,
        history: Mapping[str, Mapping[str, Mapping[str, Any]]],
    ) -> Dict[str, Any]:
        captured_at = _aware_iso_now()
        symbols = self._sanitize_history(history)
        for rows in symbols.values():
            for row in rows.values():
                row.update(
                    accepted_source=ACCEPTED_SOURCE,
                    accepted_finality=ACCEPTED_FINALITY,
                    persisted_at=captured_at,
                    coverage_metadata={
                        "field_presence": deepcopy(row.get("field_presence") or {}),
                        "suspicious_zero_session": row.get("suspicious_zero_session") is True,
                    },
                )
        return {
            "schema_version": SCHEMA_VERSION,
            "provider": PROVIDER,
            "source_endpoint": SOURCE_ENDPOINT,
            "scope": "symbol",
            "captured_at": captured_at,
            "symbols": symbols,
        }

    def _sanitize_history(
        self,
        history: Mapping[str, Any],
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        clean: Dict[str, Dict[str, Dict[str, Any]]] = {}
        symbols = sorted(
            (
                (symbol, rows)
                for raw_symbol, rows in history.items()
                if (symbol := _safe_symbol(raw_symbol)) is not None
                and isinstance(rows, Mapping)
            ),
            key=lambda item: item[0],
        )[: self.max_symbols]
        for symbol, rows in symbols:
            accepted: Dict[str, Dict[str, Any]] = {}
            for raw_date, raw_row in rows.items():
                row = _safe_row(raw_row)
                if row is None or row["trading_date"] != _safe_date(raw_date):
                    continue
                accepted[row["trading_date"]] = row
            bounded_dates = sorted(accepted)[-self.max_rows_per_symbol :]
            if bounded_dates:
                clean[symbol] = {
                    trading_date: deepcopy(accepted[trading_date])
                    for trading_date in bounded_dates
                }
        return clean

    def _atomic_write(self, document: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(
                    document,
                    handle,
                    ensure_ascii=True,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
