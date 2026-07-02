# -*- coding: utf-8 -*-
"""Manual, bounded, secret-safe profiling for Vietnam watchlist hydration.

This script is not imported by application startup. It emits only aggregate
timings, cache-state counts, row statuses, and source labels; it never emits
provider payloads, credentials, headers, tokens, or exception messages.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import setup_env  # noqa: E402

setup_env()

import src.services.vietnam_market_service as vietnam_market  # noqa: E402


PROFILE_CASES = {
    "one": ("FPT",),
    "five": ("FPT", "HPG", "SSI", "VCB", "ACB"),
    "ten": ("VCB", "BID", "CTG", "MBB", "TCB", "ACB", "VPB", "HDB", "STB", "TPB"),
}
MAX_PROFILE_TICKERS = 30
MAX_PROFILE_REPEATS = 2
TICKER_PATTERN = re.compile(r"^[A-Z0-9]{2,10}$")


def parse_profile_tickers(raw: str, *, allow_thirty: bool = False) -> List[str]:
    """Normalize a bounded ticker list without inventing or persisting members."""
    tickers: List[str] = []
    seen = set()
    for value in str(raw or "").split(","):
        ticker = value.strip().upper().removesuffix(".VN")
        if not ticker:
            continue
        if not TICKER_PATTERN.fullmatch(ticker):
            raise ValueError("invalid_ticker")
        if ticker in seen:
            continue
        seen.add(ticker)
        tickers.append(ticker)
    if not tickers:
        raise ValueError("tickers_required")
    allowed_count = MAX_PROFILE_TICKERS if allow_thirty else 10
    if len(tickers) > allowed_count:
        raise ValueError("ticker_limit_exceeded")
    return tickers


class ProfilingVietnamMarketService(vietnam_market.VietnamMarketService):
    """Time existing service stages without changing the production request path."""

    def __init__(self) -> None:
        super().__init__()
        self.stage_seconds: Dict[str, float] = defaultdict(float)
        self.per_ticker_seconds: Dict[str, float] = {}

    def _timed(self, stage: str, action: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return action(*args, **kwargs)
        finally:
            self.stage_seconds[stage] += time.perf_counter() - started

    def _load_ssi_daily_ohlcv(self, *args: Any, **kwargs: Any) -> Any:
        return self._timed("daily_ohlcv_provider", super()._load_ssi_daily_ohlcv, *args, **kwargs)

    def _latest_ssi_daily_stock_price(self, *args: Any, **kwargs: Any) -> Any:
        return self._timed(
            "daily_stock_price_and_foreign_history_provider",
            super()._latest_ssi_daily_stock_price,
            *args,
            **kwargs,
        )

    def _load_ssi_symbol_metadata(self, *args: Any, **kwargs: Any) -> Any:
        return self._timed("metadata_provider", super()._load_ssi_symbol_metadata, *args, **kwargs)

    def _load_ssi_intraday_payload(self, *args: Any, **kwargs: Any) -> Any:
        return self._timed("intraday_optional_provider", super()._load_ssi_intraday_payload, *args, **kwargs)

    def _load_ssi_realtime_payload(self, *args: Any, **kwargs: Any) -> Any:
        return self._timed("realtime_optional_read", super()._load_ssi_realtime_payload, *args, **kwargs)

    def _load_ssi_trade_tape_payload(self, *args: Any, **kwargs: Any) -> Any:
        return self._timed("trade_tape_optional_provider", super()._load_ssi_trade_tape_payload, *args, **kwargs)

    def _build_symbol(self, symbol: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        started = time.perf_counter()
        try:
            return super()._build_symbol(symbol, *args, **kwargs)
        finally:
            self.per_ticker_seconds[symbol] = time.perf_counter() - started


def _status_counts(rows: Iterable[Dict[str, Any]], field: str) -> Dict[str, int]:
    values = [str((row.get("cache_status") or {}).get(field) or "missing") for row in rows]
    return {status: values.count(status) for status in sorted(set(values))}


def profile_watchlist_case(
    case_name: str,
    tickers: List[str],
    *,
    repeat: int = 1,
    include_intraday: bool = True,
    force_refresh: bool = False,
    service_factory: Callable[[], ProfilingVietnamMarketService] = ProfilingVietnamMarketService,
    clear_cache: bool = True,
) -> Dict[str, Any]:
    """Profile one bounded case and return a whitelist-only summary."""
    safe_repeat = max(1, min(int(repeat), MAX_PROFILE_REPEATS))
    if clear_cache:
        vietnam_market.clear_vietnam_cache()
    runs: List[Dict[str, Any]] = []

    for run_index in range(safe_repeat):
        service = service_factory()
        original_indicators = vietnam_market.calculate_vietnam_indicators

        def timed_indicators(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            started = time.perf_counter()
            try:
                return original_indicators(*args, **kwargs)
            finally:
                service.stage_seconds["ta_indicators"] += time.perf_counter() - started

        vietnam_market.calculate_vietnam_indicators = timed_indicators
        started = time.perf_counter()
        try:
            payload = service.build_watchlist(
                tickers,
                force_refresh=force_refresh,
                include_intraday=include_intraday,
            )
            total_seconds = time.perf_counter() - started
            serialization_started = time.perf_counter()
            json.dumps(payload, default=str)
            serialization_seconds = time.perf_counter() - serialization_started
            rows = [row for row in (payload.get("watchlist") or []) if isinstance(row, dict)]
            row_statuses = [str(row.get("status") or "unknown") for row in rows]
            runs.append(
                {
                    "run": run_index + 1,
                    "status": "ok",
                    "total_seconds": round(total_seconds, 4),
                    "serialization_seconds": round(serialization_seconds, 6),
                    "returned_rows_count": len(rows),
                    "row_status_counts": {
                        status: row_statuses.count(status)
                        for status in sorted(set(row_statuses))
                    },
                    "latest_price_sources": sorted(
                        {
                            str(row.get("latest_price_source"))
                            for row in rows
                            if row.get("latest_price_source")
                        }
                    ),
                    "daily_stock_price_ok_count": sum(
                        1
                        for row in rows
                        if (row.get("daily_stock_price") or {}).get("status") == "ok"
                    ),
                    "stage_seconds": {
                        stage: round(seconds, 4)
                        for stage, seconds in sorted(service.stage_seconds.items())
                    },
                    "per_ticker_seconds": {
                        ticker: round(seconds, 4)
                        for ticker, seconds in service.per_ticker_seconds.items()
                    },
                    "cache_status_counts": {
                        field: _status_counts(rows, field)
                        for field in (
                            "ohlcv_cache",
                            "daily_stock_price_cache",
                            "intraday_cache",
                            "realtime_cache",
                            "trade_tape_cache",
                        )
                    },
                }
            )
        except Exception as exc:  # noqa: BLE001 - manual profiler must degrade safely.
            runs.append(
                {
                    "run": run_index + 1,
                    "status": "error",
                    "total_seconds": round(time.perf_counter() - started, 4),
                    "error_type": type(exc).__name__,
                }
            )
        finally:
            vietnam_market.calculate_vietnam_indicators = original_indicators

    return {
        "case": case_name,
        "ticker_count": len(tickers),
        "include_intraday": include_intraday,
        "force_refresh": force_refresh,
        "runs": runs,
    }


def _resolve_cases(case_names: Optional[List[str]], raw_tickers: Optional[str], allow_thirty: bool) -> List[tuple[str, List[str]]]:
    cases = [
        (name, list(PROFILE_CASES[name]))
        for name in (case_names or ["one"])
    ]
    if raw_tickers:
        cases.append(("custom", parse_profile_tickers(raw_tickers, allow_thirty=allow_thirty)))
    return cases


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Profile bounded VN watchlist hydration with sanitized output.")
    parser.add_argument("--case", action="append", choices=sorted(PROFILE_CASES), dest="cases")
    parser.add_argument("--tickers", help="Optional comma-separated custom ticker set; limited to 10 unless --allow-thirty.")
    parser.add_argument("--allow-thirty", action="store_true", help="Allow an explicit custom set of up to 30 tickers.")
    parser.add_argument("--repeat", type=int, default=1, choices=range(1, MAX_PROFILE_REPEATS + 1))
    parser.add_argument("--skip-intraday", action="store_true", help="Exclude optional intraday hydration from the profile.")
    parser.add_argument("--force-refresh", action="store_true", help="Intentionally bypass process-level caches.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.disable(logging.CRITICAL)
    try:
        cases = _resolve_cases(args.cases, args.tickers, args.allow_thirty)
        results = [
            profile_watchlist_case(
                name,
                tickers,
                repeat=args.repeat,
                include_intraday=not args.skip_intraday,
                force_refresh=args.force_refresh,
            )
            for name, tickers in cases
        ]
        output = {"status": "ok", "results": results}
        exit_code = 0
    except Exception as exc:  # noqa: BLE001 - never emit secret-bearing error text.
        output = {"status": "error", "error_type": type(exc).__name__}
        exit_code = 2
    print(json.dumps(output, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
