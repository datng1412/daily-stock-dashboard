# -*- coding: utf-8 -*-
"""Corporate-actions provider contract for VN dashboard future adapters.

This module defines a normalized, source-labeled contract only. It does not
call VNStocks, FiinGroup, public websites, broker APIs, or any external system.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Protocol


CORPORATE_ACTION_PROVIDER_SOURCE = "CorporateActionsProvider"
CORPORATE_ACTION_DISABLED_SOURCE = "CorporateActionsProvider disabled"
CORPORATE_ACTIONS_DISABLED_REASON = "Corporate actions provider disabled."
CORPORATE_ACTIONS_NOT_CONFIGURED_REASON = "Corporate actions provider not configured."
CORPORATE_ACTIONS_UNAVAILABLE_REASON = "Corporate action calendar unavailable."
CORPORATE_ACTIONS_NOT_IMPLEMENTED_REASON = "Corporate actions provider adapter not implemented."

CORPORATE_ACTION_PROVIDER_STATUSES = {
    "disabled",
    "not_configured",
    "not_implemented",
    "unavailable",
    "partial",
    "ok",
    "error",
}

CORPORATE_ACTION_EVENT_TYPES = {
    "cash_dividend",
    "stock_dividend",
    "bonus_share",
    "rights_issue",
    "stock_split",
    "merger",
    "listing_change",
    "meeting",
    "other",
    "unknown",
}

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)(access[_-]?token\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(refresh[_-]?token\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(secret\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(consumer[_-]?secret\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(account[_-]?id\s*[:=]\s*)[^\s,;]+"),
)


def utc_now_iso() -> str:
    """Return a UTC ISO timestamp for contract diagnostics."""
    return datetime.now(timezone.utc).isoformat()


def sanitize_corporate_actions_text(value: Any, *, max_length: int = 240) -> str:
    """Return a bounded, secret-safe diagnostic string."""
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r"\1<redacted>", text)
    if len(text) > max_length:
        text = text[: max_length - 3].rstrip() + "..."
    return text or "unknown corporate-actions error"


def normalize_provider_status(value: Any, *, default: str = "unavailable") -> str:
    """Normalize provider status to the public contract vocabulary."""
    status = str(value or "").strip().lower()
    return status if status in CORPORATE_ACTION_PROVIDER_STATUSES else default


def normalize_event_type(value: Any) -> str:
    """Normalize event type to the contract vocabulary."""
    event_type = str(value or "").strip().lower()
    aliases = {
        "split": "stock_split",
        "stock split": "stock_split",
        "rights": "rights_issue",
        "right_issue": "rights_issue",
        "bonus": "bonus_share",
        "dividend": "cash_dividend",
    }
    event_type = aliases.get(event_type, event_type)
    return event_type if event_type in CORPORATE_ACTION_EVENT_TYPES else "unknown"


@dataclass(frozen=True)
class CorporateActionEvent:
    """Normalized corporate-action event row.

    Most fields are optional because provider coverage varies. A future adapter
    must retain provenance and leave missing values as ``None`` instead of
    inferring events from price gaps.
    """

    ticker: str
    event_id: Optional[str] = None
    event_type: str = "unknown"
    event_subtype: Optional[str] = None
    title: Optional[str] = None
    announcement_date: Optional[str] = None
    ex_date: Optional[str] = None
    record_date: Optional[str] = None
    payment_date: Optional[str] = None
    effective_date: Optional[str] = None
    cash_dividend_per_share: Optional[float] = None
    cash_dividend_currency: Optional[str] = None
    stock_dividend_ratio: Optional[str] = None
    bonus_share_ratio: Optional[str] = None
    rights_issue_ratio: Optional[str] = None
    rights_issue_price: Optional[float] = None
    split_ratio: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    source_document_url: Optional[str] = None
    provider: Optional[str] = None
    provider_event_id: Optional[str] = None
    last_updated: Optional[str] = None
    raw_available: bool = False
    confidence: Optional[float] = None
    status: str = "unknown"
    missing_fields: List[str] = field(default_factory=list)
    # Backward-compatible fields already consumed by the VN dashboard.
    rights_ratio: Optional[str] = None
    description: Optional[str] = None
    last_checked_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return an API-safe event row with normalized type and aliases."""
        row = asdict(self)
        row["ticker"] = str(row.get("ticker") or "").strip().upper()
        row["event_type"] = normalize_event_type(row.get("event_type"))
        if not row.get("rights_ratio") and row.get("rights_issue_ratio"):
            row["rights_ratio"] = row["rights_issue_ratio"]
        if not row.get("description") and row.get("title"):
            row["description"] = row["title"]
        return row


class CorporateActionsProvider(Protocol):
    """Protocol implemented by future corporate-actions adapters."""

    provider_name: str

    def fetch_corporate_actions(self, tickers: Iterable[str], *, months_back: int) -> Dict[str, Any]:
        """Return normalized corporate-action rows for requested VN tickers."""


class DisabledCorporateActionsProvider:
    """Default provider that never performs external I/O."""

    provider_name = "disabled"

    def fetch_corporate_actions(self, tickers: Iterable[str], *, months_back: int) -> Dict[str, Any]:
        checked_at = utc_now_iso()
        requested = [str(ticker or "").strip().upper() for ticker in tickers or [] if str(ticker or "").strip()]
        return {
            "market": "VN",
            "status": "disabled",
            "source": CORPORATE_ACTION_DISABLED_SOURCE,
            "provider": self.provider_name,
            "last_checked_at": checked_at,
            "requested_tickers": requested,
            "months_back": months_back,
            "events": [],
            "items": [],
            "error": CORPORATE_ACTIONS_DISABLED_REASON,
            "error_detail": (
                "No verified Vietnam corporate-action event provider is enabled. "
                "Events are not inferred from reference prices, adjusted prices, price gaps, or OHLCV changes."
            ),
            "diagnostics": {
                "provider": self.provider_name,
                "request_domain": "corporate_actions",
                "status": "disabled",
                "row_count": 0,
                "failure_class": "provider_disabled",
                "last_checked_at": checked_at,
                "requested_tickers_count": len(requested),
            },
        }


class NotConfiguredCorporateActionsProvider:
    """Classification wrapper for future provider names with no adapter yet."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = str(provider_name or "unknown").strip().lower() or "unknown"

    def fetch_corporate_actions(self, tickers: Iterable[str], *, months_back: int) -> Dict[str, Any]:
        checked_at = utc_now_iso()
        requested = [str(ticker or "").strip().upper() for ticker in tickers or [] if str(ticker or "").strip()]
        return {
            "market": "VN",
            "status": "not_configured",
            "source": CORPORATE_ACTION_PROVIDER_SOURCE,
            "provider": self.provider_name,
            "last_checked_at": checked_at,
            "requested_tickers": requested,
            "months_back": months_back,
            "events": [],
            "items": [],
            "error": CORPORATE_ACTIONS_NOT_CONFIGURED_REASON,
            "error_detail": (
                f"{self.provider_name} corporate-actions adapter is not implemented or authorized. "
                "No external provider was called."
            ),
            "diagnostics": {
                "provider": self.provider_name,
                "request_domain": "corporate_actions",
                "status": "not_configured",
                "row_count": 0,
                "failure_class": "provider_not_configured",
                "last_checked_at": checked_at,
                "requested_tickers_count": len(requested),
            },
        }

