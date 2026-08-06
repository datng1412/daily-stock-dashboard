"""Bounded, sanitized SSI V3 evidence for suspicious VN30 foreign-flow dates.

This manual diagnostic owns no application lifecycle.  It reuses one shared
REST provider, never prints credentials or raw provider payloads, and emits
only normalized foreign-field evidence needed by the R6E repair gate.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import json
from pathlib import Path
import sys
from time import monotonic
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_provider.ssi_provider_router import create_ssi_rest_provider_router


MAX_SYMBOLS = 30
MAX_CONCURRENCY = 4
DEFAULT_DATES = ("2026-06-29", "2026-06-30")
GROSS_FIELDS = (
    "foreign_buy_volume",
    "foreign_sell_volume",
    "foreign_buy_value",
    "foreign_sell_value",
)


def _date(value: str) -> str:
    return date.fromisoformat(value).isoformat()


def _symbols(rows: Iterable[Any]) -> List[str]:
    result: List[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
        if symbol and symbol not in result:
            result.append(symbol)
    if not result or len(result) > MAX_SYMBOLS:
        raise RuntimeError("VN30 membership must contain between 1 and 30 symbols")
    return result


def _row_evidence(symbol: str, trading_date: str, result: Dict[str, Any]) -> Dict[str, Any]:
    rows = [row for row in result.get("rows") or [] if isinstance(row, dict)]
    row = next((row for row in rows if row.get("date") == trading_date), None)
    presence = dict((row or {}).get("_foreign_field_presence") or {})
    values = {field: (row or {}).get(field) for field in GROSS_FIELDS}
    return {
        "symbol": symbol,
        "requested_from_date": trading_date,
        "requested_to_date": trading_date,
        "provider_operation": "securitiesSummary?symbol=",
        "status": result.get("status"),
        "failure_class": result.get("failure_class"),
        "raw_row_exists": row is not None,
        "raw_trading_date": (row or {}).get("date"),
        "raw_field_aliases_present": sorted(
            field
            for field in GROSS_FIELDS
            if presence.get(field) not in {None, "FIELD_ABSENT"}
        ),
        "field_presence": {field: presence.get(field, "PROVIDER_ROW_MISSING") for field in GROSS_FIELDS},
        **values,
    }


def _emit(value: Dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=True, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dates", nargs="+", default=list(DEFAULT_DATES), type=_date)
    parser.add_argument("--concurrency", type=int, default=MAX_CONCURRENCY)
    parser.add_argument("--deadline-seconds", type=float, default=180.0)
    args = parser.parse_args()
    concurrency = max(1, min(MAX_CONCURRENCY, int(args.concurrency)))
    started = monotonic()
    deadline = started + max(30.0, min(180.0, float(args.deadline_seconds)))
    provider = create_ssi_rest_provider_router()
    try:
        membership = provider.get_index_components("VN30", market="HOSE", force_refresh=True)
        symbols = _symbols(membership.get("rows") or [])
        _emit({
            "mode": "membership",
            "status": membership.get("status"),
            "count": len(symbols),
            "source": "SSI IndexComponents",
        })
        for trading_date in args.dates:
            if monotonic() >= deadline:
                raise TimeoutError("global diagnostic deadline reached")
            evidence: List[Dict[str, Any]] = []
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = {
                    executor.submit(
                        provider.get_daily_stock_price,
                        symbol,
                        from_date=trading_date,
                        to_date=trading_date,
                        limit=1,
                    ): symbol
                    for symbol in symbols
                }
                for future in as_completed(futures):
                    if monotonic() >= deadline:
                        for pending in futures:
                            pending.cancel()
                        raise TimeoutError("global diagnostic deadline reached")
                    symbol = futures[future]
                    try:
                        result = future.result()
                    except Exception as exc:  # sanitized classification only
                        result = {"status": "error", "failure_class": type(exc).__name__}
                    evidence.append(_row_evidence(symbol, trading_date, result))
            evidence.sort(key=lambda row: row["symbol"])
            presence_counts = Counter(
                state
                for row in evidence
                for state in row["field_presence"].values()
            )
            nonzero_rows = sum(
                any(row.get(field) not in (None, 0) for field in GROSS_FIELDS)
                for row in evidence
            )
            exact_zero_rows = sum(
                row["raw_row_exists"]
                and all(row.get(field) == 0 for field in GROSS_FIELDS)
                and all(
                    row["field_presence"].get(field) == "FIELD_PRESENT_EXPLICIT_ZERO"
                    for field in GROSS_FIELDS
                )
                for row in evidence
            )
            _emit({
                "mode": "exact_date_summary",
                "trading_date": trading_date,
                "request_count": len(evidence),
                "concurrency": concurrency,
                "row_exists_count": sum(row["raw_row_exists"] for row in evidence),
                "nonzero_row_count": nonzero_rows,
                "explicit_zero_row_count": exact_zero_rows,
                "presence_counts": dict(sorted(presence_counts.items())),
                "status_counts": dict(sorted(Counter(str(row["status"]) for row in evidence).items())),
                "rows": evidence,
            })
            alternative = provider.get_securities_summary_by_index(
                "VN30",
                from_date=trading_date,
                to_date=trading_date,
                page_index=1,
                page_size=100,
                limit=100,
            )
            alternative_rows = [
                row for row in alternative.get("rows") or [] if isinstance(row, dict)
            ]
            _emit({
                "mode": "alternative_index_summary",
                "trading_date": trading_date,
                "provider_operation": "securitiesSummary?index=VN30",
                "status": alternative.get("status"),
                "failure_class": alternative.get("failure_class"),
                "row_count": len(alternative_rows),
                "nonzero_row_count": sum(
                    any(row.get(field) not in (None, 0) for field in GROSS_FIELDS)
                    for row in alternative_rows
                ),
                "presence_counts": dict(sorted(Counter(
                    state
                    for row in alternative_rows
                    for state in dict(row.get("_foreign_field_presence") or {}).values()
                ).items())),
            })
        _emit({"mode": "complete", "elapsed_ms": round((monotonic() - started) * 1000)})
        return 0
    finally:
        provider.close()


if __name__ == "__main__":
    raise SystemExit(main())
