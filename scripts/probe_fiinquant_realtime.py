#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone FiinQuantX realtime quote probe.

This script is intentionally not integrated with the application.

It:
- reads credentials from environment variables or repo .env
- starts a short FiinQuantX realtime stream probe
- prints compact callback rows for manual validation
- never prints credentials
"""

from __future__ import annotations

import csv
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Iterable, Optional


FIELDS_TO_PRINT = (
    "Ticker",
    "TradingDate",
    "TradingTime",
    "Time",
    "DateTime",
    "Timestamp",
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


def _load_dotenv_file() -> None:
    """Load repo .env if python-dotenv is installed.

    The probe still works without python-dotenv when env vars are set directly
    in PowerShell.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


_load_dotenv_file()


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _parse_tickers() -> list[str]:
    raw = _env("FIINQUANT_TICKERS") or "FPT,HPG,VNINDEX"
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def _parse_runtime_seconds() -> int:
    raw = _env("FIINQUANT_PROBE_SECONDS") or "60"
    try:
        return int(raw)
    except ValueError:
        raise SystemExit("FIINQUANT_PROBE_SECONDS must be an integer.")


def _validate_env() -> tuple[str, str, list[str], int, str]:
    username = _env("FIINQUANT_USERNAME")
    password = _env("FIINQUANT_PASSWORD")

    missing = [
        name
        for name, value in (
            ("FIINQUANT_USERNAME", username),
            ("FIINQUANT_PASSWORD", password),
        )
        if not value
    ]

    if missing:
        raise SystemExit(
            "Missing required environment variable(s): " + ", ".join(missing)
        )

    tickers = _parse_tickers()
    if not tickers:
        raise SystemExit("FIINQUANT_TICKERS produced an empty ticker list.")

    csv_path = _env("FIINQUANT_PROBE_CSV")
    runtime_seconds = _parse_runtime_seconds()

    return username, password, tickers, runtime_seconds, csv_path


def _load_fiin_session() -> Any:
    install_hint = (
        "Install it with: "
        "pip install --extra-index-url "
        "https://fiinquant.github.io/fiinquantx/simple fiinquantx"
    )

    last_error: Optional[BaseException] = None

    for module_name in ("fiinquantx", "FiinQuantX"):
        try:
            module = __import__(module_name, fromlist=["FiinSession"])
            return getattr(module, "FiinSession")
        except ModuleNotFoundError as exc:
            if exc.name not in {module_name, "fiinquantx", "FiinQuantX"}:
                raise SystemExit(
                    "Unable to import FiinQuantX because dependency "
                    f"'{exc.name}' is missing. Install the missing dependency "
                    "in this venv, then rerun the probe."
                ) from exc
            last_error = exc
        except ImportError as exc:
            last_error = exc
        except AttributeError as exc:
            last_error = exc

    raise SystemExit(f"Unable to import FiinQuantX. {install_hint}") from last_error


def _patch_signalrcore_negotiate_version() -> None:
    """Patch signalrcore negotiation parsing for this standalone probe only.

    This compatibility shim is intentionally probe-only. Production integration
    should use a vendor-supported dependency/runtime combination instead of
    silently monkey-patching third-party realtime libraries.
    """
    try:
        from signalrcore.hub.negotiation import NegotiateResponse
    except Exception:
        return

    if getattr(NegotiateResponse, "_dsa_negotiate_version_patched", False):
        return

    try:
        original_from_dict = NegotiateResponse.from_dict
    except Exception:
        return

    def patched_from_dict(*args: Any, **kwargs: Any) -> Any:
        patched_args = list(args)
        data_index: Optional[int] = None
        data = kwargs.get("data")

        if isinstance(data, dict):
            patched_data = dict(data)
        else:
            patched_data = None
            for index, arg in enumerate(patched_args):
                if isinstance(arg, dict):
                    data_index = index
                    patched_data = dict(arg)
                    break

        if patched_data is not None:
            negotiate_version = patched_data.get("negotiateVersion")

            if negotiate_version is None:
                patched_data["negotiateVersion"] = 0
            elif isinstance(negotiate_version, str):
                try:
                    patched_data["negotiateVersion"] = int(negotiate_version)
                except ValueError:
                    pass

            if "data" in kwargs and isinstance(kwargs.get("data"), dict):
                kwargs = dict(kwargs)
                kwargs["data"] = patched_data
            elif data_index is not None:
                patched_args[data_index] = patched_data

        return original_from_dict(*patched_args, **kwargs)

    try:
        NegotiateResponse.from_dict = staticmethod(patched_from_dict)
        NegotiateResponse._dsa_negotiate_version_patched = True
    except Exception:
        return


def _module_path(module_name: str) -> str:
    try:
        module = __import__(module_name)
    except Exception:
        return "unavailable"
    return str(getattr(module, "__file__", "unknown"))


def _signalrcore_version() -> str:
    try:
        module = __import__("signalrcore")
    except Exception:
        return "unavailable"

    version = getattr(module, "__version__", None)
    if version:
        return str(version)

    try:
        return metadata.version("signalrcore")
    except Exception:
        return "unknown"


