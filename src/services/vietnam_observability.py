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

from src.config import get_config


logger = logging.getLogger(__name__)
_LOCK = Lock()

_MOZYFIN_DEFAULTS: Dict[str, Any] = {
    "status": "disabled",
    "source": "legacy",
    "reason": "Mozyfin is disabled for VN dashboard runtime.",
}

_DASHBOARD_RUNTIME_DEFAULTS: Dict[str, Any] = {
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
    "status": "disabled",
    "source": "legacy_optional",
    "reason": "KBS is disabled for VN dashboard runtime unless legacy mode is explicitly enabled.",
    "legacy_allowed": False,
    "enabled": False,
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

_SSI_CORE_DEFAULTS: Dict[str, Any] = {
    "status": "unavailable",
    "source": "SSI",
    "reason": "SSI FastConnect core market-data support is available when SSI is enabled and credentials are configured.",
}

_SSI_INTRADAY_DEFAULTS: Dict[str, Any] = {
    "status": "unavailable",
    "source": "SSI",
    "reason": "SSI IntradayOhlc support is available through the VN watchlist/company intraday blocks when enabled.",
}

_SSI_REALTIME_DEFAULTS: Dict[str, Any] = {
    "status": "unavailable",
    "source": "SSI",
    "reason": "SSI realtime endpoint support is exposed through the VN realtime endpoint when available.",
}

_SSI_TRADE_TAPE_DEFAULTS: Dict[str, Any] = {
    "status": "unavailable",
    "source": "SSI",
    "reason": "SSI trade tape endpoint support is exposed through the VN trade tape endpoint when available.",
}

_STATE: Dict[str, Dict[str, Any]] = {
    "mozyfin": deepcopy(_MOZYFIN_DEFAULTS),
    "dashboard_runtime": deepcopy(_DASHBOARD_RUNTIME_DEFAULTS),
    "kbs": deepcopy(_KBS_DEFAULTS),
    "ssi_core": deepcopy(_SSI_CORE_DEFAULTS),
    "ssi_intraday": deepcopy(_SSI_INTRADAY_DEFAULTS),
    "ssi_realtime": deepcopy(_SSI_REALTIME_DEFAULTS),
    "ssi_trade_tape": deepcopy(_SSI_TRADE_TAPE_DEFAULTS),
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
            _STATE["dashboard_runtime"] = deepcopy(_DASHBOARD_RUNTIME_DEFAULTS)
            _STATE["kbs"] = deepcopy(_KBS_DEFAULTS)
            _STATE["ssi_core"] = deepcopy(_SSI_CORE_DEFAULTS)
            _STATE["ssi_intraday"] = deepcopy(_SSI_INTRADAY_DEFAULTS)
            _STATE["ssi_realtime"] = deepcopy(_SSI_REALTIME_DEFAULTS)
            _STATE["ssi_trade_tape"] = deepcopy(_SSI_TRADE_TAPE_DEFAULTS)
    except Exception as exc:
        logger.warning("Vietnam observability reset failed: %s", exc)


def observe_mozyfin_watchlist_request(tickers_count: int) -> None:
    try:
        with _LOCK:
            state = _STATE["dashboard_runtime"]
            state["watchlist_requests_total"] += 1
            state["last_watchlist_request_at"] = _now_iso()
            state["last_tickers_count"] = max(0, int(tickers_count))
    except Exception as exc:
        logger.warning("Vietnam observability Mozyfin request update failed: %s", exc)


def observe_mozyfin_cache_result(status: str, cache_key: Any, *, waited: bool = False) -> None:
    try:
        with _LOCK:
            state = _STATE["dashboard_runtime"]
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
            state = _STATE["dashboard_runtime"]
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
            config = get_config()
            kbs = deepcopy(_STATE["kbs"])
            legacy_allowed = bool(getattr(config, "vn_allow_legacy_kbs_provider", False))
            kbs_enabled = bool(getattr(config, "kbs_enabled", False))
            kbs["legacy_allowed"] = legacy_allowed
            kbs["enabled"] = bool(legacy_allowed and kbs_enabled)
            kbs["status"] = "ok" if kbs["enabled"] else "disabled"
            kbs["reason"] = None if kbs["enabled"] else "KBS legacy provider is disabled for normal VN dashboard runtime."
            ssi_core = deepcopy(_STATE["ssi_core"])
            ssi_core_enabled = bool(getattr(config, "ssi_fastconnect_enabled", False))
            ssi_core["enabled"] = ssi_core_enabled
            if ssi_core_enabled:
                ssi_core["status"] = "ok"
                ssi_core["reason"] = None
            else:
                ssi_core["status"] = "disabled"
                ssi_core["reason"] = "SSI FastConnect is disabled."
            ssi_intraday = deepcopy(_STATE["ssi_intraday"])
            ssi_intraday_enabled = bool(getattr(config, "ssi_fastconnect_intraday_enabled", True))
            ssi_intraday["enabled"] = ssi_intraday_enabled
            if ssi_intraday_enabled:
                ssi_intraday["status"] = "ok" if ssi_core_enabled else "unavailable"
                ssi_intraday["reason"] = None if ssi_core_enabled else "SSI IntradayOhlc is enabled but SSI FastConnect is disabled."
            else:
                ssi_intraday["status"] = "disabled"
                ssi_intraday["reason"] = "SSI IntradayOhlc is disabled."
            ssi_realtime = deepcopy(_STATE["ssi_realtime"])
            ssi_trade_tape = deepcopy(_STATE["ssi_trade_tape"])
            if not bool(getattr(config, "ssi_fastconnect_realtime_enabled", True)):
                ssi_realtime["status"] = "disabled"
                ssi_realtime["reason"] = "SSI realtime is disabled."
            if not bool(getattr(config, "ssi_fastconnect_trade_tape_enabled", True)):
                ssi_trade_tape["status"] = "disabled"
                ssi_trade_tape["reason"] = "SSI trade tape is disabled."
            streaming = _streaming_lifecycle_snapshot()
            return {
                "market": "VN",
                "status": "ok",
                "mozyfin": deepcopy(_STATE["mozyfin"]),
                "dashboard_runtime": deepcopy(_STATE["dashboard_runtime"]),
                "kbs": kbs,
                "ssi_core": ssi_core,
                "ssi_intraday": ssi_intraday,
                "ssi_realtime": ssi_realtime,
                "ssi_trade_tape": ssi_trade_tape,
                "streaming": streaming,
            }
    except Exception as exc:
        logger.warning("Vietnam observability snapshot failed: %s", exc)
        return {
            "market": "VN",
            "status": "ok",
            "mozyfin": deepcopy(_MOZYFIN_DEFAULTS),
            "dashboard_runtime": deepcopy(_DASHBOARD_RUNTIME_DEFAULTS),
            "kbs": deepcopy(_KBS_DEFAULTS),
            "ssi_core": deepcopy(_SSI_CORE_DEFAULTS),
            "ssi_intraday": deepcopy(_SSI_INTRADAY_DEFAULTS),
            "ssi_realtime": deepcopy(_SSI_REALTIME_DEFAULTS),
            "ssi_trade_tape": deepcopy(_SSI_TRADE_TAPE_DEFAULTS),
            "streaming": _empty_streaming_lifecycle_snapshot(),
        }


def _empty_streaming_lifecycle_snapshot() -> Dict[str, Any]:
    return {
        "scope": "process_local",
        "overall_state": "unknown",
        "transports": [],
        "contexts": {},
        "session": {},
        "multi_worker_note": "Each worker owns an independent SSI connection cohort and process-local metrics.",
    }


def _streaming_lifecycle_snapshot() -> Dict[str, Any]:
    """Read manager state without constructing clients or mutating lifecycle."""
    try:
        from src.services.ssi_streaming_realtime_lifecycle import (
            get_existing_ssi_streaming_realtime_manager,
        )

        manager = get_existing_ssi_streaming_realtime_manager()
        if manager is None:
            return _empty_streaming_lifecycle_snapshot()
        return manager.lifecycle_snapshot()
    except Exception:
        return _empty_streaming_lifecycle_snapshot()


def monotonic_ms() -> int:
    return int(perf_counter() * 1000)
