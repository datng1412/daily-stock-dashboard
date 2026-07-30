"""Provider-backed SSI V3 foreign, proprietary, and ICB-industry flow data."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime, timedelta
from threading import RLock
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
from zoneinfo import ZoneInfo

from data_provider.ssi_provider_protocol import SsiRestProvider
from data_provider.ssi_provider_router import (
    SsiRestProviderRouter,
    create_ssi_rest_provider_router,
)
from src.services.vietnam_vn30_membership_cache import (
    get_last_known_vn30_membership,
    remember_vn30_membership,
    reset_last_known_vn30_membership,
)


_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_MAX_SYMBOLS = 30
_MAX_RANGE_DAYS = 120
_SOURCE = "ssi_fastconnect"
_PROVIDER_VERSION = "v3"
_PROP_CACHE_LOCK = RLock()
_PROP_CACHE: Dict[Tuple[str, str, Optional[str]], Tuple[float, Dict[str, Any]]] = {}
_PROP_COMPLETED_TTL_SECONDS = 3_600
_PROP_CURRENT_TTL_SECONDS = 60
_DIRECT_INDEX_CAPABILITY = "foreign_flow_direct_index"
_DIRECT_INDEX_CAPABILITY_SCHEMA_VERSION = "v1"
_DIRECT_INDEX_CAPABILITY_TTL_SECONDS = 86_400
_DIRECT_INDEX_REQUIRED_FIELDS = (
    "totalForeignBuy",
    "totalForeignSell",
    "totalForeignBuyValue",
    "totalForeignSellValue",
)
_DIRECT_INDEX_CAPABILITY_LOCK = RLock()
_DIRECT_INDEX_CAPABILITY_CACHE: Dict[
    Tuple[str, str, str, str, str], Tuple[datetime, Dict[str, Any]]
] = {}
_CURRENT_UNIVERSE_LOCK = RLock()
_CURRENT_UNIVERSE_CACHE: Dict[
    str, Tuple[float, List[str], Dict[str, Dict[str, str]]]
] = {}
_CURRENT_UNIVERSE_TTL_SECONDS = 300
_CURRENT_UNIVERSE_FAILURE_TTL_SECONDS = 60
_CURRENT_UNIVERSE_FAILURE_CACHE: Dict[str, Tuple[float, str]] = {}


class ForeignFlowRequestValidationError(ValueError):
    """The caller supplied an invalid foreign-flow request."""


def reset_vietnam_flow_data_capability_cache() -> None:
    """Reset the process-local direct-index capability cache for tests."""
    with _DIRECT_INDEX_CAPABILITY_LOCK:
        _DIRECT_INDEX_CAPABILITY_CACHE.clear()
    with _CURRENT_UNIVERSE_LOCK:
        _CURRENT_UNIVERSE_CACHE.clear()
        _CURRENT_UNIVERSE_FAILURE_CACHE.clear()
    reset_last_known_vn30_membership()


def _iso_date(value: str, name: str) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise ValueError(f"{name} must use YYYY-MM-DD format") from exc


def _symbols(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        symbol = str(value or "").strip().upper()
        if symbol.endswith(".VN"):
            symbol = symbol[:-3]
        if not symbol or not symbol.isalnum() or len(symbol) > 10:
            raise ValueError("symbols must contain valid SSI ticker identifiers")
        if symbol not in seen:
            seen.add(symbol)
            result.append(symbol)
    if not result:
        raise ValueError("at least one symbol is required")
    if len(result) > _MAX_SYMBOLS:
        raise ValueError(f"at most {_MAX_SYMBOLS} symbols are allowed")
    return result


def _number(row: Mapping[str, Any], name: str) -> Optional[float]:
    value = row.get(name)
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result


def _sum_complete(rows: List[Mapping[str, Any]], names: Tuple[str, ...]) -> Dict[str, Optional[float]]:
    result: Dict[str, Optional[float]] = {}
    for name in names:
        values = [_number(row, name) for row in rows]
        result[name] = sum(value for value in values if value is not None) if any(
            value is not None for value in values
        ) else None
    return result


def _paired_net(
    rows: List[Mapping[str, Any]],
    buy_name: str,
    sell_name: str,
) -> Optional[float]:
    values = []
    for row in rows:
        buy = _number(row, buy_name)
        sell = _number(row, sell_name)
        if buy is not None and sell is not None:
            values.append(buy - sell)
    return sum(values) if values else None


def _provider_failure_class(result: Mapping[str, Any]) -> str:
    """Preserve a provider's safe machine-readable failure classification."""
    diagnostics = result.get("diagnostics")
    diagnostic_failure = (
        diagnostics.get("failure_class")
        if isinstance(diagnostics, Mapping)
        else None
    )
    failure_class = str(
        result.get("failure_class")
        or diagnostic_failure
        or "provider_unavailable"
    )
    # Once a failure originates at a provider call boundary, an adapter's
    # generic internal bucket is provider-unavailable to this product surface,
    # not a caller validation error or a proven unsupported capability.
    return "provider_unavailable" if failure_class == "internal_error" else failure_class


def _recovery_failure_class(result: Mapping[str, Any]) -> str:
    """Expose retryable authentication separately from explicit entitlement."""

    failure_class = _provider_failure_class(result)
    if failure_class in {
        "authentication",
        "authentication_failed",
        "auth_failed",
        "authorization",
    }:
        return "authentication_failed_retryable"
    if failure_class in {"entitlement_unavailable", "entitlement_rejected"}:
        return "explicit_entitlement_rejected"
    return failure_class


