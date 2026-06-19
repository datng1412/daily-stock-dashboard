# -*- coding: utf-8 -*-
"""Process-local Vietnam dashboard fetch observability.

The counters here are intentionally lightweight and in-memory. They must not
store credentials, headers, or raw provider payloads.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import logging
from threading import Lock
from time import perf_counter
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)
_LOCK = Lock()

_MOZYFIN_DEFAULTS: Dict[str, Any] = {
    "status": "disabled",
    "source": "legacy",
    "reason": "Mozyfin is disabled for VN dashboard runtime.",
    "watchlist_requests_total": 0,
    "watchlist_cache_hits_total": 0,
    "watchlist_cache_misses_total": 0,
    "singleflight_waits_total": 0,
    "last_watchlist_request_at": None,
    "last_fetch_at": None,
    "last_cache_key": None,
    "last_tickers_count": 0,
    "last_fetch_duration_ms": None,
}

_KBS_DEFAULTS: Dict[str, Any] = {
    "quote_requests_total": 0,
    "quote_success_total": 0,
    "quote_unavailable_total": 0,
    "trade_requests_total": 0,
    "trade_success_total": 0,
    "trade_unavailable_total": 0,
    "last_quote_request_at": None,
    "last_trade_request_at": None,
    "last_quote_tickers_count": 0,
    "last_trade_symbol": None,
    "last_error": None,
    "last_raw_error_present": False,
}

_STATE: Dict[str, Dict[str, Any]] = {
    "mozyfin": deepcopy(_MOZYFIN_DEFAULTS),
    "kbs": deepcopy(_KBS_DEFAULTS),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_cache_key(key: Any) -> str:
    return str(key)[:240]


def reset_vietnam_observability() -> None:
    """Reset counters for tests and local diagnostics."""
    try:
        with _LOCK:
            _STATE["mozyfin"] = deepcopy(_MOZYFIN_DEFAULTS)
            _STATE["kbs"] = deepcopy(_KBS_DEFAULTS)
    except Exception as exc:
        logger.warning("Vietnam observability reset failed: %s", exc)


def observe_mozyfin_watchlist_request(tickers_count: int) -> None:
    try:
        with _LOCK:
            state = _STATE["mozyfin"]
            state["watchlist_requests_total"] += 1
            state["last_watchlist_request_at"] = _now_iso()
            state["last_tickers_count"] = max(0, int(tickers_count))
    except Exception as exc:
        logger.warning("Vietnam observability Mozyfin request update failed: %s", exc)


def observe_mozyfin_cache_result(status: str, cache_key: Any, *, waited: bool = False) -> None:
    try:
        with _LOCK:
            state = _STATE["mozyfin"]
            if status == "hit":
                state["watchlist_cache_hits_total"] += 1
            elif status in {"miss", "refresh", "stale", "error"}:
                state["watchlist_cache_misses_total"] += 1
            if waited:
                state["singleflight_waits_total"] += 1
            state["last_cache_key"] = _safe_cache_key(cache_key)
    except Exception as exc:
        logger.warning("Vietnam observability Mozyfin cache update failed: %s", exc)


def observe_mozyfin_fetch(cache_key: Any, duration_ms: int) -> None:
    try:
        with _LOCK:
            state = _STATE["mozyfin"]
            state["last_fetch_at"] = _now_iso()
            state["last_cache_key"] = _safe_cache_key(cache_key)
            state["last_fetch_duration_ms"] = max(0, int(duration_ms))
    except Exception as exc:
        logger.warning("Vietnam observability Mozyfin fetch update failed: %s", exc)


def observe_kbs_quote_request(tickers_count: int) -> None:
    try:
        with _LOCK:
            state = _STATE["kbs"]
            state["quote_requests_total"] += 1
            state["last_quote_request_at"] = _now_iso()
            state["last_quote_tickers_count"] = max(0, int(tickers_count))
    except Exception as exc:
        logger.warning("Vietnam observability KBS quote request update failed: %s", exc)


def observe_kbs_quote_result(status: str, *, error: Optional[str] = None, raw_error_present: bool = False) -> None:
    try:
        with _LOCK:
            state = _STATE["kbs"]
            if status == "ok":
                state["quote_success_total"] += 1
            else:
                state["quote_unavailable_total"] += 1
            if error:
                state["last_error"] = str(error)[:160]
            state["last_raw_error_present"] = bool(raw_error_present)
    except Exception as exc:
        logger.warning("Vietnam observability KBS quote result update failed: %s", exc)


def observe_kbs_trade_request(symbol: Optional[str]) -> None:
    try:
        with _LOCK:
            state = _STATE["kbs"]
            state["trade_requests_total"] += 1
            state["last_trade_request_at"] = _now_iso()
            state["last_trade_symbol"] = str(symbol or "")[:16] or None
    except Exception as exc:
        logger.warning("Vietnam observability KBS trade request update failed: %s", exc)


def observe_kbs_trade_result(status: str, *, error: Optional[str] = None, raw_error_present: bool = False) -> None:
    try:
        with _LOCK:
            state = _STATE["kbs"]
            if status == "ok":
                state["trade_success_total"] += 1
            else:
                state["trade_unavailable_total"] += 1
            if error:
                state["last_error"] = str(error)[:160]
            state["last_raw_error_present"] = bool(raw_error_present)
    except Exception as exc:
        logger.warning("Vietnam observability KBS trade result update failed: %s", exc)


def vietnam_observability_snapshot() -> Dict[str, Any]:
    try:
        with _LOCK:
            return {
                "market": "VN",
                "status": "ok",
                "mozyfin": deepcopy(_STATE["mozyfin"]),
                "kbs": deepcopy(_STATE["kbs"]),
            }
    except Exception as exc:
        logger.warning("Vietnam observability snapshot failed: %s", exc)
        return {
            "market": "VN",
            "status": "ok",
            "mozyfin": deepcopy(_MOZYFIN_DEFAULTS),
            "kbs": deepcopy(_KBS_DEFAULTS),
        }


def monotonic_ms() -> int:
    return int(perf_counter() * 1000)
