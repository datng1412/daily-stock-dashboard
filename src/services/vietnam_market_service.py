# -*- coding: utf-8 -*-
"""Vietnam watchlist dashboard service."""

from __future__ import annotations

import math
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock, RLock
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

import pandas as pd

from data_provider.base import DataFetcherManager
from data_provider.mozyfin_fetcher import (
    VN_WATCHLIST,
    get_vn_exchange,
    get_vn_price_limit_pct,
    normalize_vn_symbol,
    vn_ticker,
)
from data_provider.ssi_fastconnect_fetcher import SsiFastConnectFetcher
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
VN_CHART_RANGES = {
    "1M": 31,
    "3M": 93,
    "6M": 186,
    "1Y": 366,
}
VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
VN_CACHE_TTL_SECONDS = {
    "ohlcv": 300,
    # Quote includes foreign flow and may include latest price in future Mozyfin outputs.
    # Keep at 60s for now; if quote becomes the live price source, 15-30s can be evaluated later.
    "quote": 60,
    "intraday_ohlcv": 60,
    "news": 1800,
    "symbol_metadata": 3600,
}
VN_PROVIDER_MOZYFIN = "mozyfin"
VN_PROVIDER_SSI = "ssi"
VN_PROVIDER_NONE = "none"
VN_SOURCE_MOZYFIN = "Mozyfin"
VN_SOURCE_SSI = "SSI"
SSI_DAILY_STOCK_PRICE_SOURCE = "SSI DailyStockPrice"
SSI_UNAVAILABLE_REASON = "SSI FastConnect unavailable"
VN_INTRADAY_WARNING = "Intraday 1H candle data is not a realtime matched quote."
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
    "foreign_net_5d": "row-specific",
    "foreign_net_20d": "row-specific",
    "foreign_net_5d_latest_available": "row-specific",
    "foreign_net_20d_latest_available": "row-specific",
    "intraday_1h_price": "VND",
    "intraday_1h_volume": "shares",
    "corporate_action_cash_dividend": "VND/share",
    "adjusted_reference_price": "VND",
}
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
) -> Dict[str, Any]:
    ttl_seconds = VN_CACHE_TTL_SECONDS[data_type]
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
    daily_data_provider: str = VN_PROVIDER_SSI
    chart_data_provider: str = VN_PROVIDER_SSI
    daily_stock_price_provider: str = VN_PROVIDER_SSI
    index_data_provider: str = VN_PROVIDER_SSI
    provider_comparison_enabled: bool = False


