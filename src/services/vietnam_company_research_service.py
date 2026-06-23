# -*- coding: utf-8 -*-
"""Vietnam company research snapshot service.

This service composes the existing SSI-backed Vietnam watchlist contract into a
company-research page payload. It intentionally does not fetch news,
fundamentals, or corporate actions in Phase 1.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.vietnam_market_service import VietnamMarketService


NOT_IMPLEMENTED_MESSAGE = "News provider is not implemented yet."


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


class VietnamCompanyResearchService:
    """Build source-aware company research snapshots for Vietnam tickers."""

    def __init__(self, market_service: Optional[VietnamMarketService] = None) -> None:
        self.market_service = market_service or VietnamMarketService()

    def get_company_research_snapshot(self, ticker: str, force_refresh: bool = False) -> Dict[str, Any]:
        symbol = _vn_ticker(str(ticker or "").strip().upper())
        if not symbol:
            return self._unavailable_payload("")

        watchlist_payload = self.market_service.build_watchlist(
            [symbol],
            force_refresh=force_refresh,
            include_intraday=True,
        )
        rows = watchlist_payload.get("watchlist") if isinstance(watchlist_payload, dict) else None
        row = rows[0] if isinstance(rows, list) and rows else None
        if not isinstance(row, dict):
            return self._unavailable_payload(symbol, errors={"market_data": "No Vietnam watchlist row returned."})

        return self._snapshot_from_watch_item(symbol, row)

    def _snapshot_from_watch_item(self, symbol: str, row: Dict[str, Any]) -> Dict[str, Any]:
        metadata = _dict(row.get("symbol_metadata"))
        daily_stock_price = _dict(row.get("daily_stock_price"))
        price_limit = _dict(row.get("price_limit"))
        foreign = _dict(row.get("foreign"))
        indicators = _dict(row.get("indicators"))
        bollinger = _dict(indicators.get("bollinger"))

        profile_name = _first_present(row.get("company_name"), row.get("name"), metadata.get("name"), metadata.get("name_en"))
        profile = {
            "ticker": symbol,
            "name": profile_name,
            "exchange": _first_present(row.get("exchange"), metadata.get("exchange"), row.get("market")),
            "industry": None,
            "source": "SSI",
            "status": "ok" if metadata.get("status") == "ok" or _has_value(profile_name, row.get("exchange"), metadata.get("exchange")) else "missing",
        }

        reference_price = _first_present(daily_stock_price.get("reference_price"), row.get("ssi_reference_price"), price_limit.get("reference_price"))
        ceiling_price = _first_present(daily_stock_price.get("ceiling_price"), row.get("ssi_ceiling_price"), price_limit.get("ceiling_price"))
        floor_price = _first_present(daily_stock_price.get("floor_price"), row.get("ssi_floor_price"), price_limit.get("floor_price"))
        price_date = _first_present(row.get("latest_price_date"), row.get("price_date"), row.get("ohlcv_date"), row.get("date"))
        price = {
            "latest_price": row.get("latest_price"),
            "daily_close": row.get("daily_close"),
            "reference_price": reference_price,
            "ceiling_price": ceiling_price,
            "floor_price": floor_price,
            "price_date": price_date,
            "source": "SSI DailyOhlc + SSI DailyStockPrice",
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
            "source": "SSI DailyOhlc",
            "status": _status_for(row.get("open"), row.get("high"), row.get("low"), row.get("close"), row.get("volume"), trading_value),
        }

        foreign_flow = {
            "foreign_buy_volume": _first_present(daily_stock_price.get("foreign_buy_volume"), foreign.get("buy")),
            "foreign_sell_volume": _first_present(daily_stock_price.get("foreign_sell_volume"), foreign.get("sell")),
            "foreign_net_volume": _first_present(daily_stock_price.get("foreign_net_volume"), row.get("ssi_foreign_net_volume"), foreign.get("net")),
            "foreign_buy_value": _first_present(daily_stock_price.get("foreign_buy_value"), foreign.get("buy_value")),
            "foreign_sell_value": _first_present(daily_stock_price.get("foreign_sell_value"), foreign.get("sell_value")),
            "foreign_net_value": _first_present(daily_stock_price.get("foreign_net_value"), row.get("ssi_foreign_net_value"), foreign.get("net_value")),
            "source": "SSI DailyOhlc + SSI DailyStockPrice",
        }
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
            "source": "derived_from_ssi_ohlcv",
        }
        technical["status"] = _status_for(
            technical["ma20"],
            technical["ma50"],
            technical["rsi14"],
            technical["bollinger_upper"],
            technical["bollinger_middle"],
            technical["bollinger_lower"],
        )
        intraday_status = _dict(row.get("intraday_status"))
        intraday = {
            "candles": list(row.get("intraday_candles") or []),
            "pulse": _dict(row.get("intraday_pulse")),
            "requested_timeframe": row.get("intraday_requested_timeframe") or row.get("intraday_timeframe"),
            "granularity": row.get("intraday_granularity"),
            "actual_granularity": row.get("intraday_actual_granularity") or row.get("intraday_granularity"),
            "granularity_seconds": row.get("intraday_granularity_seconds"),
            "actual_granularity_seconds": row.get("intraday_actual_granularity_seconds") or row.get("intraday_granularity_seconds"),
            "granularity_label": row.get("intraday_granularity_label"),
            "latest_date": row.get("intraday_latest_date"),
            "daily_price_date": row.get("daily_price_date"),
            "date_match": row.get("date_match"),
            "source": row.get("intraday_source") or intraday_status.get("source") or "SSI",
            "status": intraday_status.get("status") or "unavailable",
            "message": intraday_status.get("message") or row.get("intraday_warning"),
        }
        realtime_status = _dict(row.get("realtime_status"))
        realtime = {
            "snapshot": row.get("realtime_snapshot") if isinstance(row.get("realtime_snapshot"), dict) else None,
            "source": row.get("realtime_source") or realtime_status.get("source"),
            "status": realtime_status.get("status") or "unavailable",
            "message": realtime_status.get("message"),
        }
        trade_tape_status = _dict(row.get("trade_tape_status"))
        trade_tape_payload = _dict(row.get("trade_tape"))
        trade_tape = {
            "trades": list(trade_tape_payload.get("trades") or []),
            "source": row.get("trade_tape_source") or trade_tape_status.get("source"),
            "status": trade_tape_status.get("status") or trade_tape_payload.get("status") or "unavailable",
            "message": trade_tape_status.get("message"),
        }

        source_coverage = self._source_coverage(profile, price, trading_stats, foreign_flow, technical, daily_stock_price, intraday, realtime, trade_tape)
        market_blocks_ok = any(block.get("status") == "ok" for block in [profile, price, trading_stats, foreign_flow, technical])
        status = "ok" if price["status"] == "ok" and trading_stats["status"] == "ok" else "partial" if market_blocks_ok else "unavailable"

        errors: Dict[str, Any] = {}
        if row.get("error"):
            errors["market_data"] = row.get("error")

        return {
            "ticker": symbol,
            "status": status,
            "profile": profile,
            "price": price,
            "trading_stats": trading_stats,
            "foreign_flow": foreign_flow,
            "technical": technical,
            "intraday": intraday,
            "realtime": realtime,
            "trade_tape": trade_tape,
            "source_coverage": source_coverage,
            "news": self._placeholder("not_implemented", "NewsProvider", NOT_IMPLEMENTED_MESSAGE),
            "financials": self._placeholder("not_implemented", "TBD"),
            "events": self._placeholder("not_implemented", "TBD"),
            "data_quality_summary": _dict(row.get("data_quality_summary")),
            "warnings": list(row.get("warnings") or []),
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
        realtime: Optional[Dict[str, Any]] = None,
        trade_tape: Optional[Dict[str, Any]] = None,
    ) -> list[Dict[str, Any]]:
        daily_stock_status = "ok" if daily_stock_price.get("status") == "ok" or price.get("status") == "ok" or foreign_flow.get("status") == "ok" else "missing"
        intraday_status = _dict(intraday).get("status") or "unavailable"
        realtime_status = _dict(realtime).get("status") or "unavailable"
        trade_tape_status = _dict(trade_tape).get("status") or "unavailable"
        return [
            {"block": "Daily OHLCV", "source": "SSI DailyOhlc", "status": "ok" if technical.get("status") == "ok" or trading_stats.get("status") == "ok" else "missing"},
            {"block": "Daily stock price", "source": "SSI DailyStockPrice", "status": daily_stock_status},
            {"block": "Intraday OHLCV", "source": "SSI IntradayOhlc", "status": intraday_status},
            {"block": "Realtime snapshot", "source": "SSI", "status": realtime_status},
            {"block": "Trade tape", "source": "SSI", "status": trade_tape_status},
            {"block": "Profile", "source": "SSI SecuritiesDetails", "status": profile.get("status", "missing")},
            {"block": "News", "source": "NewsProvider", "status": "not_implemented"},
            {"block": "Financials", "source": "TBD", "status": "not_implemented"},
            {"block": "Corporate actions", "source": "TBD", "status": "not_implemented"},
        ]

    def _placeholder(self, status: str, source: Optional[str], message: Optional[str] = None) -> Dict[str, Any]:
        payload = {"items": [], "status": status, "source": source}
        if message is not None:
            payload["message"] = message
        return payload

    def _unavailable_payload(self, symbol: str, errors: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        profile = {"ticker": symbol, "name": None, "exchange": None, "industry": None, "source": "SSI", "status": "missing"}
        missing_price = {
            "latest_price": None,
            "daily_close": None,
            "reference_price": None,
            "ceiling_price": None,
            "floor_price": None,
            "price_date": None,
            "source": "SSI DailyOhlc",
            "status": "missing",
        }
        missing_trading = {
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "volume": None,
            "value": None,
            "source": "SSI DailyStockPrice",
            "status": "missing",
        }
        missing_foreign = {
            "foreign_buy_volume": None,
            "foreign_sell_volume": None,
            "foreign_net_volume": None,
            "foreign_buy_value": None,
            "foreign_sell_value": None,
            "foreign_net_value": None,
            "source": "SSI DailyStockPrice",
            "status": "missing",
        }
        missing_technical = {
            "ma20": None,
            "ma50": None,
            "rsi14": None,
            "bollinger_upper": None,
            "bollinger_middle": None,
            "bollinger_lower": None,
            "source": "derived_from_ssi_ohlcv",
            "status": "missing",
        }
        missing_intraday = {
            "candles": [],
            "pulse": {},
            "granularity": "unknown",
            "granularity_seconds": None,
            "granularity_label": "provider-returned",
            "latest_date": None,
            "daily_price_date": None,
            "date_match": "unknown",
            "source": "SSI",
            "status": "unavailable",
            "message": "SSI intraday unavailable.",
        }
        missing_realtime = {
            "snapshot": None,
            "source": "SSI",
            "status": "unavailable",
            "message": "SSI realtime unavailable.",
        }
        missing_trade_tape = {
            "trades": [],
            "source": "SSI",
            "status": "unavailable",
            "message": "SSI trade tape unavailable.",
        }
        return {
            "ticker": symbol,
            "status": "unavailable",
            "profile": profile,
            "price": missing_price,
            "trading_stats": missing_trading,
            "foreign_flow": missing_foreign,
            "technical": missing_technical,
            "intraday": missing_intraday,
            "realtime": missing_realtime,
            "trade_tape": missing_trade_tape,
            "source_coverage": self._source_coverage(profile, missing_price, missing_trading, missing_foreign, missing_technical, {}, missing_intraday, missing_realtime, missing_trade_tape),
            "news": self._placeholder("not_implemented", "RSS provider", NOT_IMPLEMENTED_MESSAGE),
            "financials": self._placeholder("not_implemented", "TBD"),
            "events": self._placeholder("not_implemented", "TBD"),
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
            "warnings": [],
            "errors": errors or {},
        }


def get_company_research_snapshot(ticker: str, force_refresh: bool = False) -> Dict[str, Any]:
    """Return a Phase 1 Vietnam company research snapshot."""
    return VietnamCompanyResearchService().get_company_research_snapshot(ticker, force_refresh=force_refresh)
