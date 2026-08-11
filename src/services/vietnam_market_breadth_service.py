"""Session-aligned VN30 market breadth derived only from SSI DailyOhlc."""

from __future__ import annotations

import math
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from src.services.vietnam_market_service import (
    SSI_INDEX_COMPONENTS_SOURCE,
    VN_SOURCE_SSI,
    VietnamMarketService,
    calculate_vietnam_indicators,
)


VN30_BREADTH_INDEX_CODE = "VN30"
VN30_BREADTH_EXPECTED_MEMBERS = 30
VN30_BREADTH_HISTORY_LIMIT = 55
VN30_BREADTH_LOOKBACK_DAYS = 120
VN30_BREADTH_MAX_WORKERS = 4


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _finite_positive(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _safe_date(value: Any) -> Optional[str]:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.strftime("%Y-%m-%d")


def normalize_vn30_members(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize current provider membership without inventing constituents."""
    normalized: List[str] = []
    seen = set()
    duplicates: List[str] = []
    invalid_count = 0
    for row in rows:
        symbol = str((row or {}).get("symbol") or "").strip().upper()
        if not symbol or not symbol.isalnum() or len(symbol) > 10:
            invalid_count += 1
            continue
        if symbol in seen:
            duplicates.append(symbol)
            continue
        seen.add(symbol)
        normalized.append(symbol)
    return {
        "symbols": sorted(normalized),
        "duplicate_symbols": sorted(set(duplicates)),
        "duplicate_count": len(duplicates),
        "invalid_count": invalid_count,
    }


def _normalize_history(dataframe: Any) -> pd.DataFrame:
    if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
        return pd.DataFrame(columns=["date", "close"])
    if "date" not in dataframe.columns or "close" not in dataframe.columns:
        return pd.DataFrame(columns=["date", "close"])
    normalized = dataframe.copy()
    normalized["date"] = normalized["date"].map(_safe_date)
    normalized = normalized[normalized["date"].notna()].drop_duplicates("date", keep="last")
    return normalized.sort_values("date").reset_index(drop=True)


def _canonical_session(histories: Dict[str, Dict[str, Any]]) -> Optional[str]:
    latest_dates = []
    for payload in histories.values():
        frame = _normalize_history(payload.get("dataframe"))
        if not frame.empty:
            latest_dates.append(str(frame.iloc[-1]["date"]))
    if not latest_dates:
        return None
    counts = Counter(latest_dates)
    highest_frequency = max(counts.values())
    return max(date for date, count in counts.items() if count == highest_frequency)


def calculate_vn30_breadth(
    symbols: List[str],
    histories: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Classify members on one modal latest provider session and aggregate coverage."""
    canonical_session = _canonical_session(histories)
    items: List[Dict[str, Any]] = []
    missing_symbols: List[str] = []
    mismatch_symbols: List[str] = []
    advances = declines = unchanged = 0
    above_ma20 = not_above_ma20 = 0
    above_ma50 = not_above_ma50 = 0
    observed_count = aligned_count = 0

    for symbol in symbols:
        history = histories.get(symbol) or {}
        frame = _normalize_history(history.get("dataframe"))
        reasons: List[str] = []
        latest_date = str(frame.iloc[-1]["date"]) if not frame.empty else None
        observed = not frame.empty
        if observed:
            observed_count += 1
        aligned = bool(canonical_session and latest_date == canonical_session)
        if observed and not aligned:
            mismatch_symbols.append(symbol)
            reasons.append("session_mismatch")
        if aligned:
            aligned_count += 1

        current_close = _finite_positive(frame.iloc[-1]["close"]) if aligned else None
        previous_close = None
        if aligned and len(frame) > 1:
            for value in reversed(frame.iloc[:-1]["close"].tolist()):
                previous_close = _finite_positive(value)
                if previous_close is not None:
                    break
        if not observed:
            reasons.append("daily_ohlcv_missing")
        elif aligned and current_close is None:
            reasons.append("current_close_missing")
        if aligned and previous_close is None:
            reasons.append("previous_close_missing")

        direction = None
        if current_close is not None and previous_close is not None:
            if current_close > previous_close:
                direction = "advance"
                advances += 1
            elif current_close < previous_close:
                direction = "decline"
                declines += 1
            else:
                direction = "unchanged"
                unchanged += 1

        indicators = calculate_vietnam_indicators(frame) if aligned and not frame.empty else {}
        ma20 = _finite_positive(indicators.get("ma20"))
        ma50 = _finite_positive(indicators.get("ma50"))
        above20 = current_close > ma20 if current_close is not None and ma20 is not None else None
        above50 = current_close > ma50 if current_close is not None and ma50 is not None else None
        if above20 is True:
            above_ma20 += 1
        elif above20 is False:
            not_above_ma20 += 1
        else:
            reasons.append("ma20_unavailable")
        if above50 is True:
            above_ma50 += 1
        elif above50 is False:
            not_above_ma50 += 1
        else:
            reasons.append("ma50_unavailable")

        if not aligned or current_close is None:
            missing_symbols.append(symbol)
        items.append(
            {
                "symbol": symbol,
                "latest_date": latest_date,
                "session_aligned": aligned,
                "current_close": current_close,
                "previous_close": previous_close,
                "direction": direction,
                "ma20": ma20,
                "above_ma20": above20,
                "ma50": ma50,
                "above_ma50": above50,
                "reasons": list(dict.fromkeys(reasons)),
            }
        )

    direction_usable = advances + declines + unchanged
    ma20_usable = above_ma20 + not_above_ma20
    ma50_usable = above_ma50 + not_above_ma50
    return {
        "provider_session_date": canonical_session,
        "direction": {
            "advances": advances,
            "declines": declines,
            "unchanged": unchanged,
            "usable_count": direction_usable,
        },
        "participation": {
            "ratio": ((advances + declines) / direction_usable) if direction_usable else None,
            "formula": "(advances + declines) / direction_usable_count",
        },
        "ma20": {
            "above_count": above_ma20,
            "not_above_count": not_above_ma20,
            "usable_count": ma20_usable,
            "percent_above": (above_ma20 / ma20_usable * 100) if ma20_usable else None,
            "formula": "close > SMA(close, 20)",
        },
        "ma50": {
            "above_count": above_ma50,
            "not_above_count": not_above_ma50,
            "usable_count": ma50_usable,
            "percent_above": (above_ma50 / ma50_usable * 100) if ma50_usable else None,
            "formula": "close > SMA(close, 50)",
        },
        "coverage": {
            "requested_count": VN30_BREADTH_EXPECTED_MEMBERS,
            "membership_count": len(symbols),
            "observed_count": observed_count,
            "aligned_count": aligned_count,
            "direction_usable_count": direction_usable,
            "ma20_usable_count": ma20_usable,
            "ma50_usable_count": ma50_usable,
            "missing_count": len(missing_symbols),
            "missing_symbols": missing_symbols,
            "session_mismatch_count": len(mismatch_symbols),
            "session_mismatch_symbols": mismatch_symbols,
        },
        "items": items,
    }


class VietnamMarketBreadthService:
    """Resolve current VN30 membership and its minimal DailyOhlc histories."""

    def __init__(self, market_service: Optional[VietnamMarketService] = None) -> None:
        self.market_service = market_service or VietnamMarketService()

    def build(self, index_code: str = VN30_BREADTH_INDEX_CODE, *, force_refresh: bool = False) -> Dict[str, Any]:
        started = time.perf_counter()
        normalized_index = str(index_code or "").strip().upper()
        if normalized_index != VN30_BREADTH_INDEX_CODE:
            raise ValueError("VN-BREADTH-1 supports index_code=VN30 only")

        membership_started = time.perf_counter()
        membership_payload = self.market_service.build_index_components(
            VN30_BREADTH_INDEX_CODE,
            force_refresh=force_refresh,
        )
        membership_ms = (time.perf_counter() - membership_started) * 1000
        normalized = normalize_vn30_members(membership_payload.get("rows") or [])
        symbols = normalized["symbols"]
        membership_ready = (
            membership_payload.get("status") == "ok"
            and len(symbols) == VN30_BREADTH_EXPECTED_MEMBERS
        )
        membership_diagnostics = dict(membership_payload.get("diagnostics") or {})
        membership = {
            "status": "ready" if membership_ready else "unavailable",
            "source": SSI_INDEX_COMPONENTS_SOURCE,
            "basis": "current_vn30_membership",
            "member_count": len(symbols),
            "symbols": symbols,
            "duplicate_count": normalized["duplicate_count"],
            "duplicate_symbols": normalized["duplicate_symbols"],
            "invalid_count": normalized["invalid_count"],
            "fetched_at": membership_diagnostics.get("cache_fetched_at"),
            "cache_status": membership_diagnostics.get("cache_status"),
            "reason": None if membership_ready else membership_payload.get("reason") or "Exact 30-member SSI VN30 membership unavailable.",
        }
        if not membership_ready:
            return {
                "status": "unavailable",
                "data_state": "unavailable",
                "usable": False,
                "index_code": VN30_BREADTH_INDEX_CODE,
                "source": VN_SOURCE_SSI,
                "source_endpoint": "securitiesSummary",
                "aggregation_basis": "current_vn30_membership_daily_ohlc",
                "historical_constituent_correct": False,
                "provider_session_date": None,
                "finality": "unknown",
                "freshness": "unavailable",
                "membership": membership,
                "direction": None,
                "participation": None,
                "ma20": None,
                "ma50": None,
                "coverage": {
                    "requested_count": VN30_BREADTH_EXPECTED_MEMBERS,
                    "membership_count": len(symbols),
                    "observed_count": 0,
                    "aligned_count": 0,
                    "direction_usable_count": 0,
                    "ma20_usable_count": 0,
                    "ma50_usable_count": 0,
                    "missing_count": VN30_BREADTH_EXPECTED_MEMBERS,
                    "missing_symbols": [],
                    "session_mismatch_count": 0,
                    "session_mismatch_symbols": [],
                },
                "items": [],
                "timing": {
                    "membership_ms": round(membership_ms, 2),
                    "daily_ohlc_ms": 0.0,
                    "calculation_ms": 0.0,
                    "serialization_ms": 0.0,
                    "total_ms": round((time.perf_counter() - started) * 1000, 2),
                },
                "diagnostics": {
                    "history_limit": VN30_BREADTH_HISTORY_LIMIT,
                    "max_concurrency": VN30_BREADTH_MAX_WORKERS,
                    "actual_concurrency": 0,
                    "provider_call_count": 0,
                    "cache_hit_count": 0,
                    "cache_miss_count": 0,
                    "fallback_used": False,
                },
                "fetched_at": _iso_now(),
            }

        histories: Dict[str, Dict[str, Any]] = {}
        daily_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=VN30_BREADTH_MAX_WORKERS) as executor:
            futures = {
                executor.submit(
                    self.market_service.read_daily_ohlcv_history,
                    symbol,
                    limit=VN30_BREADTH_HISTORY_LIMIT,
                    lookback_days=VN30_BREADTH_LOOKBACK_DAYS,
                    force_refresh=force_refresh,
                ): symbol
                for symbol in symbols
            }
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    histories[symbol] = future.result()
                except Exception as exc:  # per-member provider failures stay partial
                    histories[symbol] = {
                        "symbol": symbol,
                        "status": "unavailable",
                        "dataframe": pd.DataFrame(),
                        "cache_status": "error",
                        "cache_error": type(exc).__name__,
                        "provider_meta": {},
                    }
        daily_ms = (time.perf_counter() - daily_started) * 1000

        calculation_started = time.perf_counter()
        aggregate = calculate_vn30_breadth(symbols, histories)
        calculation_ms = (time.perf_counter() - calculation_started) * 1000
        cache_statuses = [str(payload.get("cache_status") or "error") for payload in histories.values()]
        provider_calls = sum(status != "hit" for status in cache_statuses)
        stale_used = any(status == "stale" for status in cache_statuses)
        provider_freshness = [
            str(((payload.get("provider_meta") or {}).get("diagnostics") or {}).get("freshness_status") or "unknown")
            for payload in histories.values()
        ]
        freshness = "stale" if stale_used or "stale" in provider_freshness else "fresh" if provider_freshness and all(value == "fresh" for value in provider_freshness) else "partial"
        canonical_session = aggregate["provider_session_date"]
        latest_completed_sessions = [
            _safe_date(((payload.get("provider_meta") or {}).get("diagnostics") or {}).get("latest_completed_session"))
            for payload in histories.values()
        ]
        completed_reference = max((value for value in latest_completed_sessions if value), default=None)
        finality = (
            "completed_daily"
            if canonical_session and completed_reference and canonical_session <= completed_reference
            else "provisional_daily"
            if canonical_session
            else "unknown"
        )
        complete = all(
            aggregate["coverage"][field] == VN30_BREADTH_EXPECTED_MEMBERS
            for field in ("aligned_count", "direction_usable_count", "ma20_usable_count", "ma50_usable_count")
        )
        usable = any(
            aggregate["coverage"][field] > 0
            for field in ("direction_usable_count", "ma20_usable_count", "ma50_usable_count")
        )
        status = "ready" if complete else "partial" if usable else "unavailable"
        serialized_started = time.perf_counter()
        response = {
            "status": status,
            "data_state": status,
            "usable": usable,
            "index_code": VN30_BREADTH_INDEX_CODE,
            "source": VN_SOURCE_SSI,
            "source_endpoint": "securitiesSummary",
            "aggregation_basis": "current_vn30_membership_daily_ohlc",
            "historical_constituent_correct": False,
            "provider_session_date": canonical_session,
            "finality": finality,
            "freshness": freshness,
            "membership": membership,
            **aggregate,
            "timing": {
                "membership_ms": round(membership_ms, 2),
                "daily_ohlc_ms": round(daily_ms, 2),
                "calculation_ms": round(calculation_ms, 2),
                "serialization_ms": 0.0,
                "total_ms": 0.0,
            },
            "diagnostics": {
                "history_limit": VN30_BREADTH_HISTORY_LIMIT,
                "lookback_days": VN30_BREADTH_LOOKBACK_DAYS,
                "canonical_session_method": "modal_latest_provider_session_tie_latest",
                "max_concurrency": VN30_BREADTH_MAX_WORKERS,
                "actual_concurrency": min(VN30_BREADTH_MAX_WORKERS, len(symbols)),
                "provider_call_count": provider_calls,
                "cache_hit_count": cache_statuses.count("hit"),
                "cache_miss_count": provider_calls,
                "stale_cache_used_count": cache_statuses.count("stale"),
                "fallback_used": False,
                "full_watchlist_hydration_used": False,
            },
            "fetched_at": _iso_now(),
        }
        serialization_ms = (time.perf_counter() - serialized_started) * 1000
        response["timing"]["serialization_ms"] = round(serialization_ms, 2)
        response["timing"]["total_ms"] = round((time.perf_counter() - started) * 1000, 2)
        return response

