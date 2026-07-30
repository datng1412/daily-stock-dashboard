# -*- coding: utf-8 -*-
"""Bounded SSI DailyStockPrice history for one VN symbol's foreign flow."""

from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import logging
import math
import re
from threading import RLock
from time import perf_counter
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

from data_provider.ssi_provider_protocol import SsiRestProvider
from data_provider.ssi_provider_router import (
    SsiRestProviderRouter,
    create_ssi_rest_provider_router,
)
from src.services.vietnam_foreign_flow_history_store import (
    VietnamForeignFlowHistoryStore,
)


logger = logging.getLogger(__name__)

SOURCE = "ssi_fastconnect"
SOURCE_ENDPOINT = "daily_stock_price"
VOLUME_UNIT = "shares"
VALUE_UNIT = "VND"
FINALITY = "daily_available"
DEFAULT_LIMIT = 20
MAX_ROWS = 120
MAX_DATE_RANGE_DAYS = 168
MAX_RECENT_LOOKBACK_DAYS = 200
CACHE_VERSION = "v5-vn30-decomposition-fallback"
POSITIVE_CURRENT_TTL_SECONDS = 300
POSITIVE_COMPLETED_TTL_SECONDS = 3_600
EMPTY_TTL_SECONDS = 60
NEGATIVE_TTL_SECONDS = 30
STALE_MAX_SECONDS = 86_400
CACHE_MAX_ENTRIES = 512
BATCH_MAX_TICKERS = 30
BATCH_DEFAULT_TOP_N = 5
BATCH_MAX_TOP_N = 10
BATCH_MAX_CONCURRENCY = 4
WATCHLIST_ALLOWED_SESSIONS = frozenset({1, 5, 20, 60})
WATCHLIST_PER_TICKER_TIMEOUT_SECONDS = 20.0
WATCHLIST_TOTAL_TIMEOUT_SECONDS = 45.0
PROVIDER_VERSION = "v3"
VN30_INDEX_CODE = "VN30"
VN30_HISTORY_SESSIONS = 60
VN30_AGGREGATE_CACHE_TTL_SECONDS = 300
VN30_AGGREGATE_NEGATIVE_CACHE_TTL_SECONDS = 60
VN30_AGGREGATE_CACHE_MAX_ENTRIES = 16
VN30_PUBLIC_SOURCE_ENDPOINT = "DailyStockPrice"
VN30_CANONICAL_ENDPOINT = "securitiesSummary?index="
VN30_CANONICAL_MODE = "DIRECT_INDEX_CANONICAL"
VN30_DECOMPOSITION_MODE = "CURRENT_MEMBERSHIP_DECOMPOSITION"
VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
_SAFE_FAILURE_CLASSES = {
    "auth_failed",
    "permission_denied",
    "rate_limited",
    "network_error",
    "timeout",
    "parse_failed",
    "empty_response",
    "provider_unavailable",
    "provider_exception",
}


@dataclass
class _CacheEntry:
    payload: Dict[str, Any]
    kind: str
    fetched_at: datetime
    expires_at: datetime
    stale_until: datetime


_LOCK = RLock()
_ACCEPTED_HISTORY_PERSIST_LOCK = RLock()
_CACHE: "OrderedDict[Tuple[Any, ...], _CacheEntry]" = OrderedDict()
_ACCEPTED_HISTORY: Dict[str, Dict[str, Dict[str, Any]]] = {}
_ACCEPTED_HISTORY_LOADED_PATHS: set[str] = set()
_IN_FLIGHT: Dict[Tuple[Any, ...], Future] = {}
_WAITERS: Dict[Tuple[Any, ...], int] = {}
_VN30_CACHE: "OrderedDict[Tuple[Any, ...], _CacheEntry]" = OrderedDict()
_VN30_IN_FLIGHT: Dict[Tuple[Any, ...], Future] = {}
_VN30_WAITERS: Dict[Tuple[Any, ...], int] = {}
_METRIC_DEFAULTS: Dict[str, Any] = {
    "scope": "process_local",
    "endpoint_requests": 0,
    "recent_session_requests": 0,
    "date_range_requests": 0,
    "force_refresh_requests": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "empty_cache_hits": 0,
    "negative_cache_hits": 0,
    "stale_recoveries": 0,
    "provider_calls": 0,
    "provider_successes": 0,
    "provider_empty_results": 0,
    "provider_failures": 0,
    "provider_latency_count": 0,
    "provider_latency_total_ms": 0,
    "provider_latency_max_ms": 0,
    "normalized_rows": 0,
    "rejected_rows": 0,
    "duplicate_date_count": 0,
    "net_volume_fallback_count": 0,
    "net_value_fallback_count": 0,
    "net_volume_mismatch_count": 0,
    "net_value_mismatch_count": 0,
    "active_in_flight": 0,
    "coalesced_waiters": 0,
    "max_coalesced_waiters": 0,
    "unavailable_results": 0,
    "last_success_at": None,
    "last_failure_class": None,
    "batch_requests": 0,
    "batch_force_refresh_requests": 0,
    "batch_requested_symbols": 0,
    "batch_normalized_symbols": 0,
    "batch_usable_symbols": 0,
    "batch_stale_symbols": 0,
    "batch_empty_symbols": 0,
    "batch_unavailable_symbols": 0,
    "batch_ready_results": 0,
    "batch_partial_results": 0,
    "batch_stale_results": 0,
    "batch_empty_results": 0,
    "batch_unavailable_results": 0,
    "batch_latency_count": 0,
    "batch_latency_total_ms": 0,
    "batch_latency_max_ms": 0,
    "batch_active_requests": 0,
    "batch_max_active_requests": 0,
    "ranking_build_count": 0,
    "ranking_eligible_values": 0,
    "ranking_excluded_null_values": 0,
    "ranking_excluded_zero_values": 0,
    "vn30_requests": 0,
    "vn30_force_refresh_requests": 0,
    "vn30_membership_unavailable_results": 0,
    "vn30_cache_hits": 0,
    "vn30_cache_misses": 0,
    "vn30_negative_cache_hits": 0,
    "vn30_coalesced_waiters": 0,
    "vn30_active_in_flight": 0,
    "vn30_component_histories": 0,
    "vn30_usable_components": 0,
    "vn30_stale_components": 0,
    "vn30_empty_components": 0,
    "vn30_unavailable_components": 0,
    "vn30_ready_results": 0,
    "vn30_partial_results": 0,
    "vn30_stale_results": 0,
    "vn30_unavailable_results": 0,
    "vn30_latency_count": 0,
    "vn30_latency_total_ms": 0,
    "vn30_latency_max_ms": 0,
}
_METRICS = deepcopy(_METRIC_DEFAULTS)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().isoformat()


def _metric_add(name: str, amount: int = 1) -> None:
    with _LOCK:
        _METRICS[name] += amount


def reset_vietnam_foreign_flow_state() -> None:
    """Reset process-local cache and counters for deterministic tests."""
    with _LOCK:
        _CACHE.clear()
        _ACCEPTED_HISTORY.clear()
        _ACCEPTED_HISTORY_LOADED_PATHS.clear()
        _IN_FLIGHT.clear()
        _WAITERS.clear()
        _VN30_CACHE.clear()
        _VN30_IN_FLIGHT.clear()
        _VN30_WAITERS.clear()
        _METRICS.clear()
        _METRICS.update(deepcopy(_METRIC_DEFAULTS))


def vietnam_foreign_flow_observability_snapshot() -> Dict[str, Any]:
    """Return counters only; this function performs no provider or cache work."""
    with _LOCK:
        return deepcopy(_METRICS)


def accepted_vietnam_foreign_flow_history(
    tickers: Iterable[str],
) -> Dict[str, List[Dict[str, Any]]]:
    """Read accepted completed rows without provider work or cache mutation."""

    normalized = [_normalize_ticker(ticker) for ticker in tickers]
    with _LOCK:
        return {
            ticker: [
                deepcopy(_ACCEPTED_HISTORY[ticker][trading_date])
                for trading_date in sorted(_ACCEPTED_HISTORY.get(ticker, {}))
            ]
            for ticker in normalized
        }


def _merge_accepted_history(
    history: Dict[str, Dict[str, Dict[str, Any]]],
) -> int:
    merged_rows = 0
    with _LOCK:
        for ticker, rows_by_date in history.items():
            accepted = _ACCEPTED_HISTORY.setdefault(ticker, {})
            for trading_date, row in rows_by_date.items():
                accepted[trading_date] = deepcopy(row)
                merged_rows += 1
            for old_date in sorted(accepted)[:-MAX_ROWS]:
                accepted.pop(old_date, None)
    return merged_rows


def initialize_vietnam_foreign_flow_accepted_history(
    store: Optional[VietnamForeignFlowHistoryStore] = None,
) -> Dict[str, Any]:
    """Best-effort startup restore with no provider or streaming work."""

    selected = store or VietnamForeignFlowHistoryStore()
    identity = selected.identity
    with _ACCEPTED_HISTORY_PERSIST_LOCK:
        with _LOCK:
            if identity in _ACCEPTED_HISTORY_LOADED_PATHS:
                return {
                    "restored_rows": 0,
                    **selected.diagnostics(),
                    "load_state": "already_loaded",
                }
        restored = selected.load()
        restored_rows = _merge_accepted_history(restored)
        with _LOCK:
            _ACCEPTED_HISTORY_LOADED_PATHS.add(identity)
        return {
            **selected.diagnostics(),
            "restored_rows": restored_rows,
            "load_state": selected.status,
        }


def _normalize_ticker(value: str) -> str:
    ticker = str(value or "").strip().upper()
    if ticker.endswith(".VN"):
        ticker = ticker[:-3]
    if not re.fullmatch(r"[A-Z0-9]{1,10}", ticker):
        raise ValueError("ticker must contain 1 to 10 uppercase letters or digits")
    return ticker


def normalize_vietnam_foreign_flow_tickers(values: Iterable[str]) -> Tuple[List[str], List[str]]:
    """Return trimmed request values and normalized unique VN tickers."""
    requested = [str(value or "").strip() for value in values]
    if not requested:
        raise ValueError("tickers must contain at least one symbol")
    normalized: List[str] = []
    seen = set()
    for raw in requested:
        ticker = _normalize_ticker(raw)
        if ticker == "ALL":
            raise ValueError("ALL is not a supported foreign-flow batch symbol")
        if ticker in seen:
            continue
        seen.add(ticker)
        normalized.append(ticker)
    if len(normalized) > BATCH_MAX_TICKERS:
        raise ValueError(f"tickers cannot contain more than {BATCH_MAX_TICKERS} normalized unique symbols")
    return requested, normalized


def _parse_iso_date(value: Optional[str], field_name: str) -> Optional[date]:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format") from exc


def _nullable_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not number.is_finite() or number != number.to_integral_value():
        return None
    return int(number)


