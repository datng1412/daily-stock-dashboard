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


def reset_vietnam_flow_data_capability_cache() -> None:
    """Reset the process-local direct-index capability cache for tests."""
    with _DIRECT_INDEX_CAPABILITY_LOCK:
        _DIRECT_INDEX_CAPABILITY_CACHE.clear()


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


class VietnamFlowDataService:
    """Narrow REST-only flow capabilities; ambiguous room streaming stays blocked."""

    def __init__(self, provider: Optional[SsiRestProvider] = None) -> None:
        self._router: Optional[SsiRestProviderRouter] = None
        self._initialization_failure = False
        if provider is None:
            try:
                self._router = create_ssi_rest_provider_router()
                provider = self._router
            except Exception:
                self._initialization_failure = True
        self._provider = provider

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

    def current_foreign_by_symbol(self, symbol: str) -> Dict[str, Any]:
        ticker = _symbols([symbol])[0]
        if self._provider is None:
            return {
                "status": "unavailable",
                "symbol": ticker,
                "trading_date": None,
                "freshness_status": "unavailable",
                "is_current_session": False,
                "is_provisional": False,
                "current": None,
                "latest_completed_comparison": None,
                "stream_status": "CURRENT_FOREIGN_STREAM_BLOCKED_SEMANTICS",
                "stream_reason": "SSI room buy/sell update semantics are not proven cumulative or delta.",
                "source": _SOURCE,
                "provider_version": _PROVIDER_VERSION,
                "endpoint": "securitiesSummary",
            }
        result = self._provider.get_daily_stock_price(ticker, limit=1)
        row = next((item for item in result.get("rows") or [] if isinstance(item, Mapping)), None)
        today = datetime.now(_VN_TZ).date().isoformat()
        data_date = str(row.get("date") or "") if row else None
        is_current = bool(data_date == today)
        complete = bool(row) and all(
            row.get(name) is not None
            for name in (
                "foreign_buy_volume", "foreign_sell_volume",
                "foreign_buy_value", "foreign_sell_value",
            )
        )
        current_row = dict(row) if is_current and complete else None
        return {
            "status": "ok" if current_row else "unavailable",
            "symbol": ticker,
            "trading_date": data_date,
            "freshness_status": (
                "current_session_provisional"
                if current_row
                else "previous_session_during_live_market"
                if row
                else "unavailable"
            ),
            "is_current_session": bool(current_row),
            "is_provisional": bool(current_row),
            "current": current_row,
            "latest_completed_comparison": None if current_row else (dict(row) if row else None),
            "stream_status": "CURRENT_FOREIGN_STREAM_BLOCKED_SEMANTICS",
            "stream_reason": "SSI room buy/sell update semantics are not proven cumulative or delta.",
            "source": _SOURCE,
            "provider_version": _PROVIDER_VERSION,
            "endpoint": "securitiesSummary",
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
                result = self._provider.get_market_summary(
                    normalized_scope,
                    normalized_identifier,
                    trading_date=requested_date,
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
        if bool(symbols) == bool(index_code):
            raise ValueError("provide exactly one of symbols or index_code")
        start = _iso_date(from_date, "from_date")
        end = _iso_date(to_date, "to_date")
        if date.fromisoformat(start) > date.fromisoformat(end):
            raise ValueError("from_date must not be after to_date")
        if self._provider is None:
            universe = (
                f"index:{str(index_code).strip().upper()}"
                if index_code
                else "custom_symbols"
            )
            requested_count = len(_symbols(symbols or [])) if symbols else 0
            return {
                "status": "unavailable",
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
                    "failure_class": "provider_not_configured",
                    "provider_operation_count": 0,
                },
            }
        if index_code:
            index = str(index_code).strip().upper()
            membership_result = self._provider.get_securities_by_index(index)
            member_rows = [
                row for row in membership_result.get("rows") or []
                if isinstance(row, Mapping)
            ]
            ticker_list = _symbols(row.get("symbol") for row in member_rows)
            universe = f"index:{index}"
            metadata = {
                str(row.get("symbol") or "").strip().upper(): dict(row)
                for row in member_rows
                if row.get("symbol")
            }
            summary_result = self._provider.get_securities_summary_by_index(
                index,
                from_date=start,
                to_date=end,
                limit=3000,
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
                    summary = self._provider.get_daily_stock_price(
                        ticker, from_date=start, to_date=end, limit=260
                    )
                    provider_operations += 1
                    history[ticker] = [
                        row for row in summary.get("rows") or []
                        if isinstance(row, Mapping)
                    ]
        else:
            ticker_list = _symbols(symbols or [])
            universe = "custom_symbols"
        if not index_code:
            metadata = {}
            history = {}
            provider_operations = 0
            for ticker in ticker_list:
                info = self._provider.get_security_basic_info(ticker)
                provider_operations += 1
                info_row = next((row for row in info.get("rows") or [] if isinstance(row, Mapping)), {})
                metadata[ticker] = dict(info_row)
                summary = self._provider.get_daily_stock_price(
                    ticker, from_date=start, to_date=end, limit=260
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
        return {
            "status": "ok" if aggregate_rows and all(row["status"] == "ok" for row in aggregate_rows) else ("partial" if aggregate_rows else "unavailable"),
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
                "reconciliation": reconciliation,
            },
        }
