# -*- coding: utf-8 -*-
"""Bounded SSI DailyStockPrice history for one VN symbol's foreign flow."""

from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import Future
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import logging
import math
import re
from threading import RLock
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional, Tuple

from data_provider.ssi_fastconnect_fetcher import SsiFastConnectFetcher


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
CACHE_VERSION = "v1"
POSITIVE_CURRENT_TTL_SECONDS = 300
POSITIVE_COMPLETED_TTL_SECONDS = 3_600
EMPTY_TTL_SECONDS = 60
NEGATIVE_TTL_SECONDS = 30
STALE_MAX_SECONDS = 86_400
CACHE_MAX_ENTRIES = 512
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


class VietnamForeignFlowService:
    def __init__(self, fetcher: Optional[SsiFastConnectFetcher] = None):
        self._fetcher = fetcher

    def _get_fetcher(self) -> SsiFastConnectFetcher:
        if self._fetcher is None:
            self._fetcher = SsiFastConnectFetcher()
        return self._fetcher

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
                provider_result = self._get_fetcher().get_daily_stock_price(
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