def _print_startup_diagnostics(fiin_session: Any) -> None:
    module_name = str(getattr(fiin_session, "__module__", ""))
    root_module = module_name.split(".", 1)[0] if module_name else "FiinQuantX"

    print(f"python_version={sys.version.split()[0]}", flush=True)
    print(f"fiinquant_module_path={_module_path(root_module)}", flush=True)
    print(f"signalrcore_module_path={_module_path('signalrcore')}", flush=True)
    print(f"signalrcore_version={_signalrcore_version()}", flush=True)


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

    if target.parent != Path("."):
        target.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(dict.fromkeys(field for row in rows for field in row.keys()))
    exists = target.exists() and target.stat().st_size > 0

    with target.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")

        if not exists:
            writer.writeheader()

        writer.writerows(rows)


def _stop_object(obj: Any, label: str) -> bool:
    if obj is None:
        return False

    for method_name in ("stop", "close", "disconnect", "logout"):
        method = getattr(obj, method_name, None)

        if callable(method):
            try:
                method()
                print(f"{label}_{method_name}=ok", flush=True)
                return True
            except Exception as exc:
                print(
                    f"{label}_{method_name}_error={type(exc).__name__}: {exc}",
                    flush=True,
                )

    return False


def main() -> int:
    username, password, tickers, max_seconds, csv_path = _validate_env()
    FiinSession = _load_fiin_session()
    _patch_signalrcore_negotiate_version()

    stop_event = threading.Event()
    columns_printed = threading.Event()
    counters = {"payloads": 0, "rows": 0}
    client_holder: dict[str, Any] = {}
    thread_errors: list[str] = []
    previous_excepthook = threading.excepthook

    def capture_thread_exception(args: threading.ExceptHookArgs) -> None:
        message = f"{args.exc_type.__name__}: {args.exc_value}"
        thread_errors.append(message)
        print(f"thread_error={message}", file=sys.stderr, flush=True)
        stop_event.set()

        if previous_excepthook is not threading.__excepthook__:
            try:
                previous_excepthook(args)
            except Exception:
                pass

    threading.excepthook = capture_thread_exception
    stream_failed = False

    def request_stop(signum: int | None = None, frame: Any = None) -> None:
        if signum is not None:
            print("Stop requested; closing probe...", flush=True)
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    def callback(payload: Any) -> None:
        try:
            counters["payloads"] += 1

            columns, records = _iter_records(payload)

            if columns and not columns_printed.is_set():
                print("columns=" + ",".join(columns), flush=True)
                columns_printed.set()

            latest_timestamp = None

            for row in records:
                counters["rows"] += 1
                latest_timestamp = _first_present(row, TIMESTAMP_CANDIDATES) or latest_timestamp
                _print_row(row, latest_timestamp)

            if csv_path:
                _append_csv(csv_path, records)

        except Exception as exc:
            print(f"callback_error={type(exc).__name__}: {exc}", flush=True)

    try:
        runtime_label = "until Ctrl+C" if max_seconds <= 0 else f"{max_seconds}s"
        print("provider=FiinQuantX", flush=True)
        print(f"tickers={','.join(tickers)}", flush=True)
        print(f"runtime={runtime_label}", flush=True)
        print(f"csv_enabled={bool(csv_path)}", flush=True)
        _print_startup_diagnostics(FiinSession)

        session = FiinSession(username=username, password=password)
        login_result = session.login()
        client = (
            login_result
            if hasattr(login_result, "Trading_Data_Stream")
            else session
        )
        client_holder["client"] = client

        if getattr(client, "is_login", True) is False:
            print(
                "login_error=FiinQuantX login returned without an active session",
                file=sys.stderr,
                flush=True,
            )
            return 1

        print("login=ok", flush=True)

    except Exception as exc:
        print(f"login_error={type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 1

    try:
        event = client_holder["client"].Trading_Data_Stream(
            tickers=tickers,
            callback=callback,
        )
        client_holder["stream_event"] = event

        print(f"event_class={type(event).__name__}", flush=True)
        print(f"event_has_start={callable(getattr(event, 'start', None))}", flush=True)
        print(f"event_has_stop={callable(getattr(event, 'stop', None))}", flush=True)
        print(f"event_has__stop={hasattr(event, '_stop')}", flush=True)

        event.start()

        deadline = None if max_seconds <= 0 else time.monotonic() + max_seconds

        while not stop_event.is_set():
            if deadline is not None and time.monotonic() >= deadline:
                break
            if hasattr(event, "_stop") and getattr(event, "_stop"):
                break
            time.sleep(1)

    except Exception as exc:
        stream_failed = True
        print(
            f"stream_error={type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        stop_event.set()
    finally:
        stop_event.set()
        _stop_object(client_holder.get("stream_event"), "stream")
        _stop_object(client_holder.get("client"), "client")

    print(f"callback_payloads={counters['payloads']}", flush=True)
    print(f"callback_rows={counters['rows']}", flush=True)

    if counters["payloads"] == 0:
        print(
            "warning=no_callback_payloads_received. "
            "Possible causes: market closed, free plan limitation, wrong ticker format, "
            "or stream did not start.",
            flush=True,
        )

    print("probe_done=ok", flush=True)
    return 1 if stream_failed or thread_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
