# -*- coding: utf-8 -*-
"""SSI FastConnect FC Data foundation provider.

This adapter keeps SSI FastConnect market-data requests behind one auth,
timeout, cache, and normalization layer. It never exposes tokens or request
headers in returned payloads.
"""

from __future__ import annotations

import importlib.util
import json
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from threading import RLock
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import requests

from src.config import get_config, parse_env_bool, parse_env_int
from data_provider.ssi_streaming_realtime import (
    DEFAULT_FOREIGN_ROOM_TTL_SECONDS,
    DEFAULT_MARKET_INDEX_CODES,
    DEFAULT_MARKET_INDEX_TTL_SECONDS,
    DEFAULT_ORDER_BOOK_TTL_SECONDS,
    DEFAULT_STREAMING_REALTIME_CACHE_TTL_SECONDS,
    DEFAULT_STREAMING_REALTIME_CHANNEL_TEMPLATE,
    DEFAULT_STREAMING_REALTIME_IDLE_TIMEOUT_SECONDS,
    DEFAULT_STREAMING_REALTIME_RECONNECT_INITIAL_DELAY_SECONDS,
    DEFAULT_STREAMING_REALTIME_RECONNECT_MAX_DELAY_SECONDS,
    DEFAULT_STREAMING_REALTIME_STREAM_URL,
    DEFAULT_TRADE_TAPE_BUFFER_SIZE,
    DEFAULT_TRADE_TAPE_TTL_SECONDS,
    ForeignRoomCache,
    MarketIndexPulseCache,
    OfficialSsiRealtimeStreamClient,
    OrderBookCache,
    RealtimeSnapshotCache,
    SessionStatusCache,
    SsiRealtimeStreamClient,
    SsiStreamingRealtimeManager,
    SSI_STREAMING_REALTIME_CONFIG_INCOMPLETE_REASON,
    SSI_STREAMING_REALTIME_DISABLED_REASON,
    SSI_STREAMING_REALTIME_PACKAGE_UNAVAILABLE_REASON,
    TradeTapeEventCache,
)


SSI_SOURCE = "SSI"
DEFAULT_BASE_URL = "https://fc-data.ssi.com.vn/api/v2/Market"
DISABLED_REASON = "SSI FastConnect disabled"
MISSING_CREDENTIALS_REASON = "SSI FastConnect credentials missing"
REQUEST_FAILED_REASON = "SSI FastConnect request failed"
DAILY_OHLC_RATE_LIMIT_COOLDOWN_REASON = "SSI DailyOhlc rate-limit cooldown active."
INTRADAY_DISABLED_REASON = "SSI FastConnect IntradayOhlc disabled"
INTRADAY_RATE_LIMIT_COOLDOWN_REASON = "SSI IntradayOhlc rate limit cooldown active."
REALTIME_DISABLED_REASON = "SSI FastConnect realtime disabled"
REALTIME_ENDPOINT_NOT_IDENTIFIED_REASON = "Supported SSI realtime endpoint not identified in repository."
REALTIME_STREAMING_NOT_IMPLEMENTED_REASON = "SSI realtime requires FastConnect streaming adapter; connection semantics not implemented."
TRADE_TAPE_DISABLED_REASON = "SSI FastConnect trade tape disabled"
SSI_REALTIME_ENDPOINT_CANDIDATES = ("RealtimeQuote", "RealtimePrice", "RealtimeSnapshot", "SecuritiesRealtime")
SSI_REALTIME_STREAMING_DATA_TYPES = ("X", "X-QUOTE", "X-TRADE", "F", "R", "MI")
SSI_REALTIME_QUOTE_STREAMING_DATA_TYPES = ("X",)
SSI_CHUNK_MAX_DAYS = 29
SSI_PAGE_SIZE = 1000
SSI_MAX_PAGES = 20
DEFAULT_DAILY_OHLC_RATE_LIMIT_COOLDOWN_SECONDS = 300
DEFAULT_INTRADAY_RATE_LIMIT_COOLDOWN_SECONDS = 60
DEFAULT_INDEX_REQUEST_DELAY_SECONDS = 1.15


