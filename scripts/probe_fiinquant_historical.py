#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone FiinQuantX historical/trading data access probe.

This script is intentionally not integrated with the application. It checks
whether a FiinQuantX account can access non-stream trading data, without
changing Mozyfin behavior or dashboard price semantics.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional


DEFAULT_FIELDS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
]

COMPACT_FIELDS = (
    "Ticker",
    "ticker",
    "TradingDate",
    "Date",
    "date",
    "Time",
    "Open",
    "open",
    "High",
    "high",
    "Low",
    "low",
    "Close",
    "close",
    "Volume",
    "volume",
)


def _load_dotenv_file() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


_load_dotenv_file()


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _parse_tickers() -> list[str]:
    raw = _env("FIINQUANT_TICKERS") or "ACB"
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def _parse_history_days() -> int:
    raw = _env("FIINQUANT_HISTORY_DAYS") or "5"
    try:
        value = int(raw)
    except ValueError:
        raise SystemExit("FIINQUANT_HISTORY_DAYS must be an integer.")
    if value <= 0:
        raise SystemExit("FIINQUANT_HISTORY_DAYS must be greater than 0.")
    return value


def _validate_env() -> tuple[str, str, list[str], int]:
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

    return username, password, tickers, _parse_history_days()


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
        except (ImportError, AttributeError) as exc:
            last_error = exc

    raise SystemExit(f"Unable to import FiinQuantX. {install_hint}") from last_error


def _public_callable_names(obj: Any) -> list[str]:
    names: list[str] = []
    for name in dir(obj):
        if name.startswith("_"):
            continue
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        if callable(value):
            names.append(name)
    return sorted(names)


def _to_dataframe(payload: Any) -> Any:
    if hasattr(payload, "to_dataFrame"):
        return payload.to_dataFrame()
    if hasattr(payload, "to_dataframe"):
        return payload.to_dataframe()
    return payload if hasattr(payload, "to_dict") and hasattr(payload, "columns") else None


def _iter_records(payload: Any) -> tuple[list[str], list[dict[str, Any]]]:
    df = _to_dataframe(payload)
    if df is not None:
        columns = [str(column) for column in getattr(df, "columns", [])]
        if hasattr(df, "to_dict"):
            return columns, list(df.to_dict("records"))

    if isinstance(payload, dict):
        return list(payload.keys()), [payload]

    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
        if rows:
            columns = list(dict.fromkeys(key for row in rows for key in row.keys()))
            return columns, rows

    return [], []


def _compact_row(row: dict[str, Any]) -> dict[str, Any]:
    compact = {field: row.get(field) for field in COMPACT_FIELDS if field in row}
    return compact or {"row_type": type(row).__name__}


def _print_rows(rows: Iterable[dict[str, Any]]) -> None:
    for index, row in enumerate(list(rows)[-3:], 1):
        compact = _compact_row(row)
        parts = [f"{key}={value}" for key, value in compact.items()]
        print(f"row_{index}=" + " | ".join(parts), flush=True)


def _find_historical_method(client: Any) -> str | None:
    public_methods = _public_callable_names(client)
    if "Fetch_Trading_Data" in public_methods:
        return "Fetch_Trading_Data"
    return None


def _call_historical_method(client: Any, method_name: str, tickers: list[str], days: int) -> Any:
    if method_name != "Fetch_Trading_Data":
        raise RuntimeError(f"Unsupported historical method: {method_name}")

    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)
    method = getattr(client, method_name)
    return method(
        realtime=False,
        tickers=tickers,
        fields=DEFAULT_FIELDS,
        adjusted=True,
        by="1d",
        from_date=from_date,
        to_date=to_date,
    )


def main() -> int:
    username, password, tickers, history_days = _validate_env()
    FiinSession = _load_fiin_session()

    print("provider=FiinQuantX", flush=True)
    print(f"tickers={','.join(tickers)}", flush=True)
    print(f"history_days={history_days}", flush=True)
    print(f"python_version={sys.version.split()[0]}", flush=True)

    try:
        session = FiinSession(username=username, password=password)
        login_result = session.login()
        client = (
            login_result
            if login_result is not None and hasattr(login_result, "__dict__")
            else session
        )
        print("login=ok", flush=True)
    except Exception as exc:
        print(f"login_error={type(exc).__name__}: {exc}", flush=True)
        return 1

    print(f"client_has_is_login={hasattr(client, 'is_login')}", flush=True)
    print(f"client_is_login={getattr(client, 'is_login', None)}", flush=True)
    print(f"client_has_access_token={bool(getattr(client, 'access_token', None))}", flush=True)

    public_methods = _public_callable_names(client)
    print("public_methods=" + ",".join(public_methods), flush=True)

    method_name = _find_historical_method(client)
    if not method_name:
        print("historical_method_not_found", flush=True)
        return 0

    print(f"historical_method={method_name}", flush=True)

    try:
        payload = _call_historical_method(client, method_name, tickers, history_days)
    except Exception as exc:
        print(f"historical_error={type(exc).__name__}: {exc}", flush=True)
        return 1

    columns, rows = _iter_records(payload)
    print("columns=" + ",".join(columns), flush=True)
    print(f"row_count={len(rows)}", flush=True)
    _print_rows(rows)
    print("historical_probe_done=ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