def _default_dashboard_config() -> VietnamDashboardConfig:
    app_config = get_config()
    return VietnamDashboardConfig(
        daily_data_provider=getattr(app_config, "vn_daily_data_provider", VN_PROVIDER_SSI),
        chart_data_provider=getattr(app_config, "vn_chart_data_provider", VN_PROVIDER_SSI),
        daily_stock_price_provider=getattr(app_config, "vn_daily_stock_price_provider", VN_PROVIDER_SSI),
        index_data_provider=getattr(app_config, "vn_index_data_provider", VN_PROVIDER_SSI),
        provider_comparison_enabled=getattr(app_config, "vn_provider_comparison_enabled", False),
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


def _is_fixture_mode(manager: DataFetcherManager) -> bool:
    fetcher = manager._get_fetcher_by_name("MozyfinFetcher")
    fixture_dir = getattr(fetcher, "fixture_dir", None)
    return bool((fixture_dir and fixture_dir.is_dir()) or os.getenv("MOZYFIN_FIXTURE_DIR"))


def _source_label(fixture_mode: bool) -> str:
    return "Mozyfin fixture" if fixture_mode else "Mozyfin live"


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
    rows = []
    for raw in df.tail(limit).to_dict("records"):
        rows.append(
            {
                "timestamp": raw.get("timestamp"),
                "date_time": raw.get("date_time") or raw.get("datetime") or raw.get("date"),
                "open": _safe_float(raw.get("open")),
                "high": _safe_float(raw.get("high")),
                "low": _safe_float(raw.get("low")),
                "close": _safe_float(raw.get("close")),
                "volume": _safe_float(raw.get("volume")),
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


def _latest_vn_session_candles(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    dated = [(candle, _intraday_candle_vn_date(candle)) for candle in candles]
    dates = [date for _, date in dated if date]
    if not dates:
        return []
    latest_date = max(dates)
    return [candle for candle, date in dated if date == latest_date]


def calculate_intraday_pulse(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate neutral intraday pulse metrics from available 1H candles."""
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

    return {
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


def derive_intraday_details(candles: List[Dict[str, Any]], pulse: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return neutral intraday condition labels with reasons."""
    details: List[Dict[str, Any]] = [
        _intraday_detail(
            "Not realtime quote",
            "caution",
            "Intraday 1H candle data is separate from a realtime matched quote.",
            {"source": "Mozyfin OHLCV", "is_realtime_quote": False},
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
                "Latest 1H candle close is above its open.",
                {"latest_1h_open": pulse.get("latest_1h_open"), "latest_1h_close": pulse.get("latest_1h_close")},
            )
        )
    elif direction == "down":
        details.append(
            _intraday_detail(
                "Intraday down",
                "info",
                "Latest 1H candle close is below its open.",
                {"latest_1h_open": pulse.get("latest_1h_open"), "latest_1h_close": pulse.get("latest_1h_close")},
            )
        )
    elif direction == "flat":
        details.append(
            _intraday_detail(
                "Intraday flat",
                "info",
                "Latest 1H candle close equals its open.",
                {"latest_1h_open": pulse.get("latest_1h_open"), "latest_1h_close": pulse.get("latest_1h_close")},
            )
        )

    volume_ratio = _safe_float(pulse.get("volume_vs_avg_1h"))
    if volume_ratio is not None and volume_ratio >= 1.5:
        details.append(
            _intraday_detail(
                "Intraday volume expansion",
                "info",
                "Latest 1H volume is at least 1.5 times the average of previous available 1H candles.",
                {"volume_vs_avg_1h": volume_ratio},
            )
        )

    range_percent = _safe_float(pulse.get("range_percent"))
    if range_percent is not None and range_percent >= 1.5:
        details.append(
            _intraday_detail(
                "Intraday wide range",
                "caution",
                "Latest 1H candle range is at least 1.5% of its open.",
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
    ):
        self.manager = manager or DataFetcherManager()
        self.config = config or _default_dashboard_config()
        self._ssi_fetcher = ssi_fetcher

    def _get_ssi_fetcher(self) -> SsiFastConnectFetcher:
        if self._ssi_fetcher is None:
            self._ssi_fetcher = SsiFastConnectFetcher()
        return self._ssi_fetcher

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
                except Exception:
                    return pd.DataFrame(), VN_SOURCE_SSI, {
                        "status": "unavailable",
                        "primary_source": primary_source,
                        "actual_source": VN_SOURCE_SSI,
                        "fallback_used": False,
                        "fallback_reason": None,
                        "unavailable_reason": SSI_UNAVAILABLE_REASON,
                    }

            df, source = self._load_mozyfin_daily_ohlcv(symbol, days)
            return df, source, {
                "status": "ok",
                "primary_source": VN_SOURCE_MOZYFIN,
                "actual_source": VN_SOURCE_MOZYFIN,
                "fallback_used": False,
                "fallback_reason": None,
                "unavailable_reason": None,
            }

        return load

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

    def _latest_ssi_daily_stock_price(self, symbol: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if self.config.daily_stock_price_provider != VN_PROVIDER_SSI:
            return None, None
        to_date = datetime.now(VN_TIMEZONE).date()
        from_date = to_date - timedelta(days=28)
        payload = self._get_ssi_fetcher().get_daily_stock_price(
            symbol,
            market=get_vn_exchange(symbol),
            from_date=from_date.isoformat(),
            to_date=to_date.isoformat(),
            limit=260,
        )
        if payload.get("status") != "ok":
            return None, self._safe_provider_reason(payload, SSI_UNAVAILABLE_REASON)
        rows = payload.get("rows") or []
        if not rows:
            return None, SSI_UNAVAILABLE_REASON
        return rows[-1], None

    @staticmethod
    def _normalize_ssi_symbol_metadata(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "ok",
            "symbol": str(row.get("symbol")).upper() if row.get("symbol") not in (None, "") else None,
            "exchange": row.get("exchange"),
            "market": row.get("market"),
            "security_type": row.get("security_type"),
            "name": row.get("name"),
            "name_en": row.get("name_en"),
            "issuer": row.get("issuer"),
            "lot_size": _safe_int(row.get("lot_size")),
            "listed_shares": _safe_int(row.get("listed_shares")),
            "listed_date": row.get("listed_date"),
            "source": VN_SOURCE_SSI,
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
        return rows[0] if len(rows) == 1 and isinstance(rows[0], dict) else None

    def _load_ssi_symbol_metadata(self, symbol: str) -> Dict[str, Any]:
        normalized_symbol = vn_ticker(symbol)
        market = get_vn_exchange(normalized_symbol)
        fetcher = self._get_ssi_fetcher()

        details_payload = fetcher.get_securities_details(symbol=normalized_symbol, market=market)
        row = self._matching_ssi_metadata_row(details_payload, normalized_symbol)
        if row:
            return self._normalize_ssi_symbol_metadata(row)

        securities_payload = fetcher.get_securities(market=market)
        row = self._matching_ssi_metadata_row(securities_payload, normalized_symbol)
        if row:
            return self._normalize_ssi_symbol_metadata(row)

        reason = self._safe_provider_reason(details_payload, SSI_UNAVAILABLE_REASON)
        if isinstance(securities_payload, dict) and securities_payload.get("status") != "ok":
            reason = self._safe_provider_reason(securities_payload, reason)
        return {
            "status": "unavailable",
            "source": VN_SOURCE_SSI,
            "reason": reason,
            "symbol": None,
            "exchange": None,
            "market": None,
            "security_type": None,
            "name": None,
            "name_en": None,
            "issuer": None,
            "lot_size": None,
            "listed_shares": None,
            "listed_date": None,
        }

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
        return {
            "status": "unavailable",
            "source": VN_SOURCE_SSI,
            "reason": SSI_UNAVAILABLE_REASON,
            "symbol": None,
            "exchange": None,
            "market": None,
            "security_type": None,
            "name": None,
            "name_en": None,
            "issuer": None,
            "lot_size": None,
            "listed_shares": None,
            "listed_date": None,
        }

    def _load_mozyfin_news(
        self,
        symbol: str,
        fetcher: Any,
        force_refresh: bool,
    ) -> Tuple[List[Dict[str, Any]], str, Optional[str], Optional[str], Optional[str]]:
        if not fetcher or not hasattr(fetcher, "get_news"):
            return [], "missing", None, None, None
        try:
            news_key = _cache_key("news", symbol, limit=self.config.news_limit)
            news_result = _read_cache(
                news_key,
                "news",
                lambda: fetcher.get_news(symbol, self.config.news_limit),
                force_refresh=force_refresh,
            )
            return (
                news_result["value"],
                news_result["status"],
                _iso(news_result["entry"].fetched_at),
                _iso(news_result["entry"].expires_at),
                news_result["error"],
            )
        except Exception as exc:
            logger.debug("News unavailable for %s: %s", symbol, exc)
            return [], "error", None, None, str(exc)

    @staticmethod
    def _apply_ssi_daily_stock_price_enrichment(
        symbol: str,
        latest_price_row: Dict[str, Any],
        limit_state: Dict[str, Any],
        foreign: Dict[str, Any],
        foreign_history: List[Dict[str, Any]],
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
        enriched_limit["status"] = "ok"
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
                "date": latest_price_row.get("date"),
                "net_unit": "shares",
                "buy_raw_field": "foreign_buy_volume",
                "sell_raw_field": "foreign_sell_volume",
                "latest_price": None,
                "price_raw_field": None,
                "price_date": None,
            }
        )
        history_row = {
            "buy": enriched_foreign.get("buy"),
            "sell": enriched_foreign.get("sell"),
            "net": enriched_foreign.get("net"),
            "date": enriched_foreign.get("date"),
            "net_unit": "shares",
            "buy_raw_field": "foreign_buy_volume",
            "sell_raw_field": "foreign_sell_volume",
        }
        enriched_history = [history_row] if history_row.get("date") else foreign_history
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
                        "source": "mozyfin-cli",
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
                        "warnings": ["Data unavailable for this ticker; check Mozyfin credentials, symbol, or fixture coverage."],
                        "news": [],
                        "intraday_timeframe": effective_intraday_timeframe,
                        "intraday_source": "Mozyfin OHLCV",
                        "intraday_is_realtime_quote": False,
                        "intraday_warning": VN_INTRADAY_WARNING,
                        "intraday_candles": [],
                        "intraday_pulse": calculate_intraday_pulse([]),
                        "intraday_labels": ["Not realtime quote", "Intraday data limited"],
                        "intraday_details": derive_intraday_details([], calculate_intraday_pulse([])),
                        "cache_status": {
                            "ohlcv_cache": "error",
                            "quote_cache": "error",
                            "intraday_cache": "error" if use_intraday else "missing",
                            "news_cache": "error",
                        },
                    }
                )
        health = self._build_health(rows, fixture_mode, refresh_time)
        cache_metadata = self._build_cache_metadata(rows)
        return {
            "market": "VN",
            "source": health["source"],
            "fixture_mode": fixture_mode,
            "last_refresh_time": refresh_time,
            "units": VN_DASHBOARD_UNITS,
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
                "intraday_1h_change": "latest_1h_close - latest_1h_open",
                "intraday_1h_change_percent": "(latest_1h_close - latest_1h_open) / latest_1h_open * 100",
                "intraday_range_percent": "(latest_1h_high - latest_1h_low) / latest_1h_open * 100",
                "intraday_volume_vs_avg_1h": "latest_1h_volume / average(previous available 1H candle volumes), when at least 2 previous candles exist",
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
        """Return VN corporate-action calendar/history shape when an explicit event source is unavailable."""
        symbols = normalize_vietnam_tickers(tickers)
        safe_months_back = max(1, min(int(months_back or 6), 24))
        return {
            "market": "VN",
            "status": "unavailable",
            "source": None,
            "last_checked_at": datetime.now(timezone.utc).isoformat(),
            "requested_tickers": symbols,
            "months_back": safe_months_back,
            "items": [],
            "error": "Corporate action calendar unavailable.",
            "error_detail": (
                "No verified Vietnam corporate-action event provider is configured. "
                "Events are not inferred from KBS reference price, price gaps, adjusted reference, or OHLCV changes."
            ),
        }

    def build_daily_index(
        self,
        index_code: str = "VNINDEX",
        limit: int = 260,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return strict SSI daily index rows for future market breadth cards."""
        normalized_index = str(index_code or "VNINDEX").strip().upper()
        payload = self._get_ssi_fetcher().get_daily_index(
            normalized_index,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )
        if payload.get("status") != "ok":
            return {
                "status": "unavailable",
                "source": VN_SOURCE_SSI,
                "reason": self._safe_provider_reason(payload),
                "index_code": normalized_index,
                "rows": [],
            }
        return payload

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
        quote_key = _cache_key("quote", symbol, limit=FOREIGN_HISTORY_LIMIT)
        quote_entry = _get_cache_entry(quote_key)
        intraday_key = _cache_key(
            "intraday_ohlcv",
            symbol,
            timeframe=self.config.intraday_timeframe,
            limit=self.config.intraday_limit,
        )
        intraday_entry = _get_cache_entry(intraday_key)
        news_key = _cache_key("news", symbol, limit=self.config.news_limit)
        news_entry = _get_cache_entry(news_key)
        quote_history = quote_entry.value if quote_entry and isinstance(quote_entry.value, list) else None
        foreign = _foreign_history_latest(quote_history) or {
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
                "quote_cache": "hit" if quote_entry and quote_entry.expires_at > _utc_now() else "stale" if quote_entry else "missing",
                "intraday_cache": "hit" if intraday_entry and intraday_entry.expires_at > _utc_now() else "stale" if intraday_entry else "missing",
                "news_cache": "hit" if news_entry and news_entry.expires_at > _utc_now() else "stale" if news_entry else "missing",
            },
            "cache_last_fetched_at": {
                "ohlcv": _iso(ohlcv_entry.fetched_at),
                "quote": _iso(quote_entry.fetched_at) if quote_entry else None,
                "intraday_ohlcv": _iso(intraday_entry.fetched_at) if intraday_entry else None,
                "news": _iso(news_entry.fetched_at) if news_entry else None,
            },
            "cache_next_refresh_at": {
                "ohlcv": _iso(ohlcv_entry.expires_at),
                "quote": _iso(quote_entry.expires_at) if quote_entry else None,
                "intraday_ohlcv": _iso(intraday_entry.expires_at) if intraday_entry else None,
                "news": _iso(news_entry.expires_at) if news_entry else None,
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
            "quote_cache": "missing",
            "intraday_cache": "missing",
            "news_cache": "missing",
        }
        cache_last_fetched_at = {
            "ohlcv": _iso(ohlcv_result["entry"].fetched_at),
            "quote": None,
            "intraday_ohlcv": None,
            "news": None,
        }
        cache_next_refresh_at = {
            "ohlcv": _iso(ohlcv_result["entry"].expires_at),
            "quote": None,
            "intraday_ohlcv": None,
            "news": None,
        }
        cache_errors = {}
        if ohlcv_result["error"]:
            cache_errors["ohlcv"] = ohlcv_result["error"]
        fetcher = self.manager._get_fetcher_by_name("MozyfinFetcher")  # Mozyfin remains news-only in strict SSI mode.
        symbol_metadata = self._ssi_symbol_metadata(symbol, force_refresh=force_refresh)
        metadata_source = symbol_metadata.get("source") if symbol_metadata.get("status") == "ok" else VN_SOURCE_SSI
        company_name = symbol_metadata.get("name") if symbol_metadata.get("status") == "ok" else None
        if df is None or df.empty:
            news, news_cache_status, news_fetched_at, news_next_refresh_at, news_error = self._load_mozyfin_news(
                symbol,
                fetcher,
                force_refresh,
            )
            cache_status["news_cache"] = news_cache_status
            cache_last_fetched_at["news"] = news_fetched_at
            cache_next_refresh_at["news"] = news_next_refresh_at
            if news_error:
                cache_errors["news"] = news_error
            unavailable_reason = provider_meta.get("unavailable_reason") or "No OHLCV rows were returned."
            return {
                "ticker": symbol,
                "status": "unavailable",
                "reason": unavailable_reason,
                "error": "ssi_unavailable" if provider_meta.get("primary_source") == VN_SOURCE_SSI else "no_data",
                "name": company_name,
                "company_name": company_name,
                "security_type": symbol_metadata.get("security_type"),
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
                "rows_loaded": 0,
                "validation": {
                    "valid": False,
                    "trading_date": None,
                    "missing_fields": ["date", "close", "volume", "foreign_net"],
                    "errors": [unavailable_reason],
                },
                "indicators": {},
                "status_labels": ["Watch"],
                "status_details": [
                    _status_detail("Watch", "info", "No OHLCV rows were returned for rule evaluation.", {})
                ],
                "warnings": [unavailable_reason],
                "news": news,
                "intraday_timeframe": intraday_timeframe,
                "intraday_source": "Mozyfin OHLCV",
                "intraday_is_realtime_quote": False,
                "intraday_warning": VN_INTRADAY_WARNING,
                "intraday_candles": [],
                "intraday_pulse": calculate_intraday_pulse([]),
                "intraday_labels": ["Not realtime quote", "Intraday data limited"],
                "intraday_details": derive_intraday_details([], calculate_intraday_pulse([])),
                "cache_status": cache_status,
                "cache_last_fetched_at": cache_last_fetched_at,
                "cache_next_refresh_at": cache_next_refresh_at,
                "cache_errors": cache_errors,
            }

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
        foreign_flow_source = SSI_DAILY_STOCK_PRICE_SOURCE if strict_daily_stock_price else "Mozyfin daily"
        ssi_daily_stock_price: Optional[Dict[str, Any]] = None
        ssi_daily_stock_price_reason: Optional[str] = None
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
                "net_unit": "shares",
                "buy_raw_field": None,
                "sell_raw_field": None,
                "latest_price": None,
                "price_raw_field": None,
                "price_date": None,
                "source": SSI_DAILY_STOCK_PRICE_SOURCE,
                "status": "unavailable",
            }
        elif fetcher and hasattr(fetcher, "get_foreign_trading"):
            try:
                quote_key = _cache_key("quote", symbol, limit=FOREIGN_HISTORY_LIMIT)
                quote_result = _read_cache(
                    quote_key,
                    "quote",
                    lambda: (
                        fetcher.get_foreign_trading_history(symbol, FOREIGN_HISTORY_LIMIT)
                        if hasattr(fetcher, "get_foreign_trading_history")
                        else [fetcher.get_foreign_trading(symbol)]
                    ),
                    force_refresh=force_refresh,
                )
                foreign_history = quote_result["value"] or []
                foreign = _foreign_history_latest(foreign_history) or foreign
                if foreign_history:
                    foreign_flow_source = "Mozyfin quote"
                cache_status["quote_cache"] = quote_result["status"]
                cache_last_fetched_at["quote"] = _iso(quote_result["entry"].fetched_at)
                cache_next_refresh_at["quote"] = _iso(quote_result["entry"].expires_at)
                if quote_result["error"]:
                    cache_errors["quote"] = quote_result["error"]
            except Exception as exc:
                logger.debug("Foreign trading unavailable for %s: %s", symbol, exc)
                cache_status["quote_cache"] = "error"
                cache_errors["quote"] = str(exc)
        ssi_daily_stock_price, ssi_daily_stock_price_reason = self._latest_ssi_daily_stock_price(symbol)
        if ssi_daily_stock_price:
            ssi_daily_stock_price = dict(ssi_daily_stock_price)
            ssi_daily_stock_price.setdefault("status", "ok")
            ssi_daily_stock_price.setdefault("source", VN_SOURCE_SSI)
            limit_state, foreign, foreign_history = self._apply_ssi_daily_stock_price_enrichment(
                symbol,
                ssi_daily_stock_price,
                limit_state,
                foreign,
                foreign_history,
            )
            reference_source = SSI_DAILY_STOCK_PRICE_SOURCE
            foreign_flow_source = SSI_DAILY_STOCK_PRICE_SOURCE
            limit_state["status"] = "ok"
            foreign["status"] = "ok"
            foreign["source"] = SSI_DAILY_STOCK_PRICE_SOURCE
        elif strict_daily_stock_price:
            ssi_daily_stock_price = {
                "status": "unavailable",
                "source": SSI_DAILY_STOCK_PRICE_SOURCE,
                "reason": ssi_daily_stock_price_reason or SSI_UNAVAILABLE_REASON,
            }
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
            latest_price_source = VN_SOURCE_SSI
            price_source_warning = "Quote does not provide a reliable latest price field; latest price uses SSI DailyOhlc close."
        corporate_action = build_corporate_action_reference(
            previous_close=prev_close,
            current_price=latest_price,
        )
        intraday_candles: List[Dict[str, Any]] = []
        if include_intraday and fetcher and hasattr(fetcher, "get_intraday_ohlcv"):
            try:
                intraday_key = _cache_key(
                    "intraday_ohlcv",
                    symbol,
                    timeframe=intraday_timeframe,
                    limit=intraday_limit,
                )
                intraday_result = _read_cache(
                    intraday_key,
                    "intraday_ohlcv",
                    lambda: fetcher.get_intraday_ohlcv(symbol, intraday_timeframe, intraday_limit),
                    force_refresh=force_refresh,
                )
                intraday_candles = normalize_intraday_candles(intraday_result["value"], intraday_limit)
                cache_status["intraday_cache"] = intraday_result["status"]
                cache_last_fetched_at["intraday_ohlcv"] = _iso(intraday_result["entry"].fetched_at)
                cache_next_refresh_at["intraday_ohlcv"] = _iso(intraday_result["entry"].expires_at)
                if intraday_result["error"]:
                    cache_errors["intraday_ohlcv"] = intraday_result["error"]
            except Exception as exc:
                logger.debug("Intraday OHLCV unavailable for %s: %s", symbol, exc)
                cache_status["intraday_cache"] = "error"
                cache_errors["intraday_ohlcv"] = str(exc)
        intraday_pulse = calculate_intraday_pulse(intraday_candles)
        intraday_details = derive_intraday_details(intraday_candles, intraday_pulse)
        intraday_labels = [detail["label"] for detail in intraday_details]
        validation = validate_vietnam_row(latest, foreign)
        indicators = calculate_vietnam_indicators(df, foreign, foreign_history)
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
        news = []
        if fetcher and hasattr(fetcher, "get_news"):
            try:
                news_key = _cache_key("news", symbol, limit=self.config.news_limit)
                news_result = _read_cache(
                    news_key,
                    "news",
                    lambda: fetcher.get_news(symbol, self.config.news_limit),
                    force_refresh=force_refresh,
                )
                news = news_result["value"]
                cache_status["news_cache"] = news_result["status"]
                cache_last_fetched_at["news"] = _iso(news_result["entry"].fetched_at)
                cache_next_refresh_at["news"] = _iso(news_result["entry"].expires_at)
                if news_result["error"]:
                    cache_errors["news"] = news_result["error"]
            except Exception as exc:
                logger.debug("News unavailable for %s: %s", symbol, exc)
                cache_status["news_cache"] = "error"
                cache_errors["news"] = str(exc)

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
            warnings.append("Mozy/fixture indicates adjusted or ex-dividend data; compare adjusted and raw prices before acting.")
        if limit_state["near_limit"]:
            warnings.append("Latest close is within 0.5% of the exchange daily price limit band.")
        if foreign_net is None:
            if strict_daily_stock_price:
                warnings.append("Foreign trading signal is unavailable from SSI DailyStockPrice.")
            else:
                warnings.append("Foreign trading signal is unavailable from the current Mozy output.")
        if include_intraday:
            warnings.append(VN_INTRADAY_WARNING)
            if cache_status.get("intraday_cache") == "error":
                warnings.append("Intraday 1H candles are unavailable for this ticker.")

        return {
            "ticker": symbol,
            "status": "ok",
            "reason": None,
            "name": company_name,
            "company_name": company_name,
            "entity": normalize_vn_symbol(symbol),
            "exchange": exchange,
            "market": symbol_metadata.get("market"),
            "security_type": symbol_metadata.get("security_type"),
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
            "intraday_timeframe": intraday_timeframe,
            "intraday_source": "Mozyfin OHLCV",
            "intraday_is_realtime_quote": False,
            "intraday_warning": VN_INTRADAY_WARNING,
            "intraday_candles": intraday_candles,
            "intraday_pulse": intraday_pulse,
            "intraday_labels": intraday_labels,
            "intraday_details": intraday_details,
            "cache_status": cache_status,
            "cache_last_fetched_at": cache_last_fetched_at,
            "cache_next_refresh_at": cache_next_refresh_at,
            "cache_errors": cache_errors,
        }
