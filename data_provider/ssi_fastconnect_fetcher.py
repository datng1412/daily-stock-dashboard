# -*- coding: utf-8 -*-
"""SSI FastConnect FC Data foundation provider.

This adapter is intentionally standalone for the first transition phase. It
does not replace Mozyfin daily data, KBS realtime snapshots, or dashboard
``latest_price`` semantics.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.config import get_config, parse_env_bool, parse_env_int


SSI_SOURCE = "SSI"
DEFAULT_BASE_URL = "https://fc-data.ssi.com.vn/api/v2/Market"
DISABLED_REASON = "SSI FastConnect disabled"
MISSING_CREDENTIALS_REASON = "SSI FastConnect credentials missing"
REQUEST_FAILED_REASON = "SSI FastConnect request failed"
SSI_CHUNK_MAX_DAYS = 29
SSI_PAGE_SIZE = 1000
SSI_MAX_PAGES = 20


def format_ssi_date(value: Any) -> Optional[str]:
    """Format a date-like value as the dd/mm/yyyy string expected by SSI FC Data."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")

    text = str(value).strip()
    if not text:
        return None
    if "/" in text and len(text.split("/")) == 3:
        return text

    parsed = _parse_date(text)
    if not parsed:
        return text
    try:
        return datetime.strptime(parsed, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return text


def _date_from_value(value: Any) -> Optional[date]:
    parsed = _parse_date(value)
    if not parsed:
        return None
    try:
        return datetime.strptime(parsed, "%Y-%m-%d").date()
    except ValueError:
        return None


def build_ssi_date_windows(
    from_date: Optional[Any],
    to_date: Optional[Any],
    *,
    max_days: int = SSI_CHUNK_MAX_DAYS,
) -> List[Tuple[str, str]]:
    """Return inclusive SSI date windows capped for endpoints with 30-day limits."""
    end = _date_from_value(to_date) if to_date else date.today()
    if end is None:
        end = date.today()
    today = date.today()
    if end > today:
        end = today

    start = _date_from_value(from_date) if from_date else end - timedelta(days=370)
    if start is None:
        start = end - timedelta(days=370)
    if start > end:
        start = end

    window_span = max(0, min(int(max_days), SSI_CHUNK_MAX_DAYS) - 1)
    windows: List[Tuple[str, str]] = []
    current = start
    while current <= end:
        window_end = min(current + timedelta(days=window_span), end)
        windows.append((format_ssi_date(current) or "", format_ssi_date(window_end) or ""))
        current = window_end + timedelta(days=1)
    return windows


@dataclass
class _CacheEntry:
    value: Dict[str, Any]
    expires_at: float


def _unavailable(reason: str) -> Dict[str, str]:
    return {
        "status": "unavailable",
        "source": SSI_SOURCE,
        "reason": reason,
    }


def _clean_key(key: Any) -> str:
    return "".join(ch for ch in str(key or "").strip().lower() if ch.isalnum())


def _first_value(row: Dict[str, Any], *keys: str) -> Any:
    normalized = {_clean_key(k): v for k, v in row.items()}
    for key in keys:
        value = normalized.get(_clean_key(key))
        if value not in (None, ""):
            return value
    return None


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        text = str(value).strip().replace(",", "")
        if text.lower() in {"nan", "none", "null"} or text in {"-", "--"}:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    numeric = _to_float(value)
    return int(numeric) if numeric is not None else None


def _net_value(row: Dict[str, Any], net_key: Tuple[str, ...], buy: Any, sell: Any) -> Optional[float]:
    direct = _to_float(_first_value(row, *net_key))
    if direct is not None:
        return direct
    buy_value = _to_float(buy)
    sell_value = _to_float(sell)
    if buy_value is None or sell_value is None:
        return None
    return buy_value - sell_value


def _parse_date(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()

    text = str(value).strip()
    if not text:
        return None

    try:
        numeric = float(text)
    except ValueError:
        numeric = None
    if numeric is not None:
        if numeric > 1_000_000_000_000:
            return datetime.fromtimestamp(numeric / 1000, tz=timezone.utc).date().isoformat()
        if numeric > 1_000_000_000:
            return datetime.fromtimestamp(numeric, tz=timezone.utc).date().isoformat()
        if text.isdigit() and len(text) == 8:
            try:
                return datetime.strptime(text, "%Y%m%d").date().isoformat()
            except ValueError:
                return None

    normalized = text.replace("Z", "+00:00")
    if "T" in normalized:
        try:
            return datetime.fromisoformat(normalized).date().isoformat()
        except ValueError:
            pass
    if " " in normalized:
        normalized = normalized.split(" ", 1)[0]

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(normalized, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _extract_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("data", "Data", "items", "Items", "rows", "Rows", "result", "Result"):
        value = payload.get(key)
        if isinstance(value, list):
            return [dict(row) for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            nested = _extract_rows(value)
            if nested:
                return nested
    return [payload] if payload else []


def _total_record(payload: Any) -> Optional[int]:
    if not isinstance(payload, dict):
        return None
    for key in ("totalRecord", "TotalRecord", "totalRecords", "TotalRecords"):
        value = _to_int(payload.get(key))
        if value is not None:
            return value
    data = payload.get("data") or payload.get("Data")
    if isinstance(data, dict):
        for key in ("totalRecord", "TotalRecord", "totalRecords", "TotalRecords"):
            value = _to_int(data.get(key))
            if value is not None:
                return value
    return None


def _has_required_field(row: Dict[str, Any], fields: Tuple[str, ...]) -> bool:
    if not fields:
        return True
    return any(row.get(field) not in (None, "") for field in fields)


def _has_ssi_error(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    status = str(payload.get("status") or payload.get("Status") or "").strip().lower()
    message = str(payload.get("message") or payload.get("Message") or "").strip().lower()
    success = payload.get("success", payload.get("Success"))
    code = str(payload.get("code") or payload.get("Code") or "").strip()
    if status in {"error", "failed", "fail", "unavailable"}:
        return True
    if status and status not in {"success", "ok", "0", "200"}:
        return True
    if isinstance(success, bool) and not success:
        return True
    if code and code not in {"0", "200", "OK", "ok"} and any(token in message for token in ("error", "fail")):
        return True
    return False


def _token_from_payload(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    candidates: List[Dict[str, Any]] = [payload]
    data = payload.get("data") or payload.get("Data")
    if isinstance(data, dict):
        candidates.append(data)
    for item in candidates:
        for key in ("accessToken", "AccessToken", "access_token", "token", "Token"):
            value = item.get(key)
            if value:
                return str(value)
    return None


def _expiry_from_payload(payload: Any, default_ttl_seconds: int) -> float:
    now = time.time()
    candidates: List[Dict[str, Any]] = [payload] if isinstance(payload, dict) else []
    data = payload.get("data") or payload.get("Data") if isinstance(payload, dict) else None
    if isinstance(data, dict):
        candidates.append(data)

    for item in candidates:
        for key in ("expiresIn", "expires_in", "expireIn", "ttl", "TTL"):
            ttl = _to_int(item.get(key))
            if ttl is not None and ttl > 0:
                return now + ttl
        for key in ("expiresAt", "expires_at", "expireTime", "expiration"):
            value = item.get(key)
            numeric = _to_float(value)
            if numeric is not None:
                if numeric > 1_000_000_000_000:
                    return numeric / 1000
                if numeric > 1_000_000_000:
                    return numeric
            if value:
                try:
                    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
                except ValueError:
                    continue
    return now + default_ttl_seconds


class SsiFastConnectFetcher:
    """Small FC Data client with secret-safe failures and row normalization."""

    def __init__(
        self,
        *,
        enabled: Optional[bool] = None,
        base_url: Optional[str] = None,
        consumer_id: Optional[str] = None,
        consumer_secret: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        cache_ttl_seconds: Optional[int] = None,
        token_ttl_seconds: Optional[int] = None,
        request_delay_seconds: float = 0,
        session: Optional[requests.Session] = None,
        config: Any = None,
    ) -> None:
        if config is None:
            try:
                config = get_config()
            except Exception:
                config = None

        self.enabled = (
            bool(enabled)
            if enabled is not None
            else bool(getattr(config, "ssi_fastconnect_enabled", parse_env_bool(os.getenv("SSI_FASTCONNECT_ENABLED"), default=False)))
        )
        self.base_url = (
            base_url
            or getattr(config, "ssi_fastconnect_base_url", None)
            or os.getenv("SSI_FASTCONNECT_BASE_URL")
            or DEFAULT_BASE_URL
        ).strip().rstrip("/")
        self.consumer_id = (
            consumer_id
            if consumer_id is not None
            else getattr(config, "ssi_fastconnect_consumer_id", None)
            or os.getenv("SSI_FASTCONNECT_CONSUMER_ID")
            or ""
        ).strip()
        self.consumer_secret = (
            consumer_secret
            if consumer_secret is not None
            else getattr(config, "ssi_fastconnect_consumer_secret", None)
            or os.getenv("SSI_FASTCONNECT_CONSUMER_SECRET")
            or ""
        ).strip()
        self.timeout_seconds = int(
            timeout_seconds
            if timeout_seconds is not None
            else getattr(config, "ssi_fastconnect_timeout_seconds", None)
            or parse_env_int(os.getenv("SSI_FASTCONNECT_TIMEOUT_SECONDS"), 10, field_name="SSI_FASTCONNECT_TIMEOUT_SECONDS", minimum=1)
        )
        self.cache_ttl_seconds = int(
            cache_ttl_seconds
            if cache_ttl_seconds is not None
            else getattr(config, "ssi_fastconnect_cache_ttl_seconds", None)
            or parse_env_int(os.getenv("SSI_FASTCONNECT_CACHE_TTL_SECONDS"), 300, field_name="SSI_FASTCONNECT_CACHE_TTL_SECONDS", minimum=0)
        )
        self.token_ttl_seconds = int(
            token_ttl_seconds
            if token_ttl_seconds is not None
            else getattr(config, "ssi_fastconnect_token_ttl_seconds", None)
            or parse_env_int(os.getenv("SSI_FASTCONNECT_TOKEN_TTL_SECONDS"), 900, field_name="SSI_FASTCONNECT_TOKEN_TTL_SECONDS", minimum=1)
        )
        self.session = session or requests.Session()
        self.request_delay_seconds = max(0.0, float(request_delay_seconds or 0))
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._cache: Dict[Tuple[str, Tuple[Tuple[str, Any], ...]], _CacheEntry] = {}

    def is_enabled(self) -> bool:
        return self.enabled

    def health_check(self) -> Dict[str, Any]:
        if not self.enabled:
            return _unavailable(DISABLED_REASON)
        if not self._has_credentials():
            return _unavailable(MISSING_CREDENTIALS_REASON)
        token_result = self.get_access_token()
        if token_result.get("status") != "ok":
            return token_result
        return {
            "status": "ok",
            "source": SSI_SOURCE,
            "auth": "ok",
        }

    def get_access_token(self) -> Dict[str, Any]:
        if not self.enabled:
            return _unavailable(DISABLED_REASON)
        if not self._has_credentials():
            return _unavailable(MISSING_CREDENTIALS_REASON)
        if self._access_token and self._token_expires_at > time.time() + 5:
            return {
                "status": "ok",
                "source": SSI_SOURCE,
                "cached": True,
                "expires_at": datetime.fromtimestamp(self._token_expires_at, tz=timezone.utc).isoformat(),
            }

        try:
            response = self.session.post(
                f"{self.base_url}/AccessToken",
                json={
                    "consumerID": self.consumer_id,
                    "consumerSecret": self.consumer_secret,
                },
                timeout=self.timeout_seconds,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.RequestException):
            return _unavailable(REQUEST_FAILED_REASON)

        payload = self._parse_response(response)
        if isinstance(payload, dict) and payload.get("status") == "unavailable":
            return payload

        token = _token_from_payload(payload)
        if not token:
            return _unavailable(REQUEST_FAILED_REASON)

        self._access_token = token
        self._token_expires_at = _expiry_from_payload(payload, self.token_ttl_seconds)
        return {
            "status": "ok",
            "source": SSI_SOURCE,
            "cached": False,
            "expires_at": datetime.fromtimestamp(self._token_expires_at, tz=timezone.utc).isoformat(),
        }

    def get_daily_ohlcv(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
    ) -> Dict[str, Any]:
        params = self._date_params({"symbol": symbol.strip().upper()}, from_date, to_date, limit)
        return self._cached_normalized(
            "DailyOhlc",
            params,
            limit,
            lambda row: self._map_daily_ohlcv(row),
            extra={"symbol": symbol.strip().upper()},
            param_variants=[self._alternate_param_case(params)],
            required_any=("date", "open", "high", "low", "close", "volume", "value"),
        )

    def get_daily_stock_price(
        self,
        symbol: str,
        market: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
    ) -> Dict[str, Any]:
        normalized_market = market.strip().upper() if market else None
        params: Dict[str, Any] = {"symbol": symbol.strip().upper()}
        if normalized_market:
            params["market"] = normalized_market
        required_any = (
            "date",
            "reference_price",
            "ceiling_price",
            "floor_price",
            "open",
            "high",
            "low",
            "close",
            "matched_volume",
            "matched_value",
            "total_volume",
            "total_value",
        )
        return self._cached_chunked_normalized(
            "DailyStockPrice",
            params,
            from_date,
            to_date,
            limit,
            lambda row: self._map_daily_stock_price(row),
            extra={"symbol": symbol.strip().upper(), "market": params.get("market")},
            base_param_variants=self._daily_stock_price_base_param_variants(params, normalized_market),
            required_any=required_any,
            dedupe_fields=("date",),
        )

    def get_daily_index(
        self,
        index_code: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
    ) -> Dict[str, Any]:
        normalized_index = index_code.strip().upper()
        params = {"indexID": normalized_index}
        return self._cached_chunked_normalized(
            "DailyIndex",
            params,
            from_date,
            to_date,
            limit,
            lambda row: self._map_daily_index(row, normalized_index),
            extra={"index_code": normalized_index},
            required_any=("date", "index_value", "change", "change_pct", "total_volume", "total_value"),
            base_param_variants=[self._alternate_param_case(params)],
            dedupe_fields=("index_code", "date"),
        )

    def get_index_list(self, market: Optional[str] = None) -> Dict[str, Any]:
        params = {"market": market.strip().upper()} if market else {}
        return self._cached_normalized(
            "IndexList",
            params,
            0,
            self._map_index_info,
            extra={"market": params.get("market")},
            param_variants=[self._alternate_param_case(params)] if params else None,
            required_any=("index_id", "index_code"),
        )

    def get_securities(self, market: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"pageIndex": 1, "pageSize": 1000}
        if market:
            params["market"] = market.strip().upper()
        return self._cached_normalized(
            "Securities",
            params,
            0,
            self._map_security,
            extra={"market": params.get("market")},
            param_variants=[self._alternate_param_case(params)] if params else None,
            required_any=("symbol", "name", "name_en", "exchange", "market"),
        )

    def get_securities_details(
        self,
        symbol: Optional[str] = None,
        market: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"pageIndex": 1, "pageSize": 1000}
        if symbol:
            params["symbol"] = symbol.strip().upper()
        if market:
            params["market"] = market.strip().upper()
        return self._cached_normalized(
            "SecuritiesDetails",
            params,
            0,
            self._map_security,
            extra={"symbol": params.get("symbol"), "market": params.get("market")},
            param_variants=[self._alternate_param_case(params)] if params else None,
            required_any=("symbol", "name", "name_en", "exchange", "market"),
        )

    def _has_credentials(self) -> bool:
        return bool(self.consumer_id and self.consumer_secret)

    def _date_params(
        self,
        params: Dict[str, Any],
        from_date: Optional[str],
        to_date: Optional[str],
        limit: int,
        *,
        documented_date_case: bool = False,
    ) -> Dict[str, Any]:
        if not to_date:
            to_date = format_ssi_date(date.today())
        if not from_date:
            from_date = format_ssi_date(date.today() - timedelta(days=370))
        from_key = "Fromdate" if documented_date_case else "fromDate"
        to_key = "Todate" if documented_date_case else "toDate"
        if from_date:
            params[from_key] = format_ssi_date(from_date)
        if to_date:
            params[to_key] = format_ssi_date(to_date)
        params["pageIndex"] = 1
        if limit:
            params["pageSize"] = int(limit)
        params["ascending"] = "true"
        return params

    @staticmethod
    def _alternate_param_case(params: Dict[str, Any]) -> Dict[str, Any]:
        key_map = {
            "symbol": "Symbol",
            "market": "Market",
            "fromDate": "Fromdate",
            "toDate": "Todate",
            "Fromdate": "fromDate",
            "Todate": "toDate",
            "indexID": "IndexId",
        }
        return {key_map.get(key, key): value for key, value in params.items()}

    def _daily_stock_price_param_variants(
        self,
        params: Dict[str, Any],
        market: Optional[str],
    ) -> List[Dict[str, Any]]:
        variants = [self._alternate_param_case(params)]
        if market == "HOSE":
            for alias in ("HSX", "HO"):
                alias_params = dict(params)
                alias_params["market"] = alias
                variants.append(alias_params)
                variants.append(self._alternate_param_case(alias_params))
        return variants

    def _daily_stock_price_base_param_variants(
        self,
        params: Dict[str, Any],
        market: Optional[str],
    ) -> List[Dict[str, Any]]:
        variants = [self._alternate_param_case(params)]
        if market == "HOSE":
            for alias in ("HSX", "HO"):
                alias_params = dict(params)
                alias_params["market"] = alias
                variants.append(alias_params)
                variants.append(self._alternate_param_case(alias_params))
        return variants

    def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if not self.enabled:
            return _unavailable(DISABLED_REASON)
        if not self._has_credentials():
            return _unavailable(MISSING_CREDENTIALS_REASON)

        token_result = self.get_access_token()
        if token_result.get("status") != "ok":
            return token_result

        headers = {"Authorization": f"Bearer {self._access_token}"}
        try:
            response = self.session.get(
                f"{self.base_url}/{endpoint}",
                params=params or {},
                headers=headers,
                timeout=self.timeout_seconds,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.RequestException):
            return _unavailable(REQUEST_FAILED_REASON)

        return self._parse_response(response)

    def _parse_response(self, response: Any) -> Any:
        if getattr(response, "status_code", 0) != 200:
            return _unavailable(REQUEST_FAILED_REASON)
        try:
            payload = response.json()
        except (TypeError, ValueError):
            return _unavailable(REQUEST_FAILED_REASON)
        if _has_ssi_error(payload):
            return _unavailable(REQUEST_FAILED_REASON)
        return payload

    def _cached_normalized(
        self,
        endpoint: str,
        params: Dict[str, Any],
        limit: int,
        mapper: Any,
        *,
        extra: Optional[Dict[str, Any]] = None,
        param_variants: Optional[List[Dict[str, Any]]] = None,
        required_any: Tuple[str, ...] = (),
    ) -> Dict[str, Any]:
        cache_key = (endpoint, tuple(sorted((params or {}).items())))
        if self.cache_ttl_seconds > 0:
            entry = self._cache.get(cache_key)
            if entry and entry.expires_at > time.time():
                return dict(entry.value)

        payload = self._request(endpoint, params=params)
        if isinstance(payload, dict) and payload.get("status") == "unavailable":
            return payload

        rows = [mapper(row) for row in _extract_rows(payload)]
        rows = [row for row in rows if row and _has_required_field(row, required_any)]
        if not rows:
            for variant_params in param_variants or []:
                if not variant_params or variant_params == params:
                    continue
                variant_payload = self._request(endpoint, params=variant_params)
                if isinstance(variant_payload, dict) and variant_payload.get("status") == "unavailable":
                    continue
                rows = [mapper(row) for row in _extract_rows(variant_payload)]
                rows = [row for row in rows if row and _has_required_field(row, required_any)]
                if rows:
                    break
        if rows and "date" in rows[0]:
            rows.sort(key=lambda item: (item.get("date") is None, item.get("date") or ""))
        if limit and len(rows) > limit:
            rows = rows[-limit:]

        result = {
            "status": "ok",
            "source": SSI_SOURCE,
            **{k: v for k, v in (extra or {}).items() if v is not None},
            "rows": rows,
            "count": len(rows),
        }
        if self.cache_ttl_seconds > 0:
            self._cache[cache_key] = _CacheEntry(
                value=dict(result),
                expires_at=time.time() + self.cache_ttl_seconds,
            )
        return result

    def _cached_chunked_normalized(
        self,
        endpoint: str,
        base_params: Dict[str, Any],
        from_date: Optional[str],
        to_date: Optional[str],
        limit: int,
        mapper: Any,
        *,
        extra: Optional[Dict[str, Any]] = None,
        base_param_variants: Optional[List[Dict[str, Any]]] = None,
        required_any: Tuple[str, ...] = (),
        dedupe_fields: Tuple[str, ...] = ("date",),
    ) -> Dict[str, Any]:
        windows = build_ssi_date_windows(from_date, to_date)
        cache_params = {
            **base_params,
            "fromDate": windows[0][0] if windows else "",
            "toDate": windows[-1][1] if windows else "",
            "limit": int(limit or 0),
            "chunked": True,
        }
        cache_key = (endpoint, tuple(sorted(cache_params.items())))
        if self.cache_ttl_seconds > 0:
            entry = self._cache.get(cache_key)
            if entry and entry.expires_at > time.time():
                return dict(entry.value)

        param_sets = [base_params] + [variant for variant in (base_param_variants or []) if variant and variant != base_params]
        result_rows: List[Dict[str, Any]] = []
        unavailable_result: Optional[Dict[str, Any]] = None
        chunks_used = len(windows)
        pages_used = 0
        for index, params in enumerate(param_sets):
            rows, pages, unavailable = self._fetch_chunked_rows(
                endpoint,
                params,
                windows,
                mapper,
                required_any=required_any,
            )
            pages_used += pages
            if unavailable:
                if index == 0:
                    unavailable_result = unavailable
                    break
                continue
            if rows:
                result_rows = rows
                break

        if unavailable_result:
            return unavailable_result

        rows = self._dedupe_and_sort_rows(result_rows, dedupe_fields)
        if limit and len(rows) > limit:
            rows = rows[-limit:]

        result = {
            "status": "ok",
            "source": SSI_SOURCE,
            **{k: v for k, v in (extra or {}).items() if v is not None},
            "rows": rows,
            "count": len(rows),
            "chunks_used": chunks_used,
            "pages_used": pages_used,
            "date_range": {
                "from": windows[0][0] if windows else None,
                "to": windows[-1][1] if windows else None,
            },
        }
        if self.cache_ttl_seconds > 0:
            self._cache[cache_key] = _CacheEntry(
                value=dict(result),
                expires_at=time.time() + self.cache_ttl_seconds,
            )
        return result

    def _fetch_chunked_rows(
        self,
        endpoint: str,
        base_params: Dict[str, Any],
        windows: List[Tuple[str, str]],
        mapper: Any,
        *,
        required_any: Tuple[str, ...] = (),
    ) -> Tuple[List[Dict[str, Any]], int, Optional[Dict[str, Any]]]:
        rows: List[Dict[str, Any]] = []
        pages_used = 0
        for from_value, to_value in windows:
            page_index = 1
            fetched_raw_rows = 0
            while page_index <= SSI_MAX_PAGES:
                if pages_used and self.request_delay_seconds:
                    time.sleep(self.request_delay_seconds)
                params = dict(base_params)
                params.update(
                    {
                        "Fromdate": from_value,
                        "Todate": to_value,
                        "pageIndex": page_index,
                        "pageSize": SSI_PAGE_SIZE,
                    }
                )
                payload = self._request(endpoint, params=params)
                pages_used += 1
                if isinstance(payload, dict) and payload.get("status") == "unavailable":
                    return [], pages_used, payload

                raw_rows = _extract_rows(payload)
                mapped_rows = [mapper(row) for row in raw_rows]
                mapped_rows = [row for row in mapped_rows if row and _has_required_field(row, required_any)]
                if not mapped_rows:
                    break

                rows.extend(mapped_rows)
                fetched_raw_rows += len(raw_rows)
                total = _total_record(payload)
                if total is not None and fetched_raw_rows >= total:
                    break
                if total is None and len(raw_rows) < SSI_PAGE_SIZE:
                    break
                page_index += 1
        return rows, pages_used, None

    @staticmethod
    def _dedupe_and_sort_rows(rows: List[Dict[str, Any]], dedupe_fields: Tuple[str, ...]) -> List[Dict[str, Any]]:
        deduped: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        passthrough: List[Dict[str, Any]] = []
        for row in rows:
            key_values = tuple(row.get(field) for field in dedupe_fields)
            if all(value not in (None, "") for value in key_values):
                deduped[key_values] = row
            else:
                passthrough.append(row)
        merged = list(deduped.values()) + passthrough
        if merged and "date" in merged[0]:
            merged.sort(key=lambda item: (item.get("date") is None, item.get("date") or ""))
        return merged

    def _map_daily_ohlcv(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "date": _parse_date(_first_value(row, "TradingDate", "Tradingdate", "Date", "date", "trading_date", "time")),
            "open": _to_float(_first_value(row, "Open", "OpenPrice", "open", "open_price")),
            "high": _to_float(_first_value(row, "Highest", "HighestPrice", "High", "HighPrice", "high", "high_price")),
            "low": _to_float(_first_value(row, "Lowest", "LowestPrice", "Low", "LowPrice", "low", "low_price")),
            "close": _to_float(_first_value(row, "Close", "ClosePrice", "close", "close_price")),
            "volume": _to_int(_first_value(row, "TotalVolume", "Volume", "totalVolume", "volume", "matchedVolume", "matchVolume")),
            "value": _to_float(_first_value(row, "TotalValue", "Value", "totalValue", "value", "matchedValue", "matchValue")),
            "source": SSI_SOURCE,
        }

    def _map_daily_stock_price(self, row: Dict[str, Any]) -> Dict[str, Any]:
        foreign_buy_volume = _first_value(
            row,
            "ForeignBuyVol",
            "ForeignBuyVolume",
            "ForeignBuyVolTotal",
            "ForeignBuyVolumeTotal",
            "foreignBuyVolume",
            "BuyForeignQuantity",
            "buyForeignVolume",
            "buyForeignQuantity",
        )
        foreign_sell_volume = _first_value(
            row,
            "ForeignSellVol",
            "ForeignSellVolume",
            "ForeignSellVolTotal",
            "ForeignSellVolumeTotal",
            "foreignSellVolume",
            "SellForeignQuantity",
            "sellForeignVolume",
            "sellForeignQuantity",
        )
        foreign_buy_value = _first_value(row, "ForeignBuyValue", "ForeignBuyValTotal", "foreignBuyValue", "foreign_buy_value", "BuyForeignValue")
        foreign_sell_value = _first_value(row, "ForeignSellValue", "ForeignSellValTotal", "foreignSellValue", "foreign_sell_value", "SellForeignValue")
        return {
            "date": _parse_date(_first_value(row, "TradingDate", "Tradingdate", "Date", "date", "trading_date", "time")),
            "reference_price": _to_float(_first_value(row, "RefPrice", "ReferencePrice", "BasicPrice", "referencePrice", "reference_price")),
            "ceiling_price": _to_float(_first_value(row, "Ceiling", "CeilingPrice", "ceilingPrice", "ceiling_price")),
            "floor_price": _to_float(_first_value(row, "Floor", "FloorPrice", "floorPrice", "floor_price")),
            "open": _to_float(_first_value(row, "Open", "OpenPrice", "open", "open_price")),
            "high": _to_float(_first_value(row, "Highest", "HighestPrice", "High", "HighPrice", "high", "high_price")),
            "low": _to_float(_first_value(row, "Lowest", "LowestPrice", "Low", "LowPrice", "low", "low_price")),
            "close": _to_float(_first_value(row, "Close", "ClosePrice", "close", "close_price")),
            "adjusted_close": _to_float(_first_value(row, "AdjustedClose", "AdjustedClosePrice", "ClosePriceAdjusted", "adjustedClose", "adjusted_close", "adjClose", "adj_close")),
            "matched_volume": _to_int(_first_value(row, "TotalMatchVol", "MatchedVolume", "MatchedVol", "MatchVolume", "matchedVolume", "matched_volume")),
            "matched_value": _to_float(_first_value(row, "TotalMatchVal", "MatchedValue", "MatchValue", "matchedValue", "matched_value")),
            "put_through_volume": _to_int(_first_value(row, "TotalDealVol", "PutThroughVolume", "PutThroughVol", "putThroughVolume", "put_through_volume", "dealVolume")),
            "put_through_value": _to_float(_first_value(row, "TotalDealVal", "PutThroughValue", "putThroughValue", "put_through_value", "dealValue")),
            "total_volume": _to_int(_first_value(row, "TotalTradedVol", "TotalVol", "TotalVolume", "Volume", "totalTradedVol", "totalVol", "totalVolume", "volume")),
            "total_value": _to_float(_first_value(row, "TotalTradedValue", "TotalVal", "TotalValue", "Value", "totalTradedValue", "totalVal", "totalValue", "value")),
            "foreign_buy_volume": _to_int(foreign_buy_volume),
            "foreign_sell_volume": _to_int(foreign_sell_volume),
            "foreign_net_volume": _to_int(_net_value(row, ("NetBuySellVol", "ForeignNetVolume", "ForeignNetVol", "foreignNetVolume", "foreign_net_volume"), foreign_buy_volume, foreign_sell_volume)),
            "foreign_buy_value": _to_float(foreign_buy_value),
            "foreign_sell_value": _to_float(foreign_sell_value),
            "foreign_net_value": _net_value(row, ("NetBuySellVal", "ForeignNetValue", "foreignNetValue", "foreign_net_value"), foreign_buy_value, foreign_sell_value),
            "source": SSI_SOURCE,
        }

    def _map_daily_index(self, row: Dict[str, Any], index_code: str) -> Dict[str, Any]:
        return {
            "date": _parse_date(_first_value(row, "TradingDate", "Tradingdate", "Date", "date", "trading_date", "time")),
            "index_code": str(_first_value(row, "IndexId", "IndexID", "IndexCode", "indexId", "indexID", "indexCode", "index_code", "code") or index_code).upper(),
            "index_value": _to_float(_first_value(row, "IndexValue", "Index", "Close", "CloseIndex", "indexValue", "index_value", "close")),
            "change": _to_float(_first_value(row, "Change", "IndexChange", "ChangeValue", "change", "indexChange", "changeValue")),
            "change_pct": _to_float(_first_value(row, "RatioChange", "ChangePct", "ChangePercent", "PercentChange", "ratioChange", "changePct", "change_pct", "percentChange")),
            "total_volume": _to_int(_first_value(row, "TotalVol", "TotalMatchVol", "TotalVolume", "Volume", "totalVol", "totalMatchVol", "totalVolume", "total_volume", "volume")),
            "total_value": _to_float(_first_value(row, "TotalVal", "TotalMatchVal", "TotalValue", "Value", "totalVal", "totalMatchVal", "totalValue", "total_value", "value")),
            "matched_volume": _to_int(_first_value(row, "TotalMatchVol", "MatchedVolume", "MatchedVol", "MatchVolume", "totalMatchVol", "matchedVolume", "matched_volume")),
            "matched_value": _to_float(_first_value(row, "TotalMatchVal", "MatchedValue", "MatchValue", "totalMatchVal", "matchedValue", "matched_value")),
            "put_through_volume": _to_int(_first_value(row, "TotalDealVol", "PutThroughVolume", "PutThroughVol", "putThroughVolume", "put_through_volume", "dealVolume")),
            "put_through_value": _to_float(_first_value(row, "TotalDealVal", "PutThroughValue", "putThroughValue", "put_through_value", "dealValue")),
            "advances": _to_int(_first_value(row, "Advances", "Increase", "Up", "advances", "increase", "up")),
            "unchanged": _to_int(_first_value(row, "NoChanges", "Unchanged", "NoChange", "NoChangeCount", "unchanged", "noChanges", "noChange", "no_change")),
            "declines": _to_int(_first_value(row, "Declines", "Decrease", "Down", "declines", "decrease", "down")),
            "ceiling": _to_int(_first_value(row, "Ceilings", "Ceiling", "CeilingCount", "ceilings", "ceiling", "ceilingCount")),
            "floor": _to_int(_first_value(row, "Floors", "Floor", "FloorCount", "floors", "floor", "floorCount")),
            "trading_session": _first_value(row, "TradingSession", "Session", "tradingSession", "trading_session"),
            "exchange": _first_value(row, "Exchange", "Market", "exchange", "market"),
            "source": SSI_SOURCE,
        }

    def _map_index_info(self, row: Dict[str, Any]) -> Dict[str, Any]:
        index_id = _first_value(row, "IndexID", "IndexId", "indexID", "indexId", "IndexCode", "indexCode", "Code", "code")
        index_code = _first_value(row, "IndexCode", "indexCode", "Code", "code", "IndexID", "IndexId", "indexID", "indexId")
        return {
            "index_id": str(index_id).upper() if index_id not in (None, "") else None,
            "index_code": str(index_code).upper() if index_code not in (None, "") else None,
            "name": _first_value(row, "IndexName", "Name", "indexName", "name"),
            "exchange": _first_value(row, "Exchange", "Market", "exchange", "market"),
            "source": SSI_SOURCE,
        }

    def _map_security(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "symbol": str(_first_value(row, "Symbol", "Ticker", "SecurityCode", "StockSymbol", "StockCode", "Code", "symbol", "ticker", "securityCode", "stockSymbol", "stockCode", "code") or "").upper() or None,
            "exchange": _first_value(row, "Exchange", "Market", "StockExchange", "ExchangeCode", "exchange", "market", "stockExchange", "exchangeCode"),
            "security_type": _first_value(row, "SecurityType", "SecuritiesType", "Type", "StockType", "securityType", "securitiesType", "security_type", "stockType", "type"),
            "name": _first_value(row, "Name", "CompanyName", "CompanyNameVi", "SecurityName", "VietnameseName", "IssuerNameVn", "name", "companyName", "company_name", "securityName", "vietnameseName", "issuerNameVn"),
            "name_en": _first_value(row, "NameEn", "EnglishName", "CompanyNameEn", "SecurityNameEn", "IssuerNameEn", "nameEn", "name_en", "englishName", "companyNameEn", "securityNameEn", "issuerNameEn"),
            "issuer": _first_value(row, "Issuer", "IssuerName", "OrganizationName", "OrganName", "issuer", "issuerName", "organizationName", "organName"),
            "lot_size": _to_int(_first_value(row, "LotSize", "TradingUnit", "RoundLot", "lotSize", "lot_size", "tradingUnit", "roundLot")),
            "listed_shares": _to_int(_first_value(row, "ListedShares", "ListedShare", "TotalListedShares", "SharesOutstanding", "listedShares", "listedShare", "totalListedShares", "listed_shares", "sharesOutstanding")),
            "listed_date": _parse_date(_first_value(row, "ListedDate", "ListingDate", "FirstTradingDate", "listedDate", "listed_date", "listingDate", "firstTradingDate")),
            "market": _first_value(row, "Market", "Exchange", "StockExchange", "market", "exchange", "stockExchange"),
            "source": SSI_SOURCE,
        }
