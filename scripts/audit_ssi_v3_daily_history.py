"""Bounded, secret-safe SSI V3 daily-history acceptance.

Network access is disabled unless both ``--live`` and
``SSI_V3_LIVE_ACCEPTANCE_ENABLED=true`` are present. Output contains only
normalized counts, date bounds, freshness state, and the latest OHLC values.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_provider.ssi_v3_adapter import (  # noqa: E402
    SsiFastConnectV3Adapter,
    SsiV3RestSettings,
)
from src.config import get_config  # noqa: E402


LIVE_GUARD_ENV = "SSI_V3_LIVE_ACCEPTANCE_ENABLED"
SYMBOLS = ("FPT", "SSI", "VCB", "SHS", "ACV")
FOREIGN_FIELDS = (
    "foreign_buy_volume",
    "foreign_sell_volume",
    "foreign_net_volume",
    "foreign_buy_value",
    "foreign_sell_value",
    "foreign_net_value",
)


def _enabled(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _last_row(rows: Any) -> Dict[str, Any]:
    normalized = [row for row in (rows or []) if isinstance(row, dict)]
    return normalized[-1] if normalized else {}


def _value_state(row: Dict[str, Any], key: str) -> str:
    if key not in row:
        return "absent"
    value = row.get(key)
    if value is None:
        return "null"
    return "zero" if value == 0 else "nonzero"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not args.live or not _enabled(os.getenv(LIVE_GUARD_ENV)):
        print(
            json.dumps(
                {
                    "outcome": "NOT_RUN",
                    "reason": (
                        f"Requires --live and {LIVE_GUARD_ENV}=true."
                    ),
                    "symbols": list(SYMBOLS),
                    "operation_count": 0,
                },
                sort_keys=True,
            )
        )
        return 0

    config = get_config()
    settings = SsiV3RestSettings.from_config(config)
    adapter = SsiFastConnectV3Adapter(settings)
    report: Dict[str, Any] = {
        "outcome": "STARTED",
        "symbols": {},
        "operation_count": 0,
    }
    try:
        auth = adapter.initialize_rest_access()
        if auth.get("status") != "ok":
            report["outcome"] = "AUTHENTICATION_UNAVAILABLE"
            report["authentication_status"] = auth.get("status")
            print(json.dumps(report, sort_keys=True))
            return 2

        for symbol in SYMBOLS:
            daily = adapter.get_daily_ohlcv(symbol, limit=260)
            report["operation_count"] += 1
            daily_price = adapter.get_daily_stock_price(symbol, limit=20)
            report["operation_count"] += 1
            diagnostics = dict(daily.get("diagnostics") or {})
            latest_daily = _last_row(daily.get("rows"))
            latest_price = _last_row(daily_price.get("rows"))
            daily_date = latest_daily.get("date")
            daily_price_date = latest_price.get("date")
            report["symbols"][symbol] = {
                "daily_status": daily.get("status"),
                "page_count": diagnostics.get("page_count"),
                "provider_row_count": diagnostics.get("provider_row_count"),
                "normalized_row_count": diagnostics.get("normalized_row_count"),
                "min_date": diagnostics.get("min_date"),
                "max_date": diagnostics.get("max_date"),
                "latest_daily_stock_price_date": daily_price_date,
                "daily_date_match": (
                    daily_date == daily_price_date
                    if daily_date and daily_price_date
                    else None
                ),
                "latest_ohlc": {
                    key: latest_daily.get(key)
                    for key in ("open", "high", "low", "close")
                },
                "latest_foreign_field_states": {
                    key: _value_state(latest_price, key)
                    for key in FOREIGN_FIELDS
                },
                "cache_state": diagnostics.get("cache_source"),
                "freshness_state": diagnostics.get("freshness_status"),
            }
        report["outcome"] = "COMPLETED"
        print(json.dumps(report, sort_keys=True))
        return 0
    finally:
        adapter.close()


if __name__ == "__main__":
    raise SystemExit(main())
