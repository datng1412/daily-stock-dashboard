# -*- coding: utf-8 -*-
"""Dev-only local verifier for SSI FastConnect streaming realtime.

This script verifies the streaming manager, parser, and script-local cache in a
bounded standalone process. It does not start the backend, call the realtime API,
or populate the FastAPI process cache.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import importlib
import importlib.metadata
import inspect
import io
import json
import os
import re
import sys
import time
import warnings
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_provider.ssi_fastconnect_fetcher import SsiFastConnectFetcher  # noqa: E402
from data_provider.ssi_streaming_realtime import (  # noqa: E402
    DEFAULT_STREAMING_REALTIME_CACHE_TTL_SECONDS,
    DEFAULT_STREAMING_REALTIME_CHANNEL_TEMPLATE,
    DEFAULT_STREAMING_REALTIME_STREAM_URL,
    OfficialSsiRealtimeStreamClient,
    RealtimeSnapshotCache,
    SsiStreamingRealtimeManager,
    build_symbol_channel,
    sanitize_streaming_error,
)


EXIT_OK = 0
EXIT_CONFIG_INVALID = 2
EXIT_UNSAFE_CHANNEL = 3
EXIT_MANAGER_START_FAILED = 4

SAFE_SYMBOL_RE = re.compile(r"^[A-Z0-9._-]+$")

CONSUMER_ID_KEYS = ("SSI_CONSUMER_ID", "SSI_FASTCONNECT_CONSUMER_ID", "SSI_FC_DATA_CONSUMER_ID")
CONSUMER_SECRET_KEYS = ("SSI_CONSUMER_SECRET", "SSI_FASTCONNECT_CONSUMER_SECRET", "SSI_FC_DATA_CONSUMER_SECRET")
BASE_URL_KEYS = ("SSI_FASTCONNECT_BASE_URL", "SSI_FC_DATA_BASE_URL", "SSI_BASE_URL")
STREAM_URL_KEYS = ("SSI_STREAMING_REALTIME_STREAM_URL", "SSI_FC_DATA_STREAM_URL")
AUTH_TYPE_KEYS = ("SSI_FASTCONNECT_AUTH_TYPE", "SSI_FC_DATA_AUTH_TYPE")
CHANNEL_TEMPLATE_KEYS = ("SSI_STREAMING_REALTIME_CHANNEL_TEMPLATE",)
TTL_KEYS = ("SSI_STREAMING_REALTIME_CACHE_TTL_SECONDS",)

SECRET_MARKERS = (
    "authorization",
    "bearer ",
    "access_token",
    "accesstoken",
    "consumerid",
    "consumersecret",
    "consumer_secret",
    "privatekey",
    "private_key",
)

MAX_SAMPLES = 5
MAX_EVENTS = 20

DIAGNOSIS_CACHE_HIT = "cache_hit"
DIAGNOSIS_MANAGER_START_FAILED = "manager_start_failed"
DIAGNOSIS_MANAGER_ERROR = "manager_error"
DIAGNOSIS_CALLBACK_NEVER_CALLED = "callback_never_called"
DIAGNOSIS_CALLBACK_PARSER_ZERO = "callback_called_parser_zero_rows"
DIAGNOSIS_ON_ERROR = "on_error_called"
DIAGNOSIS_NO_MESSAGE = "no_message_after_start"
DIAGNOSIS_CONFIG_INVALID = "config_invalid"
DIAGNOSIS_UNSAFE_CHANNEL = "unsafe_channel_rejected"
DIAGNOSIS_UNKNOWN = "unknown"
DIAGNOSIS_DIRECT_CALLBACK_HIT = "direct_callback_hit"
DIAGNOSIS_DIRECT_NO_MESSAGE = "direct_no_message_after_start"
DIAGNOSIS_DIRECT_ON_ERROR = "direct_on_error_called"
DIAGNOSIS_DIRECT_START_FAILED = "direct_start_failed"
DIAGNOSIS_PACKAGE_UNAVAILABLE = "package_unavailable"
DIAGNOSIS_UNSUPPORTED_CHANNEL_SHAPE = "unsupported_selected_channel_shape"

SELECTED_CHANNEL_SHAPES = ("string", "list", "comma")


def load_dotenv_if_available() -> None:
    """Load .env when python-dotenv is installed; keep it optional."""
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    try:
        load_dotenv()
    except Exception:
        return


def getenv_any(names: Sequence[str], *, default: Optional[str] = None) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def parse_positive_float(value: str, *, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number.") from exc
    if parsed < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return parsed


def parse_positive_int(value: Optional[str], *, default: int, field_name: str) -> int:
    try:
        parsed = int(value) if value not in (None, "") else int(default)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc
    if parsed < 1:
        raise ValueError(f"{field_name} must be at least 1.")
    return parsed


def parse_symbols(value: str) -> List[str]:
    symbols: List[str] = []
    seen = set()
    for item in (value or "").split(","):
        symbol = item.strip().upper()
        if not symbol:
            continue
        if symbol == "ALL":
            raise ValueError("Symbol ALL is not allowed.")
        if not SAFE_SYMBOL_RE.match(symbol):
            raise ValueError(f"Unsafe symbol rejected: {symbol!r}.")
        if symbol not in seen:
            symbols.append(symbol)
            seen.add(symbol)
    if not symbols:
        raise ValueError("At least one symbol is required.")
    return symbols


def validate_channels(symbols: Sequence[str], channel_template: str) -> List[str]:
    if "{symbol}" not in (channel_template or ""):
        raise ValueError("Channel template must include {symbol}.")
    channels = [build_symbol_channel(symbol, channel_template) for symbol in symbols]
    for channel in channels:
        if re.search(r":\s*ALL\b", channel, flags=re.IGNORECASE):
            raise ValueError("Channel template produced an ALL subscription.")
    return channels


def parse_channel_templates(value: Optional[str], fallback: str) -> List[str]:
    if not value:
        return [fallback]
    templates = [item.strip() for item in value.split(";") if item.strip()]
    if not templates:
        raise ValueError("At least one channel template is required.")
    return templates


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify SSI streaming realtime in a standalone local process.")
    parser.add_argument("--symbols", default="FPT", help="Comma-separated VN symbols. Default: FPT.")
    parser.add_argument("--wait-seconds", type=float, default=30.0, help="Bounded wait duration. Default: 30.")
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0, help="Poll interval. Default: 1.")
    parser.add_argument(
        "--channel-template",
        default=None,
        help='Streaming channel template. Default: env SSI_STREAMING_REALTIME_CHANNEL_TEMPLATE or "X:{symbol}".',
    )
    parser.add_argument(
        "--channel-templates",
        default=None,
        help='Semicolon-separated templates to test sequentially, for example "X: {symbol};X-QUOTE: {symbol}".',
    )
    parser.add_argument("--check-config-only", action="store_true", help="Validate config and channel safety only.")
    parser.add_argument("--check-package", action="store_true", help="Include lazy ssi_fc_data package availability in config-only output.")
    parser.add_argument("--verbose-safe", action="store_true", help="Include bounded sanitized diagnostic events in final JSON.")
    parser.add_argument("--inspect-package-source", action="store_true", help="Inspect installed ssi_fc_data package metadata without starting a stream.")
    parser.add_argument("--direct-official", action="store_true", help="Bypass manager/cache and call the official MarketDataStream.start directly.")
    parser.add_argument(
        "--channel-format-variants",
        action="store_true",
        help="Sequentially test safe symbol-scoped channel format variants for the first requested symbol.",
    )
    parser.add_argument(
        "--selected-channel-shape",
        choices=SELECTED_CHANNEL_SHAPES,
        default="string",
        help="Shape passed as selected_channel in direct official mode. Default: string.",
    )
    parser.add_argument(
        "--suppress-insecure-warning",
        action="store_true",
        help="Suppress only urllib3 InsecureRequestWarning emitted by the official client stack.",
    )
    return parser


def load_config(args: argparse.Namespace) -> Dict[str, Any]:
    channel_template = (
        args.channel_template
        or getenv_any(CHANNEL_TEMPLATE_KEYS)
        or DEFAULT_STREAMING_REALTIME_CHANNEL_TEMPLATE
    )
    return {
        "consumer_id": getenv_any(CONSUMER_ID_KEYS),
        "consumer_secret": getenv_any(CONSUMER_SECRET_KEYS),
        "base_url": getenv_any(BASE_URL_KEYS),
        "stream_url": getenv_any(STREAM_URL_KEYS, default=DEFAULT_STREAMING_REALTIME_STREAM_URL),
        "auth_type": getenv_any(AUTH_TYPE_KEYS, default="Bearer"),
        "channel_template": channel_template.strip() or DEFAULT_STREAMING_REALTIME_CHANNEL_TEMPLATE,
        "ttl_seconds": parse_positive_int(
            getenv_any(TTL_KEYS),
            default=DEFAULT_STREAMING_REALTIME_CACHE_TTL_SECONDS,
            field_name="SSI_STREAMING_REALTIME_CACHE_TTL_SECONDS",
        ),
    }


def stream_url_host(stream_url: str) -> Optional[str]:
    parsed = urlparse(stream_url or "")
    if parsed.hostname:
        return parsed.hostname
    return None


def trailing_slash(value: str) -> str:
    text = str(value or "").strip()
    return text.rstrip("/") + "/" if text else ""


def official_rest_root(base_url: str) -> str:
    text = str(base_url or "").strip().rstrip("/")
    suffix = "/api/v2/Market"
    if text.lower().endswith(suffix.lower()):
        text = text[: -len(suffix)]
    return trailing_slash(text)


def channel_format_variant_templates() -> List[str]:
    return [
        "X: {symbol}",
        "X:{symbol}",
        "X-QUOTE: {symbol}",
        "X-QUOTE:{symbol}",
        "X-TRADE: {symbol}",
        "X-TRADE:{symbol}",
    ]


def channel_format_warning(channels: Sequence[str]) -> Optional[str]:
    if any(re.match(r"^[A-Z-]+:\s+", str(channel or "").strip()) for channel in channels or []):
        return (
            "SSI streaming channels with a space after ':' were live-verified "
            "as non-working for callbacks; default format is X:{symbol}."
        )
    return None


def safe_repr_selected_channel(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(sanitize_streaming_error(item) for item in value[:MAX_SAMPLES]) + ("]" if len(value) <= MAX_SAMPLES else ", ...]")
    return sanitize_streaming_error(value)


def build_selected_channel(channels: Sequence[str], shape: str) -> Any:
    safe_channels = [str(channel or "").strip() for channel in channels if str(channel or "").strip()]
    if not safe_channels:
        raise ValueError("At least one selected channel is required.")
    if any(re.search(r":\s*ALL\b", channel, flags=re.IGNORECASE) for channel in safe_channels):
        raise ValueError("Selected channel produced an ALL subscription.")
    if shape == "string":
        if len(safe_channels) == 1:
            return safe_channels[0]
        return ",".join(safe_channels)
    if shape == "comma":
        return ",".join(safe_channels)
    if shape == "list":
        return list(safe_channels)
    raise ValueError(f"Unsupported selected channel shape: {shape}")


def inspect_package_source() -> Tuple[int, Dict[str, Any]]:
    try:
        package = importlib.import_module("ssi_fc_data")
        client_module = importlib.import_module("ssi_fc_data.fc_md_client")
        stream_module = importlib.import_module("ssi_fc_data.fc_md_stream")
    except Exception as exc:
        return EXIT_MANAGER_START_FAILED, {
            "status": "unavailable",
            "diagnosis": DIAGNOSIS_PACKAGE_UNAVAILABLE,
            "reason": sanitize_streaming_error(exc),
            "no_secrets_observed": True,
        }

    stream_class = getattr(stream_module, "MarketDataStream", None)
    client_class = getattr(client_module, "MarketDataClient", None)
    public_methods = []
    if stream_class is not None:
        public_methods = sorted(
            name
            for name, value in inspect.getmembers(stream_class)
            if not name.startswith("_") and callable(value)
        )
    version = None
    try:
        version = importlib.metadata.version("ssi-fc-data")
    except Exception:
        version = getattr(package, "__version__", None)
    payload = {
        "status": "ok",
        "mode": "inspect_package_source",
        "diagnosis": "package_available",
        "package": {
            "module": "ssi_fc_data",
            "file": sanitize_streaming_error(getattr(package, "__file__", None)),
            "version": sanitize_streaming_error(version) if version else None,
        },
        "fc_md_client": {
            "file": sanitize_streaming_error(getattr(client_module, "__file__", None)),
            "MarketDataClient_class": getattr(client_class, "__name__", None) if client_class is not None else None,
        },
        "fc_md_stream": {
            "file": sanitize_streaming_error(getattr(stream_module, "__file__", None)),
            "MarketDataStream_class": getattr(stream_class, "__name__", None) if stream_class is not None else None,
            "constructor_signature": sanitize_streaming_error(str(inspect.signature(stream_class))) if stream_class is not None else None,
            "start_signature": sanitize_streaming_error(str(inspect.signature(getattr(stream_class, "start")))) if stream_class is not None and hasattr(stream_class, "start") else None,
            "has_start": bool(stream_class is not None and hasattr(stream_class, "start")),
            "has_stop": bool(stream_class is not None and hasattr(stream_class, "stop")),
            "has_close": bool(stream_class is not None and hasattr(stream_class, "close")),
            "has_connection_attr_on_class": bool(stream_class is not None and hasattr(stream_class, "connection")),
            "public_methods": public_methods,
        },
        "source_snippets_included": False,
        "no_secrets_observed": True,
    }
    return EXIT_OK, payload


def missing_config_keys(config: Dict[str, Any]) -> List[str]:
    missing = []
    if not config.get("consumer_id"):
        missing.append("consumer_id")
    if not config.get("consumer_secret"):
        missing.append("consumer_secret")
    if not config.get("base_url"):
        missing.append("base_url")
    if not config.get("stream_url"):
        missing.append("stream_url")
    return missing


def parser_for_manager() -> Callable[[List[Any], List[str]], List[Dict[str, Any]]]:
    parser_owner = object.__new__(SsiFastConnectFetcher)
    return parser_owner.normalize_streaming_realtime_messages


def safe_sample_list(values: Iterable[Any], *, max_items: int = MAX_SAMPLES) -> List[str]:
    result: List[str] = []
    for value in values or []:
        text = sanitize_streaming_error(value)
        if text not in result:
            result.append(text)
        if len(result) >= max_items:
            break
    return result


def parse_content_for_sampling(content: Any) -> Any:
    if isinstance(content, str):
        text = content.strip()
        if not text:
            return content
        try:
            parsed = json.loads(text)
        except Exception:
            return content
        return parsed
    return content


def first_value(mapping: Dict[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in mapping:
            return mapping.get(key)
    lower_map = {str(key).lower(): value for key, value in mapping.items()}
    for key in keys:
        lowered = key.lower()
        if lowered in lower_map:
            return lower_map[lowered]
    return None


def sample_message_envelope(message: Any) -> Dict[str, Any]:
    sample: Dict[str, Any] = {
        "payload_type": type(message).__name__,
    }
    if isinstance(message, dict):
        keys = [str(key) for key in message.keys()]
        sample["top_level_keys"] = safe_sample_list(keys)
        data_type = first_value(message, ("DataType", "dataType", "datatype"))
        if data_type is not None:
            sample["data_type"] = sanitize_streaming_error(data_type)
        content = first_value(message, ("Content", "content"))
        sample["has_content"] = content is not None
        sample["content_type"] = type(content).__name__ if content is not None else None
        if isinstance(content, str):
            sample["content_length"] = len(content)
        parsed_content = parse_content_for_sampling(content)
        if isinstance(parsed_content, dict):
            content_keys = [str(key) for key in parsed_content.keys()]
            sample["content_keys"] = safe_sample_list(content_keys)
            rtype = first_value(parsed_content, ("RType", "rtype"))
            if rtype is not None:
                sample["rtype"] = sanitize_streaming_error(rtype)
            symbol = first_value(parsed_content, ("Symbol", "Ticker", "StockCode", "SecurityCode", "Code"))
            if symbol is not None:
                symbol_text = str(symbol).strip().upper()
                if SAFE_SYMBOL_RE.match(symbol_text):
                    sample["symbol"] = symbol_text
        elif isinstance(parsed_content, list):
            sample["content_length"] = len(parsed_content)
    elif isinstance(message, str):
        sample["payload_length"] = len(message)
    return sample


class VerificationDiagnostics:
    def __init__(self, *, verbose_safe: bool = False, max_samples: int = MAX_SAMPLES, max_events: int = MAX_EVENTS) -> None:
        self.verbose_safe = bool(verbose_safe)
        self.max_samples = max_samples
        self.max_events = max_events
        self.callback_invoked_count = 0
        self.on_message_count = 0
        self.on_error_count = 0
        self.parser_attempt_count = 0
        self.parser_rows_total = 0
        self.parser_zero_row_count = 0
        self.parser_exception_count = 0
        self.first_message_at: Optional[float] = None
        self.last_message_at: Optional[float] = None
        self.first_error_at: Optional[float] = None
        self.last_error_at: Optional[float] = None
        self.message_envelope_key_samples: List[List[str]] = []
        self.message_type_samples: List[str] = []
        self.content_key_samples: List[List[str]] = []
        self.message_samples: List[Dict[str, Any]] = []
        self.manager_status_samples: List[Dict[str, Any]] = []
        self.diagnostic_events: List[Dict[str, Any]] = []

    def _add_unique(self, items: List[Any], value: Any) -> None:
        if value not in items and len(items) < self.max_samples:
            items.append(value)

    def _event(self, event_type: str, **payload: Any) -> None:
        if not self.verbose_safe or len(self.diagnostic_events) >= self.max_events:
            return
        event = {"event": event_type}
        event.update({key: sanitize_for_json(value) for key, value in payload.items()})
        self.diagnostic_events.append(event)

    def record_message(self, message: Any) -> None:
        now = time.time()
        self.callback_invoked_count += 1
        self.on_message_count += 1
        self.first_message_at = self.first_message_at or now
        self.last_message_at = now
        sample = sample_message_envelope(message)
        if isinstance(sample.get("top_level_keys"), list):
            self._add_unique(self.message_envelope_key_samples, sample["top_level_keys"])
        if sample.get("data_type"):
            self._add_unique(self.message_type_samples, sample["data_type"])
        if sample.get("rtype"):
            self._add_unique(self.message_type_samples, sample["rtype"])
        if isinstance(sample.get("content_keys"), list):
            self._add_unique(self.content_key_samples, sample["content_keys"])
        if len(self.message_samples) < self.max_samples:
            self.message_samples.append(sample)
        self._event("on_message", sample=sample)

    def record_error(self, error: Any) -> None:
        now = time.time()
        self.callback_invoked_count += 1
        self.on_error_count += 1
        self.first_error_at = self.first_error_at or now
        self.last_error_at = now
        self._event("on_error", error=sanitize_streaming_error(error))

    def parser_wrapper(
        self,
        parser: Callable[[List[Any], List[str]], List[Dict[str, Any]]],
    ) -> Callable[[List[Any], List[str]], List[Dict[str, Any]]]:
        @wraps(parser)
        def wrapped(messages: List[Any], symbols: List[str]) -> List[Dict[str, Any]]:
            self.parser_attempt_count += 1
            try:
                rows = parser(messages, symbols)
            except Exception as exc:
                self.parser_exception_count += 1
                self._event("parser_exception", error=sanitize_streaming_error(exc))
                raise
            row_count = len(rows or [])
            self.parser_rows_total += row_count
            if row_count == 0:
                self.parser_zero_row_count += 1
            self._event("parser_result", row_count=row_count)
            return rows

        return wrapped

    def sample_manager_status(self, status: Dict[str, Any]) -> None:
        safe_status = {
            "manager_state": status.get("manager_state"),
            "runtime_status": status.get("runtime_status"),
            "channels": status.get("channels") or [],
            "messages_observed": int(status.get("messages_observed") or 0),
            "parser_rows_observed": int(status.get("parser_rows_observed") or 0),
            "is_idle": bool(status.get("is_idle")),
            "reconnect_attempt_count": int(status.get("reconnect_attempt_count") or 0),
            "latest_error": sanitize_streaming_error(status.get("latest_error")) if status.get("latest_error") else None,
        }
        if len(self.manager_status_samples) < self.max_samples:
            self.manager_status_samples.append(safe_status)
        self._event("manager_status", status=safe_status)

    def as_summary(self) -> Dict[str, Any]:
        result = {
            "callback_invoked_count": self.callback_invoked_count,
            "on_message_count": self.on_message_count,
            "on_error_count": self.on_error_count,
            "parser_attempt_count": self.parser_attempt_count,
            "parser_rows_total": self.parser_rows_total,
            "first_message_at": _iso_from_epoch(self.first_message_at),
            "last_message_at": _iso_from_epoch(self.last_message_at),
            "first_error_at": _iso_from_epoch(self.first_error_at),
            "last_error_at": _iso_from_epoch(self.last_error_at),
            "message_envelope_key_samples": self.message_envelope_key_samples,
            "message_type_samples": self.message_type_samples,
            "content_key_samples": self.content_key_samples,
            "parser_zero_row_count": self.parser_zero_row_count,
            "parser_exception_count": self.parser_exception_count,
            "manager_status_samples": self.manager_status_samples,
            "client_state_inspection": "skipped",
        }
        if self.verbose_safe:
            result["diagnostic_events"] = self.diagnostic_events
            result["message_samples"] = self.message_samples
        return result


def _iso_from_epoch(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(value))


def sanitize_for_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {sanitize_streaming_error(key): sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_for_json(item) for item in value[:MAX_SAMPLES]]
    if isinstance(value, tuple):
        return [sanitize_for_json(item) for item in list(value)[:MAX_SAMPLES]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return sanitize_streaming_error(value) if isinstance(value, str) else value
    return sanitize_streaming_error(type(value).__name__)


def make_manager(
    *,
    config: Dict[str, Any],
    parser: Callable[[List[Any], List[str]], List[Dict[str, Any]]],
) -> SsiStreamingRealtimeManager:
    return SsiStreamingRealtimeManager(
        enabled=True,
        cache=RealtimeSnapshotCache(ttl_seconds=int(config["ttl_seconds"])),
        parser=parser,
        client_factory=lambda: OfficialSsiRealtimeStreamClient(
            consumer_id=config.get("consumer_id"),
            consumer_secret=config.get("consumer_secret"),
            base_url=config.get("base_url") or "",
            stream_url=config.get("stream_url") or DEFAULT_STREAMING_REALTIME_STREAM_URL,
            auth_type=config.get("auth_type") or "Bearer",
        ),
        channel_template=config["channel_template"],
        order_book_enabled=False,
        foreign_room_enabled=False,
        market_index_enabled=False,
        trade_tape_enabled=False,
        session_status_enabled=False,
    )


def inspect_client_state(manager: Optional[SsiStreamingRealtimeManager]) -> Any:
    if manager is None:
        return "skipped"
    try:
        client = getattr(manager, "_client", None)
        if client is None:
            return {"available": False, "reason": "manager_client_not_set"}
        streams = getattr(client, "_streams", None)
        stream_items = list(streams) if isinstance(streams, list) else []
        inspected_streams = []
        for stream in stream_items[:MAX_SAMPLES]:
            connection = getattr(stream, "connection", None)
            transport = getattr(connection, "_Connection__transport", None) if connection is not None else None
            inspected_streams.append(
                {
                    "stream_class": type(stream).__name__,
                    "has_connection": connection is not None,
                    "connection_class": type(connection).__name__ if connection is not None else None,
                    "has_transport": transport is not None,
                    "transport_class": type(transport).__name__ if transport is not None else None,
                    "transport_has_stop": bool(transport is not None and callable(getattr(transport, "stop", None))),
                }
            )
        return {
            "available": True,
            "client_class": type(client).__name__,
            "stream_count": len(stream_items),
            "streams": inspected_streams,
        }
    except Exception as exc:
        return {"available": False, "reason": sanitize_streaming_error(exc)}


def classify_diagnosis(
    *,
    started: bool,
    summary: Dict[str, Any],
    diagnostics: VerificationDiagnostics,
) -> str:
    if summary.get("quote_count", 0) > 0 or summary.get("cache_status") == "hit":
        return DIAGNOSIS_CACHE_HIT
    if not started:
        return DIAGNOSIS_MANAGER_START_FAILED
    if diagnostics.on_error_count > 0:
        return DIAGNOSIS_ON_ERROR
    if summary.get("manager_state") == "errored":
        return DIAGNOSIS_MANAGER_ERROR
    if diagnostics.callback_invoked_count == 0:
        if summary.get("manager_state") == "running" and not summary.get("latest_error"):
            return DIAGNOSIS_NO_MESSAGE
        return DIAGNOSIS_CALLBACK_NEVER_CALLED
    if diagnostics.parser_rows_total == 0:
        return DIAGNOSIS_CALLBACK_PARSER_ZERO
    return DIAGNOSIS_UNKNOWN


def summarize(
    *,
    started: bool,
    manager: Optional[SsiStreamingRealtimeManager],
    symbols: Sequence[str],
    channels: Sequence[str],
    snapshot: Optional[Dict[str, Any]] = None,
    latest_error: Optional[str] = None,
    diagnostics: Optional[VerificationDiagnostics] = None,
    client_state_inspection: Any = "skipped",
) -> Dict[str, Any]:
    status = manager.status() if manager is not None else {}
    snap = snapshot or {}
    quotes = [row for row in snap.get("quotes", []) if isinstance(row, dict)]
    cache_status = snap.get("cache_status") or ("not_started" if not started else "unknown")
    error = latest_error if latest_error is not None else status.get("latest_error")
    result = {
        "started": bool(started),
        "manager_state": status.get("manager_state") or ("not_started" if not started else "unknown"),
        "runtime_status": status.get("runtime_status"),
        "channels": list(status.get("channels") or channels),
        "messages_observed": int(status.get("messages_observed") or 0),
        "parser_rows_observed": int(status.get("parser_rows_observed") or 0),
        "is_idle": bool(status.get("is_idle")),
        "idle_since": status.get("idle_since"),
        "reconnect_enabled": bool(status.get("reconnect_enabled")),
        "reconnect_attempt_count": int(status.get("reconnect_attempt_count") or 0),
        "next_reconnect_at": status.get("next_reconnect_at"),
        "reconnect_backoff_seconds": status.get("reconnect_backoff_seconds"),
        "last_reconnect_reason": status.get("last_reconnect_reason"),
        "cache_status": cache_status,
        "quote_count": len(quotes),
        "symbols_with_quotes": sorted(
            {
                str(row.get("ticker") or row.get("symbol") or "").strip().upper()
                for row in quotes
                if str(row.get("ticker") or row.get("symbol") or "").strip()
            }
        ),
        "latest_error": sanitize_streaming_error(error) if error else None,
        "no_secrets_observed": True,
        "script_cache_only": True,
        "backend_cache_populated": False,
        "requested_symbols": list(symbols),
    }
    if diagnostics is not None:
        diagnostic_summary = diagnostics.as_summary()
        diagnostic_summary["client_state_inspection"] = client_state_inspection
        result.update(diagnostic_summary)
        result["diagnosis"] = classify_diagnosis(started=started, summary=result, diagnostics=diagnostics)
    else:
        result["diagnosis"] = DIAGNOSIS_UNKNOWN
    return result


def safe_print_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def text_has_secret_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in SECRET_MARKERS)


def package_available() -> bool:
    return importlib.util.find_spec("ssi_fc_data") is not None


def config_only_summary(
    *,
    symbols: Sequence[str],
    channels: Sequence[str],
    config: Dict[str, Any],
    check_package: bool,
) -> Dict[str, Any]:
    completeness = {
        "consumer_id_present": bool(config.get("consumer_id")),
        "consumer_secret_present": bool(config.get("consumer_secret")),
        "base_url_present": bool(config.get("base_url")),
        "stream_url_present": bool(config.get("stream_url")),
    }
    payload: Dict[str, Any] = {
        "status": "ok",
        "diagnosis": DIAGNOSIS_UNKNOWN,
        "started": False,
        "manager_state": "not_started",
        "channels": list(channels),
        "requested_symbols": list(symbols),
        "stream_url_host": stream_url_host(config.get("stream_url") or ""),
        "config_complete": all(completeness.values()),
        "config": completeness,
        "script_cache_only": True,
        "backend_cache_populated": False,
        "no_secrets_observed": True,
    }
    warning = channel_format_warning(channels)
    if warning:
        payload["channel_format_warning"] = warning
    if check_package:
        payload["package_available"] = package_available()
    return payload


def suppress_insecure_warning_if_requested(enabled: bool) -> None:
    if not enabled:
        return
    try:
        from urllib3.exceptions import InsecureRequestWarning
    except Exception:
        return
    warnings.filterwarnings("ignore", category=InsecureRequestWarning)


def run_verification(
    *,
    symbols: Sequence[str],
    config: Dict[str, Any],
    wait_seconds: float,
    poll_interval_seconds: float,
    manager_factory: Callable[..., SsiStreamingRealtimeManager] = make_manager,
    sleep_func: Callable[[float], None] = time.sleep,
    monotonic_func: Callable[[], float] = time.monotonic,
) -> Tuple[int, Dict[str, Any]]:
    parser = parser_for_manager()
    diagnostics = VerificationDiagnostics(verbose_safe=bool(config.get("verbose_safe")))
    manager = manager_factory(config=config, parser=diagnostics.parser_wrapper(parser))
    started = False
    latest_snapshot: Dict[str, Any] = {}
    original_handle_message = manager.handle_message
    original_handle_error = manager.handle_error

    def instrumented_message(message: Any, *args: Any, **kwargs: Any) -> None:
        diagnostics.record_message(message)
        original_handle_message(message, *args, **kwargs)

    def instrumented_error(error: Any, *args: Any, **kwargs: Any) -> None:
        diagnostics.record_error(error)
        original_handle_error(error, *args, **kwargs)

    manager.handle_message = instrumented_message  # type: ignore[method-assign]
    manager.handle_error = instrumented_error  # type: ignore[method-assign]
    try:
        start_result = manager.start(symbols)
        started = start_result.get("manager_state") == "running"
        if not started:
            summary = summarize(
                started=False,
                manager=manager,
                symbols=symbols,
                channels=[],
                latest_error=start_result.get("latest_error") or "manager start failed",
                diagnostics=diagnostics,
                client_state_inspection=inspect_client_state(manager),
            )
            summary["diagnosis"] = DIAGNOSIS_MANAGER_START_FAILED
            return EXIT_MANAGER_START_FAILED, summary

        deadline = monotonic_func() + max(0.0, wait_seconds)
        while True:
            latest_snapshot = manager.snapshot(symbols)
            status = manager.status()
            diagnostics.sample_manager_status(status)
            if latest_snapshot.get("quotes") or status.get("manager_state") == "errored" or status.get("latest_error"):
                break
            if monotonic_func() >= deadline:
                break
            sleep_func(max(0.0, min(poll_interval_seconds, deadline - monotonic_func())))

        summary = summarize(
            started=True,
            manager=manager,
            symbols=symbols,
            channels=[],
            snapshot=latest_snapshot,
            diagnostics=diagnostics,
            client_state_inspection=inspect_client_state(manager),
        )
        if summary["latest_error"]:
            return EXIT_MANAGER_START_FAILED, summary
        return EXIT_OK, summary
    finally:
        try:
            manager.stop()
        except Exception as exc:
            summary = summarize(
                started=started,
                manager=manager,
                symbols=symbols,
                channels=[],
                snapshot=latest_snapshot,
                latest_error=exc,
                diagnostics=diagnostics,
                client_state_inspection=inspect_client_state(manager),
            )
            safe_print_json(summary)


def run_and_print_verification(**kwargs: Any) -> int:
    code, summary = run_verification(**kwargs)
    safe_print_json(summary)
    return code


def direct_diagnosis(*, started: bool, direct_on_message_count: int, direct_on_error_count: int, latest_error: Optional[str]) -> str:
    if direct_on_message_count > 0:
        return DIAGNOSIS_DIRECT_CALLBACK_HIT
    if direct_on_error_count > 0:
        return DIAGNOSIS_DIRECT_ON_ERROR
    if latest_error:
        return DIAGNOSIS_DIRECT_START_FAILED if not started else DIAGNOSIS_DIRECT_ON_ERROR
    if started:
        return DIAGNOSIS_DIRECT_NO_MESSAGE
    return DIAGNOSIS_UNKNOWN


def make_official_config(config: Dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        auth_type=config.get("auth_type") or "Bearer",
        consumerID=config.get("consumer_id") or "",
        consumerSecret=config.get("consumer_secret") or "",
        url=official_rest_root(config.get("base_url") or ""),
        stream_url=trailing_slash(config.get("stream_url") or DEFAULT_STREAMING_REALTIME_STREAM_URL),
    )


def stop_official_stream(stream: Any) -> None:
    if stream is None:
        return
    try:
        OfficialSsiRealtimeStreamClient._stop_stream(stream)
    except Exception:
        return


def captured_output_flags(stdout_text: str, stderr_text: str) -> Dict[str, Any]:
    return {
        "stdout_capture_enabled": True,
        "stderr_capture_enabled": True,
        "stdout_captured": bool(stdout_text),
        "stderr_captured": bool(stderr_text),
        "captured_output_secret_like_detected": text_has_secret_marker(stdout_text) or text_has_secret_marker(stderr_text),
        "raw_stdout_printed": False,
        "raw_stderr_printed": False,
    }


def run_direct_official(
    *,
    symbols: Sequence[str],
    config: Dict[str, Any],
    channels: Sequence[str],
    wait_seconds: float,
    poll_interval_seconds: float,
    selected_channel_shape: str,
    sleep_func: Callable[[float], None] = time.sleep,
    monotonic_func: Callable[[], float] = time.monotonic,
    import_module: Callable[[str], Any] = importlib.import_module,
) -> Tuple[int, Dict[str, Any]]:
    diagnostics = VerificationDiagnostics(verbose_safe=bool(config.get("verbose_safe")))
    selected_channel = None
    stream = None
    started = False
    latest_error: Optional[str] = None
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    direct_first_message_at: Optional[float] = None
    direct_last_message_at: Optional[float] = None
    direct_first_error_at: Optional[float] = None
    direct_last_error_at: Optional[float] = None

    try:
        selected_channel = build_selected_channel(channels, selected_channel_shape)
    except ValueError as exc:
        summary = {
            "mode": "direct_official",
            "status": "invalid",
            "diagnosis": DIAGNOSIS_UNSUPPORTED_CHANNEL_SHAPE,
            "reason": sanitize_streaming_error(exc),
            "no_secrets_observed": True,
            "script_cache_only": True,
            "backend_cache_populated": False,
        }
        return EXIT_UNSAFE_CHANNEL, summary

    def on_message(message: Any) -> None:
        nonlocal direct_first_message_at, direct_last_message_at
        now = time.time()
        direct_first_message_at = direct_first_message_at or now
        direct_last_message_at = now
        diagnostics.record_message(message)

    def on_error(error: Any) -> None:
        nonlocal direct_first_error_at, direct_last_error_at, latest_error
        now = time.time()
        direct_first_error_at = direct_first_error_at or now
        direct_last_error_at = now
        latest_error = sanitize_streaming_error(error)
        diagnostics.record_error(error)

    try:
        with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
            client_module = import_module("ssi_fc_data.fc_md_client")
            stream_module = import_module("ssi_fc_data.fc_md_stream")
            official_config = make_official_config(config)
            client = client_module.MarketDataClient(official_config)
            stream = stream_module.MarketDataStream(official_config, client)
            stream.start(on_message, on_error, selected_channel)
            started = True
    except ImportError as exc:
        latest_error = sanitize_streaming_error(exc)
        output_flags = captured_output_flags(stdout_buffer.getvalue(), stderr_buffer.getvalue())
        return EXIT_MANAGER_START_FAILED, {
            "mode": "direct_official",
            "status": "unavailable",
            "diagnosis": DIAGNOSIS_PACKAGE_UNAVAILABLE,
            "latest_error": latest_error,
            **output_flags,
            "no_secrets_observed": not output_flags["captured_output_secret_like_detected"],
            "script_cache_only": True,
            "backend_cache_populated": False,
        }
    except Exception as exc:
        latest_error = sanitize_streaming_error(exc)
    try:
        if started:
            deadline = monotonic_func() + max(0.0, wait_seconds)
            while True:
                if diagnostics.on_message_count > 0 or diagnostics.on_error_count > 0:
                    break
                if monotonic_func() >= deadline:
                    break
                sleep_func(max(0.0, min(poll_interval_seconds, deadline - monotonic_func())))
    finally:
        stop_official_stream(stream)

    stdout_text = stdout_buffer.getvalue()
    stderr_text = stderr_buffer.getvalue()
    output_flags = captured_output_flags(stdout_text, stderr_text)
    client_state = {
        "available": stream is not None,
        "stream_class": type(stream).__name__ if stream is not None else None,
        "has_connection": bool(stream is not None and getattr(stream, "connection", None) is not None),
    }
    if stream is not None and getattr(stream, "connection", None) is not None:
        connection = getattr(stream, "connection")
        transport = getattr(connection, "_Connection__transport", None)
        client_state.update(
            {
                "connection_class": type(connection).__name__,
                "has_transport": transport is not None,
                "transport_class": type(transport).__name__ if transport is not None else None,
                "transport_has_stop": bool(transport is not None and callable(getattr(transport, "stop", None))),
            }
        )
    summary = {
        "mode": "direct_official",
        "status": "ok" if started and not latest_error else "unavailable",
        "diagnosis": direct_diagnosis(
            started=started,
            direct_on_message_count=diagnostics.on_message_count,
            direct_on_error_count=diagnostics.on_error_count,
            latest_error=latest_error,
        ),
        "started": started,
        "manager_mode_available": True,
        "direct_official_mode_available": True,
        "call_pattern": "direct_official_start",
        "channels": list(channels),
        "selected_channel_argument_type": type(selected_channel).__name__,
        "selected_channel_argument_repr_safe": safe_repr_selected_channel(selected_channel),
        "callback_bound": True,
        "direct_on_message_count": diagnostics.on_message_count,
        "direct_on_error_count": diagnostics.on_error_count,
        "direct_first_message_at": _iso_from_epoch(direct_first_message_at),
        "direct_last_message_at": _iso_from_epoch(direct_last_message_at),
        "direct_first_error_at": _iso_from_epoch(direct_first_error_at),
        "direct_last_error_at": _iso_from_epoch(direct_last_error_at),
        "message_envelope_key_samples": diagnostics.message_envelope_key_samples,
        "message_type_samples": diagnostics.message_type_samples,
        "content_key_samples": diagnostics.content_key_samples,
        "client_state_inspection": client_state,
        "latest_error": latest_error,
        "script_cache_only": True,
        "backend_cache_populated": False,
        **output_flags,
    }
    if diagnostics.verbose_safe:
        summary["diagnostic_events"] = diagnostics.diagnostic_events
        summary["message_samples"] = diagnostics.message_samples
    summary["no_secrets_observed"] = not output_flags["captured_output_secret_like_detected"]
    return (EXIT_OK if not latest_error else EXIT_MANAGER_START_FAILED), summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    load_dotenv_if_available()
    args = build_arg_parser().parse_args(argv)
    suppress_insecure_warning_if_requested(args.suppress_insecure_warning)
    if args.inspect_package_source:
        code, payload = inspect_package_source()
        safe_print_json(payload)
        return code
    try:
        wait_seconds = parse_positive_float(str(args.wait_seconds), field_name="--wait-seconds")
        poll_interval_seconds = parse_positive_float(
            str(args.poll_interval_seconds),
            field_name="--poll-interval-seconds",
        )
        symbols = parse_symbols(args.symbols)
        config = load_config(args)
        if args.channel_format_variants:
            symbols = symbols[:1]
            templates = channel_format_variant_templates()
        else:
            templates = parse_channel_templates(args.channel_templates, config["channel_template"])
        planned_results = []
        for template in templates:
            template_config = dict(config)
            template_config["channel_template"] = template
            channels = validate_channels(symbols, template)
            planned_results.append((template, template_config, channels))
    except ValueError as exc:
        safe_print_json({"status": "invalid", "diagnosis": DIAGNOSIS_UNSAFE_CHANNEL, "reason": sanitize_streaming_error(exc)})
        return EXIT_UNSAFE_CHANNEL

    missing = missing_config_keys(config)
    if missing:
        safe_print_json(
            {
                "status": "invalid_config",
                "diagnosis": DIAGNOSIS_CONFIG_INVALID,
                "missing": missing,
                "started": False,
                "script_cache_only": True,
                "backend_cache_populated": False,
                "no_secrets_observed": True,
            }
        )
        return EXIT_CONFIG_INVALID

    if args.check_config_only:
        summaries = [
            {
                "channel_template": template,
                "direct_official_mode_available": bool(args.direct_official),
                "selected_channel_shape": args.selected_channel_shape if args.direct_official else None,
                **config_only_summary(
                    symbols=symbols,
                    channels=channels,
                    config=template_config,
                    check_package=bool(args.check_package),
                ),
            }
            for template, template_config, channels in planned_results
        ]
        if args.channel_templates or args.channel_format_variants:
            best_result = None
            safe_print_json(
                {
                    "mode": "direct_official_channel_discovery" if args.direct_official else "channel_discovery",
                    "status": "ok",
                    "diagnosis": DIAGNOSIS_UNKNOWN,
                    "results": summaries,
                    "best_result": best_result,
                    "script_cache_only": True,
                    "backend_cache_populated": False,
                    "no_secrets_observed": True,
                }
            )
            return EXIT_OK
        safe_print_json(summaries[0])
        return EXIT_OK

    if args.direct_official:
        results = []
        best_result = None
        exit_code = EXIT_OK
        for template, template_config, channels in planned_results:
            template_config = dict(template_config)
            template_config["verbose_safe"] = bool(args.verbose_safe)
            code, summary = run_direct_official(
                symbols=symbols,
                config=template_config,
                channels=channels,
                wait_seconds=wait_seconds,
                poll_interval_seconds=poll_interval_seconds,
                selected_channel_shape=args.selected_channel_shape,
            )
            result = {"channel_template": template, **summary}
            results.append(result)
            if best_result is None and result.get("diagnosis") in {
                DIAGNOSIS_DIRECT_CALLBACK_HIT,
                DIAGNOSIS_DIRECT_ON_ERROR,
            }:
                best_result = result
            if code != EXIT_OK and exit_code == EXIT_OK:
                exit_code = code
            if not (args.channel_templates or args.channel_format_variants):
                safe_print_json(result)
                return code
        safe_print_json(
            {
                "mode": "direct_official_channel_discovery",
                "status": "ok" if exit_code == EXIT_OK else "partial",
                "diagnosis": best_result.get("diagnosis") if isinstance(best_result, dict) else DIAGNOSIS_UNKNOWN,
                "results": results,
                "best_result": best_result,
                "script_cache_only": True,
                "backend_cache_populated": False,
                "no_secrets_observed": all(bool(result.get("no_secrets_observed")) for result in results),
            }
        )
        return exit_code

    if args.channel_templates or args.channel_format_variants:
        results = []
        best_result = None
        exit_code = EXIT_OK
        for template, template_config, _channels in planned_results:
            template_config = dict(template_config)
            template_config["verbose_safe"] = bool(args.verbose_safe)
            code, summary = run_verification(
                symbols=symbols,
                config=template_config,
                wait_seconds=wait_seconds,
                poll_interval_seconds=poll_interval_seconds,
            )
            result = {"channel_template": template, **summary}
            results.append(result)
            if best_result is None and (
                result.get("diagnosis") == DIAGNOSIS_CACHE_HIT
                or int(result.get("callback_invoked_count") or 0) > 0
            ):
                best_result = result
            if code != EXIT_OK and exit_code == EXIT_OK:
                exit_code = code
        safe_print_json(
            {
                "mode": "channel_discovery",
                "status": "ok" if exit_code == EXIT_OK else "partial",
                "diagnosis": best_result.get("diagnosis") if isinstance(best_result, dict) else DIAGNOSIS_UNKNOWN,
                "results": results,
                "best_result": best_result,
                "script_cache_only": True,
                "backend_cache_populated": False,
                "no_secrets_observed": True,
            }
        )
        return exit_code

    config = dict(config)
    config["verbose_safe"] = bool(args.verbose_safe)
    return run_and_print_verification(
        symbols=symbols,
        config=config,
        wait_seconds=wait_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
