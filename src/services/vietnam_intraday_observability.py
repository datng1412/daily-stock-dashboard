# -*- coding: utf-8 -*-
"""Bounded process-local observability for the VN intraday chart path.

This module deliberately tracks scalar counters and one sanitized last-result
snapshot only. State resets when the worker process restarts and is not shared
between multiple application workers.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from threading import Lock
from typing import Any, Dict, Literal, Optional
import re


IntradayDateKind = Literal["current", "completed"]
IntradayProviderOutcome = Literal["success", "no_data", "unavailable", "failure"]

_LOCK = Lock()


def _initial_state() -> Dict[str, Any]:
    return {
        "requests_total": 0,
        "requests_current_date": 0,
        "requests_completed_date": 0,
        "requests_force_refresh": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "cache_refreshes": 0,
        "empty_cache_hits": 0,
        "negative_cache_hits": 0,
        "stale_recoveries": 0,
        "stale_recovery_rejected_too_old": 0,
        "provider_calls": 0,
        "provider_successes": 0,
        "provider_no_data": 0,
        "provider_unavailable": 0,
        "provider_failures": 0,
        "provider_latency_count": 0,
        "provider_latency_total_ms": 0,
        "provider_latency_min_ms": None,
        "provider_latency_max_ms": None,
        "provider_latency_last_ms": None,
        "last_provider_outcome": None,
        "last_successful_provider_fetch_at": None,
        "last_provider_result": None,
        "last_returned_row_count": 0,
        "last_usable_bar_count": 0,
        "last_rejected_row_count": 0,
        "last_duplicate_minute_count": 0,
        "last_newest_bar_age_seconds": None,
        "last_freshness": None,
        "in_flight_fetches": 0,
        "current_same_key_waiters": 0,
        "coalesced_waiters": 0,
        "coalesced_requests": 0,
        "maximum_same_key_waiters": 0,
    }


_STATE = _initial_state()


def sanitize_intraday_failure_class(value: object) -> Optional[str]:
    """Return a bounded identifier, never a provider exception message."""
    text = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    return text[:80] or None


def reset_vietnam_intraday_observability() -> None:
    """Reset worker-local counters for deterministic tests/manual diagnostics."""
    with _LOCK:
        _STATE.clear()
        _STATE.update(_initial_state())


def observe_intraday_request(date_kind: IntradayDateKind, *, force_refresh: bool) -> None:
    with _LOCK:
        _STATE["requests_total"] += 1
        _STATE[f"requests_{date_kind}_date"] += 1
        if force_refresh:
            _STATE["requests_force_refresh"] += 1


def observe_intraday_cache(action: Literal["hit", "miss", "refresh"], *, entry_kind: str = "positive") -> None:
    counter = {"hit": "cache_hits", "miss": "cache_misses", "refresh": "cache_refreshes"}[action]
    with _LOCK:
        _STATE[counter] += 1
        if action == "hit" and entry_kind == "empty":
            _STATE["empty_cache_hits"] += 1
        elif action == "hit" and entry_kind == "negative":
            _STATE["negative_cache_hits"] += 1


def observe_intraday_stale_recovery(*, used: bool = False, rejected_too_old: bool = False) -> None:
    with _LOCK:
        if used:
            _STATE["stale_recoveries"] += 1
        if rejected_too_old:
            _STATE["stale_recovery_rejected_too_old"] += 1


def observe_intraday_inflight_started() -> None:
    with _LOCK:
        _STATE["in_flight_fetches"] += 1


def observe_intraday_inflight_finished() -> None:
    with _LOCK:
        _STATE["in_flight_fetches"] = max(0, _STATE["in_flight_fetches"] - 1)


def observe_intraday_coalesced_waiter(same_key_waiters: int) -> None:
    bounded_waiters = max(1, int(same_key_waiters))
    with _LOCK:
        _STATE["coalesced_waiters"] += 1
        _STATE["coalesced_requests"] += 1
        _STATE["current_same_key_waiters"] = bounded_waiters
        _STATE["maximum_same_key_waiters"] = max(
            _STATE["maximum_same_key_waiters"], bounded_waiters
        )


def observe_intraday_waiter_finished() -> None:
    with _LOCK:
        _STATE["current_same_key_waiters"] = max(0, _STATE["current_same_key_waiters"] - 1)


def observe_intraday_provider_fetch(
    *,
    outcome: IntradayProviderOutcome,
    date_kind: IntradayDateKind,
    trading_date: str,
    session_state: str,
    latency_ms: int,
    returned_rows: int,
    usable_bars: int,
    rejected_rows: int,
    duplicate_minutes: int,
    newest_bar_age_seconds: Optional[int],
    freshness: Optional[str],
    stale_recovery: bool,
    failure_class: object = None,
    at: str,
) -> Dict[str, Any]:
    """Record one actual provider call and return its sanitized log payload."""
    latency = max(0, int(latency_ms))
    returned = max(0, int(returned_rows))
    usable = max(0, int(usable_bars))
    rejected = max(0, int(rejected_rows))
    duplicates = max(0, int(duplicate_minutes))
    newest_age = None if newest_bar_age_seconds is None else max(0, int(newest_bar_age_seconds))
    sanitized_failure = sanitize_intraday_failure_class(failure_class)
    result = {
        "result": outcome,
        "date_kind": date_kind,
        "trading_date": str(trading_date)[:10],
        "session_state": str(session_state)[:40],
        "latency_ms": latency,
        "returned_row_count": returned,
        "usable_bar_count": usable,
        "rejected_row_count": rejected,
        "duplicate_minute_count": duplicates,
        "newest_bar_age_seconds": newest_age,
        "freshness": str(freshness)[:24] if freshness else None,
        "stale_recovery": bool(stale_recovery),
        "failure_class": sanitized_failure,
        "at": str(at)[:40],
    }
    with _LOCK:
        _STATE["provider_calls"] += 1
        outcome_counter = {
            "success": "provider_successes",
            "no_data": "provider_no_data",
            "unavailable": "provider_unavailable",
            "failure": "provider_failures",
        }[outcome]
        _STATE[outcome_counter] += 1
        _STATE["provider_latency_count"] += 1
        _STATE["provider_latency_total_ms"] += latency
        minimum = _STATE["provider_latency_min_ms"]
        maximum = _STATE["provider_latency_max_ms"]
        _STATE["provider_latency_min_ms"] = latency if minimum is None else min(minimum, latency)
        _STATE["provider_latency_max_ms"] = latency if maximum is None else max(maximum, latency)
        _STATE["provider_latency_last_ms"] = latency
        _STATE["last_provider_outcome"] = outcome
        if outcome == "success":
            _STATE["last_successful_provider_fetch_at"] = result["at"]
        _STATE["last_provider_result"] = deepcopy(result)
        _STATE["last_returned_row_count"] = returned
        _STATE["last_usable_bar_count"] = usable
        _STATE["last_rejected_row_count"] = rejected
        _STATE["last_duplicate_minute_count"] = duplicates
        _STATE["last_newest_bar_age_seconds"] = newest_age
        _STATE["last_freshness"] = result["freshness"]
    return result


def vietnam_intraday_observability_snapshot(
    *,
    now: datetime,
    scheduled_session_state: str,
    cache_entries: int,
    current_date_entries: int,
    completed_date_entries: int,
) -> Dict[str, Any]:
    with _LOCK:
        state = deepcopy(_STATE)
    calls = state["provider_calls"]
    last_result = state["last_provider_result"]
    if calls == 0 or last_result is None:
        status = "unknown"
    elif last_result["result"] in {"unavailable", "failure"} or last_result["stale_recovery"]:
        status = "degraded"
    elif last_result["result"] == "no_data" and last_result["session_state"] not in {
        "pre_open", "lunch", "closed"
    }:
        status = "degraded"
    else:
        status = "ok"

    latency_count = state["provider_latency_count"]
    latency_average = (
        round(state["provider_latency_total_ms"] / latency_count, 2)
        if latency_count
        else None
    )
    return {
        "status": status,
        "timezone": "Asia/Ho_Chi_Minh",
        "current_vietnam_time": now.isoformat(),
        "scheduled_session_state": scheduled_session_state,
        "process_scope": {"metrics_scope": "process_local", "resets_on_restart": True},
        "cache": {
            "entries": max(0, int(cache_entries)),
            "current_date_entries": max(0, int(current_date_entries)),
            "completed_date_entries": max(0, int(completed_date_entries)),
            "in_flight_fetches": state["in_flight_fetches"],
        },
        "requests": {
            "total": state["requests_total"],
            "current_date": state["requests_current_date"],
            "completed_date": state["requests_completed_date"],
            "force_refresh": state["requests_force_refresh"],
            "coalesced": state["coalesced_requests"],
        },
        "provider": {
            "calls": calls,
            "successes": state["provider_successes"],
            "no_data": state["provider_no_data"],
            "unavailable": state["provider_unavailable"],
            "failures": state["provider_failures"],
            "last_successful_fetch_at": state["last_successful_provider_fetch_at"],
            "latency_ms": {
                "count": latency_count,
                "min": state["provider_latency_min_ms"],
                "max": state["provider_latency_max_ms"],
                "average": latency_average,
                "last": state["provider_latency_last_ms"],
            },
        },
        "cache_activity": {
            "hits": state["cache_hits"],
            "misses": state["cache_misses"],
            "refreshes": state["cache_refreshes"],
            "empty_hits": state["empty_cache_hits"],
            "negative_hits": state["negative_cache_hits"],
            "stale_recoveries": state["stale_recoveries"],
            "stale_recovery_rejected_too_old": state["stale_recovery_rejected_too_old"],
        },
        "data_quality": {
            "last_returned_row_count": state["last_returned_row_count"],
            "last_usable_bar_count": state["last_usable_bar_count"],
            "last_rejected_row_count": state["last_rejected_row_count"],
            "last_duplicate_minute_count": state["last_duplicate_minute_count"],
            "last_newest_bar_age_seconds": state["last_newest_bar_age_seconds"],
            "last_freshness": state["last_freshness"],
        },
        "concurrency": {
            "current_same_key_waiters": state["current_same_key_waiters"],
            "coalesced_waiters": state["coalesced_waiters"],
            "maximum_same_key_waiters": state["maximum_same_key_waiters"],
        },
        "last_provider_result": last_result,
    }
