# -*- coding: utf-8 -*-
"""Safe local SSI FastConnect FC Data smoke and endpoint probe.

The script reads environment variables only and prints status/counts. It never
prints tokens, consumer credentials, headers, or full provider response bodies.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from data_provider.ssi_fastconnect_fetcher import (  # noqa: E402
    DEFAULT_BASE_URL,
    SsiFastConnectFetcher,
    _extract_rows,
    _first_value,
    format_ssi_date,
)

BASE_URLS_TO_PROBE = (
    ("api/v2", "https://fc-data.ssi.com.vn/api/v2/Market"),
    ("v2.0", "https://fc-data.ssi.com.vn/v2.0/Market"),
)
PROBE_DELAY_SECONDS = 1.15
DAILY_STOCK_PRICE_MEANINGFUL = (
    "TradingDate",
    "RefPrice",
    "CeilingPrice",
    "FloorPrice",
    "OpenPrice",
    "ClosePrice",
    "TotalVol",
    "TotalVal",
)
DAILY_INDEX_MEANINGFUL = (
    "IndexId",
    "IndexID",
    "IndexValue",
    "TradingDate",
    "RatioChange",
    "TotalMatchVol",
    "Advances",
    "Declines",
)
SENSITIVE_MARKERS = (
    "accesstoken",
    "access_token",
    "authorization",
    "bearer",
    "consumerid",
    "consumer_id",
    "consumersecret",
    "consumer_secret",
)


def _count_rows(payload: Dict[str, Any]) -> int:
    rows = payload.get("rows")
    return len(rows) if isinstance(rows, list) else 0


def _rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    value = payload.get("rows")
    return value if isinstance(value, list) else []


def _safe_keys(payload: Dict[str, Any]) -> List[str]:
    for row in _rows(payload):
        if isinstance(row, dict):
            return sorted(str(key) for key in row.keys())
    return []


def _date_span(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    dates = [row.get("date") for row in _rows(payload) if isinstance(row, dict) and row.get("date")]
    if not dates:
        return None, None
    return min(dates), max(dates)


def _first_market(payload: Dict[str, Any]) -> Optional[str]:
    for row in _rows(payload):
        if not isinstance(row, dict):
            continue
        market = row.get("market") or row.get("exchange")
        if market:
            return str(market).strip().upper()
    return None


def _index_codes(payload: Dict[str, Any]) -> List[str]:
    codes: List[str] = []
    seen = set()
    for row in _rows(payload):
        if not isinstance(row, dict):
            continue
        value = row.get("index_id") or row.get("index_code")
        if not value:
            continue
        code = str(value).strip().upper()
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def _choose_index_code(codes: List[str]) -> Optional[str]:
    for preferred in ("VNINDEX", "VN30"):
        for code in codes:
            if preferred == code or preferred in code:
                return code
    return codes[0] if codes else None


def _date_range() -> Tuple[str, str]:
    return (
        format_ssi_date(date.today() - timedelta(days=365)) or "",
        format_ssi_date(date.today()) or "",
    )


def _meaningful_raw_rows(rows: List[Dict[str, Any]], keys: Tuple[str, ...]) -> List[Dict[str, Any]]:
    if not keys:
        return rows
    return [row for row in rows if any(_first_value(row, key) not in (None, "") for key in keys)]


def _normalized_probe_rows(fetcher: SsiFastConnectFetcher, endpoint: str, rows: List[Dict[str, Any]], target: str = "") -> List[Dict[str, Any]]:
    if endpoint == "DailyStockPrice":
        raw_rows = _meaningful_raw_rows(rows, DAILY_STOCK_PRICE_MEANINGFUL)
        return [fetcher._map_daily_stock_price(row) for row in raw_rows]
    if endpoint == "DailyIndex":
        raw_rows = _meaningful_raw_rows(rows, DAILY_INDEX_MEANINGFUL)
        return [fetcher._map_daily_index(row, target) for row in raw_rows]
    if endpoint == "DailyOhlc":
        return [fetcher._map_daily_ohlcv(row) for row in rows]
    if endpoint == "IndexList":
        return [
            row
            for row in (fetcher._map_index_info(row) for row in rows)
            if row and (row.get("index_id") or row.get("index_code"))
        ]
    return rows


def _data_summary(payload: Any) -> Tuple[str, int, List[str]]:
    if not isinstance(payload, dict):
        return type(payload).__name__, 0, []
    data = payload.get("data", payload.get("Data"))
    if isinstance(data, list):
        first_keys = sorted(str(key) for key in data[0].keys()) if data and isinstance(data[0], dict) else []
        return "list", len(data), first_keys
    if isinstance(data, dict):
        nested = _extract_rows(data)
        first_keys = sorted(str(key) for key in nested[0].keys()) if nested else sorted(str(key) for key in data.keys())
        return "dict", len(nested), first_keys
    if data is None:
        return "missing", 0, []
    return type(data).__name__, 0, []


def _redact_text(value: Any, redactions: Tuple[Optional[str], ...] = ()) -> str:
    text = str(value).replace("\n", " ")
    for secret in redactions:
        if secret:
            text = text.replace(str(secret), "[redacted]")
    lowered = text.lower()
    if any(marker in lowered for marker in SENSITIVE_MARKERS):
        return "[redacted]"
    return text[:120]


def _safe_message(payload: Any, redactions: Tuple[Optional[str], ...] = ()) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    value = payload.get("message", payload.get("Message"))
    if value in (None, ""):
        return None
    return _redact_text(value, redactions)


def _status_field(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    value = payload.get("status", payload.get("Status"))
    return None if value in (None, "") else str(value)


def _total_record(payload: Any) -> Optional[Any]:
    if not isinstance(payload, dict):
        return None
    for key in ("totalRecord", "TotalRecord", "totalRecords", "TotalRecords"):
        if key in payload:
            return payload.get(key)
    data = payload.get("data", payload.get("Data"))
    if isinstance(data, dict):
        for key in ("totalRecord", "TotalRecord", "totalRecords", "TotalRecords"):
            if key in data:
                return data.get(key)
    return None


def _raw_probe(
    fetcher: SsiFastConnectFetcher,
    endpoint: str,
    params: Dict[str, Any],
) -> Tuple[Optional[int], Any]:
    if not fetcher._has_credentials():
        return None, {"status": "unavailable", "message": "credentials missing"}
    token_result = fetcher.get_access_token()
    if token_result.get("status") != "ok":
        return None, {"status": "unavailable", "message": "auth unavailable"}
    try:
        response = fetcher.session.get(
            f"{fetcher.base_url}/{endpoint}",
            params=params,
            headers={"Authorization": f"Bearer {fetcher._access_token}"},
            timeout=fetcher.timeout_seconds,
        )
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.RequestException):
        return None, {"status": "unavailable", "message": "request failed"}
    try:
        return response.status_code, response.json()
    except (TypeError, ValueError):
        return response.status_code, {"status": "unavailable", "message": "invalid json"}


def _probe_endpoint(
    fetcher: SsiFastConnectFetcher,
    *,
    base_label: str,
    endpoint: str,
    params: Dict[str, Any],
    target: str = "",
) -> Dict[str, Any]:
    http_status, payload = _raw_probe(fetcher, endpoint, params)
    rows = _extract_rows(payload)
    normalized = _normalized_probe_rows(fetcher, endpoint, rows, target=target)
    normalized = [row for row in normalized if row]
    data_type, data_length, first_row_keys = _data_summary(payload)
    normalized_keys = sorted(str(key) for key in normalized[0].keys()) if normalized else []
    redactions = (fetcher._access_token, fetcher.consumer_id, fetcher.consumer_secret)
    result = {
        "endpoint": endpoint,
        "base_url": base_label,
        "param_keys": sorted(params.keys()),
        "http_status": http_status,
        "top_level_keys": sorted(str(key) for key in payload.keys()) if isinstance(payload, dict) else [],
        "status_field": _status_field(payload),
        "message_field": _safe_message(payload, redactions),
        "totalRecord": _total_record(payload),
        "data_type": data_type,
        "data_length": data_length,
        "first_data_row_keys": first_row_keys,
        "normalized_row_count": len(normalized),
        "normalized_keys": normalized_keys,
    }
    if endpoint == "IndexList":
        mapped = [
            row
            for row in (fetcher._map_index_info(row) for row in rows)
            if row and (row.get("index_id") or row.get("index_code"))
        ]
        result["index_codes"] = _index_codes({"rows": mapped})
    return result


def _print_probe_result(result: Dict[str, Any]) -> None:
    print(f"endpoint: {result['endpoint']}")
    print(f"base_url: {result['base_url']}")
    print(f"param keys: {result['param_keys']}")
    print(f"HTTP status: {result['http_status']}")
    print(f"top-level response keys: {result['top_level_keys']}")
    print(f"status field: {result['status_field']}")
    print(f"message field: {result['message_field']}")
    print(f"totalRecord: {result['totalRecord']}")
    print(f"data type: {result['data_type']}")
    print(f"data length: {result['data_length']}")
    print(f"first data row keys: {result['first_data_row_keys']}")
    if "index_codes" in result:
        print(f"index codes: {result['index_codes']}")
    print(f"normalized row count: {result['normalized_row_count']}")
    print(f"normalized keys: {result['normalized_keys']}")


def _probe_specs(from_date: str, to_date: str) -> List[Tuple[str, Dict[str, Any], str]]:
    specs: List[Tuple[str, Dict[str, Any], str]] = []
    short_from_date = format_ssi_date(date.today() - timedelta(days=29)) or from_date
    for market in ("HOSE", "hose", "HSX", "HO"):
        specs.append((
            "DailyStockPrice",
            {
                "symbol": "FPT",
                "market": market,
                "Fromdate": from_date,
                "Todate": to_date,
                "pageIndex": 1,
                "pageSize": 1000,
            },
            "FPT",
        ))
        specs.append((
            "DailyStockPrice",
            {
                "Symbol": "FPT",
                "Market": market,
                "Fromdate": from_date,
                "Todate": to_date,
                "pageIndex": 1,
                "pageSize": 1000,
            },
            "FPT",
        ))
    specs.append((
        "DailyStockPrice",
        {
            "symbol": "FPT",
            "market": "HOSE",
            "Fromdate": short_from_date,
            "Todate": to_date,
            "pageIndex": 1,
            "pageSize": 1000,
        },
        "FPT",
    ))
    specs.append((
        "DailyStockPrice",
        {
            "symbol": "SSI",
            "market": "HOSE",
            "Fromdate": "19/07/2023",
            "Todate": "19/07/2023",
            "pageIndex": 1,
            "pageSize": 10,
        },
        "SSI",
    ))
    for exchange in ("HOSE", "HNX", "UPCOM"):
        specs.append(("IndexList", {"exchange": exchange}, exchange))
    specs.append((
        "DailyIndex",
        {
            "indexID": "HNX30",
            "Fromdate": "14/08/2023",
            "Todate": "14/08/2023",
            "pageIndex": 1,
            "pageSize": 10,
        },
        "HNX30",
    ))
    specs.append((
        "DailyIndex",
        {
            "indexID": "VN30",
            "Fromdate": from_date,
            "Todate": to_date,
            "pageIndex": 1,
            "pageSize": 1000,
        },
            "VN30",
        ))
    specs.append((
        "DailyIndex",
        {
            "indexID": "VN30",
            "Fromdate": short_from_date,
            "Todate": to_date,
            "pageIndex": 1,
            "pageSize": 1000,
        },
        "VN30",
    ))
    for key in ("IndexId", "IndexID", "indexId"):
        specs.append((
            "DailyIndex",
            {
                key: "VN30",
                "Fromdate": from_date,
                "Todate": to_date,
                "pageIndex": 1,
                "pageSize": 1000,
            },
            "VN30",
        ))
    return specs


def _run_probe() -> int:
    from_date, to_date = _date_range()
    print(f"Date range: {from_date} -> {to_date}")
    for base_label, base_url in BASE_URLS_TO_PROBE:
        fetcher = SsiFastConnectFetcher(base_url=base_url, cache_ttl_seconds=0)
        token_status = fetcher.get_access_token()
        print(f"AccessToken {base_label}: {'OK' if token_status.get('status') == 'ok' else 'Unavailable'}")
        if token_status.get("status") != "ok":
            continue
        for endpoint, params, target in _probe_specs(from_date, to_date):
            _print_probe_result(_probe_endpoint(fetcher, base_label=base_label, endpoint=endpoint, params=params, target=target))
            time.sleep(PROBE_DELAY_SECONDS)
    return 0


def _run_smoke() -> int:
    fetcher = SsiFastConnectFetcher(request_delay_seconds=PROBE_DELAY_SECONDS)
    print(f"SSI enabled: {str(fetcher.is_enabled()).lower()}")

    token_status = fetcher.get_access_token()
    print(f"AccessToken: {'OK' if token_status.get('status') == 'ok' else 'Unavailable'}")
    if token_status.get("status") != "ok":
        return 0

    from_date, to_date = _date_range()
    print(f"Date range: {from_date} -> {to_date}")

    daily_ohlc = fetcher.get_daily_ohlcv("FPT", from_date=from_date, to_date=to_date, limit=1000)
    print(f"DailyOhlc FPT rows: {_count_rows(daily_ohlc)}")
    print(f"DailyOhlc keys: {_safe_keys(daily_ohlc)}")
    first_date, last_date = _date_span(daily_ohlc)
    print(f"DailyOhlc date span: {first_date} -> {last_date}")

    time.sleep(PROBE_DELAY_SECONDS)
    daily_stock_price = fetcher.get_daily_stock_price("FPT", market="HOSE", from_date=from_date, to_date=to_date, limit=1000)
    if _count_rows(daily_stock_price) == 0:
        details = fetcher.get_securities_details("FPT", market="HOSE")
        inferred_market = _first_market(details)
        if inferred_market and inferred_market != "HOSE":
            daily_stock_price = fetcher.get_daily_stock_price(
                "FPT",
                market=inferred_market,
                from_date=from_date,
                to_date=to_date,
                limit=1000,
            )
    print(f"DailyStockPrice FPT rows: {_count_rows(daily_stock_price)}")
    print(f"DailyStockPrice chunks: {daily_stock_price.get('chunks_used')}")
    print(f"DailyStockPrice keys: {_safe_keys(daily_stock_price)}")
    first_date, last_date = _date_span(daily_stock_price)
    print(f"DailyStockPrice date span: {first_date} -> {last_date}")

    time.sleep(PROBE_DELAY_SECONDS)
    index_list = fetcher.get_index_list("HOSE")
    codes = _index_codes(index_list)
    print(f"IndexList HOSE rows: {_count_rows(index_list)}")
    print(f"Index codes: {codes}")

    time.sleep(PROBE_DELAY_SECONDS)
    selected_index = _choose_index_code(codes)
    daily_index = (
        fetcher.get_daily_index(selected_index, from_date=from_date, to_date=to_date, limit=1000)
        if selected_index
        else {"rows": []}
    )
    print(f"DailyIndex {selected_index or 'unavailable'} rows: {_count_rows(daily_index)}")
    print(f"DailyIndex chunks: {daily_index.get('chunks_used')}")
    print(f"DailyIndex keys: {_safe_keys(daily_index)}")
    first_date, last_date = _date_span(daily_index)
    print(f"DailyIndex date span: {first_date} -> {last_date}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Safe SSI FastConnect smoke/probe")
    parser.add_argument("--probe", action="store_true", help="Print safe endpoint metadata for selected SSI probes.")
    args = parser.parse_args(argv)
    return _run_probe() if args.probe else _run_smoke()


if __name__ == "__main__":
    raise SystemExit(main())
