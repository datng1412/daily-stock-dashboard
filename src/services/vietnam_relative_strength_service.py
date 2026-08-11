"""Transparent selected-stock performance versus SSI index and current ICB peers."""

from __future__ import annotations

import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from threading import Event, RLock
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

import pandas as pd

from src.services.vietnam_market_service import VietnamMarketService


RS_WINDOWS = (1, 5, 20)
RS_HISTORY_LIMIT = 55
RS_LOOKBACK_DAYS = 120
RS_MAX_CONCURRENCY = 4
RS_INDEX_CACHE_TTL_SECONDS = 300
RS_INDEX_NEGATIVE_CACHE_TTL_SECONDS = 60
RS_INDEX_CODES = ("VNINDEX", "VN30")

_INDEX_CACHE_LOCK = RLock()
_INDEX_CACHE: Dict[tuple[str, str], tuple[float, Dict[str, Any]]] = {}
_INDEX_INFLIGHT: Dict[tuple[str, str], Event] = {}


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


def normalize_close_history(dataframe: Any) -> Dict[str, float]:
    """Return sorted, deduplicated provider sessions with finite positive closes."""
    if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
        return {}
    if "date" not in dataframe.columns or "close" not in dataframe.columns:
        return {}
    rows: Dict[str, float] = {}
    for _, row in dataframe.iterrows():
        session = _safe_date(row.get("date"))
        close = _finite_positive(row.get("close"))
        if session and close is not None:
            rows[session] = close
    return dict(sorted(rows.items()))


def calculate_aligned_window(
    stock: Mapping[str, float],
    benchmark: Mapping[str, float],
    requested_sessions: int,
) -> Dict[str, Any]:
    """Calculate one exact mutually aligned provider-session return window."""
    common = sorted(set(stock).intersection(benchmark))
    required_points = requested_sessions + 1
    if len(common) < required_points:
        return {
            "requested_sessions": requested_sessions,
            "status": "unavailable",
            "complete": False,
            "start_session": None,
            "end_session": common[-1] if common else None,
            "stock_return_pct": None,
            "benchmark_return_pct": None,
            "relative_performance_pp": None,
            "aligned_session_count": len(common),
            "reason": "insufficient_aligned_provider_sessions",
        }
    selected = common[-required_points:]
    start_session, end_session = selected[0], selected[-1]
    stock_return = (stock[end_session] / stock[start_session] - 1) * 100
    benchmark_return = (benchmark[end_session] / benchmark[start_session] - 1) * 100
    return {
        "requested_sessions": requested_sessions,
        "status": "ready",
        "complete": True,
        "start_session": start_session,
        "end_session": end_session,
        "stock_return_pct": stock_return,
        "benchmark_return_pct": benchmark_return,
        "relative_performance_pp": stock_return - benchmark_return,
        "aligned_session_count": len(selected),
        "reason": None,
    }


