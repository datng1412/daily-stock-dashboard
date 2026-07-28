# -*- coding: utf-8 -*-
"""Vietnam company research snapshot service.

This service composes the existing SSI-backed Vietnam watchlist contract into a
company-research page payload. News remains gated by the configured provider;
fundamentals and corporate actions remain unavailable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, Optional
from zoneinfo import ZoneInfo

from data_provider.ssi_streaming_realtime import vietnam_market_session_from_epoch
from src.services.vietnam_market_service import VietnamMarketService


NOT_IMPLEMENTED_MESSAGE = "News provider is not implemented yet."
SSI_DAILY_OHLC_SOURCE = "SSI DailyOhlc"
SSI_DAILY_STOCK_PRICE_SOURCE = "SSI DailyStockPrice"
SSI_SECURITIES_DETAILS_SOURCE = "SSI SecuritiesDetails"
SSI_SECURITIES_ENDPOINT = "securitiesByBoard?symbol="
SSI_INTRADAY_SOURCE = "SSI IntradayOhlc"
SSI_REALTIME_SOURCE = "SSI realtime contract"
SSI_TRADE_TAPE_SOURCE = "SSI trade-tape contract"
SSI_DERIVED_SOURCE = "SSI-derived"
NEWS_FUTURE_SOURCE = "NewsProvider future"
EXTERNAL_FUTURE_SOURCE = "external provider future"
VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

_CHANNEL_READY_STATES = {"ok", "ready"}
_CHANNEL_RECONNECTING_STATES = {
    "awaiting_subscription",
    "recovering",
    "reconnecting",
    "starting",
}
_CHANNEL_NO_DATA_REASONS = {
    "cache_empty",
    "stream_cache_empty",
    "subscribed_empty",
    "xtrade_cache_empty",
}
_NON_PRIMARY_ISSUE_CODES = {
    "adjusted_price_status_unknown",
    "final_close_status_unknown",
    "metadata_partial",
    "profile_partial",
}


def _vn_ticker(symbol: str) -> str:
    return (symbol or "").strip().upper().removesuffix(".VN")


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _has_value(*values: Any) -> bool:
    return any(value is not None for value in values)


def _status_for(*values: Any) -> str:
    return "ok" if _has_value(*values) else "missing"


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _date_text(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _timestamp_date(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=VN_TIMEZONE)
    return parsed.astimezone(VN_TIMEZONE).date().isoformat()


def _status_value(block: Dict[str, Any]) -> str:
    return str(block.get("status") or "").strip().lower()


def _diagnostic_status(block: Dict[str, Any], diagnostics: Dict[str, Any]) -> str:
    for key in ("stream_state", "streamState", "streaming_status", "streamingStatus"):
        value = block.get(key)
        if value in (None, ""):
            value = diagnostics.get(key)
        if value not in (None, ""):
            return str(value).strip().lower()
    return ""


def _channel_state(
    *,
    status: Dict[str, Any],
    diagnostics: Dict[str, Any],
    usable: bool,
) -> str:
    public_status = _status_value(status)
    lifecycle = _diagnostic_status(status, diagnostics)
    reason = str(
        status.get("reason_code")
        or status.get("reasonCode")
        or status.get("classification")
        or ""
    ).strip().lower()
    if usable:
        return "stale" if public_status == "stale" or lifecycle == "stale" else "ready"
    if public_status == "disabled":
        return "disabled"
    if lifecycle in _CHANNEL_RECONNECTING_STATES or reason in _CHANNEL_RECONNECTING_STATES:
        return "reconnecting"
    if reason in _CHANNEL_NO_DATA_REASONS or lifecycle in _CHANNEL_NO_DATA_REASONS:
        return "no_data"
    if public_status == "stale" or lifecycle in {"stale", "closed"}:
        return "stale"
    if public_status in {"error", "failed"}:
        return "error"
    return "unavailable"


def _capability_state(values: Iterable[Any]) -> str:
    present = [value is not None for value in values]
    if all(present):
        return "ready"
    if any(present):
        return "partial"
    return "unavailable"


def _dedupe_issues(issues: Iterable[Any]) -> list[Dict[str, Any]]:
    output: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for raw in issues:
        issue = raw if isinstance(raw, dict) else {}
        code = str(issue.get("code") or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        output.append(dict(issue))
    return output


class VietnamCompanyResearchService:
    """Build source-aware company research snapshots for Vietnam tickers."""

    def __init__(
        self,
        market_service: Optional[VietnamMarketService] = None,
        *,
        time_func: Optional[Callable[[], float]] = None,
    ) -> None:
        self.market_service = market_service or VietnamMarketService()
        self._time_func = time_func or (lambda: datetime.now(timezone.utc).timestamp())

    def get_company_research_snapshot(self, ticker: str, force_refresh: bool = False) -> Dict[str, Any]:
        symbol = _vn_ticker(str(ticker or "").strip().upper())
        if not symbol:
            return self._unavailable_payload("")

        watchlist_payload = self.market_service.build_watchlist(
            [symbol],
            force_refresh=force_refresh,
            include_intraday=True,
            include_news=True,
        )
        rows = watchlist_payload.get("watchlist") if isinstance(watchlist_payload, dict) else None
        row = rows[0] if isinstance(rows, list) and rows else None
        if not isinstance(row, dict):
            return self._unavailable_payload(symbol, errors={"market_data": "No Vietnam watchlist row returned."})

        return self._snapshot_from_watch_item(symbol, row)

    @staticmethod
    def _daily_session_state(
        *,
        completed_session_date: Optional[str],
        live_session_date: Optional[str],
        now_date: str,
        market_active: bool,
        daily_history_diagnostics: Dict[str, Any],
    ) -> tuple[str, str]:
        """Classify EOD finality separately from cache and live-event freshness."""
        if not completed_session_date:
            return "unknown", "unknown"
        if completed_session_date > now_date:
            return "unknown", "unknown"
        adapter_freshness = str(
            daily_history_diagnostics.get("freshness_status") or ""
        ).strip().lower()
        if adapter_freshness == "stale":
            return "publication_lag", "completed"
        if market_active and completed_session_date == now_date:
            return "current", "provisional"
        if live_session_date and completed_session_date == live_session_date and market_active:
            return "current", "provisional"
        if live_session_date and completed_session_date > live_session_date:
            return "unknown", "unknown"
        return "latest_completed", "completed"

    @staticmethod
    def _live_summary_detail(channels: Dict[str, str]) -> str:
        labels = {
            "last_price": "Last price",
            "order_book": "Order book",
            "trade_tape": "Trade tape",
            "intraday": "Intraday",
        }
        priority = {"ready": 0, "reconnecting": 1, "no_data": 2, "stale": 3, "unavailable": 4, "disabled": 5, "error": 6}
        ordered = sorted(
            channels.items(),
            key=lambda item: (priority.get(item[1], 9), list(labels).index(item[0])),
        )
        return ", ".join(
            f"{labels[key]} {state.replace('_', ' ')}" for key, state in ordered
        )

    @staticmethod
    def _user_warnings(values: Iterable[Any]) -> list[str]:
        suppressed = (
            "final close status is unknown",
            "adjusted/unadjusted price status is unknown",
            "indicators are based on a daily candle whose final status is unknown",
        )
        output: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            if not text or any(fragment in text.lower() for fragment in suppressed):
                continue
            if text not in seen:
                seen.add(text)
                output.append(text)
        return output

    def _snapshot_from_watch_item(self, symbol: str, row: Dict[str, Any]) -> Dict[str, Any]:
        metadata = _dict(row.get("symbol_metadata"))
        daily_stock_price = _dict(row.get("daily_stock_price"))
        if daily_stock_price:
            daily_stock_price = dict(daily_stock_price)
            daily_stock_price["source"] = SSI_DAILY_STOCK_PRICE_SOURCE
        foreign = _dict(row.get("foreign"))
        indicators = _dict(row.get("indicators"))
        bollinger = _dict(indicators.get("bollinger"))

        profile_name = _first_present(row.get("company_name"), row.get("name"), metadata.get("name"), metadata.get("name_en"))
        metadata_status = metadata.get("status")
        profile_status = (
            metadata_status
            if metadata_status in {"ok", "unavailable"}
            else "ok"
            if _has_value(profile_name, metadata.get("exchange"))
            else "unavailable"
        )
        profile_quality = metadata.get("quality_status") or (
            "partial" if profile_status == "ok" else "unavailable"
        )
        core_profile_ready = bool(
            symbol
            and _has_value(
                profile_name,
                row.get("exchange"),
                metadata.get("exchange"),
                row.get("market"),
                metadata.get("market"),
            )
        )
        optional_profile_fields = {
            "name_en": metadata.get("name_en"),
            "issuer": metadata.get("issuer"),
            "listed_date": metadata.get("listed_date"),
        }
        optional_metadata_status = (
            "complete"
            if all(value is not None for value in optional_profile_fields.values())
            else "incomplete"
        )
        profile_diagnostics = {
            **dict(metadata.get("diagnostics") or {}),
            "source_endpoint": metadata.get("source_endpoint") or SSI_SECURITIES_ENDPOINT,
            "provider_version": metadata.get("provider_version") or "v3",
            "fetched_at": metadata.get("fetched_at"),
            "cache_status": metadata.get("cache_status"),
            "missing_fields": list(metadata.get("missing_fields") or []),
        }
        profile = {
            "ticker": symbol,
            "name": profile_name,
            "name_en": metadata.get("name_en"),
            "exchange": _first_present(row.get("exchange"), metadata.get("exchange"), row.get("market")),
            "market": _first_present(row.get("market"), metadata.get("market")),
            # Classification stays provider-backed. Do not infer one label from
            # the other or from the ticker.
            "industry": metadata.get("industry"),
            "sector": metadata.get("sector"),
            "security_type": _first_present(row.get("security_type"), metadata.get("security_type")),
            "issuer": _first_present(row.get("issuer"), metadata.get("issuer")),
            "lot_size": _first_present(row.get("lot_size"), metadata.get("lot_size")),
            "listed_shares": _first_present(row.get("listed_shares"), metadata.get("listed_shares")),
            "listed_date": _first_present(row.get("listed_date"), metadata.get("listed_date")),
            "source": _first_present(metadata.get("source_label"), metadata.get("source")) or SSI_SECURITIES_DETAILS_SOURCE,
            "source_endpoint": metadata.get("source_endpoint") or SSI_SECURITIES_ENDPOINT,
            "provider_version": metadata.get("provider_version") or "v3",
            "fetched_at": metadata.get("fetched_at"),
            "cache_status": metadata.get("cache_status"),
            "data_state": (
                "ready"
                if core_profile_ready
                else "unavailable"
            ),
            "failure_class": metadata.get("failure_class"),
            "status": profile_status,
            "quality_status": profile_quality,
            "completeness": metadata.get("completeness"),
            "missing_fields": list(metadata.get("missing_fields") or []),
            "field_coverage": dict(metadata.get("field_coverage") or {}),
            "diagnostics": profile_diagnostics,
            "core_profile_status": "ready" if core_profile_ready else "unavailable",
            "optional_metadata_status": optional_metadata_status,
            "classification_source": (
                _first_present(metadata.get("source_label"), metadata.get("source"))
                if _has_value(metadata.get("industry"), metadata.get("sector"))
                else None
            ),
        }
        if profile["source"] == "SSI":
            profile["source"] = SSI_SECURITIES_DETAILS_SOURCE

        # V3 securities-summary currently normalizes these fields as null.
        # The ssi_* compatibility keys are copies of the same DailyStockPrice
        # fields. Never fall through to the exchange-derived price_limit block.
        reference_price = _first_present(daily_stock_price.get("reference_price"), row.get("ssi_reference_price"))
        ceiling_price = _first_present(daily_stock_price.get("ceiling_price"), row.get("ssi_ceiling_price"))
        floor_price = _first_present(daily_stock_price.get("floor_price"), row.get("ssi_floor_price"))
        latest_price_source = row.get("latest_price_source") or SSI_DAILY_OHLC_SOURCE
        price_date = _first_present(row.get("latest_price_date"), row.get("price_date"), row.get("ohlcv_date"), row.get("date"))
        price = {
            "latest_price": row.get("latest_price"),
            "daily_close": row.get("daily_close"),
            "reference_price": reference_price,
            "ceiling_price": ceiling_price,
            "floor_price": floor_price,
            "price_date": price_date,
            "source": latest_price_source,
            "canonical_source": latest_price_source,
            "reference_source": SSI_DAILY_STOCK_PRICE_SOURCE if reference_price is not None else None,
            "reference_price_source": SSI_DAILY_STOCK_PRICE_SOURCE if reference_price is not None else None,
            "ceiling_price_source": SSI_DAILY_STOCK_PRICE_SOURCE if ceiling_price is not None else None,
            "floor_price_source": SSI_DAILY_STOCK_PRICE_SOURCE if floor_price is not None else None,
            "status": _status_for(row.get("latest_price"), row.get("daily_close"), reference_price, ceiling_price, floor_price),
        }

        trading_value = row.get("amount")
        trading_stats = {
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": row.get("close"),
            "volume": row.get("volume"),
            "value": trading_value,
            "source": SSI_DAILY_OHLC_SOURCE,
            "status": _status_for(row.get("open"), row.get("high"), row.get("low"), row.get("close"), row.get("volume"), trading_value),
        }

        foreign_flow = {
            "foreign_buy_volume": _first_present(daily_stock_price.get("foreign_buy_volume"), foreign.get("buy")),
            "foreign_sell_volume": _first_present(daily_stock_price.get("foreign_sell_volume"), foreign.get("sell")),
            "foreign_net_volume": _first_present(daily_stock_price.get("foreign_net_volume"), row.get("ssi_foreign_net_volume"), foreign.get("net")),
            "foreign_buy_value": _first_present(daily_stock_price.get("foreign_buy_value"), foreign.get("buy_value")),
            "foreign_sell_value": _first_present(daily_stock_price.get("foreign_sell_value"), foreign.get("sell_value")),
            "foreign_net_value": _first_present(daily_stock_price.get("foreign_net_value"), row.get("ssi_foreign_net_value"), foreign.get("net_value")),
            "date": _first_present(daily_stock_price.get("date"), row.get("daily_stock_price_date"), foreign.get("date")),
            "date_match": _first_present(daily_stock_price.get("date_match"), row.get("daily_stock_price_date_match"), foreign.get("date_match")),
            "source": SSI_DAILY_STOCK_PRICE_SOURCE,
        }
        foreign_flow["volume_unit"] = (
            "shares"
            if _has_value(
                foreign_flow["foreign_buy_volume"],
                foreign_flow["foreign_sell_volume"],
                foreign_flow["foreign_net_volume"],
            )
            else None
        )
        foreign_flow["value_unit"] = (
            "VND"
            if _has_value(
                foreign_flow["foreign_buy_value"],
                foreign_flow["foreign_sell_value"],
                foreign_flow["foreign_net_value"],
            )
            else None
        )
        foreign_flow["status"] = _status_for(
            foreign_flow["foreign_buy_volume"],
            foreign_flow["foreign_sell_volume"],
            foreign_flow["foreign_net_volume"],
            foreign_flow["foreign_buy_value"],
            foreign_flow["foreign_sell_value"],
            foreign_flow["foreign_net_value"],
        )

        technical = {
            "ma20": indicators.get("ma20"),
            "ma50": indicators.get("ma50"),
            "rsi14": _first_present(indicators.get("rsi14_wilder"), indicators.get("rsi14")),
            "bollinger_upper": bollinger.get("upper"),
            "bollinger_middle": bollinger.get("middle"),
            "bollinger_lower": bollinger.get("lower"),
            "high_52w": indicators.get("high_52w"),
            "high_52w_date": indicators.get("high_52w_date"),
            "low_52w": indicators.get("low_52w"),
            "low_52w_date": indicators.get("low_52w_date"),
            "high_low_52w_history_count": indicators.get("high_low_52w_history_count"),
            "high_low_52w_coverage_status": indicators.get("high_low_52w_coverage_status"),
            "avg_volume_10d": indicators.get("avg_volume_10d"),
            "avg_volume_10d_history_count": indicators.get("avg_volume_10d_history_count"),
            "avg_volume_10d_coverage_status": indicators.get("avg_volume_10d_coverage_status"),
            "avg_volume_3m": indicators.get("avg_volume_3m"),
            "avg_volume_3m_history_count": indicators.get("avg_volume_3m_history_count"),
            "avg_volume_3m_coverage_status": indicators.get("avg_volume_3m_coverage_status"),
            "price_vs_reference_pct": indicators.get("price_vs_reference_pct"),
            "price_vs_reference_status": indicators.get("price_vs_reference_status"),
            "daily_range_pct": indicators.get("daily_range_pct"),
            "daily_range_status": indicators.get("daily_range_status"),
            "ssi_derived_metrics_status": indicators.get("ssi_derived_metrics_status"),
            "ssi_derived_metrics_source": indicators.get("ssi_derived_metrics_source"),
            "source": SSI_DERIVED_SOURCE,
        }
        technical["status"] = _status_for(
            technical["ma20"],
            technical["ma50"],
            technical["rsi14"],
            technical["bollinger_upper"],
            technical["bollinger_middle"],
            technical["bollinger_lower"],
            technical["high_52w"],
            technical["low_52w"],
            technical["avg_volume_10d"],
            technical["avg_volume_3m"],
            technical["price_vs_reference_pct"],
            technical["daily_range_pct"],
        )
        intraday_status = _dict(row.get("intraday_status"))
        intraday_diagnostics = _dict(intraday_status.get("diagnostics"))
        intraday_pulse = row.get("intraday_pulse") if isinstance(row.get("intraday_pulse"), dict) else None
        intraday = {
            "candles": list(row.get("intraday_candles") or []),
            "pulse": intraday_pulse,
            "requested_timeframe": row.get("intraday_requested_timeframe") or row.get("intraday_timeframe"),
            "granularity": row.get("intraday_granularity"),
            "actual_granularity": row.get("intraday_actual_granularity") or row.get("intraday_granularity"),
            "granularity_seconds": row.get("intraday_granularity_seconds"),
            "actual_granularity_seconds": row.get("intraday_actual_granularity_seconds") or row.get("intraday_granularity_seconds"),
            "granularity_label": row.get("intraday_granularity_label"),
            "cadence_status": row.get("intraday_cadence_status") or intraday_status.get("intraday_cadence_status"),
            "latest_date": row.get("intraday_latest_date"),
            "daily_price_date": row.get("daily_price_date"),
            "target_session_date": row.get("target_session_date")
            or intraday_status.get("target_session_date"),
            "session_basis": row.get("session_basis")
            or intraday_status.get("session_basis"),
            "date_match": row.get("date_match"),
            "source": SSI_INTRADAY_SOURCE,
            "status": intraday_status.get("status") or "unavailable",
            "message": intraday_status.get("message") or row.get("intraday_warning"),
            "diagnostics": intraday_diagnostics,
        }
        realtime_status = dict(_dict(row.get("realtime_status")))
        row_diagnostics = _dict(row.get("diagnostics"))
        realtime_diagnostics = _dict(row_diagnostics.get("realtime")) or _dict(realtime_status.pop("diagnostics", None))
        realtime_snapshot = row.get("realtime_snapshot") if isinstance(row.get("realtime_snapshot"), dict) else None
        realtime_status = {
            **realtime_status,
            "source": realtime_status.get("source") or SSI_REALTIME_SOURCE,
            "status": realtime_status.get("status") or "unavailable",
            "message": realtime_status.get("message"),
        }
        trade_tape_status = dict(_dict(row.get("trade_tape_status")))
        trade_tape_payload = row.get("trade_tape")
        trade_tape_rows = trade_tape_payload if isinstance(trade_tape_payload, list) else _dict(trade_tape_payload).get("trades")
        trade_tape_diagnostics = _dict(row_diagnostics.get("trade_tape")) or _dict(
            trade_tape_status.pop("diagnostics", None)
        )
        trade_tape = list(trade_tape_rows or [])
        trade_tape_status = {
            **trade_tape_status,
            "source": trade_tape_status.get("source") or SSI_TRADE_TAPE_SOURCE,
            "status": trade_tape_status.get("status") or _dict(trade_tape_payload).get("status") or "unavailable",
            "message": trade_tape_status.get("message"),
        }
        order_book_status = dict(_dict(row.get("order_book_status")))
        order_book_payload = row.get("order_book")
        order_book = dict(order_book_payload) if isinstance(order_book_payload, dict) else None
        order_book_diagnostics = _dict(row_diagnostics.get("order_book")) or _dict(
            order_book_status.pop("diagnostics", None)
        )
        order_book_status = {
            **order_book_status,
            "source": order_book_status.get("source") or "SSI X-QUOTE",
            "status": order_book_status.get("status") or "unavailable",
            "message": order_book_status.get("message"),
        }

        now_epoch = float(self._time_func())
        now_local = datetime.fromtimestamp(now_epoch, timezone.utc).astimezone(VN_TIMEZONE)
        market_session = vietnam_market_session_from_epoch(now_epoch)
        completed_session_date = _date_text(price_date)
        provider_event_time = _first_present(
            _dict(order_book).get("stream_timestamp"),
            _dict(order_book).get("received_at"),
            _dict(realtime_snapshot).get("snapshot_time"),
            _dict(realtime_snapshot).get("realtime_time"),
            _dict(realtime_snapshot).get("stream_timestamp"),
            _dict(trade_tape[0] if trade_tape else {}).get("timestamp"),
        )
        live_session_date = _first_present(
            _date_text(_dict(order_book).get("trading_date")),
            _timestamp_date(_dict(order_book).get("stream_timestamp")),
            _timestamp_date(_dict(realtime_snapshot).get("snapshot_time")),
            _timestamp_date(_dict(realtime_snapshot).get("realtime_time")),
            _timestamp_date(_dict(trade_tape[0] if trade_tape else {}).get("timestamp")),
        )
        daily_history_diagnostics = _dict(row_diagnostics.get("daily_history"))
        source_freshness, final_close_status = self._daily_session_state(
            completed_session_date=completed_session_date,
            live_session_date=live_session_date,
            now_date=now_local.date().isoformat(),
            market_active=bool(market_session.get("market_session_active")),
            daily_history_diagnostics=daily_history_diagnostics,
        )
        raw_adjustment_status = str(
            row.get("adjusted_price_status")
            or row.get("price_adjustment_status")
            or ""
        ).strip().lower()
        if raw_adjustment_status in {"adjusted", "unadjusted"}:
            adjustment_status = raw_adjustment_status
        elif raw_adjustment_status in {"", "unknown", "not_provided"}:
            adjustment_status = "not_provided"
        else:
            adjustment_status = "unknown"

        cache_ages = [
            value
            for value in (
                _dict(order_book).get("age_seconds"),
                _dict(realtime_snapshot).get("age_seconds"),
                _dict(trade_tape[0] if trade_tape else {}).get("age_seconds"),
            )
            if isinstance(value, (int, float)) and value >= 0
        ]
        session_context = {
            "completed_session_date": completed_session_date,
            "live_session_date": live_session_date,
            "provider_event_time": provider_event_time,
            "fetched_at": datetime.fromtimestamp(now_epoch, timezone.utc).isoformat(),
            "cache_age_seconds": min(cache_ages) if cache_ages else None,
            "session_phase": market_session.get("market_session"),
            "session_phase_label": market_session.get("market_session_label"),
            "market_session_active": bool(market_session.get("market_session_active")),
            "holiday_aware": bool(market_session.get("market_session_holiday_aware")),
            "source_freshness": source_freshness,
        }
        price.update(
            {
                "completed_session_date": completed_session_date,
                "final_close_status": final_close_status,
                "adjustment_status": adjustment_status,
                "source_freshness": source_freshness,
            }
        )

        live_channels = {
            "last_price": _channel_state(
                status=realtime_status,
                diagnostics=realtime_diagnostics,
                usable=realtime_snapshot is not None
                and _has_value(
                    realtime_snapshot.get("price"),
                    realtime_snapshot.get("realtime_price"),
                ),
            ),
            "order_book": _channel_state(
                status=order_book_status,
                diagnostics=order_book_diagnostics,
                usable=bool(order_book and (order_book.get("bids") or order_book.get("asks"))),
            ),
            "trade_tape": _channel_state(
                status=trade_tape_status,
                diagnostics=trade_tape_diagnostics,
                usable=bool(trade_tape),
            ),
            "intraday": _channel_state(
                status=intraday_status,
                diagnostics=intraday_diagnostics,
                usable=bool(intraday.get("candles") and intraday.get("pulse")),
            ),
        }
        usable_live_channels = sum(
            state in {"ready", "stale"} for state in live_channels.values()
        )
        live_market_status = (
            "ready"
            if usable_live_channels == len(live_channels)
            else "partial"
            if usable_live_channels
            else "unavailable"
        )
        live_market = {
            "status": live_market_status,
            "channels": live_channels,
            "usable_channel_count": usable_live_channels,
            "session_date": live_session_date,
            "provider_event_time": provider_event_time,
        }

        daily_stock_price_capabilities = {
            "daily_price_limits_status": _capability_state(
                (reference_price, ceiling_price, floor_price)
            ),
            "matched_stats_status": _capability_state(
                (
                    daily_stock_price.get("matched_volume"),
                    daily_stock_price.get("matched_value"),
                )
            ),
            "put_through_status": _capability_state(
                (
                    daily_stock_price.get("put_through_volume"),
                    daily_stock_price.get("put_through_value"),
                )
            ),
            "foreign_flow_status": "ready" if foreign_flow["status"] == "ok" else "unavailable",
            "session_metadata_status": "ready" if daily_stock_price.get("date") else "unavailable",
        }
        capability_values = list(daily_stock_price_capabilities.values())
        daily_stock_price_capabilities["overall_status"] = (
            "ready"
            if all(value == "ready" for value in capability_values)
            else "partial"
            if any(value in {"ready", "partial"} for value in capability_values)
            else "unavailable"
        )

        existing_quality = _dict(row.get("data_quality_summary"))
        detailed_issues = _dedupe_issues(existing_quality.get("issues") or [])
        primary_issues = [
            issue
            for issue in detailed_issues
            if str(issue.get("code") or "") not in _NON_PRIMARY_ISSUE_CODES
        ]
        issue_codes = [str(issue["code"]) for issue in detailed_issues]
        quality_summary = {
            "overall_status": (
                "unavailable"
                if price["status"] != "ok"
                else "partial"
                if live_market_status != "ready"
                or profile["core_profile_status"] != "ready"
                or primary_issues
                else "ready"
            ),
            "groups": [
                {
                    "key": "daily_data",
                    "label": "Daily data",
                    "status": "ready" if price["status"] == "ok" else "unavailable",
                    "detail": (
                        f"Latest completed {completed_session_date}"
                        if source_freshness == "latest_completed" and completed_session_date
                        else source_freshness.replace("_", " ")
                    ),
                },
                {
                    "key": "live_market",
                    "label": "Live market",
                    "status": live_market_status,
                    "detail": self._live_summary_detail(live_channels),
                },
                {
                    "key": "company_metadata",
                    "label": "Company metadata",
                    "status": profile["core_profile_status"],
                    "detail": (
                        "Core profile ready · Optional metadata incomplete"
                        if profile["core_profile_status"] == "ready"
                        and optional_metadata_status == "incomplete"
                        else "Core profile ready"
                        if profile["core_profile_status"] == "ready"
                        else "Core profile unavailable"
                    ),
                },
            ],
            "issue_codes": issue_codes,
            "primary_issues": primary_issues,
        }
        data_quality_summary = {
            **existing_quality,
            "overall_status": quality_summary["overall_status"],
            "issues": detailed_issues,
            "issue_codes": issue_codes,
            "checks": {
                **_dict(existing_quality.get("checks")),
                "final_close_status": final_close_status,
                "adjusted_price_status": adjustment_status,
                "realtime": live_channels["last_price"],
                "order_book": live_channels["order_book"],
                "trade_tape": live_channels["trade_tape"],
                "intraday": live_channels["intraday"],
                "profile": profile["core_profile_status"],
            },
        }
        market_blocks_ok = any(block.get("status") == "ok" for block in [profile, price, trading_stats, foreign_flow, technical])
        status = "ok" if price["status"] == "ok" and trading_stats["status"] == "ok" else "partial" if market_blocks_ok else "unavailable"

        errors: Dict[str, Any] = {}
        if row.get("error"):
            errors["market_data"] = row.get("error")

        news = self._news_block(row)
        return {
            "ticker": symbol,
            "status": status,
            "session_context": session_context,
            "live_market": live_market,
            "profile": profile,
            "price": price,
            "trading_stats": trading_stats,
            "daily_stock_price": daily_stock_price,
            "foreign_flow": foreign_flow,
            "technical": technical,
            "intraday": intraday,
            "realtime_snapshot": realtime_snapshot,
            "realtime_status": realtime_status,
            "trade_tape": trade_tape,
            "trade_tape_status": trade_tape_status,
            "order_book_source": row.get("order_book_source") or order_book_status.get("source"),
            "order_book": order_book,
            "order_book_status": order_book_status,
            "diagnostics": {
                "session": session_context,
                "adjustment": {
                    "status": adjustment_status,
                    "raw_status": raw_adjustment_status or None,
                    "source": SSI_DAILY_OHLC_SOURCE,
                },
                "live_channels": live_channels,
                "daily_stock_price_capabilities": daily_stock_price_capabilities,
                "profile": {
                    "core_profile_status": profile["core_profile_status"],
                    "optional_metadata_status": optional_metadata_status,
                    "classification_source": profile["classification_source"],
                    "source_endpoint": profile["source_endpoint"],
                    "provider_version": profile["provider_version"],
                    "fetched_at": profile["fetched_at"],
                    "cache_status": profile["cache_status"],
                    "missing_fields": profile["missing_fields"],
                },
                "quality_issues": detailed_issues,
                "realtime": realtime_diagnostics,
                "trade_tape": trade_tape_diagnostics,
                "order_book": order_book_diagnostics,
            },
            "source_coverage": self._source_coverage(
                profile,
                price,
                trading_stats,
                foreign_flow,
                technical,
                daily_stock_price,
                intraday,
                realtime_status,
                trade_tape_status,
                news,
                order_book_status=order_book_status,
            ),
            "news": news,
            "financials": self._placeholder("not_implemented", EXTERNAL_FUTURE_SOURCE),
            "events": self._placeholder("not_implemented", EXTERNAL_FUTURE_SOURCE),
            "quality_summary": quality_summary,
            "data_quality_summary": data_quality_summary,
            "warnings": self._user_warnings(row.get("warnings") or []),
            "errors": errors,
        }

    def _source_coverage(
        self,
        profile: Dict[str, Any],
        price: Dict[str, Any],
        trading_stats: Dict[str, Any],
        foreign_flow: Dict[str, Any],
        technical: Dict[str, Any],
        daily_stock_price: Dict[str, Any],
        intraday: Optional[Dict[str, Any]] = None,
        realtime_status: Optional[Dict[str, Any]] = None,
        trade_tape_status: Optional[Dict[str, Any]] = None,
        news: Optional[Dict[str, Any]] = None,
        order_book_status: Optional[Dict[str, Any]] = None,
    ) -> list[Dict[str, Any]]:
        has_daily_stock_price_fields = any(
            price.get(field) is not None
            for field in ("reference_price", "ceiling_price", "floor_price")
        )
        daily_stock_status = (
            str(daily_stock_price.get("quality_status") or "ok")
            if daily_stock_price.get("status") == "ok"
            else "ok"
            if foreign_flow.get("status") == "ok" or has_daily_stock_price_fields
            else "missing"
        )
        intraday_status = _dict(intraday).get("status") or "unavailable"
        realtime_status_value = _dict(realtime_status).get("status") or "unavailable"
        trade_tape_status_value = _dict(trade_tape_status).get("status") or "unavailable"
        order_book_status_value = _dict(order_book_status).get("status") or "unavailable"
        return [
            {"group": "Prices", "block": "Daily OHLCV", "source": SSI_DAILY_OHLC_SOURCE, "status": "ok" if technical.get("status") == "ok" or trading_stats.get("status") == "ok" else "unavailable"},
            {"group": "Prices", "block": "Daily stock price", "source": SSI_DAILY_STOCK_PRICE_SOURCE, "status": daily_stock_status},
            {"group": "Live market", "block": "Intraday OHLCV", "source": SSI_INTRADAY_SOURCE, "status": intraday_status},
            {"group": "Live market", "block": "Realtime snapshot", "source": SSI_REALTIME_SOURCE, "status": realtime_status_value},
            {"group": "Live market", "block": "Order book", "source": _dict(order_book_status).get("source") or "SSI X-QUOTE", "status": order_book_status_value},
            {"group": "Live market", "block": "Trade tape", "source": SSI_TRADE_TAPE_SOURCE, "status": trade_tape_status_value},
            {
                "group": "Company",
                "block": "Profile",
                "source": profile.get("source") or SSI_SECURITIES_DETAILS_SOURCE,
                "status": profile.get("core_profile_status") or profile.get("status", "unavailable"),
            },
            {
                "group": "Company",
                "block": "Optional metadata",
                "source": profile.get("source") or SSI_SECURITIES_DETAILS_SOURCE,
                "status": profile.get("optional_metadata_status") or "incomplete",
            },
            {
                "group": "News",
                "block": "News",
                "source": _dict(news).get("source") or NEWS_FUTURE_SOURCE,
                "status": _dict(news).get("status") or "not_implemented",
            },
        ]

    def _placeholder(self, status: str, source: Optional[str], message: Optional[str] = None) -> Dict[str, Any]:
        payload = {"items": [], "status": status, "source": source}
        if message is not None:
            payload["message"] = message
        return payload

    def _news_block(self, row: Dict[str, Any]) -> Dict[str, Any]:
        status = _dict(row.get("news_status"))
        state = str(status.get("status") or "not_implemented")
        if state not in {"disabled", "unavailable", "ok"}:
            return self._placeholder("not_implemented", NEWS_FUTURE_SOURCE, NOT_IMPLEMENTED_MESSAGE)
        payload = self._placeholder(
            state,
            status.get("source") or (NEWS_FUTURE_SOURCE if state != "unavailable" else None),
            status.get("message"),
        )
        payload["items"] = list(row.get("news") or [])
        return payload

    def _unavailable_payload(self, symbol: str, errors: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        profile = {
            "ticker": symbol,
            "name": None,
            "name_en": None,
            "exchange": None,
            "market": None,
            "industry": None,
            "sector": None,
            "security_type": None,
            "issuer": None,
            "lot_size": None,
            "listed_shares": None,
            "listed_date": None,
            "source": SSI_SECURITIES_DETAILS_SOURCE,
            "source_endpoint": SSI_SECURITIES_ENDPOINT,
            "provider_version": "v3",
            "fetched_at": None,
            "cache_status": "unavailable",
            "data_state": "unavailable",
            "failure_class": "provider_unavailable",
            "status": "unavailable",
            "quality_status": "unavailable",
            "completeness": 0.0,
            "missing_fields": [],
            "field_coverage": {},
            "diagnostics": {},
            "core_profile_status": "unavailable",
            "optional_metadata_status": "incomplete",
            "classification_source": None,
        }
        missing_price = {
            "latest_price": None,
            "daily_close": None,
            "reference_price": None,
            "ceiling_price": None,
            "floor_price": None,
            "price_date": None,
            "source": SSI_DAILY_OHLC_SOURCE,
            "canonical_source": SSI_DAILY_OHLC_SOURCE,
            "reference_source": SSI_DAILY_STOCK_PRICE_SOURCE,
            "reference_price_source": None,
            "ceiling_price_source": None,
            "floor_price_source": None,
            "completed_session_date": None,
            "final_close_status": "unknown",
            "adjustment_status": "not_provided",
            "source_freshness": "unknown",
            "status": "missing",
        }
        missing_trading = {
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "volume": None,
            "value": None,
            "source": SSI_DAILY_OHLC_SOURCE,
            "status": "missing",
        }
        missing_foreign = {
            "foreign_buy_volume": None,
            "foreign_sell_volume": None,
            "foreign_net_volume": None,
            "foreign_buy_value": None,
            "foreign_sell_value": None,
            "foreign_net_value": None,
            "date": None,
            "date_match": "unavailable",
            "volume_unit": None,
            "value_unit": None,
            "source": SSI_DAILY_STOCK_PRICE_SOURCE,
            "status": "missing",
        }
        missing_daily_stock_price = {
            "status": "unavailable",
            "quality_status": "unavailable",
            "source": SSI_DAILY_STOCK_PRICE_SOURCE,
            "date": None,
            "date_match": "unavailable",
            "staleness_reason": "SSI DailyStockPrice enrichment is unavailable.",
            "missing_fields": [],
            "field_coverage": {},
            "units": {},
            "diagnostics": {},
        }
        missing_technical = {
            "ma20": None,
            "ma50": None,
            "rsi14": None,
            "bollinger_upper": None,
            "bollinger_middle": None,
            "bollinger_lower": None,
            "high_52w": None,
            "high_52w_date": None,
            "low_52w": None,
            "low_52w_date": None,
            "high_low_52w_history_count": 0,
            "high_low_52w_coverage_status": "insufficient",
            "avg_volume_10d": None,
            "avg_volume_10d_history_count": 0,
            "avg_volume_10d_coverage_status": "insufficient",
            "avg_volume_3m": None,
            "avg_volume_3m_history_count": 0,
            "avg_volume_3m_coverage_status": "insufficient",
            "price_vs_reference_pct": None,
            "price_vs_reference_status": "daily_close_unavailable",
            "daily_range_pct": None,
            "daily_range_status": "insufficient",
            "ssi_derived_metrics_status": "insufficient",
            "ssi_derived_metrics_source": "SSI DailyOhlc + SSI DailyStockPrice",
            "source": SSI_DERIVED_SOURCE,
            "status": "missing",
        }
        missing_intraday = {
            "candles": [],
            "pulse": None,
            "granularity": "unknown",
            "actual_granularity": "unknown",
            "granularity_seconds": None,
            "actual_granularity_seconds": None,
            "granularity_label": "provider-returned",
            "cadence_status": "unavailable",
            "latest_date": None,
            "daily_price_date": None,
            "date_match": "unknown",
            "source": SSI_INTRADAY_SOURCE,
            "status": "unavailable",
            "message": "SSI intraday unavailable.",
        }
        missing_realtime_status = {
            "source": SSI_REALTIME_SOURCE,
            "status": "unavailable",
            "message": "SSI realtime unavailable.",
        }
        missing_trade_tape_status = {
            "source": SSI_TRADE_TAPE_SOURCE,
            "status": "unavailable",
            "message": "SSI trade tape unavailable.",
        }
        return {
            "ticker": symbol,
            "status": "unavailable",
            "session_context": {
                "completed_session_date": None,
                "live_session_date": None,
                "provider_event_time": None,
                "fetched_at": None,
                "cache_age_seconds": None,
                "session_phase": "unknown",
                "source_freshness": "unknown",
            },
            "live_market": {
                "status": "unavailable",
                "channels": {
                    "last_price": "unavailable",
                    "order_book": "unavailable",
                    "trade_tape": "unavailable",
                    "intraday": "unavailable",
                },
                "usable_channel_count": 0,
            },
            "profile": profile,
            "price": missing_price,
            "trading_stats": missing_trading,
            "daily_stock_price": missing_daily_stock_price,
            "foreign_flow": missing_foreign,
            "technical": missing_technical,
            "intraday": missing_intraday,
            "realtime_snapshot": None,
            "realtime_status": missing_realtime_status,
            "trade_tape": [],
            "trade_tape_status": missing_trade_tape_status,
            "order_book_source": "SSI X-QUOTE",
            "order_book": None,
            "order_book_status": {
                "source": "SSI X-QUOTE",
                "status": "unavailable",
                "message": "SSI order book unavailable.",
            },
            "diagnostics": {
                "realtime": {},
                "trade_tape": {},
                "order_book": {},
            },
            "source_coverage": self._source_coverage(
                profile,
                missing_price,
                missing_trading,
                missing_foreign,
                missing_technical,
                missing_daily_stock_price,
                missing_intraday,
                missing_realtime_status,
                missing_trade_tape_status,
            ),
            "news": self._placeholder("not_implemented", NEWS_FUTURE_SOURCE, NOT_IMPLEMENTED_MESSAGE),
            "financials": self._placeholder("not_implemented", EXTERNAL_FUTURE_SOURCE),
            "events": self._placeholder("not_implemented", EXTERNAL_FUTURE_SOURCE),
            "data_quality_summary": {
                "overall_status": "unavailable",
                "canonical_price_source": "SSI DailyOhlc",
                "issues": [
                    {
                        "code": "daily_ohlc_unavailable",
                        "severity": "warning",
                        "message": "SSI DailyOhlc data is unavailable.",
                        "fields": {},
                    }
                ],
                "checks": {
                    "daily_ohlc": "unavailable",
                    "daily_stock_price": "unavailable",
                    "final_close_status": "unknown",
                    "adjusted_price_status": "unknown",
                    "intraday": "unavailable",
                    "realtime": "unavailable",
                    "trade_tape": "unavailable",
                    "profile": "unavailable",
                    "news": "not_implemented",
                },
            },
            "quality_summary": {
                "overall_status": "unavailable",
                "groups": [
                    {"key": "daily_data", "label": "Daily data", "status": "unavailable", "detail": "unknown"},
                    {"key": "live_market", "label": "Live market", "status": "unavailable", "detail": "No usable live channels"},
                    {"key": "company_metadata", "label": "Company metadata", "status": "unavailable", "detail": "Core profile unavailable"},
                ],
                "issue_codes": ["daily_ohlc_unavailable"],
                "primary_issues": [],
            },
            "warnings": [],
            "errors": errors or {},
        }


def get_company_research_snapshot(ticker: str, force_refresh: bool = False) -> Dict[str, Any]:
    """Return a Phase 1 Vietnam company research snapshot."""
    return VietnamCompanyResearchService().get_company_research_snapshot(ticker, force_refresh=force_refresh)
