"""Process-local last-known-good VN30 membership shared by flow surfaces."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, Iterable, Mapping, Optional


_LOCK = RLock()
_MEMBERSHIPS: Dict[str, Dict[str, Any]] = {}
_MAX_MEMBERS = 30


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _symbols(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        symbol = str(value or "").strip().upper()
        if symbol.endswith(".VN"):
            symbol = symbol[:-3]
        if (
            not symbol
            or not symbol.isalnum()
            or len(symbol) > 10
            or symbol in seen
        ):
            continue
        seen.add(symbol)
        result.append(symbol)
    return result


def remember_vn30_membership(
    symbols: Iterable[Any],
    *,
    classifications: Optional[Mapping[str, Mapping[str, Any]]] = None,
    source: str = "SSI IndexComponents",
    provider_effective_date: Optional[str] = None,
    fetched_at: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Replace retained membership only with one bounded, non-empty cohort."""

    normalized = _symbols(symbols)
    if not normalized or len(normalized) > _MAX_MEMBERS:
        return None
    validated_at = (now or _utc_now()).astimezone(timezone.utc)
    clean_classifications: Dict[str, Dict[str, str]] = {}
    for symbol in normalized:
        row = dict((classifications or {}).get(symbol) or {})
        code = str(row.get("icb_code") or "").strip()
        name = str(row.get("icb_name") or "").strip()
        if code and name:
            clean_classifications[symbol] = {
                "icb_code": code,
                "icb_name": name,
            }
    snapshot = {
        "index_code": "VN30",
        "symbols": normalized,
        "classifications": clean_classifications,
        "source": str(source or "SSI IndexComponents"),
        "provider_effective_date": (
            str(provider_effective_date).strip()
            if provider_effective_date
            else None
        ),
        "fetched_at": str(fetched_at or validated_at.isoformat()),
        "validated_at": validated_at.isoformat(),
        "validated_epoch": validated_at.timestamp(),
        "member_count": len(normalized),
    }
    with _LOCK:
        _MEMBERSHIPS["VN30"] = deepcopy(snapshot)
    return deepcopy(snapshot)


def get_last_known_vn30_membership(
    *,
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Return the retained valid cohort with a computed process-local age."""

    with _LOCK:
        snapshot = deepcopy(_MEMBERSHIPS.get("VN30"))
    if snapshot is None:
        return None
    current = (now or _utc_now()).astimezone(timezone.utc)
    snapshot["age_seconds"] = max(
        0,
        int(current.timestamp() - float(snapshot.get("validated_epoch") or 0)),
    )
    return snapshot


def reset_last_known_vn30_membership() -> None:
    """Clear retained membership for deterministic tests."""

    with _LOCK:
        _MEMBERSHIPS.clear()