def calculate_peer_window(
    stock: Mapping[str, float],
    peers: Mapping[str, Mapping[str, float]],
    requested_sessions: int,
) -> Dict[str, Any]:
    """Compare a stock with equal-weight peers on the stock's exact session pair."""
    stock_dates = sorted(stock)
    required_points = requested_sessions + 1
    if len(stock_dates) < required_points:
        return {
            "requested_sessions": requested_sessions,
            "status": "unavailable",
            "complete": False,
            "start_session": None,
            "end_session": stock_dates[-1] if stock_dates else None,
            "stock_return_pct": None,
            "benchmark_return_pct": None,
            "relative_performance_pp": None,
            "aligned_session_count": len(stock_dates),
            "requested_peer_count": len(peers),
            "usable_peer_count": 0,
            "missing_peers": sorted(peers),
            "reason": "insufficient_stock_provider_sessions",
        }
    selected = stock_dates[-required_points:]
    start_session, end_session = selected[0], selected[-1]
    peer_returns: List[float] = []
    usable_peers: List[str] = []
    missing_peers: List[str] = []
    for symbol, history in sorted(peers.items()):
        start = _finite_positive(history.get(start_session))
        end = _finite_positive(history.get(end_session))
        if start is None or end is None:
            missing_peers.append(symbol)
            continue
        peer_returns.append((end / start - 1) * 100)
        usable_peers.append(symbol)
    if not peer_returns:
        return {
            "requested_sessions": requested_sessions,
            "status": "unavailable",
            "complete": False,
            "start_session": start_session,
            "end_session": end_session,
            "stock_return_pct": None,
            "benchmark_return_pct": None,
            "relative_performance_pp": None,
            "aligned_session_count": len(selected),
            "requested_peer_count": len(peers),
            "usable_peer_count": 0,
            "missing_peers": missing_peers,
            "reason": "no_usable_current_vn30_icb_peers",
        }
    stock_return = (stock[end_session] / stock[start_session] - 1) * 100
    peer_return = sum(peer_returns) / len(peer_returns)
    complete = len(usable_peers) == len(peers)
    return {
        "requested_sessions": requested_sessions,
        "status": "ready" if complete else "partial",
        "complete": complete,
        "start_session": start_session,
        "end_session": end_session,
        "stock_return_pct": stock_return,
        "benchmark_return_pct": peer_return,
        "relative_performance_pp": stock_return - peer_return,
        "aligned_session_count": len(selected),
        "requested_peer_count": len(peers),
        "usable_peer_count": len(usable_peers),
        "missing_peers": missing_peers,
        "reason": None if complete else "peer_history_partial",
    }


def _normalize_index_point(result: Mapping[str, Any], code: str, session: str) -> Dict[str, Any]:
    rows = [row for row in result.get("rows") or [] if isinstance(row, Mapping)]
    matches = [
        row for row in rows
        if _safe_date(row.get("date")) == session
        and _finite_positive(row.get("index_value")) is not None
    ]
    if result.get("status") == "ok" and matches:
        return {
            "status": "ready",
            "index_code": code,
            "session": session,
            "index_value": _finite_positive(matches[-1].get("index_value")),
            "failure_class": None,
        }
    return {
        "status": "unavailable",
        "index_code": code,
        "session": session,
        "index_value": None,
        "failure_class": result.get("failure_class") or "provider_empty",
    }


def clear_relative_strength_index_cache() -> None:
    with _INDEX_CACHE_LOCK:
        _INDEX_CACHE.clear()
        _INDEX_INFLIGHT.clear()


