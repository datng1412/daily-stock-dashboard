#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone FiinQuantX realtime quote probe.

This script is intentionally not integrated with the application. It reads
credentials from environment variables, starts a short realtime stream probe,
and prints compact callback rows for manual validation.
"""

from __future__ import annotations

import csv
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


FIELDS_TO_PRINT = (
    "Ticker",
    "TradingDate",
    "Reference",
    "Open",
    "Close",
    "High",
    "Low",
    "Change",
    "ChangePercent",
    "MatchVolume",
    "MatchValue",
    "TotalMatchVolume",
    "TotalMatchValue",
    "ForeignBuyVolumeTotal",
    "ForeignSellVolumeTotal",
    "ForeignBuyValueTotal",
    "ForeignSellValueTotal",
)
TIMESTAMP_CANDIDATES = (
    "TradingDate",
    "TradingTime",
    "Time",
    "DateTime",
    "Timestamp",
    "LastUpdate",
)


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _parse_tickers() -> list[str]:
    raw = _env("FIINQUANT_TICKERS") or "FPT,HPG,VNINDEX"
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def _parse_runtime_seconds() -> int:
    raw = _env("FIINQUANT_PROBE_SECONDS") or "60"
    try:
        value = int(raw)
    except ValueError:
        raise SystemExit("FIINQUANT_PROBE_SECONDS must be an integer.")
    if value <= 0:
        raise SystemExit("FIINQUANT_PROBE_SECONDS must be greater than 0.")
    return value


def _validate_env() -> tuple[str, str, list[str], int, str]:
    username = _env("FIINQUANT_USERNAME")
    password = _env("FIINQUANT_PASSWORD")
    missing = [name for name, value in (("FIINQUANT_USERNAME", username), ("FIINQUANT_PASSWORD", password)) if not value]
    if missing:
        raise SystemExit(f"Missing required environment variable(s): {', '.join(missing)}")
    tickers = _parse_tickers()
    if not tickers:
        raise SystemExit("FIINQUANT_TICKERS produced an empty ticker list.")
    csv_path = _env("FIINQUANT_PROBE_CSV")
    return username, password, tickers, _parse_runtime_seconds(), csv_path


def _load_fiin_session() -> Any:
    install_hint = (
        "Install it with: "
        "pip install --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx"
    )
    last_error: Optional[ImportError] = None
    for module_name in ("fiinquantx", "FiinQuantX"):
        try:
            module = __import__(module_name, fromlist=["FiinSession"])
            return getattr(module, "FiinSession")
        except ModuleNotFoundError as exc:
            if exc.name not in {module_name, "fiinquantx", "FiinQuantX"}:
                raise SystemExit(
                    f"Unable to import FiinQuantX because dependency '{exc.name}' is missing. "
                    f"Install the missing dependency in this venv, then rerun the probe."
                ) from exc
            last_error = exc
        except ImportError as exc:
            last_error = exc
    raise SystemExit(f"Unable to import FiinQuantX. {install_hint}") from last_error
    return FiinSession


def _to_dataframe(payload: Any) -> Any:
    if hasattr(payload, "to_dataFrame"):
        return payload.to_dataFrame()
    if hasattr(payload, "to_dataframe"):
        return payload.to_dataframe()
    return None


def _iter_records(payload: Any) -> tuple[list[str], list[dict[str, Any]]]:
    df = _to_dataframe(payload)
    if df is not None:
        columns = [str(column) for column in getattr(df, "columns", [])]
        if hasattr(df, "to_dict"):
            return columns, list(df.to_dict("records"))
    if isinstance(payload, dict):
        return list(payload.keys()), [payload]
    return [], [{"payload_type": type(payload).__name__}]


def _first_present(row: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _compact_row(row: dict[str, Any]) -> dict[str, Any]:
    compact = {field: row.get(field) for field in FIELDS_TO_PRINT if field in row}
    if not compact:
        compact = {"payload_type": row.get("payload_type", "unknown")}
    return compact


def _print_row(row: dict[str, Any], latest_timestamp: Any) -> None:
    compact = _compact_row(row)
    prefix = datetime.now(timezone.utc).isoformat(timespec="seconds")
    parts = [f"{key}={value}" for key, value in compact.items()]
    if latest_timestamp not in (None, ""):
        parts.append(f"latest_payload_timestamp={latest_timestamp}")
    print(f"[{prefix}] " + " | ".join(parts), flush=True)


def _append_csv(path: str, rows: list[dict[str, Any]]) -> None:
    if not path or not rows:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True) if target.parent != Path(".") else None
    fieldnames = list(dict.fromkeys(field for row in rows for field in row.keys()))
    exists = target.exists() and target.stat().st_size > 0
    with target.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    username, password, tickers, max_seconds, csv_path = _validate_env()
    FiinSession = _load_fiin_session()
    stop_event = threading.Event()
    columns_printed = threading.Event()
    client_holder: dict[str, Any] = {}

    def request_stop(signum: int | None = None, frame: Any = None) -> None:
        if signum is not None:
            print("Stop requested; closing probe...", flush=True)
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    def callback(payload: Any) -> None:
        try:
            columns, records = _iter_records(payload)
            if columns and not columns_printed.is_set():
                print("columns=" + ",".join(columns), flush=True)
                columns_printed.set()
            latest_timestamp = None
            for row in records:
                latest_timestamp = _first_present(row, TIMESTAMP_CANDIDATES) or latest_timestamp
                _print_row(row, latest_timestamp)
            if csv_path:
                _append_csv(csv_path, records)
        except Exception as exc:
            print(f"callback_error={type(exc).__name__}: {exc}", flush=True)

    try:
        print(
            f"Starting FiinQuantX realtime probe for tickers={','.join(tickers)} "
            f"runtime_seconds={max_seconds} csv_enabled={bool(csv_path)}",
            flush=True,
        )
        client = FiinSession(username=username, password=password).login()
        client_holder["client"] = client
        print("login=ok", flush=True)
    except Exception as exc:
        print(f"login_error={type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1

    def stream_worker() -> None:
        try:
            client_holder["stream_result"] = client_holder["client"].Trading_Data_Stream(
                tickers=tickers,
                callback=callback,
            )
        except Exception as exc:
            client_holder["stream_error"] = exc
            stop_event.set()

    worker = threading.Thread(target=stream_worker, name="fiinquant-realtime-stream", daemon=True)
    worker.start()

    deadline = time.monotonic() + max_seconds
    while not stop_event.is_set() and time.monotonic() < deadline:
        time.sleep(0.25)

    stop_event.set()
    client = client_holder.get("client")
    for method_name in ("stop", "close", "disconnect", "logout"):
        method = getattr(client, method_name, None)
        if callable(method):
            try:
                method()
                print(f"{method_name}=ok", flush=True)
                break
            except Exception as exc:
                print(f"{method_name}_error={type(exc).__name__}: {exc}", flush=True)

    stream_error = client_holder.get("stream_error")
    if stream_error:
        print(f"stream_error={type(stream_error).__name__}: {stream_error}", file=sys.stderr, flush=True)
        return 1
    print("probe_done=ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
