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
from data_provider.ssi_streaming_snapshot_store import SsiStreamingSnapshotStore
from src.config import get_config


_RUNTIME_LOCK = threading.RLock()
_RUNTIME_MANAGER: Optional[SsiStreamingRealtimeManager] = None
_RUNTIME_STARTED_BY_LIFECYCLE = False
_RUNTIME_WANTS_STREAMING = False
_RUNTIME_SHUTDOWN_REQUESTED = False
_RUNTIME_BOOTSTRAP_SYMBOLS: List[str] = []
_RUNTIME_SNAPSHOT_RESTORED = False
_RUNTIME_MONITOR_STOP: Optional[threading.Event] = None
_RUNTIME_MONITOR_THREAD: Optional[threading.Thread] = None
_RUNTIME_MONITOR_INTERVAL_SECONDS = 1.0

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


def is_ssi_streaming_realtime_monitor_running() -> bool:
    """Return whether the process-local reconnect monitor is alive."""
    with _RUNTIME_LOCK:
        return bool(_RUNTIME_MONITOR_THREAD and _RUNTIME_MONITOR_THREAD.is_alive())


def reset_ssi_streaming_realtime_lifecycle_for_tests() -> None:
    """Reset process-local lifecycle state for deterministic tests."""
    global _RUNTIME_MANAGER, _RUNTIME_STARTED_BY_LIFECYCLE, _RUNTIME_WANTS_STREAMING, _RUNTIME_SHUTDOWN_REQUESTED, _RUNTIME_BOOTSTRAP_SYMBOLS, _RUNTIME_SNAPSHOT_RESTORED
    _stop_reconnect_monitor()
    with _RUNTIME_LOCK:
        manager = _RUNTIME_MANAGER
        _RUNTIME_MANAGER = None
        _RUNTIME_STARTED_BY_LIFECYCLE = False
        _RUNTIME_WANTS_STREAMING = False
        _RUNTIME_SHUTDOWN_REQUESTED = False
        _RUNTIME_BOOTSTRAP_SYMBOLS = []
        _RUNTIME_SNAPSHOT_RESTORED = False
    if manager is not None:
        manager.mark_shutdown()
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


def run_ssi_streaming_realtime_monitor_tick() -> Dict[str, Any]:
    """Run one reconnect monitor tick for tests or the lifecycle monitor."""
    with _RUNTIME_LOCK:
        manager = _RUNTIME_MANAGER
        wants_streaming = _RUNTIME_WANTS_STREAMING
    if manager is None:
        return {"bootstrap_status": "not_started", "manager_state": "stopped"}
    return manager.monitor_tick(wants_streaming=wants_streaming)


def _monitor_loop(stop_event: threading.Event) -> None:
    while not stop_event.wait(_RUNTIME_MONITOR_INTERVAL_SECONDS):
        try:
            run_ssi_streaming_realtime_monitor_tick()
        except Exception:
            continue


def _start_reconnect_monitor(*, interval_seconds: float = 1.0) -> None:
    global _RUNTIME_MONITOR_STOP, _RUNTIME_MONITOR_THREAD, _RUNTIME_MONITOR_INTERVAL_SECONDS
    with _RUNTIME_LOCK:
        if _RUNTIME_MONITOR_THREAD is not None and _RUNTIME_MONITOR_THREAD.is_alive():
            return
        _RUNTIME_MONITOR_INTERVAL_SECONDS = max(0.1, float(interval_seconds or 1.0))
        stop_event = threading.Event()
        thread = threading.Thread(
            target=_monitor_loop,
            args=(stop_event,),
            name="ssi-streaming-realtime-monitor",
            daemon=True,
        )
        _RUNTIME_MONITOR_STOP = stop_event
        _RUNTIME_MONITOR_THREAD = thread
        thread.start()


def _stop_reconnect_monitor() -> None:
    global _RUNTIME_MONITOR_STOP, _RUNTIME_MONITOR_THREAD
    with _RUNTIME_LOCK:
        stop_event = _RUNTIME_MONITOR_STOP
        thread = _RUNTIME_MONITOR_THREAD
        _RUNTIME_MONITOR_STOP = None
        _RUNTIME_MONITOR_THREAD = None
    if stop_event is not None:
        stop_event.set()
    if thread is not None and thread.is_alive():
        thread.join(timeout=2.0)


