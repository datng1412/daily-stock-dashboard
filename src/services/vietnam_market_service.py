# -*- coding: utf-8 -*-
"""Vietnam watchlist dashboard service."""

from __future__ import annotations

import math
import logging
import os
import re
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock, RLock
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

import pandas as pd

from data_provider.base import DataFetcherManager
from data_provider.corporate_actions_provider import (
    CORPORATE_ACTION_PROVIDER_SOURCE,
    CORPORATE_ACTIONS_UNAVAILABLE_REASON,
    CorporateActionsProvider,
    DisabledCorporateActionsProvider,
    NotConfiguredCorporateActionsProvider,
    normalize_provider_status,
    sanitize_corporate_actions_text,
)
from data_provider.ssi_fastconnect_fetcher import (
    DAILY_OHLC_RATE_LIMIT_COOLDOWN_REASON,
    SsiFastConnectFetcher,
)
from data_provider.ssi_streaming_realtime import SSI_STREAMING_REALTIME_DISABLED_REASON
from src.config import get_config
from src.services.vietnam_observability import (
    monotonic_ms,
    observe_mozyfin_cache_result,
    observe_mozyfin_fetch,
    observe_mozyfin_watchlist_request,
)


LIQUIDITY_TARGET_AVG_VOLUME = 1_000_000
FOREIGN_HISTORY_LIMIT = 20
VN_CHART_HISTORY_DAYS = 400
VN_CHART_POINT_LIMIT = 260
VN_WATCHLIST = ("FPT", "VPB", "MSB", "SCS", "ACV", "ACB")
VN_EXCHANGE_MAP = {
    "FPT": "HOSE",
    "VPB": "HOSE",
    "MSB": "HOSE",
    "SCS": "HOSE",
    "ACV": "UPCoM",
    "ACB": "HOSE",
}
VN_PRICE_LIMIT_PCT = {
    "HOSE": 7.0,
    "HNX": 10.0,
    "UPCOM": 15.0,
    "UPCoM": 15.0,
}
VN_CHART_RANGES = {
    "1M": 31,
    "3M": 93,
    "6M": 186,
    "1Y": 366,
}
VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
VN_INDEX_COMPONENTS_CACHE_TTL_SECONDS = 300
VN_INDEX_COMPONENTS_NEGATIVE_CACHE_TTL_SECONDS = 60
VN_CACHE_TTL_SECONDS = {
    "ohlcv": 300,
    "daily_stock_price": 300,
    "quote": 60,
    "intraday_ohlcv": 60,
    "realtime_snapshot": 10,
    "trade_tape": 5,
    "news": 1800,
    "symbol_metadata": 3600,
    "index_components": VN_INDEX_COMPONENTS_CACHE_TTL_SECONDS,
}
VN_PROVIDER_MOZYFIN = "mozyfin"
VN_PROVIDER_SSI = "ssi"
VN_PROVIDER_NONE = "none"
VN_SOURCE_MOZYFIN = "Mozyfin"
VN_SOURCE_SSI = "SSI"
SSI_DAILY_OHLC_SOURCE = "SSI DailyOhlc"
SSI_DAILY_STOCK_PRICE_SOURCE = "SSI DailyStockPrice"
SSI_SECURITIES_SOURCE = "SSI Securities"
SSI_SECURITIES_DETAILS_SOURCE = "SSI SecuritiesDetails"
SSI_INTRADAY_SOURCE = "SSI IntradayOhlc"
SSI_REALTIME_SOURCE = "SSI realtime contract"
SSI_TRADE_TAPE_SOURCE = "SSI trade-tape contract"
SSI_INDEX_LIST_SOURCE = "SSI IndexList"
SSI_DAILY_INDEX_SOURCE = "SSI DailyIndex"
SSI_INDEX_COMPONENTS_SOURCE = "SSI IndexComponents"
CORPORATE_ACTIONS_SOURCE = CORPORATE_ACTION_PROVIDER_SOURCE
SSI_UNAVAILABLE_REASON = "SSI FastConnect unavailable"
VN_INTRADAY_WARNING = "SSI IntradayOhlc candle data is not a realtime matched quote."
VN_INTRADAY_DISABLED_REASON = "SSI IntradayOhlc is disabled."
VN_INTRADAY_UNAVAILABLE_REASON = "SSI intraday unavailable."
VN_REALTIME_DISABLED_REASON = "SSI realtime is disabled."
VN_REALTIME_UNAVAILABLE_REASON = "SSI realtime unavailable."
VN_TRADE_TAPE_DISABLED_REASON = "SSI trade tape is disabled."
VN_TRADE_TAPE_UNAVAILABLE_REASON = "SSI trade tape unavailable."
VN_NEWS_DISABLED_REASON = "News provider disabled."
STALE_CACHE_WARNING = "Live refresh failed; showing stale cached data."
VN_STATUS_RULE_METADATA = {
    "rule_set_name": "Vietnam neutral technical labels",
    "rule_set_version": "v1",
    "no_recommendation": True,
}
VN_ALLOWED_STATUS_LABELS = {
    "Watch",
    "Stronger than short-term average",
    "Weak short-term",
    "Near support",
    "Near resistance",
    "Breakout candidate",
    "Overextended",
    "Volume expansion",
    "Low liquidity",
    "Foreign data stale",
    "Foreign net positive",
    "Foreign net negative",
    "Indicator caution",
    "Price finality unknown",
    "Adjusted price unknown",
}
VN_FORBIDDEN_STATUS_LABELS = {
    "Buy",
    "Sell",
    "Hold",
    "Accumulate",
    "Cut loss",
    "Take profit",
    "Target price",
    "Entry price",
}
VN_ALLOWED_INTRADAY_LABELS = {
    "Intraday up",
    "Intraday down",
    "Intraday flat",
    "Intraday volume expansion",
    "Intraday wide range",
    "Intraday data limited",
    "Not realtime quote",
}
VN_FORBIDDEN_INTRADAY_LABELS = {
    "Buy",
    "Sell",
    "Hold",
    "Accumulate",
    "Cut loss",
    "Take profit",
    "Entry",
    "Target",
}
VN_DASHBOARD_UNITS = {
    "latest_price": "VND",
    "ohlcv_close": "VND",
    "open": "VND",
    "high": "VND",
    "low": "VND",
    "close": "VND",
    "previous_close": "VND",
    "volume": "shares",
    "amount": "VND",
    "foreign_buy": "row-specific",
    "foreign_sell": "row-specific",
    "foreign_net": "row-specific",
    "foreign_net_unit": "shares|VND|unknown",
    "ma20": "VND",
    "ma50": "VND",
    "rsi14": "index",
    "bollinger_upper": "VND",
    "bollinger_middle": "VND",
    "bollinger_lower": "VND",
    "avg_volume_20d": "shares",
    "volume_ratio": "ratio",
    "high_20d": "VND",
    "low_20d": "VND",
    "distance_to_20d_high_pct": "percent",
    "distance_to_20d_low_pct": "percent",
    "high_52w": "VND",
    "low_52w": "VND",
    "avg_volume_10d": "shares",
    "avg_volume_3m": "shares",
    "price_vs_reference_pct": "percent",
    "daily_range_pct": "percent",
    "foreign_net_5d": "row-specific",
    "foreign_net_20d": "row-specific",
    "foreign_net_5d_latest_available": "row-specific",
    "foreign_net_20d_latest_available": "row-specific",
    "intraday_price": "VND",
    "intraday_volume": "shares",
    "latest_intraday_price": "VND",
    "latest_intraday_volume": "shares",
    "corporate_action_cash_dividend": "VND/share",
    "adjusted_reference_price": "VND",
}


def vn_ticker(symbol: str) -> str:
    return (symbol or "").strip().upper().removesuffix(".VN")


def normalize_vn_symbol(symbol: str) -> str:
    ticker = vn_ticker(symbol)
    return f"{ticker}.VN" if ticker else ""


def get_vn_exchange(symbol: str) -> str:
    return VN_EXCHANGE_MAP.get(vn_ticker(symbol), "HOSE")


def get_vn_price_limit_pct(symbol: str) -> float:
    exchange = get_vn_exchange(symbol)
    return VN_PRICE_LIMIT_PCT.get(exchange, 7.0)
logger = logging.getLogger(__name__)


def _observe(action: Callable[..., None], *args: Any, **kwargs: Any) -> None:
    try:
        action(*args, **kwargs)
    except Exception as exc:
        logger.warning("Vietnam observability update failed: %s", exc)


@dataclass
class _CacheEntry:
    value: Any
    fetched_at: datetime
    expires_at: datetime


_VN_CACHE: Dict[Tuple[Any, ...], _CacheEntry] = {}
_VN_CACHE_LOCK = RLock()
_VN_INFLIGHT_LOCKS: Dict[Tuple[Any, ...], Lock] = {}
_VN_INFLIGHT_LOCKS_LOCK = RLock()


def clear_vietnam_cache() -> None:
    """Clear process-local Vietnam cache. Intended for tests and manual diagnostics."""
    with _VN_CACHE_LOCK:
        _VN_CACHE.clear()
    with _VN_INFLIGHT_LOCKS_LOCK:
        _VN_INFLIGHT_LOCKS.clear()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _cache_key(data_type: str, symbol: str, **params: Any) -> Tuple[Any, ...]:
    normalized_params = tuple(sorted((key, str(value)) for key, value in params.items()))
    return ("VN", data_type, vn_ticker(symbol), *normalized_params)


def normalize_vietnam_tickers(values: Optional[Iterable[str]]) -> List[str]:
    symbols: List[str] = []
    seen = set()
    duplicate_count = 0
    for value in values or VN_WATCHLIST:
        ticker = vn_ticker(str(value).strip().upper())
        if not ticker or not ticker.replace(".", "").isalnum() or len(ticker) > 10:
            continue
        if ticker in seen:
            duplicate_count += 1
            continue
        seen.add(ticker)
        symbols.append(ticker)
    if duplicate_count:
        logger.info("Vietnam watchlist removed %s duplicate ticker(s)", duplicate_count)
    return symbols


def _get_cache_entry(key: Tuple[Any, ...]) -> Optional[_CacheEntry]:
    with _VN_CACHE_LOCK:
        return _VN_CACHE.get(key)


def _set_cache_entry(key: Tuple[Any, ...], value: Any, ttl_seconds: int) -> _CacheEntry:
    now = _utc_now()
    entry = _CacheEntry(value=value, fetched_at=now, expires_at=now + timedelta(seconds=ttl_seconds))
    with _VN_CACHE_LOCK:
        _VN_CACHE[key] = entry
    return entry


def _transient_cache_entry(value: Any) -> _CacheEntry:
    now = _utc_now()
    return _CacheEntry(value=value, fetched_at=now, expires_at=now)


