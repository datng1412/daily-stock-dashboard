"""Atomic durable storage for verified manual HOSE proprietary-flow EOD rows."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, Mapping, Optional


SCHEMA_VERSION = 1
DEFAULT_FILENAME = "vietnam_proprietary_flow_eod.v1.json"
EVIDENCE_RANK = {
    "INSUFFICIENT": 0,
    "OFFICIAL_URL_USER_VERIFIED": 1,
    "OFFICIAL_PDF_HASHED": 2,
}


class ProprietaryFlowStoreError(RuntimeError):
    """Raised when the durable store cannot be read or written safely."""


class ProprietaryFlowConflictError(ValueError):
    """Raised when an existing exchange/session row cannot be overwritten."""


def resolve_vietnam_proprietary_flow_eod_path(
    path: Optional[str | Path] = None,
) -> Path:
    if path is not None:
        return Path(path).expanduser().resolve()
    repository_root = Path(__file__).resolve().parents[2]
    cache_dir = Path(os.environ.get("DATA_CACHE_DIR") or "data/cache").expanduser()
    if not cache_dir.is_absolute():
        cache_dir = repository_root / cache_dir
    return (cache_dir / DEFAULT_FILENAME).resolve()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _valid_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _safe_row(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, Mapping):
        return None
    if value.get("exchange") != "HOSE" or not _valid_date(value.get("trading_date")):
        return None
    required_ints = ("buy_value", "sell_value", "net_value")
    if any(isinstance(value.get(key), bool) or not isinstance(value.get(key), int) for key in required_ints):
        return None
    if value["buy_value"] < 0 or value["sell_value"] < 0:
        return None
    if value["net_value"] != value["buy_value"] - value["sell_value"]:
        return None
    volume_values = [value.get(key) for key in ("buy_volume", "sell_volume", "net_volume")]
    if any(item is not None for item in volume_values):
        if any(isinstance(item, bool) or not isinstance(item, int) for item in volume_values):
            return None
        if volume_values[0] < 0 or volume_values[1] < 0 or volume_values[2] != volume_values[0] - volume_values[1]:
            return None
    evidence = value.get("source_evidence_strength")
    if evidence not in EVIDENCE_RANK or evidence == "INSUFFICIENT":
        return None
    if value.get("source_type") != "official_exchange_pdf_manual_entry":
        return None
    if value.get("finality") != "completed_daily" or value.get("verified_by_user") is not True:
        return None
    source_url = value.get("source_url")
    if not isinstance(source_url, str) or not source_url:
        return None
    allowed = {
        "trading_date", "exchange", "buy_volume", "sell_volume", "net_volume",
        "buy_value", "sell_value", "net_value", "source_type", "source_url",
        "source_title", "source_file_name", "source_file_hash", "source_file_size",
        "source_evidence_strength", "verified_by_user", "imported_at", "finality",
        "complete_value", "complete_volume", "complete", "data_quality", "warnings",
        "replacement_reason", "replaced_at", "previous_source_file_hash",
        "previous_imported_at",
    }
    row = {key: deepcopy(value.get(key)) for key in allowed}
    row["warnings"] = [
        str(item)[:160]
        for item in (value.get("warnings") if isinstance(value.get("warnings"), list) else [])
        if isinstance(item, str)
    ][:10]
    return row


def _material_values(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(row.get(key) for key in (
        "exchange", "trading_date", "buy_value", "sell_value", "net_value",
        "buy_volume", "sell_volume", "net_volume", "source_file_hash",
    ))


class VietnamProprietaryFlowEodStore:
    """Separate, deterministic JSON store keyed by exchange and trading date."""

    def __init__(self, path: Optional[str | Path] = None) -> None:
        self.path = resolve_vietnam_proprietary_flow_eod_path(path)
        self.status = "not_loaded"
        self.last_error: Optional[str] = None

    def load(self) -> list[Dict[str, Any]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.status = "missing"
            self.last_error = None
            return []
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.status = "invalid"
            self.last_error = "invalid_store"
            raise ProprietaryFlowStoreError("proprietary-flow EOD store is unreadable") from exc
        if not isinstance(raw, Mapping) or raw.get("schema_version") != SCHEMA_VERSION or not isinstance(raw.get("rows"), list):
            self.status = "invalid"
            self.last_error = "schema_mismatch"
            raise ProprietaryFlowStoreError("proprietary-flow EOD store schema mismatch")
        rows = [_safe_row(item) for item in raw["rows"]]
        if any(item is None for item in rows):
            self.status = "invalid"
            self.last_error = "invalid_row"
            raise ProprietaryFlowStoreError("proprietary-flow EOD store contains an invalid row")
        clean = sorted((item for item in rows if item is not None), key=lambda item: (item["exchange"], item["trading_date"]))
        self.status = "loaded"
        self.last_error = None
        return clean

    def persist(
        self,
        candidate: Mapping[str, Any],
        *,
        replace: bool = False,
        replacement_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        row = _safe_row(candidate)
        if row is None:
            raise ValueError("candidate is not a persistable canonical EOD row")
        rows = self.load()
        index = next((i for i, item in enumerate(rows) if item["exchange"] == row["exchange"] and item["trading_date"] == row["trading_date"]), None)
        if index is None:
            rows.append(row)
            self._write(rows)
            return {"persisted": True, "idempotent": False, "replaced": False, "row_count": len(rows), "row": deepcopy(row)}
        previous = rows[index]
        if _material_values(previous) == _material_values(row):
            return {"persisted": False, "idempotent": True, "replaced": False, "row_count": len(rows), "row": deepcopy(previous)}
        if not replace:
            raise ProprietaryFlowConflictError("a different row already exists for HOSE on this trading date")
        reason = str(replacement_reason or "").strip()
        if not reason:
            raise ProprietaryFlowConflictError("replacement_reason is required")
        if EVIDENCE_RANK[row["source_evidence_strength"]] < EVIDENCE_RANK[previous["source_evidence_strength"]]:
            raise ProprietaryFlowConflictError("weaker source evidence cannot replace stronger evidence")
        if previous.get("complete_value") is True and row.get("complete_value") is not True:
            raise ProprietaryFlowConflictError("an incomplete value row cannot replace a complete value row")
        row.update(
            data_quality="replacement",
            replacement_reason=reason[:240],
            replaced_at=_now_iso(),
            previous_source_file_hash=previous.get("source_file_hash"),
            previous_imported_at=previous.get("imported_at"),
        )
        rows[index] = row
        self._write(rows)
        return {"persisted": True, "idempotent": False, "replaced": True, "row_count": len(rows), "row": deepcopy(row)}

    def _write(self, rows: list[Mapping[str, Any]]) -> None:
        document = {
            "schema_version": SCHEMA_VERSION,
            "updated_at": _now_iso(),
            "rows": sorted((deepcopy(dict(row)) for row in rows), key=lambda item: (item["exchange"], item["trading_date"])),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(document, handle, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            temporary = None
            self.status = "written"
            self.last_error = None
        except (OSError, TypeError, ValueError) as exc:
            self.status = "write_error"
            self.last_error = "write_error"
            raise ProprietaryFlowStoreError("proprietary-flow EOD store write failed") from exc
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def diagnostics(self) -> Dict[str, Any]:
        return {"status": self.status, "last_error": self.last_error, "schema_version": SCHEMA_VERSION}
