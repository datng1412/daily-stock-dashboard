# -*- coding: utf-8 -*-
"""Vietnam watchlist dashboard service."""

from __future__ import annotations

import math
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from data_provider.base import DataFetcherManager
from data_provider.mozyfin_fetcher import (
    VN_WATCHLIST,
    get_vn_exchange,
    get_vn_price_limit_pct,
    normalize_vn_symbol,
    vn_ticker,
)


LIQUIDITY_TARGET_AVG_VOLUME = 1_000_000
VN_CACHE_TTL_SECONDS = {
    "ohlcv": 300,
    # Quote includes foreign flow and may include latest price in future Mozyfin outputs.
    # Keep at 60s for now; if quote becomes the live price source, 15-30s can be evaluated later.
    "quote": 60,
    "intraday_ohlcv": 60,
    "news": 1800,
}
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
    "intraday_1h_price": "VND",
    "intraday_1h_volume": "shares",
}
logger = logging.getLogger(__name__)


@dataclass
class _CacheEntry:
    value: Any
    fetched_at: datetime
    expires_at: datetime


_VN_CACHE: Dict[Tuple[Any, ...], _CacheEntry] = {}
_VN_CACHE_LOCK = RLock()


def clear_vietnam_cache() -> None:
    """Clear process-local Vietnam cache. Intended for tests and manual diagnostics."""
    with _VN_CACHE_LOCK:
        _VN_CACHE.clear()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _cache_key(data_type: str, symbol: str, **params: Any) -> Tuple[Any, ...]:
    normalized_params = tuple(sorted((key, str(value)) for key, value in params.items()))
    return ("VN", data_type, vn_ticker(symbol), *normalized_params)


def _get_cache_entry(key: Tuple[Any, ...]) -> Optional[_CacheEntry]:
    with _VN_CACHE_LOCK:
        return _VN_CACHE.get(key)


def _set_cache_entry(key: Tuple[Any, ...], value: Any, ttl_seconds: int) -> _CacheEntry:
    now = _utc_now()
    entry = _CacheEntry(value=value, fetched_at=now, expires_at=now + timedelta(seconds=ttl_seconds))
    with _VN_CACHE_LOCK:
        _VN_CACHE[key] = entry
    return entry


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
        return {"value": entry.value, "status": "hit", "entry": entry, "error": None}

    try:
        value = fetch()
        refreshed = _set_cache_entry(key, value, ttl_seconds)
        if force_refresh:
            status = "refresh"
        elif entry:
            status = "refresh"
        else:
            status = "miss"
        return {"value": value, "status": status, "entry": refreshed, "error": None}
    except Exception as exc:
        if entry is not None:
            return {"value": entry.value, "status": "stale", "entry": entry, "error": str(exc)}
        raise


@dataclass(frozen=True)
class VietnamDashboardConfig:
    liquidity_target_avg_volume: int = LIQUIDITY_TARGET_AVG_VOLUME
    history_days: int = 90
    news_limit: int = 3
    include_intraday: bool = True
    intraday_timeframe: str = "1h"
    intraday_limit: int = 8


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


def _foreign_sum(df: pd.DataFrame, window: int) -> Optional[float]:
    if "foreign_net" not in df.columns:
        return None
    series = pd.to_numeric(df["foreign_net"], errors="coerce").dropna()
    if len(series) < window:
        return None
    return _safe_float(series.tail(window).sum())


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
            "cumulative_1h_volume": None,
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
    highs = [_safe_float(candle.get("high")) for candle in candles]
    lows = [_safe_float(candle.get("low")) for candle in candles]
    volumes = [_safe_float(candle.get("volume")) for candle in candles]
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
        "session_high_from_1h": _round_optional(max(value for value in highs if value is not None)) if any(value is not None for value in highs) else None,
        "session_low_from_1h": _round_optional(min(value for value in lows if value is not None)) if any(value is not None for value in lows) else None,
        "cumulative_1h_volume": _round_optional(sum(value for value in volumes if value is not None), 0) if any(value is not None for value in volumes) else None,
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


def calculate_vietnam_indicators(df: pd.DataFrame, foreign_latest: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
    }


