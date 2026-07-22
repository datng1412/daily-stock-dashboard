# -*- coding: utf-8 -*-
"""Bounded SSI DailyStockPrice history for one VN symbol's foreign flow."""

from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import logging
import math
import re
from threading import RLock
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional, Tuple

from data_provider.ssi_fastconnect_fetcher import SsiFastConnectFetcher
from data_provider.ssi_provider_protocol import SsiRestProvider
from data_provider.ssi_provider_router import create_ssi_rest_provider_router


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
CACHE_VERSION = "v2"
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
VN30_INDEX_CODE = "VN30"
VN30_HISTORY_SESSIONS = 20
VN30_AGGREGATE_CACHE_TTL_SECONDS = 300
VN30_AGGREGATE_NEGATIVE_CACHE_TTL_SECONDS = 60
VN30_AGGREGATE_CACHE_MAX_ENTRIES = 16
VN30_PUBLIC_SOURCE_ENDPOINT = "DailyStockPrice"
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
_CACHE: "OrderedDict[Tuple[Any, ...], _CacheEntry]" = OrderedDict()
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
        }
        if not any(value is not None for key, value in row.items() if key != "trading_date"):
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
        fetcher: Optional[SsiFastConnectFetcher] = None,
        *,
        rest_provider: Optional[SsiRestProvider] = None,
    ):
        self._fetcher = fetcher
        self._rest_provider = rest_provider
        self._rest_provider_lock = RLock()

    def _get_rest_provider(self) -> SsiRestProvider:
        if self._rest_provider is None:
            with self._rest_provider_lock:
                if self._rest_provider is None:
                    self._rest_provider = create_ssi_rest_provider_router(v2_fetcher=self._fetcher)
                    if self._fetcher is None:
                        adapter = self._rest_provider.provider
                        self._fetcher = getattr(adapter, "fetcher", None)
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
                if entry is not None and entry.expires_at > now and not force_refresh:
                    _CACHE.move_to_end(key)
                    if entry.kind == "positive":
                        _METRICS["cache_hits"] += 1
                    elif entry.kind == "empty":
                        _METRICS["empty_cache_hits"] += 1
                    else:
                        _METRICS["negative_cache_hits"] += 1
                    return deepcopy(entry.payload)
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
                if failure_class == "empty_response":
                    _metric_add("provider_empty_results")
                    payload = self._build_payload(ticker, mode, requested_limit, parsed_from, parsed_to, [], "empty", "empty", None)
                    self._finish_provider_metrics(started, ticker, mode, requested_limit, parsed_from, parsed_to, "empty", 0, failure_class, attempts, pages_used, cache_outcome)
                    return payload, "empty"
                _metric_add("provider_failures")
                _metric_add("unavailable_results")
                payload = self._build_payload(ticker, mode, requested_limit, parsed_from, parsed_to, [], "unavailable", "unavailable", failure_class)
                failure_cache_outcome = "stale_recovery" if stale_available else cache_outcome
                self._finish_provider_metrics(started, ticker, mode, requested_limit, parsed_from, parsed_to, "unavailable", 0, failure_class, attempts, pages_used, failure_cache_outcome)
                return payload, "negative"
            rows, stats = _normalize_rows(all_rows)
            stats["duplicate_date_count"] += max(0, int(provider_result.get("duplicate_date_count") or 0))
            if mode == "recent_sessions":
                rows = rows[-int(requested_limit):]
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
            self._finish_provider_metrics(started, ticker, mode, requested_limit, parsed_from, parsed_to, state, len(rows), None, attempts, pages_used, cache_outcome)
            return payload, "positive" if rows else "empty"
        except Exception:
            _metric_add("provider_failures")
            _metric_add("unavailable_results")
            failure_class = "provider_exception"
            with _LOCK:
                _METRICS["last_failure_class"] = failure_class
            payload = self._build_payload(ticker, mode, requested_limit, parsed_from, parsed_to, [], "unavailable", "unavailable", failure_class)
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
        }