class VietnamRelativeStrengthService:
    """Build one selected-ticker comparison without watchlist or frontend fan-out."""

    def __init__(
        self,
        market_service: Optional[VietnamMarketService] = None,
        *,
        index_reader: Optional[Callable[[str, str], Mapping[str, Any]]] = None,
    ) -> None:
        self.market_service = market_service or VietnamMarketService()
        self.index_reader = index_reader or self._provider_index_reader

    def _provider_index_reader(self, code: str, session: str) -> Mapping[str, Any]:
        return self.market_service._get_ssi_rest_provider().get_index_summary(
            code,
            index_code=code,
            trading_date=session,
        )

    def _read_index_point(self, code: str, session: str, force_refresh: bool) -> Dict[str, Any]:
        key = (code, session)
        now = time.monotonic()
        leader = False
        with _INDEX_CACHE_LOCK:
            cached = _INDEX_CACHE.get(key)
            if not force_refresh and cached and cached[0] > now:
                return {**cached[1], "cache_status": "hit", "provider_called": False}
            event = _INDEX_INFLIGHT.get(key)
            if event is None:
                event = Event()
                _INDEX_INFLIGHT[key] = event
                leader = True
        if not leader:
            event.wait(timeout=15)
            with _INDEX_CACHE_LOCK:
                cached = _INDEX_CACHE.get(key)
            if cached:
                return {**cached[1], "cache_status": "hit", "provider_called": False}
            return {
                "status": "unavailable",
                "index_code": code,
                "session": session,
                "index_value": None,
                "failure_class": "singleflight_timeout",
                "cache_status": "error",
                "provider_called": False,
            }
        try:
            point = _normalize_index_point(self.index_reader(code, session), code, session)
            ttl = RS_INDEX_CACHE_TTL_SECONDS if point["status"] == "ready" else RS_INDEX_NEGATIVE_CACHE_TTL_SECONDS
            with _INDEX_CACHE_LOCK:
                _INDEX_CACHE[key] = (time.monotonic() + ttl, point)
            return {**point, "cache_status": "refresh" if force_refresh else "miss", "provider_called": True}
        finally:
            with _INDEX_CACHE_LOCK:
                completed = _INDEX_INFLIGHT.pop(key, None)
                if completed:
                    completed.set()

    def build(self, ticker: str, *, force_refresh: bool = False) -> Dict[str, Any]:
        started = time.perf_counter()
        symbol = str(ticker or "").strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{2,10}", symbol):
            raise ValueError("Invalid Vietnam ticker")

        stock_payload = self.market_service.read_daily_ohlcv_history(
            symbol,
            limit=RS_HISTORY_LIMIT,
            lookback_days=RS_LOOKBACK_DAYS,
            force_refresh=force_refresh,
        )
        stock_history = normalize_close_history(stock_payload.get("dataframe"))
        stock_dates = sorted(stock_history)[-21:]

        membership_payload = self.market_service.build_index_components("VN30", force_refresh=force_refresh)
        rows = [row for row in membership_payload.get("rows") or [] if isinstance(row, Mapping)]
        classifications = {
            str(row.get("symbol") or "").strip().upper(): {
                "icb_code": str(row.get("icb_code") or "").strip(),
                "icb_name": str(row.get("icb_name") or row.get("industry") or "").strip(),
            }
            for row in rows
            if str(row.get("symbol") or "").strip()
        }
        selected_classification = classifications.get(symbol) or {}
        icb_code = selected_classification.get("icb_code") or None
        icb_name = selected_classification.get("icb_name") or None
        peer_symbols = sorted(
            candidate
            for candidate, classification in classifications.items()
            if candidate != symbol and icb_code and classification.get("icb_code") == icb_code
        )

        peer_payloads: Dict[str, Dict[str, Any]] = {}
        if peer_symbols:
            with ThreadPoolExecutor(max_workers=RS_MAX_CONCURRENCY) as executor:
                futures = {
                    executor.submit(
                        self.market_service.read_daily_ohlcv_history,
                        peer,
                        limit=RS_HISTORY_LIMIT,
                        lookback_days=RS_LOOKBACK_DAYS,
                        force_refresh=force_refresh,
                    ): peer
                    for peer in peer_symbols
                }
                for future in as_completed(futures):
                    peer = futures[future]
                    try:
                        peer_payloads[peer] = future.result()
                    except Exception as exc:
                        peer_payloads[peer] = {"cache_status": "error", "dataframe": pd.DataFrame(), "error": type(exc).__name__}
        peer_histories = {
            peer: normalize_close_history(payload.get("dataframe"))
            for peer, payload in peer_payloads.items()
        }

        index_points: Dict[str, Dict[str, float]] = {code: {} for code in RS_INDEX_CODES}
        index_results: List[Dict[str, Any]] = []
        if stock_dates:
            with ThreadPoolExecutor(max_workers=RS_MAX_CONCURRENCY) as executor:
                futures = {
                    executor.submit(self._read_index_point, code, session, force_refresh): (code, session)
                    for code in RS_INDEX_CODES
                    for session in stock_dates
                }
                for future in as_completed(futures):
                    code, session = futures[future]
                    try:
                        result = future.result()
                    except Exception as exc:
                        result = {
                            "status": "unavailable",
                            "index_code": code,
                            "session": session,
                            "index_value": None,
                            "failure_class": type(exc).__name__,
                            "cache_status": "error",
                            "provider_called": True,
                        }
                    index_results.append(result)
                    value = _finite_positive(result.get("index_value"))
                    if result.get("status") == "ready" and value is not None:
                        index_points[code][session] = value

        comparisons: Dict[str, Dict[str, Any]] = {}
        for code in RS_INDEX_CODES:
            windows = {
                f"{window}d": calculate_aligned_window(stock_history, index_points[code], window)
                for window in RS_WINDOWS
            }
            usable = any(window["status"] == "ready" for window in windows.values())
            complete = all(window["complete"] for window in windows.values())
            comparisons[code.lower()] = {
                "status": "ready" if complete else "partial" if usable else "unavailable",
                "usable": usable,
                "benchmark_code": code,
                "benchmark_name": code,
                "source": "SSI indexSummary",
                "source_endpoint": "/api/v3/data/indexSummary",
                "actual_field": "indexValue",
                "methodology": "provider_index_value_exact_aligned_sessions",
                "windows": windows,
            }

        peer_windows = {
            f"{window}d": calculate_peer_window(stock_history, peer_histories, window)
            for window in RS_WINDOWS
        }
        peer_usable = any(window["status"] in {"ready", "partial"} for window in peer_windows.values())
        peer_complete = bool(peer_symbols) and all(window["complete"] for window in peer_windows.values())
        comparisons["industry"] = {
            "status": "ready" if peer_complete else "partial" if peer_usable else "unavailable",
            "usable": peer_usable,
            "benchmark_code": icb_code,
            "benchmark_name": icb_name,
            "source": "SSI DailyOhlc + SSI ICB",
            "source_endpoint": "securitiesSummary + securitiesByBoard?index=VN30",
            "actual_field": "close",
            "methodology": "current_vn30_icb_equal_weight_peers_excluding_selected",
            "peer_member_count": len(peer_symbols),
            "peer_symbols": peer_symbols,
            "historical_constituent_correct": False,
            "official_sector_index_return": False,
            "windows": peer_windows,
        }

        usable = bool(stock_history) and any(item["usable"] for item in comparisons.values())
        complete = bool(stock_history) and all(item["status"] == "ready" for item in comparisons.values())
        status = "ready" if complete else "partial" if usable else "unavailable"
        history_payloads = [stock_payload, *peer_payloads.values()]
        cache_statuses = [str(payload.get("cache_status") or "error") for payload in history_payloads]
        index_provider_calls = sum(bool(item.get("provider_called")) for item in index_results)
        return {
            "status": status,
            "data_state": status,
            "usable": usable,
            "ticker": symbol,
            "stock_source": "SSI DailyOhlc",
            "stock_latest_session": stock_dates[-1] if stock_dates else None,
            "stock_session_count": len(stock_history),
            "historical_constituent_correct": False,
            "comparisons": comparisons,
            "timing": {
                "total_ms": round((time.perf_counter() - started) * 1000, 2),
            },
            "diagnostics": {
                "stock_daily_ohlc_provider_call_count": int(stock_payload.get("cache_status") != "hit"),
                "stock_daily_ohlc_cache_hit_count": int(stock_payload.get("cache_status") == "hit"),
                "peer_daily_ohlc_provider_call_count": sum(status != "hit" for status in cache_statuses[1:]),
                "peer_daily_ohlc_cache_hit_count": cache_statuses[1:].count("hit"),
                "benchmark_provider_call_count": index_provider_calls,
                "benchmark_cache_hit_count": sum(item.get("cache_status") == "hit" for item in index_results),
                "benchmark_cache_miss_count": sum(item.get("cache_status") in {"miss", "refresh"} for item in index_results),
                "membership_provider_call_count": int((membership_payload.get("diagnostics") or {}).get("cache_status") != "hit"),
                "membership_cache_status": (membership_payload.get("diagnostics") or {}).get("cache_status"),
                "max_concurrency": RS_MAX_CONCURRENCY,
                "full_watchlist_hydration_used": False,
                "synthetic_index_used": False,
                "fallback_used": False,
            },
            "fetched_at": _iso_now(),
        }
