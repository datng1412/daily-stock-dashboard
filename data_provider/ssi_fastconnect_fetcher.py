# -*- coding: utf-8 -*-
"""SSI FastConnect FC Data foundation provider.

This adapter keeps SSI FastConnect market-data requests behind one auth,
timeout, cache, and normalization layer. It never exposes tokens or request
headers in returned payloads.
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
INTRADAY_DISABLED_REASON = "SSI FastConnect IntradayOhlc disabled"
REALTIME_DISABLED_REASON = "SSI FastConnect realtime disabled"
TRADE_TAPE_DISABLED_REASON = "SSI FastConnect trade tape disabled"
SSI_CHUNK_MAX_DAYS = 29
SSI_PAGE_SIZE = 1000
SSI_MAX_PAGES = 20


def _endpoint_attempt_reason(
    *,
    kind: str,
    endpoints: Tuple[str, ...],
    first_unavailable: Optional[Dict[str, Any]] = None,
) -> str:
    """Build a secret-free diagnostic for realtime/trade-tape probe failures."""
    reason = str((first_unavailable or {}).get("reason") or REQUEST_FAILED_REASON)
    endpoint = (first_unavailable or {}).get("endpoint")
    http_status = (first_unavailable or {}).get("http_status")
    code = (first_unavailable or {}).get("code")
    details = [f"attempted endpoints: {', '.join(endpoints)}"]
    if endpoint:
        details.append(f"last endpoint: {endpoint}")
    if http_status is not None:
        details.append(f"http status: {http_status}")
    if code is not None:
        details.append(f"provider code: {code}")
    return f"SSI FastConnect {kind} unavailable ({'; '.join(details)}). Last error: {reason}"


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


def _safe_text(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    return str(value)


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


def _parse_datetime(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.isoformat()

    text = str(value).strip()
    if not text:
        return None

    try:
        numeric = float(text)
    except ValueError:
        numeric = None
    if numeric is not None:
        if numeric > 1_000_000_000_000:
            return datetime.fromtimestamp(numeric / 1000, tz=timezone.utc).isoformat()
        if numeric > 1_000_000_000:
            return datetime.fromtimestamp(numeric, tz=timezone.utc).isoformat()

    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).isoformat()
    except ValueError:
        pass

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(normalized, fmt).isoformat()
        except ValueError:
            continue
    return None


def _timestamp_from_datetime(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


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


def _pick_ci(payload: Any, *keys: str) -> Any:
    """Return a dictionary value by key using case-insensitive matching."""
    if not isinstance(payload, dict):
        return None
    for key in keys:
        if key in payload:
            return payload.get(key)
    lower_lookup = {str(key).lower(): value for key, value in payload.items()}
    for key in keys:
        lowered = str(key).lower()
        if lowered in lower_lookup:
            return lower_lookup[lowered]
    return None


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
    return any(row.get(field) not in (None, "", [], {}) for field in fields)


def _has_ssi_error(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    status = str(_pick_ci(payload, "status", "Status") or "").strip().lower()
    message = str(_pick_ci(payload, "message", "Message") or "").strip().lower()
    success = _pick_ci(payload, "success", "Success")
    code = str(_pick_ci(payload, "code", "Code", "errorCode", "ErrorCode", "error_code") or "").strip()
    if status in {"error", "failed", "fail", "unavailable"}:
        return True
    if status and status not in {"success", "ok", "0", "200"}:
        return True
    if isinstance(success, bool) and not success:
        return True
    if code and code not in {"0", "200", "OK", "ok"} and (message or status):
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
        intraday_enabled: Optional[bool] = None,
        realtime_enabled: Optional[bool] = None,
        trade_tape_enabled: Optional[bool] = None,
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
        self.intraday_enabled = (
            bool(intraday_enabled)
            if intraday_enabled is not None
            else bool(getattr(config, "ssi_fastconnect_intraday_enabled", parse_env_bool(os.getenv("SSI_FASTCONNECT_INTRADAY_ENABLED"), default=True)))
        )
        self.realtime_enabled = (
            bool(realtime_enabled)
            if realtime_enabled is not None
            else bool(getattr(config, "ssi_fastconnect_realtime_enabled", parse_env_bool(os.getenv("SSI_FASTCONNECT_REALTIME_ENABLED"), default=True)))
        )
        self.trade_tape_enabled = (
            bool(trade_tape_enabled)
            if trade_tape_enabled is not None
            else bool(getattr(config, "ssi_fastconnect_trade_tape_enabled", parse_env_bool(os.getenv("SSI_FASTCONNECT_TRADE_TAPE_ENABLED"), default=True)))
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

    def get_intraday_ohlcv(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 64,
        interval: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.intraday_enabled:
            return {
                "status": "disabled",
                "source": SSI_SOURCE,
                "reason": INTRADAY_DISABLED_REASON,
                "rows": [],
                "count": 0,
            }

        params: Dict[str, Any] = {"symbol": symbol.strip().upper()}
        if interval:
            params["timeFrame"] = str(interval).strip()
        params = self._date_params(params, from_date, to_date, limit)
        variants = [self._alternate_param_case(params)]
        if interval:
            for interval_key in ("interval", "resolution", "timeframe", "TimeFrame"):
                variant = dict(params)
                variant.pop("timeFrame", None)
                variant[interval_key] = str(interval).strip()
                variants.append(variant)
                variants.append(self._alternate_param_case(variant))
        payload = self._cached_normalized(
            "IntradayOhlc",
            params,
            limit,
            lambda row: self._map_intraday_ohlcv(row, symbol),
            extra={"symbol": symbol.strip().upper(), "interval": interval},
            param_variants=variants,
            required_any=("date_time", "timestamp", "open", "high", "low", "close", "volume"),
        )
        return self._empty_as_unavailable(payload)

    def get_realtime_snapshot(self, symbols: List[str]) -> Dict[str, Any]:
        """Return SSI realtime snapshot rows when an account exposes them.

        SSI realtime/streaming endpoint names vary by entitlement and
        documentation set. This method tries a small set of FC Data-style
        endpoint names and normalizes only meaningful quote rows. Unknown,
        unentitled, or empty responses return clean unavailable payloads.
        """
        normalized_symbols = [str(symbol or "").strip().upper() for symbol in symbols or [] if str(symbol or "").strip()]
        if not self.realtime_enabled:
            return {
                "status": "disabled",
                "source": SSI_SOURCE,
                "reason": REALTIME_DISABLED_REASON,
                "requested_tickers": normalized_symbols,
                "quotes": [],
                "count": 0,
            }
        if not normalized_symbols:
            return {
                "status": "unavailable",
                "source": SSI_SOURCE,
                "reason": "No symbol requested",
                "requested_tickers": [],
                "quotes": [],
                "count": 0,
            }

        cache_key = ("RealtimeSnapshot", (("symbols", ",".join(normalized_symbols)),))
        if self.cache_ttl_seconds > 0:
            entry = self._cache.get(cache_key)
            if entry and entry.expires_at > time.time():
                return dict(entry.value)

        endpoint_candidates = ("RealtimeQuote", "RealtimePrice", "RealtimeSnapshot", "SecuritiesRealtime")
        rows: List[Dict[str, Any]] = []
        first_unavailable: Optional[Dict[str, Any]] = None
        for endpoint in endpoint_candidates:
            for symbol in normalized_symbols:
                params = {"symbol": symbol}
                payload = self._request(endpoint, params=params)
                if isinstance(payload, dict) and payload.get("status") == "unavailable":
                    if first_unavailable is None:
                        first_unavailable = payload
                    continue
                mapped = [self._map_realtime_snapshot(row, fallback_symbol=symbol) for row in _extract_rows(payload)]
                mapped = [
                    row
                    for row in mapped
                    if row and _has_required_field(row, ("price", "reference_price", "volume", "value", "bid_levels", "ask_levels"))
                ]
                rows.extend(mapped)
            if rows:
                break

        deduped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            ticker = str(row.get("ticker") or row.get("symbol") or "").upper()
            if ticker:
                deduped[ticker] = row
        quotes = [deduped[symbol] for symbol in normalized_symbols if symbol in deduped]
        if not quotes:
            payload = {
                "status": "unavailable",
                "source": SSI_SOURCE,
                "reason": _endpoint_attempt_reason(
                    kind="realtime snapshot",
                    endpoints=endpoint_candidates,
                    first_unavailable=first_unavailable,
                ),
                "requested_tickers": normalized_symbols,
                "quotes": [],
                "count": 0,
                "attempted_endpoints": list(endpoint_candidates),
            }
            if self.cache_ttl_seconds > 0:
                self._cache[cache_key] = _CacheEntry(value=dict(payload), expires_at=time.time() + self.cache_ttl_seconds)
            return payload

        result = {
            "status": "ok",
            "source": SSI_SOURCE,
            "requested_tickers": normalized_symbols,
            "quotes": quotes,
            "count": len(quotes),
        }
        if self.cache_ttl_seconds > 0:
            self._cache[cache_key] = _CacheEntry(value=dict(result), expires_at=time.time() + self.cache_ttl_seconds)
        return result

    def get_trade_tape(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Return SSI trade tape rows when an account exposes them."""
        normalized_symbol = str(symbol or "").strip().upper()
        safe_limit = max(1, min(int(limit or 100), 500))
        if not self.trade_tape_enabled:
            return {
                "status": "disabled",
                "source": SSI_SOURCE,
                "symbol": normalized_symbol,
                "reason": TRADE_TAPE_DISABLED_REASON,
                "trades": [],
                "count": 0,
            }
        if not normalized_symbol:
            return {
                "status": "unavailable",
                "source": SSI_SOURCE,
                "symbol": normalized_symbol,
                "reason": "No symbol requested",
                "trades": [],
                "count": 0,
            }

        params = {"symbol": normalized_symbol, "pageIndex": 1, "pageSize": safe_limit}
        endpoint_candidates = ("TradeTape", "MatchedTrades", "SecuritiesTrades")
        first_unavailable: Optional[Dict[str, Any]] = None
        trades: List[Dict[str, Any]] = []
        for endpoint in endpoint_candidates:
            payload = self._cached_normalized(
                endpoint,
                params,
                safe_limit,
                lambda row: self._map_trade_tape(row),
                extra={"symbol": normalized_symbol},
                param_variants=[self._alternate_param_case(params)],
                required_any=("time", "price", "volume", "value"),
                retry_unavailable_variants=True,
            )
            if payload.get("status") == "ok" and payload.get("rows"):
                trades = list(payload.get("rows") or [])
                break
            if first_unavailable is None and payload.get("status") == "unavailable":
                first_unavailable = payload

        if not trades:
            return {
                "status": "unavailable",
                "source": SSI_SOURCE,
                "symbol": normalized_symbol,
                "reason": _endpoint_attempt_reason(
                    kind="trade tape",
                    endpoints=endpoint_candidates,
                    first_unavailable=first_unavailable,
                ),
                "trades": [],
                "count": 0,
                "attempted_endpoints": list(endpoint_candidates),
            }

        trades = trades[-safe_limit:]
        return {
            "status": "ok",
            "source": SSI_SOURCE,
            "symbol": normalized_symbol,
            "trades": trades,
            "count": len(trades),
        }

    def get_index_list(self, market: Optional[str] = None) -> Dict[str, Any]:
        params = {"market": market.strip().upper()} if market else {}
        payload = self._cached_normalized(
            "IndexList",
            params,
            0,
            self._map_index_info,
            extra={"market": params.get("market")},
            param_variants=[self._alternate_param_case(params)] if params else None,
            required_any=("index_id", "index_code"),
        )
        return self._empty_as_unavailable(payload)

    def get_index_components(self, index_code: str, market: Optional[str] = None) -> Dict[str, Any]:
        normalized_index = index_code.strip().upper()
        params: Dict[str, Any] = {
            "indexID": normalized_index,
            "pageIndex": 1,
            "pageSize": 1000,
        }
        if market:
            params["market"] = market.strip().upper()
        common_params = {key: value for key, value in params.items() if key != "indexID"}
        variants = [
            {**common_params, "indexCode": normalized_index},
            {**common_params, "IndexId": normalized_index},
            {**common_params, "IndexCode": normalized_index},
            self._alternate_param_case(params),
        ]
        payload = self._cached_normalized(
            "IndexComponents",
            params,
            0,
            lambda row: self._map_index_component(row, normalized_index),
            extra={"index_code": normalized_index, "market": params.get("market")},
            param_variants=variants,
            required_any=("symbol",),
            retry_unavailable_variants=True,
        )
        return self._empty_as_unavailable(payload)

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
            "pageIndex": "PageIndex",
            "pageSize": "PageSize",
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
        except requests.exceptions.Timeout:
            return {**_unavailable(REQUEST_FAILED_REASON), "endpoint": endpoint, "error_type": "timeout"}
        except requests.exceptions.ConnectionError:
            return {**_unavailable(REQUEST_FAILED_REASON), "endpoint": endpoint, "error_type": "connection_error"}
        except requests.exceptions.RequestException:
            return {**_unavailable(REQUEST_FAILED_REASON), "endpoint": endpoint, "error_type": "request_error"}

        return self._parse_response(response, endpoint=endpoint)

    def _parse_response(self, response: Any, endpoint: Optional[str] = None) -> Any:
        http_status = getattr(response, "status_code", 0)
        if http_status != 200:
            return {
                **_unavailable(REQUEST_FAILED_REASON),
                "endpoint": endpoint,
                "http_status": http_status,
                "error_type": "http_error",
            }
        try:
            payload = response.json()
        except (TypeError, ValueError):
            return {**_unavailable(REQUEST_FAILED_REASON), "endpoint": endpoint, "http_status": http_status, "error_type": "invalid_json"}
        if _has_ssi_error(payload):
            result = {**_unavailable(REQUEST_FAILED_REASON), "endpoint": endpoint, "http_status": http_status, "error_type": "ssi_error"}
            if isinstance(payload, dict):
                code = _pick_ci(payload, "code", "errorCode", "status", "Status")
                if code is not None:
                    result["code"] = str(code)[:80]
            return result
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
        retry_unavailable_variants: bool = False,
    ) -> Dict[str, Any]:
        cache_key = (endpoint, tuple(sorted((params or {}).items())))
        if self.cache_ttl_seconds > 0:
            entry = self._cache.get(cache_key)
            if entry and entry.expires_at > time.time():
                return dict(entry.value)

        payload = self._request(endpoint, params=params)
        first_unavailable = payload if isinstance(payload, dict) and payload.get("status") == "unavailable" else None
        if first_unavailable and not retry_unavailable_variants:
            return payload

        rows = [] if first_unavailable else [mapper(row) for row in _extract_rows(payload)]
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
        if not rows and first_unavailable:
            return first_unavailable
        if rows and "date_time" in rows[0]:
            rows.sort(key=lambda item: (item.get("date_time") is None, item.get("date_time") or ""))
        elif rows and "date" in rows[0]:
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

    @staticmethod
    def _empty_as_unavailable(payload: Dict[str, Any]) -> Dict[str, Any]:
        if payload.get("status") != "ok":
            return payload
        if payload.get("count", 0) == 0:
            return {
                **payload,
                "status": "unavailable",
                "reason": REQUEST_FAILED_REASON,
                "rows": [],
                "count": 0,
            }
        return payload

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

    def _map_intraday_ohlcv(self, row: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        explicit_datetime = _first_value(
            row,
            "DateTime",
            "datetime",
            "dateTime",
            "TradingDateTime",
            "tradingDateTime",
        )
        date_part = _first_value(row, "TradingDate", "Date", "date", "tradingDate")
        time_part = _first_value(row, "TradingTime", "Time", "time", "tradingTime")
        combined_datetime = None
        if date_part and time_part and not any(separator in str(time_part) for separator in ("-", "/", "T")):
            combined_datetime = f"{date_part} {time_part}"
        date_time = _parse_datetime(
            explicit_datetime
            or combined_datetime
            or time_part
            or date_part
        )
        return {
            "timestamp": _timestamp_from_datetime(date_time),
            "date_time": date_time,
            "open": _to_float(_first_value(row, "Open", "OpenPrice", "open", "open_price")),
            "high": _to_float(_first_value(row, "Highest", "HighestPrice", "High", "HighPrice", "high", "high_price")),
            "low": _to_float(_first_value(row, "Lowest", "LowestPrice", "Low", "LowPrice", "low", "low_price")),
            "close": _to_float(_first_value(row, "Close", "ClosePrice", "close", "close_price")),
            "volume": _to_int(_first_value(row, "TotalVolume", "Volume", "totalVolume", "volume", "matchedVolume", "matchVolume")),
            "ticker": symbol.strip().upper(),
            "source": SSI_SOURCE,
        }

    def _map_realtime_snapshot(self, row: Dict[str, Any], *, fallback_symbol: str) -> Dict[str, Any]:
        ticker = _first_value(row, "Symbol", "Ticker", "StockCode", "SecurityCode", "Code", "symbol", "ticker", "stockCode", "securityCode", "code")
        price = _to_float(
            _first_value(
                row,
                "LastPrice",
                "MatchedPrice",
                "MatchPrice",
                "Close",
                "ClosePrice",
                "Price",
                "lastPrice",
                "matchedPrice",
                "matchPrice",
                "close",
                "price",
            )
        )
        bid_levels = self._map_quote_levels(row, side="bid")
        ask_levels = self._map_quote_levels(row, side="ask")
        fetched_at = datetime.now(timezone.utc).isoformat()
        return {
            "ticker": str(ticker or fallback_symbol).upper(),
            "symbol": str(ticker or fallback_symbol).upper(),
            "source": SSI_SOURCE,
            "fetched_at": fetched_at,
            "price": price,
            "realtime_price": price,
            "snapshot_price": price,
            "change": _to_float(_first_value(row, "Change", "PriceChange", "ChangeValue", "change", "priceChange", "changeValue")),
            "change_pct": _to_float(_first_value(row, "ChangePercent", "PercentChange", "RatioChange", "changePercent", "percentChange", "ratioChange")),
            "reference_price": _to_float(_first_value(row, "RefPrice", "ReferencePrice", "BasicPrice", "referencePrice", "reference_price")),
            "ceiling_price": _to_float(_first_value(row, "Ceiling", "CeilingPrice", "ceilingPrice", "ceiling_price")),
            "floor_price": _to_float(_first_value(row, "Floor", "FloorPrice", "floorPrice", "floor_price")),
            "open": _to_float(_first_value(row, "Open", "OpenPrice", "open", "openPrice")),
            "high": _to_float(_first_value(row, "High", "Highest", "HighPrice", "HighestPrice", "high", "highest", "highPrice")),
            "low": _to_float(_first_value(row, "Low", "Lowest", "LowPrice", "LowestPrice", "low", "lowest", "lowPrice")),
            "volume": _to_int(_first_value(row, "TotalVolume", "TotalVol", "Volume", "MatchedVolume", "MatchVolume", "totalVolume", "volume", "matchedVolume")),
            "value": _to_float(_first_value(row, "TotalValue", "TotalVal", "Value", "MatchedValue", "MatchValue", "totalValue", "value", "matchedValue")),
            "bid_levels": bid_levels,
            "ask_levels": ask_levels,
            "status": "ok",
        }

    @staticmethod
    def _map_quote_levels(row: Dict[str, Any], *, side: str) -> List[Dict[str, Optional[float]]]:
        nested_keys = ("BidLevels", "Bids", "bidLevels", "bids") if side == "bid" else ("AskLevels", "Asks", "askLevels", "asks")
        nested = _first_value(row, *nested_keys)
        if isinstance(nested, list):
            levels = []
            for level in nested[:5]:
                if not isinstance(level, dict):
                    continue
                price = _to_float(_first_value(level, "Price", "price", "BidPrice", "AskPrice", "bidPrice", "askPrice"))
                volume = _to_float(_first_value(level, "Volume", "Vol", "volume", "vol", "BidVol", "AskVol", "bidVol", "askVol"))
                if price is not None or volume is not None:
                    levels.append({"price": price, "volume": volume})
            return levels

        levels = []
        prefixes = ("Bid", "bid") if side == "bid" else ("Ask", "ask")
        for index in range(1, 6):
            price_keys = tuple(f"{prefix}Price{index}" for prefix in prefixes) + tuple(f"{prefix}_price_{index}" for prefix in prefixes)
            volume_keys = tuple(f"{prefix}Vol{index}" for prefix in prefixes) + tuple(f"{prefix}Volume{index}" for prefix in prefixes) + tuple(f"{prefix}_vol_{index}" for prefix in prefixes)
            price = _to_float(_first_value(row, *price_keys))
            volume = _to_float(_first_value(row, *volume_keys))
            if price is not None or volume is not None:
                levels.append({"price": price, "volume": volume})
        return levels

    def _map_trade_tape(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "time": _safe_text(_first_value(row, "Time", "TradingTime", "MatchedTime", "MatchTime", "time", "tradingTime", "matchedTime", "matchTime")),
            "price": _to_float(_first_value(row, "Price", "MatchedPrice", "MatchPrice", "price", "matchedPrice", "matchPrice")),
            "volume": _to_float(_first_value(row, "Volume", "MatchedVolume", "MatchVolume", "volume", "matchedVolume", "matchVolume")),
            "value": _to_float(_first_value(row, "Value", "MatchedValue", "MatchValue", "value", "matchedValue", "matchValue")),
            "side_if_available": _safe_text(_first_value(row, "Side", "MatchType", "BuySell", "side", "matchType", "buySell")),
            "sequence_if_available": _safe_text(_first_value(row, "Sequence", "Seq", "Id", "ID", "sequence", "seq", "id")),
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
            "index_name": _first_value(row, "IndexName", "Name", "indexName", "name"),
            "exchange": _first_value(row, "Exchange", "Market", "exchange", "market"),
            "market": _first_value(row, "Market", "Exchange", "market", "exchange"),
            "source": SSI_SOURCE,
        }

    def _map_index_component(self, row: Dict[str, Any], index_code: str) -> Dict[str, Any]:
        component_index = _first_value(row, "IndexID", "IndexId", "IndexCode", "indexID", "indexId", "indexCode", "index_code")
        symbol = _first_value(row, "Symbol", "Ticker", "StockSymbol", "StockCode", "SecurityCode", "ComponentCode", "Code", "symbol", "ticker", "stockSymbol", "stockCode", "securityCode", "componentCode", "code")
        return {
            "index_code": str(component_index or index_code).upper(),
            "symbol": str(symbol).upper() if symbol not in (None, "") else None,
            "exchange": _first_value(row, "Exchange", "Market", "StockExchange", "ExchangeCode", "exchange", "market", "stockExchange", "exchangeCode"),
            "market": _first_value(row, "Market", "Exchange", "StockExchange", "market", "exchange", "stockExchange"),
            "weight": _to_float(_first_value(row, "Weight", "WeightPct", "WeightPercent", "Ratio", "Rate", "Percentage", "Proportion", "weight", "weightPct", "weightPercent", "ratio", "rate", "percentage", "proportion")),
            "name": _first_value(row, "Name", "CompanyName", "SecurityName", "StockName", "TickerName", "name", "companyName", "securityName", "stockName", "tickerName"),
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
