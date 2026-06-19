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
            include_intraday=False,
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
        price_date = _first_present(daily_stock_price.get("date"), row.get("latest_price_date"), row.get("price_date"), row.get("date"))
        price = {
            "latest_price": row.get("latest_price"),
            "daily_close": row.get("daily_close"),
            "reference_price": reference_price,
            "ceiling_price": ceiling_price,
            "floor_price": floor_price,
            "price_date": price_date,
            "source": "SSI DailyStockPrice",
            "status": _status_for(row.get("latest_price"), row.get("daily_close"), reference_price, ceiling_price, floor_price),
        }

        trading_value = _first_present(daily_stock_price.get("total_value"), daily_stock_price.get("matched_value"), row.get("amount"))
        trading_stats = {
            "open": _first_present(daily_stock_price.get("open"), row.get("open")),
            "high": _first_present(daily_stock_price.get("high"), row.get("high")),
            "low": _first_present(daily_stock_price.get("low"), row.get("low")),
            "close": _first_present(daily_stock_price.get("close"), row.get("close")),
            "volume": _first_present(daily_stock_price.get("total_volume"), daily_stock_price.get("matched_volume"), row.get("volume")),
            "value": trading_value,
            "source": "SSI DailyStockPrice",
            "status": _status_for(row.get("open"), row.get("high"), row.get("low"), row.get("close"), row.get("volume"), trading_value),
        }

        foreign_flow = {
            "foreign_buy_volume": _first_present(daily_stock_price.get("foreign_buy_volume"), foreign.get("buy")),
            "foreign_sell_volume": _first_present(daily_stock_price.get("foreign_sell_volume"), foreign.get("sell")),
            "foreign_net_volume": _first_present(daily_stock_price.get("foreign_net_volume"), row.get("ssi_foreign_net_volume"), foreign.get("net")),
            "foreign_buy_value": _first_present(daily_stock_price.get("foreign_buy_value"), foreign.get("buy_value")),
            "foreign_sell_value": _first_present(daily_stock_price.get("foreign_sell_value"), foreign.get("sell_value")),
            "foreign_net_value": _first_present(daily_stock_price.get("foreign_net_value"), row.get("ssi_foreign_net_value"), foreign.get("net_value")),
            "source": "SSI DailyStockPrice",
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

        source_coverage = self._source_coverage(profile, price, trading_stats, foreign_flow, technical, daily_stock_price)
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
            "source_coverage": source_coverage,
            "news": self._placeholder("not_implemented", "NewsProvider", NOT_IMPLEMENTED_MESSAGE),
            "financials": self._placeholder("not_implemented", "TBD"),
            "events": self._placeholder("not_implemented", "TBD"),
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
    ) -> list[Dict[str, Any]]:
        daily_stock_status = "ok" if daily_stock_price.get("status") == "ok" or price.get("status") == "ok" or foreign_flow.get("status") == "ok" else "missing"
        return [
            {"block": "Daily OHLCV", "source": "SSI DailyOhlc", "status": "ok" if technical.get("status") == "ok" or trading_stats.get("status") == "ok" else "missing"},
            {"block": "Daily stock price", "source": "SSI DailyStockPrice", "status": daily_stock_status},
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
            "source": "SSI DailyStockPrice",
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
        return {
            "ticker": symbol,
            "status": "unavailable",
            "profile": profile,
            "price": missing_price,
            "trading_stats": missing_trading,
            "foreign_flow": missing_foreign,
            "technical": missing_technical,
            "source_coverage": self._source_coverage(profile, missing_price, missing_trading, missing_foreign, missing_technical, {}),
            "news": self._placeholder("not_implemented", "RSS provider", NOT_IMPLEMENTED_MESSAGE),
            "financials": self._placeholder("not_implemented", "TBD"),
            "events": self._placeholder("not_implemented", "TBD"),
            "warnings": [],
            "errors": errors or {},
        }


def get_company_research_snapshot(ticker: str, force_refresh: bool = False) -> Dict[str, Any]:
    """Return a Phase 1 Vietnam company research snapshot."""
    return VietnamCompanyResearchService().get_company_research_snapshot(ticker, force_refresh=force_refresh)
