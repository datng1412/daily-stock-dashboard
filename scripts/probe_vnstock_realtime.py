#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone vnstock KBS realtime/snapshot quote probe.

This script is intentionally not integrated with the application. It checks
whether vnstock KBS quote surfaces work in this environment without changing
Mozyfin behavior or dashboard latest_price semantics.
"""

from __future__ import annotations

import os
import sys
from typing import Any


COMPACT_FIELDS = (
    "symbol",
    "ticker",
    "code",
    "time",
    "tradingDate",
    "trading_time",
    "lastPrice",
    "last_price",
    "matchPrice",
    "match_price",
    "price",
    "refPrice",
    "reference",
    "open",
    "high",
    "low",
    "close",
    "change",
    "changePercent",
    "change_percent",
    "volume",
    "matchVolume",
    "match_volume",
    "totalVolume",
    "total_volume",
)


def _parse_tickers() -> list[str]:
    raw = (os.getenv("VNSTOCK_TICKERS") or "FPT,ACB,VCB").strip()
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def _load_vnstock() -> tuple[Any | None, Any | None]:
    try:
        from vnstock import Market, Trading
    except ImportError:
        print("vnstock_missing=pip install -U vnstock", flush=True)
        return None, None
    except Exception as exc:
        print(f"vnstock_import_error={type(exc).__name__}: {exc}", flush=True)
        return None, None

    return Trading, Market


def _to_dataframe(payload: Any) -> Any:
    if hasattr(payload, "to_dataFrame"):
        return payload.to_dataFrame()
    if hasattr(payload, "to_dataframe"):
        return payload.to_dataframe()
    return payload if hasattr(payload, "columns") and hasattr(payload, "to_dict") else None


def _columns_and_rows(payload: Any) -> tuple[list[str], list[dict[str, Any]]]:
    df = _to_dataframe(payload)
    if df is not None:
        columns = [str(column) for column in getattr(df, "columns", [])]
        if hasattr(df, "to_dict"):
            return columns, list(df.to_dict("records"))

    if isinstance(payload, dict):
        return [str(key) for key in payload.keys()], [payload]

    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
        columns = list(dict.fromkeys(key for row in rows for key in row.keys()))
        return [str(column) for column in columns], rows

    return [], []


def _shape(payload: Any, rows: list[dict[str, Any]], columns: list[str]) -> str:
    df = _to_dataframe(payload)
    if df is not None and hasattr(df, "shape"):
        return str(tuple(df.shape))
    return str((len(rows), len(columns)))


def _compact_row(row: dict[str, Any]) -> dict[str, Any]:
    compact = {field: row.get(field) for field in COMPACT_FIELDS if field in row}
    return compact or {key: row.get(key) for key in list(row.keys())[:8]}


def _print_result(label: str, payload: Any, max_rows: int = 5) -> None:
    columns, rows = _columns_and_rows(payload)
    print(f"{label}_shape={_shape(payload, rows, columns)}", flush=True)
    print(f"{label}_columns=" + ",".join(columns), flush=True)
    for index, row in enumerate(rows[:max_rows], 1):
        compact = _compact_row(row)
        parts = [f"{key}={value}" for key, value in compact.items()]
        print(f"{label}_row_{index}=" + " | ".join(parts), flush=True)


def _method_error(label: str, exc: BaseException) -> None:
    print(f"{label}_error={type(exc).__name__}: {exc}", flush=True)


def main() -> int:
    tickers = _parse_tickers()
    print("provider=vnstock", flush=True)
    print("source=KBS", flush=True)
    print(f"tickers={','.join(tickers)}", flush=True)
    print(f"python_version={sys.version.split()[0]}", flush=True)

    if not tickers:
        print("tickers_error=VNSTOCK_TICKERS produced an empty ticker list.", flush=True)
        return 1

    Trading, Market = _load_vnstock()
    if Trading is None or Market is None:
        return 0

    try:
        price_board = Trading(source="KBS").price_board(tickers)
        _print_result("price_board", price_board)
    except Exception as exc:
        _method_error("price_board", exc)

    first_symbol = tickers[0]
    try:
        quote = Market().equity(first_symbol).quote()
        _print_result(f"quote_{first_symbol}", quote, max_rows=1)
    except Exception as exc:
        _method_error(f"quote_{first_symbol}", exc)

    try:
        trades = Market().equity(first_symbol).trades()
        _print_result(f"trades_{first_symbol}", trades)
    except Exception as exc:
        _method_error(f"trades_{first_symbol}", exc)

    print("probe_done=ok", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