def _endpoint_attempt_reason(
    *,
    kind: str,
    endpoints: Tuple[str, ...],
    first_unavailable: Optional[Dict[str, Any]] = None,
    attempts: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Build a secret-free diagnostic for realtime/trade-tape probe failures."""
    reason = str((first_unavailable or {}).get("reason") or REQUEST_FAILED_REASON)
    endpoint = (first_unavailable or {}).get("endpoint")
    http_status = (first_unavailable or {}).get("http_status")
    code = (first_unavailable or {}).get("code")
    details = [f"attempted endpoints: {', '.join(endpoints)}"]
    endpoint_statuses = _endpoint_status_summary(attempts or [])
    if endpoint_statuses:
        details.append(f"endpoint statuses: {endpoint_statuses}")
    else:
        if endpoint:
            details.append(f"sample endpoint: {endpoint}")
        if http_status is not None:
            details.append(f"http status: {http_status}")
        if code is not None:
            details.append(f"provider code: {code}")
    return f"SSI FastConnect {kind} unavailable ({'; '.join(details)}). Last error: {reason}"


def _endpoint_status_summary(attempts: List[Dict[str, Any]]) -> str:
    grouped: Dict[str, List[str]] = {}
    for attempt in attempts:
        endpoint = str(attempt.get("endpoint") or "").strip()
        if not endpoint:
            continue
        label = None
        http_status = attempt.get("http_status")
        if http_status is not None:
            label = f"http {http_status}"
        else:
            error_type = attempt.get("error_type")
            if error_type:
                label = str(error_type)
            else:
                status = attempt.get("status")
                if status:
                    label = str(status)
        if not label:
            continue
        labels = grouped.setdefault(endpoint, [])
        if label not in labels:
            labels.append(label)
    return ", ".join(f"{endpoint}={'+'.join(labels)}" for endpoint, labels in grouped.items())


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


@dataclass
class _RateLimitCooldown:
    expires_at: float
    cooldown_until: Optional[str]


def _unavailable(reason: str) -> Dict[str, str]:
    return {
        "status": "unavailable",
        "source": SSI_SOURCE,
        "reason": reason,
    }


def _safe_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _classify_provider_failure(
    *,
    error_type: Optional[str] = None,
    http_status: Optional[Any] = None,
    code: Optional[Any] = None,
    reason: Optional[str] = None,
) -> str:
    """Map provider/request failure metadata into a safe diagnostic class."""
    error = str(error_type or "").strip().lower()
    status_code = _safe_int(http_status)
    provider_code = _safe_int(code)
    provider_code_text = str(code or "").strip().lower()
    reason_text = str(reason or "").strip().lower()

    if reason_text == MISSING_CREDENTIALS_REASON.lower():
        return "auth_failed"
    if error == "timeout":
        return "timeout"
    if error in {"connection_error", "network_error", "request_error"}:
        return "network_error"
    if error == "invalid_json":
        return "parse_failed"
    if any(marker in provider_code_text for marker in ("auth", "token", "credential")):
        return "auth_failed"
    if any(marker in provider_code_text for marker in ("permission", "forbidden", "denied")):
        return "permission_denied"
    if any(marker in provider_code_text for marker in ("rate", "throttle", "too_many")):
        return "rate_limited"
    if any(marker in provider_code_text for marker in ("request_null", "bad_request", "invalid_param", "parameter")):
        return "bad_request_params"

    effective_code = provider_code if provider_code is not None else status_code
    if effective_code == 429:
        return "rate_limited"
    if effective_code == 401:
        return "auth_failed"
    if effective_code == 403:
        return "permission_denied"
    if effective_code == 400:
        return "bad_request_params"
    if effective_code in {408, 504}:
        return "timeout"
    if effective_code is not None and effective_code >= 500:
        return "provider_unavailable"
    if error == "ssi_error":
        return "provider_unavailable"
    if error == "http_error":
        return "provider_unavailable"
    return "unknown"


def _safe_diagnostic_text(value: Any, *, max_length: int = 120) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_length]


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


def _extract_index_component_rows(payload: Any, requested_index: str) -> List[Dict[str, Any]]:
    """Flatten SSI's nested IndexComponent envelope for one exact index only."""
    if isinstance(payload, dict) and payload.get("status") == "unavailable":
        return []
    normalized_requested = str(requested_index or "").strip().upper()
    components: List[Dict[str, Any]] = []
    for row in _extract_rows(payload):
        nested = _first_value(row, "IndexComponent", "IndexComponents", "Components", "components")
        outer_index = _first_value(
            row,
            "IndexID",
            "IndexId",
            "IndexCode",
            "indexID",
            "indexId",
            "indexCode",
            "index_code",
        )
        normalized_outer = str(outer_index or "").strip().upper()
        if isinstance(nested, list):
            if not normalized_outer or normalized_outer != normalized_requested:
                continue
            outer_exchange = _first_value(row, "Exchange", "Market", "exchange", "market")
            for component in nested:
                if not isinstance(component, dict):
                    continue
                flattened = dict(component)
                flattened.setdefault("IndexCode", normalized_outer)
                if outer_exchange not in (None, ""):
                    flattened.setdefault("Exchange", outer_exchange)
                components.append(flattened)
            continue
        if normalized_outer and normalized_outer != normalized_requested:
            continue
        components.append(row)
    return components


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


def _ssi_error_record(payload: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    candidates = [payload]
    for key in ("data", "Data", "result", "Result"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)
    for candidate in candidates:
        status = str(_pick_ci(candidate, "status", "Status") or "").strip().lower()
        message = str(_pick_ci(candidate, "message", "Message") or "").strip().lower()
        success = _pick_ci(candidate, "success", "Success")
        code = str(_pick_ci(candidate, "code", "Code", "errorCode", "ErrorCode", "error_code") or "").strip()
        if status in {"error", "failed", "fail", "unavailable"}:
            return candidate
        if status and status not in {"success", "ok", "0", "200"}:
            return candidate
        if isinstance(success, bool) and not success:
            return candidate
        if code and code not in {"0", "200", "OK", "ok"} and (message or status):
            return candidate
    return None


def _has_ssi_error(payload: Any) -> bool:
    return _ssi_error_record(payload) is not None


def _is_rate_limited_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    failure_class = str(payload.get("failure_class") or "").strip().lower()
    code = str(payload.get("code") or "").strip()
    http_status = str(payload.get("http_status") or "").strip()
    return failure_class == "rate_limited" or code == "429" or http_status == "429"


def _should_retry_param_variant(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if _is_rate_limited_payload(payload):
        return False
    error_type = str(payload.get("error_type") or "").strip().lower()
    failure_class = str(payload.get("failure_class") or "").strip().lower()
    if failure_class in {"auth_failed", "permission_denied", "network_error", "timeout", "parse_failed"}:
        return False
    return error_type == "ssi_error"


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

    _daily_ohlc_rate_limit_lock = RLock()
    _daily_ohlc_rate_limit_cooldowns: Dict[Tuple[str, str], _RateLimitCooldown] = {}
    _intraday_rate_limit_lock = RLock()
    _intraday_rate_limit_cooldowns: Dict[Tuple[str, str], _RateLimitCooldown] = {}

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
        streaming_realtime_enabled: Optional[bool] = None,
        streaming_realtime_cache_ttl_seconds: Optional[int] = None,
        streaming_realtime_channel_template: Optional[str] = None,
        streaming_realtime_stream_url: Optional[str] = None,
        streaming_realtime_idle_timeout_seconds: Optional[int] = None,
        streaming_realtime_reconnect_enabled: Optional[bool] = None,
        streaming_realtime_reconnect_initial_delay_seconds: Optional[int] = None,
        streaming_realtime_reconnect_max_delay_seconds: Optional[int] = None,
        streaming_realtime_reconnect_max_attempts: Optional[int] = None,
        trade_tape_buffer_size: Optional[int] = None,
        trade_tape_ttl_seconds: Optional[int] = None,
        streaming_realtime_client_factory: Optional[Callable[[], SsiRealtimeStreamClient]] = None,
        streaming_realtime_manager: Optional[SsiStreamingRealtimeManager] = None,
        daily_ohlc_rate_limit_cooldown_seconds: Optional[int] = None,
        intraday_rate_limit_cooldown_seconds: Optional[int] = None,
        monotonic_clock: Optional[Callable[[], float]] = None,
        utcnow: Optional[Callable[[], datetime]] = None,
        request_delay_seconds: float = 0,
        index_request_delay_seconds: float = DEFAULT_INDEX_REQUEST_DELAY_SECONDS,
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
        configured_daily_ohlc_cooldown = getattr(config, "ssi_daily_ohlc_rate_limit_cooldown_seconds", None)
        if daily_ohlc_rate_limit_cooldown_seconds is not None:
            daily_ohlc_cooldown_seconds = daily_ohlc_rate_limit_cooldown_seconds
        elif configured_daily_ohlc_cooldown is not None:
            daily_ohlc_cooldown_seconds = configured_daily_ohlc_cooldown
        else:
            daily_ohlc_cooldown_seconds = parse_env_int(
                os.getenv("SSI_DAILY_OHLC_RATE_LIMIT_COOLDOWN_SECONDS"),
                DEFAULT_DAILY_OHLC_RATE_LIMIT_COOLDOWN_SECONDS,
                field_name="SSI_DAILY_OHLC_RATE_LIMIT_COOLDOWN_SECONDS",
                minimum=0,
            )
        self.daily_ohlc_rate_limit_cooldown_seconds = max(0, int(daily_ohlc_cooldown_seconds or 0))
        self.intraday_enabled = (
            bool(intraday_enabled)
            if intraday_enabled is not None
            else bool(getattr(config, "ssi_fastconnect_intraday_enabled", parse_env_bool(os.getenv("SSI_FASTCONNECT_INTRADAY_ENABLED"), default=True)))
        )
        configured_intraday_cooldown = getattr(config, "ssi_intraday_rate_limit_cooldown_seconds", None)
        if intraday_rate_limit_cooldown_seconds is not None:
            cooldown_seconds = intraday_rate_limit_cooldown_seconds
        elif configured_intraday_cooldown is not None:
            cooldown_seconds = configured_intraday_cooldown
        else:
            cooldown_seconds = parse_env_int(
                os.getenv("SSI_INTRADAY_RATE_LIMIT_COOLDOWN_SECONDS"),
                DEFAULT_INTRADAY_RATE_LIMIT_COOLDOWN_SECONDS,
                field_name="SSI_INTRADAY_RATE_LIMIT_COOLDOWN_SECONDS",
                minimum=0,
            )
        self.intraday_rate_limit_cooldown_seconds = max(0, int(cooldown_seconds or 0))
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
        self.streaming_realtime_enabled = (
            bool(streaming_realtime_enabled)
            if streaming_realtime_enabled is not None
            else bool(
                getattr(
                    config,
                    "ssi_streaming_realtime_enabled",
                    parse_env_bool(os.getenv("SSI_STREAMING_REALTIME_ENABLED"), default=False),
                )
            )
        )
        self.streaming_realtime_cache_ttl_seconds = int(
            streaming_realtime_cache_ttl_seconds
            if streaming_realtime_cache_ttl_seconds is not None
            else getattr(config, "ssi_streaming_realtime_cache_ttl_seconds", None)
            or parse_env_int(
                os.getenv("SSI_STREAMING_REALTIME_CACHE_TTL_SECONDS"),
                DEFAULT_STREAMING_REALTIME_CACHE_TTL_SECONDS,
                field_name="SSI_STREAMING_REALTIME_CACHE_TTL_SECONDS",
                minimum=1,
            )
        )
        self.streaming_realtime_channel_template = (
            streaming_realtime_channel_template
            if streaming_realtime_channel_template is not None
            else getattr(config, "ssi_streaming_realtime_channel_template", None)
            or os.getenv("SSI_STREAMING_REALTIME_CHANNEL_TEMPLATE")
            or DEFAULT_STREAMING_REALTIME_CHANNEL_TEMPLATE
        ).strip() or DEFAULT_STREAMING_REALTIME_CHANNEL_TEMPLATE
        self.streaming_realtime_stream_url = (
            streaming_realtime_stream_url
            if streaming_realtime_stream_url is not None
            else getattr(config, "ssi_streaming_realtime_stream_url", None)
            or os.getenv("SSI_STREAMING_REALTIME_STREAM_URL")
            or DEFAULT_STREAMING_REALTIME_STREAM_URL
        ).strip() or DEFAULT_STREAMING_REALTIME_STREAM_URL
        self.streaming_realtime_idle_timeout_seconds = int(
            streaming_realtime_idle_timeout_seconds
            if streaming_realtime_idle_timeout_seconds is not None
            else getattr(config, "ssi_streaming_realtime_idle_timeout_seconds", None)
            or parse_env_int(
                os.getenv("SSI_STREAMING_REALTIME_IDLE_TIMEOUT_SECONDS"),
                DEFAULT_STREAMING_REALTIME_IDLE_TIMEOUT_SECONDS,
                field_name="SSI_STREAMING_REALTIME_IDLE_TIMEOUT_SECONDS",
                minimum=1,
            )
        )
        self.streaming_realtime_reconnect_enabled = (
            bool(streaming_realtime_reconnect_enabled)
            if streaming_realtime_reconnect_enabled is not None
            else bool(
                getattr(
                    config,
                    "ssi_streaming_realtime_reconnect_enabled",
                    parse_env_bool(os.getenv("SSI_STREAMING_REALTIME_RECONNECT_ENABLED"), default=True),
                )
            )
        )
        self.streaming_realtime_reconnect_initial_delay_seconds = int(
            streaming_realtime_reconnect_initial_delay_seconds
            if streaming_realtime_reconnect_initial_delay_seconds is not None
            else getattr(config, "ssi_streaming_realtime_reconnect_initial_delay_seconds", None)
            or parse_env_int(
                os.getenv("SSI_STREAMING_REALTIME_RECONNECT_INITIAL_DELAY_SECONDS"),
                DEFAULT_STREAMING_REALTIME_RECONNECT_INITIAL_DELAY_SECONDS,
                field_name="SSI_STREAMING_REALTIME_RECONNECT_INITIAL_DELAY_SECONDS",
                minimum=1,
            )
        )
        self.streaming_realtime_reconnect_max_delay_seconds = int(
            streaming_realtime_reconnect_max_delay_seconds
            if streaming_realtime_reconnect_max_delay_seconds is not None
            else getattr(config, "ssi_streaming_realtime_reconnect_max_delay_seconds", None)
            or parse_env_int(
                os.getenv("SSI_STREAMING_REALTIME_RECONNECT_MAX_DELAY_SECONDS"),
                DEFAULT_STREAMING_REALTIME_RECONNECT_MAX_DELAY_SECONDS,
                field_name="SSI_STREAMING_REALTIME_RECONNECT_MAX_DELAY_SECONDS",
                minimum=1,
            )
        )
        self.streaming_realtime_reconnect_max_attempts = int(
            streaming_realtime_reconnect_max_attempts
            if streaming_realtime_reconnect_max_attempts is not None
            else getattr(config, "ssi_streaming_realtime_reconnect_max_attempts", None)
            or parse_env_int(
                os.getenv("SSI_STREAMING_REALTIME_RECONNECT_MAX_ATTEMPTS"),
                0,
                field_name="SSI_STREAMING_REALTIME_RECONNECT_MAX_ATTEMPTS",
                minimum=0,
            )
        )
        self.trade_tape_buffer_size = int(
            trade_tape_buffer_size
            if trade_tape_buffer_size is not None
            else getattr(config, "ssi_trade_tape_buffer_size", None)
            or parse_env_int(
                os.getenv("SSI_TRADE_TAPE_BUFFER_SIZE"),
                DEFAULT_TRADE_TAPE_BUFFER_SIZE,
                field_name="SSI_TRADE_TAPE_BUFFER_SIZE",
                minimum=1,
            )
        )
        self.trade_tape_ttl_seconds = int(
            trade_tape_ttl_seconds
            if trade_tape_ttl_seconds is not None
            else getattr(config, "ssi_trade_tape_ttl_seconds", None)
            or parse_env_int(
                os.getenv("SSI_TRADE_TAPE_TTL_SECONDS"),
                DEFAULT_TRADE_TAPE_TTL_SECONDS,
                field_name="SSI_TRADE_TAPE_TTL_SECONDS",
                minimum=1,
            )
        )
        self._streaming_realtime_client_factory_supplied = streaming_realtime_client_factory is not None
        self._streaming_realtime_manager_supplied = streaming_realtime_manager is not None
        if streaming_realtime_client_factory is None and self.streaming_realtime_enabled:
            streaming_realtime_client_factory = self._build_official_streaming_realtime_client
        self.streaming_realtime_manager = streaming_realtime_manager or SsiStreamingRealtimeManager(
            enabled=self.streaming_realtime_enabled,
            cache=RealtimeSnapshotCache(self.streaming_realtime_cache_ttl_seconds),
            order_book_cache=OrderBookCache(DEFAULT_ORDER_BOOK_TTL_SECONDS),
            foreign_room_cache=ForeignRoomCache(DEFAULT_FOREIGN_ROOM_TTL_SECONDS),
            market_index_cache=MarketIndexPulseCache(DEFAULT_MARKET_INDEX_TTL_SECONDS),
            trade_tape_cache=TradeTapeEventCache(
                self.trade_tape_buffer_size,
                self.trade_tape_ttl_seconds,
            ),
            session_status_cache=SessionStatusCache(),
            parser=self.normalize_streaming_realtime_messages,
            client_factory=streaming_realtime_client_factory,
            channel_template=self.streaming_realtime_channel_template,
            trade_tape_enabled=self.trade_tape_enabled,
            market_index_codes=DEFAULT_MARKET_INDEX_CODES,
            idle_timeout_seconds=self.streaming_realtime_idle_timeout_seconds,
            reconnect_enabled=self.streaming_realtime_reconnect_enabled,
            reconnect_initial_delay_seconds=self.streaming_realtime_reconnect_initial_delay_seconds,
            reconnect_max_delay_seconds=self.streaming_realtime_reconnect_max_delay_seconds,
            reconnect_max_attempts=self.streaming_realtime_reconnect_max_attempts,
        )
        self.session = session or requests.Session()
        self.request_delay_seconds = max(0.0, float(request_delay_seconds or 0))
        self.index_request_delay_seconds = max(0.0, float(index_request_delay_seconds or 0))
        self._monotonic_clock = monotonic_clock or time.monotonic
        self._utcnow = utcnow or (lambda: datetime.now(timezone.utc))
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._last_index_request_at: Optional[float] = None
        self._cache: Dict[Tuple[str, Tuple[Tuple[str, Any], ...]], _CacheEntry] = {}

    def _build_official_streaming_realtime_client(self) -> SsiRealtimeStreamClient:
        return OfficialSsiRealtimeStreamClient(
            consumer_id=self.consumer_id,
            consumer_secret=self.consumer_secret,
            base_url=self.base_url,
            stream_url=self.streaming_realtime_stream_url,
        )

    @classmethod
    def clear_daily_ohlc_rate_limit_cooldowns(cls) -> None:
        with cls._daily_ohlc_rate_limit_lock:
            cls._daily_ohlc_rate_limit_cooldowns.clear()

    def _daily_ohlc_rate_limit_cooldown_key(self, symbol: str) -> Tuple[str, str]:
        parsed_base_url = urlsplit(str(self.base_url or "").strip())
        host = str(parsed_base_url.hostname or "").strip().lower()
        try:
            port = parsed_base_url.port
        except ValueError:
            port = None
        authority = f"{host}:{port}" if host and port else host
        path = str(parsed_base_url.path or "").strip().lower().rstrip("/")
        normalized_base_url = f"{parsed_base_url.scheme.lower()}://{authority}{path}" if authority else "ssi-fastconnect"
        normalized_symbol = str(symbol or "").strip().upper()
        return normalized_base_url, normalized_symbol

    def _get_daily_ohlc_rate_limit_cooldown(
        self,
        key: Tuple[str, str],
    ) -> Optional[_RateLimitCooldown]:
        now = self._monotonic_clock()
        with self._daily_ohlc_rate_limit_lock:
            cooldown = self._daily_ohlc_rate_limit_cooldowns.get(key)
            if cooldown and cooldown.expires_at > now:
                return cooldown
            if cooldown:
                self._daily_ohlc_rate_limit_cooldowns.pop(key, None)
        return None

    def _record_daily_ohlc_rate_limit_cooldown(
        self,
        key: Tuple[str, str],
    ) -> Optional[_RateLimitCooldown]:
        cooldown_seconds = self.daily_ohlc_rate_limit_cooldown_seconds
        if cooldown_seconds <= 0:
            return None

        now = self._monotonic_clock()
        try:
            cooldown_until = (self._utcnow() + timedelta(seconds=cooldown_seconds)).isoformat()
        except Exception:
            cooldown_until = None
        cooldown = _RateLimitCooldown(
            expires_at=now + cooldown_seconds,
            cooldown_until=cooldown_until,
        )
        with self._daily_ohlc_rate_limit_lock:
            self._daily_ohlc_rate_limit_cooldowns[key] = cooldown
        return cooldown

    def _daily_ohlc_cooldown_remaining_seconds(self, cooldown: _RateLimitCooldown) -> int:
        remaining = max(0.0, cooldown.expires_at - self._monotonic_clock())
        return int(remaining) if remaining == int(remaining) else int(remaining) + 1

    def _with_daily_ohlc_cooldown_diagnostics(
        self,
        payload: Dict[str, Any],
        *,
        cooldown: _RateLimitCooldown,
        active: bool,
        recorded: bool,
    ) -> Dict[str, Any]:
        result = dict(payload)
        diagnostics = dict(result.get("diagnostics") or {})
        diagnostics.update(
            {
                "cooldown_active": bool(active),
                "cooldown_recorded": bool(recorded),
                "cooldown_seconds": self.daily_ohlc_rate_limit_cooldown_seconds,
                "cooldown_remaining_seconds": self._daily_ohlc_cooldown_remaining_seconds(cooldown),
            }
        )
        if cooldown.cooldown_until:
            diagnostics["cooldown_until"] = cooldown.cooldown_until
        result["diagnostics"] = diagnostics
        return result

    def _daily_ohlc_cooldown_payload(
        self,
        *,
        symbol: str,
        params: Dict[str, Any],
        cooldown: _RateLimitCooldown,
    ) -> Dict[str, Any]:
        payload = {
            "status": "unavailable",
            "source": SSI_SOURCE,
            "symbol": symbol,
            "reason": DAILY_OHLC_RATE_LIMIT_COOLDOWN_REASON,
            "failure_class": "rate_limited",
            "rows": [],
            "count": 0,
            "diagnostics": {
                "endpoint": "DailyOhlc",
                "symbol": symbol,
                "from_date": params.get("fromDate") or params.get("Fromdate"),
                "to_date": params.get("toDate") or params.get("Todate"),
                "pageIndex": params.get("pageIndex"),
                "pageSize": params.get("pageSize"),
                "ascending": params.get("ascending"),
            },
        }
        return self._with_daily_ohlc_cooldown_diagnostics(
            payload,
            cooldown=cooldown,
            active=True,
            recorded=False,
        )

    @classmethod
    def clear_intraday_rate_limit_cooldowns(cls) -> None:
        with cls._intraday_rate_limit_lock:
            cls._intraday_rate_limit_cooldowns.clear()

    @staticmethod
    def _intraday_rate_limit_cooldown_key(symbol: str, interval: Optional[str]) -> Tuple[str, str]:
        normalized_symbol = str(symbol or "").strip().upper()
        normalized_interval = str(interval or "").strip().lower() or "default"
        return normalized_symbol, normalized_interval

    def _get_intraday_rate_limit_cooldown(
        self,
        key: Tuple[str, str],
    ) -> Optional[_RateLimitCooldown]:
        now = self._monotonic_clock()
        with self._intraday_rate_limit_lock:
            cooldown = self._intraday_rate_limit_cooldowns.get(key)
            if cooldown and cooldown.expires_at > now:
                return cooldown
            if cooldown:
                self._intraday_rate_limit_cooldowns.pop(key, None)
        return None

    def _record_intraday_rate_limit_cooldown(
        self,
        key: Tuple[str, str],
    ) -> Optional[_RateLimitCooldown]:
        cooldown_seconds = self.intraday_rate_limit_cooldown_seconds
        if cooldown_seconds <= 0:
            return None

        now = self._monotonic_clock()
        try:
            cooldown_until = (self._utcnow() + timedelta(seconds=cooldown_seconds)).isoformat()
        except Exception:
            cooldown_until = None
        cooldown = _RateLimitCooldown(
            expires_at=now + cooldown_seconds,
            cooldown_until=cooldown_until,
        )
        with self._intraday_rate_limit_lock:
            self._intraday_rate_limit_cooldowns[key] = cooldown
        return cooldown

    def _intraday_cooldown_remaining_seconds(self, cooldown: _RateLimitCooldown) -> int:
        remaining = max(0.0, cooldown.expires_at - self._monotonic_clock())
        return int(remaining) if remaining == int(remaining) else int(remaining) + 1

    @staticmethod
    def _is_rate_limited_payload(payload: Dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}
        failure_class = payload.get("failure_class") or diagnostics.get("failure_class")
        return str(failure_class or "").strip().lower() == "rate_limited"

    def _with_intraday_cooldown_diagnostics(
        self,
        payload: Dict[str, Any],
        *,
        cooldown: _RateLimitCooldown,
        active: bool,
        recorded: bool,
    ) -> Dict[str, Any]:
        result = dict(payload)
        diagnostics = dict(result.get("diagnostics") or {})
        diagnostics.update(
            {
                "cooldown_active": bool(active),
                "cooldown_recorded": bool(recorded),
                "cooldown_seconds": self.intraday_rate_limit_cooldown_seconds,
                "cooldown_remaining_seconds": self._intraday_cooldown_remaining_seconds(cooldown),
            }
        )
        if cooldown.cooldown_until:
            diagnostics["cooldown_until"] = cooldown.cooldown_until
        result["diagnostics"] = diagnostics
        return result

    def _intraday_cooldown_payload(
        self,
        *,
        symbol: str,
        params: Dict[str, Any],
        public_limit: int,
        interval: Optional[str],
        cooldown: _RateLimitCooldown,
    ) -> Dict[str, Any]:
        payload = {
            "status": "unavailable",
            "source": SSI_SOURCE,
            "symbol": symbol,
            "reason": INTRADAY_RATE_LIMIT_COOLDOWN_REASON,
            "failure_class": "rate_limited",
            "rows": [],
            "count": 0,
        }
        payload = self._with_intraday_failure_diagnostics(
            payload,
            params=params,
            public_limit=public_limit,
            interval=interval,
        )
        return self._with_intraday_cooldown_diagnostics(
            payload,
            cooldown=cooldown,
            active=True,
            recorded=False,
        )

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
        except requests.exceptions.Timeout:
            return {
                **_unavailable(REQUEST_FAILED_REASON),
                "error_type": "timeout",
                "failure_class": "timeout",
            }
        except requests.exceptions.ConnectionError:
            return {
                **_unavailable(REQUEST_FAILED_REASON),
                "error_type": "connection_error",
                "failure_class": "network_error",
            }
        except requests.exceptions.RequestException:
            return {
                **_unavailable(REQUEST_FAILED_REASON),
                "error_type": "request_error",
                "failure_class": "network_error",
            }

        payload = self._parse_response(response)
        if isinstance(payload, dict) and payload.get("status") == "unavailable":
            return payload

        token = _token_from_payload(payload)
        if not token:
            return {
                **_unavailable(REQUEST_FAILED_REASON),
                "error_type": "auth_response_missing_token",
                "failure_class": "auth_failed",
            }

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
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        normalized_symbol = str(symbol or "").strip().upper()
        params = self._date_params({"symbol": normalized_symbol}, from_date, to_date, limit)
        if not self.enabled:
            return _unavailable(DISABLED_REASON)
        if not self._has_credentials():
            return _unavailable(MISSING_CREDENTIALS_REASON)
        cooldown_key = self._daily_ohlc_rate_limit_cooldown_key(normalized_symbol)
        active_cooldown = self._get_daily_ohlc_rate_limit_cooldown(cooldown_key)
        if active_cooldown:
            return self._daily_ohlc_cooldown_payload(
                symbol=normalized_symbol,
                params=params,
                cooldown=active_cooldown,
            )

        payload = self._cached_normalized(
            "DailyOhlc",
            params,
            limit,
            lambda row: self._map_daily_ohlcv(row),
            extra={"symbol": normalized_symbol},
            param_variants=[self._alternate_param_case(params)],
            required_any=("date", "open", "high", "low", "close", "volume", "value"),
            retry_unavailable_variants=True,
            force_refresh=force_refresh,
        )
        payload = self._empty_as_unavailable(
            payload,
            reason="SSI DailyOhlc returned no rows.",
            failure_class="empty_response",
            diagnostics={
                "endpoint": "DailyOhlc",
                "symbol": normalized_symbol,
                "from_date": params.get("fromDate") or params.get("Fromdate"),
                "to_date": params.get("toDate") or params.get("Todate"),
                "pageIndex": params.get("pageIndex"),
                "pageSize": params.get("pageSize"),
                "ascending": params.get("ascending"),
            },
        )
        if self._is_rate_limited_payload(payload):
            cooldown = self._record_daily_ohlc_rate_limit_cooldown(cooldown_key)
            if cooldown:
                payload = self._with_daily_ohlc_cooldown_diagnostics(
                    payload,
                    cooldown=cooldown,
                    active=False,
                    recorded=True,
                )
        return payload

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
        force_refresh: bool = False,
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
            force_refresh=force_refresh,
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

        normalized_symbol = str(symbol or "").strip().upper()
        normalized_interval = str(interval).strip() if interval else None
        params: Dict[str, Any] = {"symbol": normalized_symbol}
        if normalized_interval:
            params["timeFrame"] = normalized_interval
        public_limit = max(int(limit or 0), 0)
        params = self._date_params(params, from_date, to_date, SSI_PAGE_SIZE)
        if not self.enabled:
            return self._with_intraday_failure_diagnostics(
                {
                    **_unavailable(DISABLED_REASON),
                    "rows": [],
                    "count": 0,
                },
                params=params,
                public_limit=public_limit,
                interval=normalized_interval,
            )
        if not self._has_credentials():
            return self._with_intraday_failure_diagnostics(
                {
                    **_unavailable(MISSING_CREDENTIALS_REASON),
                    "rows": [],
                    "count": 0,
                },
                params=params,
                public_limit=public_limit,
                interval=normalized_interval,
            )
        cooldown_key = self._intraday_rate_limit_cooldown_key(normalized_symbol, normalized_interval)
        active_cooldown = self._get_intraday_rate_limit_cooldown(cooldown_key)
        if active_cooldown:
            return self._intraday_cooldown_payload(
                symbol=normalized_symbol,
                params=params,
                public_limit=public_limit,
                interval=normalized_interval,
                cooldown=active_cooldown,
            )

        variants = [self._alternate_param_case(params)]
        if normalized_interval:
            for interval_key in ("interval", "resolution", "timeframe", "TimeFrame"):
                variant = dict(params)
                variant.pop("timeFrame", None)
                variant[interval_key] = normalized_interval
                variants.append(variant)
                variants.append(self._alternate_param_case(variant))
        payload = self._cached_paged_normalized(
            "IntradayOhlc",
            params,
            public_limit,
            lambda row: self._map_intraday_ohlcv(row, normalized_symbol),
            extra={"symbol": normalized_symbol, "interval": normalized_interval},
            param_variants=variants,
            required_any=("date_time", "timestamp", "open", "high", "low", "close", "volume"),
        )
        payload = self._empty_as_unavailable(
            payload,
            reason="SSI IntradayOhlc returned no candles.",
            failure_class="empty_response",
        )
        payload = self._with_intraday_failure_diagnostics(
            payload,
            params=params,
            public_limit=public_limit,
            interval=normalized_interval,
        )
        if self._is_rate_limited_payload(payload):
            cooldown = self._record_intraday_rate_limit_cooldown(cooldown_key)
            if cooldown:
                payload = self._with_intraday_cooldown_diagnostics(
                    payload,
                    cooldown=cooldown,
                    active=False,
                    recorded=True,
                )
        return payload

    def get_completed_intraday_1m(
        self,
        symbol: str,
        trading_date: str,
    ) -> Dict[str, Any]:
        """Fetch one completed SSI IntradayOhlc date with one fixed request.

        This narrow chart-history path intentionally does not reuse the compact
        intraday pulse paging, parameter variants, retries, or cache.
        """
        normalized_symbol = str(symbol or "").strip().upper()
        provider_date = format_ssi_date(trading_date)
        params: Dict[str, Any] = {
            "symbol": normalized_symbol,
            "fromDate": provider_date,
            "toDate": provider_date,
            "pageIndex": 1,
            "pageSize": 1000,
            "ascending": True,
            "resolution": 1,
        }
        if not self.intraday_enabled:
            return {
                "status": "unavailable",
                "source": SSI_SOURCE,
                "reason": INTRADAY_DISABLED_REASON,
                "rows": [],
                "count": 0,
            }

        payload = self._request("IntradayOhlc", params)
        if isinstance(payload, dict) and payload.get("status") == "unavailable":
            return {
                "status": "unavailable",
                "source": SSI_SOURCE,
                "reason": str(payload.get("reason") or REQUEST_FAILED_REASON),
                "failure_class": payload.get("failure_class"),
                "http_status": payload.get("http_status"),
                "code": payload.get("code"),
                "rows": [],
                "count": 0,
            }

        rows: List[Dict[str, Any]]
        data = _pick_ci(payload, "data")
        explicit_rows = _pick_ci(data, "items", "rows", "result") if isinstance(data, dict) else None
        if isinstance(explicit_rows, list):
            rows = [dict(row) for row in explicit_rows if isinstance(row, dict)]
        else:
            rows = _extract_rows(payload)
        return {
            "status": "ok",
            "source": SSI_SOURCE,
            "rows": rows,
            "count": len(rows),
            "total_record": _total_record(payload),
        }

    def get_realtime_snapshot(self, symbols: List[str]) -> Dict[str, Any]:
        """Return the current SSI realtime contract state.

        SSI realtime is a streaming contract. This request-time method only
        reads the disabled-by-default streaming manager/cache state; it never
        opens a long-running stream or probes speculative REST names.
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

        if not self.streaming_realtime_enabled:
            return {
                "status": "unavailable",
                "source": SSI_SOURCE,
                "reason": SSI_STREAMING_REALTIME_DISABLED_REASON,
                "requested_tickers": normalized_symbols,
                "quotes": [],
                "count": 0,
                "attempted_endpoints": [],
                "candidate_endpoints": [],
                "rest_candidate_endpoints": list(SSI_REALTIME_ENDPOINT_CANDIDATES),
                "endpoint_attempts": [],
                "discovery_status": "streaming_manager_disabled",
                "rest_status": "unsupported",
                "streaming_status": "disabled",
                "streaming_data_types": list(SSI_REALTIME_QUOTE_STREAMING_DATA_TYPES),
                "parsed_streaming_rows": 0,
                "cache_status": "disabled",
                "manager_state": "disabled",
                "diagnostics": {
                    "manager_state": "disabled",
                    "streaming_status": "disabled",
                    "cache_status": "disabled",
                    "live_adapter_status": "not_enabled",
                    "parser_rows_observed": 0,
                },
            }

        if (
            not self._streaming_realtime_manager_supplied
            and (not self.consumer_id or not self.consumer_secret or not self.streaming_realtime_stream_url)
        ):
            return {
                "status": "unavailable",
                "source": SSI_SOURCE,
                "reason": SSI_STREAMING_REALTIME_CONFIG_INCOMPLETE_REASON,
                "requested_tickers": normalized_symbols,
                "quotes": [],
                "count": 0,
                "attempted_endpoints": [],
                "candidate_endpoints": [],
                "rest_candidate_endpoints": list(SSI_REALTIME_ENDPOINT_CANDIDATES),
                "endpoint_attempts": [],
                "discovery_status": "streaming_configuration_incomplete",
                "rest_status": "unsupported",
                "streaming_status": "configuration_incomplete",
                "streaming_data_types": list(SSI_REALTIME_QUOTE_STREAMING_DATA_TYPES),
                "parsed_streaming_rows": 0,
                "cache_status": "unavailable",
                "manager_state": self.streaming_realtime_manager.state,
                "diagnostics": {
                    "manager_state": self.streaming_realtime_manager.state,
                    "streaming_status": "configuration_incomplete",
                    "cache_status": "unavailable",
                    "live_adapter_status": "configuration_incomplete",
                    "parser_rows_observed": 0,
                },
            }

        if (
            not self._streaming_realtime_client_factory_supplied
            and not self._streaming_realtime_manager_supplied
            and importlib.util.find_spec("ssi_fc_data") is None
        ):
            return {
                "status": "unavailable",
                "source": SSI_SOURCE,
                "reason": SSI_STREAMING_REALTIME_PACKAGE_UNAVAILABLE_REASON,
                "requested_tickers": normalized_symbols,
                "quotes": [],
                "count": 0,
                "attempted_endpoints": [],
                "candidate_endpoints": [],
                "rest_candidate_endpoints": list(SSI_REALTIME_ENDPOINT_CANDIDATES),
                "endpoint_attempts": [],
                "discovery_status": "streaming_package_unavailable",
                "rest_status": "unsupported",
                "streaming_status": "package_unavailable",
                "streaming_data_types": list(SSI_REALTIME_QUOTE_STREAMING_DATA_TYPES),
                "parsed_streaming_rows": 0,
                "cache_status": "unavailable",
                "manager_state": self.streaming_realtime_manager.state,
                "diagnostics": {
                    "manager_state": self.streaming_realtime_manager.state,
                    "streaming_status": "package_unavailable",
                    "cache_status": "unavailable",
                    "live_adapter_status": "package_unavailable",
                    "parser_rows_observed": 0,
                },
            }

        result = dict(self.streaming_realtime_manager.snapshot(normalized_symbols))
        diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
        result.setdefault("source", SSI_SOURCE)
        result.setdefault("requested_tickers", normalized_symbols)
        result.setdefault("quotes", [])
        result.setdefault("count", len(result.get("quotes") or []))
        result.setdefault("rest_candidate_endpoints", list(SSI_REALTIME_ENDPOINT_CANDIDATES))
        result.setdefault("endpoint_attempts", [])
        result.setdefault("discovery_status", result.get("streaming_status") or "streaming_manager")
        result.setdefault("streaming_data_types", list(SSI_REALTIME_QUOTE_STREAMING_DATA_TYPES))
        result.setdefault("runtime_status", diagnostics.get("runtime_status"))
        return result

    def get_order_book(self, symbol: str) -> Dict[str, Any]:
        """Return SSI X-QUOTE order-book rows from the streaming cache only.

        Request-time calls do not open streams, add subscriptions, or infer
        missing bid/ask levels.
        """
        normalized_symbol = str(symbol or "").strip().upper()
        base = {
            "source": SSI_SOURCE,
            "symbol": normalized_symbol,
            "order_book": None,
            "count": 0,
            "attempted_endpoints": [],
            "candidate_endpoints": [],
            "rest_status": "unsupported",
            "streaming_data_types": ["X-QUOTE"],
        }
        if not normalized_symbol:
            return {
                **base,
                "status": "unavailable",
                "reason": "No symbol requested",
                "streaming_status": "missing_symbol",
                "cache_status": "unavailable",
                "diagnostics": {
                    "streaming_status": "missing_symbol",
                    "cache_status": "unavailable",
                },
            }

        if not self.streaming_realtime_enabled:
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_DISABLED_REASON,
                "streaming_status": "disabled",
                "cache_status": "disabled",
                "manager_state": "disabled",
                "diagnostics": {
                    "manager_state": "disabled",
                    "streaming_status": "disabled",
                    "cache_status": "disabled",
                    "live_adapter_status": "not_enabled",
                    "order_book_rows_observed": 0,
                },
            }

        if (
            not self._streaming_realtime_manager_supplied
            and (not self.consumer_id or not self.consumer_secret or not self.streaming_realtime_stream_url)
        ):
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_CONFIG_INCOMPLETE_REASON,
                "streaming_status": "configuration_incomplete",
                "cache_status": "unavailable",
                "manager_state": self.streaming_realtime_manager.state,
                "diagnostics": {
                    "manager_state": self.streaming_realtime_manager.state,
                    "streaming_status": "configuration_incomplete",
                    "cache_status": "unavailable",
                    "live_adapter_status": "configuration_incomplete",
                    "order_book_rows_observed": 0,
                },
            }

        if (
            not self._streaming_realtime_client_factory_supplied
            and not self._streaming_realtime_manager_supplied
            and importlib.util.find_spec("ssi_fc_data") is None
        ):
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_PACKAGE_UNAVAILABLE_REASON,
                "streaming_status": "package_unavailable",
                "cache_status": "unavailable",
                "manager_state": self.streaming_realtime_manager.state,
                "diagnostics": {
                    "manager_state": self.streaming_realtime_manager.state,
                    "streaming_status": "package_unavailable",
                    "cache_status": "unavailable",
                    "live_adapter_status": "package_unavailable",
                    "order_book_rows_observed": 0,
                },
            }

        result = dict(self.streaming_realtime_manager.order_book(normalized_symbol))
        diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
        result.setdefault("source", SSI_SOURCE)
        result.setdefault("symbol", normalized_symbol)
        result.setdefault("order_book", None)
        result.setdefault("count", 1 if result.get("order_book") else 0)
        result.setdefault("attempted_endpoints", [])
        result.setdefault("candidate_endpoints", [])
        result.setdefault("rest_status", "unsupported")
        result.setdefault("streaming_data_types", ["X-QUOTE"])
        result.setdefault("runtime_status", diagnostics.get("runtime_status"))
        return result

    def normalize_streaming_realtime_messages(
        self,
        messages: List[Any],
        symbols: List[str],
    ) -> List[Dict[str, Any]]:
        """Normalize buffered SSI realtime stream messages for requested symbols.

        This parser is deterministic and side-effect free. It does not connect
        to SSI streaming or turn a single trade update into trade-tape history.
        """
        requested_symbols = [
            str(symbol or "").strip().upper()
            for symbol in symbols or []
            if str(symbol or "").strip()
        ]
        requested_set = set(requested_symbols)
        latest_by_symbol: Dict[str, Dict[str, Any]] = {}
        session_status_by_symbol: Dict[str, Dict[str, Any]] = {}
        foreign_room_by_symbol: Dict[str, Dict[str, Any]] = {}
        market_index_by_code: Dict[str, Dict[str, Any]] = {}

        for message in messages or []:
            parsed = self._parse_streaming_realtime_message(message)
            if not parsed:
                continue
            content = parsed["content"]
            symbol = str(
                _first_value(content, "Symbol", "Ticker", "StockCode", "SecurityCode", "Code", "IndexCode", "IndexID", "IndexId")
                or ""
            ).strip().upper()
            if not symbol or symbol not in requested_set:
                continue
            if parsed["data_type"] == "MI":
                row = self._map_streaming_market_index(content, fallback_index_code=symbol)
                if row:
                    market_index_by_code[symbol] = row
                continue
            if parsed["data_type"] == "F":
                row = self._map_streaming_session_status(content, fallback_symbol=symbol)
                if row:
                    session_status_by_symbol[symbol] = row
                continue
            if parsed["data_type"] == "R":
                row = self._map_streaming_foreign_room(content, fallback_symbol=symbol)
                if row:
                    foreign_room_by_symbol[symbol] = row
                continue
            row = self._map_streaming_realtime_snapshot(content, parsed["data_type"], fallback_symbol=symbol)
            if not row:
                continue
            latest_by_symbol[symbol] = self._merge_streaming_realtime_rows(latest_by_symbol.get(symbol), row)

        rows = [latest_by_symbol[symbol] for symbol in requested_symbols if symbol in latest_by_symbol]
        rows.extend(session_status_by_symbol[symbol] for symbol in requested_symbols if symbol in session_status_by_symbol)
        rows.extend(foreign_room_by_symbol[symbol] for symbol in requested_symbols if symbol in foreign_room_by_symbol)
        rows.extend(market_index_by_code[symbol] for symbol in requested_symbols if symbol in market_index_by_code)
        return rows

    def _parse_streaming_realtime_message(self, message: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(message, dict):
            return None

        envelope_type = self._normalize_streaming_data_type(
            _first_value(message, "DataType", "dataType", "datatype")
        )
        content = _first_value(message, "Content", "content")
        if isinstance(content, str):
            text = content.strip()
            if not text:
                return None
            if text.endswith(","):
                text = text[:-1].rstrip()
            try:
                content = json.loads(text)
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
        if not isinstance(content, dict):
            return None

        nested_type = self._normalize_streaming_data_type(_first_value(content, "RType", "rtype"))
        data_type = nested_type or envelope_type
        if data_type not in SSI_REALTIME_STREAMING_DATA_TYPES:
            return None
        return {"data_type": data_type, "envelope_type": envelope_type, "content": content}

    @staticmethod
    def _normalize_streaming_data_type(value: Any) -> Optional[str]:
        text = str(value or "").strip().upper()
        if not text:
            return None
        compact = text.replace("_", "-")
        aliases = {
            "QUOTE": "X-QUOTE",
            "XQUOTE": "X-QUOTE",
            "X-QUOTE": "X-QUOTE",
            "TRADE": "X-TRADE",
            "XTRADE": "X-TRADE",
            "X-TRADE": "X-TRADE",
            "X": "X",
            "F": "F",
            "R": "R",
            "MI": "MI",
            "MARKETINDEX": "MI",
            "MARKET-INDEX": "MI",
        }
        return aliases.get(compact)

    def _map_streaming_market_index(
        self,
        row: Dict[str, Any],
        *,
        fallback_index_code: str,
    ) -> Optional[Dict[str, Any]]:
        index_code = str(
            _first_value(row, "IndexCode", "IndexID", "IndexId", "Code", "indexCode")
            or fallback_index_code
            or ""
        ).strip().upper()
        if not index_code:
            return None

        def nonnegative(value: Any) -> Optional[float]:
            number = _to_float(value)
            if number is None or number < 0:
                return None
            return number

        index_value = nonnegative(_first_value(row, "IndexValue", "IndexVal", "indexValue", "indexVal"))
        estimated_index_value = nonnegative(_first_value(row, "IndexValEst", "EstimatedIndexValue", "indexValEst"))
        change = _to_float(_first_value(row, "Change", "change"))
        change_pct = _to_float(_first_value(row, "RatioChange", "ChangePercent", "change_pct", "ratioChange"))
        total_trades = nonnegative(_first_value(row, "TotalTrade", "totalTrade"))
        total_volume = nonnegative(_first_value(row, "TotalQtty", "TotalVolume", "totalQtty", "total_volume"))
        total_value = nonnegative(_first_value(row, "TotalValue", "totalValue"))
        advances = nonnegative(_first_value(row, "Advances", "advances"))
        unchanged = nonnegative(_first_value(row, "Nochanges", "NoChanges", "unchanged"))
        declines = nonnegative(_first_value(row, "Declines", "declines"))
        if not any(
            value is not None
            for value in (
                index_value,
                estimated_index_value,
                change,
                change_pct,
                total_trades,
                total_volume,
                total_value,
                advances,
                unchanged,
                declines,
            )
        ):
            return None

        trading_date = _first_value(row, "TradingDate", "Date", "tradingDate")
        time_value = _first_value(row, "Time", "TradingTime", "time", "tradingTime")
        combined_datetime = None
        if trading_date and time_value:
            combined_datetime = f"{trading_date} {time_value}"

        return {
            "index_code": index_code,
            "exchange": _safe_text(_first_value(row, "Exchange", "Market", "ExchangeCode", "exchange", "market")),
            "index_value": index_value,
            "estimated_index_value": estimated_index_value,
            "change": change,
            "change_pct": change_pct,
            "total_trades": total_trades,
            "total_volume": total_volume,
            "total_value": total_value,
            "advances": advances,
            "unchanged": unchanged,
            "declines": declines,
            "trading_date": _parse_date(trading_date),
            "time": _safe_text(time_value),
            "stream_timestamp": _parse_datetime(combined_datetime or time_value or trading_date),
            "stream_data_type": "MI",
            "r_type": _safe_text(_first_value(row, "RType", "rtype")) or "MI",
            "source": "SSI MI market-index stream",
            "channel_format_status": "needs_live_proof",
            "value_semantics_status": "needs_live_proof",
        }

    def _map_streaming_foreign_room(
        self,
        row: Dict[str, Any],
        *,
        fallback_symbol: str,
    ) -> Optional[Dict[str, Any]]:
        symbol = str(
            _first_value(row, "Symbol", "Ticker", "StockCode", "SecurityCode", "Code")
            or fallback_symbol
            or ""
        ).strip().upper()
        if not symbol:
            return None

        def nonnegative(value: Any) -> Optional[float]:
            number = _to_float(value)
            if number is None or number < 0:
                return None
            return number

        total_room = nonnegative(_first_value(row, "TotalRoom", "totalRoom", "total_room"))
        current_room = nonnegative(_first_value(row, "CurrentRoom", "currentRoom", "current_room"))
        foreign_buy_volume = nonnegative(_first_value(row, "FBuyVol", "fBuyVol", "f_buy_vol"))
        foreign_sell_volume = nonnegative(_first_value(row, "FSellVol", "fSellVol", "f_sell_vol"))
        foreign_buy_value = nonnegative(_first_value(row, "FBuyVal", "fBuyVal", "f_buy_val"))
        foreign_sell_value = nonnegative(_first_value(row, "FSellVal", "fSellVal", "f_sell_val"))
        if not any(
            value is not None
            for value in (
                total_room,
                current_room,
                foreign_buy_volume,
                foreign_sell_volume,
                foreign_buy_value,
                foreign_sell_value,
            )
        ):
            return None

        trading_date = _first_value(row, "TradingDate", "Date", "tradingDate")
        time_value = _first_value(row, "Time", "TradingTime", "time", "tradingTime")
        combined_datetime = None
        if trading_date and time_value:
            combined_datetime = f"{trading_date} {time_value}"

        return {
            "ticker": symbol,
            "symbol": symbol,
            "exchange": _safe_text(_first_value(row, "Exchange", "Market", "ExchangeCode", "exchange", "market")),
            "total_room": total_room,
            "current_room": current_room,
            "foreign_buy_volume": foreign_buy_volume,
            "foreign_sell_volume": foreign_sell_volume,
            "foreign_buy_value": foreign_buy_value,
            "foreign_sell_value": foreign_sell_value,
            "trading_date": _parse_date(trading_date),
            "time": _safe_text(time_value),
            "stream_timestamp": _parse_datetime(combined_datetime or time_value or trading_date),
            "stream_data_type": "R",
            "r_type": _safe_text(_first_value(row, "RType", "rtype")) or "R",
            "source": "SSI R foreign-room stream",
            "value_semantics_status": "needs_semantics_proof",
        }

    def _map_streaming_session_status(
        self,
        row: Dict[str, Any],
        *,
        fallback_symbol: str,
    ) -> Optional[Dict[str, Any]]:
        symbol = str(
            _first_value(row, "Symbol", "Ticker", "StockCode", "SecurityCode", "Code")
            or fallback_symbol
            or ""
        ).strip().upper()
        if not symbol:
            return None

        trading_session = _safe_text(
            _first_value(row, "TradingSession", "Session", "SessionCode", "tradingSession", "session")
        )
        trading_status = _safe_text(
            _first_value(row, "TradingStatus", "Status", "MarketStatus", "tradingStatus", "marketStatus")
        )
        trading_date = _first_value(row, "TradingDate", "Date", "tradingDate")
        time_value = _first_value(row, "Time", "TradingTime", "time", "tradingTime")
        exchange = _safe_text(_first_value(row, "Exchange", "Market", "ExchangeCode", "exchange", "market"))

        if not any((trading_session, trading_status, trading_date, time_value, exchange)):
            return None

        combined_datetime = None
        if trading_date and time_value:
            combined_datetime = f"{trading_date} {time_value}"

        return {
            "ticker": symbol,
            "symbol": symbol,
            "exchange": exchange,
            "trading_date": _parse_date(trading_date),
            "time": _safe_text(time_value),
            "trading_session": trading_session,
            "trading_status": trading_status,
            "stream_timestamp": _parse_datetime(combined_datetime or time_value or trading_date),
            "stream_data_type": "F",
            "r_type": _safe_text(_first_value(row, "RType", "rtype")) or "F",
            "source": "SSI F trading session/status stream",
        }

    def _map_streaming_realtime_snapshot(
        self,
        row: Dict[str, Any],
        data_type: str,
        *,
        fallback_symbol: str,
    ) -> Optional[Dict[str, Any]]:
        mapped = self._map_realtime_snapshot(row, fallback_symbol=fallback_symbol)
        last_price = _to_float(_first_value(row, "LastPrice", "lastPrice"))
        has_last_trade = data_type in {"X", "X-TRADE"} and last_price is not None
        bid_levels = mapped.get("bid_levels") or []
        ask_levels = mapped.get("ask_levels") or []
        if not has_last_trade and not bid_levels and not ask_levels:
            return None

        if not has_last_trade:
            mapped["price"] = None
            mapped["realtime_price"] = None
            mapped["snapshot_price"] = None
        else:
            mapped["price"] = last_price
            mapped["realtime_price"] = last_price
            mapped["snapshot_price"] = last_price

        trading_date = _first_value(row, "TradingDate", "Date", "tradingDate")
        time_value = _first_value(row, "Time", "TradingTime", "MatchedTime", "time", "tradingTime")
        combined_datetime = None
        if trading_date and time_value:
            combined_datetime = f"{trading_date} {time_value}"
        stream_timestamp = _parse_datetime(combined_datetime or time_value or trading_date)

        mapped.update(
            {
                "stream_data_type": data_type,
                "r_type": _safe_text(_first_value(row, "RType", "rtype")) or data_type,
                "has_last_trade": has_last_trade,
                "quote_only": data_type == "X-QUOTE" and not has_last_trade,
                "trading_date": _parse_date(trading_date),
                "time": _safe_text(time_value),
                "stream_timestamp": stream_timestamp,
                "last_volume": _to_float(_first_value(row, "LastVol", "LastVolume", "MatchedVolume", "MatchVolume")),
                "last_value": _to_float(_first_value(row, "LastValue", "LastVal", "MatchedValue", "MatchValue", "lastValue", "matchedValue")),
                "side_if_available": _safe_text(_first_value(row, "Side", "MatchType", "BuySell", "side", "matchType", "buySell")),
                "sequence_if_available": _safe_text(_first_value(row, "Sequence", "Seq", "Id", "ID", "sequence", "seq", "id")),
            }
        )
        return mapped

    @staticmethod
    def _merge_streaming_realtime_rows(
        existing: Optional[Dict[str, Any]],
        row: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not existing:
            return dict(row)
        merged = dict(existing)
        for key, value in row.items():
            if key in {"price", "realtime_price", "snapshot_price"} and not row.get("has_last_trade"):
                continue
            if key in {"has_last_trade", "quote_only"} and not row.get("has_last_trade"):
                continue
            if value not in (None, "", [], {}):
                merged[key] = value
        if row.get("has_last_trade"):
            merged["has_last_trade"] = True
            merged["quote_only"] = False
        return merged

    def get_trade_tape(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Return SSI trade tape rows from the streaming X-TRADE buffer only.

        Request-time calls must not open streams, add subscriptions, or probe
        speculative REST endpoint names. The background streaming lifecycle is
        the only producer for this optional trade-tape contract.
        """
        normalized_symbol = str(symbol or "").strip().upper()
        safe_limit = max(1, min(int(limit or self.trade_tape_buffer_size), self.trade_tape_buffer_size))
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

        if not self.streaming_realtime_enabled:
            return {
                "status": "unavailable",
                "source": SSI_SOURCE,
                "symbol": normalized_symbol,
                "reason": "SSI trade tape stream buffer disabled.",
                "trades": [],
                "count": 0,
                "attempted_endpoints": [],
                "candidate_endpoints": [],
                "rest_status": "unsupported",
                "streaming_status": "disabled",
                "cache_status": "disabled",
                "diagnostics": {
                    "streaming_status": "disabled",
                    "cache_status": "disabled",
                    "manager_state": "disabled",
                    "channel_type": "X-TRADE",
                    "trade_tape_buffer_size": self.trade_tape_buffer_size,
                    "trade_tape_ttl_seconds": self.trade_tape_ttl_seconds,
                },
            }

        result = dict(self.streaming_realtime_manager.trade_tape(normalized_symbol, safe_limit))
        result.setdefault("source", SSI_SOURCE)
        result.setdefault("symbol", normalized_symbol)
        result.setdefault("trades", [])
        result.setdefault("count", len(result.get("trades") or []))
        result.setdefault("attempted_endpoints", [])
        result.setdefault("candidate_endpoints", [])
        result.setdefault("rest_status", "unsupported")
        return result

    def get_session_status(self, symbol: str) -> Dict[str, Any]:
        """Return SSI F stream trading session/status from the streaming cache only.

        Request-time calls do not open streams, add subscriptions, or infer the
        business meaning of SSI session/status codes.
        """
        normalized_symbol = str(symbol or "").strip().upper()
        base = {
            "source": SSI_SOURCE,
            "symbol": normalized_symbol,
            "session_status": None,
            "count": 0,
            "attempted_endpoints": [],
            "candidate_endpoints": [],
            "rest_status": "unsupported",
            "streaming_data_types": ["F"],
        }
        if not normalized_symbol:
            return {
                **base,
                "status": "unavailable",
                "reason": "No symbol requested",
                "streaming_status": "missing_symbol",
                "cache_status": "unavailable",
                "diagnostics": {
                    "streaming_status": "missing_symbol",
                    "cache_status": "unavailable",
                },
            }

        if not self.streaming_realtime_enabled:
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_DISABLED_REASON,
                "streaming_status": "disabled",
                "cache_status": "disabled",
                "manager_state": "disabled",
                "diagnostics": {
                    "manager_state": "disabled",
                    "streaming_status": "disabled",
                    "cache_status": "disabled",
                    "live_adapter_status": "not_enabled",
                    "session_status_rows_observed": 0,
                },
            }

        if (
            not self._streaming_realtime_manager_supplied
            and (not self.consumer_id or not self.consumer_secret or not self.streaming_realtime_stream_url)
        ):
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_CONFIG_INCOMPLETE_REASON,
                "streaming_status": "configuration_incomplete",
                "cache_status": "unavailable",
                "manager_state": self.streaming_realtime_manager.state,
                "diagnostics": {
                    "manager_state": self.streaming_realtime_manager.state,
                    "streaming_status": "configuration_incomplete",
                    "cache_status": "unavailable",
                    "live_adapter_status": "configuration_incomplete",
                    "session_status_rows_observed": 0,
                },
            }

        if (
            not self._streaming_realtime_client_factory_supplied
            and not self._streaming_realtime_manager_supplied
            and importlib.util.find_spec("ssi_fc_data") is None
        ):
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_PACKAGE_UNAVAILABLE_REASON,
                "streaming_status": "package_unavailable",
                "cache_status": "unavailable",
                "manager_state": self.streaming_realtime_manager.state,
                "diagnostics": {
                    "manager_state": self.streaming_realtime_manager.state,
                    "streaming_status": "package_unavailable",
                    "cache_status": "unavailable",
                    "live_adapter_status": "package_unavailable",
                    "session_status_rows_observed": 0,
                },
            }

        result = dict(self.streaming_realtime_manager.session_status(normalized_symbol))
        diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
        result.setdefault("source", SSI_SOURCE)
        result.setdefault("symbol", normalized_symbol)
        result.setdefault("session_status", None)
        result.setdefault("count", 1 if result.get("session_status") else 0)
        result.setdefault("attempted_endpoints", [])
        result.setdefault("candidate_endpoints", [])
        result.setdefault("rest_status", "unsupported")
        result.setdefault("streaming_data_types", ["F"])
        result.setdefault("runtime_status", diagnostics.get("runtime_status"))
        return result

    def get_foreign_room(self, symbol: str) -> Dict[str, Any]:
        """Return SSI R foreign-room context from the streaming cache only.

        Request-time calls do not open streams, add subscriptions, probe REST
        endpoints, or mix R rows into DailyStockPrice foreign-flow enrichment.
        """
        normalized_symbol = str(symbol or "").strip().upper()
        base = {
            "source": SSI_SOURCE,
            "symbol": normalized_symbol,
            "foreign_room": None,
            "count": 0,
            "attempted_endpoints": [],
            "candidate_endpoints": [],
            "rest_status": "unsupported",
            "streaming_data_types": ["R"],
        }
        if not normalized_symbol:
            return {
                **base,
                "status": "unavailable",
                "reason": "No symbol requested",
                "streaming_status": "missing_symbol",
                "cache_status": "unavailable",
                "diagnostics": {
                    "streaming_status": "missing_symbol",
                    "cache_status": "unavailable",
                },
            }

        if not self.streaming_realtime_enabled:
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_DISABLED_REASON,
                "streaming_status": "disabled",
                "cache_status": "disabled",
                "manager_state": "disabled",
                "diagnostics": {
                    "manager_state": "disabled",
                    "streaming_status": "disabled",
                    "cache_status": "disabled",
                    "live_adapter_status": "not_enabled",
                    "foreign_room_rows_observed": 0,
                },
            }

        if (
            not self._streaming_realtime_manager_supplied
            and (not self.consumer_id or not self.consumer_secret or not self.streaming_realtime_stream_url)
        ):
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_CONFIG_INCOMPLETE_REASON,
                "streaming_status": "configuration_incomplete",
                "cache_status": "unavailable",
                "manager_state": self.streaming_realtime_manager.state,
                "diagnostics": {
                    "manager_state": self.streaming_realtime_manager.state,
                    "streaming_status": "configuration_incomplete",
                    "cache_status": "unavailable",
                    "live_adapter_status": "configuration_incomplete",
                    "foreign_room_rows_observed": 0,
                },
            }

        if (
            not self._streaming_realtime_client_factory_supplied
            and not self._streaming_realtime_manager_supplied
            and importlib.util.find_spec("ssi_fc_data") is None
        ):
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_PACKAGE_UNAVAILABLE_REASON,
                "streaming_status": "package_unavailable",
                "cache_status": "unavailable",
                "manager_state": self.streaming_realtime_manager.state,
                "diagnostics": {
                    "manager_state": self.streaming_realtime_manager.state,
                    "streaming_status": "package_unavailable",
                    "cache_status": "unavailable",
                    "live_adapter_status": "package_unavailable",
                    "foreign_room_rows_observed": 0,
                },
            }

        result = dict(self.streaming_realtime_manager.foreign_room(normalized_symbol))
        diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
        result.setdefault("source", SSI_SOURCE)
        result.setdefault("symbol", normalized_symbol)
        result.setdefault("foreign_room", None)
        result.setdefault("count", 1 if result.get("foreign_room") else 0)
        result.setdefault("attempted_endpoints", [])
        result.setdefault("candidate_endpoints", [])
        result.setdefault("rest_status", "unsupported")
        result.setdefault("streaming_data_types", ["R"])
        result.setdefault("runtime_status", diagnostics.get("runtime_status"))
        return result

    def get_market_index_pulse(self, index_codes: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        """Return SSI MI market-index pulse rows from the streaming cache only.

        Request-time calls do not open streams, add subscriptions, probe REST
        endpoints, or reconcile MI rows with REST DailyIndex rows.
        """
        requested_codes = [
            code
            for code in (
                str(value or "").strip().upper()
                for value in (index_codes or DEFAULT_MARKET_INDEX_CODES)
            )
            if code
        ]
        requested_codes = list(dict.fromkeys(requested_codes))[:10] or list(DEFAULT_MARKET_INDEX_CODES)
        base = {
            "source": SSI_SOURCE,
            "requested_index_codes": requested_codes,
            "market_index_pulse": [],
            "count": 0,
            "attempted_endpoints": [],
            "candidate_endpoints": [],
            "rest_status": "unsupported",
            "streaming_data_types": ["MI"],
            "channel_format_status": "needs_live_proof",
        }

        if not self.streaming_realtime_enabled:
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_DISABLED_REASON,
                "streaming_status": "disabled",
                "cache_status": "disabled",
                "manager_state": "disabled",
                "diagnostics": {
                    "manager_state": "disabled",
                    "streaming_status": "disabled",
                    "cache_status": "disabled",
                    "live_adapter_status": "not_enabled",
                    "market_index_rows_observed": 0,
                    "requested_index_codes": requested_codes,
                },
            }

        if (
            not self._streaming_realtime_manager_supplied
            and (not self.consumer_id or not self.consumer_secret or not self.streaming_realtime_stream_url)
        ):
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_CONFIG_INCOMPLETE_REASON,
                "streaming_status": "configuration_incomplete",
                "cache_status": "unavailable",
                "manager_state": self.streaming_realtime_manager.state,
                "diagnostics": {
                    "manager_state": self.streaming_realtime_manager.state,
                    "streaming_status": "configuration_incomplete",
                    "cache_status": "unavailable",
                    "live_adapter_status": "configuration_incomplete",
                    "market_index_rows_observed": 0,
                    "requested_index_codes": requested_codes,
                },
            }

        if (
            not self._streaming_realtime_client_factory_supplied
            and not self._streaming_realtime_manager_supplied
            and importlib.util.find_spec("ssi_fc_data") is None
        ):
            return {
                **base,
                "status": "unavailable",
                "reason": SSI_STREAMING_REALTIME_PACKAGE_UNAVAILABLE_REASON,
                "streaming_status": "package_unavailable",
                "cache_status": "unavailable",
                "manager_state": self.streaming_realtime_manager.state,
                "diagnostics": {
                    "manager_state": self.streaming_realtime_manager.state,
                    "streaming_status": "package_unavailable",
                    "cache_status": "unavailable",
                    "live_adapter_status": "package_unavailable",
                    "market_index_rows_observed": 0,
                    "requested_index_codes": requested_codes,
                },
            }

        result = dict(self.streaming_realtime_manager.market_index_pulse(requested_codes))
        diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
        result.setdefault("source", SSI_SOURCE)
        result.setdefault("requested_index_codes", requested_codes)
        result.setdefault("market_index_pulse", [])
        result.setdefault("count", len(result.get("market_index_pulse") or []))
        result.setdefault("attempted_endpoints", [])
        result.setdefault("candidate_endpoints", [])
        result.setdefault("rest_status", "unsupported")
        result.setdefault("streaming_data_types", ["MI"])
        result.setdefault("runtime_status", diagnostics.get("runtime_status"))
        result.setdefault("channel_format_status", "needs_live_proof")
        return result

    def get_index_list(self, market: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
        params = {"market": market.strip().upper()} if market else {}
        payload = self._cached_normalized(
            "IndexList",
            params,
            0,
            self._map_index_info,
            extra={"market": params.get("market")},
            param_variants=[self._alternate_param_case(params)] if params else None,
            required_any=("index_id", "index_code"),
            force_refresh=force_refresh,
        )
        return self._empty_as_unavailable(payload)

    def get_index_components(
        self,
        index_code: str,
        market: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        normalized_index = index_code.strip().upper()
        params: Dict[str, Any] = {
            "indexCode": normalized_index,
            "pageIndex": 1,
            "pageSize": 1000,
        }
        if market:
            params["market"] = market.strip().upper()
        payload = self._cached_normalized(
            "IndexComponents",
            params,
            0,
            lambda row: self._map_index_component(row, normalized_index),
            extra={"index_code": normalized_index, "market": params.get("market")},
            required_any=("symbol",),
            force_refresh=force_refresh,
            row_extractor=lambda provider_payload: _extract_index_component_rows(
                provider_payload,
                normalized_index,
            ),
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

        if endpoint in {"IndexList", "DailyIndex", "IndexComponents"}:
            now = self._monotonic_clock()
            if self._last_index_request_at is not None and self.index_request_delay_seconds > 0:
                remaining = self.index_request_delay_seconds - (now - self._last_index_request_at)
                if remaining > 0:
                    time.sleep(remaining)
            self._last_index_request_at = self._monotonic_clock()

        headers = {"Authorization": f"Bearer {self._access_token}"}
        try:
            response = self.session.get(
                f"{self.base_url}/{endpoint}",
                params=params or {},
                headers=headers,
                timeout=self.timeout_seconds,
            )
        except requests.exceptions.Timeout:
            return {
                **_unavailable(REQUEST_FAILED_REASON),
                "endpoint": endpoint,
                "error_type": "timeout",
                "failure_class": "timeout",
            }
        except requests.exceptions.ConnectionError:
            return {
                **_unavailable(REQUEST_FAILED_REASON),
                "endpoint": endpoint,
                "error_type": "connection_error",
                "failure_class": "network_error",
            }
        except requests.exceptions.RequestException:
            return {
                **_unavailable(REQUEST_FAILED_REASON),
                "endpoint": endpoint,
                "error_type": "request_error",
                "failure_class": "network_error",
            }

        return self._parse_response(response, endpoint=endpoint)

    def _parse_response(self, response: Any, endpoint: Optional[str] = None) -> Any:
        http_status = getattr(response, "status_code", 0)
        if http_status != 200:
            return {
                **_unavailable(REQUEST_FAILED_REASON),
                "endpoint": endpoint,
                "http_status": http_status,
                "error_type": "http_error",
                "failure_class": _classify_provider_failure(error_type="http_error", http_status=http_status),
            }
        try:
            payload = response.json()
        except (TypeError, ValueError):
            return {
                **_unavailable(REQUEST_FAILED_REASON),
                "endpoint": endpoint,
                "http_status": http_status,
                "error_type": "invalid_json",
                "failure_class": "parse_failed",
            }
        error_record = _ssi_error_record(payload)
        if error_record is not None:
            result = {
                **_unavailable(REQUEST_FAILED_REASON),
                "endpoint": endpoint,
                "http_status": http_status,
                "error_type": "ssi_error",
            }
            if isinstance(error_record, dict):
                code = _pick_ci(error_record, "code", "errorCode", "status", "Status")
                if code is not None:
                    result["code"] = str(code)[:80]
            result["failure_class"] = _classify_provider_failure(
                error_type="ssi_error",
                http_status=http_status,
                code=result.get("code"),
            )
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
        force_refresh: bool = False,
        row_extractor: Optional[Callable[[Any], List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        cache_key = (endpoint, tuple(sorted((params or {}).items())))
        if self.cache_ttl_seconds > 0 and not force_refresh:
            entry = self._cache.get(cache_key)
            if entry and entry.expires_at > time.time():
                return dict(entry.value)

        payload = self._request(endpoint, params=params)
        first_unavailable = payload if isinstance(payload, dict) and payload.get("status") == "unavailable" else None
        if first_unavailable and not retry_unavailable_variants:
            return payload
        if first_unavailable and not _should_retry_param_variant(first_unavailable):
            return first_unavailable

        extract_rows = row_extractor or _extract_rows
        rows = [] if first_unavailable else [mapper(row) for row in extract_rows(payload)]
        rows = [row for row in rows if row and _has_required_field(row, required_any)]
        if not rows:
            for variant_params in param_variants or []:
                if not variant_params or variant_params == params:
                    continue
                variant_payload = self._request(endpoint, params=variant_params)
                if isinstance(variant_payload, dict) and variant_payload.get("status") == "unavailable":
                    if self._is_rate_limited_payload(variant_payload):
                        return variant_payload
                    continue
                rows = [mapper(row) for row in extract_rows(variant_payload)]
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
    def _empty_as_unavailable(
        payload: Dict[str, Any],
        *,
        reason: str = REQUEST_FAILED_REASON,
        failure_class: Optional[str] = None,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if payload.get("status") != "ok":
            return payload
        if payload.get("count", 0) == 0:
            result = {
                **payload,
                "status": "unavailable",
                "reason": reason,
                "rows": [],
                "count": 0,
            }
            if failure_class:
                result["failure_class"] = failure_class
            if diagnostics:
                result["diagnostics"] = dict(diagnostics)
            return result
        return payload

    @staticmethod
    def _with_intraday_failure_diagnostics(
        payload: Dict[str, Any],
        *,
        params: Dict[str, Any],
        public_limit: int,
        interval: Optional[str],
    ) -> Dict[str, Any]:
        if not isinstance(payload, dict) or str(payload.get("status") or "").lower() not in {"unavailable", "disabled"}:
            return payload

        existing = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}
        diagnostics: Dict[str, Any] = {
            key: value
            for key, value in existing.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        }
        failure_class = payload.get("failure_class") or diagnostics.get("failure_class")
        if not failure_class:
            failure_class = _classify_provider_failure(
                error_type=payload.get("error_type"),
                http_status=payload.get("http_status"),
                code=payload.get("code") or diagnostics.get("provider_code"),
                reason=payload.get("reason"),
            )

        def set_diag(key: str, value: Any) -> None:
            text = _safe_diagnostic_text(value)
            if text is not None:
                diagnostics[key] = text

        diagnostics["failure_class"] = str(failure_class)
        diagnostics["endpoint"] = "IntradayOhlc"
        set_diag("http_status", payload.get("http_status"))
        set_diag("provider_code", payload.get("code") or diagnostics.get("provider_code"))
        set_diag("error_type", payload.get("error_type"))
        set_diag("symbol", params.get("symbol"))
        set_diag("from_date", params.get("fromDate") or params.get("Fromdate"))
        set_diag("to_date", params.get("toDate") or params.get("Todate"))
        set_diag("requested_timeframe", interval or params.get("timeFrame") or params.get("TimeFrame"))
        set_diag("pageIndex", params.get("pageIndex") or 1)
        set_diag("pageSize", params.get("pageSize") or SSI_PAGE_SIZE)
        set_diag("ascending", params.get("ascending"))
        set_diag("public_limit", public_limit)
        set_diag("request_page_size", payload.get("request_page_size") or SSI_PAGE_SIZE)

        result = dict(payload)
        result["failure_class"] = str(failure_class)
        result["diagnostics"] = diagnostics
        return result

    def _cached_paged_normalized(
        self,
        endpoint: str,
        params: Dict[str, Any],
        limit: int,
        mapper: Any,
        *,
        extra: Optional[Dict[str, Any]] = None,
        param_variants: Optional[List[Dict[str, Any]]] = None,
        required_any: Tuple[str, ...] = (),
        page_size: int = SSI_PAGE_SIZE,
    ) -> Dict[str, Any]:
        cache_params = {**(params or {}), "pageSize": int(page_size), "paged": True, "limit": int(limit or 0)}
        cache_key = (endpoint, tuple(sorted(cache_params.items())))
        if self.cache_ttl_seconds > 0:
            entry = self._cache.get(cache_key)
            if entry and entry.expires_at > time.time():
                return dict(entry.value)

        param_sets = [params] + [variant for variant in (param_variants or []) if variant and variant != params]
        first_unavailable: Optional[Dict[str, Any]] = None
        rows: List[Dict[str, Any]] = []
        pages_used = 0
        for index, param_set in enumerate(param_sets):
            candidate_rows: List[Dict[str, Any]] = []
            fetched_raw_rows = 0
            page_index = 1
            unavailable: Optional[Dict[str, Any]] = None
            while page_index <= SSI_MAX_PAGES:
                page_params = dict(param_set)
                page_params["pageIndex"] = page_index
                page_params["pageSize"] = int(page_size)
                if pages_used and self.request_delay_seconds:
                    time.sleep(self.request_delay_seconds)
                payload = self._request(endpoint, params=page_params)
                pages_used += 1
                if isinstance(payload, dict) and payload.get("status") == "unavailable":
                    unavailable = payload
                    break

                raw_rows = _extract_rows(payload)
                mapped_rows = [mapper(row) for row in raw_rows]
                mapped_rows = [row for row in mapped_rows if row and _has_required_field(row, required_any)]
                candidate_rows.extend(mapped_rows)
                fetched_raw_rows += len(raw_rows)
                total = _total_record(payload)
                if total is not None and fetched_raw_rows >= total:
                    break
                if total is None and len(raw_rows) < page_size:
                    break
                page_index += 1

            if unavailable:
                if index == 0:
                    first_unavailable = unavailable
                    break
                continue
            if candidate_rows:
                rows = candidate_rows
                break

        if first_unavailable:
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
            "pages_used": pages_used,
            "request_page_size": int(page_size),
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
        force_refresh: bool = False,
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
        if self.cache_ttl_seconds > 0 and not force_refresh:
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
            for index, level in enumerate(nested[:10], start=1):
                if not isinstance(level, dict):
                    continue
                level_number = _to_int(_first_value(level, "Level", "level", "Position", "position")) or index
                price = _to_float(_first_value(level, "Price", "price", "BidPrice", "AskPrice", "bidPrice", "askPrice"))
                volume = _to_float(_first_value(level, "Volume", "Vol", "volume", "vol", "BidVol", "AskVol", "bidVol", "askVol"))
                if price is not None and price > 0 and (volume is None or volume >= 0):
                    level = {"price": price}
                    if volume is not None:
                        level["volume"] = volume
                    levels.append(level)
            return levels

        levels = []
        prefixes = ("Bid", "bid") if side == "bid" else ("Ask", "ask")
        for index in range(1, 11):
            price_keys = tuple(f"{prefix}Price{index}" for prefix in prefixes) + tuple(f"{prefix}_price_{index}" for prefix in prefixes)
            volume_keys = tuple(f"{prefix}Vol{index}" for prefix in prefixes) + tuple(f"{prefix}Volume{index}" for prefix in prefixes) + tuple(f"{prefix}_vol_{index}" for prefix in prefixes)
            price = _to_float(_first_value(row, *price_keys))
            volume = _to_float(_first_value(row, *volume_keys))
            if price is not None and price > 0 and (volume is None or volume >= 0):
                level = {"price": price}
                if volume is not None:
                    level["volume"] = volume
                levels.append(level)
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
        index_value = _to_float(
            _first_value(
                row,
                "IndexValue",
                "Index",
                "Close",
                "CloseIndex",
                "indexValue",
                "index_value",
                "close",
            )
        )
        return {
            "date": _parse_date(_first_value(row, "TradingDate", "Tradingdate", "Date", "date", "trading_date", "time")),
            "index_code": str(_first_value(row, "IndexId", "IndexID", "IndexCode", "indexId", "indexID", "indexCode", "index_code", "code") or index_code).upper(),
            "index_value": index_value if index_value is not None and index_value > 0 else None,
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
            "industry": _first_value(row, "Industry", "IndustryName", "Sector", "SectorName", "BusinessLine", "ICBName", "IcbName", "industry", "industryName", "industry_name", "sector", "sectorName", "sector_name", "businessLine", "business_line", "icbName", "icb_name"),
            "sector": _first_value(row, "Sector", "SectorName", "sector", "sectorName", "sector_name"),
            "issuer": _first_value(row, "Issuer", "IssuerName", "OrganizationName", "OrganName", "issuer", "issuerName", "organizationName", "organName"),
            "lot_size": _to_int(_first_value(row, "LotSize", "TradingUnit", "RoundLot", "lotSize", "lot_size", "tradingUnit", "roundLot")),
            "listed_shares": _to_int(_first_value(row, "ListedShares", "ListedShare", "TotalListedShares", "SharesOutstanding", "listedShares", "listedShare", "totalListedShares", "listed_shares", "sharesOutstanding")),
            "listed_date": _parse_date(_first_value(row, "ListedDate", "ListingDate", "FirstTradingDate", "listedDate", "listed_date", "listingDate", "firstTradingDate")),
            "market": _first_value(row, "Market", "Exchange", "StockExchange", "market", "exchange", "stockExchange"),
            "source": SSI_SOURCE,
        }