def _valid_date(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _safe_failure_class(value: Any) -> str:
    normalized = str(value or "provider_unavailable").strip().lower()
    return normalized if normalized in _SAFE_FAILURE_CLASSES else "provider_unavailable"


def _public_failure_class(value: Any) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    aliases = {
        "auth_failed": "authentication",
        "authentication": "authentication",
        "permission_denied": "authorization",
        "authorization": "authorization",
        "timeout": "timeout",
        "package_unavailable": "package_unavailable",
        "unsupported": "unsupported",
        "network_error": "provider_unavailable",
        "rate_limited": "provider_unavailable",
        "parse_failed": "provider_unavailable",
        "empty_response": "provider_unavailable",
        "provider_exception": "provider_unavailable",
        "provider_unavailable": "provider_unavailable",
        "validation": "validation",
    }
    return aliases.get(normalized, "unknown")


def _normalize_rows(rows: Optional[Iterable[Dict[str, Any]]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    by_date: Dict[str, Dict[str, Any]] = {}
    stats = {
        "normalized_rows": 0,
        "rejected_rows": 0,
        "duplicate_date_count": 0,
        "net_volume_fallback_count": 0,
        "net_value_fallback_count": 0,
        "net_volume_mismatch_count": 0,
        "net_value_mismatch_count": 0,
    }
    for raw in rows or []:
        if not isinstance(raw, dict):
            stats["rejected_rows"] += 1
            continue
        # Exclude only an actual current-session row. The latest provider
        # session before today is eligible as completed-session data.
        if raw.get("foreign_finality") == "current_session_provisional":
            stats["rejected_rows"] += 1
            continue
        trading_date = _valid_date(raw.get("date"))
        if trading_date is None:
            stats["rejected_rows"] += 1
            continue
        buy_volume = _nullable_int(raw.get("foreign_buy_volume"))
        sell_volume = _nullable_int(raw.get("foreign_sell_volume"))
        buy_value = _nullable_int(raw.get("foreign_buy_value"))
        sell_value = _nullable_int(raw.get("foreign_sell_value"))
        net_volume = _nullable_int(raw.get("foreign_net_volume"))
        net_value = _nullable_int(raw.get("foreign_net_value"))
        volume_source = raw.get("_foreign_net_volume_source")
        value_source = raw.get("_foreign_net_value_source")
        if net_volume is None and buy_volume is not None and sell_volume is not None:
            net_volume = buy_volume - sell_volume
            volume_source = "derived"
        if net_value is None and buy_value is not None and sell_value is not None:
            net_value = buy_value - sell_value
            value_source = "derived"
        if volume_source == "derived":
            stats["net_volume_fallback_count"] += 1
        if value_source == "derived":
            stats["net_value_fallback_count"] += 1
        if bool(raw.get("_foreign_net_volume_mismatch")):
            stats["net_volume_mismatch_count"] += 1
        elif volume_source != "derived" and net_volume is not None and buy_volume is not None and sell_volume is not None and net_volume != buy_volume - sell_volume:
            stats["net_volume_mismatch_count"] += 1
        if bool(raw.get("_foreign_net_value_mismatch")):
            stats["net_value_mismatch_count"] += 1
        elif value_source != "derived" and net_value is not None and buy_value is not None and sell_value is not None and net_value != buy_value - sell_value:
            stats["net_value_mismatch_count"] += 1
        row = {
            "trading_date": trading_date,
            "foreign_buy_volume": buy_volume,
            "foreign_sell_volume": sell_volume,
            "foreign_net_volume": net_volume,
            "foreign_buy_value": buy_value,
            "foreign_sell_value": sell_value,
            "foreign_net_value": net_value,
            "field_presence": deepcopy(raw.get("_foreign_field_presence") or {}),
        }
        gross_fields = (
            "foreign_buy_volume",
            "foreign_sell_volume",
            "foreign_buy_value",
            "foreign_sell_value",
        )
        explicit_zero = all(
            row["field_presence"].get(name) == "FIELD_PRESENT_EXPLICIT_ZERO"
            for name in gross_fields
        )
        row["suspicious_zero_session"] = explicit_zero
        row["anomaly_code"] = "all_foreign_gross_fields_explicit_zero" if explicit_zero else None
        if not any(
            row.get(name) is not None
            for name in (
                "foreign_buy_volume",
                "foreign_sell_volume",
                "foreign_net_volume",
                "foreign_buy_value",
                "foreign_sell_value",
                "foreign_net_value",
            )
        ):
            stats["rejected_rows"] += 1
            continue
        if trading_date in by_date:
            stats["duplicate_date_count"] += 1
        by_date[trading_date] = row
    accepted = [by_date[key] for key in sorted(by_date)]
    stats["normalized_rows"] = len(accepted)
    return accepted, stats


def _window(rows: List[Dict[str, Any]], requested: int) -> Dict[str, Any]:
    selected = rows[-requested:]
    volume_values = [row["foreign_net_volume"] for row in selected if row["foreign_net_volume"] is not None]
    value_values = [row["foreign_net_value"] for row in selected if row["foreign_net_value"] is not None]

    def counts(field: str) -> Tuple[int, int, int, int]:
        values = [row[field] for row in selected]
        return (
            sum(value is not None and value > 0 for value in values),
            sum(value is not None and value < 0 for value in values),
            sum(value == 0 for value in values),
            sum(value is None for value in values),
        )

    vp, vn, vz, vnull = counts("foreign_net_volume")
    xp, xn, xz, xnull = counts("foreign_net_value")
    return {
        "requested_sessions": requested,
        "covered_sessions": len(selected),
        "complete": len(selected) == requested,
        "start_date": selected[0]["trading_date"] if selected else None,
        "end_date": selected[-1]["trading_date"] if selected else None,
        "cumulative_foreign_net_volume": sum(volume_values) if volume_values else None,
        "cumulative_foreign_net_value": sum(value_values) if value_values else None,
        "net_volume_contributing_sessions": len(volume_values),
        "net_value_contributing_sessions": len(value_values),
        "positive_net_volume_sessions": vp,
        "negative_net_volume_sessions": vn,
        "zero_net_volume_sessions": vz,
        "null_net_volume_sessions": vnull,
        "positive_net_value_sessions": xp,
        "negative_net_value_sessions": xn,
        "zero_net_value_sessions": xz,
        "null_net_value_sessions": xnull,
    }


def _metric_sign(value: Optional[int]) -> Optional[str]:
    if value is None:
        return None
    if value > 0:
        return "net_buy"
    if value < 0:
        return "net_sell"
    return "zero"


def _extreme_event(rows: List[Dict[str, Any]], field: str, *, positive: bool) -> Optional[Dict[str, Any]]:
    candidates = [row for row in rows if row.get(field) is not None and (row[field] > 0 if positive else row[field] < 0)]
    if not candidates:
        return None
    extreme_value = (max if positive else min)(row[field] for row in candidates)
    row = max((item for item in candidates if item[field] == extreme_value), key=lambda item: item["trading_date"])
    return {"value": row[field], "trading_date": row["trading_date"]}


def _analytics_window(rows: List[Dict[str, Any]], field: str, requested: int) -> Dict[str, Any]:
    selected = rows[-requested:]
    values = [row[field] for row in selected if row.get(field) is not None]
    covered = len(values)
    return {
        "requested_sessions": requested,
        "observed_sessions": len(selected),
        "covered_sessions": covered,
        "complete": len(selected) == requested and covered == requested,
        "start_date": selected[0]["trading_date"] if selected else None,
        "end_date": selected[-1]["trading_date"] if selected else None,
        "net_sum": sum(values) if values else None,
        "average_net": sum(values) / covered if covered else None,
        "average_absolute_net": sum(abs(value) for value in values) / covered if covered else None,
        "net_buy_session_count": sum(value > 0 for value in values),
        "net_sell_session_count": sum(value < 0 for value in values),
        "zero_session_count": sum(value == 0 for value in values),
        "unavailable_session_count": len(selected) - covered,
        "max_net_buy": _extreme_event(selected, field, positive=True),
        "max_net_sell": _extreme_event(selected, field, positive=False),
    }


def _current_streak(rows: List[Dict[str, Any]], field: str) -> Dict[str, Any]:
    if not rows:
        return {"direction": "unavailable", "sessions": 0, "start_date": None, "end_date": None, "basis": "accepted_provider_rows"}
    latest = rows[-1]
    direction = _metric_sign(latest.get(field))
    if direction is None:
        return {"direction": "unavailable", "sessions": 0, "start_date": None, "end_date": latest["trading_date"], "basis": "accepted_provider_rows"}
    if direction == "zero":
        return {"direction": "none", "sessions": 0, "start_date": latest["trading_date"], "end_date": latest["trading_date"], "basis": "accepted_provider_rows"}
    sessions = 0
    start_date = latest["trading_date"]
    for row in reversed(rows):
        if _metric_sign(row.get(field)) != direction:
            break
        sessions += 1
        start_date = row["trading_date"]
    return {
        "direction": direction,
        "sessions": sessions,
        "start_date": start_date,
        "end_date": latest["trading_date"],
        "basis": "accepted_provider_rows",
    }


def _latest_reversal(rows: List[Dict[str, Any]], field: str) -> Optional[Dict[str, Any]]:
    for index in range(len(rows) - 1, 0, -1):
        previous = rows[index - 1]
        current = rows[index]
        previous_direction = _metric_sign(previous.get(field))
        current_direction = _metric_sign(current.get(field))
        if previous_direction not in {"net_buy", "net_sell"} or current_direction not in {"net_buy", "net_sell"}:
            continue
        if previous_direction != current_direction:
            return {
                "from_direction": previous_direction,
                "to_direction": current_direction,
                "trading_date": current["trading_date"],
                "previous_trading_date": previous["trading_date"],
                "current_value": current[field],
                "previous_value": previous[field],
            }
    return None


def _percentile(latest: Optional[int], values: List[int], *, absolute: bool = False) -> Optional[float]:
    if latest is None or len(values) < 5:
        return None
    target = abs(latest) if absolute else latest
    sample = [abs(value) for value in values] if absolute else values
    return sum(value <= target for value in sample) / len(sample) * 100.0


def _z_score(latest: Optional[int], values: List[int]) -> Optional[float]:
    if latest is None or len(values) < 5:
        return None
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    if variance <= 0:
        return None
    result = (latest - mean) / math.sqrt(variance)
    return result if math.isfinite(result) else None


def _comparison(rows: List[Dict[str, Any]], field: str) -> Dict[str, Any]:
    latest_value = rows[-1].get(field) if rows else None
    values_20 = [row[field] for row in rows[-20:] if row.get(field) is not None]
    values_60 = [row[field] for row in rows[-60:] if row.get(field) is not None]
    signed_20 = _percentile(latest_value, values_20)
    signed_60 = _percentile(latest_value, values_60)
    absolute_20 = _percentile(latest_value, values_20, absolute=True)
    absolute_60 = _percentile(latest_value, values_60, absolute=True)
    z_20 = _z_score(latest_value, values_20)
    z_60 = _z_score(latest_value, values_60)
    basis: List[str] = []
    if absolute_60 is not None and absolute_60 >= 90:
        basis.append("absolute_percentile_60d_gte_90")
    if z_60 is not None and abs(z_60) >= 2:
        basis.append("absolute_z_score_60d_gte_2")
    sufficient = absolute_60 is not None or z_60 is not None
    state = "elevated" if basis else "normal" if latest_value is not None and sufficient else "unavailable"
    return {
        "latest_value": latest_value,
        "sample_count_20d": len(values_20),
        "sample_count_60d": len(values_60),
        "average_net_20d": sum(values_20) / len(values_20) if values_20 else None,
        "average_absolute_net_20d": sum(abs(value) for value in values_20) / len(values_20) if values_20 else None,
        "average_net_60d": sum(values_60) / len(values_60) if values_60 else None,
        "average_absolute_net_60d": sum(abs(value) for value in values_60) / len(values_60) if values_60 else None,
        "signed_percentile_20d": signed_20,
        "signed_percentile_60d": signed_60,
        "absolute_percentile_20d": absolute_20,
        "absolute_percentile_60d": absolute_60,
        "z_score_20d": z_20,
        "z_score_60d": z_60,
        "unusual_flow_state": state,
        "unusual_flow_basis": basis if basis else (["within_recent_distribution"] if state == "normal" else ["insufficient_finite_history"]),
    }


def _rolling_series(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for index, row in enumerate(rows):
        derived: Dict[str, Any] = {"trading_date": row["trading_date"]}
        for family, field in (("value", "foreign_net_value"), ("volume", "foreign_net_volume")):
            for requested in (5, 20):
                selected = rows[max(0, index - requested + 1):index + 1]
                values = [item.get(field) for item in selected]
                derived[f"rolling_net_{requested}d_{family}"] = (
                    sum(values) if len(values) == requested and all(value is not None for value in values) else None
                )
        result.append(derived)
    return result


def _symbol_analytics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    bounded = rows[-60:]

    def family(field: str) -> Dict[str, Any]:
        latest = bounded[-1] if bounded else None
        return {
            "latest": {"value": latest.get(field), "trading_date": latest["trading_date"]} if latest else None,
            "windows": {str(size): _analytics_window(bounded, field, size) for size in (5, 20, 60)},
            "current_streak": _current_streak(bounded, field),
            "latest_reversal": _latest_reversal(bounded, field),
            "comparison": _comparison(bounded, field),
        }

    return {
        "basis": "accepted_provider_rows",
        "max_sessions": 60,
        "observed_sessions": len(bounded),
        "value": family("foreign_net_value"),
        "volume": family("foreign_net_volume"),
        "rolling_series": _rolling_series(bounded),
    }


class VietnamForeignFlowService:
    def __init__(
        self,
        fetcher: Optional[Any] = None,
        *,
        rest_provider: Optional[SsiRestProvider] = None,
        accepted_history_path: Optional[str] = None,
        accepted_history_store: Optional[VietnamForeignFlowHistoryStore] = None,
        persist_accepted_history: Optional[bool] = None,
    ):
        self._fetcher = fetcher
        self._rest_provider = rest_provider
        self._rest_provider_lock = RLock()
        explicitly_configured = (
            accepted_history_path is not None or accepted_history_store is not None
        )
        self._persist_accepted_history = (
            bool(persist_accepted_history)
            if persist_accepted_history is not None
            else fetcher is None or explicitly_configured
        )
        self._accepted_history_store = (
            accepted_history_store
            or (
                VietnamForeignFlowHistoryStore(accepted_history_path)
                if self._persist_accepted_history
                else None
            )
        )

    def _ensure_accepted_history_loaded(self) -> None:
        if self._accepted_history_store is not None:
            initialize_vietnam_foreign_flow_accepted_history(
                self._accepted_history_store
            )

    def _persist_completed_history(self) -> None:
        store = self._accepted_history_store
        if store is None:
            return
        with _ACCEPTED_HISTORY_PERSIST_LOCK:
            with _LOCK:
                snapshot = deepcopy(_ACCEPTED_HISTORY)
            if not store.write(snapshot):
                logger.warning(
                    "Accepted SSI DailyStockPrice foreign-flow history persistence failed"
                )

    def _get_rest_provider(self) -> SsiRestProvider:
        if self._rest_provider is None:
            with self._rest_provider_lock:
                if self._rest_provider is None:
                    if self._fetcher is not None:
                        self._rest_provider = SsiRestProviderRouter(self._fetcher)
                    else:
                        self._rest_provider = create_ssi_rest_provider_router()
        return self._rest_provider

    def get_symbol_history(
        self,
        ticker: str,
        *,
        limit: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        self._ensure_accepted_history_loaded()
        normalized_ticker = _normalize_ticker(ticker)
        parsed_from = _parse_iso_date(from_date, "from_date")
        parsed_to = _parse_iso_date(to_date, "to_date")
        explicit_limit = limit is not None
        if (parsed_from is None) != (parsed_to is None):
            raise ValueError("from_date and to_date must be provided together")
        if parsed_from is not None and explicit_limit:
            raise ValueError("limit cannot be combined with from_date/to_date")
        if parsed_from is not None:
            if parsed_from > parsed_to:
                raise ValueError("from_date must be on or before to_date")
            if (parsed_to - parsed_from).days + 1 > MAX_DATE_RANGE_DAYS:
                raise ValueError(f"date range cannot exceed {MAX_DATE_RANGE_DAYS} calendar days")
            mode = "date_range"
            requested_limit = None
        else:
            mode = "recent_sessions"
            requested_limit = DEFAULT_LIMIT if limit is None else int(limit)
            if not 1 <= requested_limit <= MAX_ROWS:
                raise ValueError(f"limit must be between 1 and {MAX_ROWS}")
        key = (
            SOURCE,
            SOURCE_ENDPOINT,
            normalized_ticker,
            mode,
            requested_limit,
            parsed_from.isoformat() if parsed_from else None,
            parsed_to.isoformat() if parsed_to else None,
            MAX_ROWS,
            CACHE_VERSION,
        )
        _metric_add("endpoint_requests")
        _metric_add("recent_session_requests" if mode == "recent_sessions" else "date_range_requests")
        if force_refresh:
            _metric_add("force_refresh_requests")

        now = _utc_now()
        with _LOCK:
            active = _IN_FLIGHT.get(key)
            if active is not None:
                _WAITERS[key] = _WAITERS.get(key, 0) + 1
                _METRICS["coalesced_waiters"] += 1
                _METRICS["max_coalesced_waiters"] = max(_METRICS["max_coalesced_waiters"], _WAITERS[key])
                future = active
                owner = False
            else:
                entry = _CACHE.get(key)
                if (
                    entry is not None
                    and entry.expires_at > now
                    and not force_refresh
                ):
                    _CACHE.move_to_end(key)
                    if entry.kind == "positive":
                        _METRICS["cache_hits"] += 1
                    elif entry.kind == "empty":
                        _METRICS["empty_cache_hits"] += 1
                    else:
                        _METRICS["negative_cache_hits"] += 1
                    cached = deepcopy(entry.payload)
                    cached["cache_state"] = "hit"
                    cached["cache_age_seconds"] = max(0.0, (now - entry.fetched_at).total_seconds())
                    return cached
                _METRICS["cache_misses"] += 1
                future = Future()
                _IN_FLIGHT[key] = future
                _WAITERS[key] = 0
                _METRICS["active_in_flight"] += 1
                owner = True
                stale_entry = entry if entry is not None and entry.kind == "positive" and entry.stale_until > now else None
        if not owner:
            try:
                return deepcopy(future.result())
            finally:
                with _LOCK:
                    _WAITERS[key] = max(0, _WAITERS.get(key, 1) - 1)

        try:
            payload, kind = self._fetch(
                normalized_ticker,
                mode=mode,
                requested_limit=requested_limit,
                parsed_from=parsed_from,
                parsed_to=parsed_to,
                cache_outcome="refresh" if force_refresh else "miss",
                stale_available=stale_entry is not None,
            )
            if kind == "negative" and stale_entry is not None:
                stale_payload = deepcopy(stale_entry.payload)
                stale_payload.update(
                    data_state="stale",
                    freshness="stale",
                    stale_reason="SSI DailyStockPrice refresh was unavailable; showing bounded cached history.",
                    failure_class=payload.get("failure_class"),
                    cache_state="stale_hit",
                    cache_age_seconds=max(0.0, (now - stale_entry.fetched_at).total_seconds()),
                )
                payload = stale_payload
                kind = "stale"
                _metric_add("stale_recoveries")
            if kind != "stale":
                self._store(key, payload, kind, parsed_to)
            future.set_result(deepcopy(payload))
            return payload
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            with _LOCK:
                _IN_FLIGHT.pop(key, None)
                _WAITERS.pop(key, None)
                _METRICS["active_in_flight"] = max(0, _METRICS["active_in_flight"] - 1)

    def _store(self, key: Tuple[Any, ...], payload: Dict[str, Any], kind: str, parsed_to: Optional[date]) -> None:
        now = _utc_now()
        if kind == "positive":
            completed = parsed_to is not None and parsed_to < now.date()
            ttl = POSITIVE_COMPLETED_TTL_SECONDS if completed else POSITIVE_CURRENT_TTL_SECONDS
        elif kind == "empty":
            ttl = EMPTY_TTL_SECONDS
        else:
            ttl = NEGATIVE_TTL_SECONDS
        entry = _CacheEntry(
            payload=deepcopy(payload),
            kind=kind,
            fetched_at=now,
            expires_at=now + timedelta(seconds=ttl),
            stale_until=now + timedelta(seconds=STALE_MAX_SECONDS),
        )
        with _LOCK:
            _CACHE[key] = entry
            _CACHE.move_to_end(key)
            while len(_CACHE) > CACHE_MAX_ENTRIES:
                _CACHE.popitem(last=False)

    def _fetch(
        self,
        ticker: str,
        *,
        mode: str,
        requested_limit: Optional[int],
        parsed_from: Optional[date],
        parsed_to: Optional[date],
        cache_outcome: str,
        stale_available: bool,
    ) -> Tuple[Dict[str, Any], str]:
        started = perf_counter()
        all_rows: List[Dict[str, Any]] = []
        provider_result: Dict[str, Any] = {}
        attempts = 1
        pages_used = 0

        def accepted_rows() -> List[Dict[str, Any]]:
            with _LOCK:
                stored = deepcopy(_ACCEPTED_HISTORY.get(ticker, {}))
            rows = [stored[key] for key in sorted(stored)]
            if mode == "date_range":
                return [
                    row
                    for row in rows
                    if parsed_from.isoformat()
                    <= str(row.get("trading_date") or "")
                    <= parsed_to.isoformat()
                ][:MAX_ROWS]
            return rows[-int(requested_limit):]

        def preserved_payload(
            *,
            failure_class: Optional[str],
            provider_latest_returned: Optional[str],
            reason: str,
        ) -> Optional[Dict[str, Any]]:
            rows = accepted_rows()
            if not rows:
                return None
            payload = self._build_payload(
                ticker,
                mode,
                requested_limit,
                parsed_from,
                parsed_to,
                rows,
                "stale",
                "stale",
                failure_class,
            )
            payload.update(
                cache_state="stale_hit",
                cache_age_seconds=0.0,
                stale_reason=reason,
                response_regressive=True,
                preserved_latest_completed=rows[-1]["trading_date"],
                provider_latest_returned=provider_latest_returned,
                cached_latest_retained=True,
            )
            return payload

        try:
            if mode == "date_range":
                request_ranges = [(parsed_from, parsed_to)]
            else:
                today = _utc_now().date()
                initial_days = min(MAX_RECENT_LOOKBACK_DAYS, max(30, math.ceil(int(requested_limit) * 1.5) + 14))
                lookbacks = [initial_days]
                while lookbacks[-1] < MAX_RECENT_LOOKBACK_DAYS and len(lookbacks) < 3:
                    lookbacks.append(min(MAX_RECENT_LOOKBACK_DAYS, max(lookbacks[-1] + 30, lookbacks[-1] * 2)))
                request_ranges = [(today - timedelta(days=days - 1), today) for days in lookbacks]
            for index, (start, end) in enumerate(request_ranges):
                attempts = index + 1
                _metric_add("provider_calls")
                provider_result = self._get_rest_provider().get_daily_stock_price(
                    ticker,
                    from_date=start.isoformat(),
                    to_date=end.isoformat(),
                    limit=MAX_ROWS,
                )
                pages_used += max(0, int(provider_result.get("pages_used") or 0))
                if provider_result.get("status") == "ok":
                    _metric_add("provider_successes")
                if provider_result.get("status") != "ok":
                    break
                all_rows = provider_result.get("rows") if isinstance(provider_result.get("rows"), list) else []
                if mode == "date_range" or len(all_rows) >= int(requested_limit) or end == date.min or start <= today - timedelta(days=MAX_RECENT_LOOKBACK_DAYS - 1):
                    break
            failure_class = _safe_failure_class(provider_result.get("failure_class"))
            if provider_result.get("status") != "ok":
                preserved = None if stale_available else preserved_payload(
                    failure_class=failure_class,
                    provider_latest_returned=None,
                    reason=(
                        "SSI DailyStockPrice refresh was weaker than accepted history; "
                        "last-known-good completed sessions are preserved."
                    ),
                )
                if preserved is not None:
                    self._finish_provider_metrics(
                        started,
                        ticker,
                        mode,
                        requested_limit,
                        parsed_from,
                        parsed_to,
                        "stale",
                        len(preserved["rows"]),
                        failure_class,
                        attempts,
                        pages_used,
                        "accepted_history_recovery",
                    )
                    return preserved, "stale"
                if failure_class == "empty_response":
                    _metric_add("provider_empty_results")
                    payload = self._build_payload(ticker, mode, requested_limit, parsed_from, parsed_to, [], "empty", "empty", None)
                    payload.update(cache_state=cache_outcome, cache_age_seconds=0.0)
                    self._finish_provider_metrics(started, ticker, mode, requested_limit, parsed_from, parsed_to, "empty", 0, failure_class, attempts, pages_used, cache_outcome)
                    return payload, "empty"
                _metric_add("provider_failures")
                _metric_add("unavailable_results")
                payload = self._build_payload(ticker, mode, requested_limit, parsed_from, parsed_to, [], "unavailable", "unavailable", failure_class)
                payload.update(cache_state=cache_outcome, cache_age_seconds=0.0)
                failure_cache_outcome = "stale_recovery" if stale_available else cache_outcome
                self._finish_provider_metrics(started, ticker, mode, requested_limit, parsed_from, parsed_to, "unavailable", 0, failure_class, attempts, pages_used, failure_cache_outcome)
                return payload, "negative"
            rows, stats = _normalize_rows(all_rows)
            stats["duplicate_date_count"] += max(0, int(provider_result.get("duplicate_date_count") or 0))
            provider_latest_returned = (
                rows[-1]["trading_date"] if rows else None
            )
            with _LOCK:
                accepted = _ACCEPTED_HISTORY.setdefault(ticker, {})
                cached_latest_before = max(accepted) if accepted else None
                for row in rows:
                    accepted[str(row["trading_date"])] = deepcopy(row)
                if len(accepted) > MAX_ROWS:
                    for old_date in sorted(accepted)[:-MAX_ROWS]:
                        accepted.pop(old_date, None)
                cached_latest_after = max(accepted) if accepted else None
            self._persist_completed_history()
            response_regressive = bool(
                cached_latest_before
                and (
                    provider_latest_returned is None
                    or provider_latest_returned < cached_latest_before
                )
            )
            rows = accepted_rows()
            if len(rows) > MAX_ROWS:
                raise ValueError(f"normalized provider response exceeded the {MAX_ROWS}-row public cap")
            for name, amount in stats.items():
                _metric_add(name, amount)
            state = "ready" if rows else "empty"
            if not rows:
                _metric_add("provider_empty_results")
            with _LOCK:
                _METRICS["last_success_at"] = _iso_now()
                _METRICS["last_failure_class"] = None
            payload = self._build_payload(ticker, mode, requested_limit, parsed_from, parsed_to, rows, state, "fresh", None)
            payload.update(
                cache_state=cache_outcome,
                cache_age_seconds=0.0,
                response_regressive=response_regressive,
                preserved_latest_completed=cached_latest_after,
                provider_latest_returned=provider_latest_returned,
                cached_latest_retained=bool(
                    response_regressive
                    and cached_latest_after == cached_latest_before
                ),
            )
            if response_regressive:
                payload.update(
                    data_state="stale",
                    freshness="stale",
                    stale_reason=(
                        "SSI DailyStockPrice returned an older latest session; "
                        "last-known-good completed history is retained."
                    ),
                )
            self._finish_provider_metrics(started, ticker, mode, requested_limit, parsed_from, parsed_to, state, len(rows), None, attempts, pages_used, cache_outcome)
            return payload, "positive" if rows else "empty"
        except Exception:
            _metric_add("provider_failures")
            _metric_add("unavailable_results")
            failure_class = "provider_exception"
            with _LOCK:
                _METRICS["last_failure_class"] = failure_class
            payload = self._build_payload(ticker, mode, requested_limit, parsed_from, parsed_to, [], "unavailable", "unavailable", failure_class)
            payload.update(cache_state=cache_outcome, cache_age_seconds=0.0)
            failure_cache_outcome = "stale_recovery" if stale_available else cache_outcome
            self._finish_provider_metrics(started, ticker, mode, requested_limit, parsed_from, parsed_to, "unavailable", 0, failure_class, attempts, pages_used, failure_cache_outcome)
            return payload, "negative"

    def _finish_provider_metrics(
        self,
        started: float,
        ticker: str,
        mode: str,
        requested_limit: Optional[int],
        parsed_from: Optional[date],
        parsed_to: Optional[date],
        result_class: str,
        row_count: int,
        failure_class: Optional[str],
        attempts: int,
        pages_used: int,
        cache_outcome: str,
    ) -> None:
        latency_ms = max(0, int((perf_counter() - started) * 1000))
        with _LOCK:
            _METRICS["provider_latency_count"] += 1
            _METRICS["provider_latency_total_ms"] += latency_ms
            _METRICS["provider_latency_max_ms"] = max(_METRICS["provider_latency_max_ms"], latency_ms)
            if failure_class:
                _METRICS["last_failure_class"] = failure_class
        logger.info(
            "vn_foreign_flow_provider_fetch",
            extra={
                "vn_foreign_flow": {
                    "ticker": ticker,
                    "query_mode": mode,
                    "requested_limit": requested_limit,
                    "requested_from_date": parsed_from.isoformat() if parsed_from else None,
                    "requested_to_date": parsed_to.isoformat() if parsed_to else None,
                    "result_class": result_class,
                    "row_count": row_count,
                    "request_attempts": attempts,
                    "pages_used": pages_used,
                    "latency_ms": latency_ms,
                    "cache_outcome": cache_outcome,
                    "failure_class": failure_class,
                }
            },
        )

    @staticmethod
    def _build_payload(
        ticker: str,
        mode: str,
        requested_limit: Optional[int],
        parsed_from: Optional[date],
        parsed_to: Optional[date],
        rows: List[Dict[str, Any]],
        data_state: str,
        freshness: str,
        failure_class: Optional[str],
    ) -> Dict[str, Any]:
        requested_sessions = requested_limit if mode == "recent_sessions" else None
        return {
            "ticker": ticker,
            "source": SOURCE,
            "source_endpoint": SOURCE_ENDPOINT,
            "volume_unit": VOLUME_UNIT,
            "value_unit": VALUE_UNIT,
            "finality": FINALITY,
            "data_state": data_state,
            "freshness": freshness,
            "rows": rows,
            "windows": {"5": _window(rows, 5), "20": _window(rows, 20), "60": _window(rows, 60)},
            "analytics": _symbol_analytics(rows),
            "latest_row": rows[-1] if rows else None,
            "requested": {
                "mode": mode,
                "requested_limit": requested_limit,
                "requested_from_date": parsed_from.isoformat() if parsed_from else None,
                "requested_to_date": parsed_to.isoformat() if parsed_to else None,
                "returned_session_count": len(rows),
            },
            "coverage": {
                "requested_sessions": requested_sessions,
                "covered_sessions": len(rows),
                "complete": len(rows) >= requested_sessions if requested_sessions is not None else None,
                "start_date": rows[0]["trading_date"] if rows else None,
                "end_date": rows[-1]["trading_date"] if rows else None,
            },
            "fetched_at": _iso_now(),
            "stale_reason": None,
            "failure_class": failure_class,
            "provider_version": PROVIDER_VERSION,
            "cache_state": "unavailable",
            "cache_age_seconds": None,
        }


class VietnamForeignFlowBatchService:
    """Compose bounded watchlist summaries from the authoritative symbol service."""

    def __init__(
        self,
        symbol_service: Optional[VietnamForeignFlowService] = None,
        *,
        max_concurrency: int = BATCH_MAX_CONCURRENCY,
        per_ticker_timeout_seconds: float = WATCHLIST_PER_TICKER_TIMEOUT_SECONDS,
        total_timeout_seconds: float = WATCHLIST_TOTAL_TIMEOUT_SECONDS,
    ) -> None:
        self._symbol_service = symbol_service or VietnamForeignFlowService()
        self._max_concurrency = max(1, min(int(max_concurrency), BATCH_MAX_CONCURRENCY))
        self._per_ticker_timeout_seconds = max(0.01, float(per_ticker_timeout_seconds))
        self._total_timeout_seconds = max(
            self._per_ticker_timeout_seconds,
            float(total_timeout_seconds),
        )

    def get_batch(
        self,
        tickers: Iterable[str],
        *,
        top_n: int = BATCH_DEFAULT_TOP_N,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        requested_tickers, normalized_tickers = normalize_vietnam_foreign_flow_tickers(tickers)
        requested_top_n = int(top_n)
        if not 1 <= requested_top_n <= BATCH_MAX_TOP_N:
            raise ValueError(f"top_n must be between 1 and {BATCH_MAX_TOP_N}")
        effective_top_n = min(requested_top_n, len(normalized_tickers))
        started = perf_counter()
        with _LOCK:
            _METRICS["batch_requests"] += 1
            if force_refresh:
                _METRICS["batch_force_refresh_requests"] += 1
            _METRICS["batch_requested_symbols"] += len(requested_tickers)
            _METRICS["batch_normalized_symbols"] += len(normalized_tickers)
            _METRICS["batch_active_requests"] += 1
            _METRICS["batch_max_active_requests"] = max(
                _METRICS["batch_max_active_requests"],
                _METRICS["batch_active_requests"],
            )

        result_state = "unavailable"
        counts = {"usable": 0, "fresh": 0, "stale": 0, "empty": 0, "unavailable": 0}
        ranking_stats = {"eligible": 0, "excluded_null": 0, "excluded_zero": 0}
        try:
            histories = self._load_histories(normalized_tickers, force_refresh=force_refresh)
            rows = [self._compose_symbol(ticker, histories[ticker]) for ticker in normalized_tickers]
            counts = self._count_states(rows)
            result_state = self._batch_state(len(rows), counts)
            rankings, ranking_stats = self._build_rankings(rows, effective_top_n)
            coverage_ratio = counts["usable"] / len(normalized_tickers)
            payload = {
                "source": SOURCE,
                "source_endpoint": SOURCE_ENDPOINT,
                "volume_unit": VOLUME_UNIT,
                "value_unit": VALUE_UNIT,
                "finality": FINALITY,
                "requested_tickers": requested_tickers,
                "normalized_tickers": normalized_tickers,
                "requested_count": len(requested_tickers),
                "normalized_count": len(normalized_tickers),
                "returned_count": len(rows),
                "usable_count": counts["usable"],
                "fresh_count": counts["fresh"],
                "stale_count": counts["stale"],
                "empty_count": counts["empty"],
                "unavailable_count": counts["unavailable"],
                "coverage_ratio": coverage_ratio,
                "complete": result_state == "ready",
                "data_state": result_state,
                "rows": rows,
                "rankings": rankings,
                "fetched_at": _iso_now(),
            }
            return payload
        finally:
            latency_ms = max(0, int((perf_counter() - started) * 1000))
            with _LOCK:
                _METRICS["batch_usable_symbols"] += counts["usable"]
                _METRICS["batch_stale_symbols"] += counts["stale"]
                _METRICS["batch_empty_symbols"] += counts["empty"]
                _METRICS["batch_unavailable_symbols"] += counts["unavailable"]
                result_metric = f"batch_{result_state}_results"
                if result_metric in _METRICS:
                    _METRICS[result_metric] += 1
                _METRICS["batch_latency_count"] += 1
                _METRICS["batch_latency_total_ms"] += latency_ms
                _METRICS["batch_latency_max_ms"] = max(_METRICS["batch_latency_max_ms"], latency_ms)
                _METRICS["batch_active_requests"] = max(0, _METRICS["batch_active_requests"] - 1)
                _METRICS["ranking_build_count"] += 1
                _METRICS["ranking_eligible_values"] += ranking_stats["eligible"]
                _METRICS["ranking_excluded_null_values"] += ranking_stats["excluded_null"]
                _METRICS["ranking_excluded_zero_values"] += ranking_stats["excluded_zero"]
            logger.info(
                "vn_foreign_flow_batch_complete",
                extra={
                    "vn_foreign_flow_batch": {
                        "requested_count": len(requested_tickers),
                        "normalized_count": len(normalized_tickers),
                        "usable_count": counts["usable"],
                        "stale_count": counts["stale"],
                        "empty_count": counts["empty"],
                        "unavailable_count": counts["unavailable"],
                        "result_state": result_state,
                        "duration_ms": latency_ms,
                        "force_refresh": bool(force_refresh),
                    }
                },
            )

    def get_watchlist(
        self,
        tickers: Iterable[str],
        *,
        sessions: int = 60,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        requested_tickers, normalized_tickers = normalize_vietnam_foreign_flow_tickers(tickers)
        requested_sessions = int(sessions)
        if requested_sessions not in WATCHLIST_ALLOWED_SESSIONS:
            allowed = ", ".join(str(value) for value in sorted(WATCHLIST_ALLOWED_SESSIONS))
            raise ValueError(f"sessions must be one of: {allowed}")

        histories = self._load_watchlist_histories(
            normalized_tickers,
            sessions=requested_sessions,
            force_refresh=force_refresh,
        )
        items = [
            self._compose_watchlist_item(ticker, histories[ticker], requested_sessions)
            for ticker in normalized_tickers
        ]
        self._add_observed_session_lag(items)
        ready_count = sum(item["availability"] == "ready" for item in items)
        partial_count = sum(item["availability"] == "partial" for item in items)
        unavailable_count = sum(item["availability"] == "unavailable" for item in items)
        usable = ready_count + partial_count > 0
        status = (
            "ready"
            if ready_count == len(items)
            else "partial"
            if usable
            else "unavailable"
        )
        cache_states = {str(item["cache_state"]) for item in items}
        cache_ages = [
            float(item["cache_age_seconds"])
            for item in items
            if item["cache_age_seconds"] is not None
        ]
        failure_classes = [
            item["failure_class"] for item in items if item["failure_class"]
        ]
        return {
            "status": status,
            "data_state": status,
            "usable": usable,
            "requested_tickers": requested_tickers,
            "normalized_tickers": normalized_tickers,
            "duplicate_tickers_removed": len(requested_tickers) - len(normalized_tickers),
            "expected_symbol_count": len(normalized_tickers),
            "ready_symbol_count": ready_count,
            "partial_symbol_count": partial_count,
            "unavailable_symbol_count": unavailable_count,
            "requested_session_count": requested_sessions,
            "fetched_at": _iso_now(),
            "provider": SOURCE,
            "provider_version": PROVIDER_VERSION,
            "cache_state": next(iter(cache_states)) if len(cache_states) == 1 else "mixed",
            "cache_age_seconds": max(cache_ages) if cache_ages else None,
            "failure_class": (
                failure_classes[0]
                if status == "unavailable" and len(set(failure_classes)) == 1
                else None
            ),
            "items": items,
        }

    def _load_watchlist_histories(
        self,
        tickers: List[str],
        *,
        sessions: int,
        force_refresh: bool,
    ) -> Dict[str, Dict[str, Any]]:
        started_at: Dict[str, float] = {}
        started_lock = RLock()

        def load(ticker: str) -> Dict[str, Any]:
            with started_lock:
                started_at[ticker] = perf_counter()
            try:
                return self._symbol_service.get_symbol_history(
                    ticker,
                    limit=sessions,
                    force_refresh=force_refresh,
                )
            except Exception:
                return self._unavailable_history(
                    ticker,
                    requested_sessions=sessions,
                    failure_class="provider_exception",
                )

        executor = ThreadPoolExecutor(
            max_workers=min(self._max_concurrency, len(tickers)),
            thread_name_prefix="vn-foreign-watchlist",
        )
        future_to_ticker = {executor.submit(load, ticker): ticker for ticker in tickers}
        pending = set(future_to_ticker)
        results: Dict[str, Dict[str, Any]] = {}
        batch_deadline = perf_counter() + self._total_timeout_seconds
        try:
            while pending:
                now = perf_counter()
                for future in list(pending):
                    ticker = future_to_ticker[future]
                    task_started = started_at.get(ticker)
                    if (
                        task_started is not None
                        and now - task_started >= self._per_ticker_timeout_seconds
                    ):
                        pending.remove(future)
                        future.cancel()
                        results[ticker] = self._unavailable_history(
                            ticker,
                            requested_sessions=sessions,
                            failure_class="timeout",
                        )
                if not pending or now >= batch_deadline:
                    break
                done, _ = wait(
                    pending,
                    timeout=min(0.05, max(0.0, batch_deadline - now)),
                    return_when=FIRST_COMPLETED,
                )
                for future in done:
                    pending.remove(future)
                    ticker = future_to_ticker[future]
                    try:
                        results[ticker] = future.result()
                    except Exception:
                        results[ticker] = self._unavailable_history(
                            ticker,
                            requested_sessions=sessions,
                            failure_class="provider_exception",
                        )
            for future in pending:
                ticker = future_to_ticker[future]
                future.cancel()
                results[ticker] = self._unavailable_history(
                    ticker,
                    requested_sessions=sessions,
                    failure_class="timeout",
                )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        return {ticker: results[ticker] for ticker in tickers}

    @staticmethod
    def _complete_sum(rows: List[Dict[str, Any]], field: str, sessions: int) -> Optional[int]:
        selected = rows[-sessions:]
        if len(selected) != sessions:
            return None
        values = [row.get(field) for row in selected]
        if any(value is None for value in values):
            return None
        return sum(int(value) for value in values)

    @classmethod
    def _compose_watchlist_item(
        cls,
        ticker: str,
        history: Dict[str, Any],
        requested_sessions: int,
    ) -> Dict[str, Any]:
        rows = history.get("rows") if isinstance(history.get("rows"), list) else []
        rows = [row for row in rows if isinstance(row, dict)][-60:]
        actual_count = len(rows)
        source_state = str(history.get("data_state") or "unavailable")
        usable_history = source_state in {"ready", "stale"} and bool(rows)
        metrics: Dict[str, Optional[int]] = {}
        for window in (1, 5, 20, 60):
            for family in ("value", "volume"):
                for side in ("buy", "sell", "net"):
                    field = f"foreign_{side}_{family}"
                    metrics[f"{side}_{family}_{window}d"] = (
                        cls._complete_sum(rows, field, window)
                        if usable_history
                        else None
                    )
        requested_metric_names = [
            f"{side}_{family}_{requested_sessions}d"
            for family in ("value", "volume")
            for side in ("buy", "sell", "net")
        ]
        complete = actual_count >= requested_sessions
        requested_metrics_complete = all(metrics[name] is not None for name in requested_metric_names)
        if not usable_history:
            availability = "unavailable"
        elif complete and requested_metrics_complete:
            availability = "ready"
        else:
            availability = "partial"

        streak = _current_streak(rows, "foreign_net_value")
        direction = streak.get("direction")
        anomaly_sessions = [
            str(row["trading_date"])
            for row in rows
            if row.get("suspicious_zero_session")
        ]
        raw_cache_state = str(history.get("cache_state") or "unavailable")
        cache_state = raw_cache_state if raw_cache_state in {
            "hit", "miss", "refresh", "stale_hit", "unavailable"
        } else "unavailable"
        source_freshness = (
            "stale"
            if source_state == "stale" or history.get("freshness") == "stale"
            else "latest_completed"
            if usable_history
            else "unknown"
        )
        return {
            "ticker": ticker,
            "availability": availability,
            "data_state": availability,
            "failure_class": _public_failure_class(history.get("failure_class")),
            "latest_session": rows[-1].get("trading_date") if rows else None,
            "source_freshness": source_freshness,
            "source_session_lag": None,
            "fetched_at": history.get("fetched_at") or _iso_now(),
            "cache_state": cache_state,
            "cache_age_seconds": history.get("cache_age_seconds"),
            "actual_session_count": actual_count,
            "requested_session_count": requested_sessions,
            "complete": complete and requested_metrics_complete,
            **metrics,
            "buy_streak": (
                int(streak.get("sessions") or 0)
                if direction == "net_buy"
                else 0
                if direction in {"net_sell", "zero", "none"}
                else None
            ),
            "sell_streak": (
                int(streak.get("sessions") or 0)
                if direction == "net_sell"
                else 0
                if direction in {"net_buy", "zero", "none"}
                else None
            ),
            "streak_metric_basis": "foreign_net_value",
            "contains_provider_anomaly": bool(anomaly_sessions),
            "anomaly_sessions": anomaly_sessions,
            "anomaly_count": len(anomaly_sessions),
            "source": history.get("source") or SOURCE,
            "source_endpoint": history.get("source_endpoint") or SOURCE_ENDPOINT,
        }

    @staticmethod
    def _add_observed_session_lag(items: List[Dict[str, Any]]) -> None:
        dates = sorted({
            str(item["latest_session"])
            for item in items
            if item.get("latest_session")
        }, reverse=True)
        lag_by_date = {value: index for index, value in enumerate(dates)}
        for item in items:
            latest = item.get("latest_session")
            item["source_session_lag"] = lag_by_date.get(str(latest)) if latest else None

    def _load_histories(self, tickers: List[str], *, force_refresh: bool) -> Dict[str, Dict[str, Any]]:
        def load(ticker: str) -> Dict[str, Any]:
            try:
                return self._symbol_service.get_symbol_history(
                    ticker,
                    limit=20,
                    force_refresh=force_refresh,
                )
            except Exception:
                return self._unavailable_history(ticker)

        worker_count = min(self._max_concurrency, len(tickers))
        if worker_count <= 1:
            return {ticker: load(ticker) for ticker in tickers}
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="vn-foreign-flow") as executor:
            futures = {ticker: executor.submit(load, ticker) for ticker in tickers}
            return {ticker: futures[ticker].result() for ticker in tickers}

    @staticmethod
    def _unavailable_history(
        ticker: str,
        *,
        requested_sessions: int = 20,
        failure_class: str = "provider_exception",
    ) -> Dict[str, Any]:
        payload = VietnamForeignFlowService._build_payload(
            ticker,
            "recent_sessions",
            requested_sessions,
            None,
            None,
            [],
            "unavailable",
            "unavailable",
            failure_class,
        )
        payload.update(cache_state="unavailable", cache_age_seconds=None)
        return payload

    @staticmethod
    def _compose_symbol(ticker: str, history: Dict[str, Any]) -> Dict[str, Any]:
        state = str(history.get("data_state") or "unavailable")
        if state not in {"ready", "stale", "empty", "unavailable"}:
            state = "unavailable"
        freshness = str(history.get("freshness") or state)
        if freshness not in {"fresh", "stale", "empty", "unavailable"}:
            freshness = "unavailable"
        latest = history.get("latest_row") if isinstance(history.get("latest_row"), dict) else {}
        windows = history.get("windows") if isinstance(history.get("windows"), dict) else {}
        window_5 = windows.get("5") if isinstance(windows.get("5"), dict) else {}
        window_20 = windows.get("20") if isinstance(windows.get("20"), dict) else {}
        return {
            "ticker": ticker,
            "data_state": state,
            "freshness": freshness,
            "failure_class": history.get("failure_class"),
            "stale_reason": history.get("stale_reason"),
            "latest_trading_date": latest.get("trading_date"),
            "foreign_buy_volume": latest.get("foreign_buy_volume"),
            "foreign_sell_volume": latest.get("foreign_sell_volume"),
            "foreign_net_volume": latest.get("foreign_net_volume"),
            "foreign_buy_value": latest.get("foreign_buy_value"),
            "foreign_sell_value": latest.get("foreign_sell_value"),
            "foreign_net_value": latest.get("foreign_net_value"),
            "foreign_net_volume_5d": window_5.get("cumulative_foreign_net_volume"),
            "foreign_net_value_5d": window_5.get("cumulative_foreign_net_value"),
            "foreign_net_volume_20d": window_20.get("cumulative_foreign_net_volume"),
            "foreign_net_value_20d": window_20.get("cumulative_foreign_net_value"),
            "covered_sessions_5d": int(window_5.get("covered_sessions") or 0),
            "complete_5d": bool(window_5.get("complete")),
            "window_end_date_5d": window_5.get("end_date"),
            "covered_sessions_20d": int(window_20.get("covered_sessions") or 0),
            "complete_20d": bool(window_20.get("complete")),
            "window_end_date_20d": window_20.get("end_date"),
            "source": history.get("source") or SOURCE,
            "source_endpoint": history.get("source_endpoint") or SOURCE_ENDPOINT,
            "volume_unit": history.get("volume_unit") or VOLUME_UNIT,
            "value_unit": history.get("value_unit") or VALUE_UNIT,
            "finality": history.get("finality") or FINALITY,
            "fetched_at": history.get("fetched_at") or _iso_now(),
        }

    @staticmethod
    def _count_states(rows: List[Dict[str, Any]]) -> Dict[str, int]:
        fresh = sum(row["data_state"] == "ready" and row["freshness"] == "fresh" for row in rows)
        stale = sum(row["data_state"] == "stale" or row["freshness"] == "stale" for row in rows)
        empty = sum(row["data_state"] == "empty" for row in rows)
        unavailable = sum(row["data_state"] == "unavailable" for row in rows)
        return {
            "usable": fresh + stale,
            "fresh": fresh,
            "stale": stale,
            "empty": empty,
            "unavailable": unavailable,
        }

    @staticmethod
    def _batch_state(row_count: int, counts: Dict[str, int]) -> str:
        if counts["fresh"] == row_count:
            return "ready"
        if counts["stale"] == row_count:
            return "stale"
        if counts["empty"] == row_count:
            return "empty"
        if counts["usable"] > 0:
            return "partial"
        if counts["unavailable"] > 0:
            return "unavailable"
        return "partial"

    @staticmethod
    def _build_rankings(rows: List[Dict[str, Any]], top_n: int) -> Tuple[Dict[str, Any], Dict[str, int]]:
        specifications = {
            "latest_net_value": ("foreign_net_value", "latest_trading_date", None, None),
            "net_value_5d": ("foreign_net_value_5d", "window_end_date_5d", "covered_sessions_5d", "complete_5d"),
            "net_value_20d": ("foreign_net_value_20d", "window_end_date_20d", "covered_sessions_20d", "complete_20d"),
        }
        rankings: Dict[str, Any] = {}
        stats = {"eligible": 0, "excluded_null": 0, "excluded_zero": 0}
        for name, (value_key, date_key, covered_key, complete_key) in specifications.items():
            entries = []
            for row in rows:
                if row["data_state"] not in {"ready", "stale"}:
                    continue
                value = row.get(value_key)
                if value is None:
                    stats["excluded_null"] += 1
                    continue
                if value == 0:
                    stats["excluded_zero"] += 1
                    continue
                stats["eligible"] += 1
                entries.append(
                    {
                        "ticker": row["ticker"],
                        "value": value,
                        "trading_date": row.get(date_key),
                        "covered_sessions": int(row.get(covered_key) or 1) if covered_key else 1,
                        "complete": bool(row.get(complete_key)) if complete_key else True,
                        "data_state": row["data_state"],
                    }
                )
            rankings[name] = {
                "top_buy": sorted(
                    (entry for entry in entries if entry["value"] > 0),
                    key=lambda entry: (-entry["value"], entry["ticker"]),
                )[:top_n],
                "top_sell": sorted(
                    (entry for entry in entries if entry["value"] < 0),
                    key=lambda entry: (entry["value"], entry["ticker"]),
                )[:top_n],
            }
        return rankings, stats


class VietnamForeignFlowVn30Service:
    """Combine canonical SSI VN30 totals with current-basket decomposition."""

    def __init__(
        self,
        symbol_service: Optional[VietnamForeignFlowService] = None,
        market_service: Optional[Any] = None,
        *,
        flow_data_service: Optional[Any] = None,
        max_concurrency: int = BATCH_MAX_CONCURRENCY,
        now_fn: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._symbol_service = symbol_service or VietnamForeignFlowService()
        self._market_service = market_service
        self._flow_data_service = flow_data_service
        self._max_concurrency = max(1, min(int(max_concurrency), BATCH_MAX_CONCURRENCY))
        self._now_fn = now_fn or (lambda: datetime.now(VN_TIMEZONE))

    def _get_market_service(self) -> Any:
        if self._market_service is None:
            from src.services.vietnam_market_service import VietnamMarketService

            self._market_service = VietnamMarketService()
        return self._market_service

    def _get_flow_data_service(self) -> Any:
        if self._flow_data_service is None:
            from src.services.vietnam_flow_data_service import VietnamFlowDataService

            provider = None
            provider_getter = getattr(self._symbol_service, "_get_rest_provider", None)
            if callable(provider_getter):
                try:
                    provider = provider_getter()
                except Exception:
                    provider = None
            self._flow_data_service = VietnamFlowDataService(provider=provider)
        return self._flow_data_service

    @staticmethod
    def _previous_weekday(value: date) -> date:
        candidate = value
        while candidate.weekday() >= 5:
            candidate -= timedelta(days=1)
        return candidate

    @classmethod
    def _expected_completed_session(cls, now: datetime) -> date:
        local = now.astimezone(VN_TIMEZONE)
        if local.weekday() < 5 and local.time() >= time(15, 0):
            return local.date()
        return cls._previous_weekday(local.date() - timedelta(days=1))

    @staticmethod
    def _session_gap(older: Optional[str], newer: Optional[str]) -> Optional[int]:
        if not older or not newer:
            return None
        start = date.fromisoformat(older)
        end = date.fromisoformat(newer)
        if start >= end:
            return 0
        gap = 0
        candidate = start + timedelta(days=1)
        while candidate <= end:
            if candidate.weekday() < 5:
                gap += 1
            candidate += timedelta(days=1)
        return gap

    def get_vn30_aggregate(
        self,
        *,
        top_n: int = BATCH_DEFAULT_TOP_N,
        force_refresh: bool = False,
        force_capability_refresh: bool = False,
    ) -> Dict[str, Any]:
        requested_top_n = int(top_n)
        if not 1 <= requested_top_n <= BATCH_MAX_TOP_N:
            raise ValueError(f"top_n must be between 1 and {BATCH_MAX_TOP_N}")
        request_started = perf_counter()
        _metric_add("vn30_requests")
        if force_refresh:
            _metric_add("vn30_force_refresh_requests")

        membership_started = perf_counter()
        try:
            membership_payload = self._get_market_service().build_index_components(
                VN30_INDEX_CODE,
                force_refresh=force_refresh,
            )
        except Exception:
            membership_payload = {
                "status": "unavailable",
                "rows": [],
                "diagnostics": {
                    "failure_class": "provider_not_configured",
                    "cache_status": "unavailable",
                },
            }
        membership_ms = max(0, int((perf_counter() - membership_started) * 1000))
        membership = self._normalize_membership(membership_payload)
        membership_hash = hashlib.sha256(
            ",".join(membership["member_tickers"]).encode("ascii", errors="ignore")
        ).hexdigest()[:16]
        local_now = self._now_fn().astimezone(VN_TIMEZONE)
        expected_completed = self._expected_completed_session(local_now)
        requested_to = local_now.date()
        requested_from = requested_to - timedelta(days=120)
        cache_key = (
            SOURCE,
            "v3",
            "vn30",
            VN30_INDEX_CODE,
            VN30_CANONICAL_MODE,
            VN30_DECOMPOSITION_MODE,
            requested_from.isoformat(),
            requested_to.isoformat(),
            VN30_HISTORY_SESSIONS,
            membership_hash,
            requested_top_n,
            CACHE_VERSION,
            expected_completed.isoformat(),
        )
        now = _utc_now()
        with _LOCK:
            active = _VN30_IN_FLIGHT.get(cache_key)
            if active is not None:
                _VN30_WAITERS[cache_key] = _VN30_WAITERS.get(cache_key, 0) + 1
                _METRICS["vn30_coalesced_waiters"] += 1
                future = active
                owner = False
                cache_status = "coalesced"
            else:
                entry = _VN30_CACHE.get(cache_key)
                if (
                    entry is not None
                    and entry.expires_at > now
                    and not force_refresh
                    and not force_capability_refresh
                ):
                    _VN30_CACHE.move_to_end(cache_key)
                    metric = "vn30_cache_hits" if entry.kind == "positive" else "vn30_negative_cache_hits"
                    _METRICS[metric] += 1
                    return self._with_cache_metadata(entry.payload, entry, "hit", False)
                _METRICS["vn30_cache_misses"] += 1
                future = Future()
                _VN30_IN_FLIGHT[cache_key] = future
                _VN30_WAITERS[cache_key] = 0
                _METRICS["vn30_active_in_flight"] += 1
                owner = True
                cache_status = (
                    "capability_refresh"
                    if force_capability_refresh and not force_refresh
                    else "refresh"
                    if force_refresh
                    else "miss"
                )
        if not owner:
            try:
                payload = deepcopy(future.result())
                payload["cache"] = dict(payload.get("cache") or {}, status=cache_status, coalesced=True)
                return payload
            finally:
                with _LOCK:
                    _VN30_WAITERS[cache_key] = max(0, _VN30_WAITERS.get(cache_key, 1) - 1)

        result_state = "unavailable"
        component_counts = {"usable": 0, "stale": 0, "empty": 0, "unavailable": 0}
        try:
            direct_started = perf_counter()
            direct = self._get_flow_data_service().foreign_history_by_index(
                VN30_INDEX_CODE,
                from_date=requested_from.isoformat(),
                to_date=requested_to.isoformat(),
                limit=120,
                force_capability_refresh=force_capability_refresh,
            )
            direct_ms = max(0, int((perf_counter() - direct_started) * 1000))
            canonical = self._build_canonical(
                direct,
                requested_from=requested_from.isoformat(),
                requested_to=requested_to.isoformat(),
                expected_completed=expected_completed.isoformat(),
                now=local_now,
            )
            if membership["status"] != "ready":
                _metric_add("vn30_membership_unavailable_results")
                payload = self._unavailable_payload(
                    requested_top_n,
                    membership,
                    membership_ms=membership_ms,
                    total_ms=max(0, int((perf_counter() - request_started) * 1000)),
                )
                payload = self._apply_canonical(payload, canonical, direct_ms)
                result_state = payload["data_state"]
                kind = "positive" if canonical["latest"] else "negative"
            else:
                histories_started = perf_counter()
                histories = self._load_histories(
                    membership["member_tickers"],
                    force_refresh=force_refresh,
                )
                histories_ms = max(0, int((perf_counter() - histories_started) * 1000))
                aggregate_started = perf_counter()
                payload = self._build_aggregate(
                    membership,
                    histories,
                    canonical,
                    requested_top_n,
                    membership_ms=membership_ms,
                    direct_ms=direct_ms,
                    histories_ms=histories_ms,
                    build_started=aggregate_started,
                    request_started=request_started,
                )
                result_state = payload["data_state"]
                component_counts = payload["component_counts"]
                kind = (
                    "positive"
                    if canonical["latest"] or component_counts["usable"] > 0
                    else "negative"
                )
            payload["cache_key_dimensions"] = {
                "schema_version": CACHE_VERSION,
                "provider_version": "v3",
                "scope": "vn30",
                "index_code": VN30_INDEX_CODE,
                "canonical_mode": VN30_CANONICAL_MODE,
                "decomposition_mode": VN30_DECOMPOSITION_MODE,
                "requested_from_date": requested_from.isoformat(),
                "requested_to_date": requested_to.isoformat(),
                "requested_session_count": VN30_HISTORY_SESSIONS,
                "membership_identity": membership_hash,
                "canonical_cache_identity": hashlib.sha256(
                    repr(
                        (
                            "v3",
                            "vn30",
                            VN30_CANONICAL_MODE,
                            requested_from.isoformat(),
                            requested_to.isoformat(),
                            VN30_HISTORY_SESSIONS,
                            CACHE_VERSION,
                        )
                    ).encode("ascii")
                ).hexdigest()[:16],
                "decomposition_cache_identity": hashlib.sha256(
                    repr(
                        (
                            "v3",
                            "vn30",
                            VN30_DECOMPOSITION_MODE,
                            membership_hash,
                            requested_from.isoformat(),
                            requested_to.isoformat(),
                            VN30_HISTORY_SESSIONS,
                            CACHE_VERSION,
                        )
                    ).encode("ascii")
                ).hexdigest()[:16],
                "expected_latest_completed_session": expected_completed.isoformat(),
            }
            entry = self._store_vn30(cache_key, payload, kind)
            payload = self._with_cache_metadata(payload, entry, cache_status, False)
            future.set_result(deepcopy(payload))
            return payload
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            total_ms = max(0, int((perf_counter() - request_started) * 1000))
            with _LOCK:
                _VN30_IN_FLIGHT.pop(cache_key, None)
                _VN30_WAITERS.pop(cache_key, None)
                _METRICS["vn30_active_in_flight"] = max(0, _METRICS["vn30_active_in_flight"] - 1)
                _METRICS["vn30_component_histories"] += len(membership["member_tickers"])
                for name in ("usable", "stale", "empty", "unavailable"):
                    _METRICS[f"vn30_{name}_components"] += component_counts[name]
                state_metric = f"vn30_{result_state}_results"
                if state_metric in _METRICS:
                    _METRICS[state_metric] += 1
                _METRICS["vn30_latency_count"] += 1
                _METRICS["vn30_latency_total_ms"] += total_ms
                _METRICS["vn30_latency_max_ms"] = max(_METRICS["vn30_latency_max_ms"], total_ms)
            logger.info(
                "vn30_foreign_flow_aggregate_complete",
                extra={
                    "vn30_foreign_flow": {
                        "membership_count": len(membership["member_tickers"]),
                        "usable_count": component_counts["usable"],
                        "data_state": result_state,
                        "duration_ms": total_ms,
                        "force_refresh": bool(force_refresh),
                    }
                },
            )

    @staticmethod
    def _normalize_membership(payload: Dict[str, Any]) -> Dict[str, Any]:
        rows = payload.get("rows") if isinstance(payload, dict) and isinstance(payload.get("rows"), list) else []
        members: List[str] = []
        seen = set()
        mismatched_rows = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_index = str(row.get("index_code") or VN30_INDEX_CODE).strip().upper()
            if row_index != VN30_INDEX_CODE:
                mismatched_rows += 1
                continue
            if not row.get("symbol"):
                continue
            try:
                ticker = _normalize_ticker(row.get("symbol"))
            except ValueError:
                continue
            if ticker not in seen:
                seen.add(ticker)
                members.append(ticker)
        diagnostics = payload.get("diagnostics") if isinstance(payload, dict) and isinstance(payload.get("diagnostics"), dict) else {}
        membership_too_large = len(members) > BATCH_MAX_TICKERS
        ready = (
            payload.get("status") == "ok"
            and bool(members)
            and mismatched_rows == 0
            and not membership_too_large
        )
        published_members = members if ready else []
        resolved_at = _iso_now()
        return {
            "status": "ready" if ready else "unavailable",
            "index_code": VN30_INDEX_CODE,
            "source": "SSI IndexComponents",
            "member_count": len(published_members),
            "component_count": len(published_members),
            "member_tickers": published_members,
            "cache_status": diagnostics.get("cache_status"),
            "failure_class": None if ready else (
                "membership_mismatch"
                if mismatched_rows
                else "membership_count_exceeded"
                if membership_too_large
                else diagnostics.get("failure_class") or "membership_unavailable"
            ),
            "reason": None if ready else "SSI VN30 membership is unavailable.",
            "fetched_at": resolved_at,
            "resolved_at": resolved_at,
        }

    def _load_histories(self, tickers: List[str], *, force_refresh: bool) -> Dict[str, Dict[str, Any]]:
        def load(ticker: str) -> Dict[str, Any]:
            try:
                return self._symbol_service.get_symbol_history(
                    ticker,
                    limit=VN30_HISTORY_SESSIONS,
                    force_refresh=force_refresh,
                )
            except Exception:
                return VietnamForeignFlowBatchService._unavailable_history(ticker)

        workers = min(self._max_concurrency, len(tickers))
        if workers <= 1:
            return {ticker: load(ticker) for ticker in tickers}
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="vn30-foreign-flow") as executor:
            futures = {ticker: executor.submit(load, ticker) for ticker in tickers}
            return {ticker: futures[ticker].result() for ticker in tickers}

    @staticmethod
    def _canonical_window(rows: List[Dict[str, Any]], requested: int) -> Dict[str, Any]:
        valid = [row for row in rows if row.get("valid_session")]
        selected = valid[-requested:]
        considered = rows[-requested:]
        partial = [row for row in considered if row.get("data_state") == "partial"]
        suspicious = [row for row in selected if row.get("suspicious_zero_session")]
        result: Dict[str, Any] = {
            "requested_sessions": requested,
            "covered_sessions": len(selected),
            "valid_sessions": len(selected),
            "partial_sessions": len(partial),
            "suspicious_sessions": len(suspicious),
            "missing_sessions": max(0, requested - len(selected)),
            "complete": len(selected) == requested and not partial,
            "start_date": selected[0]["trading_date"] if selected else None,
            "end_date": selected[-1]["trading_date"] if selected else None,
            "coverage_mode": "provider_aggregate",
            "constituent_coverage": "not_applicable",
        }
        for family in ("volume", "value"):
            for side in ("buy", "sell", "net"):
                values = [
                    row.get(f"foreign_{side}_{family}")
                    for row in selected
                    if row.get(f"foreign_{side}_{family}") is not None
                ]
                result[f"foreign_{side}_{family}"] = (
                    sum(values) if values else None
                )
        return result

    @classmethod
    def _build_canonical(
        cls,
        direct: Dict[str, Any],
        *,
        requested_from: str,
        requested_to: str,
        expected_completed: str,
        now: datetime,
    ) -> Dict[str, Any]:
        metric_names = (
            "foreign_buy_volume",
            "foreign_sell_volume",
            "foreign_buy_value",
            "foreign_sell_value",
        )
        accepted: List[Dict[str, Any]] = []
        excluded: List[Dict[str, str]] = []
        latest_returned = None
        for raw in direct.get("rows") or []:
            if not isinstance(raw, dict) or not _valid_date(raw.get("trading_date")):
                continue
            row = deepcopy(raw)
            trading_date = row["trading_date"]
            latest_returned = max(latest_returned or trading_date, trading_date)
            if trading_date > expected_completed:
                excluded.append(
                    {
                        "trading_date": trading_date,
                        "reason": "current_session_provisional",
                    }
                )
                continue
            presence = dict(row.get("field_presence") or {})
            missing = sum(
                presence.get(name) in {
                    "FIELD_ABSENT",
                    "FIELD_NULL",
                    "PARSE_FAILURE",
                    "PROVIDER_ROW_MISSING",
                }
                or row.get(name) is None
                for name in metric_names
            )
            explicit_zero = sum(
                presence.get(name) == "FIELD_PRESENT_EXPLICIT_ZERO"
                for name in metric_names
            )
            row.update(
                {
                    "source": SOURCE,
                    "provider_version": "v3",
                    "endpoint": VN30_CANONICAL_ENDPOINT,
                    "finality": "latest_completed_provider_session",
                    "freshness": None,
                    "coverage_mode": "provider_aggregate",
                    "constituent_coverage": "not_applicable",
                    "missing_field_count": missing,
                    "explicit_zero_field_count": explicit_zero,
                    "all_constituents_zero": False,
                    "suspicious_zero_session": explicit_zero == len(metric_names),
                    "anomaly": (
                        "provider_aggregate_explicit_zero"
                        if explicit_zero == len(metric_names)
                        else None
                    ),
                    "valid_session": missing == 0,
                    "data_state": "ready" if missing == 0 else "partial",
                    "state": "ready" if missing == 0 else "partial",
                }
            )
            accepted.append(row)
        accepted.sort(key=lambda row: row["trading_date"])
        valid = [row for row in accepted if row["valid_session"]]
        capability_unsupported = (
            direct.get("capability_status") == "unsupported"
            or (
                bool(accepted)
                and not valid
                and all(
                    all(row.get(name) is None for name in metric_names)
                    for row in accepted
                )
            )
        )
        latest = valid[-1] if valid else None
        selected_date = latest.get("trading_date") if latest else None
        lag = cls._session_gap(selected_date, expected_completed)
        if selected_date is None:
            freshness = "unavailable"
        elif lag == 0:
            freshness = "latest_completed_session"
        elif lag == 1:
            freshness = "stale_one_session"
        else:
            freshness = "stale_multiple_sessions"
        for row in accepted:
            row["freshness"] = (
                freshness if row.get("trading_date") == selected_date else "historical"
            )
        status = (
            "ready"
            if latest and freshness == "latest_completed_session"
            else "stale"
            if latest
            else "unavailable"
        )
        return {
            "status": status,
            "capability_status": (
                "unsupported"
                if capability_unsupported
                else "available"
                if latest
                else str(direct.get("capability_status") or "unavailable")
            ),
            "failure_class": (
                "DIRECT_INDEX_FOREIGN_FIELDS_UNSUPPORTED"
                if capability_unsupported
                else direct.get("failure_class")
                or (direct.get("diagnostics") or {}).get("failure_class")
            ),
            "usable": bool(latest),
            "mode": VN30_CANONICAL_MODE,
            "source": SOURCE,
            "provider_version": "v3",
            "endpoint": VN30_CANONICAL_ENDPOINT,
            "aggregation_mode": "provider_aggregate",
            "coverage_mode": "provider_aggregate",
            "constituent_coverage": "not_applicable",
            "trading_date": selected_date,
            "latest": latest,
            "windows": {
                "5": cls._canonical_window(accepted, 5),
                "20": cls._canonical_window(accepted, 20),
                "60": cls._canonical_window(accepted, 60),
            },
            "series": valid[-VN30_HISTORY_SESSIONS:],
            "diagnostics": {
                "requested_from_date": requested_from,
                "requested_to_date": requested_to,
                "latest_returned_date": latest_returned,
                "latest_completed_provider_session": expected_completed,
                "selected_canonical_date": selected_date,
                "excluded_dates": [item["trading_date"] for item in excluded],
                "exclusion_reasons": excluded,
                "session_lag": lag,
                "source_freshness": freshness,
                "returned_session_count": len(accepted),
                "valid_session_count": len(valid),
                "partial_session_count": sum(
                    row.get("data_state") == "partial" for row in accepted
                ),
                "provider_operation_count": int(
                    (direct.get("diagnostics") or {}).get(
                        "provider_operation_count", 0
                    )
                ),
                "required_fields": list(
                    (direct.get("diagnostics") or {}).get("required_fields")
                    or (
                        "totalForeignBuy",
                        "totalForeignSell",
                        "totalForeignBuyValue",
                        "totalForeignSellValue",
                    )
                ),
                "unsupported_fields": list(
                    (direct.get("diagnostics") or {}).get("unsupported_fields")
                    or (
                        (
                            "totalForeignBuy",
                            "totalForeignSell",
                            "totalForeignBuyValue",
                            "totalForeignSellValue",
                        )
                        if capability_unsupported
                        else ()
                    )
                ),
                "observed_row_count": int(
                    (direct.get("diagnostics") or {}).get(
                        "observed_row_count", len(accepted)
                    )
                ),
                "capability_cache_status": (
                    direct.get("diagnostics") or {}
                ).get("capability_cache_status"),
                "capability_checked_at": (
                    direct.get("diagnostics") or {}
                ).get("capability_checked_at"),
                "capability_ttl_seconds": (
                    direct.get("diagnostics") or {}
                ).get("capability_ttl_seconds"),
                "capability_refresh_reason": (
                    direct.get("diagnostics") or {}
                ).get("capability_refresh_reason"),
            },
        }

    @staticmethod
    def _apply_canonical(
        payload: Dict[str, Any], canonical: Dict[str, Any], direct_ms: int
    ) -> Dict[str, Any]:
        payload["canonical_source"] = canonical["source"]
        payload["canonical_provider_version"] = canonical["provider_version"]
        payload["canonical_endpoint"] = canonical["endpoint"]
        payload["canonical_aggregation_mode"] = canonical["mode"]
        payload["canonical_trading_date"] = canonical["trading_date"]
        payload["canonical"] = canonical
        decomposition = payload.get("decomposition") or {}
        decomposition_usable = bool(
            decomposition.get("latest")
            and decomposition.get("status") in {"ready", "partial", "stale"}
        )
        canonical_usable = bool(canonical.get("latest"))
        use_decomposition = not canonical_usable and decomposition_usable
        primary = decomposition if use_decomposition else canonical
        payload["latest"] = primary.get("latest")
        payload["windows"] = primary.get("windows") or {}
        payload["series"] = primary.get("series") or []
        payload["aggregate_session_dates"] = [
            row["trading_date"] for row in payload["series"]
        ]
        payload["source_endpoint"] = (
            SOURCE_ENDPOINT if use_decomposition else VN30_CANONICAL_ENDPOINT
        )
        payload["aggregation_basis"] = (
            "current_vn30_membership"
            if use_decomposition
            else "direct_index_provider_aggregate"
        )
        payload["primary_data_mode"] = (
            "current_membership_decomposition"
            if use_decomposition
            else "direct_index_canonical"
        )
        payload["data_state"] = (
            "ready"
            if canonical["status"] == "ready"
            and decomposition.get("status") == "ready"
            else "stale"
            if canonical["status"] == "stale" and canonical_usable
            else "partial"
            if canonical_usable or decomposition_usable
            else "unavailable"
        )
        payload["status"] = payload["data_state"]
        payload["usable"] = canonical_usable or decomposition_usable
        payload["capability_status"] = (
            "decomposition_ready_canonical_unsupported"
            if canonical.get("capability_status") == "unsupported"
            and decomposition_usable
            else "canonical_unsupported_decomposition_unavailable"
            if canonical.get("capability_status") == "unsupported"
            else "canonical_available"
            if canonical_usable
            else "unavailable"
        )
        membership_ready = payload.get("membership", {}).get("status") == "ready"
        payload["source_coverage"] = [
            {
                "source": "SSI V3 Direct VN30 Foreign Aggregate",
                "capability_status": canonical.get("capability_status"),
                "usable": canonical_usable,
                "failure_class": canonical.get("failure_class"),
            },
            {
                "source": "SSI V3 Symbol Foreign Data",
                "capability_status": (
                    "available" if decomposition_usable else "unavailable"
                ),
                "usable": decomposition_usable,
            },
            {
                "source": "SSI VN30 Index Components",
                "capability_status": (
                    "available" if membership_ready else "unavailable"
                ),
                "usable": membership_ready,
            },
        ]
        payload.setdefault("timing", {})["direct_index_ms"] = direct_ms
        return payload

    @staticmethod
    def _history_rows(history: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        rows = history.get("rows") if isinstance(history.get("rows"), list) else []
        return {
            row["trading_date"]: row
            for row in rows
            if isinstance(row, dict) and _valid_date(row.get("trading_date"))
        }

    @staticmethod
    def _metric_family_coverage(row: Optional[Dict[str, Any]], family: str) -> bool:
        if not row:
            return False
        return all(row.get(f"foreign_{side}_{family}") is not None for side in ("buy", "sell", "net"))

    @classmethod
    def _aggregate_day(
        cls,
        trading_date: str,
        tickers: List[str],
        rows_by_ticker: Dict[str, Dict[str, Dict[str, Any]]],
        histories: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {"trading_date": trading_date}
        any_numeric = False
        for family in ("volume", "value"):
            coverage = 0
            for side in ("buy", "sell", "net"):
                values = []
                for ticker in tickers:
                    row = rows_by_ticker[ticker].get(trading_date)
                    value = row.get(f"foreign_{side}_{family}") if row else None
                    if value is not None:
                        values.append(value)
                result[f"foreign_{side}_{family}"] = sum(values) if values else None
                any_numeric = any_numeric or bool(values)
            coverage = sum(
                cls._metric_family_coverage(rows_by_ticker[ticker].get(trading_date), family)
                for ticker in tickers
            )
            result[f"{family}_coverage_count"] = coverage
            result[f"{family}_coverage_ratio"] = coverage / len(tickers) if tickers else 0.0
            result[f"{family}_coverage"] = {
                "covered_components": coverage,
                "expected_components": len(tickers),
                "coverage_ratio": coverage / len(tickers) if tickers else 0.0,
                "complete": coverage == len(tickers) and bool(tickers),
            }
            net_values = {
                ticker: (rows_by_ticker[ticker].get(trading_date) or {}).get(f"foreign_net_{family}")
                for ticker in tickers
            }
            result[f"{family}_breadth"] = {
                "net_buy_count": sum(value is not None and value > 0 for value in net_values.values()),
                "net_sell_count": sum(value is not None and value < 0 for value in net_values.values()),
                "zero_count": sum(value == 0 for value in net_values.values()),
                "unavailable_count": sum(value is None for value in net_values.values()),
            }
        result["positive_components"] = result["value_breadth"]["net_buy_count"]
        result["negative_components"] = result["value_breadth"]["net_sell_count"]
        result["zero_components"] = result["value_breadth"]["zero_count"]
        result["missing_components"] = result["value_breadth"]["unavailable_count"]
        required_fields = (
            "foreign_buy_volume",
            "foreign_sell_volume",
            "foreign_buy_value",
            "foreign_sell_value",
        )
        explicit_zero_components = 0
        missing_field_components = 0
        for ticker in tickers:
            component_row = rows_by_ticker[ticker].get(trading_date)
            presence = (
                dict(component_row.get("field_presence") or {})
                if component_row
                else {}
            )
            if component_row is None:
                missing_field_components += 1
            elif all(
                presence.get(name) == "FIELD_PRESENT_EXPLICIT_ZERO"
                for name in required_fields
            ):
                explicit_zero_components += 1
            elif any(
                presence.get(name)
                in {
                    "FIELD_ABSENT",
                    "FIELD_NULL",
                    "PARSE_FAILURE",
                    "PROVIDER_ROW_MISSING",
                }
                or component_row.get(name) is None
                for name in required_fields
            ):
                missing_field_components += 1
        result["all_constituents_zero"] = (
            bool(tickers) and explicit_zero_components == len(tickers)
        )
        result["explicit_zero_component_count"] = explicit_zero_components
        result["missing_field_component_count"] = missing_field_components
        result["suspicious_zero_session"] = result["all_constituents_zero"]
        result["anomaly"] = (
            "all_constituents_explicit_zero"
            if result["all_constituents_zero"]
            else None
        )
        result["anomaly_code"] = result["anomaly"]
        result["anomaly_status"] = (
            "provider_backed_suspect"
            if result["all_constituents_zero"]
            else None
        )
        contributing = [
            ticker
            for ticker in tickers
            if any(
                (rows_by_ticker[ticker].get(trading_date) or {}).get(f"foreign_{side}_{family}") is not None
                for family in ("volume", "value")
                for side in ("buy", "sell", "net")
            )
        ]
        all_stale = bool(contributing) and all(histories[ticker].get("freshness") == "stale" for ticker in contributing)
        full = result["value_coverage_count"] == len(tickers) and result["volume_coverage_count"] == len(tickers)
        if not any_numeric:
            result["data_state"] = "unavailable"
        elif all_stale:
            result["data_state"] = "stale"
        elif full and missing_field_components == 0:
            result["data_state"] = "ready"
        else:
            result["data_state"] = "partial"
        result["state"] = result["data_state"]
        result["valid_session"] = result["data_state"] in {"ready", "stale"}
        return result

    @staticmethod
    def _aggregate_window(series: List[Dict[str, Any]], requested_sessions: int, member_count: int) -> Dict[str, Any]:
        selected = series[-requested_sessions:]
        valid = [row for row in selected if row.get("data_state") == "ready"]
        partial_count = sum(row.get("data_state") == "partial" for row in selected)
        suspicious_count = sum(
            bool(row.get("suspicious_zero_session")) for row in selected
        )
        result: Dict[str, Any] = {
            "requested_sessions": requested_sessions,
            "covered_sessions": len(selected),
            "valid_sessions": len(valid),
            "partial_sessions": partial_count,
            "suspicious_sessions": suspicious_count,
            "contains_provider_anomaly": suspicious_count > 0,
            "anomaly_sessions": [
                row["trading_date"]
                for row in selected
                if row.get("suspicious_zero_session")
            ],
            "anomaly_count": suspicious_count,
            "missing_sessions": max(0, requested_sessions - len(selected)),
            "complete": (
                len(selected) == requested_sessions
                and partial_count == 0
            ),
            "start_date": selected[0]["trading_date"] if selected else None,
            "end_date": selected[-1]["trading_date"] if selected else None,
        }
        for family in ("volume", "value"):
            for side in ("buy", "sell", "net"):
                values = [row[f"foreign_{side}_{family}"] for row in selected if row.get(f"foreign_{side}_{family}") is not None]
                result[f"foreign_{side}_{family}"] = sum(values) if values else None
            observed = sum(int(row.get(f"{family}_coverage_count") or 0) for row in selected)
            expected = member_count * requested_sessions
            result[f"{family}_component_sessions"] = observed
            result[f"{family}_coverage_ratio"] = observed / expected if expected else 0.0
            result[f"{family}_complete"] = len(selected) == requested_sessions and observed == expected
        result["positive_component_sessions"] = sum(int(row.get("positive_components") or 0) for row in selected)
        result["negative_component_sessions"] = sum(int(row.get("negative_components") or 0) for row in selected)
        result["zero_component_sessions"] = sum(int(row.get("zero_components") or 0) for row in selected)
        result["missing_component_sessions"] = sum(int(row.get("missing_components") or 0) for row in selected)
        return result

    @classmethod
    def _compose_component(
        cls,
        ticker: str,
        history: Dict[str, Any],
        rows_by_date: Dict[str, Dict[str, Any]],
        session_dates: List[str],
    ) -> Dict[str, Any]:
        global_latest = session_dates[-1] if session_dates else None
        latest = rows_by_date.get(global_latest) if global_latest else None
        own_dates = sorted(rows_by_date)
        has_same_date = latest is not None
        has_any_same_date_value = bool(
            latest
            and any(
                latest.get(f"foreign_{side}_{family}") is not None
                for family in ("volume", "value")
                for side in ("buy", "sell")
            )
        )
        component_state = (
            "ready"
            if has_same_date and has_any_same_date_value
            else "unavailable"
        )
        source_freshness = (
            "latest_completed_session"
            if has_same_date
            else "stale_one_session"
            if own_dates
            else "unavailable"
        )
        result: Dict[str, Any] = {
            "ticker": ticker,
            "data_state": component_state,
            "freshness": "fresh" if has_same_date else "stale" if own_dates else "unavailable",
            "source_freshness": source_freshness,
            "failure_class": history.get("failure_class"),
            "stale_reason": (
                history.get("stale_reason")
                if has_same_date
                else "No component row exists on the decomposition date."
            ),
            "latest_trading_date": own_dates[-1] if own_dates else None,
            "aggregate_latest_date": global_latest,
        }
        for family in ("volume", "value"):
            for side in ("buy", "sell", "net"):
                result[f"foreign_{side}_{family}"] = latest.get(f"foreign_{side}_{family}") if latest else None
        for size, suffix in ((5, "5d"), (20, "20d"), (60, "60d")):
            selected_dates = session_dates[-size:]
            selected_rows = [rows_by_date[day] for day in selected_dates if day in rows_by_date]
            for family in ("volume", "value"):
                for side in ("buy", "sell", "net"):
                    values = [row[f"foreign_{side}_{family}"] for row in selected_rows if row.get(f"foreign_{side}_{family}") is not None]
                    result[f"foreign_{side}_{family}_{suffix}"] = sum(values) if values else None
                covered = sum(cls._metric_family_coverage(rows_by_date.get(day), family) for day in selected_dates)
                result[f"{family}_covered_sessions_{suffix}"] = covered
                result[f"{family}_complete_{suffix}"] = len(selected_dates) == size and covered == size
            result[f"window_end_date_{suffix}"] = selected_dates[-1] if selected_dates else None
        return result

    @staticmethod
    def _ranking_pair(components: List[Dict[str, Any]], key: str, date_key: str, top_n: int) -> Dict[str, Any]:
        entries = [
            {
                "ticker": row["ticker"],
                "value": row[key],
                "trading_date": row.get(date_key),
                "data_state": row["data_state"],
            }
            for row in components
            if row.get(key) is not None and row.get(key) != 0 and row.get("data_state") in {"ready", "stale"}
        ]
        return {
            "top_buy": sorted((item for item in entries if item["value"] > 0), key=lambda item: (-item["value"], item["ticker"]))[:top_n],
            "top_sell": sorted((item for item in entries if item["value"] < 0), key=lambda item: (item["value"], item["ticker"]))[:top_n],
        }

    def _build_aggregate(
        self,
        membership: Dict[str, Any],
        histories: Dict[str, Dict[str, Any]],
        canonical: Dict[str, Any],
        top_n: int,
        *,
        membership_ms: int,
        direct_ms: int,
        histories_ms: int,
        build_started: float,
        request_started: float,
    ) -> Dict[str, Any]:
        tickers = membership["member_tickers"]
        rows_by_ticker = {ticker: self._history_rows(histories[ticker]) for ticker in tickers}
        available_dates = sorted({day for rows in rows_by_ticker.values() for day in rows})
        canonical_date = canonical.get("trading_date")
        decomposition_date = (
            canonical_date
            if canonical_date
            else available_dates[-1]
            if available_dates
            else None
        )
        session_dates = [
            day for day in available_dates
            if decomposition_date is None or day <= decomposition_date
        ][-VN30_HISTORY_SESSIONS:]
        series = [self._aggregate_day(day, tickers, rows_by_ticker, histories) for day in session_dates]
        components = [self._compose_component(ticker, histories[ticker], rows_by_ticker[ticker], session_dates) for ticker in tickers]
        counts = {
            "usable": sum(row["data_state"] in {"ready", "stale"} for row in components),
            "stale": sum(row["data_state"] == "stale" or row["freshness"] == "stale" for row in components),
            "empty": sum(row["data_state"] == "empty" for row in components),
            "unavailable": sum(row["data_state"] == "unavailable" for row in components),
        }
        latest = series[-1] if series else None
        if counts["usable"] == 0:
            state = "unavailable"
        elif counts["stale"] == len(tickers):
            state = "stale"
        elif latest and latest["data_state"] == "ready" and counts["usable"] == len(tickers):
            state = "ready"
        else:
            state = "partial"
        rankings = {
            "latest_net_value": self._ranking_pair(components, "foreign_net_value", "aggregate_latest_date", top_n),
            "latest_net_volume": self._ranking_pair(components, "foreign_net_volume", "aggregate_latest_date", top_n),
            "net_value_5d": self._ranking_pair(components, "foreign_net_value_5d", "window_end_date_5d", top_n),
            "net_volume_5d": self._ranking_pair(components, "foreign_net_volume_5d", "window_end_date_5d", top_n),
            "net_value_20d": self._ranking_pair(components, "foreign_net_value_20d", "window_end_date_20d", top_n),
            "net_volume_20d": self._ranking_pair(components, "foreign_net_volume_20d", "window_end_date_20d", top_n),
            "net_value_60d": self._ranking_pair(components, "foreign_net_value_60d", "window_end_date_60d", top_n),
            "net_volume_60d": self._ranking_pair(components, "foreign_net_volume_60d", "window_end_date_60d", top_n),
        }
        decomposition_latest = series[-1] if series else None
        reconciliation = self._reconcile(
            canonical.get("latest"), decomposition_latest
        )
        build_ms = max(0, int((perf_counter() - build_started) * 1000))
        payload = {
            "scope": "vn30",
            "index_code": VN30_INDEX_CODE,
            "source": SOURCE,
            "source_endpoint": VN30_CANONICAL_ENDPOINT,
            "membership_source": "SSI IndexComponents",
            "volume_unit": VOLUME_UNIT,
            "value_unit": VALUE_UNIT,
            "finality": FINALITY,
            "aggregation_basis": "current_vn30_membership",
            "historical_constituent_correct": False,
            "data_state": state,
            "decomposition_aggregation_mode": VN30_DECOMPOSITION_MODE,
            "decomposition_universe": "current_vn30_membership",
            "decomposition_date": decomposition_date,
            "membership": membership,
            "aggregate_session_dates": [],
            "latest": None,
            "windows": {},
            "series": [],
            "components": components,
            "component_counts": counts,
            "rankings": rankings,
            "decomposition": {
                "status": state,
                "data_state": state,
                "usable": bool(decomposition_latest),
                "mode": VN30_DECOMPOSITION_MODE,
                "aggregation_mode": VN30_DECOMPOSITION_MODE,
                "aggregation_basis": "current_vn30_membership",
                "universe": "current_vn30_membership",
                "date": decomposition_date,
                "decomposition_date": decomposition_date,
                "latest_completed_session": decomposition_date,
                "membership_source": "SSI IndexComponents",
                "member_count": len(tickers),
                "historical_constituent_correct": False,
                "source": SOURCE,
                "provider_version": "v3",
                "series": series,
                "latest": decomposition_latest,
                "windows": {
                    "5": self._aggregate_window(series, 5, len(tickers)),
                    "20": self._aggregate_window(series, 20, len(tickers)),
                    "60": self._aggregate_window(series, 60, len(tickers)),
                },
                "components": components,
                "component_counts": counts,
                "rankings": rankings,
                "reconciliation": reconciliation,
                "anomaly_sessions": [
                    row["trading_date"]
                    for row in series
                    if row.get("suspicious_zero_session")
                ],
                "anomaly_count": sum(
                    bool(row.get("suspicious_zero_session")) for row in series
                ),
            },
            "cache": {},
            "timing": {
                "membership_ms": membership_ms,
                "direct_index_ms": direct_ms,
                "component_histories_ms": histories_ms,
                "aggregate_build_ms": build_ms,
                "total_ms": max(0, int((perf_counter() - request_started) * 1000)),
            },
            "fetched_at": _iso_now(),
        }
        return self._apply_canonical(payload, canonical, direct_ms)

    @staticmethod
    def _reconcile(
        direct: Optional[Dict[str, Any]],
        decomposition: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        direct_date = direct.get("trading_date") if direct else None
        decomposition_date = decomposition.get("trading_date") if decomposition else None
        result: Dict[str, Any] = {
            "direct_index_date": direct_date,
            "decomposition_date": decomposition_date,
            "direct_foreign_buy_value": direct.get("foreign_buy_value") if direct else None,
            "decomposition_foreign_buy_value": decomposition.get("foreign_buy_value") if decomposition else None,
            "direct_foreign_sell_value": direct.get("foreign_sell_value") if direct else None,
            "decomposition_foreign_sell_value": decomposition.get("foreign_sell_value") if decomposition else None,
            "direct_net_value": direct.get("foreign_net_value") if direct else None,
            "decomposition_net_value": decomposition.get("foreign_net_value") if decomposition else None,
            "difference_value": None,
            "difference_ratio": None,
            "reconciliation_status": "not_comparable",
        }
        if not direct or not decomposition:
            return result
        if direct_date != decomposition_date:
            result["reconciliation_status"] = "date_mismatch"
            return result
        direct_net = direct.get("foreign_net_value")
        decomposition_net = decomposition.get("foreign_net_value")
        if direct_net is None or decomposition_net is None:
            return result
        difference = decomposition_net - direct_net
        result["difference_value"] = difference
        result["difference_ratio"] = (
            abs(difference) / abs(direct_net) if direct_net else None
        )
        if difference == 0:
            result["reconciliation_status"] = "exact"
        elif result["difference_ratio"] is not None and result["difference_ratio"] <= 0.01:
            result["reconciliation_status"] = "within_tolerance"
        else:
            result["reconciliation_status"] = "differs_expected_membership_method"
        return result

    @staticmethod
    def _unavailable_payload(top_n: int, membership: Dict[str, Any], *, membership_ms: int, total_ms: int) -> Dict[str, Any]:
        empty_pair = {"top_buy": [], "top_sell": []}
        empty_window = {
            "requested_sessions": 5,
            "covered_sessions": 0,
            "complete": False,
            "start_date": None,
            "end_date": None,
            "foreign_buy_volume": None,
            "foreign_sell_volume": None,
            "foreign_net_volume": None,
            "foreign_buy_value": None,
            "foreign_sell_value": None,
            "foreign_net_value": None,
            "volume_component_sessions": 0,
            "volume_coverage_ratio": 0.0,
            "volume_complete": False,
            "value_component_sessions": 0,
            "value_coverage_ratio": 0.0,
            "value_complete": False,
            "positive_component_sessions": 0,
            "negative_component_sessions": 0,
            "zero_component_sessions": 0,
            "missing_component_sessions": 0,
        }
        window_20 = dict(empty_window, requested_sessions=20)
        window_60 = dict(empty_window, requested_sessions=60)
        return {
            "scope": "vn30",
            "index_code": VN30_INDEX_CODE,
            "source": SOURCE,
            "source_endpoint": VN30_CANONICAL_ENDPOINT,
            "membership_source": "SSI IndexComponents",
            "volume_unit": VOLUME_UNIT,
            "value_unit": VALUE_UNIT,
            "finality": FINALITY,
            "aggregation_basis": "current_vn30_membership",
            "historical_constituent_correct": False,
            "decomposition_aggregation_mode": VN30_DECOMPOSITION_MODE,
            "decomposition_universe": "current_vn30_membership",
            "decomposition_date": None,
            "data_state": "unavailable",
            "status": "unavailable",
            "usable": False,
            "capability_status": "unavailable",
            "primary_data_mode": "current_membership_decomposition",
            "source_coverage": [],
            "membership": membership,
            "aggregate_session_dates": [],
            "latest": None,
            "windows": {"5": empty_window, "20": window_20, "60": window_60},
            "series": [],
            "components": [],
            "component_counts": {"usable": 0, "stale": 0, "empty": 0, "unavailable": 0},
            "rankings": {
                "latest_net_value": deepcopy(empty_pair),
                "latest_net_volume": deepcopy(empty_pair),
                "net_value_5d": deepcopy(empty_pair),
                "net_volume_5d": deepcopy(empty_pair),
                "net_value_20d": deepcopy(empty_pair),
                "net_volume_20d": deepcopy(empty_pair),
                "net_value_60d": deepcopy(empty_pair),
                "net_volume_60d": deepcopy(empty_pair),
            },
            "decomposition": {
                "status": "unavailable",
                "data_state": "unavailable",
                "usable": False,
                "mode": VN30_DECOMPOSITION_MODE,
                "aggregation_mode": VN30_DECOMPOSITION_MODE,
                "aggregation_basis": "current_vn30_membership",
                "universe": "current_vn30_membership",
                "date": None,
                "decomposition_date": None,
                "latest_completed_session": None,
                "membership_source": "SSI IndexComponents",
                "member_count": 0,
                "historical_constituent_correct": False,
                "source": SOURCE,
                "provider_version": "v3",
                "series": [],
                "latest": None,
                "windows": {"5": empty_window, "20": window_20, "60": window_60},
                "components": [],
                "component_counts": {
                    "usable": 0,
                    "stale": 0,
                    "empty": 0,
                    "unavailable": 0,
                },
                "rankings": {
                    "latest_net_value": deepcopy(empty_pair),
                    "latest_net_volume": deepcopy(empty_pair),
                    "net_value_5d": deepcopy(empty_pair),
                    "net_volume_5d": deepcopy(empty_pair),
                    "net_value_20d": deepcopy(empty_pair),
                    "net_volume_20d": deepcopy(empty_pair),
                    "net_value_60d": deepcopy(empty_pair),
                    "net_volume_60d": deepcopy(empty_pair),
                },
                "reconciliation": {
                    "direct_index_date": None,
                    "decomposition_date": None,
                    "reconciliation_status": "not_comparable",
                },
                "anomaly_sessions": [],
                "anomaly_count": 0,
            },
            "cache": {},
            "timing": {"membership_ms": membership_ms, "component_histories_ms": 0, "aggregate_build_ms": 0, "total_ms": total_ms},
            "fetched_at": _iso_now(),
        }

    @staticmethod
    def _store_vn30(key: Tuple[Any, ...], payload: Dict[str, Any], kind: str) -> _CacheEntry:
        now = _utc_now()
        ttl = VN30_AGGREGATE_CACHE_TTL_SECONDS if kind == "positive" else VN30_AGGREGATE_NEGATIVE_CACHE_TTL_SECONDS
        entry = _CacheEntry(
            payload=deepcopy(payload),
            kind=kind,
            fetched_at=now,
            expires_at=now + timedelta(seconds=ttl),
            stale_until=now + timedelta(seconds=ttl),
        )
        with _LOCK:
            _VN30_CACHE[key] = entry
            _VN30_CACHE.move_to_end(key)
            while len(_VN30_CACHE) > VN30_AGGREGATE_CACHE_MAX_ENTRIES:
                _VN30_CACHE.popitem(last=False)
        return entry

    @staticmethod
    def _with_cache_metadata(payload: Dict[str, Any], entry: _CacheEntry, status: str, coalesced: bool) -> Dict[str, Any]:
        result = deepcopy(payload)
        now = _utc_now()
        result["cache"] = {
            "status": status,
            "coalesced": coalesced,
            "age_seconds": max(0, int((now - entry.fetched_at).total_seconds())),
            "ttl_seconds": VN30_AGGREGATE_CACHE_TTL_SECONDS if entry.kind == "positive" else VN30_AGGREGATE_NEGATIVE_CACHE_TTL_SECONDS,
            "negative": entry.kind != "positive",
        }
        canonical = result.get("canonical")
        if isinstance(canonical, dict):
            diagnostics = canonical.setdefault("diagnostics", {})
            diagnostics.update(
                {
                    "cache_status": status,
                    "cache_age_seconds": result["cache"]["age_seconds"],
                    "cache_ttl_seconds": result["cache"]["ttl_seconds"],
                }
            )
        return result
