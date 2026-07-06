# -*- coding: utf-8 -*-
"""Secret-safe SSI DailyOhlc capability diagnostic.

This script is manual-only. It checks the strict SSI DailyOhlc path with a
small ticker set and bounded request shapes. It does not print credentials,
auth headers, tokens, account IDs, cookies, or raw provider bodies.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_provider.ssi_fastconnect_fetcher import (
    REQUEST_FAILED_REASON,
    SsiFastConnectFetcher,
    _extract_rows,
    _has_required_field,
    _should_retry_param_variant,
    format_ssi_date,
)


SECRET_KEY_MARKERS = (
    "token",
    "secret",
    "authorization",
    "auth",
    "cookie",
    "account",
    "consumer",
    "key",
)

MAX_TICKERS = 10


def is_secret_key(key: Any) -> bool:
    lowered = str(key or "").strip().lower()
    return any(marker in lowered for marker in SECRET_KEY_MARKERS)


def sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return sanitize_mapping(value)
    if isinstance(value, list):
        return [sanitize_value(item) for item in value[:20]]
    if isinstance(value, tuple):
        return [sanitize_value(item) for item in value[:20]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        text = str(value) if isinstance(value, str) else value
        if isinstance(text, str) and len(text) > 200:
            return text[:200] + "..."
        return text
    return str(type(value).__name__)


def sanitize_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
    safe: Dict[str, Any] = {}
    for key, value in (mapping or {}).items():
        safe_key = str(key)
        if is_secret_key(safe_key):
            safe[safe_key] = "<redacted>"
        else:
            safe[safe_key] = sanitize_value(value)
    return safe


def classify_provider_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "unknown"
    if str(payload.get("status") or "").lower() == "ok":
        rows = payload.get("rows")
        if isinstance(rows, list) and rows:
            return "ok"
        return "empty_response"
    failure_class = str(payload.get("failure_class") or "").strip()
    if failure_class:
        return failure_class
    error_type = str(payload.get("error_type") or "").strip()
    code = str(payload.get("code") or "").strip()
    http_status = str(payload.get("http_status") or "").strip()
    if code == "429" or http_status == "429":
        return "rate_limited"
    if error_type == "ssi_error":
        return "provider_unavailable"
    if error_type:
        return error_type
    return str(payload.get("status") or "unknown")


def parse_tickers(text: str) -> List[str]:
    seen = set()
    tickers: List[str] = []
    for part in (text or "").split(","):
        ticker = part.strip().upper()
        if not ticker or ticker in seen:
            continue
        if not ticker.replace(".", "").replace("-", "").isalnum():
            continue
        seen.add(ticker)
        tickers.append(ticker)
        if len(tickers) >= MAX_TICKERS:
            break
    return tickers


def resolve_date_range(days: int, end_date: Optional[str]) -> Tuple[str, str]:
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    else:
        end = date.today()
    bounded_days = max(1, min(int(days), 370))
    start = end - timedelta(days=bounded_days - 1)
    return format_ssi_date(start) or "", format_ssi_date(end) or ""


def primary_params(ticker: str, from_date: str, to_date: str) -> Dict[str, Any]:
    return {
        "symbol": ticker,
        "fromDate": from_date,
        "toDate": to_date,
        "pageIndex": 1,
        "pageSize": 260,
        "ascending": "true",
    }


def alternate_params(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "Symbol": params.get("symbol"),
        "Fromdate": params.get("fromDate"),
        "Todate": params.get("toDate"),
        "PageIndex": params.get("pageIndex"),
        "PageSize": params.get("pageSize"),
        "ascending": params.get("ascending"),
    }


def normalize_rows(fetcher: SsiFastConnectFetcher, payload: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if isinstance(payload, dict) and str(payload.get("status") or "").lower() in {"unavailable", "disabled"}:
        return [], []
    raw_rows = _extract_rows(payload)
    normalized = [fetcher._map_daily_ohlcv(row) for row in raw_rows]
    normalized = [
        row
        for row in normalized
        if row and _has_required_field(row, ("date", "open", "high", "low", "close", "volume", "value"))
    ]
    return raw_rows, normalized


def summarize_attempt(
    fetcher: SsiFastConnectFetcher,
    *,
    ticker: str,
    shape: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    payload = fetcher._request("DailyOhlc", params=params)
    raw_rows, normalized_rows = normalize_rows(fetcher, payload)
    first_raw = raw_rows[0] if raw_rows else None
    first_normalized = normalized_rows[0] if normalized_rows else None
    diagnostics = payload.get("diagnostics") if isinstance(payload, dict) and isinstance(payload.get("diagnostics"), dict) else {}
    return {
        "endpoint": "DailyOhlc",
        "endpoint_path": "/Market/DailyOhlc",
        "ticker": ticker,
        "shape": shape,
        "params": sanitize_mapping(params),
        "http_status": payload.get("http_status") if isinstance(payload, dict) else None,
        "provider_code": payload.get("code") if isinstance(payload, dict) else None,
        "status": payload.get("status") if isinstance(payload, dict) else None,
        "reason": payload.get("reason") if isinstance(payload, dict) else None,
        "error_type": payload.get("error_type") if isinstance(payload, dict) else None,
        "class": classify_provider_payload(payload if not normalized_rows else {"status": "ok", "rows": normalized_rows}),
        "top_level_keys": sorted(str(key) for key in payload.keys()) if isinstance(payload, dict) else [],
        "candidate_row_list_keys": [
            key for key in ("data", "Data", "items", "Items", "rows", "Rows", "result", "Result")
            if isinstance(payload, dict) and key in payload
        ],
        "raw_rows": len(raw_rows),
        "norm_rows": len(normalized_rows),
        "first_raw_row_keys": sorted(str(key) for key in first_raw.keys()) if isinstance(first_raw, dict) else [],
        "first_normalized_row": sanitize_mapping(first_normalized or {}) if first_normalized else None,
        "diagnostics": sanitize_mapping(diagnostics),
    }


def should_try_alternate(attempt: Dict[str, Any]) -> bool:
    payload = {
        "status": attempt.get("status"),
        "failure_class": attempt.get("class"),
        "error_type": attempt.get("error_type"),
        "code": attempt.get("provider_code"),
        "http_status": attempt.get("http_status"),
    }
    return _should_retry_param_variant(payload)


def diagnose_daily_ohlc(tickers: Iterable[str], days: int, end_date: Optional[str]) -> Dict[str, Any]:
    from_date, to_date = resolve_date_range(days, end_date)
    fetcher = SsiFastConnectFetcher(cache_ttl_seconds=0, request_delay_seconds=0)
    attempts: List[Dict[str, Any]] = []
    stopped_after_rate_limit = False
    for ticker in tickers:
        if stopped_after_rate_limit:
            attempts.append(
                {
                    "endpoint": "DailyOhlc",
                    "ticker": ticker,
                    "shape": "primary",
                    "status": "skipped",
                    "class": "skipped_after_429",
                    "raw_rows": None,
                    "norm_rows": None,
                    "notes": "Skipped to avoid repeated SSI DailyOhlc probes after provider rate limit.",
                }
            )
            continue
        params = primary_params(ticker, from_date, to_date)
        primary = summarize_attempt(fetcher, ticker=ticker, shape="primary", params=params)
        attempts.append(primary)
        if primary.get("class") == "rate_limited":
            stopped_after_rate_limit = True
            continue
        if primary.get("norm_rows"):
            continue
        if should_try_alternate(primary):
            alternate = summarize_attempt(fetcher, ticker=ticker, shape="alternate", params=alternate_params(params))
            attempts.append(alternate)
            if alternate.get("class") == "rate_limited":
                stopped_after_rate_limit = True
        else:
            attempts.append(
                {
                    "endpoint": "DailyOhlc",
                    "ticker": ticker,
                    "shape": "alternate",
                    "status": "skipped",
                    "class": "skipped",
                    "raw_rows": None,
                    "norm_rows": None,
                    "notes": "Alternate shape skipped because primary response was not a retryable SSI provider error.",
                }
            )
    conclusion = conclude(attempts)
    return {
        "date_range": {"from": from_date, "to": to_date, "days": days},
        "attempts": attempts,
        "conclusion": conclusion,
    }


def conclude(attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
    if any((attempt.get("norm_rows") or 0) > 0 for attempt in attempts):
        return {
            "classification": "daily_ohlc_available",
            "message": "DailyOhlc returned normalized rows for at least one bounded attempt.",
        }
    classes = {str(attempt.get("class") or "") for attempt in attempts}
    if "rate_limited" in classes or "skipped_after_429" in classes:
        return {
            "classification": "provider_rate_limited",
            "message": "DailyOhlc hit SSI provider rate limiting before usable rows were returned.",
        }
    if "provider_unavailable" in classes:
        return {
            "classification": "provider_unavailable",
            "message": "DailyOhlc returned SSI provider errors without usable rows.",
        }
    return {
        "classification": "daily_ohlc_unavailable",
        "message": "DailyOhlc did not return usable rows in the bounded diagnostic.",
    }


def backend_summary(backend_url: str, tickers: List[str]) -> Dict[str, Any]:
    base = backend_url.rstrip("/")
    joined = ",".join(tickers)
    result: Dict[str, Any] = {"backend_url": base}
    try:
        watchlist = requests.get(
            f"{base}/api/v1/stocks/vn/watchlist",
            params={"tickers": joined, "include_intraday": "false"},
            timeout=20,
        ).json()
        result["watchlist"] = [
            {
                "ticker": row.get("ticker"),
                "status": row.get("status"),
                "reason": row.get("reason"),
                "rows_loaded": row.get("rows_loaded"),
                "latest_price": row.get("latest_price"),
                "latest_price_source": row.get("latest_price_source"),
                "error": row.get("error"),
                "daily_stock_price_status": (row.get("daily_stock_price") or {}).get("status"),
            }
            for row in watchlist.get("watchlist", [])
            if isinstance(row, dict)
        ]
    except Exception as exc:  # pragma: no cover - network/backend dependent
        result["watchlist_error"] = str(type(exc).__name__)
    try:
        realtime = requests.get(
            f"{base}/api/v1/stocks/vn/realtime",
            params={"tickers": tickers[0] if tickers else "FPT"},
            timeout=20,
        ).json()
        result["realtime"] = {
            key: realtime.get(key)
            for key in ("status", "source", "reason_code", "classification", "streaming_status", "runtime_status")
        }
    except Exception as exc:  # pragma: no cover - network/backend dependent
        result["realtime_error"] = str(type(exc).__name__)
    try:
        components = requests.get(
            f"{base}/api/v1/stocks/vn/index-components",
            params={"index_code": "VN30"},
            timeout=20,
        ).json()
        result["index_components"] = {
            key: components.get(key)
            for key in ("status", "source", "index_code", "count", "fallback_used", "reason")
        }
    except Exception as exc:  # pragma: no cover - network/backend dependent
        result["index_components_error"] = str(type(exc).__name__)
    return sanitize_mapping(result)


def print_table(attempts: List[Dict[str, Any]]) -> None:
    print("Endpoint   Ticker  Shape      HTTP  ProviderCode  RawRows  NormRows  Class")
    for attempt in attempts:
        print(
            f"{attempt.get('endpoint', ''):<10} "
            f"{attempt.get('ticker', ''):<7} "
            f"{attempt.get('shape', ''):<10} "
            f"{str(attempt.get('http_status') or '-'):<5} "
            f"{str(attempt.get('provider_code') or '-'):<13} "
            f"{str(attempt.get('raw_rows') if attempt.get('raw_rows') is not None else '-'):<7} "
            f"{str(attempt.get('norm_rows') if attempt.get('norm_rows') is not None else '-'):<8} "
            f"{attempt.get('class', '')}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose SSI DailyOhlc with bounded, secret-safe probes.")
    parser.add_argument("--tickers", default="FPT,ACB,SSI,VCB", help="Comma-separated VN tickers, capped at 10.")
    parser.add_argument("--days", type=int, default=30, help="Calendar-day window, capped at 370.")
    parser.add_argument("--end-date", help="Optional end date in YYYY-MM-DD.")
    parser.add_argument("--backend-url", help="Optional local backend URL for public contract comparison.")
    parser.add_argument("--output-json", help="Optional path for sanitized JSON output.")
    args = parser.parse_args()

    tickers = parse_tickers(args.tickers)
    if not tickers:
        raise SystemExit("No valid tickers supplied.")

    result = diagnose_daily_ohlc(tickers, args.days, args.end_date)
    if args.backend_url:
        result["backend"] = backend_summary(args.backend_url, tickers)

    print_table(result["attempts"])
    print()
    print("Conclusion:", result["conclusion"]["classification"], "-", result["conclusion"]["message"])

    if args.output_json:
        path = Path(args.output_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sanitize_value(result), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Sanitized JSON written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
