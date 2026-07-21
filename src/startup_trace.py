"""Bounded, secret-free lifecycle tracing for FastAPI pre-bind startup."""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Tuple


logger = logging.getLogger(__name__)

_TRACE_LIMIT = 64
_lock = threading.Lock()
_stages: deque[str] = deque(maxlen=_TRACE_LIMIT)
_last_stage = "NOT_STARTED"


def reset_startup_trace() -> None:
    global _last_stage
    with _lock:
        _stages.clear()
        _last_stage = "NOT_STARTED"


def mark_startup_stage(stage: str) -> None:
    """Record and log one bounded lifecycle marker without arbitrary details."""
    global _last_stage
    normalized = str(stage or "UNKNOWN").strip().upper()[:96]
    with _lock:
        _last_stage = normalized
        _stages.append(normalized)
    logger.info("fastapi_startup stage=%s", normalized)


def get_last_startup_stage() -> str:
    with _lock:
        return _last_stage


def get_startup_stages() -> Tuple[str, ...]:
    with _lock:
        return tuple(_stages)
