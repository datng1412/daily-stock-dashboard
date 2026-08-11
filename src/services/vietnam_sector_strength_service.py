"""Current-VN30 ICB sector context from canonical breadth and completed flow."""

from __future__ import annotations

import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

from src.services.vietnam_foreign_flow_service import (
    VietnamForeignFlowBatchService,
    accepted_vietnam_foreign_flow_history,
    vietnam_foreign_flow_observability_snapshot,
)
from src.services.vietnam_market_breadth_service import (
    VN30_BREADTH_EXPECTED_MEMBERS,
    VN30_BREADTH_INDEX_CODE,
    VietnamMarketBreadthService,
)
from src.services.vietnam_market_service import VietnamMarketService


SECTOR_STRENGTH_MAX_CONCURRENCY = 4
SECTOR_STRENGTH_FLOW_HISTORY_SESSIONS = 60
SECTOR_STRENGTH_FLOW_WINDOWS = (1, 5, 20)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _finite_positive(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _mean(values: Iterable[float]) -> Optional[float]:
    materialized = list(values)
    return sum(materialized) / len(materialized) if materialized else None


def _normalized_classifications(
    rows: Iterable[Mapping[str, Any]],
    member_symbols: List[str],
) -> Dict[str, Dict[str, str]]:
    members = set(member_symbols)
    result: Dict[str, Dict[str, str]] = {}
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        code = str(row.get("icb_code") or "").strip()
        name = str(row.get("icb_name") or row.get("industry") or "").strip()
        if symbol in members and code and name:
            result[symbol] = {"icb_code": code, "icb_name": name}
    return result


def _accepted_value_rows(rows: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Keep accepted complete rows while excluding unresolved all-zero anomalies."""
    accepted: List[Dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        trading_date = str(raw.get("trading_date") or "").strip()
        value = raw.get("foreign_net_value")
        if (
            not trading_date
            or raw.get("complete") is False
            or bool(raw.get("suspicious_zero_session"))
            or value is None
        ):
            continue
        try:
            normalized_value = int(value)
        except (TypeError, ValueError):
            continue
        accepted.append({**dict(raw), "foreign_net_value": normalized_value})
    return sorted(accepted, key=lambda row: str(row["trading_date"]))


def _foreign_window(
    member_symbols: List[str],
    rows_by_symbol: Mapping[str, List[Dict[str, Any]]],
    requested_sessions: int,
) -> Dict[str, Any]:
    values: List[int] = []
    start_dates: List[str] = []
    end_dates: List[str] = []
    usable_symbols: List[str] = []
    for symbol in member_symbols:
        selected = rows_by_symbol.get(symbol, [])[-requested_sessions:]
        if len(selected) != requested_sessions:
            continue
        values.append(sum(int(row["foreign_net_value"]) for row in selected))
        start_dates.append(str(selected[0]["trading_date"]))
        end_dates.append(str(selected[-1]["trading_date"]))
        usable_symbols.append(symbol)
    usable_count = len(usable_symbols)
    requested_count = len(member_symbols)
    unique_start_dates = sorted(set(start_dates))
    unique_end_dates = sorted(set(end_dates))
    return {
        "requested_sessions": requested_sessions,
        "requested_member_count": requested_count,
        "usable_member_count": usable_count,
        "missing_member_count": requested_count - usable_count,
        "usable_symbols": usable_symbols,
        "coverage_ratio": usable_count / requested_count if requested_count else None,
        "complete": bool(requested_count and usable_count == requested_count),
        "net_value": sum(values) if values else None,
        "start_date": unique_start_dates[0] if len(unique_start_dates) == 1 else None,
        "end_date": unique_end_dates[0] if len(unique_end_dates) == 1 else None,
        "observed_start_dates": unique_start_dates,
        "observed_end_dates": unique_end_dates,
    }


def calculate_sector_groups(
    *,
    member_symbols: List[str],
    classifications: Mapping[str, Mapping[str, str]],
    breadth_items: Iterable[Mapping[str, Any]],
    accepted_flow_history: Mapping[str, Iterable[Mapping[str, Any]]],
) -> List[Dict[str, Any]]:
    """Aggregate current-cohort facts without inventing classifications or values."""
    groups: Dict[tuple[str, str], List[str]] = defaultdict(list)
    for symbol in member_symbols:
        classification = classifications.get(symbol)
        if not classification:
            continue
        groups[(classification["icb_code"], classification["icb_name"])].append(symbol)
    breadth_by_symbol = {
        str(item.get("symbol") or "").strip().upper(): dict(item)
        for item in breadth_items
        if item.get("symbol")
    }
    flow_by_symbol = {
        symbol: _accepted_value_rows(accepted_flow_history.get(symbol) or [])
        for symbol in member_symbols
    }
    results: List[Dict[str, Any]] = []
    for (code, name), unsorted_symbols in groups.items():
        symbols = sorted(unsorted_symbols)
        advances = declines = unchanged = 0
        above20 = not_above20 = above50 = not_above50 = 0
        returns: List[float] = []
        for symbol in symbols:
            item = breadth_by_symbol.get(symbol) or {}
            direction = item.get("direction")
            if direction == "advance":
                advances += 1
            elif direction == "decline":
                declines += 1
            elif direction == "unchanged":
                unchanged += 1
            above_ma20 = item.get("above_ma20")
            if above_ma20 is True:
                above20 += 1
            elif above_ma20 is False:
                not_above20 += 1
            above_ma50 = item.get("above_ma50")
            if above_ma50 is True:
                above50 += 1
            elif above_ma50 is False:
                not_above50 += 1
            current_close = _finite_positive(item.get("current_close"))
            previous_close = _finite_positive(item.get("previous_close"))
            if current_close is not None and previous_close is not None:
                returns.append(current_close / previous_close - 1)

        direction_usable = advances + declines + unchanged
        ma20_usable = above20 + not_above20
        ma50_usable = above50 + not_above50
        foreign_windows = {
            str(window): _foreign_window(symbols, flow_by_symbol, window)
            for window in SECTOR_STRENGTH_FLOW_WINDOWS
        }
        latest_dates = sorted({
            str(rows[-1]["trading_date"])
            for symbol in symbols
            if (rows := flow_by_symbol.get(symbol))
        })
        return_usable = len(returns)
        any_usable = any((return_usable, direction_usable, ma20_usable, ma50_usable)) or any(
            window["usable_member_count"] > 0 for window in foreign_windows.values()
        )
        complete = (
            return_usable == len(symbols)
            and direction_usable == len(symbols)
            and ma20_usable == len(symbols)
            and ma50_usable == len(symbols)
            and all(window["complete"] for window in foreign_windows.values())
        )
        results.append({
            "icb_code": code,
            "icb_name": name,
            "member_symbols": symbols,
            "member_count": len(symbols),
            "data_state": "ready" if complete else "partial" if any_usable else "unavailable",
            "return_1d": {
                "value": _mean(returns),
                "usable_count": return_usable,
                "missing_count": len(symbols) - return_usable,
                "method": "equal_weight_mean_member_close_return",
            },
            "direction": {
                "advances": advances,
                "declines": declines,
                "unchanged": unchanged,
                "usable_count": direction_usable,
            },
            "ma20": {
                "above_count": above20,
                "not_above_count": not_above20,
                "usable_count": ma20_usable,
                "percent_above": above20 / ma20_usable * 100 if ma20_usable else None,
            },
            "ma50": {
                "above_count": above50,
                "not_above_count": not_above50,
                "usable_count": ma50_usable,
                "percent_above": above50 / ma50_usable * 100 if ma50_usable else None,
            },
            "foreign_flow": {
                "source": "SSI DailyStockPrice",
                "finality": "completed_accepted",
                "latest_completed_date": latest_dates[-1] if latest_dates else None,
                "windows": foreign_windows,
            },
        })
    return sorted(
        results,
        key=lambda group: (
            group["return_1d"]["value"] is None,
            -(group["return_1d"]["value"] or 0.0),
            group["icb_name"],
            group["icb_code"],
        ),
    )


class VietnamSectorStrengthService:
    """Compose one current-VN30 sector response from shared lower-level caches."""

    def __init__(
        self,
        market_service: Optional[VietnamMarketService] = None,
        breadth_service: Optional[VietnamMarketBreadthService] = None,
        flow_batch_service: Optional[VietnamForeignFlowBatchService] = None,
        *,
        accepted_history_reader: Callable[[Iterable[str]], Dict[str, List[Dict[str, Any]]]] = accepted_vietnam_foreign_flow_history,
        flow_metrics_reader: Callable[[], Dict[str, Any]] = vietnam_foreign_flow_observability_snapshot,
    ) -> None:
        self.market_service = market_service or VietnamMarketService()
        self.breadth_service = breadth_service or VietnamMarketBreadthService(self.market_service)
        self.flow_batch_service = flow_batch_service or VietnamForeignFlowBatchService(
            max_concurrency=SECTOR_STRENGTH_MAX_CONCURRENCY
        )
        self.accepted_history_reader = accepted_history_reader
        self.flow_metrics_reader = flow_metrics_reader

    def build(self, index_code: str = VN30_BREADTH_INDEX_CODE, *, force_refresh: bool = False) -> Dict[str, Any]:
        started = time.perf_counter()
        normalized_index = str(index_code or "").strip().upper()
        if normalized_index != VN30_BREADTH_INDEX_CODE:
            raise ValueError("VN-SECTOR-1 supports index_code=VN30 only")

        breadth_started = time.perf_counter()
        breadth = self.breadth_service.build(
            index_code=normalized_index,
            force_refresh=force_refresh,
        )
        breadth_ms = (time.perf_counter() - breadth_started) * 1000
        member_symbols = list((breadth.get("membership") or {}).get("symbols") or [])

        classification_started = time.perf_counter()
        membership_payload = self.market_service.build_index_components(
            normalized_index,
            force_refresh=False,
        )
        classifications = _normalized_classifications(
            membership_payload.get("rows") or [], member_symbols
        )
        classification_ms = (time.perf_counter() - classification_started) * 1000
        classified_symbols = sorted(classifications)
        unclassified_symbols = [symbol for symbol in member_symbols if symbol not in classifications]
        group_ids = {
            (row["icb_code"], row["icb_name"])
            for row in classifications.values()
        }
        membership_diagnostics = dict(membership_payload.get("diagnostics") or {})
        exact_membership = (
            breadth.get("membership", {}).get("status") == "ready"
            and len(member_symbols) == VN30_BREADTH_EXPECTED_MEMBERS
        )
        if not exact_membership:
            return self._unavailable(
                started=started,
                breadth=breadth,
                member_symbols=member_symbols,
                classified_symbols=classified_symbols,
                unclassified_symbols=unclassified_symbols,
                group_count=len(group_ids),
                breadth_ms=breadth_ms,
                classification_ms=classification_ms,
                membership_cache_status=membership_diagnostics.get("cache_status"),
            )

        flow_before = self.flow_metrics_reader()
        flow_started = time.perf_counter()
        flow_batch = self.flow_batch_service.get_watchlist(
            member_symbols,
            sessions=SECTOR_STRENGTH_FLOW_HISTORY_SESSIONS,
            force_refresh=force_refresh,
        )
        flow_ms = (time.perf_counter() - flow_started) * 1000
        flow_after = self.flow_metrics_reader()
        accepted_history = self.accepted_history_reader(member_symbols)

        calculation_started = time.perf_counter()
        groups = calculate_sector_groups(
            member_symbols=member_symbols,
            classifications=classifications,
            breadth_items=breadth.get("items") or [],
            accepted_flow_history=accepted_history,
        )
        calculation_ms = (time.perf_counter() - calculation_started) * 1000
        latest_flow_dates = sorted({
            str(group["foreign_flow"]["latest_completed_date"])
            for group in groups
            if group["foreign_flow"].get("latest_completed_date")
        })
        all_complete = (
            len(classified_symbols) == VN30_BREADTH_EXPECTED_MEMBERS
            and bool(groups)
            and all(group["data_state"] == "ready" for group in groups)
        )
        usable = bool(groups) and any(group["data_state"] != "unavailable" for group in groups)
        status = "ready" if all_complete else "partial" if usable else "unavailable"
        flow_items = list(flow_batch.get("items") or [])
        flow_provider_calls = max(
            0,
            int(flow_after.get("provider_calls") or 0)
            - int(flow_before.get("provider_calls") or 0),
        )
        response = {
            "status": status,
            "data_state": status,
            "usable": usable,
            "index_code": VN30_BREADTH_INDEX_CODE,
            "universe": "current_vn30_membership",
            "source": "SSI",
            "membership_source": "SSI IndexComponents",
            "classification_source": "SSI ICB",
            "price_source": "SSI DailyOhlc",
            "foreign_flow_source": "SSI DailyStockPrice",
            "aggregation_basis": "current_vn30_icb_equal_weight",
            "historical_constituent_correct": False,
            "official_sector_index_return": False,
            "price_session_date": breadth.get("provider_session_date"),
            "price_finality": breadth.get("finality") or "unknown",
            "foreign_flow_latest_completed_date": latest_flow_dates[-1] if latest_flow_dates else None,
            "membership": {
                "requested_count": VN30_BREADTH_EXPECTED_MEMBERS,
                "member_count": len(member_symbols),
                "classified_count": len(classified_symbols),
                "unclassified_count": len(unclassified_symbols),
                "unclassified_symbols": unclassified_symbols,
                "group_count": len(groups),
                "duplicate_symbols": [],
                "symbols": member_symbols,
                "cache_status": membership_diagnostics.get("cache_status"),
            },
            "groups": groups,
            "timing": {
                "breadth_ms": round(breadth_ms, 2),
                "classification_ms": round(classification_ms, 2),
                "foreign_flow_ms": round(flow_ms, 2),
                "calculation_ms": round(calculation_ms, 2),
                "total_ms": round((time.perf_counter() - started) * 1000, 2),
            },
            "diagnostics": {
                "membership_provider_call_count": 0 if (breadth.get("membership") or {}).get("cache_status") == "hit" else 1,
                "daily_ohlc_provider_call_count": int((breadth.get("diagnostics") or {}).get("provider_call_count") or 0),
                "daily_ohlc_cache_hit_count": int((breadth.get("diagnostics") or {}).get("cache_hit_count") or 0),
                "daily_ohlc_cache_miss_count": int((breadth.get("diagnostics") or {}).get("cache_miss_count") or 0),
                "foreign_flow_provider_call_count": flow_provider_calls,
                "foreign_flow_cache_hit_count": sum(str(item.get("cache_state")) == "hit" for item in flow_items),
                "foreign_flow_cache_miss_count": sum(str(item.get("cache_state")) in {"miss", "refresh"} for item in flow_items),
                "max_concurrency": SECTOR_STRENGTH_MAX_CONCURRENCY,
                "breadth_reused": True,
                "full_watchlist_hydration_used": False,
                "current_foreign_flow_included": False,
                "fallback_used": False,
                "flow_batch_state": flow_batch.get("data_state"),
            },
            "fetched_at": _iso_now(),
        }
        return response

    @staticmethod
    def _unavailable(
        *,
        started: float,
        breadth: Dict[str, Any],
        member_symbols: List[str],
        classified_symbols: List[str],
        unclassified_symbols: List[str],
        group_count: int,
        breadth_ms: float,
        classification_ms: float,
        membership_cache_status: Optional[str],
    ) -> Dict[str, Any]:
        return {
            "status": "unavailable",
            "data_state": "unavailable",
            "usable": False,
            "index_code": VN30_BREADTH_INDEX_CODE,
            "universe": "current_vn30_membership",
            "source": "SSI",
            "membership_source": "SSI IndexComponents",
            "classification_source": "SSI ICB",
            "price_source": "SSI DailyOhlc",
            "foreign_flow_source": "SSI DailyStockPrice",
            "aggregation_basis": "current_vn30_icb_equal_weight",
            "historical_constituent_correct": False,
            "official_sector_index_return": False,
            "price_session_date": breadth.get("provider_session_date"),
            "price_finality": breadth.get("finality") or "unknown",
            "foreign_flow_latest_completed_date": None,
            "membership": {
                "requested_count": VN30_BREADTH_EXPECTED_MEMBERS,
                "member_count": len(member_symbols),
                "classified_count": len(classified_symbols),
                "unclassified_count": len(unclassified_symbols),
                "unclassified_symbols": unclassified_symbols,
                "group_count": group_count,
                "duplicate_symbols": [],
                "symbols": member_symbols,
                "cache_status": membership_cache_status,
            },
            "groups": [],
            "timing": {
                "breadth_ms": round(breadth_ms, 2),
                "classification_ms": round(classification_ms, 2),
                "foreign_flow_ms": 0.0,
                "calculation_ms": 0.0,
                "total_ms": round((time.perf_counter() - started) * 1000, 2),
            },
            "diagnostics": {
                "membership_provider_call_count": 0 if (breadth.get("membership") or {}).get("cache_status") == "hit" else 1,
                "daily_ohlc_provider_call_count": int((breadth.get("diagnostics") or {}).get("provider_call_count") or 0),
                "daily_ohlc_cache_hit_count": int((breadth.get("diagnostics") or {}).get("cache_hit_count") or 0),
                "daily_ohlc_cache_miss_count": int((breadth.get("diagnostics") or {}).get("cache_miss_count") or 0),
                "foreign_flow_provider_call_count": 0,
                "foreign_flow_cache_hit_count": 0,
                "foreign_flow_cache_miss_count": 0,
                "max_concurrency": SECTOR_STRENGTH_MAX_CONCURRENCY,
                "breadth_reused": True,
                "full_watchlist_hydration_used": False,
                "current_foreign_flow_included": False,
                "fallback_used": False,
            },
            "fetched_at": _iso_now(),
        }