class VietnamFlowDataService:
    """SSI flow capabilities with isolated completed and provisional sources."""

    def __init__(
        self,
        provider: Optional[SsiRestProvider] = None,
        *,
        streaming_reader: Optional[Any] = None,
    ) -> None:
        self._router: Optional[SsiRestProviderRouter] = None
        self._initialization_failure = False
        if provider is None:
            try:
                self._router = create_ssi_rest_provider_router()
                provider = self._router
            except Exception:
                self._initialization_failure = True
        self._provider = provider
        self._streaming_reader = streaming_reader

    def _get_current_flow_reader(self) -> Optional[Any]:
        if self._streaming_reader is not None:
            return self._streaming_reader
        try:
            from data_provider.ssi_v3_streaming import SsiStreamingRealtimeReader
            from src.services.ssi_streaming_realtime_lifecycle import (
                get_existing_ssi_streaming_realtime_manager,
            )

            manager = get_existing_ssi_streaming_realtime_manager()
            if manager is not None:
                self._streaming_reader = SsiStreamingRealtimeReader(manager)
        except Exception:
            self._streaming_reader = None
        return self._streaming_reader

    def close(self) -> None:
        if self._router is not None:
            self._router.close()

    @staticmethod
    def _date_range(from_date: str, to_date: str) -> List[str]:
        start = date.fromisoformat(_iso_date(from_date, "from_date"))
        end = date.fromisoformat(_iso_date(to_date, "to_date"))
        if start > end:
            raise ValueError("from_date must not be after to_date")
        if (end - start).days + 1 > _MAX_RANGE_DAYS:
            raise ValueError(f"date range cannot exceed {_MAX_RANGE_DAYS} calendar days")
        # The V3 indexSummary contract accepts one provider date per request.
        # Skip weekends to keep long explorer windows bounded without inventing
        # sessions; exchange holidays remain provider-empty and are reported.
        return [
            candidate.isoformat()
            for offset in range((end - start).days + 1)
            for candidate in [start + timedelta(days=offset)]
            if candidate.weekday() < 5
        ]

    def foreign_history_by_index(
        self,
        index_code: str,
        *,
        from_date: str,
        to_date: str,
        limit: int = 260,
        force_capability_refresh: bool = False,
    ) -> Dict[str, Any]:
        index = str(index_code or "").strip().upper()
        if not index:
            raise ValueError("index_code is required")
        start = _iso_date(from_date, "from_date")
        end = _iso_date(to_date, "to_date")
        if date.fromisoformat(start) > date.fromisoformat(end):
            raise ValueError("from_date must not be after to_date")
        if not 1 <= int(limit) <= 3000:
            raise ValueError("limit must be between 1 and 3000")
        if self._provider is None:
            return {
                "status": "unavailable",
                "capability_status": "unavailable",
                "scope": "index",
                "identifier": index,
                "requested_from_date": start,
                "requested_to_date": end,
                "rows": [],
                "source": _SOURCE,
                "provider_version": _PROVIDER_VERSION,
                "endpoint": "securitiesSummary?index=",
                "diagnostics": {"failure_class": "provider_not_configured"},
            }

        capability_key = (
            _SOURCE,
            _PROVIDER_VERSION,
            _DIRECT_INDEX_CAPABILITY,
            index,
            _DIRECT_INDEX_CAPABILITY_SCHEMA_VERSION,
        )
        now = datetime.now(tz=ZoneInfo("UTC"))
        if not force_capability_refresh:
            with _DIRECT_INDEX_CAPABILITY_LOCK:
                cached = _DIRECT_INDEX_CAPABILITY_CACHE.get(capability_key)
                if cached and cached[0] > now:
                    metadata = deepcopy(cached[1])
                else:
                    metadata = None
                    if cached:
                        _DIRECT_INDEX_CAPABILITY_CACHE.pop(capability_key, None)
            if metadata is not None:
                return {
                    "status": "unavailable",
                    "capability_status": "unsupported",
                    "failure_class": "DIRECT_INDEX_FOREIGN_FIELDS_UNSUPPORTED",
                    "scope": "index",
                    "identifier": index,
                    "requested_from_date": start,
                    "requested_to_date": end,
                    "rows": [],
                    "source": _SOURCE,
                    "provider_version": _PROVIDER_VERSION,
                    "endpoint": "securitiesSummary?index=",
                    "usable_session_count": 0,
                    "diagnostics": {
                        **metadata,
                        "provider_operation_count": 0,
                        "capability_cache_status": "hit",
                        "capability_refresh_reason": "negative_capability_cache_hit",
                    },
                }

        result = self._provider.get_securities_summary_by_index(
            index,
            from_date=start,
            to_date=end,
            limit=int(limit),
        )
        if result.get("status") != "ok":
            return {
                "status": "unavailable",
                "capability_status": "unavailable",
                "scope": "index",
                "identifier": index,
                "rows": [],
                "source": _SOURCE,
                "provider_version": _PROVIDER_VERSION,
                "endpoint": "securitiesSummary?index=",
                "diagnostics": {
                    **dict(result.get("diagnostics") or {}),
                    "capability_cache_status": "bypassed"
                    if force_capability_refresh
                    else "miss",
                    "capability_refresh_reason": "provider_request_failed",
                },
            }

        grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
        for row in result.get("rows") or []:
            if (
                isinstance(row, Mapping)
                and row.get("date")
                and str(row.get("symbol") or "").strip().upper() == index
            ):
                grouped[str(row["date"])].append(row)
        rows: List[Dict[str, Any]] = []
        metric_names = (
            "foreign_buy_volume",
            "foreign_sell_volume",
            "foreign_buy_value",
            "foreign_sell_value",
        )
        for trading_date in sorted(grouped):
            # A direct index request is canonical only when SSI returns the
            # aggregate row itself (for example symbol=VN30). Never rebuild
            # this contract from current constituent rows.
            provider_row = grouped[trading_date][-1]
            gross = {name: _number(provider_row, name) for name in metric_names}
            presence = dict(provider_row.get("_foreign_field_presence") or {})
            complete = all(gross[name] is not None for name in metric_names)
            explicit_zero_count = sum(
                presence.get(name) == "FIELD_PRESENT_EXPLICIT_ZERO"
                for name in metric_names
            )
            rows.append({
                "index": index,
                "trading_date": trading_date,
                **gross,
                "foreign_net_volume": (
                    gross["foreign_buy_volume"] - gross["foreign_sell_volume"]
                    if gross["foreign_buy_volume"] is not None
                    and gross["foreign_sell_volume"] is not None
                    else None
                ),
                "foreign_net_value": (
                    gross["foreign_buy_value"] - gross["foreign_sell_value"]
                    if gross["foreign_buy_value"] is not None
                    and gross["foreign_sell_value"] is not None
                    else None
                ),
                "status": "ok" if complete else "partial",
                "provider_aggregate_row": True,
                "coverage_mode": "provider_aggregate",
                "constituent_coverage": "not_applicable",
                "field_presence": presence,
                "all_fields_explicit_zero": explicit_zero_count == len(metric_names),
                "source": _SOURCE,
                "provider_version": _PROVIDER_VERSION,
                "endpoint": "securitiesSummary?index=",
            })
        usable_session_count = sum(
            all(row.get(name) is not None for name in metric_names)
            for row in rows
        )
        if rows and usable_session_count == 0 and all(
            all(row.get(name) is None for name in metric_names)
            for row in rows
        ):
            checked_at = now.isoformat()
            expires_at = now + timedelta(
                seconds=_DIRECT_INDEX_CAPABILITY_TTL_SECONDS
            )
            capability_metadata = {
                "unsupported_fields": list(_DIRECT_INDEX_REQUIRED_FIELDS),
                "required_fields": list(_DIRECT_INDEX_REQUIRED_FIELDS),
                "observed_row_count": len(rows),
                "checked_at": checked_at,
                "expires_at": expires_at.isoformat(),
                "provider_version": _PROVIDER_VERSION,
                "endpoint": "securitiesSummary",
                "capability": _DIRECT_INDEX_CAPABILITY,
                "capability_schema_version": _DIRECT_INDEX_CAPABILITY_SCHEMA_VERSION,
                "capability_checked_at": checked_at,
                "capability_ttl_seconds": _DIRECT_INDEX_CAPABILITY_TTL_SECONDS,
            }
            with _DIRECT_INDEX_CAPABILITY_LOCK:
                _DIRECT_INDEX_CAPABILITY_CACHE[capability_key] = (
                    expires_at,
                    deepcopy(capability_metadata),
                )
            return {
                "status": "unavailable",
                "capability_status": "unsupported",
                "failure_class": "DIRECT_INDEX_FOREIGN_FIELDS_UNSUPPORTED",
                "scope": "index",
                "identifier": index,
                "requested_from_date": start,
                "requested_to_date": end,
                "rows": [],
                "source": _SOURCE,
                "provider_version": _PROVIDER_VERSION,
                "endpoint": "securitiesSummary?index=",
                "usable_session_count": 0,
                "diagnostics": {
                    **capability_metadata,
                    "provider_operation_count": 1,
                    "raw_row_count": len(result.get("rows") or []),
                    "aggregate_shape": "provider_index_rows",
                    "capability_cache_status": "stored",
                    "capability_refresh_reason": (
                        "explicit_capability_refresh"
                        if force_capability_refresh
                        else "successful_probe_no_usable_foreign_fields"
                    ),
                },
            }

        return {
            "status": "ok" if rows and all(row["status"] == "ok" for row in rows) else ("partial" if rows else "unavailable"),
            "capability_status": "available" if usable_session_count else "inconclusive",
            "scope": "index",
            "identifier": index,
            "requested_from_date": start,
            "requested_to_date": end,
            "rows": rows,
            "source": _SOURCE,
            "provider_version": _PROVIDER_VERSION,
            "endpoint": "securitiesSummary?index=",
            "usable_session_count": usable_session_count,
            "diagnostics": {
                "provider_operation_count": 1,
                "raw_row_count": len(result.get("rows") or []),
                "aggregate_shape": "provider_index_rows" if rows else "no_direct_index_rows",
                "capability_cache_status": "bypassed"
                if force_capability_refresh
                else "miss",
                "capability_refresh_reason": (
                    "explicit_capability_refresh"
                    if force_capability_refresh
                    else "capability_probe"
                ),
            },
        }

    def current_foreign_by_symbol(
        self,
        symbol: str,
        *,
        force_refresh: bool = False,
        recovery_trigger: str = "route_touch",
    ) -> Dict[str, Any]:
        ticker = _symbols([symbol])[0]
        if force_refresh and recovery_trigger == "route_touch":
            recovery_trigger = "manual_refresh"
        reader = self._get_current_flow_reader()
        if reader is None or not callable(getattr(reader, "get_current_foreign_flow", None)):
            stream = {
                "status": "unavailable",
                "data_state": "unavailable",
                "usable": False,
                "failure_class": "stream_manager_not_initialized",
                "provider_session_date": datetime.now(_VN_TZ).date().isoformat(),
                "is_current_session": False,
                "is_provisional": False,
                "current": None,
                "stream_status": "manager_not_started",
                "stream_reason": "SSI streaming lifecycle has not created a process-shared manager.",
                "cache": {"status": "not_started", "age_seconds": None},
                "market_session": {},
                "diagnostics": {},
            }
        else:
            try:
                ensure = getattr(reader, "ensure_current_foreign_flow", None)
                if callable(ensure):
                    ensure(
                        ticker,
                        recovery_trigger=recovery_trigger,
                    )
                stream = dict(reader.get_current_foreign_flow(ticker))
            except Exception:
                stream = {
                    "status": "unavailable",
                    "data_state": "error",
                    "usable": False,
                    "failure_class": "current_flow_reader_error",
                    "provider_session_date": datetime.now(_VN_TZ).date().isoformat(),
                    "is_current_session": False,
                    "is_provisional": False,
                    "current": None,
                    "stream_status": "reader_error",
                    "stream_reason": "SSI current foreign-flow cache could not be read.",
                    "cache": {"status": "unavailable", "age_seconds": None},
                    "market_session": {},
                    "diagnostics": {},
                }

        session_date = str(
            stream.get("provider_session_date")
            or datetime.now(_VN_TZ).date().isoformat()
        )
        comparison: Optional[Dict[str, Any]] = None
        comparison_failure: Optional[str] = None
        if self._provider is not None:
            result = self._provider.get_daily_stock_price(ticker, limit=5)
            if result.get("status") == "ok":
                completed_rows = [
                    dict(item)
                    for item in result.get("rows") or []
                    if isinstance(item, Mapping)
                    and str(item.get("date") or "") < session_date
                ]
                if completed_rows:
                    comparison = max(
                        completed_rows,
                        key=lambda item: str(item.get("date") or ""),
                    )
                    comparison["finality"] = "completed_session_authority"
                    comparison["source"] = "SSI V3 DailyStockPrice"
            else:
                comparison_failure = _recovery_failure_class(result)

        data_state = str(stream.get("data_state") or "unavailable")
        current_row = dict(stream.get("current") or {}) or None
        usable = bool(stream.get("usable") and current_row)
        public_status = (
            "ok"
            if data_state == "ready" and usable
            else "partial"
            if usable
            else "unavailable"
        )
        return {
            "status": public_status,
            "data_state": data_state,
            "usable": usable,
            "failure_class": stream.get("failure_class"),
            "symbol": ticker,
            "trading_date": session_date if current_row else None,
            "freshness_status": data_state,
            "is_current_session": bool(stream.get("is_current_session") and current_row),
            "is_provisional": bool(stream.get("is_provisional") and current_row),
            "current": current_row,
            "latest_completed_comparison": comparison,
            "stream_status": str(stream.get("stream_status") or data_state),
            "stream_reason": str(stream.get("stream_reason") or ""),
            "source": (
                "SSI FastConnect V3 ForeignRoomMessage"
                if current_row
                else _SOURCE
            ),
            "provider_version": _PROVIDER_VERSION,
            "endpoint": f"room.{ticker}",
            "finality": "current_session_provisional" if current_row else None,
            "update_semantics": (
                "cumulative_replacement_snapshot" if current_row else None
            ),
            "cache": dict(stream.get("cache") or {}),
            "market_session": dict(stream.get("market_session") or {}),
            "diagnostics": {
                **dict(stream.get("diagnostics") or {}),
                "completed_comparison_source": "SSI V3 DailyStockPrice",
                "completed_comparison_failure_class": comparison_failure,
                "provisional_appended_to_history": False,
            },
        }

    def current_foreign_aggregate(
        self,
        *,
        symbols: Optional[Iterable[str]] = None,
        index_code: Optional[str] = None,
        include_industries: bool = False,
        force_refresh: bool = False,
        recovery_trigger: str = "route_touch",
    ) -> Dict[str, Any]:
        """Build a display-only current aggregate from the shared R cache."""

        if bool(symbols) == bool(index_code):
            raise ValueError("provide exactly one of symbols or index_code")
        if force_refresh and recovery_trigger == "route_touch":
            recovery_trigger = "manual_refresh"
        classifications: Dict[str, Dict[str, str]] = {}
        membership_diagnostics: Dict[str, Any] = {
            "membership_source": None,
            "membership_retained": False,
            "membership_age_seconds": None,
            "membership_refresh_failure_class": None,
            "negative_cache_bypassed": False,
            "recovery_scheduled": False,
        }
        normalized_index = str(index_code or "").strip().upper() or None
        if normalized_index:
            now = time.monotonic()
            with _CURRENT_UNIVERSE_LOCK:
                cached = _CURRENT_UNIVERSE_CACHE.get(normalized_index)
                if cached and cached[0] > now and not force_refresh:
                    ticker_list = list(cached[1])
                    classifications = deepcopy(cached[2])
                else:
                    ticker_list = []
            if not ticker_list:
                with _CURRENT_UNIVERSE_LOCK:
                    failed = _CURRENT_UNIVERSE_FAILURE_CACHE.get(
                        normalized_index
                    )
                failure_cooldown_active = bool(
                    failed and failed[0] > now and not force_refresh
                )
                membership: Dict[str, Any] = {}
                if not failure_cooldown_active and self._provider is not None:
                    if force_refresh:
                        request_recovery = getattr(
                            self._provider, "request_auth_recovery", None
                        )
                        if callable(request_recovery):
                            recovery = dict(
                                request_recovery(trigger=recovery_trigger)
                            )
                            membership_diagnostics.update(
                                negative_cache_bypassed=bool(
                                    recovery.get("negative_cache_bypassed")
                                ),
                                recovery_scheduled=bool(
                                    recovery.get("recovery_scheduled")
                                ),
                                recovery_status=recovery.get("status"),
                            )
                    membership = self._provider.get_securities_by_index(
                        normalized_index
                    )
                elif failed:
                    membership = {
                        "status": "unavailable",
                        "failure_class": failed[1],
                        "rows": [],
                    }
                elif self._provider is None:
                    membership = {
                        "status": "unavailable",
                        "failure_class": "provider_not_configured",
                        "rows": [],
                    }

                membership_rows = [
                    dict(row)
                    for row in membership.get("rows") or []
                    if isinstance(row, Mapping)
                ]
                if membership.get("status") == "ok":
                    try:
                        ticker_list = _symbols(
                            row.get("symbol") for row in membership_rows
                        )
                    except ValueError:
                        ticker_list = []
                    if ticker_list:
                        for row in membership_rows:
                            ticker = str(
                                row.get("symbol") or ""
                            ).strip().upper()
                            if ticker not in ticker_list:
                                continue
                            code = str(row.get("icb_code") or "").strip()
                            name = str(row.get("icb_name") or "").strip()
                            if code and name:
                                classifications[ticker] = {
                                    "icb_code": code,
                                    "icb_name": name,
                                }
                        with _CURRENT_UNIVERSE_LOCK:
                            _CURRENT_UNIVERSE_CACHE[normalized_index] = (
                                now + _CURRENT_UNIVERSE_TTL_SECONDS,
                                list(ticker_list),
                                deepcopy(classifications),
                            )
                            _CURRENT_UNIVERSE_FAILURE_CACHE.pop(
                                normalized_index, None
                            )
                        if normalized_index == "VN30":
                            remember_vn30_membership(
                                ticker_list,
                                classifications=classifications,
                                fetched_at=membership.get("fetched_at"),
                            )
                        membership_diagnostics["membership_source"] = (
                            "SSI IndexComponents"
                        )
                if not ticker_list:
                    failure_class = _recovery_failure_class(membership)
                    membership_diagnostics[
                        "membership_refresh_failure_class"
                    ] = failure_class
                    with _CURRENT_UNIVERSE_LOCK:
                        _CURRENT_UNIVERSE_FAILURE_CACHE[normalized_index] = (
                            now + _CURRENT_UNIVERSE_FAILURE_TTL_SECONDS,
                            failure_class,
                        )
                    retained = (
                        get_last_known_vn30_membership()
                        if normalized_index == "VN30"
                        else None
                    )
                    if retained:
                        ticker_list = list(retained["symbols"])
                        classifications = deepcopy(
                            retained["classifications"]
                        )
                        membership_diagnostics.update(
                            membership_source=retained["source"],
                            membership_retained=True,
                            membership_age_seconds=retained["age_seconds"],
                        )
                    else:
                        unavailable = self._unavailable_current_aggregate(
                            universe=f"index:{normalized_index}",
                            failure_class=failure_class,
                        )
                        unavailable["diagnostics"].update(
                            membership_diagnostics
                        )
                        return unavailable
            else:
                membership_diagnostics["membership_source"] = (
                    "SSI IndexComponents"
                )
            universe = f"index:{normalized_index}"
        else:
            ticker_list = _symbols(symbols or [])
            universe = "selected_symbols"

        reader = self._get_current_flow_reader()
        if reader is None or not callable(
            getattr(reader, "get_current_foreign_flow", None)
        ):
            streams = {
                ticker: {
                    "status": "unavailable",
                    "data_state": "unavailable",
                    "usable": False,
                    "failure_class": "stream_manager_not_initialized",
                    "provider_session_date": None,
                    "current": None,
                    "stream_status": "manager_not_started",
                    "market_session": {},
                }
                for ticker in ticker_list
            }
            ensure_result: Dict[str, Any] = {
                "status": "unavailable",
                "recovery_requested": False,
            }
        else:
            ensure_result = {}
            try:
                ensure_cohort = getattr(
                    reader, "ensure_current_foreign_flow_cohort", None
                )
                if callable(ensure_cohort):
                    ensure_result = dict(
                        ensure_cohort(
                            ticker_list,
                            recovery_trigger=recovery_trigger,
                        )
                    )
                else:
                    for ticker in ticker_list:
                        ensure = getattr(
                            reader, "ensure_current_foreign_flow", None
                        )
                        if callable(ensure):
                            ensure(
                                ticker,
                                recovery_trigger=recovery_trigger,
                            )
                streams = {
                    ticker: dict(reader.get_current_foreign_flow(ticker))
                    for ticker in ticker_list
                }
            except Exception:
                streams = {
                    ticker: {
                        "status": "unavailable",
                        "data_state": "error",
                        "usable": False,
                        "failure_class": "current_flow_reader_error",
                        "provider_session_date": None,
                        "current": None,
                        "stream_status": "reader_error",
                        "market_session": {},
                    }
                    for ticker in ticker_list
                }
                ensure_result = {
                    "status": "unavailable",
                    "recovery_requested": False,
                }

        observed_dates = sorted({
            str(stream.get("provider_session_date"))
            for stream in streams.values()
            if stream.get("current")
            and stream.get("usable")
            and stream.get("provider_session_date")
        })
        provider_session_date = observed_dates[-1] if observed_dates else next(
            (
                str(stream.get("provider_session_date"))
                for stream in streams.values()
                if stream.get("provider_session_date")
            ),
            None,
        )
        items: List[Dict[str, Any]] = []
        for ticker in ticker_list:
            stream = streams[ticker]
            current = (
                dict(stream.get("current") or {})
                if stream.get("usable")
                and stream.get("provider_session_date") == provider_session_date
                else {}
            )
            item = {
                "symbol": ticker,
                "provider_session_date": (
                    provider_session_date if current else None
                ),
                "data_state": str(stream.get("data_state") or "unavailable"),
                "usable": bool(current),
                "is_stale": str(stream.get("data_state")) in {"stale", "error"},
                "stream_status": str(stream.get("stream_status") or "unavailable"),
                "foreign_buy_volume": _number(current, "foreign_buy_volume"),
                "foreign_sell_volume": _number(current, "foreign_sell_volume"),
                "foreign_buy_value": _number(current, "foreign_buy_value"),
                "foreign_sell_value": _number(current, "foreign_sell_value"),
                "provider_time": current.get("stream_timestamp")
                or current.get("time"),
                "received_at": current.get("received_at"),
                "raw_field_presence": dict(
                    current.get("raw_field_presence") or {}
                ),
                **classifications.get(ticker, {}),
            }
            item["foreign_net_volume"] = (
                item["foreign_buy_volume"] - item["foreign_sell_volume"]
                if item["foreign_buy_volume"] is not None
                and item["foreign_sell_volume"] is not None
                else None
            )
            item["foreign_net_value"] = (
                item["foreign_buy_value"] - item["foreign_sell_value"]
                if item["foreign_buy_value"] is not None
                and item["foreign_sell_value"] is not None
                else None
            )
            items.append(item)

        aggregate = self._aggregate_current_items(items, len(ticker_list))
        observed_count = int(aggregate["observed_count"])
        stale_count = sum(
            bool(item["is_stale"]) and item["usable"] for item in items
        )
        if observed_count:
            states = {
                str(item["data_state"])
                for item in items
                if item["usable"]
            }
            data_state = (
                "stale"
                if states & {"stale", "error"}
                else "market_closed"
                if states == {"market_closed"}
                else "ready"
            )
        else:
            states = {
                str(stream.get("data_state") or "")
                for stream in streams.values()
            }
            data_state = (
                "waiting"
                if "waiting" in states
                else "market_closed"
                if "market_closed" in states
                else "unavailable"
            )

        try:
            from src.services.vietnam_foreign_flow_service import (
                accepted_vietnam_foreign_flow_history,
            )

            accepted_history = accepted_vietnam_foreign_flow_history(ticker_list)
        except Exception:
            accepted_history = {ticker: [] for ticker in ticker_list}
        display_by_symbol: Dict[str, List[Dict[str, Any]]] = {}
        for item in items:
            ticker = str(item["symbol"])
            accepted_rows = [
                {
                    **dict(row),
                    "source_kind": "completed",
                    "source": "SSI DailyStockPrice",
                    "finality": "completed_accepted",
                    "status": "Đủ",
                    "is_current": False,
                    "is_completed": True,
                    "is_partial": any(
                        row.get(name) is None
                        for name in (
                            "foreign_buy_volume",
                            "foreign_sell_volume",
                            "foreign_buy_value",
                            "foreign_sell_value",
                        )
                    ),
                    "is_stale": False,
                }
                for row in accepted_history.get(ticker, [])
                if row.get("trading_date")
            ]
            accepted_dates = {
                str(row["trading_date"]) for row in accepted_rows
            }
            latest_accepted = max(accepted_dates) if accepted_dates else None
            current_date = (
                str(item.get("provider_session_date") or "")
                if item.get("usable")
                else ""
            )
            if (
                current_date
                and current_date not in accepted_dates
                and (latest_accepted is None or current_date > latest_accepted)
            ):
                current_row = {
                    "trading_date": current_date,
                    **{
                        name: item.get(name)
                        for name in (
                            "foreign_buy_volume",
                            "foreign_sell_volume",
                            "foreign_net_volume",
                            "foreign_buy_value",
                            "foreign_sell_value",
                            "foreign_net_value",
                        )
                    },
                    "source_kind": "current",
                    "source": "SSI FastConnect V3 ForeignRoomMessage",
                    "finality": "current_session_provisional",
                    "status": (
                        "Tạm tính"
                        if item.get("data_state") == "market_closed"
                        else "Mất kết nối"
                        if item.get("data_state") in {"stale", "error"}
                        else "Đang diễn ra"
                    ),
                    "requested_count": 1,
                    "observed_count": 1,
                    "complete_volume_count": int(
                        item.get("foreign_buy_volume") is not None
                        and item.get("foreign_sell_volume") is not None
                    ),
                    "complete_value_count": int(
                        item.get("foreign_buy_value") is not None
                        and item.get("foreign_sell_value") is not None
                    ),
                    "coverage": 1.0,
                    "provider_time": item.get("provider_time"),
                    "received_at": item.get("received_at"),
                    "is_current": True,
                    "is_completed": False,
                    "is_partial": (
                        item.get("foreign_buy_volume") is None
                        or item.get("foreign_sell_volume") is None
                        or item.get("foreign_buy_value") is None
                        or item.get("foreign_sell_value") is None
                    ),
                    "is_stale": bool(item.get("is_stale")),
                }
                accepted_rows.append(current_row)
            display_rows = sorted(
                accepted_rows,
                key=lambda row: str(row.get("trading_date") or ""),
            )[-60:]
            display_by_symbol[ticker] = display_rows
            item["display_latest"] = display_rows[-1] if display_rows else None
            item["display_windows"] = {
                str(size): self._display_window(display_rows, size)
                for size in (1, 5, 20, 60)
            }

        display_dates = sorted({
            str(row.get("trading_date"))
            for rows in display_by_symbol.values()
            for row in rows
            if row.get("trading_date")
        })[-60:]
        display_series: List[Dict[str, Any]] = []
        for trading_date in display_dates:
            entries = [
                {
                    **row,
                    "usable": any(
                        row.get(name) is not None
                        for name in (
                            "foreign_buy_volume",
                            "foreign_sell_volume",
                            "foreign_buy_value",
                            "foreign_sell_value",
                        )
                    ),
                }
                for rows in display_by_symbol.values()
                for row in rows
                if row.get("trading_date") == trading_date
            ]
            aggregate_row = self._aggregate_current_items(
                entries, len(ticker_list)
            )
            has_current = any(
                row.get("source_kind") == "current" for row in entries
            )
            display_series.append({
                "trading_date": trading_date,
                **aggregate_row,
                "source_kind": "current" if has_current else "completed",
                "source": (
                    "SSI FastConnect V3 ForeignRoomMessage aggregate"
                    if has_current
                    else "SSI DailyStockPrice current-membership aggregate"
                ),
                "finality": (
                    "current_session_provisional"
                    if has_current
                    else "completed_accepted"
                ),
                "status": (
                    "Tạm tính"
                    if has_current and data_state == "market_closed"
                    else "Mất kết nối"
                    if has_current and data_state == "stale"
                    else "Đang diễn ra"
                    if has_current
                    else "Đủ"
                ),
                "is_current": has_current,
                "is_completed": not has_current,
                "is_stale": has_current and data_state == "stale",
            })

        groups: List[Dict[str, Any]] = []
        if include_industries:
            by_industry: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
            expected_by_industry: Dict[Tuple[str, str], int] = defaultdict(int)
            for ticker in ticker_list:
                classification = classifications.get(ticker)
                if not classification:
                    continue
                key = (
                    classification["icb_code"],
                    classification["icb_name"],
                )
                expected_by_industry[key] += 1
                item = next(row for row in items if row["symbol"] == ticker)
                by_industry[key].append(item)
            for key in sorted(expected_by_industry):
                group = self._aggregate_current_items(
                    by_industry.get(key, []),
                    expected_by_industry[key],
                )
                groups.append({
                    "icb_code": key[0],
                    "icb_name": key[1],
                    "universe": (
                        "current_vn30_membership"
                        if normalized_index == "VN30"
                        else universe
                    ),
                    "provider_session_date": provider_session_date,
                    "data_state": (
                        data_state if group["observed_count"] else "unavailable"
                    ),
                    **group,
                })
        rankings: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for size in (1, 5, 20, 60):
            candidates = []
            for item in items:
                window = dict(item.get("display_windows", {}).get(str(size)) or {})
                value = window.get("foreign_net_value")
                if value is None:
                    continue
                candidates.append({
                    "ticker": item["symbol"],
                    "value": value,
                    "trading_date": window.get("end_date"),
                    "is_provisional": bool(window.get("is_provisional")),
                    "is_partial": bool(window.get("is_partial")),
                })
            rankings[str(size)] = {
                "top_buy": sorted(
                    (row for row in candidates if row["value"] > 0),
                    key=lambda row: (-row["value"], row["ticker"]),
                )[:10],
                "top_sell": sorted(
                    (row for row in candidates if row["value"] < 0),
                    key=lambda row: (row["value"], row["ticker"]),
                )[:10],
            }
        display_usable = bool(display_series)
        current_failure_class = (
            None
            if observed_count
            else next(
                (
                    stream.get("failure_class")
                    for stream in streams.values()
                    if stream.get("failure_class")
                ),
                None,
            )
        )
        return {
            "status": (
                "ok"
                if observed_count == len(ticker_list)
                and aggregate["complete_volume_count"] == len(ticker_list)
                and aggregate["complete_value_count"] == len(ticker_list)
                and not membership_diagnostics["membership_retained"]
                else "partial"
                if observed_count or display_usable
                else "unavailable"
            ),
            "data_state": data_state,
            "usable": bool(observed_count or display_usable),
            "failure_class": current_failure_class,
            "scope": "current_foreign_flow_aggregate",
            "universe": universe,
            "provider_session_date": provider_session_date,
            "is_provisional": bool(observed_count),
            "finality": (
                "current_session_provisional" if observed_count else None
            ),
            "source": "SSI FastConnect V3 ForeignRoomMessage",
            "provider_version": _PROVIDER_VERSION,
            "endpoint": "room.{symbol}",
            "update_semantics": "cumulative_replacement_snapshot",
            "aggregate": aggregate if observed_count else None,
            "display_series": display_series,
            "display_windows": {
                str(size): self._display_window(display_series, size)
                for size in (1, 5, 20, 60)
            },
            "rankings": rankings,
            "items": items,
            "groups": groups,
            "coverage": {
                "requested_symbol_count": len(ticker_list),
                "classified_symbol_count": len(classifications),
                "subscribed_symbol_count": sum(
                    item["stream_status"]
                    not in {
                        "r_not_subscribed",
                        "ticker_not_bootstrapped",
                        "manager_not_started",
                    }
                    for item in items
                ),
                "observed_symbol_count": observed_count,
                "complete_volume_count": aggregate["complete_volume_count"],
                "complete_value_count": aggregate["complete_value_count"],
                "missing_symbols": [
                    item["symbol"] for item in items if not item["usable"]
                ],
                "stale_symbol_count": stale_count,
            },
            "market_session": next(
                (
                    dict(stream.get("market_session") or {})
                    for stream in streams.values()
                    if stream.get("market_session")
                ),
                {},
            ),
            "diagnostics": {
                "cohort_subscription_status": ensure_result.get("status"),
                "subscription_added_count": ensure_result.get(
                    "subscription_added_count", 0
                ),
                "mixed_provider_session_dates_excluded": observed_dates[:-1],
                "fallback_used": bool(
                    display_usable
                    and (
                        not observed_count
                        or membership_diagnostics["membership_retained"]
                    )
                ),
                "completed_fallback_used": bool(
                    display_usable and not observed_count
                ),
                "current_snapshot_retained": bool(
                    observed_count and data_state == "stale"
                ),
                "recovery_in_flight": (
                    ensure_result.get("recovery_status")
                    == "already_scheduled"
                ),
                **membership_diagnostics,
                "provisional_persisted": False,
            },
        }

    @staticmethod
    def _aggregate_current_items(
        items: List[Dict[str, Any]],
        requested_count: int,
    ) -> Dict[str, Any]:
        usable = [item for item in items if item.get("usable")]
        sums: Dict[str, Optional[float]] = {}
        for name in (
            "foreign_buy_volume",
            "foreign_sell_volume",
            "foreign_buy_value",
            "foreign_sell_value",
        ):
            values = [
                _number(item, name)
                for item in usable
                if _number(item, name) is not None
            ]
            sums[name] = sum(values) if values else None
        sums["foreign_net_volume"] = (
            sums["foreign_buy_volume"] - sums["foreign_sell_volume"]
            if sums["foreign_buy_volume"] is not None
            and sums["foreign_sell_volume"] is not None
            else None
        )
        sums["foreign_net_value"] = (
            sums["foreign_buy_value"] - sums["foreign_sell_value"]
            if sums["foreign_buy_value"] is not None
            and sums["foreign_sell_value"] is not None
            else None
        )
        observed_count = len(usable)
        complete_volume_count = sum(
            item.get("foreign_buy_volume") is not None
            and item.get("foreign_sell_volume") is not None
            for item in usable
        )
        complete_value_count = sum(
            item.get("foreign_buy_value") is not None
            and item.get("foreign_sell_value") is not None
            for item in usable
        )
        return {
            **sums,
            "requested_count": requested_count,
            "observed_count": observed_count,
            "complete_volume_count": complete_volume_count,
            "complete_value_count": complete_value_count,
            "coverage_ratio": (
                observed_count / requested_count if requested_count else 0.0
            ),
            "is_partial": (
                observed_count < requested_count
                or complete_volume_count < requested_count
                or complete_value_count < requested_count
            ),
        }

    @staticmethod
    def _display_window(
        rows: List[Dict[str, Any]],
        requested_count: int,
    ) -> Dict[str, Any]:
        selected = rows[-requested_count:]
        result: Dict[str, Any] = {
            "requested_sessions": requested_count,
            "actual_sessions": len(selected),
            "complete": len(selected) == requested_count,
            "start_date": selected[0].get("trading_date") if selected else None,
            "end_date": selected[-1].get("trading_date") if selected else None,
            "is_provisional": any(
                row.get("source_kind") == "current" for row in selected
            ),
            "is_partial": (
                len(selected) != requested_count
                or any(bool(row.get("is_partial")) for row in selected)
            ),
        }
        for name in (
            "foreign_buy_volume",
            "foreign_sell_volume",
            "foreign_net_volume",
            "foreign_buy_value",
            "foreign_sell_value",
            "foreign_net_value",
        ):
            values = [
                _number(row, name)
                for row in selected
                if _number(row, name) is not None
            ]
            result[name] = sum(values) if values else None
        return result

    @staticmethod
    def _unavailable_current_aggregate(
        *,
        universe: str,
        failure_class: str,
        symbols: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        requested = list(symbols or [])
        return {
            "status": "unavailable",
            "data_state": "unavailable",
            "usable": False,
            "failure_class": failure_class,
            "scope": "current_foreign_flow_aggregate",
            "universe": universe,
            "provider_session_date": None,
            "is_provisional": False,
            "finality": None,
            "source": "SSI FastConnect V3 ForeignRoomMessage",
            "provider_version": _PROVIDER_VERSION,
            "endpoint": "room.{symbol}",
            "update_semantics": "cumulative_replacement_snapshot",
            "aggregate": None,
            "display_series": [],
            "display_windows": {},
            "rankings": {},
            "items": [],
            "groups": [],
            "coverage": {
                "requested_symbol_count": len(requested),
                "classified_symbol_count": 0,
                "subscribed_symbol_count": 0,
                "observed_symbol_count": 0,
                "complete_volume_count": 0,
                "complete_value_count": 0,
                "missing_symbols": requested,
                "stale_symbol_count": 0,
            },
            "market_session": {},
            "diagnostics": {"provisional_persisted": False},
        }

    def proprietary_flow(
        self,
        scope: str,
        identifier: str,
        *,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        normalized_scope = str(scope or "").strip().lower()
        normalized_identifier = str(identifier or "").strip().upper()
        if normalized_scope not in {"board", "index"}:
            raise ValueError("scope must be board or index")
        requested_dates = (
            self._date_range(from_date, to_date)
            if from_date and to_date
            else [None]
            if not from_date and not to_date
            else (_ for _ in ()).throw(ValueError("from_date and to_date must be provided together"))
        )
        if self._provider is None:
            return {
                "status": "unavailable",
                "scope": normalized_scope,
                "identifier": normalized_identifier,
                "rows": [],
                "source": _SOURCE,
                "provider_version": _PROVIDER_VERSION,
                "endpoint": "indexSummary",
                "unsupported_scopes": ["symbol", "icb_industry"],
                "fetched_at": datetime.now(tz=ZoneInfo("UTC")).isoformat(),
                "cache": {"status": "unavailable", "age_seconds": None},
                "diagnostics": {"failure_class": "provider_not_configured"},
            }
        rows: List[Dict[str, Any]] = []
        failures = 0
        provider_operations = 0
        cache_hits = 0
        for requested_date in requested_dates:
            cache_key = (normalized_scope, normalized_identifier, requested_date)
            now = time.monotonic()
            with _PROP_CACHE_LOCK:
                cached = _PROP_CACHE.get(cache_key)
                if cached and cached[0] > now and not force_refresh:
                    result = deepcopy(cached[1])
                    cache_hits += 1
                else:
                    result = None
                    if cached:
                        _PROP_CACHE.pop(cache_key, None)
            if result is None:
                result = (
                    self._provider.get_index_summary(
                        normalized_identifier,
                        index_code=normalized_identifier,
                        trading_date=requested_date,
                    )
                    if normalized_scope == "index"
                    else self._provider.get_market_summary(
                        normalized_scope,
                        normalized_identifier,
                        trading_date=requested_date,
                    )
                )
                provider_operations += 1
                if result.get("status") == "ok" and result.get("rows"):
                    ttl = (
                        _PROP_COMPLETED_TTL_SECONDS
                        if requested_date is not None
                        and requested_date < datetime.now(_VN_TZ).date().isoformat()
                        else _PROP_CURRENT_TTL_SECONDS
                    )
                    with _PROP_CACHE_LOCK:
                        _PROP_CACHE[cache_key] = (now + ttl, deepcopy(result))
            if result.get("status") != "ok":
                failures += 1
                continue
            for raw in result.get("rows") or []:
                if not isinstance(raw, Mapping):
                    continue
                row = dict(raw)
                provider_date = row.get("date")
                today = datetime.now(_VN_TZ).date().isoformat()
                row.update({
                    "scope": normalized_scope,
                    "identifier": normalized_identifier,
                    "trading_date": provider_date,
                    "freshness_status": (
                        "current_session_provisional"
                        if provider_date == today
                        else "latest_completed_session"
                        if provider_date
                        else "unavailable"
                    ),
                })
                rows.append(row)
        by_date = {str(row.get("trading_date")): row for row in rows if row.get("trading_date")}
        ordered = [by_date[key] for key in sorted(by_date)]
        return {
            "status": "ok" if ordered and failures == 0 else ("partial" if ordered else "unavailable"),
            "scope": normalized_scope,
            "identifier": normalized_identifier,
            "rows": ordered,
            "source": _SOURCE,
            "provider_version": _PROVIDER_VERSION,
            "endpoint": "indexSummary",
            "unsupported_scopes": ["symbol", "icb_industry"],
            "requested_from_date": from_date,
            "requested_to_date": to_date,
            "fetched_at": datetime.now(tz=ZoneInfo("UTC")).isoformat(),
            "cache": {
                "status": "refresh" if force_refresh else "hit" if cache_hits and provider_operations == 0 else "partial_hit" if cache_hits else "miss",
                "age_seconds": None,
            },
            "diagnostics": {
                "provider_operation_count": provider_operations,
                "cache_hit_count": cache_hits,
                "failed_operation_count": failures,
                "requested_provider_dates": len(requested_dates),
            },
        }

    def industry_history(
        self,
        *,
        symbols: Optional[Iterable[str]] = None,
        index_code: Optional[str] = None,
        from_date: str,
        to_date: str,
    ) -> Dict[str, Any]:
        try:
            if bool(symbols) == bool(index_code):
                raise ValueError("provide exactly one of symbols or index_code")
            start = _iso_date(from_date, "from_date")
            end = _iso_date(to_date, "to_date")
            if date.fromisoformat(start) > date.fromisoformat(end):
                raise ValueError("from_date must not be after to_date")
            normalized_symbols = _symbols(symbols or []) if symbols else None
            normalized_index = (
                str(index_code or "").strip().upper() if index_code else None
            )
            if normalized_index is not None and (
                not normalized_index.isalnum() or len(normalized_index) > 20
            ):
                raise ValueError("index_code must be a valid SSI index identifier")
        except ValueError as exc:
            raise ForeignFlowRequestValidationError(str(exc)) from exc

        def unavailable(
            failure_class: str,
            *,
            requested_count: int = 0,
            provider_operations: int = 0,
        ) -> Dict[str, Any]:
            universe = (
                f"index:{normalized_index}"
                if normalized_index
                else "custom_symbols"
            )
            return {
                "status": "unavailable",
                "data_state": "unavailable",
                "usable": False,
                "failure_class": failure_class,
                "universe": universe,
                "requested_symbol_count": requested_count,
                "classified_symbol_count": 0,
                "unclassified_symbol_count": requested_count,
                "rows": [],
                "current_session_status": "CURRENT_FOREIGN_STREAM_BLOCKED_SEMANTICS",
                "proprietary_industry_status": "unsupported",
                "source": _SOURCE,
                "provider_version": _PROVIDER_VERSION,
                "requested_from_date": start,
                "requested_to_date": end,
                "fetched_at": datetime.now(tz=ZoneInfo("UTC")).isoformat(),
                "cache": {"status": "unavailable", "age_seconds": None},
                "diagnostics": {
                    "failure_class": failure_class,
                    "provider_operation_count": provider_operations,
                },
            }

        if self._provider is None:
            return unavailable(
                "provider_not_configured",
                requested_count=len(normalized_symbols or []),
            )
        provider_failures: List[str] = []

        def provider_result(call: Any) -> Dict[str, Any]:
            try:
                result = call()
            except (TimeoutError, OSError, ValueError) as exc:
                failure_class = (
                    "request_timeout"
                    if isinstance(exc, TimeoutError)
                    else "network_error"
                    if isinstance(exc, OSError)
                    else "provider_unavailable"
                )
                provider_failures.append(failure_class)
                return {
                    "status": "unavailable",
                    "rows": [],
                    "failure_class": failure_class,
                }
            if result.get("status") not in {"ok", "partial"}:
                provider_failures.append(_provider_failure_class(result))
            return result

        if normalized_index:
            index = normalized_index
            membership_result = provider_result(
                lambda: self._provider.get_securities_by_index(index)
            )
            if membership_result.get("status") != "ok":
                return unavailable(
                    _provider_failure_class(membership_result),
                    provider_operations=1,
                )
            member_rows = [
                row for row in membership_result.get("rows") or []
                if isinstance(row, Mapping)
            ]
            if not member_rows:
                return unavailable(
                    "membership_unavailable",
                    provider_operations=1,
                )
            try:
                ticker_list = _symbols(row.get("symbol") for row in member_rows)
            except ValueError:
                return unavailable(
                    "membership_unavailable",
                    provider_operations=1,
                )
            universe = f"index:{index}"
            metadata = {
                str(row.get("symbol") or "").strip().upper(): dict(row)
                for row in member_rows
                if row.get("symbol")
            }
            summary_result = provider_result(
                lambda: self._provider.get_securities_summary_by_index(
                    index,
                    from_date=start,
                    to_date=end,
                    limit=3000,
                )
            )
            if summary_result.get("status") not in {"ok", "partial"}:
                return unavailable(
                    _provider_failure_class(summary_result),
                    requested_count=len(ticker_list),
                    provider_operations=2,
                )
            history: Dict[str, List[Mapping[str, Any]]] = {
                ticker: [] for ticker in ticker_list
            }
            direct_member_rows = 0
            for row in summary_result.get("rows") or []:
                if not isinstance(row, Mapping):
                    continue
                ticker = str(row.get("symbol") or "").strip().upper()
                if ticker in history:
                    history[ticker].append(row)
                    direct_member_rows += 1
            provider_operations = 2
            if not direct_member_rows:
                for ticker in ticker_list:
                    summary = provider_result(
                        lambda ticker=ticker: self._provider.get_daily_stock_price(
                            ticker, from_date=start, to_date=end, limit=260
                        )
                    )
                    provider_operations += 1
                    history[ticker] = [
                        row for row in summary.get("rows") or []
                        if isinstance(row, Mapping)
                    ]
        else:
            ticker_list = normalized_symbols or []
            universe = "custom_symbols"
        if not index_code:
            metadata = {}
            history = {}
            provider_operations = 0
            for ticker in ticker_list:
                info = provider_result(
                    lambda ticker=ticker: self._provider.get_security_basic_info(ticker)
                )
                provider_operations += 1
                info_row = next((row for row in info.get("rows") or [] if isinstance(row, Mapping)), {})
                metadata[ticker] = dict(info_row)
                summary = provider_result(
                    lambda ticker=ticker: self._provider.get_daily_stock_price(
                        ticker, from_date=start, to_date=end, limit=260
                    )
                )
                provider_operations += 1
                history[ticker] = [
                    row for row in summary.get("rows") or []
                    if isinstance(row, Mapping)
                ]

        groups: Dict[Tuple[str, str], List[Tuple[str, Mapping[str, Any]]]] = defaultdict(list)
        unclassified_symbols = {
            ticker for ticker, item in metadata.items()
            if not item.get("icb_code") or not item.get("icb_name")
        }
        for ticker, rows in history.items():
            item = metadata[ticker]
            code = item.get("icb_code")
            name = item.get("icb_name")
            if not code or not name:
                continue
            for row in rows:
                trading_date = row.get("date")
                if trading_date:
                    groups[(str(trading_date), str(code))].append((ticker, row))

        aggregate_rows: List[Dict[str, Any]] = []
        for (trading_date, code), entries in sorted(groups.items()):
            symbol_rows = [row for _, row in entries]
            industry_symbols = {
                ticker for ticker in ticker_list
                if str(metadata[ticker].get("icb_code") or "") == code
            }
            complete = sum(all(row.get(name) is not None for name in (
                "foreign_buy_volume", "foreign_sell_volume",
                "foreign_buy_value", "foreign_sell_value",
            )) for row in symbol_rows)
            gross = _sum_complete(symbol_rows, (
                "foreign_buy_volume", "foreign_sell_volume",
                "foreign_buy_value", "foreign_sell_value",
                "matched_volume", "matched_value",
            ))
            expected = len(industry_symbols)
            aggregate_rows.append({
                "universe": universe,
                "icb_code": code,
                "icb_name": next(
                    str(metadata[ticker]["icb_name"])
                    for ticker in industry_symbols
                ),
                "trading_date": trading_date,
                **gross,
                "foreign_net_volume": _paired_net(
                    symbol_rows, "foreign_buy_volume", "foreign_sell_volume"
                ),
                "foreign_net_value": _paired_net(
                    symbol_rows, "foreign_buy_value", "foreign_sell_value"
                ),
                "expected_symbol_count": expected,
                "returned_symbol_count": len({ticker for ticker, _ in entries}),
                "complete_foreign_symbol_count": complete,
                "unclassified_symbol_count": len(unclassified_symbols),
                "coverage_ratio": complete / expected if expected else 0.0,
                "status": "ok" if expected and complete == expected else "partial",
                "source": _SOURCE,
            })
        reconciliation: Dict[str, Dict[str, Any]] = {}
        classified_source_rows = [
            row
            for ticker, rows in history.items()
            if ticker not in unclassified_symbols
            for row in rows
        ]
        for field in ("foreign_buy_value", "foreign_sell_value", "matched_value"):
            source_values = [
                _number(row, field)
                for row in classified_source_rows
                if _number(row, field) is not None
            ]
            aggregate_values = [
                _number(row, field)
                for row in aggregate_rows
                if _number(row, field) is not None
            ]
            source_total = sum(source_values) if source_values else None
            aggregate_total = sum(aggregate_values) if aggregate_values else None
            reconciliation[field] = {
                "source_total": source_total,
                "aggregate_total": aggregate_total,
                "matches": (
                    source_total == aggregate_total
                    if source_total is not None and aggregate_total is not None
                    else None
                ),
            }
        if not aggregate_rows and provider_failures:
            return unavailable(
                provider_failures[0],
                requested_count=len(ticker_list),
                provider_operations=provider_operations,
            )
        complete_result = (
            bool(aggregate_rows)
            and not provider_failures
            and all(row["status"] == "ok" for row in aggregate_rows)
        )
        return {
            "status": "ok" if complete_result else ("partial" if aggregate_rows else "unavailable"),
            "data_state": "ready" if complete_result else ("partial" if aggregate_rows else "unavailable"),
            "usable": bool(aggregate_rows),
            "failure_class": None if aggregate_rows else "provider_empty",
            "universe": universe,
            "requested_symbol_count": len(ticker_list),
            "classified_symbol_count": len(ticker_list) - len(unclassified_symbols),
            "unclassified_symbol_count": len(unclassified_symbols),
            "rows": aggregate_rows,
            "current_session_status": "CURRENT_FOREIGN_STREAM_BLOCKED_SEMANTICS",
            "proprietary_industry_status": "unsupported",
            "source": _SOURCE,
            "provider_version": _PROVIDER_VERSION,
            "requested_from_date": start,
            "requested_to_date": end,
            "fetched_at": datetime.now(tz=ZoneInfo("UTC")).isoformat(),
            "cache": {"status": "miss", "age_seconds": None},
            "diagnostics": {
                "provider_operation_count": provider_operations,
                "failed_operation_count": len(provider_failures),
                "reconciliation": reconciliation,
            },
        }
