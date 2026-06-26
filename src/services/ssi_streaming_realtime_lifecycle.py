# -*- coding: utf-8 -*-
"""FastAPI lifecycle bootstrap for SSI streaming realtime.

This module owns the backend process-local streaming manager reference. It is
side-effect free on import: no official SSI package import, client construction,
thread startup, or network work happens until `bootstrap_ssi_streaming_realtime`
is called from application startup.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Iterable
from typing import Any, Callable, Dict, List, Optional, Tuple

from data_provider.ssi_fastconnect_fetcher import SsiFastConnectFetcher
from data_provider.ssi_streaming_realtime import (
    SsiRealtimeStreamClient,
    SsiStreamingRealtimeManager,
    SSI_STREAMING_REALTIME_BOOTSTRAP_EMPTY_REASON,
    SSI_STREAMING_REALTIME_DISABLED_REASON,
    build_symbol_channel,
    normalize_streaming_symbols,
    sanitize_streaming_error,
)
from src.config import get_config


_RUNTIME_LOCK = threading.RLock()
_RUNTIME_MANAGER: Optional[SsiStreamingRealtimeManager] = None
_RUNTIME_STARTED_BY_LIFECYCLE = False

_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9._-]+$")


def parse_bootstrap_symbols(value: Any) -> Tuple[List[str], List[str]]:
    """Parse comma-separated bootstrap symbols and reject unsafe values."""
    if isinstance(value, str):
        raw_symbols = value.split(",")
    elif isinstance(value, Iterable):
        raw_symbols = list(value)
    else:
        raw_symbols = []

    accepted: List[str] = []
    rejected: List[str] = []
    seen = set()
    for raw_symbol in raw_symbols:
        symbol = str(raw_symbol or "").strip().upper()
        if not symbol:
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        if symbol == "ALL" or "*" in symbol or not _SYMBOL_PATTERN.match(symbol):
            rejected.append(symbol)
            continue
        accepted.append(symbol)
    return accepted, rejected


def get_existing_ssi_streaming_realtime_manager() -> Optional[SsiStreamingRealtimeManager]:
    """Return the backend lifecycle manager if startup created one."""
    with _RUNTIME_LOCK:
        return _RUNTIME_MANAGER


def reset_ssi_streaming_realtime_lifecycle_for_tests() -> None:
    """Reset process-local lifecycle state for deterministic tests."""
    global _RUNTIME_MANAGER, _RUNTIME_STARTED_BY_LIFECYCLE
    with _RUNTIME_LOCK:
        manager = _RUNTIME_MANAGER
        _RUNTIME_MANAGER = None
        _RUNTIME_STARTED_BY_LIFECYCLE = False
    if manager is not None:
        manager.stop()


def _new_manager(
    *,
    config: Any,
    client_factory: Optional[Callable[[], SsiRealtimeStreamClient]] = None,
) -> SsiStreamingRealtimeManager:
    fetcher = SsiFastConnectFetcher(
        config=config,
        streaming_realtime_client_factory=client_factory,
    )
    return fetcher.streaming_realtime_manager


def bootstrap_ssi_streaming_realtime(
    *,
    config: Optional[Any] = None,
    client_factory: Optional[Callable[[], SsiRealtimeStreamClient]] = None,
) -> Dict[str, Any]:
    """Start the backend SSI realtime manager when config explicitly allows it.

    Startup remains best-effort and non-fatal. Request handlers do not call this
    function; they only read the process-local manager if startup created it.
    """
    global _RUNTIME_MANAGER, _RUNTIME_STARTED_BY_LIFECYCLE

    cfg = config or get_config()
    enabled = bool(getattr(cfg, "ssi_streaming_realtime_enabled", False))
    if not enabled:
        return {
            "bootstrap_status": "disabled",
            "reason": SSI_STREAMING_REALTIME_DISABLED_REASON,
            "manager_state": "disabled",
            "bootstrap_symbols": [],
            "bootstrap_rejected_symbols": [],
        }

    symbols, rejected_symbols = parse_bootstrap_symbols(
        getattr(cfg, "ssi_streaming_realtime_bootstrap_symbols", "")
    )

    with _RUNTIME_LOCK:
        manager = _RUNTIME_MANAGER
        if manager is None:
            manager = _new_manager(config=cfg, client_factory=client_factory)
            _RUNTIME_MANAGER = manager

    if not symbols:
        manager.set_bootstrap_context(
            status="symbols_empty",
            reason=SSI_STREAMING_REALTIME_BOOTSTRAP_EMPTY_REASON,
            symbols=[],
            rejected_symbols=rejected_symbols,
            started_by_lifecycle=False,
        )
        status = manager.status()
        status.update(
            {
                "bootstrap_status": "symbols_empty",
                "bootstrap_reason": SSI_STREAMING_REALTIME_BOOTSTRAP_EMPTY_REASON,
                "bootstrap_symbols": [],
                "bootstrap_rejected_symbols": rejected_symbols,
            }
        )
        return status

    safe_symbols: List[str] = []
    for symbol in symbols:
        try:
            build_symbol_channel(
                symbol,
                getattr(cfg, "ssi_streaming_realtime_channel_template", None) or None,
            )
            safe_symbols.append(symbol)
        except Exception:
            rejected_symbols.append(symbol)

    if not safe_symbols:
        manager.set_bootstrap_context(
            status="symbols_empty",
            reason=SSI_STREAMING_REALTIME_BOOTSTRAP_EMPTY_REASON,
            symbols=[],
            rejected_symbols=rejected_symbols,
            started_by_lifecycle=False,
        )
        status = manager.status()
        status.update(
            {
                "bootstrap_status": "symbols_empty",
                "bootstrap_reason": SSI_STREAMING_REALTIME_BOOTSTRAP_EMPTY_REASON,
                "bootstrap_symbols": [],
                "bootstrap_rejected_symbols": normalize_streaming_symbols(rejected_symbols),
            }
        )
        return status

    manager.set_bootstrap_context(
        status="starting",
        symbols=safe_symbols,
        rejected_symbols=rejected_symbols,
        started_by_lifecycle=True,
    )
    status = manager.start(safe_symbols)
    manager.set_bootstrap_context(
        status="running" if status.get("manager_state") == "running" else "start_failed",
        reason=status.get("latest_error"),
        symbols=safe_symbols,
        rejected_symbols=rejected_symbols,
        started_by_lifecycle=status.get("manager_state") == "running",
    )
    status = manager.status()
    with _RUNTIME_LOCK:
        _RUNTIME_STARTED_BY_LIFECYCLE = status.get("manager_state") == "running"
    return status


def shutdown_ssi_streaming_realtime() -> Dict[str, Any]:
    """Stop the backend lifecycle manager only if startup owns it."""
    global _RUNTIME_STARTED_BY_LIFECYCLE
    with _RUNTIME_LOCK:
        manager = _RUNTIME_MANAGER
        should_stop = _RUNTIME_STARTED_BY_LIFECYCLE
        _RUNTIME_STARTED_BY_LIFECYCLE = False
    if manager is None or not should_stop:
        return {"bootstrap_status": "not_started", "manager_state": "stopped"}
    try:
        status = manager.stop()
        manager.set_bootstrap_context(
            status="stopped",
            reason=None,
            symbols=status.get("requested_symbols") or [],
            rejected_symbols=status.get("bootstrap_rejected_symbols") or [],
            started_by_lifecycle=False,
        )
        return manager.status()
    except Exception as exc:  # pragma: no cover - defensive shutdown path
        return {
            "bootstrap_status": "stop_error",
            "manager_state": "errored",
            "latest_error": sanitize_streaming_error(exc),
        }