def _safe_cache_error_text(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    lowered = text.lower()
    if any(marker in lowered for marker in ("token", "secret", "authorization", "bearer", "consumer", "account")):
        return fallback
    return text[:160]


def _daily_cache_unavailable_reason(data_type: str, value: Any) -> Optional[str]:
    if data_type == "ohlcv" and isinstance(value, tuple) and len(value) >= 3:
        meta = value[2] if isinstance(value[2], dict) else {}
        if str(meta.get("status") or "").lower() == "unavailable":
            return _safe_cache_error_text(
                meta.get("unavailable_reason"),
                "refresh returned unavailable DailyOhlc value",
            )
        df = value[0]
        if isinstance(df, pd.DataFrame) and df.empty:
            return "refresh returned empty DailyOhlc value"
    if data_type == "daily_stock_price" and isinstance(value, tuple):
        row = value[0] if len(value) > 0 else None
        reason = value[1] if len(value) > 1 else None
        diagnostics = value[2] if len(value) > 2 and isinstance(value[2], dict) else {}
        if row is None and (reason or diagnostics.get("failure_class")):
            return _safe_cache_error_text(
                reason or diagnostics.get("failure_class"),
                "refresh returned unavailable DailyStockPrice value",
            )
    return None


def _get_inflight_lock(key: Tuple[Any, ...]) -> Lock:
    with _VN_INFLIGHT_LOCKS_LOCK:
        lock = _VN_INFLIGHT_LOCKS.get(key)
        if lock is None:
            lock = Lock()
            _VN_INFLIGHT_LOCKS[key] = lock
        return lock


def _read_cache(
    key: Tuple[Any, ...],
    data_type: str,
    fetch: Callable[[], Any],
    force_refresh: bool = False,
    ttl_resolver: Optional[Callable[[Any], int]] = None,
) -> Dict[str, Any]:
    default_ttl_seconds = VN_CACHE_TTL_SECONDS[data_type]
    now = _utc_now()
    entry = _get_cache_entry(key)
    if entry and entry.expires_at > now and not force_refresh:
        logger.debug("VN cache hit: %s", key)
        _observe(observe_mozyfin_cache_result, "hit", key)
        return {"value": entry.value, "status": "hit", "entry": entry, "error": None}

    lock = _get_inflight_lock(key)
    waited = lock.locked()
    if waited:
        logger.debug("VN cache single-flight wait: %s", key)
    with lock:
        now = _utc_now()
        current_entry = _get_cache_entry(key)
        if current_entry and current_entry.expires_at > now:
            if waited:
                logger.debug("VN cache single-flight reuse: %s", key)
                _observe(observe_mozyfin_cache_result, "hit", key, waited=True)
                return {"value": current_entry.value, "status": "hit", "entry": current_entry, "error": None}
            if not force_refresh:
                logger.debug("VN cache hit: %s", key)
                _observe(observe_mozyfin_cache_result, "hit", key)
                return {"value": current_entry.value, "status": "hit", "entry": current_entry, "error": None}

        logger.debug("VN cache %s: %s", "refresh" if current_entry or force_refresh else "miss", key)
        started_ms = monotonic_ms()
        try:
            value = fetch()
            _observe(observe_mozyfin_fetch, key, monotonic_ms() - started_ms)
            unavailable_reason = _daily_cache_unavailable_reason(data_type, value)
            if unavailable_reason:
                if current_entry is not None:
                    _observe(observe_mozyfin_cache_result, "stale", key, waited=waited)
                    return {
                        "value": current_entry.value,
                        "status": "stale",
                        "entry": current_entry,
                        "error": unavailable_reason,
                    }
                _observe(observe_mozyfin_cache_result, "error", key, waited=waited)
                return {
                    "value": value,
                    "status": "error",
                    "entry": _transient_cache_entry(value),
                    "error": unavailable_reason,
                }
            ttl_seconds = (
                max(0, int(ttl_resolver(value)))
                if ttl_resolver is not None
                else default_ttl_seconds
            )
            refreshed = _set_cache_entry(key, value, ttl_seconds)
            if force_refresh:
                status = "refresh"
            elif current_entry:
                status = "refresh"
            else:
                status = "miss"
            _observe(observe_mozyfin_cache_result, status, key, waited=waited)
            return {"value": value, "status": status, "entry": refreshed, "error": None}
        except Exception as exc:
            if current_entry is not None:
                _observe(observe_mozyfin_cache_result, "stale", key, waited=waited)
                return {"value": current_entry.value, "status": "stale", "entry": current_entry, "error": str(exc)}
            _observe(observe_mozyfin_cache_result, "error", key, waited=waited)
            raise


@dataclass(frozen=True)
class VietnamDashboardConfig:
    liquidity_target_avg_volume: int = LIQUIDITY_TARGET_AVG_VOLUME
    history_days: int = 90
    news_limit: int = 5
    include_intraday: bool = True
    intraday_timeframe: str = "1h"
    intraday_limit: int = 8
    news_provider: str = "disabled"
    mozyfin_enabled: bool = False
    mozyfin_news_enabled: bool = False
    allow_legacy_mozyfin_provider: bool = False
    daily_data_provider: str = VN_PROVIDER_SSI
    chart_data_provider: str = VN_PROVIDER_SSI
    daily_stock_price_provider: str = VN_PROVIDER_SSI
    index_data_provider: str = VN_PROVIDER_SSI
    intraday_data_provider: str = VN_PROVIDER_SSI
    ssi_intraday_enabled: bool = True
    realtime_data_provider: str = VN_PROVIDER_SSI
    trade_tape_provider: str = VN_PROVIDER_SSI
    ssi_realtime_enabled: bool = True
    ssi_streaming_realtime_enabled: bool = False
    ssi_trade_tape_enabled: bool = True
    corporate_actions_provider_enabled: bool = False
    corporate_actions_provider: str = "disabled"
    corporate_actions_provider_timeout_seconds: int = 10
    kbs_enabled: bool = False
    allow_legacy_kbs_provider: bool = False
    provider_comparison_enabled: bool = False


def _default_dashboard_config() -> VietnamDashboardConfig:
    app_config = get_config()
    return VietnamDashboardConfig(
        daily_data_provider=getattr(app_config, "vn_daily_data_provider", VN_PROVIDER_SSI),
        chart_data_provider=getattr(app_config, "vn_chart_data_provider", VN_PROVIDER_SSI),
        daily_stock_price_provider=getattr(app_config, "vn_daily_stock_price_provider", VN_PROVIDER_SSI),
        index_data_provider=getattr(app_config, "vn_index_data_provider", VN_PROVIDER_SSI),
        intraday_data_provider=getattr(app_config, "vn_intraday_data_provider", VN_PROVIDER_SSI),
        ssi_intraday_enabled=getattr(app_config, "ssi_fastconnect_intraday_enabled", True),
        realtime_data_provider=getattr(app_config, "vn_realtime_data_provider", VN_PROVIDER_SSI),
        trade_tape_provider=getattr(app_config, "vn_trade_tape_provider", VN_PROVIDER_SSI),
        ssi_realtime_enabled=getattr(app_config, "ssi_fastconnect_realtime_enabled", True),
        ssi_streaming_realtime_enabled=getattr(app_config, "ssi_streaming_realtime_enabled", False),
        ssi_trade_tape_enabled=getattr(app_config, "ssi_fastconnect_trade_tape_enabled", True),
        corporate_actions_provider_enabled=getattr(app_config, "vn_corporate_actions_provider_enabled", False),
        corporate_actions_provider=getattr(app_config, "vn_corporate_actions_provider", "disabled"),
        corporate_actions_provider_timeout_seconds=getattr(app_config, "vn_corporate_actions_provider_timeout_seconds", 10),
        kbs_enabled=getattr(app_config, "kbs_enabled", False),
        allow_legacy_kbs_provider=getattr(app_config, "vn_allow_legacy_kbs_provider", False),
        provider_comparison_enabled=getattr(app_config, "vn_provider_comparison_enabled", False),
        news_provider=getattr(app_config, "vn_news_provider", "disabled"),
        mozyfin_enabled=getattr(app_config, "mozyfin_enabled", False),
        mozyfin_news_enabled=getattr(app_config, "mozyfin_news_enabled", False),
        allow_legacy_mozyfin_provider=getattr(app_config, "vn_allow_legacy_mozyfin_provider", False),
    )


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        numeric = float(value)
        if math.isnan(numeric):
            return None
        return numeric
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        numeric = float(value)
        if math.isnan(numeric):
            return None
        return int(numeric)
    except (TypeError, ValueError):
        return None


def _last_value(df: pd.DataFrame, column: str) -> Any:
    if column not in df.columns or df.empty:
        return None
    return df.iloc[-1].get(column)


def _valid_date_string(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.strftime("%Y-%m-%d")


def _date_match_status(left: Optional[str], right: Optional[str]) -> str:
    if not left or not right:
        return "unknown"
    return "matched" if left == right else "mismatched"


DAILY_STOCK_PRICE_ENRICHMENT_FIELDS = (
    "reference_price",
    "ceiling_price",
    "floor_price",
    "matched_volume",
    "matched_value",
    "put_through_volume",
    "put_through_value",
    "foreign_buy_volume",
    "foreign_sell_volume",
    "foreign_net_volume",
    "foreign_buy_value",
    "foreign_sell_value",
    "foreign_net_value",
    "adjusted_close",
)

DAILY_STOCK_PRICE_FIELD_UNITS = {
    "reference_price": "VND",
    "ceiling_price": "VND",
    "floor_price": "VND",
    "matched_volume": "shares",
    "matched_value": "VND",
    "put_through_volume": "shares",
    "put_through_value": "VND",
    "foreign_buy_volume": "shares",
    "foreign_sell_volume": "shares",
    "foreign_net_volume": "shares",
    "foreign_buy_value": "VND",
    "foreign_sell_value": "VND",
    "foreign_net_value": "VND",
    "adjusted_close": "VND",
}

SYMBOL_METADATA_FIELDS = (
    "symbol",
    "exchange",
    "market",
    "name",
    "name_en",
    "industry",
    "sector",
    "security_type",
    "issuer",
    "lot_size",
    "listed_shares",
    "listed_date",
)

INDEX_LIST_FIELDS = (
    "index_id",
    "index_code",
    "index_name",
    "exchange",
    "market",
)

DAILY_INDEX_FIELDS = (
    "index_code",
    "date",
    "index_value",
    "change",
    "change_pct",
    "total_volume",
    "total_value",
    "matched_volume",
    "matched_value",
    "put_through_volume",
    "put_through_value",
    "advances",
    "unchanged",
    "declines",
    "ceiling",
    "floor",
    "trading_session",
    "exchange",
)

INDEX_COMPONENT_FIELDS = (
    "index_code",
    "symbol",
    "exchange",
    "market",
    "weight",
    "name",
)


def _status_from_block(block: Any, default: str = "unavailable") -> str:
    if not isinstance(block, dict):
        return default
    value = block.get("status")
    return str(value) if value else default


LIVE_DIAGNOSTIC_KEYS = {
    "attempted_endpoints",
    "endpoint",
    "last_endpoint",
    "http_status",
    "provider_code",
    "code",
    "errorCode",
    "failure_class",
    "error_type",
    "retryable",
    "cooldown_active",
    "cooldown_seconds",
    "cooldown_remaining_seconds",
    "cooldown_until",
    "backoff_seconds",
    "next_reconnect_at",
    "reconnect_attempts",
    "streaming_status",
    "runtime_status",
    "manager_state",
    "cache_status",
    "cache_ttl_seconds",
    "trade_tape_ttl_seconds",
    "trade_tape_buffer_size",
    "trade_tape_buffer_row_count",
    "trade_tape_returned_row_count",
    "trade_rows_observed",
    "latest_trade_timestamp",
    "latest_trade_age_seconds",
    "channel_type",
    "bootstrap_membership",
    "live_adapter_status",
    "bootstrap_symbols",
    "requested_symbols",
    "channels",
    "messages_observed",
    "parser_rows_observed",
    "last_message_at",
    "provider_message",
    "latest_error",
}
LIVE_SECRET_MARKERS = (
    "authorization",
    "bearer ",
    "token",
    "secret",
    "cookie",
    "accountid",
    "account_id",
    "consumerid",
    "consumer_id",
    "consumersecret",
    "consumer_secret",
    "api_key",
    "apikey",
)


def _safe_live_diagnostic_text(value: Any, *, max_length: int = 160) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    if any(marker in lowered for marker in LIVE_SECRET_MARKERS):
        return "[redacted]"
    text = re.sub(r"https?://\S+", "<url>", text, flags=re.IGNORECASE)
    return text[:max_length]


def _safe_live_diagnostic_value(key: str, value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return value
    if key in {"attempted_endpoints", "bootstrap_symbols", "requested_symbols", "channels"} and isinstance(value, (list, tuple, set)):
        safe_items = [
            _safe_live_diagnostic_text(item, max_length=80)
            for item in list(value)[:20]
        ]
        return [item for item in safe_items if item]
    return _safe_live_diagnostic_text(value)


def _live_failure_diagnostics(payload: Any, *, reason: Optional[str] = None) -> Dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    nested = payload.get("diagnostics")
    sources = [nested] if isinstance(nested, dict) else []
    sources.append(payload)
    diagnostics: Dict[str, Any] = {}
    for source in sources:
        for key, value in source.items():
            if key not in LIVE_DIAGNOSTIC_KEYS:
                continue
            output_key = "provider_code" if key in {"code", "errorCode"} else key
            if key in {"latest_error", "provider_message"}:
                output_key = "provider_message"
            safe_value = _safe_live_diagnostic_value(output_key, value)
            if safe_value is not None:
                diagnostics[output_key] = safe_value
    safe_reason = _safe_live_diagnostic_text(reason)
    if safe_reason and "provider_message" not in diagnostics:
        diagnostics["provider_message"] = safe_reason
    if "retryable" not in diagnostics:
        failure_class = str(diagnostics.get("failure_class") or "").lower()
        if failure_class:
            diagnostics["retryable"] = failure_class in {
                "rate_limited",
                "timeout",
                "network_error",
                "provider_unavailable",
            }
    return diagnostics


def _lower_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _diagnostic_value(diagnostics: Dict[str, Any], *keys: str) -> Optional[Any]:
    for key in keys:
        if key in diagnostics and diagnostics.get(key) not in (None, ""):
            return diagnostics.get(key)
    return None


def _status_block_value(block: Dict[str, Any], key: str) -> Any:
    if key in block and block.get(key) not in (None, ""):
        return block.get(key)
    diagnostics = block.get("diagnostics")
    if isinstance(diagnostics, dict) and diagnostics.get(key) not in (None, ""):
        return diagnostics.get(key)
    return None


def _classify_intraday_reason(
    *,
    status: str,
    reason: Optional[str],
    diagnostics: Optional[Dict[str, Any]] = None,
) -> str:
    diagnostics = dict(diagnostics or {})
    normalized_status = _lower_text(status)
    reason_text = _lower_text(reason)
    failure_class = _lower_text(_diagnostic_value(diagnostics, "failure_class"))
    date_match = _lower_text(_diagnostic_value(diagnostics, "date_match"))
    cadence_status = _lower_text(_diagnostic_value(diagnostics, "intraday_cadence_status"))

    if normalized_status == "ok":
        if cadence_status in {"different_from_requested", "irregular"}:
            return "cadence_mismatch"
        return "ok"
    if normalized_status == "disabled":
        return "disabled"
    if failure_class == "rate_limited" or _lower_text(_diagnostic_value(diagnostics, "provider_code")) == "429":
        return "unavailable_rate_limited"
    if date_match == "mismatched" or failure_class == "stale_or_date_mismatched":
        return "unavailable_date_mismatch"
    if failure_class in {"empty_response", "empty_result"} or "no candles" in reason_text or "no rows" in reason_text:
        return "unavailable_no_rows"
    if failure_class in {"timeout", "network_error", "request_error", "provider_error", "auth_failed"}:
        return "unavailable_provider_error"
    if normalized_status == "unavailable":
        return "unavailable_provider_error" if failure_class else "unavailable_unknown"
    return "unknown"


def _status_message_from_reason(
    *,
    section: str,
    status: str,
    reason_code: str,
    fallback: str,
) -> str:
    if section == "intraday":
        messages = {
            "ok": "SSI IntradayOhlc ready.",
            "cadence_mismatch": "SSI IntradayOhlc cadence differs from the requested timeframe.",
            "disabled": VN_INTRADAY_DISABLED_REASON,
            "unavailable_rate_limited": "SSI IntradayOhlc rate-limited by provider.",
            "unavailable_date_mismatch": "SSI IntradayOhlc latest candle date does not match latest daily trading date.",
            "unavailable_no_rows": "SSI IntradayOhlc returned no usable candles.",
            "unavailable_provider_error": "SSI IntradayOhlc provider unavailable.",
            "unavailable_unknown": VN_INTRADAY_UNAVAILABLE_REASON,
        }
    elif section == "realtime":
        messages = {
            "cache_hit": "SSI realtime snapshot ready.",
            "disabled": VN_REALTIME_DISABLED_REASON,
            "config_disabled": "SSI realtime manager disabled.",
            "not_started": "SSI realtime manager unavailable.",
            "bootstrap_symbols_empty": "SSI realtime cache miss.",
            "ticker_not_bootstrapped": "SSI realtime cache miss.",
            "running_idle": "SSI realtime cache miss.",
            "cache_empty": "SSI realtime cache miss.",
            "cache_stale": "SSI realtime stale.",
            "connection_error": VN_REALTIME_UNAVAILABLE_REASON,
            "auth_or_entitlement_failure": VN_REALTIME_UNAVAILABLE_REASON,
            "network_or_tls_failure": VN_REALTIME_UNAVAILABLE_REASON,
            "rate_limited": VN_REALTIME_UNAVAILABLE_REASON,
            "unknown": VN_REALTIME_UNAVAILABLE_REASON,
        }
    else:
        messages = {
            "historical_trade_tape_supported": "SSI historical trade tape ready.",
            "streaming_trade_tape_supported": "SSI trade tape ready.",
            "latest_trade_stream_only": VN_TRADE_TAPE_UNAVAILABLE_REASON,
            "disabled": VN_TRADE_TAPE_DISABLED_REASON,
            "unavailable_no_rows": "No SSI trade rows available.",
            "stream_not_started": VN_TRADE_TAPE_UNAVAILABLE_REASON,
            "stream_not_bootstrapped": VN_TRADE_TAPE_UNAVAILABLE_REASON,
            "stream_cache_empty": VN_TRADE_TAPE_UNAVAILABLE_REASON,
            "stream_cache_stale": VN_TRADE_TAPE_UNAVAILABLE_REASON,
            "unavailable_provider_error": VN_TRADE_TAPE_UNAVAILABLE_REASON,
            "unavailable_unknown": VN_TRADE_TAPE_UNAVAILABLE_REASON,
            "not_implemented": VN_TRADE_TAPE_UNAVAILABLE_REASON,
        }
    if reason_code in messages:
        return messages[reason_code]
    if status == "disabled":
        return messages.get("disabled", fallback)
    return fallback


def _classify_realtime_reason(
    *,
    status: str,
    reason: Optional[str],
    diagnostics: Optional[Dict[str, Any]] = None,
    symbol: Optional[str] = None,
) -> str:
    diagnostics = dict(diagnostics or {})
    normalized_status = _lower_text(status)
    reason_text = _lower_text(reason)
    streaming_status = _lower_text(_diagnostic_value(diagnostics, "streaming_status"))
    cache_status = _lower_text(_diagnostic_value(diagnostics, "cache_status"))
    manager_state = _lower_text(_diagnostic_value(diagnostics, "manager_state"))
    runtime_status = _lower_text(_diagnostic_value(diagnostics, "runtime_status"))
    latest_error = _lower_text(_diagnostic_value(diagnostics, "latest_error", "provider_message"))

    if normalized_status == "ok":
        return "cache_hit"
    if normalized_status == "disabled" or streaming_status == "disabled":
        return "config_disabled"
    if streaming_status == "bootstrap_symbols_empty" or cache_status == "bootstrap_symbols_empty":
        return "bootstrap_symbols_empty"
    if manager_state and manager_state != "running":
        return "not_started" if manager_state in {"stopped", "starting"} else "connection_error"
    if runtime_status == "not_started" or streaming_status == "manager_not_started" or cache_status == "not_started":
        return "not_started"

    bootstrap_symbols = {
        str(item or "").strip().upper()
        for item in diagnostics.get("bootstrap_symbols", []) or []
        if str(item or "").strip()
    }
    requested_symbol = str(symbol or "").strip().upper()
    if requested_symbol and bootstrap_symbols and requested_symbol not in bootstrap_symbols:
        return "ticker_not_bootstrapped"
    if runtime_status == "running_idle":
        return "running_idle"
    if streaming_status in {"cache_stale"} or cache_status == "stale":
        return "cache_stale"
    if streaming_status == "cache_empty" or cache_status == "empty":
        return "cache_empty"
    if "not implemented" in latest_error or "not implemented" in reason_text:
        return "unknown"
    if "entitlement" in latest_error or "permission" in latest_error or "401" in latest_error or "403" in latest_error:
        return "auth_or_entitlement_failure"
    if "rate" in latest_error and "limit" in latest_error:
        return "rate_limited"
    if "tls" in latest_error or "ssl" in latest_error or "network" in latest_error or "connection" in latest_error:
        return "network_or_tls_failure"
    if "configuration incomplete" in reason_text or "package unavailable" in reason_text:
        return "connection_error"
    return "unknown"


def _classify_trade_tape_reason(
    *,
    status: str,
    reason: Optional[str],
) -> str:
    normalized_status = _lower_text(status)
    reason_text = _lower_text(reason)
    if normalized_status == "ok":
        if "stream" in reason_text or "x-trade" in reason_text or "cache_hit" in reason_text:
            return "streaming_trade_tape_supported"
        return "historical_trade_tape_supported"
    if normalized_status == "disabled":
        return "disabled"
    if "not bootstrapped" in reason_text:
        return "stream_not_bootstrapped"
    if "buffer stale" in reason_text or "cache stale" in reason_text:
        return "stream_cache_stale"
    if "buffer empty" in reason_text or "cache empty" in reason_text:
        return "stream_cache_empty"
    if "not started" in reason_text or "manager unavailable" in reason_text or "bootstrap symbols empty" in reason_text:
        return "stream_not_started"
    if "no trade rows" in reason_text:
        return "unavailable_no_rows"
    if "tradetape" in reason_text or "matchedtrades" in reason_text or "securitiestrades" in reason_text:
        return "latest_trade_stream_only"
    if normalized_status == "not_implemented":
        return "not_implemented"
    if normalized_status == "unavailable":
        return "unavailable_unknown"
    return "unknown"


INTRADAY_DIAGNOSTIC_KEYS = {
    "failure_class",
    "endpoint",
    "http_status",
    "provider_code",
    "code",
    "error_type",
    "symbol",
    "from_date",
    "to_date",
    "requested_timeframe",
    "pageIndex",
    "pageSize",
    "ascending",
    "public_limit",
    "request_page_size",
    "cooldown_active",
    "cooldown_recorded",
    "cooldown_seconds",
    "cooldown_remaining_seconds",
    "cooldown_until",
    "pages_used",
    "intraday_latest_date",
    "daily_price_date",
    "date_match",
    "intraday_granularity",
    "intraday_granularity_seconds",
    "intraday_granularity_label",
    "intraday_actual_granularity",
    "intraday_actual_granularity_seconds",
    "intraday_cadence_status",
    "normalized_row_count",
    "filtered_usable_row_count",
}


def _safe_intraday_diagnostic_value(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return value
    text = str(value).strip()
    return text[:120] if text else None


def _intraday_failure_diagnostics(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    diagnostics: Dict[str, Any] = {}
    nested = payload.get("diagnostics")
    sources = [nested] if isinstance(nested, dict) else []
    sources.append(payload)
    for source in sources:
        for key, value in source.items():
            if key not in INTRADAY_DIAGNOSTIC_KEYS:
                continue
            output_key = "provider_code" if key == "code" else key
            safe_value = _safe_intraday_diagnostic_value(value)
            if safe_value is not None:
                diagnostics[output_key] = safe_value
    return diagnostics


def _public_live_status(status: Optional[str]) -> str:
    normalized = str(status or "").lower()
    if normalized in {"ok", "unavailable", "disabled"}:
        return normalized
    return "unavailable"


def build_vietnam_data_quality_summary(row: Dict[str, Any]) -> Dict[str, Any]:
    """Build a user-safe data-quality summary without changing source semantics."""
    daily_close = _safe_float(
        row.get("ohlcv_close")
        if row.get("ohlcv_close") is not None
        else row.get("daily_close")
        if row.get("daily_close") is not None
        else row.get("latest_price")
    )
    daily_date = _valid_date_string(row.get("ohlcv_date") or row.get("latest_price_date") or row.get("date"))
    row_status = str(row.get("status") or "")
    source_labels = [
        str(row.get("latest_price_source") or ""),
        str(row.get("actual_source") or ""),
        str(row.get("source") or ""),
        str(row.get("primary_source") or ""),
    ]
    daily_source_is_ssi = any("ssi" in label.lower() for label in source_labels)
    daily_stock_price = row.get("daily_stock_price") if isinstance(row.get("daily_stock_price"), dict) else {}
    daily_stock_close = _safe_float(daily_stock_price.get("close"))
    daily_stock_date = _valid_date_string(daily_stock_price.get("date"))
    intraday_status = _status_from_block(row.get("intraday_status"))
    realtime_status = _status_from_block(row.get("realtime_status"))
    trade_tape_status = _status_from_block(row.get("trade_tape_status"))
    intraday_block = row.get("intraday_status") if isinstance(row.get("intraday_status"), dict) else {}
    realtime_block = row.get("realtime_status") if isinstance(row.get("realtime_status"), dict) else {}
    trade_tape_block = row.get("trade_tape_status") if isinstance(row.get("trade_tape_status"), dict) else {}
    news_status = _status_from_block(row.get("news_status"), default="disabled")
    final_close_status = str(row.get("final_close_status") or "unknown")
    adjusted_price_status = str(row.get("adjusted_price_status") or row.get("price_adjustment_status") or "unknown")

    daily_ohlc_check = (
        "ok"
        if row_status not in {"unavailable", "error"}
        and daily_close is not None
        and daily_date
        and daily_source_is_ssi
        else "unavailable"
    )
    daily_stock_price_status = str(daily_stock_price.get("status") or "unavailable")
    daily_stock_price_quality = str(daily_stock_price.get("quality_status") or "")
    if daily_stock_price_status != "ok":
        daily_stock_price_check = "unavailable"
    elif daily_stock_price_quality in {"ok", "partial"}:
        daily_stock_price_check = daily_stock_price_quality
    else:
        daily_stock_price_check = "ok"
    daily_stock_price_date_match = str(
        daily_stock_price.get("date_match")
        or row.get("daily_stock_price_date_match")
        or "unknown"
    )
    daily_stock_price_missing_fields = list(daily_stock_price.get("missing_fields") or [])
    indicators = row.get("indicators") if isinstance(row.get("indicators"), dict) else {}
    rows_loaded_raw = row.get("rows_loaded")
    try:
        rows_loaded = int(rows_loaded_raw or 0)
    except (TypeError, ValueError):
        rows_loaded = 0
    rsi14_value = _safe_float(
        indicators.get("rsi14_wilder")
        if indicators.get("rsi14_wilder") is not None
        else indicators.get("rsi14")
    )
    ma20_value = _safe_float(indicators.get("ma20"))
    foreign_block = row.get("foreign") if isinstance(row.get("foreign"), dict) else {}
    foreign_net_value = _safe_float(row.get("ssi_foreign_net_volume"))
    if foreign_net_value is None:
        foreign_net_value = _safe_float(foreign_block.get("net"))
    date_match = str(row.get("date_match") or "")
    intraday_reason_code = str(
        intraday_block.get("reason_code")
        or intraday_block.get("classification")
        or _classify_intraday_reason(
            status=intraday_status,
            reason=intraday_block.get("message"),
            diagnostics=intraday_block.get("diagnostics") if isinstance(intraday_block.get("diagnostics"), dict) else intraday_block,
        )
    )
    intraday_cadence_status = str(
        row.get("intraday_cadence_status")
        or intraday_block.get("intraday_cadence_status")
        or ""
    )
    if intraday_status == "unavailable" and (date_match == "mismatched" or intraday_reason_code == "unavailable_date_mismatch"):
        intraday_check = "stale"
    elif intraday_status == "ok" and intraday_cadence_status in {"different_from_requested", "irregular"}:
        intraday_check = "partial"
    else:
        intraday_check = intraday_status
    realtime_reason_code = str(
        realtime_block.get("reason_code")
        or realtime_block.get("classification")
        or _classify_realtime_reason(
            status=realtime_status,
            reason=realtime_block.get("message"),
            diagnostics=realtime_block.get("diagnostics") if isinstance(realtime_block.get("diagnostics"), dict) else realtime_block,
            symbol=row.get("ticker"),
        )
    )
    trade_tape_reason_code = str(
        trade_tape_block.get("reason_code")
        or trade_tape_block.get("classification")
        or _classify_trade_tape_reason(
            status=trade_tape_status,
            reason=trade_tape_block.get("message"),
        )
    )

    metadata = row.get("symbol_metadata") if isinstance(row.get("symbol_metadata"), dict) else {}
    metadata_status = str(metadata.get("status") or "unavailable")
    metadata_quality = str(metadata.get("quality_status") or "")
    missing_profile_fields = list(metadata.get("missing_fields") or [])
    if metadata_status != "ok":
        profile_status = "unavailable"
    elif metadata_quality in {"complete", "partial", "unknown"}:
        profile_status = metadata_quality
    else:
        fallback_name = row.get("company_name") or row.get("name") or metadata.get("name") or metadata.get("name_en")
        fallback_industry = row.get("industry") or metadata.get("industry") or metadata.get("sector")
        missing_profile_fields = []
        if not fallback_name:
            missing_profile_fields.append("name")
        if not fallback_industry:
            missing_profile_fields.append("industry")
        profile_status = "partial" if missing_profile_fields else "complete"

    issues: List[Dict[str, Any]] = []
    if daily_ohlc_check != "ok":
        issues.append(
            {
                "code": "daily_ohlc_unavailable",
                "severity": "warning",
                "message": "SSI DailyOhlc data is unavailable.",
                "fields": {},
            }
        )
        issues.append(
            {
                "code": "daily_ohlcv_missing",
                "severity": "warning",
                "message": "SSI DailyOhlc required daily OHLCV fields are missing.",
                "fields": {"rows_loaded": rows_loaded},
            }
        )
    if daily_date and daily_stock_date and daily_date == daily_stock_date and daily_close is not None and daily_stock_close is not None and daily_close != daily_stock_close:
        issues.append(
            {
                "code": "daily_ohlc_vs_daily_stock_price_mismatch",
                "severity": "warning",
                "message": "SSI DailyOhlc close differs from SSI DailyStockPrice close for the same trading date.",
                "fields": {
                    "daily_ohlc_close": daily_close,
                    "daily_stock_price_close": daily_stock_close,
                    "date": daily_date,
                    "daily_ohlc_source": SSI_DAILY_OHLC_SOURCE,
                    "daily_stock_price_source": SSI_DAILY_STOCK_PRICE_SOURCE,
                },
            }
        )
    if daily_stock_price_status == "ok" and daily_stock_price_date_match == "mismatched":
        issues.append(
            {
                "code": "daily_stock_price_date_mismatch",
                "severity": "warning",
                "message": "SSI DailyStockPrice date differs from SSI DailyOhlc.",
                "fields": {
                    "daily_ohlc_date": daily_date,
                    "daily_stock_price_date": daily_stock_date,
                    "daily_ohlc_source": SSI_DAILY_OHLC_SOURCE,
                    "daily_stock_price_source": SSI_DAILY_STOCK_PRICE_SOURCE,
                },
            }
        )
    if daily_stock_price_status == "ok" and daily_stock_price_missing_fields:
        issues.append(
            {
                "code": "daily_stock_price_partial",
                "severity": "info",
                "message": "SSI DailyStockPrice enrichment is partial.",
                "fields": {"missing_fields": daily_stock_price_missing_fields},
            }
        )
    elif daily_stock_price_check == "unavailable":
        issues.append(
            {
                "code": "daily_stock_price_missing",
                "severity": "info",
                "message": "SSI DailyStockPrice enrichment is unavailable.",
                "fields": {"status": daily_stock_price_status},
            }
        )
    if daily_ohlc_check == "ok" and rsi14_value is None:
        issues.append(
            {
                "code": "rsi_missing",
                "severity": "info",
                "message": "RSI14 requires at least 15 close prices.",
                "fields": {"rows_loaded": rows_loaded, "required_min_rows": 15},
            }
        )
    if daily_ohlc_check == "ok" and (daily_close is None or ma20_value is None):
        issues.append(
            {
                "code": "ma_state_insufficient_data",
                "severity": "info",
                "message": "MA state requires a daily close and at least 20 close prices.",
                "fields": {"rows_loaded": rows_loaded, "required_min_rows": 20},
            }
        )
    if daily_ohlc_check == "ok" and rows_loaded and rows_loaded < 20:
        issues.append(
            {
                "code": "ta_insufficient_history",
                "severity": "info",
                "message": "Technical indicators are limited because the DailyOhlc history is short.",
                "fields": {"rows_loaded": rows_loaded, "required_min_rows": 20},
            }
        )
    if daily_ohlc_check == "ok" and foreign_net_value is None:
        issues.append(
            {
                "code": "foreign_flow_missing",
                "severity": "info",
                "message": "Foreign-flow value is unavailable from SSI DailyStockPrice.",
                "fields": {
                    "daily_stock_price_status": daily_stock_price_status,
                    "daily_stock_price_source": SSI_DAILY_STOCK_PRICE_SOURCE,
                },
            }
        )
    if final_close_status == "unknown":
        issues.append(
            {
                "code": "final_close_status_unknown",
                "severity": "info",
                "message": "Final close status is unknown.",
                "fields": {"final_close_status": final_close_status},
            }
        )
    if adjusted_price_status == "unknown":
        issues.append(
            {
                "code": "adjusted_price_status_unknown",
                "severity": "info",
                "message": "Adjusted price status is unknown.",
                "fields": {"adjusted_price_status": adjusted_price_status},
            }
        )
    if intraday_check == "stale":
        issues.append(
            {
                "code": "intraday_stale_or_mismatched",
                "severity": "warning",
                "message": "SSI IntradayOhlc latest candle date does not match the daily trading date.",
                "fields": {
                    "intraday_latest_date": row.get("intraday_latest_date"),
                    "daily_price_date": row.get("daily_price_date") or daily_date,
                    "date_match": row.get("date_match"),
                    "reason_code": intraday_reason_code,
                },
            }
        )
    elif intraday_check == "partial" and intraday_reason_code == "cadence_mismatch":
        issues.append(
            {
                "code": "intraday_cadence_mismatch",
                "severity": "info",
                "message": "SSI IntradayOhlc cadence differs from the requested timeframe.",
                "fields": {
                    "status": intraday_check,
                    "reason_code": intraday_reason_code,
                    "requested_timeframe": row.get("intraday_requested_timeframe") or row.get("intraday_timeframe"),
                    "actual_granularity": row.get("intraday_actual_granularity") or row.get("intraday_granularity"),
                    "cadence_status": intraday_cadence_status,
                },
            }
        )
    elif intraday_check in {"unavailable", "disabled"}:
        issue_code = "intraday_disabled" if intraday_check == "disabled" else f"intraday_{intraday_reason_code}"
        issues.append(
            {
                "code": issue_code,
                "severity": "info",
                "message": _status_message_from_reason(
                    section="intraday",
                    status=intraday_check,
                    reason_code=intraday_reason_code,
                    fallback=f"SSI intraday is {intraday_check}.",
                ),
                "fields": {
                    "status": intraday_check,
                    "reason_code": intraday_reason_code,
                    "failure_class": intraday_block.get("failure_class"),
                    "cadence_status": intraday_cadence_status or None,
                    "intraday_latest_date": row.get("intraday_latest_date"),
                    "daily_price_date": row.get("daily_price_date") or daily_date,
                },
            }
        )
    if realtime_status in {"unavailable", "disabled"}:
        realtime_fields = {
            "status": realtime_status,
            "reason_code": realtime_reason_code,
            "streaming_status": _status_block_value(realtime_block, "streaming_status"),
            "runtime_status": _status_block_value(realtime_block, "runtime_status"),
            "cache_status": _status_block_value(realtime_block, "cache_status"),
        }
        issues.append(
            {
                "code": "realtime_disabled" if realtime_status == "disabled" else f"realtime_{realtime_reason_code}",
                "severity": "info",
                "message": _status_message_from_reason(
                    section="realtime",
                    status=realtime_status,
                    reason_code=realtime_reason_code,
                    fallback=f"SSI realtime is {realtime_status}.",
                ),
                "fields": {key: value for key, value in realtime_fields.items() if value not in (None, "")},
            }
        )
    if trade_tape_status in {"unavailable", "disabled"}:
        issues.append(
            {
                "code": "trade_tape_disabled" if trade_tape_status == "disabled" else f"trade_tape_{trade_tape_reason_code}",
                "severity": "info",
                "message": _status_message_from_reason(
                    section="trade_tape",
                    status=trade_tape_status,
                    reason_code=trade_tape_reason_code,
                    fallback=f"SSI trade tape is {trade_tape_status}.",
                ),
                "fields": {
                    "status": trade_tape_status,
                    "reason_code": trade_tape_reason_code,
                },
            }
        )
    if profile_status == "partial":
        issues.append(
            {
                "code": "profile_partial",
                "severity": "info",
                "message": "Profile partial. Some metadata is unavailable.",
                "fields": {"missing_fields": missing_profile_fields},
            }
        )
    elif profile_status == "unavailable":
        issues.append(
            {
                "code": "profile_unavailable",
                "severity": "info",
                "message": "Profile unavailable. Daily SSI data is still available.",
                "fields": {},
            }
        )

    optional_partial_checks = {
        "daily_stock_price": daily_stock_price_check,
        "intraday": intraday_check,
        "realtime": realtime_status,
        "trade_tape": trade_tape_status,
        "profile": profile_status,
        "news": news_status,
        "final_close_status": final_close_status,
        "adjusted_price_status": adjusted_price_status,
    }
    partial_values = {"unavailable", "disabled", "stale", "partial", "unknown", "provisional", "in_progress"}

    if daily_ohlc_check != "ok":
        overall_status = "unavailable"
    elif issues or any(value in partial_values for value in optional_partial_checks.values()):
        overall_status = "partial"
    else:
        overall_status = "ok"

    return {
        "overall_status": overall_status,
        "canonical_price_source": "SSI DailyOhlc",
        "issues": issues,
        "checks": {
            "daily_ohlc": daily_ohlc_check,
            "daily_stock_price": daily_stock_price_check,
            "final_close_status": final_close_status,
            "adjusted_price_status": adjusted_price_status,
            "intraday": intraday_check,
            "realtime": realtime_status,
            "trade_tape": trade_tape_status,
            "profile": profile_status,
            "news": news_status,
        },
    }


def _is_fixture_mode(manager: Optional[DataFetcherManager]) -> bool:
    return False


def _source_label(fixture_mode: bool) -> str:
    return "SSI live"


def validate_vietnam_row(row: pd.Series, foreign: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validate latest Vietnam market row without blocking dashboard rendering."""
    missing_fields: List[str] = []
    errors: List[str] = []

    date_text = _valid_date_string(row.get("date"))
    close = _safe_float(row.get("close"))
    volume = _safe_float(row.get("volume"))
    foreign_net = _safe_float((foreign or {}).get("net"))

    if date_text is None:
        missing_fields.append("date")
        errors.append("Trading date is missing or invalid.")
    if close is None:
        missing_fields.append("close")
    elif close <= 0:
        errors.append("Close price must be greater than 0.")
    if volume is None:
        missing_fields.append("volume")
    elif volume < 0:
        errors.append("Volume must be greater than or equal to 0.")
    if foreign_net is None:
        missing_fields.append("foreign_net")

    return {
        "valid": not errors,
        "trading_date": date_text,
        "missing_fields": missing_fields,
        "errors": errors,
    }


def calculate_liquidity_score(df: pd.DataFrame, target_avg_volume: int = LIQUIDITY_TARGET_AVG_VOLUME) -> Dict[str, Any]:
    """Score 20-day average volume on a 0-100 scale."""
    if df is None or df.empty or "volume" not in df.columns:
        return {"avg_volume_20d": None, "score": 0}
    avg_volume = _safe_float(df["volume"].tail(20).mean())
    if avg_volume is None or target_avg_volume <= 0:
        return {"avg_volume_20d": avg_volume, "score": 0}
    score = max(0, min(100, round(avg_volume / target_avg_volume * 100)))
    return {"avg_volume_20d": avg_volume, "score": score}


def calculate_price_limit_state(df: pd.DataFrame, ticker: str) -> Dict[str, Any]:
    """Return Vietnam exchange price-limit awareness for the latest candle."""
    limit_pct = get_vn_price_limit_pct(ticker)
    if df is None or len(df) < 2:
        return {
            "limit_pct": limit_pct,
            "ceiling_price": None,
            "floor_price": None,
            "distance_to_limit_pct": None,
            "near_limit": False,
        }
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    close = _safe_float(latest.get("close"))
    prev_close = _safe_float(prev.get("close"))
    if close is None or prev_close is None or prev_close <= 0:
        return {
            "limit_pct": limit_pct,
            "ceiling_price": None,
            "floor_price": None,
            "distance_to_limit_pct": None,
            "near_limit": False,
        }
    ceiling = prev_close * (1 + limit_pct / 100)
    floor = prev_close * (1 - limit_pct / 100)
    distance = min(abs(ceiling - close), abs(close - floor)) / prev_close * 100
    return {
        "limit_pct": limit_pct,
        "ceiling_price": round(ceiling, 2),
        "floor_price": round(floor, 2),
        "distance_to_limit_pct": round(distance, 2),
        "near_limit": distance <= 0.5,
    }


def _round_optional(value: Optional[float], digits: int = 2) -> Optional[float]:
    return round(value, digits) if value is not None else None


def build_corporate_action_reference(
    *,
    previous_close: Optional[float],
    current_price: Optional[float],
    event: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a separate corporate-action reference layer without changing raw OHLCV fields."""
    base = {
        "status": "unavailable",
        "type": "unknown",
        "ex_date": None,
        "cash_dividend_per_share": None,
        "previous_close": _round_optional(previous_close),
        "adjusted_reference_price": None,
        "adjustment_source": "manual_unavailable",
        "price_vs_adjusted_reference": None,
        "price_vs_adjusted_reference_pct": None,
        "note": "Corporate action data is unavailable; raw OHLCV close is unchanged.",
    }
    if not event:
        return base

    event_type = str(event.get("type") or "unknown")
    if event_type != "cash_dividend":
        return {
            **base,
            "status": "detected",
            "type": event_type,
            "ex_date": _valid_date_string(event.get("ex_date")),
            "adjustment_source": str(event.get("adjustment_source") or "provider_event"),
            "note": "Corporate action is shown separately from raw OHLCV close.",
        }

    dividend = _safe_float(event.get("cash_dividend_per_share"))
    if previous_close is None or dividend is None:
        return {
            **base,
            "status": "detected",
            "type": "cash_dividend",
            "ex_date": _valid_date_string(event.get("ex_date")),
            "cash_dividend_per_share": _round_optional(dividend),
            "adjustment_source": str(event.get("adjustment_source") or "provider_event"),
            "note": "Cash dividend event exists, but adjusted reference could not be calculated from available fields.",
        }

    adjusted_reference = previous_close - dividend
    price_diff = current_price - adjusted_reference if current_price is not None else None
    price_diff_pct = price_diff / adjusted_reference * 100 if price_diff is not None and adjusted_reference else None
    return {
        "status": "detected",
        "type": "cash_dividend",
        "ex_date": _valid_date_string(event.get("ex_date")),
        "cash_dividend_per_share": _round_optional(dividend),
        "previous_close": _round_optional(previous_close),
        "adjusted_reference_price": _round_optional(adjusted_reference),
        "adjustment_source": str(event.get("adjustment_source") or "provider_event"),
        "price_vs_adjusted_reference": _round_optional(price_diff),
        "price_vs_adjusted_reference_pct": _round_optional(price_diff_pct),
        "note": "Cash dividend adjustment is shown separately from raw OHLCV close.",
    }


def _latest_rolling_value(series: pd.Series, window: int) -> Optional[float]:
    if len(series.dropna()) < window:
        return None
    return _safe_float(series.rolling(window).mean().iloc[-1])


def calculate_rsi14_simple(close: pd.Series) -> Optional[float]:
    """Calculate latest RSI14 using a simple rolling average. Kept for debug comparison."""
    values = pd.to_numeric(close, errors="coerce").dropna()
    if len(values.dropna()) < 15:
        return None
    delta = values.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = _safe_float(gain.rolling(14).mean().iloc[-1])
    avg_loss = _safe_float(loss.rolling(14).mean().iloc[-1])
    if avg_gain is None or avg_loss is None:
        return None
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_rsi14(close: pd.Series) -> Optional[float]:
    """Calculate latest RSI14 using Wilder/RMA smoothing."""
    values = pd.to_numeric(close, errors="coerce").dropna()
    if len(values) < 15:
        return None
    delta = values.diff().dropna()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = _safe_float(gain.iloc[:14].mean())
    avg_loss = _safe_float(loss.iloc[:14].mean())
    if avg_gain is None or avg_loss is None:
        return None
    for index in range(14, len(delta)):
        avg_gain = (avg_gain * 13 + _safe_float(gain.iloc[index])) / 14
        avg_loss = (avg_loss * 13 + _safe_float(loss.iloc[index])) / 14
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_rsi14_series(close: pd.Series) -> pd.Series:
    """Calculate RSI14 series using the same Wilder/RMA smoothing as calculate_rsi14."""
    values = pd.to_numeric(close, errors="coerce")
    rsi = pd.Series(index=values.index, dtype="float64")
    valid = values.dropna()
    if len(valid) < 15:
        return rsi
    delta = valid.diff().dropna()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = _safe_float(gain.iloc[:14].mean())
    avg_loss = _safe_float(loss.iloc[:14].mean())
    if avg_gain is None or avg_loss is None:
        return rsi

    first_index = valid.index[14]
    if avg_loss == 0:
        rsi.loc[first_index] = 100.0 if avg_gain > 0 else 50.0
    else:
        rs = avg_gain / avg_loss
        rsi.loc[first_index] = 100 - (100 / (1 + rs))

    for index in range(14, len(delta)):
        avg_gain = (avg_gain * 13 + _safe_float(gain.iloc[index])) / 14
        avg_loss = (avg_loss * 13 + _safe_float(loss.iloc[index])) / 14
        output_index = valid.index[index + 1]
        if avg_loss == 0:
            rsi.loc[output_index] = 100.0 if avg_gain > 0 else 50.0
        else:
            rs = avg_gain / avg_loss
            rsi.loc[output_index] = 100 - (100 / (1 + rs))
    return rsi


def _foreign_sum(df: pd.DataFrame, window: int) -> Optional[float]:
    if "foreign_net" not in df.columns:
        return None
    series = pd.to_numeric(df["foreign_net"], errors="coerce").dropna()
    if len(series) < window:
        return None
    return _safe_float(series.tail(window).sum())


def _foreign_history_latest(history: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    if not history:
        return None
    rows = [row for row in history if _valid_date_string(row.get("date"))]
    if not rows:
        return history[0]
    return max(rows, key=lambda row: _valid_date_string(row.get("date")) or "")


def _foreign_history_sum(history: Optional[List[Dict[str, Any]]], window: int) -> Optional[float]:
    if not history:
        return None
    valid_rows = [row for row in history if _safe_float(row.get("net")) is not None]
    if len(valid_rows) < window:
        return None
    ordered_rows = sorted(
        valid_rows,
        key=lambda row: _valid_date_string(row.get("date")) or "",
        reverse=True,
    )
    return _safe_float(sum(_safe_float(row.get("net")) or 0 for row in ordered_rows[:window]))


def _normalize_ssi_daily_stock_price_foreign_history(
    rows: Optional[Iterable[Dict[str, Any]]],
    *,
    limit: int = FOREIGN_HISTORY_LIMIT,
) -> List[Dict[str, Any]]:
    """Return bounded SSI DailyStockPrice foreign-flow rows for indicator windows."""
    history: List[Dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        row_date = _valid_date_string(row.get("date"))
        if not row_date:
            continue
        buy_volume = _safe_float(row.get("foreign_buy_volume"))
        sell_volume = _safe_float(row.get("foreign_sell_volume"))
        net_volume = _safe_float(row.get("foreign_net_volume"))
        buy_value = _safe_float(row.get("foreign_buy_value"))
        sell_value = _safe_float(row.get("foreign_sell_value"))
        net_value = _safe_float(row.get("foreign_net_value"))
        if not any(
            value is not None
            for value in (
                buy_volume,
                sell_volume,
                net_volume,
                buy_value,
                sell_value,
                net_value,
            )
        ):
            continue
        history.append(
            {
                "buy": buy_volume,
                "sell": sell_volume,
                "net": net_volume,
                "buy_value": buy_value,
                "sell_value": sell_value,
                "net_value": net_value,
                "date": row_date,
                "net_unit": "shares"
                if any(value is not None for value in (buy_volume, sell_volume, net_volume))
                else None,
                "value_unit": "VND"
                if any(value is not None for value in (buy_value, sell_value, net_value))
                else None,
                "buy_raw_field": "foreign_buy_volume" if buy_volume is not None else None,
                "sell_raw_field": "foreign_sell_volume" if sell_volume is not None else None,
                "net_raw_field": "foreign_net_volume" if net_volume is not None else None,
            }
        )
    history.sort(key=lambda item: item.get("date") or "")
    if limit and len(history) > limit:
        return history[-limit:]
    return history


def calculate_foreign_history_summary(history: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Calculate latest-available foreign flow sums from quote history rows."""
    valid_rows = [row for row in (history or []) if _safe_float(row.get("net")) is not None]
    latest = _foreign_history_latest(valid_rows)
    return {
        "foreign_net_5d_latest_available": _round_optional(_foreign_history_sum(valid_rows, 5), 0),
        "foreign_net_20d_latest_available": _round_optional(_foreign_history_sum(valid_rows, 20), 0),
        "foreign_net_latest_available_date": _valid_date_string((latest or {}).get("date")),
        "foreign_net_history_count": len(valid_rows),
    }


def _history_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    history = df.copy()
    if "date" in history.columns:
        parsed_dates = pd.to_datetime(history["date"], errors="coerce")
        history = history.assign(_parsed_date=parsed_dates)
        dated = history[history["_parsed_date"].notna()]
        if not dated.empty:
            history = dated.sort_values("_parsed_date")
        history = history.drop(columns=["_parsed_date"], errors="ignore")
    return history.reset_index(drop=True)


def _coverage_status(count: int, *, complete: int, partial: int) -> str:
    if count >= complete:
        return "complete"
    if count >= partial:
        return "partial"
    return "insufficient"


def _calculate_52w_high_low(df: pd.DataFrame) -> Dict[str, Any]:
    history = _history_frame(df).tail(252).copy()
    if "date" not in history.columns or "high" not in history.columns or "low" not in history.columns:
        valid_mask = pd.Series(False, index=history.index)
        valid_count = 0
    else:
        dates = pd.to_datetime(history["date"], errors="coerce")
        high = pd.to_numeric(history["high"], errors="coerce")
        low = pd.to_numeric(history["low"], errors="coerce")
        valid_mask = dates.notna() & high.notna() & low.notna() & (high > 0) & (low > 0)
        valid_count = int(valid_mask.sum())
    coverage_status = _coverage_status(valid_count, complete=240, partial=120)
    result = {
        "high_52w": None,
        "high_52w_date": None,
        "low_52w": None,
        "low_52w_date": None,
        "high_low_52w_history_count": valid_count,
        "high_low_52w_coverage_status": coverage_status,
    }
    if coverage_status == "insufficient":
        return result

    valid_history = history.loc[valid_mask].copy()
    high = pd.to_numeric(history["high"], errors="coerce")
    low = pd.to_numeric(history["low"], errors="coerce")
    valid_high = high.loc[valid_mask]
    valid_low = low.loc[valid_mask]
    if valid_history.empty:
        return result

    max_high = valid_high.max()
    min_low = valid_low.min()
    high_idx = valid_high[valid_high == max_high].index[-1]
    low_idx = valid_low[valid_low == min_low].index[-1]
    result.update(
        {
            "high_52w": _round_optional(_safe_float(max_high)),
            "high_52w_date": _valid_date_string(valid_history.loc[high_idx].get("date")),
            "low_52w": _round_optional(_safe_float(min_low)),
            "low_52w_date": _valid_date_string(valid_history.loc[low_idx].get("date")),
        }
    )
    return result


def _calculate_average_volume_windows(df: pd.DataFrame) -> Dict[str, Any]:
    history = _history_frame(df)
    if "volume" not in history.columns:
        volume = pd.Series(dtype="float64")
    else:
        volume = pd.to_numeric(history["volume"], errors="coerce")
        volume = volume[volume.notna() & (volume >= 0)]
    latest_10d = volume.tail(10)
    latest_3m = volume.tail(63)
    count_10d = int(len(latest_10d))
    count_3m = int(len(latest_3m))
    coverage_10d = "complete" if count_10d >= 10 else "insufficient"
    coverage_3m = _coverage_status(count_3m, complete=60, partial=30)
    return {
        "avg_volume_10d": _round_optional(_safe_float(latest_10d.mean()), 0)
        if coverage_10d == "complete"
        else None,
        "avg_volume_10d_history_count": count_10d,
        "avg_volume_10d_coverage_status": coverage_10d,
        "avg_volume_3m": _round_optional(_safe_float(latest_3m.mean()), 0)
        if coverage_3m != "insufficient"
        else None,
        "avg_volume_3m_history_count": count_3m,
        "avg_volume_3m_coverage_status": coverage_3m,
    }


def _calculate_price_vs_reference_pct(
    daily_close: Optional[float],
    reference_price: Optional[float],
) -> Dict[str, Any]:
    if daily_close is None or daily_close <= 0:
        return {
            "price_vs_reference_pct": None,
            "price_vs_reference_status": "daily_close_unavailable",
        }
    if reference_price is None or reference_price <= 0:
        return {
            "price_vs_reference_pct": None,
            "price_vs_reference_status": "reference_unavailable",
        }
    return {
        "price_vs_reference_pct": _round_optional((daily_close - reference_price) / reference_price * 100, 2),
        "price_vs_reference_status": "ok",
    }


def _calculate_daily_range_pct(
    latest_high: Optional[float],
    latest_low: Optional[float],
    daily_close: Optional[float],
) -> Dict[str, Any]:
    if (
        latest_high is None
        or latest_low is None
        or daily_close is None
        or daily_close <= 0
        or latest_high < latest_low
    ):
        return {
            "daily_range_pct": None,
            "daily_range_status": "insufficient",
        }
    return {
        "daily_range_pct": _round_optional((latest_high - latest_low) / daily_close * 100, 2),
        "daily_range_status": "ok",
    }


def _ssi_derived_metrics_status(metrics: Dict[str, Any]) -> str:
    statuses = [
        str(metrics.get("high_low_52w_coverage_status") or "insufficient"),
        str(metrics.get("avg_volume_10d_coverage_status") or "insufficient"),
        str(metrics.get("avg_volume_3m_coverage_status") or "insufficient"),
        str(metrics.get("price_vs_reference_status") or "reference_unavailable"),
        str(metrics.get("daily_range_status") or "insufficient"),
    ]
    if all(status in {"complete", "ok"} for status in statuses):
        return "ok"
    if any(status in {"complete", "partial", "ok"} for status in statuses):
        return "partial"
    return "insufficient"


def _status_detail(label: str, severity: str, reason: str, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if label not in VN_ALLOWED_STATUS_LABELS:
        raise ValueError(f"Unsupported Vietnam status label: {label}")
    if label in VN_FORBIDDEN_STATUS_LABELS:
        raise ValueError(f"Forbidden recommendation label: {label}")
    return {
        "label": label,
        "severity": severity,
        "reason": reason,
        "inputs": inputs or {},
    }


def _intraday_detail(label: str, severity: str, reason: str, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if label not in VN_ALLOWED_INTRADAY_LABELS:
        raise ValueError(f"Unsupported Vietnam intraday label: {label}")
    if label in VN_FORBIDDEN_INTRADAY_LABELS:
        raise ValueError(f"Forbidden intraday recommendation label: {label}")
    return {
        "label": label,
        "severity": severity,
        "reason": reason,
        "inputs": inputs or {},
    }


def normalize_intraday_candles(df: Optional[pd.DataFrame], limit: int = 8) -> List[Dict[str, Any]]:
    """Normalize intraday OHLCV rows for API output."""
    if df is None or df.empty:
        return []

    def is_missing_intraday_value(value: Any) -> bool:
        if value in (None, ""):
            return True
        try:
            return bool(pd.isna(value))
        except (TypeError, ValueError):
            return False

    rows = []
    for raw in df.tail(limit).to_dict("records"):
        timestamp = raw.get("timestamp")
        date_time = raw.get("date_time") or raw.get("datetime") or raw.get("date")
        close = _safe_float(raw.get("close"))
        if (is_missing_intraday_value(timestamp) and is_missing_intraday_value(date_time)) or close is None:
            continue
        rows.append(
            {
                "timestamp": timestamp,
                "date_time": date_time,
                "open": _safe_float(raw.get("open")),
                "high": _safe_float(raw.get("high")),
                "low": _safe_float(raw.get("low")),
                "close": close,
                "volume": _safe_float(raw.get("volume")),
                "ticker": raw.get("ticker"),
            }
        )
    return rows


def _intraday_candle_vn_date(candle: Dict[str, Any]) -> Optional[str]:
    value = candle.get("date_time") or candle.get("timestamp")
    if value in (None, ""):
        return None
    timestamp: Optional[datetime] = None
    numeric = _safe_float(value)
    if numeric is not None and numeric > 1_000_000_000:
        timestamp = datetime.fromtimestamp(numeric, tz=timezone.utc)
    else:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        timestamp = parsed.to_pydatetime()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(VN_TIMEZONE).date().isoformat()


def _intraday_candle_vn_datetime(candle: Dict[str, Any]) -> Optional[datetime]:
    value = candle.get("date_time") or candle.get("timestamp")
    if value in (None, ""):
        return None
    numeric = _safe_float(value)
    if numeric is not None and numeric > 1_000_000_000:
        return datetime.fromtimestamp(numeric, tz=timezone.utc).astimezone(VN_TIMEZONE)
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    timestamp = parsed.to_pydatetime()
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=VN_TIMEZONE)
    return timestamp.astimezone(VN_TIMEZONE)


def _requested_timeframe_seconds(timeframe: Optional[str]) -> Optional[int]:
    raw = str(timeframe or "").strip().lower()
    if not raw:
        return None
    aliases = {
        "1": 60,
        "1m": 60,
        "1min": 60,
        "5": 300,
        "5m": 300,
        "5min": 300,
        "15": 900,
        "15m": 900,
        "15min": 900,
        "30": 1800,
        "30m": 1800,
        "30min": 1800,
        "60": 3600,
        "60m": 3600,
        "1h": 3600,
        "1hour": 3600,
        "1d": 86400,
        "d": 86400,
        "day": 86400,
    }
    return aliases.get(raw)


def _granularity_label_from_seconds(seconds: Optional[int]) -> str:
    if seconds is None:
        return "unknown"
    if 45 <= seconds <= 90:
        return "1m"
    if 240 <= seconds <= 360:
        return "5m"
    if 840 <= seconds <= 960:
        return "15m"
    if 1740 <= seconds <= 1860:
        return "30m"
    if 3300 <= seconds <= 3900:
        return "1h"
    if 82800 <= seconds <= 90000:
        return "daily-like"
    return f"{max(1, round(seconds / 60))}m"


def _detect_intraday_granularity(
    candles: List[Dict[str, Any]],
    requested_timeframe: Optional[str] = None,
) -> Dict[str, Any]:
    datetimes = [_intraday_candle_vn_datetime(candle) for candle in candles]
    datetimes = sorted(value for value in datetimes if value is not None)
    deltas = [
        int((right - left).total_seconds())
        for left, right in zip(datetimes, datetimes[1:])
        if int((right - left).total_seconds()) > 0
    ]
    if not deltas:
        return {
            "intraday_granularity": "unknown",
            "intraday_granularity_seconds": None,
            "intraday_granularity_label": "provider-returned",
            "intraday_actual_granularity": "unknown",
            "intraday_actual_granularity_seconds": None,
            "intraday_cadence_status": "unknown",
        }
    seconds = int(statistics.median(deltas))
    unique_deltas = sorted(set(deltas))
    tolerance = max(30, int(seconds * 0.2))
    irregular = len(unique_deltas) > 1 and any(abs(delta - seconds) > tolerance for delta in unique_deltas)
    if irregular:
        granularity = "unknown"
        cadence_status = "irregular"
    else:
        granularity = _granularity_label_from_seconds(seconds)
        requested_seconds = _requested_timeframe_seconds(requested_timeframe)
        if requested_seconds is None:
            cadence_status = "unknown"
        elif abs(seconds - requested_seconds) <= max(30, int(requested_seconds * 0.2)):
            cadence_status = "matched"
        else:
            cadence_status = "different_from_requested"
    return {
        "intraday_granularity": granularity,
        "intraday_granularity_seconds": None if irregular else seconds,
        "intraday_granularity_label": granularity,
        "intraday_actual_granularity": granularity,
        "intraday_actual_granularity_seconds": None if irregular else seconds,
        "intraday_cadence_status": cadence_status,
    }


def _latest_vn_session_candles(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    dated = [(candle, _intraday_candle_vn_date(candle)) for candle in candles]
    dates = [date for _, date in dated if date]
    if not dates:
        return []
    latest_date = max(dates)
    return [candle for candle, date in dated if date == latest_date]


def calculate_intraday_pulse(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate neutral intraday pulse metrics from provider-returned candles."""
    if not candles:
        return {
            "latest_1h_close": None,
            "latest_1h_open": None,
            "latest_1h_high": None,
            "latest_1h_low": None,
            "latest_1h_volume": None,
            "latest_1h_change": None,
            "latest_1h_change_percent": None,
            "session_high_from_1h": None,
            "session_low_from_1h": None,
            "session_range_pct_from_1h": None,
            "session_volume_from_1h": None,
            "session_candles_count": 0,
            "cumulative_1h_volume": None,
            "loaded_candles_total_volume": None,
            "direction": "unknown",
            "range_percent": None,
            "volume_vs_avg_1h": None,
            "latest_intraday_close": None,
            "latest_intraday_open": None,
            "latest_intraday_high": None,
            "latest_intraday_low": None,
            "latest_intraday_volume": None,
            "intraday_change": None,
            "intraday_change_percent": None,
            "session_high_from_intraday": None,
            "session_low_from_intraday": None,
            "session_range_pct_from_intraday": None,
            "session_volume_from_intraday": None,
            "intraday_volume_vs_average": None,
        }

    latest = candles[-1]
    latest_open = _safe_float(latest.get("open"))
    latest_high = _safe_float(latest.get("high"))
    latest_low = _safe_float(latest.get("low"))
    latest_close = _safe_float(latest.get("close"))
    latest_volume = _safe_float(latest.get("volume"))
    latest_change = latest_close - latest_open if latest_close is not None and latest_open is not None else None
    latest_change_pct = latest_change / latest_open * 100 if latest_change is not None and latest_open else None
    session_candles = _latest_vn_session_candles(candles)
    session_highs = [_safe_float(candle.get("high")) for candle in session_candles]
    session_lows = [_safe_float(candle.get("low")) for candle in session_candles]
    session_volumes = [_safe_float(candle.get("volume")) for candle in session_candles]
    session_open = _safe_float(session_candles[0].get("open")) if session_candles else None
    session_high = max(value for value in session_highs if value is not None) if any(value is not None for value in session_highs) else None
    session_low = min(value for value in session_lows if value is not None) if any(value is not None for value in session_lows) else None
    session_volume = sum(value for value in session_volumes if value is not None) if any(value is not None for value in session_volumes) else None
    volumes = [_safe_float(candle.get("volume")) for candle in candles]
    loaded_total_volume = sum(value for value in volumes if value is not None) if any(value is not None for value in volumes) else None
    previous_volumes = [value for value in volumes[:-1] if value is not None]
    avg_previous_volume = sum(previous_volumes) / len(previous_volumes) if len(previous_volumes) >= 2 else None

    if latest_change is None:
        direction = "unknown"
    elif latest_change > 0:
        direction = "up"
    elif latest_change < 0:
        direction = "down"
    else:
        direction = "flat"

    pulse = {
        "latest_1h_close": _round_optional(latest_close),
        "latest_1h_open": _round_optional(latest_open),
        "latest_1h_high": _round_optional(latest_high),
        "latest_1h_low": _round_optional(latest_low),
        "latest_1h_volume": _round_optional(latest_volume, 0),
        "latest_1h_change": _round_optional(latest_change),
        "latest_1h_change_percent": _round_optional(latest_change_pct, 2),
        "session_high_from_1h": _round_optional(session_high),
        "session_low_from_1h": _round_optional(session_low),
        "session_range_pct_from_1h": _round_optional((session_high - session_low) / session_open * 100, 2) if session_high is not None and session_low is not None and session_open else None,
        "session_volume_from_1h": _round_optional(session_volume, 0),
        "session_candles_count": len(session_candles),
        "cumulative_1h_volume": _round_optional(loaded_total_volume, 0),
        "loaded_candles_total_volume": _round_optional(loaded_total_volume, 0),
        "direction": direction,
        "range_percent": _round_optional((latest_high - latest_low) / latest_open * 100, 2) if latest_high is not None and latest_low is not None and latest_open else None,
        "volume_vs_avg_1h": _round_optional(latest_volume / avg_previous_volume, 2) if latest_volume is not None and avg_previous_volume else None,
    }
    pulse.update(
        {
            "latest_intraday_close": pulse["latest_1h_close"],
            "latest_intraday_open": pulse["latest_1h_open"],
            "latest_intraday_high": pulse["latest_1h_high"],
            "latest_intraday_low": pulse["latest_1h_low"],
            "latest_intraday_volume": pulse["latest_1h_volume"],
            "intraday_change": pulse["latest_1h_change"],
            "intraday_change_percent": pulse["latest_1h_change_percent"],
            "session_high_from_intraday": pulse["session_high_from_1h"],
            "session_low_from_intraday": pulse["session_low_from_1h"],
            "session_range_pct_from_intraday": pulse["session_range_pct_from_1h"],
            "session_volume_from_intraday": pulse["session_volume_from_1h"],
            "intraday_volume_vs_average": pulse["volume_vs_avg_1h"],
        }
    )
    return pulse


def derive_intraday_details(candles: List[Dict[str, Any]], pulse: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return neutral intraday condition labels with reasons."""
    details: List[Dict[str, Any]] = [
        _intraday_detail(
            "Not realtime quote",
            "caution",
            "Intraday candle data is separate from a realtime matched quote.",
            {"source": "SSI IntradayOhlc", "is_realtime_quote": False},
        )
    ]
    if len(candles) < 3:
        details.append(
            _intraday_detail(
                "Intraday data limited",
                "caution",
                "Fewer than 3 intraday candles are available.",
                {"candles_loaded": len(candles)},
            )
        )

    direction = pulse.get("direction")
    if direction == "up":
        details.append(
            _intraday_detail(
                "Intraday up",
                "info",
                "Latest provider-returned intraday candle close is above its open.",
                {"latest_1h_open": pulse.get("latest_1h_open"), "latest_1h_close": pulse.get("latest_1h_close")},
            )
        )
    elif direction == "down":
        details.append(
            _intraday_detail(
                "Intraday down",
                "info",
                "Latest provider-returned intraday candle close is below its open.",
                {"latest_1h_open": pulse.get("latest_1h_open"), "latest_1h_close": pulse.get("latest_1h_close")},
            )
        )
    elif direction == "flat":
        details.append(
            _intraday_detail(
                "Intraday flat",
                "info",
                "Latest provider-returned intraday candle close equals its open.",
                {"latest_1h_open": pulse.get("latest_1h_open"), "latest_1h_close": pulse.get("latest_1h_close")},
            )
        )

    volume_ratio = _safe_float(pulse.get("volume_vs_avg_1h"))
    if volume_ratio is not None and volume_ratio >= 1.5:
        details.append(
            _intraday_detail(
                "Intraday volume expansion",
                "info",
                "Latest provider-returned intraday volume is at least 1.5 times the average of previous available intraday candles.",
                {"volume_vs_avg_1h": volume_ratio},
            )
        )

    range_percent = _safe_float(pulse.get("range_percent"))
    if range_percent is not None and range_percent >= 1.5:
        details.append(
            _intraday_detail(
                "Intraday wide range",
                "caution",
                "Latest provider-returned intraday candle range is at least 1.5% of its open.",
                {"range_percent": range_percent},
            )
        )

    seen = set()
    deduped = []
    for detail in details:
        label = detail["label"]
        if label in seen:
            continue
        seen.add(label)
        deduped.append(detail)
    return deduped


def derive_neutral_status_details(
    indicators: Dict[str, Any],
    change_pct: Optional[float] = None,
    *,
    latest_price: Optional[float] = None,
    final_close_status: str = "unknown",
    candle_status: str = "unknown",
    adjusted_price_status: str = "unknown",
    foreign_date_match: str = "unknown",
    foreign_net_date: Optional[str] = None,
    foreign_net_unit: str = "unknown",
    foreign_net: Optional[float] = None,
    rows_loaded: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return neutral condition labels with reasons; never emit recommendations."""
    details: List[Dict[str, Any]] = []
    close = _safe_float(latest_price)
    if close is None:
        close = _safe_float(indicators.get("close"))
    ma20 = _safe_float(indicators.get("ma20"))
    ma50 = _safe_float(indicators.get("ma50"))
    rsi14 = _safe_float(indicators.get("rsi14_wilder") if indicators.get("rsi14_wilder") is not None else indicators.get("rsi14"))
    volume_ratio = _safe_float(indicators.get("volume_ratio"))
    avg_volume_20d = _safe_float(indicators.get("avg_volume_20d"))
    high_20d = _safe_float(indicators.get("high_20d"))
    low_20d = _safe_float(indicators.get("low_20d"))
    bollinger = indicators.get("bollinger") or {}
    bollinger_upper = _safe_float(bollinger.get("upper") if isinstance(bollinger, dict) else None)
    rows_count = int(rows_loaded or 0)
    too_few_candles = rows_count < 20 or ma20 is None or avg_volume_20d is None or high_20d is None or low_20d is None

    has_main_trend = False
    change_available = change_pct is not None
    stronger_change_ok = (change_pct or 0) >= 0 if change_available else True
    if close is not None and ma20 is not None and ma50 is not None and close >= ma20 and ma20 >= ma50 and stronger_change_ok:
        details.append(
            _status_detail(
                "Stronger than short-term average",
                "info",
                "Latest price is at or above MA20 and MA20 is at or above MA50.",
                {"latest_price": close, "ma20": ma20, "ma50": ma50, "change_pct": change_pct},
            )
        )
        has_main_trend = True

    weak_ma = ma20 is not None and ma50 is not None and ma20 < ma50
    weak_change = change_pct is not None and change_pct < 0
    if close is not None and ma20 is not None and close < ma20 and (weak_ma or weak_change):
        details.append(
            _status_detail(
                "Weak short-term",
                "caution",
                "Latest price is below MA20 with weaker moving-average or daily change context.",
                {"latest_price": close, "ma20": ma20, "ma50": ma50, "change_pct": change_pct},
            )
        )
        has_main_trend = True

    if close is not None and low_20d and close >= low_20d:
        distance_low = (close - low_20d) / low_20d * 100
        if distance_low <= 3:
            details.append(
                _status_detail(
                    "Near support",
                    "info",
                    "Latest price is within 3% above the 20-day low.",
                    {"latest_price": close, "low_20d": low_20d, "distance_percent": round(distance_low, 2)},
                )
            )
            has_main_trend = True

    if close is not None and high_20d and close <= high_20d:
        distance_high_below = (high_20d - close) / high_20d * 100
        if distance_high_below <= 3:
            details.append(
                _status_detail(
                    "Near resistance",
                    "info",
                    "Latest price is within 3% below the 20-day high.",
                    {"latest_price": close, "high_20d": high_20d, "distance_percent": round(distance_high_below, 2)},
                )
            )
            has_main_trend = True

    if close is not None and high_20d and volume_ratio is not None:
        distance_to_high_abs = abs(close - high_20d) / high_20d * 100
        if distance_to_high_abs <= 0.5 and volume_ratio >= 1.2:
            details.append(
                _status_detail(
                    "Breakout candidate",
                    "info" if final_close_status == "final" else "caution",
                    "Latest price is within 0.5% of the 20-day high with elevated volume.",
                    {
                        "latest_price": close,
                        "high_20d": high_20d,
                        "distance_percent": round(distance_to_high_abs, 2),
                        "volume_ratio": volume_ratio,
                        "final_close_status": final_close_status,
                    },
                )
            )
            has_main_trend = True

    overextended_inputs: Dict[str, Any] = {}
    if rsi14 is not None and rsi14 >= 70:
        overextended_inputs["rsi14_wilder"] = rsi14
    if close is not None and bollinger_upper is not None and close >= bollinger_upper:
        overextended_inputs["latest_price"] = close
        overextended_inputs["bollinger_upper"] = bollinger_upper
    if overextended_inputs:
        details.append(
            _status_detail(
                "Overextended",
                "risk",
                "RSI14 is elevated or latest price is at/above the Bollinger upper band.",
                overextended_inputs,
            )
        )
        has_main_trend = True

    if volume_ratio is not None and volume_ratio >= 1.5:
        details.append(
            _status_detail(
                "Volume expansion",
                "info",
                "Today volume is at least 1.5 times the 20-day average volume.",
                {"volume_ratio": volume_ratio},
            )
        )

    if avg_volume_20d is not None and avg_volume_20d < 100_000:
        details.append(
            _status_detail(
                "Low liquidity",
                "risk",
                "20-day average volume is below 100,000 shares.",
                {"avg_volume_20d": avg_volume_20d},
            )
        )

    if foreign_date_match != "matched" or not foreign_net_date:
        details.append(
            _status_detail(
                "Foreign data stale",
                "caution",
                "Foreign net date is missing or does not match the OHLCV date.",
                {"foreign_date_match": foreign_date_match, "foreign_net_date": foreign_net_date},
            )
        )

    foreign_value = _safe_float(foreign_net)
    if foreign_date_match == "matched" and foreign_net_unit == "shares" and foreign_value is not None and foreign_value > 0:
        details.append(
            _status_detail(
                "Foreign net positive",
                "info",
                "Matched-date foreign net quantity is positive.",
                {"foreign_net": foreign_value, "foreign_net_unit": foreign_net_unit},
            )
        )
    if foreign_date_match == "matched" and foreign_net_unit == "shares" and foreign_value is not None and foreign_value < 0:
        details.append(
            _status_detail(
                "Foreign net negative",
                "caution",
                "Matched-date foreign net quantity is negative.",
                {"foreign_net": foreign_value, "foreign_net_unit": foreign_net_unit},
            )
        )

    if final_close_status != "final" or candle_status != "final" or adjusted_price_status == "unknown" or too_few_candles:
        details.append(
            _status_detail(
                "Indicator caution",
                "caution",
                "Indicator inputs include non-final, unknown-adjustment, or limited-history data.",
                {
                    "final_close_status": final_close_status,
                    "candle_status": candle_status,
                    "adjusted_price_status": adjusted_price_status,
                    "rows_loaded": rows_loaded,
                    "too_few_candles": too_few_candles,
                },
            )
        )

    if final_close_status == "unknown":
        details.append(
            _status_detail(
                "Price finality unknown",
                "caution",
                "The dashboard cannot confirm whether the latest daily candle is final.",
                {"final_close_status": final_close_status},
            )
        )

    if adjusted_price_status == "unknown":
        details.append(
            _status_detail(
                "Adjusted price unknown",
                "caution",
                "The dashboard cannot confirm whether the OHLCV prices are adjusted or unadjusted.",
                {"adjusted_price_status": adjusted_price_status},
            )
        )

    if not has_main_trend:
        details.insert(0, _status_detail("Watch", "info", "No stronger short-term, weak short-term, support, resistance, breakout, or overextended condition is active.", {}))

    seen = set()
    deduped = []
    for detail in details:
        label = detail["label"]
        if label in seen:
            continue
        seen.add(label)
        deduped.append(detail)
    return deduped


def derive_neutral_status_labels(indicators: Dict[str, Any], change_pct: Optional[float] = None, **kwargs: Any) -> List[str]:
    """Return neutral watchlist status labels; these are not recommendations."""
    return [detail["label"] for detail in derive_neutral_status_details(indicators, change_pct, **kwargs)]


def calculate_vietnam_indicators(
    df: pd.DataFrame,
    foreign_latest: Optional[Dict[str, Any]] = None,
    foreign_history: Optional[List[Dict[str, Any]]] = None,
    reference_price: Optional[float] = None,
) -> Dict[str, Any]:
    """Calculate neutral Vietnam watchlist indicators for the latest row."""
    if df is None or df.empty:
        return {}
    close = pd.to_numeric(df.get("close"), errors="coerce")
    high = pd.to_numeric(df.get("high"), errors="coerce")
    low = pd.to_numeric(df.get("low"), errors="coerce")
    volume = pd.to_numeric(df.get("volume"), errors="coerce")
    latest_close = _safe_float(close.iloc[-1])
    latest_volume = _safe_float(volume.iloc[-1])

    ma20 = _latest_rolling_value(close, 20)
    ma50 = _latest_rolling_value(close, 50)
    rsi14 = calculate_rsi14(close)
    rsi14_simple = calculate_rsi14_simple(close)
    bb_middle = ma20
    bb_std = _safe_float(close.rolling(20).std(ddof=0).iloc[-1]) if len(close.dropna()) >= 20 else None
    bb_upper = (bb_middle + 2 * bb_std) if bb_middle is not None and bb_std is not None else None
    bb_lower = (bb_middle - 2 * bb_std) if bb_middle is not None and bb_std is not None else None
    avg_volume_20d = _safe_float(volume.rolling(20).mean().iloc[-1]) if len(volume.dropna()) >= 20 else None
    volume_ratio = latest_volume / avg_volume_20d if latest_volume is not None and avg_volume_20d else None
    high_20d = _safe_float(high.rolling(20).max().iloc[-1]) if len(high.dropna()) >= 20 else None
    low_20d = _safe_float(low.rolling(20).min().iloc[-1]) if len(low.dropna()) >= 20 else None
    distance_high = ((latest_close - high_20d) / high_20d * 100) if latest_close is not None and high_20d else None
    distance_low = ((latest_close - low_20d) / low_20d * 100) if latest_close is not None and low_20d else None
    foreign_net_5d = _foreign_sum(df, 5)
    foreign_net_20d = _foreign_sum(df, 20)
    foreign_history_summary = calculate_foreign_history_summary(foreign_history)
    ssi_derived_metrics = {
        **_calculate_52w_high_low(df),
        **_calculate_average_volume_windows(df),
        **_calculate_price_vs_reference_pct(latest_close, _safe_float(reference_price)),
        **_calculate_daily_range_pct(_safe_float(high.iloc[-1]), _safe_float(low.iloc[-1]), latest_close),
        "ssi_derived_metrics_source": "SSI DailyOhlc + SSI DailyStockPrice",
    }
    ssi_derived_metrics["ssi_derived_metrics_status"] = _ssi_derived_metrics_status(ssi_derived_metrics)

    return {
        "close": _round_optional(latest_close),
        "ma20": _round_optional(ma20),
        "ma50": _round_optional(ma50),
        "rsi14": _round_optional(rsi14),
        "rsi14_wilder": _round_optional(rsi14),
        "rsi14_simple_debug": _round_optional(rsi14_simple),
        "rsi_method": "Wilder/RMA",
        "bollinger": {
            "middle": _round_optional(bb_middle),
            "upper": _round_optional(bb_upper),
            "lower": _round_optional(bb_lower),
        },
        "avg_volume_20d": _round_optional(avg_volume_20d, 0),
        "volume_ratio": _round_optional(volume_ratio, 2),
        "high_20d": _round_optional(high_20d),
        "low_20d": _round_optional(low_20d),
        "distance_to_20d_high_pct": _round_optional(distance_high, 2),
        "distance_to_20d_low_pct": _round_optional(distance_low, 2),
        "foreign_net_5d": _round_optional(foreign_net_5d, 0),
        "foreign_net_20d": _round_optional(foreign_net_20d, 0),
        "foreign_net_latest": _round_optional(_safe_float((foreign_latest or {}).get("net")), 0),
        **ssi_derived_metrics,
        **foreign_history_summary,
    }


def normalize_daily_chart_data(df: Optional[pd.DataFrame], limit: int = VN_CHART_POINT_LIMIT) -> List[Dict[str, Any]]:
    """Normalize daily OHLCV rows and matching indicators for inspect charts."""
    if df is None or df.empty:
        return []

    chart_df = df.sort_values("date").tail(limit).reset_index(drop=True).copy()
    close = pd.to_numeric(chart_df.get("close"), errors="coerce")
    volume = pd.to_numeric(chart_df.get("volume"), errors="coerce")
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    volume_ma20 = volume.rolling(20).mean()
    volume_ma50 = volume.rolling(50).mean()
    bb_std = close.rolling(20).std(ddof=0)
    bb_upper = ma20 + (2 * bb_std)
    bb_lower = ma20 - (2 * bb_std)
    rsi14 = calculate_rsi14_series(close)

    rows: List[Dict[str, Any]] = []
    for index, raw in chart_df.iterrows():
        rows.append(
            {
                "date": _valid_date_string(raw.get("date")),
                "time": int(pd.Timestamp(raw.get("date")).timestamp()) if _valid_date_string(raw.get("date")) else None,
                "open": _round_optional(_safe_float(raw.get("open"))),
                "high": _round_optional(_safe_float(raw.get("high"))),
                "low": _round_optional(_safe_float(raw.get("low"))),
                "close": _round_optional(_safe_float(raw.get("close"))),
                "volume": _round_optional(_safe_float(volume.iloc[index]), 0),
                "volume_ma20": _round_optional(_safe_float(volume_ma20.iloc[index]), 0),
                "volume_ma50": _round_optional(_safe_float(volume_ma50.iloc[index]), 0),
                "ma20": _round_optional(_safe_float(ma20.iloc[index])),
                "ma50": _round_optional(_safe_float(ma50.iloc[index])),
                "rsi14": _round_optional(_safe_float(rsi14.iloc[index])),
                "bb_upper": _round_optional(_safe_float(bb_upper.iloc[index])),
                "bb_mid": _round_optional(_safe_float(ma20.iloc[index])),
                "bb_lower": _round_optional(_safe_float(bb_lower.iloc[index])),
            }
        )
    return rows


def filter_chart_points_by_range(points: List[Dict[str, Any]], range_label: str) -> List[Dict[str, Any]]:
    """Filter chart points after indicator warmup has been calculated."""
    if not points:
        return []
    days = VN_CHART_RANGES.get(range_label.upper(), VN_CHART_RANGES["6M"])
    dates = [
        pd.to_datetime(point.get("date"), errors="coerce")
        for point in points
        if point.get("date")
    ]
    valid_dates = [date for date in dates if not pd.isna(date)]
    if not valid_dates:
        return points
    latest_date = max(valid_dates)
    cutoff = latest_date - pd.Timedelta(days=days)
    filtered = [
        point
        for point in points
        if point.get("date") and not pd.isna(pd.to_datetime(point.get("date"), errors="coerce"))
        and pd.to_datetime(point.get("date"), errors="coerce") >= cutoff
    ]
    return filtered or points


class VietnamMarketService:
    def __init__(
        self,
        manager: Optional[DataFetcherManager] = None,
        config: Optional[VietnamDashboardConfig] = None,
        ssi_fetcher: Optional[SsiFastConnectFetcher] = None,
        corporate_actions_provider: Optional[CorporateActionsProvider] = None,
    ):
        self.config = config or _default_dashboard_config()
        if manager is not None:
            self.manager = manager
        elif self.config.allow_legacy_mozyfin_provider and self.config.mozyfin_enabled:
            self.manager = DataFetcherManager()
        else:
            self.manager = None
        self._ssi_fetcher = ssi_fetcher
        self._corporate_actions_provider = corporate_actions_provider

    def _get_ssi_fetcher(self) -> SsiFastConnectFetcher:
        if self._ssi_fetcher is None:
            streaming_realtime_manager = None
            try:
                from src.services.ssi_streaming_realtime_lifecycle import (
                    get_existing_ssi_streaming_realtime_manager,
                )

                streaming_realtime_manager = get_existing_ssi_streaming_realtime_manager()
            except Exception:  # noqa: BLE001 - lifecycle state is best-effort.
                streaming_realtime_manager = None
            if streaming_realtime_manager is not None:
                self._ssi_fetcher = SsiFastConnectFetcher(
                    realtime_enabled=self.config.ssi_realtime_enabled,
                    streaming_realtime_enabled=self.config.ssi_streaming_realtime_enabled,
                    streaming_realtime_manager=streaming_realtime_manager,
                )
            else:
                self._ssi_fetcher = SsiFastConnectFetcher()
        return self._ssi_fetcher

    def _get_corporate_actions_provider(self) -> CorporateActionsProvider:
        if self._corporate_actions_provider is not None:
            return self._corporate_actions_provider
        provider_name = str(self.config.corporate_actions_provider or "disabled").strip().lower()
        if not self.config.corporate_actions_provider_enabled or provider_name in {"", "disabled", "none"}:
            return DisabledCorporateActionsProvider()
        return NotConfiguredCorporateActionsProvider(provider_name)

    @staticmethod
    def _provider_label(provider: str) -> str:
        return VN_SOURCE_SSI if provider == VN_PROVIDER_SSI else VN_SOURCE_MOZYFIN

    @staticmethod
    def _safe_provider_reason(payload: Any, fallback: str = "SSI provider unavailable") -> str:
        if not isinstance(payload, dict):
            return fallback
        reason = str(payload.get("reason") or "")
        if reason in {
            "SSI FastConnect disabled",
            "SSI FastConnect credentials missing",
            "SSI FastConnect request failed",
            DAILY_OHLC_RATE_LIMIT_COOLDOWN_REASON,
        }:
            return reason
        return fallback

    @staticmethod
    def _ssi_ohlcv_dataframe(symbol: str, rows: List[Dict[str, Any]]) -> pd.DataFrame:
        records: List[Dict[str, Any]] = []
        exchange = get_vn_exchange(symbol)
        for row in rows:
            date_value = pd.to_datetime(row.get("date"), errors="coerce")
            if pd.isna(date_value):
                continue
            records.append(
                {
                    "date": date_value,
                    "open": _safe_float(row.get("open")),
                    "high": _safe_float(row.get("high")),
                    "low": _safe_float(row.get("low")),
                    "close": _safe_float(row.get("close")),
                    "volume": _safe_float(row.get("volume")),
                    "amount": _safe_float(row.get("value")),
                    "exchange": exchange,
                    "market_index": "VNINDEX.VN",
                    "price_adjustment_status": "unknown",
                }
            )
        if not records:
            return pd.DataFrame()
        return pd.DataFrame(records).sort_values("date").reset_index(drop=True)

    def _load_ssi_daily_ohlcv(self, symbol: str, limit: int) -> Tuple[pd.DataFrame, str]:
        payload = self._get_ssi_fetcher().get_daily_ohlcv(symbol, limit=limit)
        if payload.get("status") != "ok":
            raise RuntimeError(self._safe_provider_reason(payload))
        rows = payload.get("rows") or []
        df = self._ssi_ohlcv_dataframe(symbol, rows)
        if df.empty:
            raise RuntimeError("SSI DailyOhlc returned no rows")
        return df, VN_SOURCE_SSI

    def _load_mozyfin_daily_ohlcv(self, symbol: str, days: int) -> Tuple[pd.DataFrame, str]:
        if not self.config.allow_legacy_mozyfin_provider or self.manager is None:
            raise RuntimeError("Mozyfin is disabled for VN dashboard runtime.")
        return self.manager.get_daily_data(normalize_vn_symbol(symbol), days=days)

    def _daily_ohlcv_cache_key(self, symbol: str, provider: str, *, limit: int, days: int) -> Tuple[Any, ...]:
        params: Dict[str, Any] = {"timeframe": "1d", "limit": limit, "days": days}
        if provider == VN_PROVIDER_SSI:
            params["provider"] = VN_PROVIDER_SSI
        return _cache_key("ohlcv", symbol, **params)

    def _build_daily_ohlcv_loader(
        self,
        symbol: str,
        provider: str,
        *,
        limit: int,
        days: int,
    ) -> Callable[[], Tuple[pd.DataFrame, str, Dict[str, Any]]]:
        primary_source = self._provider_label(provider)

        def load() -> Tuple[pd.DataFrame, str, Dict[str, Any]]:
            if provider == VN_PROVIDER_SSI:
                try:
                    df, source = self._load_ssi_daily_ohlcv(symbol, limit)
                    return df, source, {
                        "status": "ok",
                        "primary_source": primary_source,
                        "actual_source": VN_SOURCE_SSI,
                        "fallback_used": False,
                        "fallback_reason": None,
                        "unavailable_reason": None,
                    }
                except Exception as exc:
                    return pd.DataFrame(), VN_SOURCE_SSI, {
                        "status": "unavailable",
                        "primary_source": primary_source,
                        "actual_source": VN_SOURCE_SSI,
                        "fallback_used": False,
                        "fallback_reason": None,
                        "unavailable_reason": _safe_cache_error_text(exc, SSI_UNAVAILABLE_REASON),
                    }

            try:
                df, source = self._load_mozyfin_daily_ohlcv(symbol, days)
                return df, source, {
                    "status": "ok",
                    "primary_source": VN_SOURCE_MOZYFIN,
                    "actual_source": VN_SOURCE_MOZYFIN,
                    "fallback_used": False,
                    "fallback_reason": None,
                    "unavailable_reason": None,
                }
            except Exception as exc:
                return pd.DataFrame(), VN_SOURCE_SSI, {
                    "status": "unavailable",
                    "primary_source": VN_SOURCE_SSI,
                    "actual_source": VN_SOURCE_SSI,
                    "fallback_used": False,
                    "fallback_reason": None,
                    "unavailable_reason": str(exc) or "Mozyfin is disabled for VN dashboard runtime.",
                }

        return load

    def _intraday_payload_from_rows(
        self,
        symbol: str,
        rows: List[Dict[str, Any]],
        intraday_timeframe: str,
        intraday_limit: int,
    ) -> Dict[str, Any]:
        normalized_row_count = len(rows or [])
        df = pd.DataFrame(rows or [])
        if not df.empty and "date_time" in df.columns:
            df = df.sort_values("date_time").reset_index(drop=True)
        candles = normalize_intraday_candles(df, intraday_limit)
        if not candles:
            return self._ssi_intraday_unavailable_payload(
                intraday_timeframe,
                status="unavailable",
                reason="SSI IntradayOhlc returned no candles.",
                diagnostics={
                    "normalized_row_count": normalized_row_count,
                    "filtered_usable_row_count": 0,
                    "intraday_cadence_status": "unavailable",
                },
            )
        granularity = _detect_intraday_granularity(candles, intraday_timeframe)
        intraday_latest_date = _intraday_candle_vn_date(candles[-1]) if candles else None
        pulse = calculate_intraday_pulse(candles)
        pulse.update(granularity)
        pulse["intraday_latest_date"] = intraday_latest_date
        pulse["intraday_requested_timeframe"] = intraday_timeframe
        pulse["intraday_actual_granularity"] = granularity["intraday_actual_granularity"]
        pulse["intraday_actual_granularity_seconds"] = granularity["intraday_actual_granularity_seconds"]
        pulse["intraday_cadence_status"] = granularity["intraday_cadence_status"]
        details = derive_intraday_details(candles, pulse)
        labels = [detail["label"] for detail in details]
        reason_code = _classify_intraday_reason(
            status="ok",
            reason=None,
            diagnostics=granularity,
        )
        return {
            "intraday_timeframe": intraday_timeframe,
            "intraday_requested_timeframe": intraday_timeframe,
            **granularity,
            "intraday_latest_date": intraday_latest_date,
            "daily_price_date": None,
            "date_match": "unknown",
            "intraday_source": SSI_INTRADAY_SOURCE,
            "intraday_is_realtime_quote": False,
            "intraday_warning": "SSI IntradayOhlc granularity is provider-returned; use the returned timestamps for cadence.",
            "intraday_candles": candles,
            "intraday_pulse": pulse,
            "intraday_labels": labels,
            "intraday_details": details,
            "intraday_status": {
                "status": "ok",
                "source": SSI_INTRADAY_SOURCE,
                "message": None,
                "reason_code": reason_code,
                "classification": reason_code,
                "count": len(candles),
                "ticker": symbol,
                "intraday_latest_date": intraday_latest_date,
                "daily_price_date": None,
                "date_match": "unknown",
                **granularity,
                "intraday_requested_timeframe": intraday_timeframe,
                "intraday_actual_granularity": granularity["intraday_actual_granularity"],
                "intraday_actual_granularity_seconds": granularity["intraday_actual_granularity_seconds"],
                "diagnostics": {
                    "endpoint": "IntradayOhlc",
                    "symbol": symbol,
                    "requested_timeframe": intraday_timeframe,
                    "public_limit": intraday_limit,
                    "normalized_row_count": normalized_row_count,
                    "filtered_usable_row_count": len(candles),
                    "intraday_latest_date": intraday_latest_date,
                    **granularity,
                },
            },
        }

    def _ssi_intraday_unavailable_payload(
        self,
        intraday_timeframe: str,
        *,
        status: str = "unavailable",
        reason: Optional[str] = None,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        reason_text = reason or VN_INTRADAY_UNAVAILABLE_REASON
        diagnostics = dict(diagnostics or {})
        intraday_granularity = diagnostics.get("intraday_granularity") or "unknown"
        intraday_granularity_seconds = diagnostics.get("intraday_granularity_seconds")
        intraday_granularity_label = diagnostics.get("intraday_granularity_label") or "provider-returned"
        intraday_cadence_status = diagnostics.get("intraday_cadence_status") or (
            "unavailable" if status in {"unavailable", "disabled"} else "unknown"
        )
        status_payload = {
            "status": status,
            "source": SSI_INTRADAY_SOURCE,
            "message": reason_text,
            "reason_code": _classify_intraday_reason(
                status=status,
                reason=reason_text,
                diagnostics=diagnostics,
            ),
            "intraday_requested_timeframe": intraday_timeframe,
            "intraday_actual_granularity": intraday_granularity,
            "intraday_actual_granularity_seconds": intraday_granularity_seconds,
            "intraday_cadence_status": intraday_cadence_status,
        }
        status_payload["classification"] = status_payload["reason_code"]
        status_payload.update(diagnostics)
        if diagnostics:
            status_payload["diagnostics"] = dict(diagnostics)
        return {
            "intraday_timeframe": intraday_timeframe,
            "intraday_requested_timeframe": intraday_timeframe,
            "intraday_granularity": intraday_granularity,
            "intraday_actual_granularity": intraday_granularity,
            "intraday_granularity_seconds": intraday_granularity_seconds,
            "intraday_actual_granularity_seconds": intraday_granularity_seconds,
            "intraday_granularity_label": intraday_granularity_label,
            "intraday_cadence_status": intraday_cadence_status,
            "intraday_latest_date": diagnostics.get("intraday_latest_date"),
            "daily_price_date": diagnostics.get("daily_price_date"),
            "date_match": diagnostics.get("date_match") or "unknown",
            "intraday_source": SSI_INTRADAY_SOURCE,
            "intraday_is_realtime_quote": False,
            "intraday_warning": reason_text,
            "intraday_candles": [],
            "intraday_pulse": None,
            "intraday_labels": [],
            "intraday_details": [],
            "intraday_status": status_payload,
        }

    def _load_ssi_intraday_payload(self, symbol: str, intraday_timeframe: str, intraday_limit: int) -> Dict[str, Any]:
        if self.config.intraday_data_provider != VN_PROVIDER_SSI:
            return self._ssi_intraday_unavailable_payload(
                intraday_timeframe,
                status="disabled",
                reason=VN_INTRADAY_DISABLED_REASON,
            )
        if not self.config.ssi_intraday_enabled:
            return self._ssi_intraday_unavailable_payload(
                intraday_timeframe,
                status="disabled",
                reason=VN_INTRADAY_DISABLED_REASON,
            )

        to_date = datetime.now(VN_TIMEZONE).date()
        from_date = to_date - timedelta(days=7)
        payload = self._get_ssi_fetcher().get_intraday_ohlcv(
            symbol,
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
            limit=max(int(intraday_limit or 8), 8),
            interval=intraday_timeframe,
        )
        status = str(payload.get("status") or "").lower() if isinstance(payload, dict) else ""
        if status == "ok":
            rows = payload.get("rows") if isinstance(payload, dict) else []
            normalized_rows = [dict(row) for row in rows if isinstance(row, dict)]
            if normalized_rows:
                return self._intraday_payload_from_rows(symbol, normalized_rows, intraday_timeframe, intraday_limit)
            return self._ssi_intraday_unavailable_payload(
                intraday_timeframe,
                status="unavailable",
                reason="SSI IntradayOhlc returned no candles.",
            )
        if status == "disabled":
            disabled_reason = payload.get("reason") if isinstance(payload, dict) else None
            return self._ssi_intraday_unavailable_payload(
                intraday_timeframe,
                status="disabled",
                reason=disabled_reason or VN_INTRADAY_DISABLED_REASON,
                diagnostics=_intraday_failure_diagnostics(payload),
            )
        unavailable_reason = None
        diagnostics: Dict[str, Any] = {}
        if isinstance(payload, dict):
            unavailable_reason = payload.get("reason") or payload.get("message")
            diagnostics = _intraday_failure_diagnostics(payload)
        return self._ssi_intraday_unavailable_payload(
            intraday_timeframe,
            status=status or "unavailable",
            reason=unavailable_reason or VN_INTRADAY_UNAVAILABLE_REASON,
            diagnostics=diagnostics,
        )

    def _validate_intraday_freshness(
        self,
        intraday_payload: Dict[str, Any],
        *,
        daily_price_date: Optional[str],
    ) -> Dict[str, Any]:
        status = str((intraday_payload.get("intraday_status") or {}).get("status") or "").lower()
        if status != "ok":
            return intraday_payload

        candles = [row for row in (intraday_payload.get("intraday_candles") or []) if isinstance(row, dict)]
        intraday_latest_date = intraday_payload.get("intraday_latest_date")
        if not intraday_latest_date and candles:
            intraday_latest_date = _intraday_candle_vn_date(candles[-1])
        daily_date = _valid_date_string(daily_price_date)
        diagnostics = {
            "intraday_latest_date": intraday_latest_date,
            "daily_price_date": daily_date,
            "date_match": "unknown",
            "intraday_granularity": intraday_payload.get("intraday_granularity") or "unknown",
            "intraday_granularity_seconds": intraday_payload.get("intraday_granularity_seconds"),
            "intraday_granularity_label": intraday_payload.get("intraday_granularity_label") or "provider-returned",
            "intraday_actual_granularity": intraday_payload.get("intraday_actual_granularity") or intraday_payload.get("intraday_granularity") or "unknown",
            "intraday_actual_granularity_seconds": intraday_payload.get("intraday_actual_granularity_seconds") or intraday_payload.get("intraday_granularity_seconds"),
            "intraday_cadence_status": intraday_payload.get("intraday_cadence_status") or "unknown",
        }
        if intraday_latest_date and daily_date:
            diagnostics["date_match"] = "matched" if intraday_latest_date == daily_date else "mismatched"
        if diagnostics["date_match"] == "mismatched":
            diagnostics["failure_class"] = "stale_or_date_mismatched"
            return self._ssi_intraday_unavailable_payload(
                str(intraday_payload.get("intraday_timeframe") or self.config.intraday_timeframe or "provider"),
                status="unavailable",
                reason="SSI IntradayOhlc latest candle date does not match latest daily trading date.",
                diagnostics=diagnostics,
            )

        updated = dict(intraday_payload)
        updated.update(
            {
                "intraday_latest_date": intraday_latest_date,
                "daily_price_date": daily_date,
                "date_match": diagnostics["date_match"],
                "intraday_requested_timeframe": updated.get("intraday_requested_timeframe") or updated.get("intraday_timeframe"),
                "intraday_actual_granularity": updated.get("intraday_actual_granularity") or diagnostics["intraday_actual_granularity"],
                "intraday_actual_granularity_seconds": updated.get("intraday_actual_granularity_seconds") or diagnostics["intraday_actual_granularity_seconds"],
                "intraday_cadence_status": updated.get("intraday_cadence_status") or diagnostics["intraday_cadence_status"],
            }
        )
        status_payload = dict(updated.get("intraday_status") or {})
        status_payload.update(
            {
                "intraday_latest_date": intraday_latest_date,
                "daily_price_date": daily_date,
                "date_match": diagnostics["date_match"],
                "intraday_requested_timeframe": updated.get("intraday_requested_timeframe") or updated.get("intraday_timeframe"),
                "intraday_actual_granularity": updated.get("intraday_actual_granularity") or diagnostics["intraday_actual_granularity"],
                "intraday_actual_granularity_seconds": updated.get("intraday_actual_granularity_seconds") or diagnostics["intraday_actual_granularity_seconds"],
                "intraday_cadence_status": updated.get("intraday_cadence_status") or diagnostics["intraday_cadence_status"],
            }
        )
        status_diagnostics = dict(status_payload.get("diagnostics") or {})
        status_diagnostics.update(
            {
                "daily_price_date": daily_date,
                "date_match": diagnostics["date_match"],
                "intraday_cadence_status": status_payload.get("intraday_cadence_status"),
                "intraday_actual_granularity": status_payload.get("intraday_actual_granularity"),
                "intraday_actual_granularity_seconds": status_payload.get("intraday_actual_granularity_seconds"),
            }
        )
        status_payload["diagnostics"] = status_diagnostics
        updated["intraday_status"] = status_payload
        pulse = dict(updated.get("intraday_pulse") or {})
        pulse.update(
            {
                "intraday_latest_date": intraday_latest_date,
                "daily_price_date": daily_date,
                "date_match": diagnostics["date_match"],
                "intraday_requested_timeframe": updated.get("intraday_requested_timeframe") or updated.get("intraday_timeframe"),
                "intraday_actual_granularity": updated.get("intraday_actual_granularity") or diagnostics["intraday_actual_granularity"],
                "intraday_actual_granularity_seconds": updated.get("intraday_actual_granularity_seconds") or diagnostics["intraday_actual_granularity_seconds"],
                "intraday_cadence_status": updated.get("intraday_cadence_status") or diagnostics["intraday_cadence_status"],
            }
        )
        updated["intraday_pulse"] = pulse
        return updated

    def _disabled_intraday_payload(self, intraday_timeframe: str) -> Dict[str, Any]:
        return {
            "intraday_timeframe": intraday_timeframe,
            "intraday_requested_timeframe": intraday_timeframe,
            "intraday_granularity": "unknown",
            "intraday_actual_granularity": "unknown",
            "intraday_granularity_seconds": None,
            "intraday_actual_granularity_seconds": None,
            "intraday_granularity_label": "provider-returned",
            "intraday_cadence_status": "unavailable",
            "intraday_latest_date": None,
            "daily_price_date": None,
            "date_match": "unknown",
            "intraday_source": SSI_INTRADAY_SOURCE,
            "intraday_is_realtime_quote": False,
            "intraday_warning": VN_INTRADAY_DISABLED_REASON,
            "intraday_candles": [],
            "intraday_pulse": None,
            "intraday_labels": [],
            "intraday_details": [],
            "intraday_status": {
                "status": "disabled",
                "source": SSI_INTRADAY_SOURCE,
                "message": VN_INTRADAY_DISABLED_REASON,
                "intraday_requested_timeframe": intraday_timeframe,
                "intraday_actual_granularity": "unknown",
                "intraday_actual_granularity_seconds": None,
                "intraday_cadence_status": "unavailable",
            },
        }

    @staticmethod
    def _disabled_cache_status() -> Dict[str, str]:
        return {
            "quote_cache": "disabled",
            "intraday_cache": "disabled",
            "realtime_cache": "disabled",
            "trade_tape_cache": "disabled",
            "news_cache": "disabled",
        }

    @staticmethod
    def _disabled_cache_times() -> Dict[str, Optional[str]]:
        return {
            "quote": None,
            "intraday_ohlcv": None,
            "realtime_snapshot": None,
            "trade_tape": None,
            "news": None,
        }

    @staticmethod
    def _news_status_block() -> Dict[str, Any]:
        return {
            "status": "disabled",
            "source": None,
            "items": [],
            "message": VN_NEWS_DISABLED_REASON,
        }

    @staticmethod
    def _disabled_realtime_payload(symbol: str) -> Dict[str, Any]:
        return {
            "realtime_source": None,
            "realtime_snapshot": None,
            "realtime_status": {
                "status": "disabled",
                "source": None,
                "message": VN_REALTIME_DISABLED_REASON,
                "reason_code": "disabled",
                "classification": "disabled",
                "ticker": symbol,
            },
        }

    @staticmethod
    def _disabled_trade_tape_payload(symbol: str) -> Dict[str, Any]:
        return {
            "trade_tape_source": None,
            "trade_tape": [],
            "trade_tape_status": {
                "status": "disabled",
                "source": None,
                "message": VN_TRADE_TAPE_DISABLED_REASON,
                "reason_code": "disabled",
                "classification": "disabled",
                "ticker": symbol,
            },
        }

    @staticmethod
    def _ssi_realtime_unavailable_payload(
        symbol: str,
        *,
        status: str = "unavailable",
        reason: Optional[str] = None,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        reason_text = reason or VN_REALTIME_UNAVAILABLE_REASON
        public_status = _public_live_status(status)
        safe_diagnostics = _live_failure_diagnostics(
            diagnostics,
            reason=reason_text if reason_text != VN_REALTIME_UNAVAILABLE_REASON else None,
        )
        reason_code = _classify_realtime_reason(
            status=public_status,
            reason=reason_text,
            diagnostics=safe_diagnostics,
            symbol=symbol,
        )
        status_payload = {
            "status": public_status,
            "source": SSI_REALTIME_SOURCE,
            "message": _status_message_from_reason(
                section="realtime",
                status=public_status,
                reason_code=reason_code,
                fallback=VN_REALTIME_UNAVAILABLE_REASON,
            ),
            "ticker": symbol,
        }
        if safe_diagnostics:
            status_payload["diagnostics"] = safe_diagnostics
        status_payload["reason_code"] = reason_code
        status_payload["classification"] = reason_code
        for key in ("streaming_status", "runtime_status", "manager_state", "cache_status"):
            if key in safe_diagnostics:
                status_payload[key] = safe_diagnostics.get(key)
        return {
            "realtime_source": SSI_REALTIME_SOURCE,
            "realtime_snapshot": None,
            "realtime_status": status_payload,
        }

    @staticmethod
    def _ssi_trade_tape_unavailable_payload(
        symbol: str,
        *,
        status: str = "unavailable",
        reason: Optional[str] = None,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        reason_text = reason or VN_TRADE_TAPE_UNAVAILABLE_REASON
        public_status = _public_live_status(status)
        status_payload = {
            "status": public_status,
            "source": SSI_TRADE_TAPE_SOURCE,
            "message": _status_message_from_reason(
                section="trade_tape",
                status=public_status,
                reason_code=_classify_trade_tape_reason(status=public_status, reason=reason_text),
                fallback=VN_TRADE_TAPE_UNAVAILABLE_REASON,
            ),
            "ticker": symbol,
        }
        reason_code = _classify_trade_tape_reason(status=public_status, reason=reason_text)
        status_payload["reason_code"] = reason_code
        status_payload["classification"] = reason_code
        safe_diagnostics = _live_failure_diagnostics(
            diagnostics,
            reason=reason_text if reason_text != VN_TRADE_TAPE_UNAVAILABLE_REASON else None,
        )
        if safe_diagnostics:
            status_payload["diagnostics"] = safe_diagnostics
        return {
            "trade_tape_source": SSI_TRADE_TAPE_SOURCE,
            "trade_tape": [],
            "trade_tape_status": status_payload,
        }

    @staticmethod
    def _realtime_quote_from_snapshot(row: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        price = _safe_float(row.get("price") or row.get("realtime_price") or row.get("snapshot_price"))
        change = _safe_float(row.get("change") or row.get("price_change"))
        change_pct = _safe_float(row.get("change_pct") or row.get("percent_change"))
        bid_levels = list(row.get("bid_levels") or [])
        ask_levels = list(row.get("ask_levels") or [])
        first_bid = bid_levels[0] if bid_levels and isinstance(bid_levels[0], dict) else {}
        first_ask = ask_levels[0] if ask_levels and isinstance(ask_levels[0], dict) else {}
        fetched_at = row.get("fetched_at")
        snapshot_time = row.get("snapshot_time") or row.get("realtime_time") or row.get("stream_timestamp") or fetched_at
        age_seconds = _safe_int(row.get("age_seconds"))
        cache_ttl_seconds = _safe_int(row.get("cache_ttl_seconds"))
        return {
            "symbol": symbol,
            "ticker": symbol,
            "source": SSI_REALTIME_SOURCE,
            "fetched_at": fetched_at,
            "price": price,
            "change": change,
            "change_pct": change_pct,
            "reference_price": _safe_float(row.get("reference_price")),
            "ceiling_price": _safe_float(row.get("ceiling_price")),
            "floor_price": _safe_float(row.get("floor_price")),
            "open": _safe_float(row.get("open")),
            "high": _safe_float(row.get("high")),
            "low": _safe_float(row.get("low")),
            "volume": _safe_float(row.get("volume")),
            "value": _safe_float(row.get("value")),
            "bid_levels": bid_levels,
            "ask_levels": ask_levels,
            "status": row.get("status") or "ok",
            "age_seconds": age_seconds,
            "is_stale": row.get("is_stale") if isinstance(row.get("is_stale"), bool) else None,
            "stale_reason": row.get("stale_reason"),
            "cached_at": row.get("cached_at"),
            "cache_ttl_seconds": cache_ttl_seconds,
            # Compatibility fields for the existing UI/API contract.
            "realtime_price": price,
            "snapshot_price": price,
            "realtime_time": snapshot_time,
            "snapshot_time": snapshot_time,
            "snapshot_note": "SSI realtime snapshot; separate from official daily close.",
            "reference_price_source": SSI_REALTIME_SOURCE,
            "open_price": _safe_float(row.get("open")),
            "high_price": _safe_float(row.get("high")),
            "low_price": _safe_float(row.get("low")),
            "price_change": change,
            "percent_change": change_pct,
            "volume_accumulated": _safe_float(row.get("volume")),
            "total_value": _safe_float(row.get("value")),
            "bid_price_1": _safe_float(first_bid.get("price")),
            "bid_vol_1": _safe_float(first_bid.get("volume")),
            "ask_price_1": _safe_float(first_ask.get("price")),
            "ask_vol_1": _safe_float(first_ask.get("volume")),
        }

    @staticmethod
    def _trade_row_from_ssi(row: Dict[str, Any]) -> Dict[str, Any]:
        side = row.get("side_if_available")
        sequence = row.get("sequence_if_available")
        return {
            "ticker": row.get("ticker") or row.get("symbol"),
            "symbol": row.get("symbol") or row.get("ticker"),
            "time": row.get("time"),
            "timestamp": row.get("timestamp"),
            "timestamp_display": row.get("timestamp_display") or row.get("time"),
            "price": _safe_float(row.get("price")),
            "volume": _safe_float(row.get("volume")),
            "value": _safe_float(row.get("value")),
            "side": row.get("side") or side,
            "side_if_available": side,
            "sequence": row.get("sequence") or sequence,
            "sequence_if_available": sequence,
            "match_type": side,
            "id": sequence,
            "raw_type": row.get("raw_type"),
            "source": SSI_TRADE_TAPE_SOURCE,
        }

    def _load_ssi_realtime_payload(self, symbol: str) -> Dict[str, Any]:
        if self.config.realtime_data_provider != VN_PROVIDER_SSI or not self.config.ssi_realtime_enabled:
            return self._disabled_realtime_payload(symbol)
        if not self.config.ssi_streaming_realtime_enabled:
            return self._ssi_realtime_unavailable_payload(
                symbol,
                reason=SSI_STREAMING_REALTIME_DISABLED_REASON,
                diagnostics={
                    "streaming_status": "disabled",
                    "manager_state": "disabled",
                    "cache_status": "disabled",
                    "live_adapter_status": "not_enabled",
                },
            )

        payload = self._get_ssi_fetcher().get_realtime_snapshot([symbol])
        status = str(payload.get("status") or "").lower() if isinstance(payload, dict) else ""
        if status == "ok":
            quotes = payload.get("quotes") if isinstance(payload, dict) else []
            quote = next((row for row in quotes if isinstance(row, dict) and str(row.get("ticker") or row.get("symbol") or "").upper() == symbol), None)
            if quote:
                normalized = self._realtime_quote_from_snapshot(quote, symbol)
                return {
                    "realtime_source": SSI_REALTIME_SOURCE,
                    "realtime_snapshot": normalized,
                    "realtime_status": {
                        "status": "ok",
                        "source": SSI_REALTIME_SOURCE,
                        "message": None,
                        "reason_code": "cache_hit",
                        "classification": "cache_hit",
                        "ticker": symbol,
                        "diagnostics": _live_failure_diagnostics(payload),
                    },
                }
            return self._ssi_realtime_unavailable_payload(symbol, reason="SSI realtime returned no quote row.")
        if status == "disabled":
            return self._disabled_realtime_payload(symbol)
        return self._ssi_realtime_unavailable_payload(
            symbol,
            status=status or "unavailable",
            reason=(payload.get("reason") or payload.get("message")) if isinstance(payload, dict) else None,
            diagnostics=payload if isinstance(payload, dict) else None,
        )

    def _load_ssi_trade_tape_payload(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        if self.config.trade_tape_provider != VN_PROVIDER_SSI or not self.config.ssi_trade_tape_enabled:
            return self._disabled_trade_tape_payload(symbol)

        payload = self._get_ssi_fetcher().get_trade_tape(symbol, limit=limit)
        status = str(payload.get("status") or "").lower() if isinstance(payload, dict) else ""
        if status == "ok":
            trades = [self._trade_row_from_ssi(row) for row in (payload.get("trades") or []) if isinstance(row, dict)]
            if trades:
                safe_diagnostics = _live_failure_diagnostics(payload)
                reason_code = "streaming_trade_tape_supported" if payload.get("streaming_status") else "historical_trade_tape_supported"
                trade_tape_status = {
                    "status": "ok",
                    "source": SSI_TRADE_TAPE_SOURCE,
                    "message": None,
                    "reason_code": reason_code,
                    "classification": reason_code,
                    "ticker": symbol,
                    "count": len(trades),
                    "fetched_at": _utc_now().isoformat(),
                }
                if safe_diagnostics:
                    trade_tape_status["diagnostics"] = safe_diagnostics
                return {
                    "trade_tape_source": SSI_TRADE_TAPE_SOURCE,
                    "trade_tape": trades,
                    "trade_tape_status": trade_tape_status,
                }
            return self._ssi_trade_tape_unavailable_payload(symbol, reason="SSI trade tape returned no trade rows.")
        if status == "disabled":
            return self._disabled_trade_tape_payload(symbol)
        return self._ssi_trade_tape_unavailable_payload(
            symbol,
            status=status or "unavailable",
            reason=(payload.get("reason") or payload.get("message")) if isinstance(payload, dict) else None,
            diagnostics=payload if isinstance(payload, dict) else None,
        )

    def _unpack_daily_ohlcv_value(
        self,
        value: Any,
        provider: str,
    ) -> Tuple[pd.DataFrame, str, Dict[str, Any]]:
        if isinstance(value, tuple) and len(value) >= 3:
            return value[0], value[1], dict(value[2] or {})
        df, source = value
        actual_source = VN_SOURCE_SSI if str(source).upper() == VN_SOURCE_SSI else VN_SOURCE_MOZYFIN
        return df, source, {
            "status": "ok",
            "primary_source": self._provider_label(provider),
            "actual_source": actual_source,
            "fallback_used": False,
            "fallback_reason": None,
            "unavailable_reason": None,
        }

    def _latest_ssi_daily_stock_price(
        self,
        symbol: str,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Dict[str, Any], List[Dict[str, Any]]]:
        if self.config.daily_stock_price_provider != VN_PROVIDER_SSI:
            return None, None, {
                "endpoint": "DailyStockPrice",
                "symbol": symbol,
                "normalized_row_count": 0,
                "failure_class": "disabled",
            }, []
        to_date = datetime.now(VN_TIMEZONE).date()
        from_date = to_date - timedelta(days=28)
        diagnostics = {
            "endpoint": "DailyStockPrice",
            "symbol": symbol,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "normalized_row_count": 0,
            "selected_latest_row_date": None,
        }
        payload = self._get_ssi_fetcher().get_daily_stock_price(
            symbol,
            market=get_vn_exchange(symbol),
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
            limit=260,
        )
        if payload.get("status") != "ok":
            diagnostics["failure_class"] = str(payload.get("failure_class") or "provider_unavailable")
            return None, self._safe_provider_reason(payload, SSI_UNAVAILABLE_REASON), diagnostics, []
        rows = payload.get("rows") or []
        diagnostics["normalized_row_count"] = len(rows) if isinstance(rows, list) else 0
        provider_rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
        if not provider_rows:
            diagnostics["failure_class"] = "empty_result"
            return None, SSI_UNAVAILABLE_REASON, diagnostics, []
        dated_rows = sorted(
            (
                row
                for row in provider_rows
                if _valid_date_string(row.get("date"))
            ),
            key=lambda row: _valid_date_string(row.get("date")) or "",
        )
        selected = dated_rows[-1] if dated_rows else provider_rows[-1]
        foreign_history = _normalize_ssi_daily_stock_price_foreign_history(provider_rows)
        history_dates = [
            date_text
            for date_text in (_valid_date_string(row.get("date")) for row in foreign_history)
            if date_text
        ]
        history_net_row_count = sum(
            1
            for row in foreign_history
            if _safe_float(row.get("net")) is not None
        )
        diagnostics["selected_latest_row_date"] = _valid_date_string(selected.get("date"))
        diagnostics.update(
            {
                "foreign_history_row_count": len(foreign_history),
                "foreign_history_net_row_count": history_net_row_count,
                "foreign_history_date_start": history_dates[0] if history_dates else None,
                "foreign_history_date_end": history_dates[-1] if history_dates else None,
                "foreign_history_status": (
                    "ok"
                    if history_net_row_count >= FOREIGN_HISTORY_LIMIT
                    else "partial"
                    if history_net_row_count
                    else "unavailable"
                ),
            }
        )
        return selected, None, diagnostics, foreign_history

    def _read_latest_ssi_daily_stock_price(
        self,
        symbol: str,
        *,
        force_refresh: bool,
    ) -> Dict[str, Any]:
        """Reuse the bounded DailyStockPrice enrichment/history across HTTP requests."""
        cache_key = _cache_key(
            "daily_stock_price",
            symbol,
            provider=self.config.daily_stock_price_provider,
            market=get_vn_exchange(symbol),
            as_of_date=datetime.now(VN_TIMEZONE).date().isoformat(),
            lookback_days=28,
            limit=260,
        )
        return _read_cache(
            cache_key,
            "daily_stock_price",
            lambda: self._latest_ssi_daily_stock_price(symbol),
            force_refresh=force_refresh,
        )

    def _daily_stock_price_enrichment_block(
        self,
        symbol: str,
        *,
        daily_ohlc_date: Optional[str],
        force_refresh: bool,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
        cache_status: Dict[str, Any] = {}
        cache_last_fetched_at: Dict[str, Any] = {}
        cache_next_refresh_at: Dict[str, Any] = {}
        cache_errors: Dict[str, Any] = {}
        if self.config.daily_stock_price_provider != VN_PROVIDER_SSI:
            return (
                {
                    "daily_stock_price": {},
                    "cache_status": cache_status,
                    "cache_last_fetched_at": cache_last_fetched_at,
                    "cache_next_refresh_at": cache_next_refresh_at,
                    "cache_errors": cache_errors,
                },
                {},
                [],
            )

        daily_stock_price_result = self._read_latest_ssi_daily_stock_price(
            symbol,
            force_refresh=force_refresh,
        )
        (
            ssi_daily_stock_price,
            ssi_daily_stock_price_reason,
            ssi_daily_stock_price_diagnostics,
            ssi_daily_stock_price_history,
        ) = daily_stock_price_result["value"]
        cache_status["daily_stock_price_cache"] = daily_stock_price_result["status"]
        cache_last_fetched_at["daily_stock_price"] = _iso(daily_stock_price_result["entry"].fetched_at)
        cache_next_refresh_at["daily_stock_price"] = _iso(daily_stock_price_result["entry"].expires_at)
        if daily_stock_price_result["error"]:
            cache_errors["daily_stock_price"] = daily_stock_price_result["error"]

        if ssi_daily_stock_price:
            enrichment = self._normalize_ssi_daily_stock_price_enrichment(
                ssi_daily_stock_price,
                daily_ohlc_date=daily_ohlc_date,
                diagnostics=ssi_daily_stock_price_diagnostics,
            )
        else:
            enrichment = self._unavailable_ssi_daily_stock_price(
                reason=ssi_daily_stock_price_reason,
                daily_ohlc_date=daily_ohlc_date,
                diagnostics=ssi_daily_stock_price_diagnostics,
            )

        return (
            {
                "daily_stock_price": enrichment,
                "cache_status": cache_status,
                "cache_last_fetched_at": cache_last_fetched_at,
                "cache_next_refresh_at": cache_next_refresh_at,
                "cache_errors": cache_errors,
            },
            enrichment,
            ssi_daily_stock_price_history,
        )

    @staticmethod
    def _normalize_ssi_daily_stock_price_enrichment(
        row: Dict[str, Any],
        *,
        daily_ohlc_date: Optional[str],
        diagnostics: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized = dict(row)
        normalized["status"] = "ok"
        normalized["source"] = SSI_DAILY_STOCK_PRICE_SOURCE
        normalized["date"] = _valid_date_string(row.get("date"))

        for field in DAILY_STOCK_PRICE_ENRICHMENT_FIELDS:
            normalized[field] = _safe_float(row.get(field))

        date_match = _date_match_status(daily_ohlc_date, normalized["date"])
        field_coverage = {
            field: normalized.get(field) is not None
            for field in DAILY_STOCK_PRICE_ENRICHMENT_FIELDS
        }
        missing_fields = [
            field
            for field, available in field_coverage.items()
            if not available
        ]
        units = {
            field: DAILY_STOCK_PRICE_FIELD_UNITS[field]
            for field, available in field_coverage.items()
            if available
        }
        staleness_reason = None
        if date_match == "mismatched":
            staleness_reason = "DailyStockPrice date differs from DailyOhlc."
        elif date_match == "unknown":
            staleness_reason = "DailyStockPrice date alignment with DailyOhlc is unknown."

        safe_diagnostics = dict(diagnostics)
        safe_diagnostics.update(
            {
                "selected_latest_row_date": normalized["date"],
                "daily_ohlc_date": daily_ohlc_date,
                "date_match": date_match,
                "missing_fields": missing_fields,
                "field_coverage": field_coverage,
            }
        )
        normalized.update(
            {
                "quality_status": "partial" if date_match != "matched" or missing_fields else "ok",
                "date_match": date_match,
                "staleness_reason": staleness_reason,
                "missing_fields": missing_fields,
                "field_coverage": field_coverage,
                "units": units,
                "diagnostics": safe_diagnostics,
            }
        )
        return normalized

    @staticmethod
    def _unavailable_ssi_daily_stock_price(
        *,
        reason: Optional[str],
        daily_ohlc_date: Optional[str],
        diagnostics: Dict[str, Any],
    ) -> Dict[str, Any]:
        field_coverage = {field: False for field in DAILY_STOCK_PRICE_ENRICHMENT_FIELDS}
        safe_diagnostics = dict(diagnostics)
        safe_diagnostics.update(
            {
                "daily_ohlc_date": daily_ohlc_date,
                "date_match": "unavailable",
                "missing_fields": list(DAILY_STOCK_PRICE_ENRICHMENT_FIELDS),
                "field_coverage": field_coverage,
            }
        )
        return {
            "status": "unavailable",
            "quality_status": "unavailable",
            "source": SSI_DAILY_STOCK_PRICE_SOURCE,
            "reason": reason or SSI_UNAVAILABLE_REASON,
            "date": None,
            "date_match": "unavailable",
            "staleness_reason": "SSI DailyStockPrice enrichment is unavailable.",
            "missing_fields": list(DAILY_STOCK_PRICE_ENRICHMENT_FIELDS),
            "field_coverage": field_coverage,
            "units": {},
            "diagnostics": safe_diagnostics,
        }

    @staticmethod
    def _normalize_ssi_symbol_metadata(
        row: Dict[str, Any],
        source_label: str = SSI_SECURITIES_DETAILS_SOURCE,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized = {
            "status": "ok",
            "symbol": str(row.get("symbol")).upper() if row.get("symbol") not in (None, "") else None,
            "exchange": row.get("exchange"),
            "market": row.get("market"),
            "security_type": row.get("security_type"),
            "name": row.get("name"),
            "name_en": row.get("name_en"),
            "industry": row.get("industry"),
            "sector": row.get("sector"),
            "issuer": row.get("issuer"),
            "lot_size": _safe_int(row.get("lot_size")),
            "listed_shares": _safe_int(row.get("listed_shares")),
            "listed_date": row.get("listed_date"),
            "source": source_label,
        }
        field_coverage = {
            field: normalized.get(field) not in (None, "")
            for field in SYMBOL_METADATA_FIELDS
        }
        missing_fields = [
            field
            for field, available in field_coverage.items()
            if not available
        ]
        safe_diagnostics = dict(diagnostics or {})
        safe_diagnostics.update(
            {
                "selected_row_source": source_label,
                "field_coverage": field_coverage,
                "missing_fields": missing_fields,
            }
        )
        normalized.update(
            {
                "quality_status": "complete" if not missing_fields else "partial" if normalized["symbol"] else "unknown",
                "completeness": round(
                    sum(1 for available in field_coverage.values() if available) / len(SYMBOL_METADATA_FIELDS),
                    4,
                ),
                "missing_fields": missing_fields,
                "field_coverage": field_coverage,
                "diagnostics": safe_diagnostics,
            }
        )
        return normalized

    @staticmethod
    def _unavailable_ssi_symbol_metadata(
        *,
        reason: Optional[str],
        diagnostics: Dict[str, Any],
    ) -> Dict[str, Any]:
        field_coverage = {field: False for field in SYMBOL_METADATA_FIELDS}
        safe_diagnostics = dict(diagnostics)
        safe_diagnostics.update(
            {
                "selected_row_source": None,
                "field_coverage": field_coverage,
                "missing_fields": list(SYMBOL_METADATA_FIELDS),
            }
        )
        return {
            "status": "unavailable",
            "quality_status": "unavailable",
            "completeness": 0.0,
            "source": SSI_SECURITIES_DETAILS_SOURCE,
            "reason": reason or SSI_UNAVAILABLE_REASON,
            "symbol": None,
            "exchange": None,
            "market": None,
            "security_type": None,
            "name": None,
            "name_en": None,
            "industry": None,
            "sector": None,
            "issuer": None,
            "lot_size": None,
            "listed_shares": None,
            "listed_date": None,
            "missing_fields": list(SYMBOL_METADATA_FIELDS),
            "field_coverage": field_coverage,
            "diagnostics": safe_diagnostics,
        }

    @staticmethod
    def _matching_ssi_metadata_row(payload: Dict[str, Any], symbol: str) -> Optional[Dict[str, Any]]:
        if payload.get("status") != "ok":
            return None
        rows = payload.get("rows") or []
        if not isinstance(rows, list):
            return None
        normalized_symbol = vn_ticker(symbol)
        for row in rows:
            if isinstance(row, dict) and str(row.get("symbol") or "").upper() == normalized_symbol:
                return row
        return None

    def _load_ssi_symbol_metadata(self, symbol: str) -> Dict[str, Any]:
        normalized_symbol = vn_ticker(symbol)
        market = get_vn_exchange(normalized_symbol)
        fetcher = self._get_ssi_fetcher()

        details_payload = fetcher.get_securities_details(symbol=normalized_symbol, market=market)
        details_rows = details_payload.get("rows") if isinstance(details_payload, dict) else None
        details_row_count = len(details_rows) if isinstance(details_rows, list) else 0
        attempted_endpoints = ["SecuritiesDetails"]
        row = self._matching_ssi_metadata_row(details_payload, normalized_symbol)
        if row:
            return self._normalize_ssi_symbol_metadata(
                row,
                SSI_SECURITIES_DETAILS_SOURCE,
                diagnostics={
                    "endpoint": "SecuritiesDetails",
                    "attempted_endpoints": attempted_endpoints,
                    "requested_symbol": normalized_symbol,
                    "normalized_row_count": details_row_count,
                    "endpoint_row_counts": {"SecuritiesDetails": details_row_count},
                },
            )

        securities_payload = fetcher.get_securities(market=market)
        attempted_endpoints.append("Securities")
        securities_rows = securities_payload.get("rows") if isinstance(securities_payload, dict) else None
        securities_row_count = len(securities_rows) if isinstance(securities_rows, list) else 0
        row = self._matching_ssi_metadata_row(securities_payload, normalized_symbol)
        if row:
            return self._normalize_ssi_symbol_metadata(
                row,
                SSI_SECURITIES_SOURCE,
                diagnostics={
                    "endpoint": "Securities",
                    "attempted_endpoints": attempted_endpoints,
                    "requested_symbol": normalized_symbol,
                    "normalized_row_count": securities_row_count,
                    "endpoint_row_counts": {
                        "SecuritiesDetails": details_row_count,
                        "Securities": securities_row_count,
                    },
                    "fallback_within_ssi": True,
                },
            )

        reason = self._safe_provider_reason(details_payload, SSI_UNAVAILABLE_REASON)
        if isinstance(securities_payload, dict) and securities_payload.get("status") != "ok":
            reason = self._safe_provider_reason(securities_payload, reason)
        provider_failed = (
            not isinstance(details_payload, dict)
            or details_payload.get("status") != "ok"
            or not isinstance(securities_payload, dict)
            or securities_payload.get("status") != "ok"
        )
        failure_class = (
            "provider_unavailable"
            if provider_failed
            else "empty_result"
            if details_row_count == 0 and securities_row_count == 0
            else "no_matching_symbol"
        )
        return self._unavailable_ssi_symbol_metadata(
            reason=reason,
            diagnostics={
                "endpoint": "SecuritiesDetails",
                "attempted_endpoints": attempted_endpoints,
                "requested_symbol": normalized_symbol,
                "normalized_row_count": 0,
                "endpoint_row_counts": {
                    "SecuritiesDetails": details_row_count,
                    "Securities": securities_row_count,
                },
                "failure_class": failure_class,
            },
        )

    def _ssi_symbol_metadata(self, symbol: str, force_refresh: bool = False) -> Dict[str, Any]:
        key = _cache_key("symbol_metadata", symbol, provider=VN_PROVIDER_SSI, market=get_vn_exchange(symbol))
        try:
            result = _read_cache(
                key,
                "symbol_metadata",
                lambda: self._load_ssi_symbol_metadata(symbol),
                force_refresh=force_refresh,
            )
            value = result["value"]
            if isinstance(value, dict):
                return value
        except Exception:
            logger.debug("SSI symbol metadata unavailable for %s", symbol)
        return self._unavailable_ssi_symbol_metadata(
            reason=SSI_UNAVAILABLE_REASON,
            diagnostics={
                "endpoint": "SecuritiesDetails",
                "attempted_endpoints": ["SecuritiesDetails", "Securities"],
                "requested_symbol": vn_ticker(symbol),
                "normalized_row_count": 0,
                "failure_class": "service_error",
            },
        )

    @staticmethod
    def _apply_ssi_daily_stock_price_enrichment(
        symbol: str,
        latest_price_row: Dict[str, Any],
        limit_state: Dict[str, Any],
        foreign: Dict[str, Any],
        foreign_history: List[Dict[str, Any]],
        daily_stock_price_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
        enriched_limit = dict(limit_state)
        for source_key, target_key in (
            ("reference_price", "reference_price"),
            ("ceiling_price", "ceiling_price"),
            ("floor_price", "floor_price"),
        ):
            value = _safe_float(latest_price_row.get(source_key))
            if value is not None:
                enriched_limit[target_key] = value
        enriched_limit["reference_source"] = SSI_DAILY_STOCK_PRICE_SOURCE
        enriched_limit["source"] = SSI_DAILY_STOCK_PRICE_SOURCE
        enriched_limit["status"] = (
            "ok"
            if any(
                _safe_float(enriched_limit.get(field)) is not None
                for field in ("reference_price", "ceiling_price", "floor_price")
            )
            else "unavailable"
        )
        close = _safe_float(latest_price_row.get("close"))
        ceiling = _safe_float(enriched_limit.get("ceiling_price"))
        floor = _safe_float(enriched_limit.get("floor_price"))
        reference = _safe_float(enriched_limit.get("reference_price"))
        if close is not None and reference and ceiling is not None and floor is not None:
            distance = min(abs(ceiling - close), abs(close - floor)) / reference * 100
            enriched_limit["distance_to_limit_pct"] = round(distance, 2)
            enriched_limit["near_limit"] = distance <= 0.5

        enriched_foreign = dict(foreign)
        enriched_foreign.update(
            {
                "buy": _safe_float(latest_price_row.get("foreign_buy_volume")),
                "sell": _safe_float(latest_price_row.get("foreign_sell_volume")),
                "net": _safe_float(latest_price_row.get("foreign_net_volume")),
                "buy_value": _safe_float(latest_price_row.get("foreign_buy_value")),
                "sell_value": _safe_float(latest_price_row.get("foreign_sell_value")),
                "net_value": _safe_float(latest_price_row.get("foreign_net_value")),
                "date": latest_price_row.get("date"),
                "buy_raw_field": "foreign_buy_volume",
                "sell_raw_field": "foreign_sell_volume",
                "latest_price": None,
                "price_raw_field": None,
                "price_date": None,
                "source": SSI_DAILY_STOCK_PRICE_SOURCE,
            }
        )
        enriched_foreign["status"] = (
            "ok"
            if any(
                enriched_foreign.get(field) is not None
                for field in ("buy", "sell", "net", "buy_value", "sell_value", "net_value")
            )
            else "unavailable"
        )
        enriched_foreign["net_unit"] = (
            "shares"
            if any(enriched_foreign.get(field) is not None for field in ("buy", "sell", "net"))
            else None
        )
        enriched_foreign["value_unit"] = (
            "VND"
            if any(enriched_foreign.get(field) is not None for field in ("buy_value", "sell_value", "net_value"))
            else None
        )
        history_row = {
            "buy": enriched_foreign.get("buy"),
            "sell": enriched_foreign.get("sell"),
            "net": enriched_foreign.get("net"),
            "buy_value": enriched_foreign.get("buy_value"),
            "sell_value": enriched_foreign.get("sell_value"),
            "net_value": enriched_foreign.get("net_value"),
            "date": enriched_foreign.get("date"),
            "net_unit": "shares",
            "value_unit": "VND" if enriched_foreign.get("value_unit") else None,
            "buy_raw_field": "foreign_buy_volume",
            "sell_raw_field": "foreign_sell_volume",
            "net_raw_field": "foreign_net_volume",
        }
        enriched_history = (
            list(daily_stock_price_history[-FOREIGN_HISTORY_LIMIT:])
            if daily_stock_price_history
            else [history_row]
            if history_row.get("date")
            else foreign_history
        )
        enriched_limit["ssi_symbol"] = symbol
        return enriched_limit, enriched_foreign, enriched_history

    def build_chart(self, symbol: str, range_label: str = "6M") -> Dict[str, Any]:
        """Build selected-symbol daily OHLCV chart data from the configured daily provider."""
        normalized_symbol = normalize_vn_symbol(symbol)
        ticker = normalized_symbol.replace(".VN", "")
        effective_range = range_label.upper()
        if effective_range not in VN_CHART_RANGES:
            effective_range = "6M"
        provider = self.config.chart_data_provider
        ohlcv_key = self._daily_ohlcv_cache_key(
            ticker,
            provider,
            limit=VN_CHART_POINT_LIMIT,
            days=VN_CHART_HISTORY_DAYS,
        )
        ohlcv_result = _read_cache(
            ohlcv_key,
            "ohlcv",
            self._build_daily_ohlcv_loader(
                ticker,
                provider,
                limit=VN_CHART_POINT_LIMIT,
                days=VN_CHART_HISTORY_DAYS,
            ),
            force_refresh=False,
        )
        df, _source, provider_meta = self._unpack_daily_ohlcv_value(ohlcv_result["value"], provider)
        all_points = normalize_daily_chart_data(df, VN_CHART_POINT_LIMIT)
        points = filter_chart_points_by_range(all_points, effective_range)
        latest_date = points[-1].get("date") if points else None
        status = provider_meta.get("status") or ("ok" if points else "unavailable")
        return {
            "symbol": ticker,
            "status": status,
            "reason": provider_meta.get("unavailable_reason") if status == "unavailable" else None,
            "source": provider_meta.get("actual_source") or provider_meta.get("primary_source") or VN_SOURCE_SSI,
            "primary_source": provider_meta.get("primary_source"),
            "actual_source": provider_meta.get("actual_source"),
            "fallback_used": False,
            "fallback_reason": None,
            "timeframe": "1d",
            "range": effective_range,
            "latest_date": latest_date,
            "points": points,
            "candles": points,
        }

    def build_watchlist(
        self,
        tickers: Optional[Iterable[str]] = None,
        force_refresh: bool = False,
        include_intraday: Optional[bool] = None,
        intraday_timeframe: Optional[str] = None,
        intraday_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        symbols = normalize_vietnam_tickers(tickers)
        _observe(observe_mozyfin_watchlist_request, len(symbols))
        rows = []
        fixture_mode = _is_fixture_mode(self.manager)
        refresh_time = datetime.now(timezone.utc).isoformat()
        use_intraday = self.config.include_intraday if include_intraday is None else include_intraday
        effective_intraday_timeframe = intraday_timeframe or self.config.intraday_timeframe
        effective_intraday_limit = intraday_limit or self.config.intraday_limit
        for symbol in symbols:
            try:
                rows.append(
                    self._build_symbol(
                        symbol,
                        force_refresh=force_refresh,
                        include_intraday=use_intraday,
                        intraday_timeframe=effective_intraday_timeframe,
                        intraday_limit=effective_intraday_limit,
                    )
                )
            except Exception as exc:
                logger.warning("Vietnam dashboard failed for %s: %s", symbol, exc)
                rows.append(
                    {
                        "ticker": symbol,
                        "entity": normalize_vn_symbol(symbol),
                        "exchange": get_vn_exchange(symbol),
                        "source": VN_SOURCE_SSI,
                        "primary_source": VN_SOURCE_SSI,
                        "actual_source": VN_SOURCE_SSI,
                        "fallback_used": False,
                        "rows_loaded": 0,
                        "error": str(exc),
                        "liquidity": {"avg_volume_20d": None, "score": 0},
                        "price_limit": {
                            "limit_pct": get_vn_price_limit_pct(symbol),
                            "ceiling_price": None,
                            "floor_price": None,
                            "distance_to_limit_pct": None,
                            "near_limit": False,
                        },
                        "foreign": {"signal": "neutral_or_unavailable"},
                        "indicators": {},
                        "status_labels": ["Watch"],
                        "status_details": [
                            _status_detail("Watch", "info", "No usable market data was available for rule evaluation.", {})
                        ],
                        "validation": {
                            "valid": False,
                            "trading_date": None,
                            "missing_fields": ["date", "close", "volume", "foreign_net"],
                            "errors": [str(exc)],
                        },
                        "trend": {},
                        "warnings": ["Data unavailable for this ticker from SSI FastConnect."],
                        "news": [],
                        "news_status": self._news_status_block(),
                        "intraday_timeframe": effective_intraday_timeframe,
                        **self._disabled_intraday_payload(effective_intraday_timeframe),
                        "cache_status": {
                            "ohlcv_cache": "error",
                            **self._disabled_cache_status(),
                        },
                        "cache_last_fetched_at": self._disabled_cache_times(),
                        "cache_next_refresh_at": self._disabled_cache_times(),
                        "cache_errors": {},
                        "data_quality_summary": {
                            "overall_status": "unavailable",
                            "canonical_price_source": "SSI DailyOhlc",
                            "issues": [
                                {
                                    "code": "daily_ohlcv_missing",
                                    "severity": "warning",
                                    "message": "SSI DailyOhlc required daily OHLCV fields are missing.",
                                    "fields": {"rows_loaded": 0},
                                },
                                {
                                    "code": "provider_error",
                                    "severity": "warning",
                                    "message": "SSI provider path failed for this ticker.",
                                    "fields": {},
                                },
                            ],
                            "checks": {
                                "daily_ohlc": "unavailable",
                                "daily_stock_price": "unavailable",
                                "final_close_status": "unknown",
                                "adjusted_price_status": "unknown",
                                "intraday": "disabled",
                                "realtime": "disabled",
                                "trade_tape": "disabled",
                                "profile": "unavailable",
                                "news": "disabled",
                            },
                        },
                    }
                )
        returned_tickers = [
            vn_ticker(str(row.get("ticker") or "").strip().upper())
            for row in rows
            if isinstance(row, dict) and row.get("ticker")
        ]
        returned_ticker_set = {ticker for ticker in returned_tickers if ticker}
        missing_tickers = [symbol for symbol in symbols if symbol not in returned_ticker_set]
        health = self._build_health(rows, fixture_mode, refresh_time)
        health.update(
            {
                "requested_tickers_count": len(symbols),
                "returned_rows_count": len(rows),
                "missing_tickers": missing_tickers,
            }
        )
        cache_metadata = self._build_cache_metadata(rows)
        return {
            "market": "VN",
            "source": health["source"],
            "fixture_mode": fixture_mode,
            "last_refresh_time": refresh_time,
            "units": VN_DASHBOARD_UNITS,
            "requested_tickers_count": len(symbols),
            "returned_rows_count": len(rows),
            "missing_tickers": missing_tickers,
            "data_quality": health,
            "cache_metadata": cache_metadata,
            "watchlist": rows,
            "rule_metadata": VN_STATUS_RULE_METADATA,
            "formulas": {
                "liquidity_score": "min(100, avg_volume_20d / 1,000,000 * 100)",
                "price_change_pct": "(close - previous_close) / previous_close * 100",
                "price_limit_distance_pct": "min(abs(ceiling-close), abs(close-floor)) / previous_close * 100",
                "ma20": "SMA(close, 20)",
                "ma50": "SMA(close, 50)",
                "rsi14": "Wilder/RMA RSI using close; seed with SMA of the first 14 gains/losses, then smooth recursively",
                "rsi_method": "Wilder/RMA",
                "bollinger_20_2": "SMA(close, 20) +/- 2 * standard deviation of close",
                "volume_average_20": "SMA(volume, 20)",
                "volume_ratio": "today_volume / SMA(volume, 20)",
                "distance_to_20d_high_pct": "(close - high_20d) / high_20d * 100",
                "distance_to_20d_low_pct": "(close - low_20d) / low_20d * 100",
                "foreign_net_sums": "sum(foreign_net) over the latest 5 or 20 rows when foreign_net history is available",
                "neutral_status_labels": "Rule-based neutral condition labels only; no trading recommendations are generated",
                "intraday_change": "latest_intraday_close - latest_intraday_open using provider-returned intraday candles",
                "intraday_change_percent": "(latest_intraday_close - latest_intraday_open) / latest_intraday_open * 100",
                "intraday_range_percent": "(latest_intraday_high - latest_intraday_low) / latest_intraday_open * 100",
                "intraday_volume_vs_average": "latest_intraday_volume / average(previous available provider-returned intraday candle volumes), when at least 2 previous candles exist",
            },
        }

    def build_health(self, tickers: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        symbols = normalize_vietnam_tickers(tickers)
        fixture_mode = _is_fixture_mode(self.manager)
        refresh_time = datetime.now(timezone.utc).isoformat()
        rows = []
        for symbol in symbols:
            cached = self._build_cached_health_row(symbol)
            if cached:
                rows.append(cached)
        health = self._build_health(rows, fixture_mode, refresh_time)
        health["cache_metadata"] = self._build_cache_metadata(rows)
        return health

    def build_corporate_actions(self, tickers: Optional[Iterable[str]] = None, months_back: int = 6) -> Dict[str, Any]:
        """Return VN corporate-action calendar/history through the safe provider contract."""
        symbols = normalize_vietnam_tickers(tickers)
        safe_months_back = max(1, min(int(months_back or 6), 24))
        provider = self._get_corporate_actions_provider()
        try:
            payload = provider.fetch_corporate_actions(symbols, months_back=safe_months_back)
        except Exception as exc:  # noqa: BLE001 - optional external domain must fail open.
            checked_at = datetime.now(timezone.utc).isoformat()
            provider_name = sanitize_corporate_actions_text(getattr(provider, "provider_name", "unknown"), max_length=80)
            safe_error = sanitize_corporate_actions_text(exc)
            payload = {
                "market": "VN",
                "status": "error",
                "source": CORPORATE_ACTIONS_SOURCE,
                "provider": provider_name,
                "last_checked_at": checked_at,
                "requested_tickers": symbols,
                "months_back": safe_months_back,
                "events": [],
                "items": [],
                "error": CORPORATE_ACTIONS_UNAVAILABLE_REASON,
                "error_detail": "Corporate actions provider failed; SSI daily data remains independent.",
                "diagnostics": {
                    "provider": provider_name,
                    "request_domain": "corporate_actions",
                    "status": "error",
                    "row_count": 0,
                    "failure_class": "provider_error",
                    "last_checked_at": checked_at,
                    "error_summary": safe_error,
                    "requested_tickers_count": len(symbols),
                },
            }

        payload = dict(payload or {})
        status = normalize_provider_status(payload.get("status"))
        raw_events = payload.get("events")
        if not isinstance(raw_events, list):
            # Legacy provider-contract compatibility only. New adapters must
            # return canonical ``events``; public ``items`` is derived below.
            raw_events = payload.get("items")
        events = [dict(item) for item in (raw_events or []) if isinstance(item, dict)]
        diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}
        diagnostics = {
            "provider": sanitize_corporate_actions_text(diagnostics.get("provider") or payload.get("provider") or "unknown", max_length=80),
            "request_domain": "corporate_actions",
            "status": status,
            "row_count": len(events),
            "failure_class": sanitize_corporate_actions_text(diagnostics.get("failure_class") or status, max_length=80),
            "last_checked_at": payload.get("last_checked_at") or diagnostics.get("last_checked_at") or datetime.now(timezone.utc).isoformat(),
            "requested_tickers_count": len(symbols),
        }
        if payload.get("diagnostics") and "error_summary" in payload["diagnostics"]:
            diagnostics["error_summary"] = sanitize_corporate_actions_text(payload["diagnostics"].get("error_summary"))

        last_checked_at = payload.get("last_checked_at") or diagnostics["last_checked_at"]
        return {
            "market": "VN",
            "status": status,
            "source": payload.get("source") or CORPORATE_ACTIONS_SOURCE,
            "provider": payload.get("provider") or diagnostics["provider"],
            "last_checked_at": last_checked_at,
            "requested_tickers": symbols,
            "months_back": safe_months_back,
            "events": events,
            "items": events,
            "error": payload.get("error") if status != "ok" else None,
            "error_detail": payload.get("error_detail") if status != "ok" else None,
            "diagnostics": diagnostics,
        }

    def build_daily_index(
        self,
        index_code: str = "VNINDEX",
        limit: int = 260,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        reference_date: Optional[str] = None,
        force_refresh: bool = False,
        index_list_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return strict SSI DailyIndex rows for one IndexList-confirmed identifier."""
        normalized_index = str(index_code or "VNINDEX").strip().upper()
        provider_index, public_index, diagnostics = self._resolve_ssi_index_identifier(
            normalized_index,
            None,
            force_refresh=force_refresh,
            index_list_payload=index_list_payload,
        )
        diagnostics.update(
            {
                "endpoint": "DailyIndex",
                "requested_index_code": normalized_index,
                "selected_identifier": provider_index,
                "from_date": _valid_date_string(from_date),
                "to_date": _valid_date_string(to_date),
            }
        )
        if not provider_index:
            diagnostics.update(
                {
                    "normalized_row_count": 0,
                    "selected_row_date": None,
                    "failure_class": "identifier_unavailable",
                }
            )
            return {
                "status": "unavailable",
                "quality_status": "unavailable",
                "source": SSI_DAILY_INDEX_SOURCE,
                "reason": "SSI index identifier unavailable.",
                "index_code": public_index,
                "date": None,
                "date_match": "unavailable",
                "rows": [],
                "count": 0,
                "missing_fields": list(DAILY_INDEX_FIELDS),
                "field_coverage": {field: False for field in DAILY_INDEX_FIELDS},
                "fallback_used": False,
                "diagnostics": diagnostics,
            }

        refresh_kwargs = {"force_refresh": True} if force_refresh else {}
        payload = self._get_ssi_fetcher().get_daily_index(
            provider_index,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            **refresh_kwargs,
        )
        provider_rows = payload.get("rows") if isinstance(payload, dict) else None
        if payload.get("status") != "ok" or not isinstance(provider_rows, list) or not provider_rows:
            diagnostics.update(
                {
                    "normalized_row_count": 0,
                    "selected_row_date": None,
                    "failure_class": (
                        str(payload.get("failure_class"))
                        if isinstance(payload, dict) and payload.get("failure_class")
                        else "empty_result"
                        if payload.get("status") == "ok"
                        else "provider_unavailable"
                    ),
                }
            )
            return {
                "status": "unavailable",
                "quality_status": "unavailable",
                "source": SSI_DAILY_INDEX_SOURCE,
                "reason": self._safe_provider_reason(payload),
                "index_code": public_index,
                "date": None,
                "date_match": "unavailable",
                "rows": [],
                "count": 0,
                "missing_fields": list(DAILY_INDEX_FIELDS),
                "field_coverage": {field: False for field in DAILY_INDEX_FIELDS},
                "fallback_used": False,
                "diagnostics": diagnostics,
            }

        rows: List[Dict[str, Any]] = []
        for row in provider_rows:
            if not isinstance(row, dict):
                continue
            normalized_row = dict(row)
            normalized_row["index_code"] = public_index
            normalized_row["source"] = SSI_DAILY_INDEX_SOURCE
            rows.append(normalized_row)
        if not rows:
            diagnostics.update(
                {
                    "normalized_row_count": 0,
                    "selected_row_date": None,
                    "failure_class": "empty_result",
                }
            )
            return {
                "status": "unavailable",
                "quality_status": "unavailable",
                "source": SSI_DAILY_INDEX_SOURCE,
                "reason": SSI_UNAVAILABLE_REASON,
                "index_code": public_index,
                "date": None,
                "date_match": "unavailable",
                "rows": [],
                "count": 0,
                "missing_fields": list(DAILY_INDEX_FIELDS),
                "field_coverage": {field: False for field in DAILY_INDEX_FIELDS},
                "fallback_used": False,
                "diagnostics": diagnostics,
            }

        latest = rows[-1]
        selected_date = _valid_date_string(latest.get("date"))
        normalized_reference_date = _valid_date_string(reference_date)
        date_match = _date_match_status(normalized_reference_date, selected_date)
        field_coverage = {
            field: latest.get(field) not in (None, "")
            for field in DAILY_INDEX_FIELDS
        }
        missing_fields = [
            field
            for field, available in field_coverage.items()
            if not available
        ]
        diagnostics.update(
            {
                "normalized_row_count": len(rows),
                "selected_row_date": selected_date,
                "field_coverage": field_coverage,
                "missing_fields": missing_fields,
                "date_match": date_match,
                "chunks_used": payload.get("chunks_used"),
                "pages_used": payload.get("pages_used"),
            }
        )
        return {
            "status": "ok",
            "quality_status": "complete" if not missing_fields and date_match != "mismatched" else "partial",
            "source": SSI_DAILY_INDEX_SOURCE,
            "index_code": public_index,
            "date": selected_date,
            "date_match": date_match,
            "rows": rows,
            "count": len(rows),
            "missing_fields": missing_fields,
            "field_coverage": field_coverage,
            "fallback_used": False,
            "diagnostics": diagnostics,
        }

    def build_daily_indexes(
        self,
        index_codes: Iterable[str],
        *,
        limit: int = 40,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Return the latest real SSI DailyIndex row for each requested index."""
        normalized_codes = list(
            dict.fromkeys(
                code
                for code in (
                    self._normalize_index_value(value)
                    for value in index_codes
                )
                if code
            )
        )[:10]
        if not normalized_codes:
            normalized_codes = ["VNINDEX", "VN30"]
        normalized_to_date = _valid_date_string(to_date) or datetime.now(VN_TIMEZONE).date().isoformat()
        normalized_from_date = _valid_date_string(from_date) or (
            datetime.now(VN_TIMEZONE).date() - timedelta(days=45)
        ).isoformat()

        index_list_payload = self.build_index_list(
            "HOSE",
            force_refresh=force_refresh,
        )
        results = [
            self.build_daily_index(
                code,
                limit=limit,
                from_date=normalized_from_date,
                to_date=normalized_to_date,
                force_refresh=force_refresh,
                index_list_payload=index_list_payload,
            )
            for code in normalized_codes
        ]
        rows: List[Dict[str, Any]] = []
        for result in results:
            result_rows = result.get("rows") if isinstance(result, dict) else None
            if result.get("status") != "ok" or not isinstance(result_rows, list) or not result_rows:
                continue
            latest = dict(result_rows[-1])
            latest["status"] = "ok"
            latest["quality_status"] = result.get("quality_status")
            latest["missing_fields"] = list(result.get("missing_fields") or [])
            latest["field_coverage"] = dict(result.get("field_coverage") or {})
            rows.append(latest)

        latest_date = max(
            (
                date_text
                for date_text in (_valid_date_string(row.get("date")) for row in rows)
                if date_text
            ),
            default=None,
        )
        for row in rows:
            row["date_match"] = _date_match_status(latest_date, _valid_date_string(row.get("date")))
            if row["date_match"] == "mismatched":
                row["quality_status"] = "partial"

        successful_codes = {
            str(row.get("index_code") or "").upper()
            for row in rows
        }
        status_by_index = {
            code: next(
                (
                    str(result.get("status") or "unavailable")
                    for result in results
                    if str(result.get("index_code") or "").upper() == code
                ),
                "unavailable",
            )
            for code in normalized_codes
        }
        overall_status = (
            "ok"
            if len(successful_codes) == len(normalized_codes)
            else "partial"
            if successful_codes
            else "unavailable"
        )
        return {
            "status": overall_status,
            "source": SSI_DAILY_INDEX_SOURCE,
            "reason": None if rows else "SSI daily index unavailable.",
            "requested_index_codes": normalized_codes,
            "latest_date": latest_date,
            "rows": rows,
            "count": len(rows),
            "fallback_used": False,
            "diagnostics": {
                "endpoint": "DailyIndex",
                "requested_index_codes": normalized_codes,
                "from_date": normalized_from_date,
                "to_date": normalized_to_date,
                "normalized_row_count": len(rows),
                "failure_class": None if rows else "no_usable_rows",
                "selected_row_dates": {
                    str(row.get("index_code")): row.get("date")
                    for row in rows
                },
                "index_statuses": status_by_index,
                "per_index": {
                    str(result.get("index_code") or normalized_codes[index]): dict(
                        result.get("diagnostics") or {}
                    )
                    for index, result in enumerate(results)
                },
            },
        }

    @staticmethod
    def _index_row_quality(
        row: Dict[str, Any],
        fields: Tuple[str, ...],
    ) -> Tuple[Dict[str, bool], List[str]]:
        field_coverage = {
            field: row.get(field) not in (None, "")
            for field in fields
        }
        missing_fields = [
            field
            for field, available in field_coverage.items()
            if not available
        ]
        return field_coverage, missing_fields

    def build_index_list(
        self,
        market: Optional[str] = None,
        *,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Return strict SSI index identifiers for index-aware dashboard work."""
        normalized_market = str(market or "").strip().upper() or None
        refresh_kwargs = {"force_refresh": True} if force_refresh else {}
        payload = self._get_ssi_fetcher().get_index_list(normalized_market, **refresh_kwargs)
        provider_rows = payload.get("rows") if isinstance(payload, dict) else None
        diagnostics = {
            "endpoint": "IndexList",
            "requested_market": normalized_market,
            "normalized_row_count": len(provider_rows) if isinstance(provider_rows, list) else 0,
        }
        if payload.get("status") != "ok" or not isinstance(provider_rows, list) or not provider_rows:
            diagnostics["failure_class"] = (
                str(payload.get("failure_class"))
                if isinstance(payload, dict) and payload.get("failure_class")
                else "empty_result"
                if payload.get("status") == "ok"
                else "provider_unavailable"
            )
            return {
                "status": "unavailable",
                "source": SSI_INDEX_LIST_SOURCE,
                "reason": self._safe_provider_reason(payload),
                "market": normalized_market,
                "rows": [],
                "count": 0,
                "fallback_used": False,
                "diagnostics": diagnostics,
            }
        rows: List[Dict[str, Any]] = []
        for row in provider_rows:
            if not isinstance(row, dict):
                continue
            normalized_row = dict(row)
            normalized_row["source"] = SSI_INDEX_LIST_SOURCE
            coverage, missing = self._index_row_quality(normalized_row, INDEX_LIST_FIELDS)
            normalized_row["field_coverage"] = coverage
            normalized_row["missing_fields"] = missing
            rows.append(normalized_row)
        diagnostics["normalized_row_count"] = len(rows)
        diagnostics["returned_markets"] = sorted(
            {
                str(row.get("market") or row.get("exchange")).upper()
                for row in rows
                if row.get("market") or row.get("exchange")
            }
        )
        return {
            "status": "ok",
            "source": SSI_INDEX_LIST_SOURCE,
            "market": normalized_market,
            "fallback_used": False,
            "rows": rows,
            "count": len(rows),
            "diagnostics": diagnostics,
        }

    @staticmethod
    def _normalize_index_value(value: Any) -> Optional[str]:
        text = str(value or "").strip().upper()
        return text or None

    def _resolve_ssi_index_identifier(
        self,
        index_code: str,
        market: Optional[str],
        *,
        force_refresh: bool = False,
        index_list_payload: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], str, Dict[str, Any]]:
        normalized_index = self._normalize_index_value(index_code) or ""
        diagnostics: Dict[str, Any] = {
            "requested_index_code": normalized_index,
            "provider_index_identifier": None,
            "index_identifier_source": None,
            "resolution_status": "unavailable",
            "index_list_status": None,
            "index_list_rows": 0,
        }
        fetcher = self._get_ssi_fetcher()
        get_index_list = getattr(fetcher, "get_index_list", None)
        if not callable(get_index_list):
            diagnostics["index_list_status"] = "unavailable"
            diagnostics["index_list_reason"] = "SSI IndexList method unavailable."
            diagnostics["failure_class"] = "index_list_method_unavailable"
            return None, normalized_index, diagnostics
        if index_list_payload is None:
            refresh_kwargs = {"force_refresh": True} if force_refresh else {}
            payload = get_index_list(market, **refresh_kwargs)
        else:
            payload = index_list_payload
        diagnostics["index_list_status"] = payload.get("status")
        rows = payload.get("rows") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            diagnostics["index_list_reason"] = self._safe_provider_reason(payload)
            diagnostics["failure_class"] = "index_list_unavailable"
            return None, normalized_index, diagnostics
        diagnostics["index_list_rows"] = len(rows)
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_id = self._normalize_index_value(row.get("index_id"))
            row_code = self._normalize_index_value(row.get("index_code"))
            if normalized_index in {row_id, row_code}:
                provider_identifier = row_id or row_code or normalized_index
                public_index_code = row_code or row_id or normalized_index
                diagnostics.update(
                    {
                        "provider_index_identifier": provider_identifier,
                        "resolved_index_code": public_index_code,
                        "index_identifier_source": "IndexList",
                        "resolution_status": "resolved",
                    }
                )
                return provider_identifier, public_index_code, diagnostics
        if payload.get("status") != "ok":
            diagnostics["index_list_reason"] = self._safe_provider_reason(payload)
            diagnostics["failure_class"] = "index_list_unavailable"
        else:
            diagnostics["failure_class"] = "identifier_not_found"
        return None, normalized_index, diagnostics

    def build_index_components(
        self,
        index_code: str,
        market: Optional[str] = None,
        *,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Return strict SSI component rows for an explicit index code."""
        normalized_index = str(index_code or "").strip().upper()
        normalized_market = str(market or "").strip().upper() or None
        cache_key = _cache_key(
            "index_components",
            normalized_index,
            provider=VN_PROVIDER_SSI,
            market=normalized_market or "",
        )
        cache_result = _read_cache(
            cache_key,
            "index_components",
            lambda: self._build_index_components_uncached(
                normalized_index,
                normalized_market,
                force_refresh=force_refresh,
            ),
            force_refresh=force_refresh,
            ttl_resolver=lambda payload: (
                VN_INDEX_COMPONENTS_CACHE_TTL_SECONDS
                if isinstance(payload, dict)
                and payload.get("status") == "ok"
                and bool(payload.get("rows"))
                else VN_INDEX_COMPONENTS_NEGATIVE_CACHE_TTL_SECONDS
            ),
        )
        result = dict(cache_result["value"])
        diagnostics = dict(result.get("diagnostics") or {})
        cache_entry = cache_result.get("entry")
        diagnostics.update(
            {
                "cache_status": cache_result["status"],
                "cache_ttl_seconds": (
                    VN_INDEX_COMPONENTS_CACHE_TTL_SECONDS
                    if result.get("status") == "ok" and bool(result.get("rows"))
                    else VN_INDEX_COMPONENTS_NEGATIVE_CACHE_TTL_SECONDS
                ),
                "cache_negative": result.get("status") != "ok" or not bool(result.get("rows")),
                "cache_key": {
                    "provider": VN_PROVIDER_SSI,
                    "endpoint": "IndexComponents",
                    "index_code": normalized_index,
                    "market": normalized_market,
                },
                "cache_expires_at": _iso(cache_entry.expires_at) if cache_entry else None,
            }
        )
        result["diagnostics"] = diagnostics
        return result

    def _build_index_components_uncached(
        self,
        normalized_index: str,
        normalized_market: Optional[str],
        *,
        force_refresh: bool,
    ) -> Dict[str, Any]:
        diagnostics: Dict[str, Any] = {
            "endpoint": "IndexComponents",
            "requested_index_code": normalized_index,
            "requested_market": normalized_market,
            "provider_index_identifier": normalized_index,
            "selected_identifier": normalized_index,
            "index_identifier_source": "explicit_index_code",
            "resolution_status": "direct",
            "index_list_status": "not_required",
            "index_list_rows": 0,
            "index_components_attempted": True,
        }
        refresh_kwargs = {"force_refresh": True} if force_refresh else {}
        payload = self._get_ssi_fetcher().get_index_components(
            normalized_index,
            market=normalized_market,
            **refresh_kwargs,
        )
        provider_rows = payload.get("rows") if isinstance(payload, dict) else None
        diagnostics.update(
            {
                "index_components_status": payload.get("status"),
                "index_components_reason": self._safe_provider_reason(payload) if payload.get("status") != "ok" else None,
                "normalized_row_count": len(provider_rows) if isinstance(provider_rows, list) else 0,
            }
        )
        if payload.get("status") != "ok" or not isinstance(provider_rows, list) or not provider_rows:
            diagnostics["failure_class"] = (
                str(payload.get("failure_class"))
                if isinstance(payload, dict) and payload.get("failure_class")
                else "no_rows"
                if payload.get("status") == "ok"
                else "index_components_unavailable"
            )
            return {
                "status": "unavailable",
                "source": SSI_INDEX_COMPONENTS_SOURCE,
                "reason": self._safe_provider_reason(payload),
                "index_code": normalized_index,
                "market": normalized_market,
                "rows": [],
                "count": 0,
                "fallback_used": False,
                "diagnostics": diagnostics,
            }
        rows = []
        for row in provider_rows:
            if not isinstance(row, dict):
                continue
            normalized_row_index = self._normalize_index_value(row.get("index_code"))
            row_payload = dict(row)
            if not normalized_row_index or normalized_row_index == normalized_index:
                row_payload["index_code"] = normalized_index
            row_payload["source"] = SSI_INDEX_COMPONENTS_SOURCE
            coverage, missing = self._index_row_quality(row_payload, INDEX_COMPONENT_FIELDS)
            row_payload["field_coverage"] = coverage
            row_payload["missing_fields"] = missing
            rows.append(row_payload)
        aggregate_coverage = {
            field: all(row.get(field) not in (None, "") for row in rows)
            for field in INDEX_COMPONENT_FIELDS
        }
        diagnostics["field_coverage"] = aggregate_coverage
        diagnostics["missing_fields"] = [
            field
            for field, available in aggregate_coverage.items()
            if not available
        ]
        return {
            "status": "ok",
            "source": SSI_INDEX_COMPONENTS_SOURCE,
            "fallback_used": False,
            "index_code": normalized_index,
            "market": normalized_market,
            "rows": rows,
            "count": len(rows),
            "diagnostics": diagnostics,
        }

    def _build_cache_metadata(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        hit_count = 0
        miss_count = 0
        stale_count = 0
        symbols: Dict[str, Any] = {}
        last_fetched_at: Dict[str, Dict[str, Optional[str]]] = {}
        next_refresh_at: Dict[str, Dict[str, Optional[str]]] = {}
        for row in rows:
            ticker = row.get("ticker", "")
            status = row.get("cache_status", {})
            fetched = row.get("cache_last_fetched_at", {})
            refresh = row.get("cache_next_refresh_at", {})
            symbols[ticker] = status
            last_fetched_at[ticker] = fetched
            next_refresh_at[ticker] = refresh
            for value in status.values():
                if value == "hit":
                    hit_count += 1
                elif value in {"miss", "refresh"}:
                    miss_count += 1
                elif value == "stale":
                    stale_count += 1
        return {
            "cache_hit_count": hit_count,
            "cache_miss_count": miss_count,
            "stale_cache_used_count": stale_count,
            "cache_ttl_seconds": VN_CACHE_TTL_SECONDS,
            "last_fetched_at": last_fetched_at,
            "next_refresh_at": next_refresh_at,
            "symbols": symbols,
        }

    def _build_cached_health_row(self, symbol: str) -> Optional[Dict[str, Any]]:
        ohlcv_key = _cache_key("ohlcv", symbol, timeframe="1d", limit=260, days=self.config.history_days)
        ohlcv_entry = _get_cache_entry(ohlcv_key)
        if ohlcv_entry is None:
            return None
        df, source, _provider_meta = self._unpack_daily_ohlcv_value(
            ohlcv_entry.value,
            self.config.daily_data_provider,
        )
        if df is None or df.empty:
            return None
        df = df.sort_values("date").reset_index(drop=True)
        latest = df.iloc[-1]
        foreign = {
            "buy": _safe_float(_last_value(df, "foreign_buy")),
            "sell": _safe_float(_last_value(df, "foreign_sell")),
            "net": _safe_float(_last_value(df, "foreign_net")),
        }
        validation = validate_vietnam_row(latest, foreign)
        return {
            "ticker": symbol,
            "source": source,
            "date": latest.get("date").strftime("%Y-%m-%d") if hasattr(latest.get("date"), "strftime") else str(latest.get("date")),
            "validation": validation,
            "cache_status": {
                "ohlcv_cache": "hit" if ohlcv_entry.expires_at > _utc_now() else "stale",
                **self._disabled_cache_status(),
            },
            "cache_last_fetched_at": {
                "ohlcv": _iso(ohlcv_entry.fetched_at),
                **self._disabled_cache_times(),
            },
            "cache_next_refresh_at": {
                "ohlcv": _iso(ohlcv_entry.expires_at),
                **self._disabled_cache_times(),
            },
        }

    def _build_health(self, rows: List[Dict[str, Any]], fixture_mode: bool, refresh_time: str) -> Dict[str, Any]:
        missing_fields = {
            row.get("ticker", ""): row.get("validation", {}).get("missing_fields", [])
            for row in rows
            if row.get("validation", {}).get("missing_fields")
        }
        errors = {
            row.get("ticker", ""): [*row.get("validation", {}).get("errors", []), *([row["error"]] if row.get("error") else [])]
            for row in rows
            if row.get("validation", {}).get("errors") or row.get("error")
        }
        valid_dates = [
            row.get("validation", {}).get("trading_date") or row.get("date")
            for row in rows
            if row.get("validation", {}).get("trading_date") or row.get("date")
        ]
        actual_sources = {row.get("actual_source") for row in rows if row.get("actual_source")}
        primary_sources = {row.get("primary_source") for row in rows if row.get("primary_source")}
        source_label = _source_label(fixture_mode)
        if self.config.daily_data_provider == VN_PROVIDER_SSI:
            source_label = "SSI live" if VN_SOURCE_SSI in actual_sources else "SSI unavailable"
        elif VN_SOURCE_SSI in actual_sources or VN_SOURCE_SSI in primary_sources:
            source_label = "SSI live" if VN_SOURCE_SSI in actual_sources else "SSI unavailable"
        return {
            "source": source_label,
            "fixture_mode": fixture_mode,
            "symbols_loaded": sum(1 for row in rows if not row.get("error")),
            "last_trading_date": max(valid_dates) if valid_dates else None,
            "last_refresh_time": refresh_time,
            "missing_fields": missing_fields,
            "errors": errors,
            "units": VN_DASHBOARD_UNITS,
        }

    def build_realtime_snapshot(
        self,
        symbols: Optional[Iterable[str]],
        *,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        tickers = normalize_vietnam_tickers(symbols)
        if not tickers:
            return {
                "market": "VN",
                "source": SSI_REALTIME_SOURCE,
                "status": "unavailable",
                "error": "No symbol requested",
                "error_detail": "No Vietnam ticker was requested.",
                "reason_code": "unknown",
                "classification": "unknown",
                "status_message": "No Vietnam ticker was requested.",
                "requested_tickers": [],
                "quotes": [],
                "cache": {"cache_status": "unavailable"},
            }

        if self.config.realtime_data_provider != VN_PROVIDER_SSI or not self.config.ssi_realtime_enabled:
            return {
                "market": "VN",
                "source": SSI_REALTIME_SOURCE,
                "status": "disabled",
                "error": None,
                "error_detail": VN_REALTIME_DISABLED_REASON,
                "reason_code": "disabled",
                "classification": "disabled",
                "status_message": VN_REALTIME_DISABLED_REASON,
                "requested_tickers": tickers,
                "quotes": [],
                "cache": {"cache_status": "disabled"},
            }
        if not self.config.ssi_streaming_realtime_enabled:
            diagnostics = {
                "streaming_status": "disabled",
                "manager_state": "disabled",
                "cache_status": "disabled",
                "live_adapter_status": "not_enabled",
            }
            return {
                "market": "VN",
                "source": SSI_REALTIME_SOURCE,
                "status": "unavailable",
                "error": "SSI realtime manager disabled.",
                "error_detail": "SSI realtime manager disabled.",
                "reason_code": "config_disabled",
                "classification": "config_disabled",
                "status_message": "SSI realtime manager disabled.",
                "requested_tickers": tickers,
                "quotes": [],
                "cache": {"cache_status": "disabled"},
                "streaming_status": "disabled",
                "manager_state": "disabled",
                "cache_status": "disabled",
                "diagnostics": diagnostics,
            }

        # Realtime reads the process-local streaming cache directly. Wrapping
        # this call in the generic response cache would hide fresh stream rows.
        read_at = _utc_now()
        read_error: Optional[Exception] = None
        try:
            payload = self._get_ssi_fetcher().get_realtime_snapshot(tickers)
        except Exception as exc:
            read_error = exc
            payload = {}
            logger.debug("SSI realtime cache read failed for %s", ",".join(tickers))
        payload = payload if isinstance(payload, dict) else {}
        status = str(payload.get("status") or "unavailable").lower()
        quotes = [
            self._realtime_quote_from_snapshot(row, str(row.get("ticker") or row.get("symbol") or "").upper())
            for row in payload.get("quotes", [])
            if isinstance(row, dict)
        ]
        diagnostics = _live_failure_diagnostics(
            payload,
            reason=(payload.get("reason") or payload.get("message")) if status != "ok" else None,
        )
        streaming_cache_ttl_seconds = _safe_int(diagnostics.get("cache_ttl_seconds"))
        response = {
            "market": "VN",
            "source": SSI_REALTIME_SOURCE,
            "status": "ok" if status == "ok" and quotes else status,
            "error": None if status == "ok" else payload.get("reason") or VN_REALTIME_UNAVAILABLE_REASON,
            "error_detail": None if status == "ok" else payload.get("reason") or payload.get("message") or VN_REALTIME_UNAVAILABLE_REASON,
            "requested_tickers": tickers,
            "quotes": quotes,
            "cache": {
                "cache_status": "bypassed",
                "response_cache_status": "bypassed",
                "streaming_cache_status": payload.get("cache_status") or "unavailable",
                "last_fetched_at": _iso(read_at),
                "next_refresh_at": _iso(read_at),
                "ttl_seconds": 0,
                "streaming_cache_ttl_seconds": streaming_cache_ttl_seconds,
            },
        }
        if diagnostics:
            response["diagnostics"] = diagnostics
        for key in ("streaming_status", "manager_state", "runtime_status", "cache_status", "parsed_streaming_rows"):
            if key in payload:
                response[key] = payload.get(key)
        if status == "ok" and not quotes:
            response["status"] = "unavailable"
            response["error"] = VN_REALTIME_UNAVAILABLE_REASON
            response["error_detail"] = "SSI realtime returned no quote rows."
        if read_error:
            response["status"] = "unavailable"
            response["error"] = VN_REALTIME_UNAVAILABLE_REASON
            response["error_detail"] = VN_REALTIME_UNAVAILABLE_REASON
            response["cache"]["streaming_cache_status"] = "unavailable"
            diagnostics = {
                **diagnostics,
                "failure_class": "provider_unavailable",
                "retryable": True,
            }
            response["diagnostics"] = diagnostics
        response_reason_code = _classify_realtime_reason(
            status=str(response.get("status") or status or "unavailable"),
            reason=str(response.get("error_detail") or response.get("error") or payload.get("reason") or ""),
            diagnostics=diagnostics,
            symbol=tickers[0] if len(tickers) == 1 else None,
        )
        response["reason_code"] = response_reason_code
        response["classification"] = response_reason_code
        response["status_message"] = _status_message_from_reason(
            section="realtime",
            status=str(response.get("status") or "unavailable"),
            reason_code=response_reason_code,
            fallback=VN_REALTIME_UNAVAILABLE_REASON,
        )
        if response.get("status") != "ok":
            response["error"] = response["status_message"]
            response["error_detail"] = response["status_message"]
        return response

    def build_trade_tape(
        self,
        symbol: str,
        *,
        limit: int = 100,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        ticker = vn_ticker(symbol)
        safe_limit = max(1, min(int(limit or 100), 500))
        if not ticker:
            return {
                "market": "VN",
                "source": SSI_TRADE_TAPE_SOURCE,
                "symbol": "",
                "status": "unavailable",
                "error": "No symbol requested",
                "error_detail": "No Vietnam ticker was requested.",
                "reason_code": "unknown",
                "classification": "unknown",
                "status_message": "No Vietnam ticker was requested.",
                "trades": [],
                "note": "SSI trade tape is separate from official daily OHLCV.",
                "cache": {"cache_status": "unavailable"},
            }

        if self.config.trade_tape_provider != VN_PROVIDER_SSI or not self.config.ssi_trade_tape_enabled:
            return {
                "market": "VN",
                "source": SSI_TRADE_TAPE_SOURCE,
                "symbol": ticker,
                "status": "disabled",
                "error": None,
                "error_detail": VN_TRADE_TAPE_DISABLED_REASON,
                "reason_code": "disabled",
                "classification": "disabled",
                "status_message": VN_TRADE_TAPE_DISABLED_REASON,
                "trades": [],
                "note": "SSI trade tape is disabled.",
                "cache": {"cache_status": "disabled"},
            }

        cache_key = _cache_key(
            "trade_tape",
            ticker,
            provider=self.config.trade_tape_provider,
            enabled=self.config.ssi_trade_tape_enabled,
            limit=safe_limit,
        )
        result = _read_cache(
            cache_key,
            "trade_tape",
            lambda: self._get_ssi_fetcher().get_trade_tape(ticker, limit=safe_limit),
            force_refresh=force_refresh,
        )
        payload = result["value"] if isinstance(result.get("value"), dict) else {}
        status = str(payload.get("status") or "unavailable").lower()
        trades = [self._trade_row_from_ssi(row) for row in payload.get("trades", []) if isinstance(row, dict)]
        diagnostics = _live_failure_diagnostics(
            payload,
            reason=(payload.get("reason") or payload.get("message")) if status != "ok" else None,
        )
        response = {
            "market": "VN",
            "source": SSI_TRADE_TAPE_SOURCE,
            "symbol": ticker,
            "status": "ok" if status == "ok" and trades else status,
            "error": None if status == "ok" else payload.get("reason") or VN_TRADE_TAPE_UNAVAILABLE_REASON,
            "error_detail": None if status == "ok" else payload.get("reason") or payload.get("message") or VN_TRADE_TAPE_UNAVAILABLE_REASON,
            "trades": trades,
            "note": "SSI trade tape is separate from official daily OHLCV.",
            "cache": {
                "cache_status": result["status"],
                "last_fetched_at": _iso(result["entry"].fetched_at),
                "next_refresh_at": _iso(result["entry"].expires_at),
                "ttl_seconds": VN_CACHE_TTL_SECONDS["trade_tape"],
            },
            "diagnostics": diagnostics,
        }
        if status == "ok" and not trades:
            response["status"] = "unavailable"
            response["error"] = VN_TRADE_TAPE_UNAVAILABLE_REASON
            response["error_detail"] = "SSI trade tape returned no trade rows."
        if result.get("error"):
            response["status"] = "unavailable"
            response["error"] = VN_TRADE_TAPE_UNAVAILABLE_REASON
            response["error_detail"] = str(result["error"])
            response["diagnostics"] = _live_failure_diagnostics(
                payload,
                reason=str(result["error"]),
            )
        response_reason_code = _classify_trade_tape_reason(
            status=str(response.get("status") or status or "unavailable"),
            reason=str(response.get("error_detail") or response.get("error") or payload.get("reason") or payload.get("streaming_status") or ""),
        )
        if response.get("status") == "ok" and payload.get("streaming_status"):
            response_reason_code = "streaming_trade_tape_supported"
        response["reason_code"] = response_reason_code
        response["classification"] = response_reason_code
        response["status_message"] = _status_message_from_reason(
            section="trade_tape",
            status=str(response.get("status") or "unavailable"),
            reason_code=response_reason_code,
            fallback=VN_TRADE_TAPE_UNAVAILABLE_REASON,
        )
        if response.get("status") != "ok":
            response["error"] = response["status_message"]
            response["error_detail"] = response["status_message"]
        return response

    def _build_symbol(
        self,
        symbol: str,
        force_refresh: bool = False,
        include_intraday: bool = True,
        intraday_timeframe: str = "1h",
        intraday_limit: int = 8,
    ) -> Dict[str, Any]:
        daily_provider = self.config.daily_data_provider
        ohlcv_key = self._daily_ohlcv_cache_key(
            symbol,
            daily_provider,
            limit=260,
            days=self.config.history_days,
        )
        ohlcv_result = _read_cache(
            ohlcv_key,
            "ohlcv",
            self._build_daily_ohlcv_loader(
                symbol,
                daily_provider,
                limit=260,
                days=self.config.history_days,
            ),
            force_refresh=force_refresh,
        )
        df, source, provider_meta = self._unpack_daily_ohlcv_value(ohlcv_result["value"], daily_provider)
        cache_status = {
            "ohlcv_cache": ohlcv_result["status"],
            **self._disabled_cache_status(),
        }
        cache_last_fetched_at = {
            "ohlcv": _iso(ohlcv_result["entry"].fetched_at),
            **self._disabled_cache_times(),
        }
        cache_next_refresh_at = {
            "ohlcv": _iso(ohlcv_result["entry"].expires_at),
            **self._disabled_cache_times(),
        }
        cache_errors = {}
        if ohlcv_result["error"]:
            cache_errors["ohlcv"] = ohlcv_result["error"]
        symbol_metadata = self._ssi_symbol_metadata(symbol, force_refresh=force_refresh)
        metadata_source = symbol_metadata.get("source") or SSI_SECURITIES_DETAILS_SOURCE
        company_name = symbol_metadata.get("name") if symbol_metadata.get("status") == "ok" else None
        if df is None or df.empty:
            unavailable_reason = provider_meta.get("unavailable_reason") or "No OHLCV rows were returned."
            daily_stock_price_payload, ssi_daily_stock_price, _ssi_daily_stock_price_history = (
                self._daily_stock_price_enrichment_block(
                    symbol,
                    daily_ohlc_date=None,
                    force_refresh=force_refresh,
                )
            )
            cache_status.update(daily_stock_price_payload["cache_status"])
            cache_last_fetched_at.update(daily_stock_price_payload["cache_last_fetched_at"])
            cache_next_refresh_at.update(daily_stock_price_payload["cache_next_refresh_at"])
            cache_errors.update(daily_stock_price_payload["cache_errors"])
            daily_stock_price_status = str(ssi_daily_stock_price.get("status") or "unavailable")
            price_limit_status = (
                "ok"
                if daily_stock_price_status == "ok"
                and any(
                    ssi_daily_stock_price.get(field) is not None
                    for field in ("reference_price", "ceiling_price", "floor_price")
                )
                else "unavailable"
            )
            foreign_status = (
                "ok"
                if daily_stock_price_status == "ok"
                and any(
                    ssi_daily_stock_price.get(field) is not None
                    for field in ("foreign_buy_volume", "foreign_sell_volume", "foreign_net_volume")
                )
                else "unavailable"
            )
            row_payload = {
                "ticker": symbol,
                "status": "unavailable",
                "reason": unavailable_reason,
                "error": "ssi_unavailable" if provider_meta.get("primary_source") == VN_SOURCE_SSI else "no_data",
                "name": company_name,
                "company_name": company_name,
                "security_type": symbol_metadata.get("security_type"),
                "industry": symbol_metadata.get("industry"),
                "sector": symbol_metadata.get("sector"),
                "market": symbol_metadata.get("market"),
                "metadata_source": metadata_source,
                "symbol_metadata": symbol_metadata,
                "issuer": symbol_metadata.get("issuer"),
                "lot_size": symbol_metadata.get("lot_size"),
                "listed_shares": symbol_metadata.get("listed_shares"),
                "listed_date": symbol_metadata.get("listed_date"),
                "source": source,
                "primary_source": provider_meta.get("primary_source"),
                "actual_source": provider_meta.get("actual_source"),
                "fallback_used": False,
                "fallback_reason": None,
                "reference_source": SSI_DAILY_STOCK_PRICE_SOURCE,
                "foreign_flow_source": SSI_DAILY_STOCK_PRICE_SOURCE,
                "rows_loaded": 0,
                "latest_price": None,
                "latest_price_source": None,
                "latest_price_date": None,
                "ohlcv_close": None,
                "daily_close": None,
                "ohlcv_date": None,
                "daily_stock_price_date": ssi_daily_stock_price.get("date"),
                "daily_stock_price_date_match": ssi_daily_stock_price.get("date_match"),
                "daily_stock_price_staleness_reason": ssi_daily_stock_price.get("staleness_reason"),
                "validation": {
                    "valid": False,
                    "trading_date": None,
                    "missing_fields": ["date", "close", "volume", "foreign_net"],
                    "errors": [unavailable_reason],
                },
                "price_limit": {
                    "limit_pct": get_vn_price_limit_pct(symbol),
                    "reference_price": _safe_float(ssi_daily_stock_price.get("reference_price")),
                    "ceiling_price": _safe_float(ssi_daily_stock_price.get("ceiling_price")),
                    "floor_price": _safe_float(ssi_daily_stock_price.get("floor_price")),
                    "distance_to_limit_pct": None,
                    "near_limit": False,
                    "source": SSI_DAILY_STOCK_PRICE_SOURCE,
                    "status": price_limit_status,
                },
                "daily_stock_price": ssi_daily_stock_price,
                "ssi_reference_price": _safe_float(ssi_daily_stock_price.get("reference_price")),
                "ssi_ceiling_price": _safe_float(ssi_daily_stock_price.get("ceiling_price")),
                "ssi_floor_price": _safe_float(ssi_daily_stock_price.get("floor_price")),
                "ssi_adjusted_close": _safe_float(ssi_daily_stock_price.get("adjusted_close")),
                "ssi_foreign_net_volume": _safe_float(ssi_daily_stock_price.get("foreign_net_volume")),
                "ssi_foreign_net_value": _safe_float(ssi_daily_stock_price.get("foreign_net_value")),
                "ssi_matched_volume": _safe_float(ssi_daily_stock_price.get("matched_volume")),
                "ssi_matched_value": _safe_float(ssi_daily_stock_price.get("matched_value")),
                "ssi_put_through_volume": _safe_float(ssi_daily_stock_price.get("put_through_volume")),
                "ssi_put_through_value": _safe_float(ssi_daily_stock_price.get("put_through_value")),
                "foreign": {
                    "buy": _safe_float(ssi_daily_stock_price.get("foreign_buy_volume")),
                    "sell": _safe_float(ssi_daily_stock_price.get("foreign_sell_volume")),
                    "net": _safe_float(ssi_daily_stock_price.get("foreign_net_volume")),
                    "buy_value": _safe_float(ssi_daily_stock_price.get("foreign_buy_value")),
                    "sell_value": _safe_float(ssi_daily_stock_price.get("foreign_sell_value")),
                    "net_value": _safe_float(ssi_daily_stock_price.get("foreign_net_value")),
                    "date": ssi_daily_stock_price.get("date"),
                    "net_unit": "shares" if foreign_status == "ok" else None,
                    "value_unit": "VND" if _safe_float(ssi_daily_stock_price.get("foreign_net_value")) is not None else None,
                    "source": SSI_DAILY_STOCK_PRICE_SOURCE,
                    "status": foreign_status,
                },
                "indicators": {},
                "status_labels": ["Watch"],
                "status_details": [
                    _status_detail("Watch", "info", "No OHLCV rows were returned for rule evaluation.", {})
                ],
                "warnings": [unavailable_reason],
                "news": [],
                "news_status": self._news_status_block(),
                **self._disabled_intraday_payload(intraday_timeframe),
                **self._disabled_realtime_payload(symbol),
                **self._disabled_trade_tape_payload(symbol),
                "diagnostics": {
                    "realtime": {},
                    "trade_tape": {},
                },
                "cache_status": cache_status,
                "cache_last_fetched_at": cache_last_fetched_at,
                "cache_next_refresh_at": cache_next_refresh_at,
                "cache_errors": cache_errors,
            }
            row_payload["data_quality_summary"] = build_vietnam_data_quality_summary(row_payload)
            row_payload["data_quality_summary"]["issues"].append(
                {
                    "code": "provider_empty",
                    "severity": "warning",
                    "message": "Provider returned no usable DailyOhlc rows for this ticker.",
                    "fields": {"rows_loaded": 0},
                }
            )
            return row_payload

        df = df.sort_values("date").reset_index(drop=True)
        latest = df.iloc[-1]
        previous = df.iloc[-2] if len(df) >= 2 else latest
        close = _safe_float(latest.get("close"))
        prev_close = _safe_float(previous.get("close"))
        change_pct = _safe_float(latest.get("pct_chg"))
        if change_pct is None and close is not None and prev_close:
            change_pct = (close - prev_close) / prev_close * 100

        liquidity = calculate_liquidity_score(df, self.config.liquidity_target_avg_volume)
        limit_state = calculate_price_limit_state(df, symbol)
        exchange = str(symbol_metadata.get("exchange") or _last_value(df, "exchange") or get_vn_exchange(symbol))
        ex_dividend_warning = bool(_last_value(df, "ex_dividend_warning"))
        ohlcv_date = _valid_date_string(latest.get("date"))
        price_adjustment_status = str(_last_value(df, "price_adjustment_status") or "unknown")
        foreign = {
            "buy": _safe_float(_last_value(df, "foreign_buy")),
            "sell": _safe_float(_last_value(df, "foreign_sell")),
            "net": _safe_float(_last_value(df, "foreign_net")),
            "date": ohlcv_date,
            "net_unit": "unknown",
            "buy_raw_field": "foreign_buy" if _last_value(df, "foreign_buy") is not None else None,
            "sell_raw_field": "foreign_sell" if _last_value(df, "foreign_sell") is not None else None,
            "latest_price": None,
            "price_raw_field": None,
            "price_date": None,
        }
        foreign_history: List[Dict[str, Any]] = []
        strict_daily_stock_price = self.config.daily_stock_price_provider == VN_PROVIDER_SSI
        reference_source = SSI_DAILY_STOCK_PRICE_SOURCE if strict_daily_stock_price else "exchange_limit_estimate"
        foreign_flow_source = SSI_DAILY_STOCK_PRICE_SOURCE if strict_daily_stock_price else "disabled"
        ssi_daily_stock_price: Optional[Dict[str, Any]] = None
        ssi_daily_stock_price_reason: Optional[str] = None
        ssi_daily_stock_price_diagnostics: Dict[str, Any] = {}
        if strict_daily_stock_price:
            limit_state = {
                "limit_pct": get_vn_price_limit_pct(symbol),
                "reference_price": None,
                "ceiling_price": None,
                "floor_price": None,
                "distance_to_limit_pct": None,
                "near_limit": False,
                "source": SSI_DAILY_STOCK_PRICE_SOURCE,
                "status": "unavailable",
            }
            foreign = {
                "buy": None,
                "sell": None,
                "net": None,
                "date": None,
                "net_unit": None,
                "buy_raw_field": None,
                "sell_raw_field": None,
                "latest_price": None,
                "price_raw_field": None,
                "price_date": None,
                "source": SSI_DAILY_STOCK_PRICE_SOURCE,
                "status": "unavailable",
            }
        daily_stock_price_result = self._read_latest_ssi_daily_stock_price(
            symbol,
            force_refresh=force_refresh,
        )
        (
            ssi_daily_stock_price,
            ssi_daily_stock_price_reason,
            ssi_daily_stock_price_diagnostics,
            ssi_daily_stock_price_history,
        ) = daily_stock_price_result["value"]
        cache_status["daily_stock_price_cache"] = daily_stock_price_result["status"]
        cache_last_fetched_at["daily_stock_price"] = _iso(daily_stock_price_result["entry"].fetched_at)
        cache_next_refresh_at["daily_stock_price"] = _iso(daily_stock_price_result["entry"].expires_at)
        if daily_stock_price_result["error"]:
            cache_errors["daily_stock_price"] = daily_stock_price_result["error"]
        if ssi_daily_stock_price:
            ssi_daily_stock_price = self._normalize_ssi_daily_stock_price_enrichment(
                ssi_daily_stock_price,
                daily_ohlc_date=ohlcv_date,
                diagnostics=ssi_daily_stock_price_diagnostics,
            )
            limit_state, foreign, foreign_history = self._apply_ssi_daily_stock_price_enrichment(
                symbol,
                ssi_daily_stock_price,
                limit_state,
                foreign,
                foreign_history,
                ssi_daily_stock_price_history,
            )
            reference_source = SSI_DAILY_STOCK_PRICE_SOURCE
            foreign_flow_source = SSI_DAILY_STOCK_PRICE_SOURCE
        elif strict_daily_stock_price:
            ssi_daily_stock_price = self._unavailable_ssi_daily_stock_price(
                reason=ssi_daily_stock_price_reason,
                daily_ohlc_date=ohlcv_date,
                diagnostics=ssi_daily_stock_price_diagnostics,
            )
        ssi_daily_stock_price_available = (
            bool(ssi_daily_stock_price)
            and ssi_daily_stock_price.get("status") != "unavailable"
            and bool(ssi_daily_stock_price.get("date"))
        )
        foreign_net = _safe_float(foreign.get("net"))
        quote_date = _valid_date_string(foreign.get("date"))
        foreign_net_date = quote_date
        foreign_date_match = _date_match_status(ohlcv_date, foreign_net_date)
        foreign_net_unit = str(foreign.get("net_unit") or "unknown")
        foreign_buy_raw_field = foreign.get("buy_raw_field")
        foreign_sell_raw_field = foreign.get("sell_raw_field")
        quote_latest_price = _safe_float(foreign.get("latest_price"))
        quote_price_raw_field = foreign.get("price_raw_field")
        quote_price_date = _valid_date_string(foreign.get("price_date"))
        if quote_latest_price is not None and quote_price_raw_field:
            latest_price = quote_latest_price
            latest_price_source = "quote"
            latest_price_raw_field = str(quote_price_raw_field)
            latest_price_date = quote_price_date
            price_source_warning = None
        else:
            latest_price = close
            latest_price_source = "ohlcv" if close is not None else "unknown"
            latest_price_raw_field = "close" if close is not None else None
            latest_price_date = ohlcv_date
            price_source_warning = "Quote does not provide a reliable latest price field; latest price uses OHLCV close."
        if latest_price_source == "ohlcv" and provider_meta.get("actual_source") == VN_SOURCE_SSI:
            latest_price_source = SSI_DAILY_OHLC_SOURCE
            price_source_warning = "Quote does not provide a reliable latest price field; latest price uses SSI DailyOhlc close."
        corporate_action = build_corporate_action_reference(
            previous_close=prev_close,
            current_price=latest_price,
        )
        intraday_payload = self._disabled_intraday_payload(intraday_timeframe)
        if include_intraday:
            intraday_key = _cache_key(
                "intraday_ohlcv",
                symbol,
                provider=self.config.intraday_data_provider,
                timeframe=intraday_timeframe,
                limit=intraday_limit,
                enabled=self.config.ssi_intraday_enabled,
            )
            intraday_result = _read_cache(
                intraday_key,
                "intraday_ohlcv",
                lambda: self._load_ssi_intraday_payload(symbol, intraday_timeframe, intraday_limit),
                force_refresh=force_refresh,
            )
            intraday_payload = intraday_result["value"]
            intraday_payload = self._validate_intraday_freshness(
                intraday_payload,
                daily_price_date=latest_price_date or ohlcv_date,
            )
            cache_status["intraday_cache"] = intraday_result["status"]
            cache_last_fetched_at["intraday_ohlcv"] = _iso(intraday_result["entry"].fetched_at)
            cache_next_refresh_at["intraday_ohlcv"] = _iso(intraday_result["entry"].expires_at)
            if intraday_result["error"]:
                cache_errors["intraday_ohlcv"] = intraday_result["error"]
        realtime_payload = self._disabled_realtime_payload(symbol)
        realtime_key = _cache_key(
            "realtime_snapshot",
            symbol,
            provider=self.config.realtime_data_provider,
            enabled=self.config.ssi_realtime_enabled,
            streaming_enabled=self.config.ssi_streaming_realtime_enabled,
        )
        realtime_result = _read_cache(
            realtime_key,
            "realtime_snapshot",
            lambda: self._load_ssi_realtime_payload(symbol),
            force_refresh=force_refresh,
        )
        realtime_payload = dict(realtime_result["value"])
        realtime_status_payload = dict(realtime_payload.get("realtime_status") or {})
        realtime_diagnostics = _live_failure_diagnostics(realtime_status_payload.pop("diagnostics", {}))
        realtime_payload["realtime_status"] = realtime_status_payload
        cache_status["realtime_cache"] = realtime_result["status"]
        cache_last_fetched_at["realtime_snapshot"] = _iso(realtime_result["entry"].fetched_at)
        cache_next_refresh_at["realtime_snapshot"] = _iso(realtime_result["entry"].expires_at)
        if realtime_result["error"]:
            cache_errors["realtime_snapshot"] = realtime_result["error"]

        trade_tape_payload = self._disabled_trade_tape_payload(symbol)
        trade_tape_key = _cache_key(
            "trade_tape",
            symbol,
            provider=self.config.trade_tape_provider,
            enabled=self.config.ssi_trade_tape_enabled,
            limit=100,
        )
        trade_tape_result = _read_cache(
            trade_tape_key,
            "trade_tape",
            lambda: self._load_ssi_trade_tape_payload(symbol, limit=100),
            force_refresh=force_refresh,
        )
        trade_tape_payload = dict(trade_tape_result["value"])
        trade_tape_status_payload = dict(trade_tape_payload.get("trade_tape_status") or {})
        trade_tape_diagnostics = _live_failure_diagnostics(trade_tape_status_payload.pop("diagnostics", {}))
        trade_tape_payload["trade_tape_status"] = trade_tape_status_payload
        cache_status["trade_tape_cache"] = trade_tape_result["status"]
        cache_last_fetched_at["trade_tape"] = _iso(trade_tape_result["entry"].fetched_at)
        cache_next_refresh_at["trade_tape"] = _iso(trade_tape_result["entry"].expires_at)
        if trade_tape_result["error"]:
            cache_errors["trade_tape"] = trade_tape_result["error"]
        validation = validate_vietnam_row(latest, foreign)
        indicators = calculate_vietnam_indicators(
            df,
            foreign,
            foreign_history,
            reference_price=_safe_float((ssi_daily_stock_price or {}).get("reference_price")),
        )
        candle_status = "unknown"
        final_close_status = "unknown"
        adjusted_price_status = price_adjustment_status
        status_details = derive_neutral_status_details(
            indicators,
            change_pct,
            latest_price=latest_price,
            final_close_status=final_close_status,
            candle_status=candle_status,
            adjusted_price_status=adjusted_price_status,
            foreign_date_match=foreign_date_match,
            foreign_net_date=foreign_net_date,
            foreign_net_unit=foreign_net_unit,
            foreign_net=foreign_net,
            rows_loaded=len(df),
        )
        status_labels = [detail["label"] for detail in status_details]
        news: List[Dict[str, Any]] = []

        warnings: List[str] = []
        if ohlcv_result["status"] == "stale" or "stale" in cache_status.values():
            warnings.append(STALE_CACHE_WARNING)
        warnings.extend(validation["errors"])
        warnings.extend(f"Missing {field}; dashboard value shown as '-'." for field in validation["missing_fields"])
        if foreign_date_match == "mismatched" and not ssi_daily_stock_price_available:
            warnings.append("Foreign net date does not match OHLCV date.")
        if foreign_date_match != "matched" and not ssi_daily_stock_price_available:
            warnings.append("Foreign net is not confirmed as same-day flow.")
        if price_source_warning:
            warnings.append(price_source_warning)
        warnings.append("Final close status is unknown; daily candle may still be in progress.")
        if price_adjustment_status == "unknown":
            warnings.append("Adjusted/unadjusted price status is unknown.")
        if indicators.get("rsi14_wilder") is None:
            warnings.append("RSI14 requires at least 15 close prices; value is unavailable for this row.")
        warnings.append("Indicators are based on a daily candle whose final status is unknown.")
        if ex_dividend_warning:
            warnings.append("Provider row indicates adjusted or ex-dividend data; compare explicit corporate-action data before interpreting the gap.")
        if limit_state["near_limit"]:
            warnings.append("Latest close is within 0.5% of the exchange daily price limit band.")
        if foreign_net is None:
            if strict_daily_stock_price:
                warnings.append("Foreign trading signal is unavailable from SSI DailyStockPrice.")
            else:
                warnings.append("Foreign trading signal is unavailable.")
        if include_intraday:
            intraday_status = str((intraday_payload.get("intraday_status") or {}).get("status") or "")
            intraday_message = (intraday_payload.get("intraday_status") or {}).get("message")
            if intraday_status == "ok":
                warnings.append(VN_INTRADAY_WARNING)
            elif intraday_message:
                warnings.append(str(intraday_message))

        row_payload = {
            "ticker": symbol,
            "status": "ok",
            "reason": None,
            "name": company_name,
            "company_name": company_name,
            "entity": normalize_vn_symbol(symbol),
            "exchange": exchange,
            "market": symbol_metadata.get("market"),
            "security_type": symbol_metadata.get("security_type"),
            "industry": symbol_metadata.get("industry"),
            "sector": symbol_metadata.get("sector"),
            "metadata_source": metadata_source,
            "symbol_metadata": symbol_metadata,
            "issuer": symbol_metadata.get("issuer"),
            "lot_size": symbol_metadata.get("lot_size"),
            "listed_shares": symbol_metadata.get("listed_shares"),
            "listed_date": symbol_metadata.get("listed_date"),
            "market_index": _last_value(df, "market_index"),
            "source": source,
            "primary_source": provider_meta.get("primary_source"),
            "actual_source": provider_meta.get("actual_source"),
            "fallback_used": False,
            "fallback_reason": None,
            "reference_source": reference_source,
            "foreign_flow_source": foreign_flow_source,
            "rows_loaded": len(df),
            "date": latest.get("date").strftime("%Y-%m-%d") if hasattr(latest.get("date"), "strftime") else str(latest.get("date")),
            "latest_price": latest_price,
            "latest_price_source": latest_price_source,
            "latest_price_raw_field": latest_price_raw_field,
            "latest_price_date": latest_price_date,
            "quote_price_date": quote_price_date,
            "quote_price_raw_field": str(quote_price_raw_field) if quote_price_raw_field else None,
            "price_source_warning": price_source_warning,
            "ohlcv_close": close,
            "daily_close": close,
            "price_date": latest_price_date,
            "ohlcv_date": ohlcv_date,
            "daily_stock_price_date": (ssi_daily_stock_price or {}).get("date"),
            "daily_stock_price_date_match": (ssi_daily_stock_price or {}).get("date_match"),
            "daily_stock_price_staleness_reason": (ssi_daily_stock_price or {}).get("staleness_reason"),
            "quote_date": quote_date,
            "foreign_net_date": foreign_net_date,
            "foreign_date_match": foreign_date_match,
            "candle_status": candle_status,
            "final_close_status": final_close_status,
            "price_adjustment_status": price_adjustment_status,
            "adjusted_price_status": adjusted_price_status,
            "corporate_action": corporate_action,
            "open": _safe_float(latest.get("open")),
            "high": _safe_float(latest.get("high")),
            "low": _safe_float(latest.get("low")),
            "close": close,
            "previous_close": prev_close,
            "change_pct": round(change_pct, 2) if change_pct is not None else None,
            "volume": _safe_float(latest.get("volume")),
            "amount": _safe_float(latest.get("amount")),
            "liquidity": liquidity,
            "price_limit": limit_state,
            "daily_stock_price": ssi_daily_stock_price or {},
            "ssi_reference_price": _safe_float((ssi_daily_stock_price or {}).get("reference_price")),
            "ssi_ceiling_price": _safe_float((ssi_daily_stock_price or {}).get("ceiling_price")),
            "ssi_floor_price": _safe_float((ssi_daily_stock_price or {}).get("floor_price")),
            "ssi_adjusted_close": _safe_float((ssi_daily_stock_price or {}).get("adjusted_close")),
            "ssi_foreign_net_volume": _safe_float((ssi_daily_stock_price or {}).get("foreign_net_volume")),
            "ssi_foreign_net_value": _safe_float((ssi_daily_stock_price or {}).get("foreign_net_value")),
            "ssi_matched_volume": _safe_float((ssi_daily_stock_price or {}).get("matched_volume")),
            "ssi_matched_value": _safe_float((ssi_daily_stock_price or {}).get("matched_value")),
            "ssi_put_through_volume": _safe_float((ssi_daily_stock_price or {}).get("put_through_volume")),
            "ssi_put_through_value": _safe_float((ssi_daily_stock_price or {}).get("put_through_value")),
            "foreign": {
                "buy": _safe_float(foreign.get("buy")),
                "sell": _safe_float(foreign.get("sell")),
                "net": foreign_net,
                "buy_value": _safe_float((ssi_daily_stock_price or {}).get("foreign_buy_value")),
                "sell_value": _safe_float((ssi_daily_stock_price or {}).get("foreign_sell_value")),
                "net_value": _safe_float((ssi_daily_stock_price or {}).get("foreign_net_value")),
                "source": foreign_flow_source,
                "status": foreign.get("status"),
                "net_unit": foreign_net_unit,
                "value_unit": foreign.get("value_unit"),
                "date": foreign_net_date,
                "date_match": foreign_date_match,
                "buy_raw_field": foreign_buy_raw_field,
                "sell_raw_field": foreign_sell_raw_field,
                "signal": "foreign_net_positive" if (foreign_net or 0) > 0 else "foreign_net_negative" if (foreign_net or 0) < 0 else "neutral_or_unavailable",
            },
            "foreign_net_unit": foreign_net_unit,
            "foreign_buy_raw_field": foreign_buy_raw_field,
            "foreign_sell_raw_field": foreign_sell_raw_field,
            "indicators": indicators,
            "status_labels": status_labels,
            "status_details": status_details,
            "validation": validation,
            "trend": {},
            "warnings": warnings,
            "news": news,
            "news_status": self._news_status_block(),
            **intraday_payload,
            **realtime_payload,
            **trade_tape_payload,
            "diagnostics": {
                "realtime": realtime_diagnostics,
                "trade_tape": trade_tape_diagnostics,
            },
            "cache_status": cache_status,
            "cache_last_fetched_at": cache_last_fetched_at,
            "cache_next_refresh_at": cache_next_refresh_at,
            "cache_errors": cache_errors,
        }
        row_payload["data_quality_summary"] = build_vietnam_data_quality_summary(row_payload)
        return row_payload