class VietnamForeignFlowBatchService:
    """Compose bounded watchlist summaries from the authoritative symbol service."""

    def __init__(
        self,
        symbol_service: Optional[VietnamForeignFlowService] = None,
        *,
        max_concurrency: int = BATCH_MAX_CONCURRENCY,
    ) -> None:
        self._symbol_service = symbol_service or VietnamForeignFlowService()
        self._max_concurrency = max(1, min(int(max_concurrency), BATCH_MAX_CONCURRENCY))

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
    def _unavailable_history(ticker: str) -> Dict[str, Any]:
        return VietnamForeignFlowService._build_payload(
            ticker,
            "recent_sessions",
            20,
            None,
            None,
            [],
            "unavailable",
            "unavailable",
            "provider_exception",
        )

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
    """Aggregate SSI daily foreign flow for the current SSI-derived VN30 membership."""

    def __init__(
        self,
        symbol_service: Optional[VietnamForeignFlowService] = None,
        market_service: Optional[Any] = None,
        *,
        max_concurrency: int = BATCH_MAX_CONCURRENCY,
    ) -> None:
        self._symbol_service = symbol_service or VietnamForeignFlowService()
        self._market_service = market_service
        self._max_concurrency = max(1, min(int(max_concurrency), BATCH_MAX_CONCURRENCY))

    def _get_market_service(self) -> Any:
        if self._market_service is None:
            from src.services.vietnam_market_service import VietnamMarketService

            self._market_service = VietnamMarketService()
        return self._market_service

    def get_vn30_aggregate(
        self,
        *,
        top_n: int = BATCH_DEFAULT_TOP_N,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        requested_top_n = int(top_n)
        if not 1 <= requested_top_n <= BATCH_MAX_TOP_N:
            raise ValueError(f"top_n must be between 1 and {BATCH_MAX_TOP_N}")
        request_started = perf_counter()
        _metric_add("vn30_requests")
        if force_refresh:
            _metric_add("vn30_force_refresh_requests")

        membership_started = perf_counter()
        membership_payload = self._get_market_service().build_index_components(
            VN30_INDEX_CODE,
            force_refresh=force_refresh,
        )
        membership_ms = max(0, int((perf_counter() - membership_started) * 1000))
        membership = self._normalize_membership(membership_payload)
        membership_hash = hashlib.sha256(
            ",".join(membership["member_tickers"]).encode("ascii", errors="ignore")
        ).hexdigest()[:16]
        cache_key = (
            SOURCE,
            SOURCE_ENDPOINT,
            VN30_INDEX_CODE,
            membership_hash,
            VN30_HISTORY_SESSIONS,
            requested_top_n,
            CACHE_VERSION,
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
                if entry is not None and entry.expires_at > now and not force_refresh:
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
                cache_status = "refresh" if force_refresh else "miss"
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
            if membership["status"] != "ready":
                _metric_add("vn30_membership_unavailable_results")
                payload = self._unavailable_payload(
                    requested_top_n,
                    membership,
                    membership_ms=membership_ms,
                    total_ms=max(0, int((perf_counter() - request_started) * 1000)),
                )
                kind = "negative"
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
                    requested_top_n,
                    membership_ms=membership_ms,
                    histories_ms=histories_ms,
                    build_started=aggregate_started,
                    request_started=request_started,
                )
                result_state = payload["data_state"]
                component_counts = payload["component_counts"]
                kind = "positive" if component_counts["usable"] > 0 else "negative"
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
        elif full:
            result["data_state"] = "ready"
        else:
            result["data_state"] = "partial"
        result["state"] = result["data_state"]
        return result

    @staticmethod
    def _aggregate_window(series: List[Dict[str, Any]], requested_sessions: int, member_count: int) -> Dict[str, Any]:
        selected = series[-requested_sessions:]
        result: Dict[str, Any] = {
            "requested_sessions": requested_sessions,
            "covered_sessions": len(selected),
            "complete": len(selected) == requested_sessions,
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
        result: Dict[str, Any] = {
            "ticker": ticker,
            "data_state": history.get("data_state") if history.get("data_state") in {"ready", "stale", "empty", "unavailable"} else "unavailable",
            "freshness": history.get("freshness") if history.get("freshness") in {"fresh", "stale", "empty", "unavailable"} else "unavailable",
            "failure_class": history.get("failure_class"),
            "stale_reason": history.get("stale_reason"),
            "latest_trading_date": own_dates[-1] if own_dates else None,
            "aggregate_latest_date": global_latest,
        }
        for family in ("volume", "value"):
            for side in ("buy", "sell", "net"):
                result[f"foreign_{side}_{family}"] = latest.get(f"foreign_{side}_{family}") if latest else None
        for size, suffix in ((5, "5d"), (20, "20d")):
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
        top_n: int,
        *,
        membership_ms: int,
        histories_ms: int,
        build_started: float,
        request_started: float,
    ) -> Dict[str, Any]:
        tickers = membership["member_tickers"]
        rows_by_ticker = {ticker: self._history_rows(histories[ticker]) for ticker in tickers}
        session_dates = sorted({day for rows in rows_by_ticker.values() for day in rows})[-VN30_HISTORY_SESSIONS:]
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
        }
        build_ms = max(0, int((perf_counter() - build_started) * 1000))
        return {
            "scope": "vn30",
            "index_code": VN30_INDEX_CODE,
            "source": SOURCE,
            "source_endpoint": VN30_PUBLIC_SOURCE_ENDPOINT,
            "membership_source": "SSI IndexComponents",
            "volume_unit": VOLUME_UNIT,
            "value_unit": VALUE_UNIT,
            "finality": FINALITY,
            "aggregation_basis": "current_vn30_membership",
            "historical_constituent_correct": False,
            "data_state": state,
            "membership": membership,
            "aggregate_session_dates": session_dates,
            "latest": latest,
            "windows": {
                "5": self._aggregate_window(series, 5, len(tickers)),
                "20": self._aggregate_window(series, 20, len(tickers)),
            },
            "series": series,
            "components": components,
            "component_counts": counts,
            "rankings": rankings,
            "cache": {},
            "timing": {
                "membership_ms": membership_ms,
                "component_histories_ms": histories_ms,
                "aggregate_build_ms": build_ms,
                "total_ms": max(0, int((perf_counter() - request_started) * 1000)),
            },
            "fetched_at": _iso_now(),
        }

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
        return {
            "scope": "vn30",
            "index_code": VN30_INDEX_CODE,
            "source": SOURCE,
            "source_endpoint": VN30_PUBLIC_SOURCE_ENDPOINT,
            "membership_source": "SSI IndexComponents",
            "volume_unit": VOLUME_UNIT,
            "value_unit": VALUE_UNIT,
            "finality": FINALITY,
            "aggregation_basis": "current_vn30_membership",
            "historical_constituent_correct": False,
            "data_state": "unavailable",
            "membership": membership,
            "aggregate_session_dates": [],
            "latest": None,
            "windows": {"5": empty_window, "20": window_20},
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
        return result