class VietnamMarketService:
    def __init__(self, manager: Optional[DataFetcherManager] = None, config: Optional[VietnamDashboardConfig] = None):
        self.manager = manager or DataFetcherManager()
        self.config = config or VietnamDashboardConfig()

    def build_watchlist(
        self,
        tickers: Optional[Iterable[str]] = None,
        force_refresh: bool = False,
        include_intraday: Optional[bool] = None,
        intraday_timeframe: Optional[str] = None,
        intraday_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        symbols = [vn_ticker(t) for t in (tickers or VN_WATCHLIST) if vn_ticker(t)]
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
        symbols = [vn_ticker(t) for t in (tickers or VN_WATCHLIST) if vn_ticker(t)]
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
        df, source = ohlcv_entry.value
        if df is None or df.empty:
            return None
        df = df.sort_values("date").reset_index(drop=True)
        latest = df.iloc[-1]
        quote_key = _cache_key("quote", symbol, limit=1)
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
        foreign = quote_entry.value if quote_entry else {
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
        return {
            "source": _source_label(fixture_mode),
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
        ohlcv_key = _cache_key("ohlcv", symbol, timeframe="1d", limit=260, days=self.config.history_days)
        ohlcv_result = _read_cache(
            ohlcv_key,
            "ohlcv",
            lambda: self.manager.get_daily_data(normalize_vn_symbol(symbol), days=self.config.history_days),
            force_refresh=force_refresh,
        )
        df, source = ohlcv_result["value"]
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
        if df is None or df.empty:
            return {
                "ticker": symbol,
                "error": "no_data",
                "source": source,
                "rows_loaded": 0,
                "validation": {
                    "valid": False,
                    "trading_date": None,
                    "missing_fields": ["date", "close", "volume", "foreign_net"],
                    "errors": ["No OHLCV rows were returned."],
                },
                "indicators": {},
                "status_labels": ["Watch"],
                "status_details": [
                    _status_detail("Watch", "info", "No OHLCV rows were returned for rule evaluation.", {})
                ],
                "warnings": ["No OHLCV rows were returned."],
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
        exchange = str(_last_value(df, "exchange") or get_vn_exchange(symbol))
        ex_dividend_warning = bool(_last_value(df, "ex_dividend_warning"))
        fetcher = self.manager._get_fetcher_by_name("MozyfinFetcher")  # dashboard-only helper path
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
        if fetcher and hasattr(fetcher, "get_foreign_trading"):
            try:
                quote_key = _cache_key("quote", symbol, limit=1)
                quote_result = _read_cache(
                    quote_key,
                    "quote",
                    lambda: fetcher.get_foreign_trading(symbol),
                    force_refresh=force_refresh,
                )
                foreign = quote_result["value"]
                cache_status["quote_cache"] = quote_result["status"]
                cache_last_fetched_at["quote"] = _iso(quote_result["entry"].fetched_at)
                cache_next_refresh_at["quote"] = _iso(quote_result["entry"].expires_at)
                if quote_result["error"]:
                    cache_errors["quote"] = quote_result["error"]
            except Exception as exc:
                logger.debug("Foreign trading unavailable for %s: %s", symbol, exc)
                cache_status["quote_cache"] = "error"
                cache_errors["quote"] = str(exc)
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
        indicators = calculate_vietnam_indicators(df, foreign)
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
        if foreign_date_match == "mismatched":
            warnings.append("Foreign net date does not match OHLCV date.")
        if foreign_date_match != "matched":
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
            warnings.append("Foreign trading signal is unavailable from the current Mozy output.")
        if include_intraday:
            warnings.append(VN_INTRADAY_WARNING)
            if cache_status.get("intraday_cache") == "error":
                warnings.append("Intraday 1H candles are unavailable for this ticker.")

        return {
            "ticker": symbol,
            "entity": normalize_vn_symbol(symbol),
            "exchange": exchange,
            "market_index": _last_value(df, "market_index"),
            "source": source,
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
            "price_date": latest_price_date,
            "ohlcv_date": ohlcv_date,
            "quote_date": quote_date,
            "foreign_net_date": foreign_net_date,
            "foreign_date_match": foreign_date_match,
            "candle_status": candle_status,
            "final_close_status": final_close_status,
            "price_adjustment_status": price_adjustment_status,
            "adjusted_price_status": adjusted_price_status,
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
            "foreign": {
                "buy": _safe_float(foreign.get("buy")),
                "sell": _safe_float(foreign.get("sell")),
                "net": foreign_net,
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