def bootstrap_ssi_streaming_realtime(
    *,
    config: Optional[Any] = None,
    client_factory: Optional[Callable[[], SsiRealtimeStreamClient]] = None,
    start_monitor: bool = True,
    monitor_interval_seconds: float = 1.0,
) -> Dict[str, Any]:
    """Start the backend SSI realtime manager when config explicitly allows it.

    Startup remains best-effort and non-fatal. Request handlers do not call this
    function; they only read the process-local manager if startup created it.
    """
    global _RUNTIME_MANAGER, _RUNTIME_STARTED_BY_LIFECYCLE, _RUNTIME_WANTS_STREAMING, _RUNTIME_BOOTSTRAP_SYMBOLS, _RUNTIME_SNAPSHOT_RESTORED

    cfg = config or get_config()
    with _RUNTIME_LOCK:
        if _RUNTIME_SHUTDOWN_REQUESTED:
            manager = _RUNTIME_MANAGER
            return manager.status() if manager is not None else {
                "bootstrap_status": "shutdown",
                "manager_state": "stopped",
            }
    enabled = bool(getattr(cfg, "ssi_streaming_realtime_enabled", False))
    if not enabled:
        _stop_reconnect_monitor()
        with _RUNTIME_LOCK:
            _RUNTIME_WANTS_STREAMING = False
            _RUNTIME_BOOTSTRAP_SYMBOLS = []
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
        if not _RUNTIME_SNAPSHOT_RESTORED:
            store = SsiStreamingSnapshotStore(
                enabled=bool(getattr(cfg, "ssi_streaming_snapshot_enabled", False)),
                path=getattr(cfg, "ssi_streaming_snapshot_path", "runtime/ssi_streaming_last_known.v1.json"),
                write_interval_seconds=getattr(cfg, "ssi_streaming_snapshot_write_interval_seconds", 5),
                trade_limit=min(
                    int(getattr(cfg, "ssi_streaming_snapshot_trade_limit", 50) or 50),
                    int(getattr(manager.trade_tape_cache, "max_rows_per_symbol", 50) or 50),
                ),
                max_symbols=getattr(cfg, "ssi_streaming_snapshot_max_symbols", 128),
                max_age_days=getattr(cfg, "ssi_streaming_snapshot_max_age_days", 7),
            )
            manager.set_snapshot_store(store)
            snapshot = store.load()
            if snapshot.get("captured_at"):
                manager.restore_persisted_snapshot(snapshot)
            _RUNTIME_SNAPSHOT_RESTORED = True

    if not symbols:
        _stop_reconnect_monitor()
        with _RUNTIME_LOCK:
            _RUNTIME_WANTS_STREAMING = False
            _RUNTIME_BOOTSTRAP_SYMBOLS = []
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
        _stop_reconnect_monitor()
        with _RUNTIME_LOCK:
            _RUNTIME_WANTS_STREAMING = False
            _RUNTIME_BOOTSTRAP_SYMBOLS = []
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
    with _RUNTIME_LOCK:
        if _RUNTIME_SHUTDOWN_REQUESTED:
            return manager.status()
        _RUNTIME_WANTS_STREAMING = True
        _RUNTIME_BOOTSTRAP_SYMBOLS = list(safe_symbols)
    status = manager.start(safe_symbols)
    manager.set_bootstrap_context(
        status="running" if status.get("manager_state") == "running" else "start_failed",
        reason=status.get("latest_error"),
        symbols=safe_symbols,
        rejected_symbols=rejected_symbols,
        started_by_lifecycle=True,
    )
    status = manager.status()
    with _RUNTIME_LOCK:
        _RUNTIME_STARTED_BY_LIFECYCLE = (
            status.get("manager_state") == "running" and not _RUNTIME_SHUTDOWN_REQUESTED
        )
        should_start_monitor = start_monitor and not _RUNTIME_SHUTDOWN_REQUESTED
    if should_start_monitor:
        _start_reconnect_monitor(interval_seconds=monitor_interval_seconds)
    return status


def shutdown_ssi_streaming_realtime() -> Dict[str, Any]:
    """Stop the backend lifecycle manager only if startup owns it."""
    global _RUNTIME_STARTED_BY_LIFECYCLE, _RUNTIME_WANTS_STREAMING, _RUNTIME_SHUTDOWN_REQUESTED, _RUNTIME_BOOTSTRAP_SYMBOLS
    _stop_reconnect_monitor()
    with _RUNTIME_LOCK:
        if _RUNTIME_SHUTDOWN_REQUESTED:
            return {"bootstrap_status": "not_started", "manager_state": "stopped"}
        manager = _RUNTIME_MANAGER
        _RUNTIME_STARTED_BY_LIFECYCLE = False
        _RUNTIME_WANTS_STREAMING = False
        _RUNTIME_SHUTDOWN_REQUESTED = True
        _RUNTIME_BOOTSTRAP_SYMBOLS = []
    if manager is None:
        return {"bootstrap_status": "not_started", "manager_state": "stopped"}
    try:
        manager.mark_shutdown()
        manager.close_streaming_snapshot_store()
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
