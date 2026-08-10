"""Validation and read model for verified manual HOSE proprietary-flow EOD."""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
from pathlib import Path
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from src.services.vietnam_proprietary_flow_eod_store import (
    ProprietaryFlowStoreError,
    VietnamProprietaryFlowEodStore,
)


class ProprietaryFlowValidationError(ValueError):
    """Raised when a manual candidate violates the canonical contract."""


def _integer(name: str, value: Any, *, nonnegative: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProprietaryFlowValidationError(f"{name} must be an integer")
    if nonnegative and value < 0:
        raise ProprietaryFlowValidationError(f"{name} must be nonnegative")
    return value


def _clean_text(value: Any, limit: int) -> Optional[str]:
    if value is None:
        return None
    clean = " ".join(str(value).split()).strip()
    return clean[:limit] or None


class VietnamProprietaryFlowEodService:
    """Network-free service. The CLI is its only production write owner."""

    def __init__(self, store: Optional[VietnamProprietaryFlowEodStore] = None) -> None:
        self.store = store or VietnamProprietaryFlowEodStore()

    @staticmethod
    def validate_exchange(exchange: str) -> str:
        normalized = str(exchange or "").strip().upper()
        if normalized != "HOSE":
            raise ProprietaryFlowValidationError("exchange must be HOSE")
        return normalized

    def validate_candidate(
        self,
        *,
        trading_date: str,
        exchange: str,
        buy_value: int,
        sell_value: int,
        source_url: str,
        verified_by_user: bool,
        source_file: Optional[str | Path] = None,
        source_file_unavailable: bool = False,
        source_title: Optional[str] = None,
        net_value: Optional[int] = None,
        buy_volume: Optional[int] = None,
        sell_volume: Optional[int] = None,
        net_volume: Optional[int] = None,
        for_persist: bool = False,
    ) -> Dict[str, Any]:
        try:
            parsed_date = date.fromisoformat(str(trading_date))
        except ValueError as exc:
            raise ProprietaryFlowValidationError("date must use YYYY-MM-DD") from exc
        normalized_exchange = self.validate_exchange(exchange)
        buy = _integer("buy_value", buy_value, nonnegative=True)
        sell = _integer("sell_value", sell_value, nonnegative=True)
        derived_net = buy - sell
        if net_value is not None and _integer("net_value", net_value) != derived_net:
            raise ProprietaryFlowValidationError("net_value must equal buy_value - sell_value")
        if (buy_volume is None) != (sell_volume is None):
            raise ProprietaryFlowValidationError("buy_volume and sell_volume must be supplied together")
        if buy_volume is None:
            if net_volume is not None:
                raise ProprietaryFlowValidationError("net_volume requires buy_volume and sell_volume")
            buy_vol = sell_vol = derived_net_volume = None
        else:
            buy_vol = _integer("buy_volume", buy_volume, nonnegative=True)
            sell_vol = _integer("sell_volume", sell_volume, nonnegative=True)
            derived_net_volume = buy_vol - sell_vol
            if net_volume is not None and _integer("net_volume", net_volume) != derived_net_volume:
                raise ProprietaryFlowValidationError("net_volume must equal buy_volume - sell_volume")
        clean_url = str(source_url or "").strip()
        parsed_url = urlparse(clean_url)
        if not clean_url or parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ProprietaryFlowValidationError("source_url must be a non-empty HTTP(S) URL")
        if for_persist and verified_by_user is not True:
            raise ProprietaryFlowValidationError("persist requires --verified-by-user")

        file_name = file_hash = None
        file_size: Optional[int] = None
        evidence = "INSUFFICIENT"
        warnings: list[str] = []
        if source_file is not None:
            path = Path(source_file).expanduser()
            if not path.is_file():
                raise ProprietaryFlowValidationError("source_file does not exist")
            if path.suffix.casefold() != ".pdf":
                raise ProprietaryFlowValidationError("source_file must be a PDF")
            hasher = hashlib.sha256()
            file_size = 0
            with path.open("rb") as handle:
                signature = handle.read(5)
                if signature != b"%PDF-":
                    raise ProprietaryFlowValidationError("source_file has an invalid PDF signature")
                hasher.update(signature)
                file_size += len(signature)
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    hasher.update(chunk)
                    file_size += len(chunk)
            file_name = re.sub(r"[^A-Za-z0-9._ -]", "_", path.name)[:160]
            file_hash = hasher.hexdigest()
            evidence = "OFFICIAL_PDF_HASHED"
        elif source_file_unavailable and verified_by_user is True:
            evidence = "OFFICIAL_URL_USER_VERIFIED"
            warnings.append("source_pdf_unavailable_hash_not_recorded")
        else:
            warnings.append("source_evidence_insufficient_for_persistence")
        if for_persist and evidence == "INSUFFICIENT":
            raise ProprietaryFlowValidationError("persist without a PDF requires --source-file-unavailable")

        complete_volume = buy_vol is not None and sell_vol is not None
        return {
            "trading_date": parsed_date.isoformat(),
            "exchange": normalized_exchange,
            "buy_volume": buy_vol,
            "sell_volume": sell_vol,
            "net_volume": derived_net_volume,
            "buy_value": buy,
            "sell_value": sell,
            "net_value": derived_net,
            "source_type": "official_exchange_pdf_manual_entry",
            "source_url": clean_url,
            "source_title": _clean_text(source_title, 240),
            "source_file_name": file_name,
            "source_file_hash": file_hash,
            "source_file_size": file_size,
            "source_evidence_strength": evidence,
            "verified_by_user": verified_by_user is True,
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "finality": "completed_daily",
            "complete_value": True,
            "complete_volume": complete_volume,
            "complete": True,
            "data_quality": "accepted" if complete_volume else "accepted_value_only",
            "warnings": warnings,
        }

    def preview_candidate(self, **kwargs: Any) -> Dict[str, Any]:
        row = self.validate_candidate(**kwargs, for_persist=False)
        return {"operation": "dry_run", "accepted": True, "would_persist": False, **row, "conflicts": []}

    def persist_candidate(
        self,
        *,
        replace: bool = False,
        replacement_reason: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        row = self.validate_candidate(**kwargs, for_persist=True)
        result = self.store.persist(row, replace=replace, replacement_reason=replacement_reason)
        return {
            "operation": "persist",
            **{key: result[key] for key in ("persisted", "idempotent", "replaced", "row_count")},
            "store_path": str(self.store.path),
            "trading_date": result["row"]["trading_date"],
            "exchange": result["row"]["exchange"],
        }

    def get_latest(self, exchange: str = "HOSE") -> Dict[str, Any]:
        normalized = self.validate_exchange(exchange)
        try:
            rows = [row for row in self.store.load() if row["exchange"] == normalized]
        except ProprietaryFlowStoreError:
            return self._latest_response(normalized, None, "storage_error")
        latest = rows[-1] if rows else None
        return self._latest_response(normalized, latest, self._state(latest))

    def get_history(self, exchange: str = "HOSE", limit: int = 60) -> Dict[str, Any]:
        normalized = self.validate_exchange(exchange)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 250:
            raise ProprietaryFlowValidationError("limit must be between 1 and 250")
        try:
            rows = [row for row in self.store.load() if row["exchange"] == normalized][-limit:]
        except ProprietaryFlowStoreError:
            rows = []
            state = "storage_error"
        else:
            state = self._state(rows[-1] if rows else None)
        return {
            "status": "ok" if rows else ("error" if state == "storage_error" else "empty"),
            "data_state": state,
            "exchange": normalized,
            "count": len(rows),
            "series": rows,
            "source_summary": {
                "source_type": "official_exchange_pdf_manual_entry",
                "finality": "completed_daily",
                "value_unit": "VND",
                "volume_unit": "shares",
            },
            "warnings": ["durable_store_unavailable"] if state == "storage_error" else [],
        }

    def get_data_state(self, exchange: str = "HOSE") -> str:
        return self.get_latest(exchange)["data_state"]

    @staticmethod
    def _state(row: Optional[Dict[str, Any]]) -> str:
        if row is None:
            return "no_data"
        if row.get("data_quality") == "suspicious":
            return "suspicious"
        if row.get("complete_value") is not True:
            return "incomplete"
        return "ready"

    @staticmethod
    def _latest_response(exchange: str, row: Optional[Dict[str, Any]], state: str) -> Dict[str, Any]:
        return {
            "status": "ok" if row else ("error" if state == "storage_error" else "empty"),
            "data_state": state,
            "exchange": exchange,
            "latest": row,
            "source": "official_exchange_pdf_manual_entry",
            "warnings": ["durable_store_unavailable"] if state == "storage_error" else [],
        }
