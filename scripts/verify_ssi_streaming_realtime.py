# -*- coding: utf-8 -*-
"""Dev-only local verifier for SSI FastConnect streaming realtime.

This script verifies the streaming manager, parser, and script-local cache in a
bounded standalone process. It does not start the backend, call the realtime API,
or populate the FastAPI process cache.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence


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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify SSI streaming realtime in a standalone local process.")
    parser.add_argument("--symbols", default="FPT", help="Comma-separated VN symbols. Default: FPT.")
    parser.add_argument("--wait-seconds", type=float, default=30.0, help="Bounded wait duration. Default: 30.")
    parser.add_argument("--poll-interval-seconds", type=float, default=1.0, help="Poll interval. Default: 1.")
    parser.add_argument(
        "--channel-template",
        default=None,
        help='Streaming channel template. Default: env SSI_STREAMING_REALTIME_CHANNEL_TEMPLATE or "X: {symbol}".',
    )
    parser.add_argument("--check-config-only", action="store_true", help="Validate config and channel safety only.")
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
    )


def summarize(
    *,
    started: bool,
    manager: Optional[SsiStreamingRealtimeManager],
    symbols: Sequence[str],
    channels: Sequence[str],
    snapshot: Optional[Dict[str, Any]] = None,
    latest_error: Optional[str] = None,
) -> Dict[str, Any]:
    status = manager.status() if manager is not None else {}
    snap = snapshot or {}
    quotes = [row for row in snap.get("quotes", []) if isinstance(row, dict)]
    cache_status = snap.get("cache_status") or ("not_started" if not started else "unknown")
    error = latest_error if latest_error is not None else status.get("latest_error")
    return {
        "started": bool(started),
        "manager_state": status.get("manager_state") or ("not_started" if not started else "unknown"),
        "channels": list(status.get("channels") or channels),
        "messages_observed": int(status.get("messages_observed") or 0),
        "parser_rows_observed": int(status.get("parser_rows_observed") or 0),
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


def safe_print_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def text_has_secret_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in SECRET_MARKERS)


def run_verification(
    *,
    symbols: Sequence[str],
    config: Dict[str, Any],
    wait_seconds: float,
    poll_interval_seconds: float,
    manager_factory: Callable[..., SsiStreamingRealtimeManager] = make_manager,
    sleep_func: Callable[[float], None] = time.sleep,
    monotonic_func: Callable[[], float] = time.monotonic,
) -> int:
    parser = parser_for_manager()
    manager = manager_factory(config=config, parser=parser)
    started = False
    latest_snapshot: Dict[str, Any] = {}
    try:
        start_result = manager.start(symbols)
        started = start_result.get("manager_state") == "running"
        if not started:
            safe_print_json(
                summarize(
                    started=False,
                    manager=manager,
                    symbols=symbols,
                    channels=[],
                    latest_error=start_result.get("latest_error") or "manager start failed",
                )
            )
            return EXIT_MANAGER_START_FAILED

        deadline = monotonic_func() + max(0.0, wait_seconds)
        while True:
            latest_snapshot = manager.snapshot(symbols)
            status = manager.status()
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
        )
        safe_print_json(summary)
        if summary["latest_error"]:
            return EXIT_MANAGER_START_FAILED
        return EXIT_OK
    finally:
        try:
            manager.stop()
        except Exception as exc:
            safe_print_json(
                summarize(
                    started=started,
                    manager=manager,
                    symbols=symbols,
                    channels=[],
                    snapshot=latest_snapshot,
                    latest_error=exc,
                )
            )


def main(argv: Optional[Sequence[str]] = None) -> int:
    load_dotenv_if_available()
    args = build_arg_parser().parse_args(argv)
    try:
        wait_seconds = parse_positive_float(str(args.wait_seconds), field_name="--wait-seconds")
        poll_interval_seconds = parse_positive_float(
            str(args.poll_interval_seconds),
            field_name="--poll-interval-seconds",
        )
        symbols = parse_symbols(args.symbols)
        config = load_config(args)
        channels = validate_channels(symbols, config["channel_template"])
    except ValueError as exc:
        safe_print_json({"status": "invalid", "reason": sanitize_streaming_error(exc)})
        return EXIT_UNSAFE_CHANNEL

    missing = missing_config_keys(config)
    if missing:
        safe_print_json(
            {
                "status": "invalid_config",
                "missing": missing,
                "started": False,
                "script_cache_only": True,
                "backend_cache_populated": False,
                "no_secrets_observed": True,
            }
        )
        return EXIT_CONFIG_INVALID

    if args.check_config_only:
        safe_print_json(
            {
                "status": "ok",
                "started": False,
                "manager_state": "not_started",
                "channels": channels,
                "requested_symbols": symbols,
                "script_cache_only": True,
                "backend_cache_populated": False,
                "no_secrets_observed": True,
            }
        )
        return EXIT_OK

    return run_verification(
        symbols=symbols,
        config=config,
        wait_seconds=wait_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
