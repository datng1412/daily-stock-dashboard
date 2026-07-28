from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from data_provider.vnstock_community_news_provider import clear_vnstock_community_news_cache
from src.services.vietnam_company_research_service import VietnamCompanyResearchService
from src.services import vietnam_market_service as vn_market_service
from src.services.vietnam_market_service import VietnamDashboardConfig, VietnamMarketService, clear_vietnam_cache


class ExplodingManager:
    def _get_fetcher_by_name(self, name: str):  # pragma: no cover - failure path
        raise AssertionError(f"Mozyfin must not be requested in VN dashboard runtime: {name}")

    def get_daily_data(self, *args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("Mozyfin daily data must not be requested in VN dashboard runtime")


class FakeSsiFetcher:
    def get_daily_ohlcv(self, symbol: str, **kwargs):
        start = date(2026, 6, 1)
        rows = []
        for index in range(30):
            rows.append(
                {
                    "date": (start + timedelta(days=index)).isoformat(),
                    "open": 100 + index,
                    "high": 102 + index,
                    "low": 99 + index,
                    "close": 101 + index,
                    "volume": 1_000_000 + index,
                    "value": 101_000_000 + index,
                    "source": "SSI",
                }
            )
        return {"status": "ok", "source": "SSI", "rows": rows}

    def get_daily_stock_price(self, symbol: str, **kwargs):
        return {
            "status": "ok",
            "source": "SSI",
            "rows": [
                {
                    "symbol": symbol,
                    "date": "2026-06-30",
                    "reference_price": 129.0,
                    "ceiling_price": 138.0,
                    "floor_price": 120.0,
                    "open": 129.5,
                    "high": 132.0,
                    "low": 128.0,
                    "close": 130.0,
                    "matched_volume": 1_234_567,
                    "matched_value": 123_456_789_000,
                    "put_through_volume": 10_000,
                    "put_through_value": 1_000_000_000,
                    "foreign_buy_volume": 100_000,
                    "foreign_sell_volume": 80_000,
                    "foreign_net_volume": 20_000,
                    "foreign_buy_value": 10_000_000_000,
                    "foreign_sell_value": 8_000_000_000,
                    "foreign_net_value": 2_000_000_000,
                    "source": "SSI",
                }
            ],
        }

    def get_intraday_ohlcv(self, symbol: str, **kwargs):
        return {
            "status": "ok",
            "source": "SSI",
            "rows": [
                {
                    "date_time": "2026-06-30T09:00:00+07:00",
                    "timestamp": 1782784800,
                    "open": 130.0,
                    "high": 131.0,
                    "low": 129.5,
                    "close": 130.5,
                    "volume": 1000,
                    "ticker": symbol,
                    "source": "SSI",
                },
                {
                    "date_time": "2026-06-30T10:00:00+07:00",
                    "timestamp": 1782788400,
                    "open": 130.5,
                    "high": 132.0,
                    "low": 130.0,
                    "close": 131.5,
                    "volume": 2000,
                    "ticker": symbol,
                    "source": "SSI",
                },
                {
                    "date_time": "2026-06-30T11:00:00+07:00",
                    "timestamp": 1782792000,
                    "open": 131.5,
                    "high": 133.0,
                    "low": 131.0,
                    "close": 132.5,
                    "volume": 3000,
                    "ticker": symbol,
                    "source": "SSI",
                },
            ],
        }

    def get_realtime_snapshot(self, symbols):
        symbol = symbols[0]
        return {
            "status": "ok",
            "source": "SSI",
            "requested_tickers": symbols,
            "quotes": [
                {
                    "ticker": symbol,
                    "source": "SSI",
                    "fetched_at": "2026-06-30T04:00:00+00:00",
                    "price": 130.5,
                    "change": 1.5,
                    "change_pct": 1.16,
                    "reference_price": 129.0,
                    "ceiling_price": 138.0,
                    "floor_price": 120.0,
                    "open": 129.5,
                    "high": 132.0,
                    "low": 128.0,
                    "volume": 1_234_567,
                    "value": 123_456_789_000,
                    "bid_levels": [{"price": 130.4, "volume": 1000}],
                    "ask_levels": [{"price": 130.6, "volume": 2000}],
                    "status": "ok",
                }
            ],
        }

    def get_trade_tape(self, symbol: str, **kwargs):
        return {
            "status": "ok",
            "source": "SSI",
            "symbol": symbol,
            "trades": [
                {
                    "time": "10:00:00",
                    "timestamp": "2026-06-30T10:00:00+07:00",
                    "timestamp_display": "10:00:00",
                    "price": 130.5,
                    "volume": 1000,
                    "value": 130_500_000,
                    "side_if_available": None,
                    "sequence_if_available": "1",
                    "raw_type": "X-TRADE",
                    "source": "SSI",
                }
            ],
        }

    def get_securities_details(self, **kwargs):
        symbol = kwargs.get("symbol") or "FPT"
        return {
            "status": "ok",
            "source": "SSI",
            "rows": [
                {
                    "symbol": symbol,
                    "exchange": "HOSE",
                    "market": "HOSE",
                    "security_type": "stock",
                    "name": "FPT Corporation",
                    "source": "SSI",
                }
            ],
        }

    def get_securities(self, **kwargs):
        return self.get_securities_details(symbol="FPT")

    def get_index_list(self, market=None, **kwargs):
        return {
            "status": "ok",
            "source": "SSI",
            "market": market,
            "rows": [
                {
                    "index_id": "VNINDEX",
                    "index_code": "VNINDEX",
                    "index_name": "VN Index",
                    "exchange": "HOSE",
                    "market": "HOSE",
                    "source": "SSI",
                },
                {
                    "index_id": "VN30",
                    "index_code": "VN30",
                    "index_name": "VN30 Index",
                    "exchange": "HOSE",
                    "market": "HOSE",
                    "source": "SSI",
                },
            ],
            "count": 2,
        }

    def get_index_components(
        self,
        index_code: str,
        market=None,
        force_refresh: bool = False,
    ):
        return {
            "status": "ok",
            "source": "SSI",
            "index_code": index_code,
            "market": market,
            "rows": [
                {
                    "index_code": index_code,
                    "symbol": "FPT",
                    "exchange": "HOSE",
                    "market": "HOSE",
                    "weight": 7.25,
                    "name": "FPT Corp",
                    "source": "SSI",
                }
            ],
            "count": 1,
        }


def _service() -> VietnamMarketService:
    return VietnamMarketService(
        manager=ExplodingManager(),
        config=VietnamDashboardConfig(
            daily_data_provider="ssi",
            chart_data_provider="ssi",
            daily_stock_price_provider="ssi",
            index_data_provider="ssi",
            intraday_data_provider="ssi",
            ssi_intraday_enabled=True,
            realtime_data_provider="ssi",
            trade_tape_provider="ssi",
            ssi_realtime_enabled=True,
            ssi_streaming_realtime_enabled=True,
            ssi_trade_tape_enabled=True,
            kbs_enabled=False,
            allow_legacy_kbs_provider=False,
            include_intraday=True,
            news_provider="disabled",
            mozyfin_enabled=False,
            mozyfin_news_enabled=False,
        ),
        ssi_fetcher=FakeSsiFetcher(),
        time_func=lambda: datetime(2026, 6, 30, 3, 0, tzinfo=timezone.utc).timestamp(),
    )


def test_vn_watchlist_does_not_request_mozyfin_when_env_vars_exist(monkeypatch):
    monkeypatch.setenv("MOZYFIN_API_KEY", "placeholder-not-used")
    monkeypatch.setenv("MOZYFIN_COMMAND", "missing-mozyfin-cli")

    payload = _service().build_watchlist(["FPT"], force_refresh=True, include_intraday=True)
    item = payload["watchlist"][0]

    assert payload["source"] == "SSI live"
    assert item["source"] == "SSI"
    assert item["actual_source"] == "SSI"
    assert item["fallback_used"] is False
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["daily_stock_price"]["status"] == "ok"
    assert item["news"] == []
    assert item["news_status"]["status"] == "disabled"
    assert item["cache_status"]["news_cache"] == "disabled"
    assert "news" not in item["cache_errors"]
    assert item["intraday_source"] == "SSI IntradayOhlc"
    assert item["intraday_status"]["status"] == "ok"
    assert item["cache_status"]["intraday_cache"] in {"miss", "refresh"}
    assert item["realtime_source"] == "SSI realtime contract"
    assert item["realtime_status"]["status"] == "ok"
    assert item["trade_tape_source"] == "SSI trade-tape contract"
    assert item["trade_tape_status"]["status"] == "ok"


def test_missing_mozyfin_cli_does_not_affect_vn_watchlist(monkeypatch):
    monkeypatch.delenv("MOZYFIN_API_KEY", raising=False)
    monkeypatch.setenv("MOZYFIN_COMMAND", "definitely-not-installed")

    item = _service().build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["source"] == "SSI"
    assert item["news_status"]["message"] == "News provider disabled."
    assert "Mozyfin" not in " ".join(item["cache_errors"].values())


def test_vnstock_news_config_is_blocked_without_affecting_ssi_daily_rows():
    service = VietnamMarketService(
        manager=ExplodingManager(),
        config=VietnamDashboardConfig(
            daily_data_provider="ssi",
            chart_data_provider="ssi",
            daily_stock_price_provider="ssi",
            index_data_provider="ssi",
            intraday_data_provider="ssi",
            realtime_data_provider="ssi",
            trade_tape_provider="ssi",
            news_provider="vnstock_news",
            mozyfin_enabled=False,
            mozyfin_news_enabled=False,
        ),
        ssi_fetcher=FakeSsiFetcher(),
    )

    item = service.build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["news"] == []
    assert item["news_status"]["status"] == "unavailable"
    assert item["news_status"]["reason_code"] == "blocked_pending_terms"
    assert item["news_status"]["source"] == "Vnstock News"


def test_vnstock_news_personal_package_missing_is_optional(monkeypatch):
    clear_vietnam_cache()
    monkeypatch.delitem(sys.modules, "vnstock_news", raising=False)
    service = VietnamMarketService(
        manager=ExplodingManager(),
        config=VietnamDashboardConfig(
            daily_data_provider="ssi",
            chart_data_provider="ssi",
            daily_stock_price_provider="ssi",
            index_data_provider="ssi",
            intraday_data_provider="ssi",
            realtime_data_provider="ssi",
            trade_tape_provider="ssi",
            news_provider="vnstock_news_personal",
            vnstock_news_personal_enabled=True,
            mozyfin_enabled=False,
            mozyfin_news_enabled=False,
        ),
        ssi_fetcher=FakeSsiFetcher(),
    )

    item = service.build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["news"] == []
    assert item["news_status"]["status"] == "unavailable"
    assert item["news_status"]["reason_code"] == "provider_package_missing"
    assert item["cache_status"]["news_cache"] in {"miss", "refresh"}


def test_vnstock_news_personal_mocked_success_keeps_ssi_daily_price(monkeypatch):
    clear_vietnam_cache()

    class FakeCrawler:
        def __init__(self, site_name):
            self.site_name = site_name

        def get_articles_from_feed(self, limit_per_feed):
            return [
                {
                    "url": f"https://example.test/{self.site_name}/fpt",
                    "title": "FPT announces new data center",
                    "short_description": "FPT expands technology infrastructure.",
                    "content": "Full content is intentionally not included by default.",
                    "publish_time": "2026-07-10T09:00:00+07:00",
                    "category": "business",
                },
                {
                    "url": f"https://example.test/{self.site_name}/general",
                    "title": "General market update",
                    "short_description": "No ticker match.",
                },
            ][:limit_per_feed]

    monkeypatch.setitem(sys.modules, "vnstock_news", SimpleNamespace(Crawler=FakeCrawler))
    service = VietnamMarketService(
        manager=ExplodingManager(),
        config=VietnamDashboardConfig(
            daily_data_provider="ssi",
            chart_data_provider="ssi",
            daily_stock_price_provider="ssi",
            index_data_provider="ssi",
            intraday_data_provider="ssi",
            realtime_data_provider="ssi",
            trade_tape_provider="ssi",
            news_provider="vnstock_news_personal",
            vnstock_news_personal_enabled=True,
            vnstock_news_sites="vnexpress",
            vnstock_news_limit_per_site=2,
            vnstock_news_include_content=False,
            mozyfin_enabled=False,
            mozyfin_news_enabled=False,
        ),
        ssi_fetcher=FakeSsiFetcher(),
    )

    item = service.build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["news_status"]["status"] == "ok"
    assert item["news_status"]["reason_code"] == "local_personal_research_only"
    assert item["news_status"]["rights_status"] == "personal_research_only"
    assert len(item["news"]) == 1
    assert item["news"][0]["title"] == "FPT announces new data center"
    assert item["news"][0]["source"] == "Vnstock News"
    assert item["news"][0]["content"] is None


def test_vnstock_community_news_is_selected_ticker_only_and_keeps_ssi_prices(monkeypatch):
    clear_vietnam_cache()
    clear_vnstock_community_news_cache()
    calls = []

    class FakeCompany:
        def __init__(self, ticker):
            self.ticker = ticker

        def news(self):
            calls.append(self.ticker)
            return [
                {
                    "article_id": f"{self.ticker}-1",
                    "title": f"{self.ticker} company update",
                    "publish_time": "2026-07-10T09:00:00+07:00",
                    "url": "/relative-company-news",
                }
            ]

    class FakeReference:
        def company(self, ticker):
            return FakeCompany(ticker)

    monkeypatch.setitem(sys.modules, "vnstock", SimpleNamespace(Reference=FakeReference))
    service = VietnamMarketService(
        manager=ExplodingManager(),
        config=VietnamDashboardConfig(
            daily_data_provider="ssi",
            chart_data_provider="ssi",
            daily_stock_price_provider="ssi",
            index_data_provider="ssi",
            intraday_data_provider="ssi",
            realtime_data_provider="ssi",
            trade_tape_provider="ssi",
            news_provider="vnstock_community",
            vnstock_community_news_limit_per_ticker=3,
            vnstock_community_news_cache_ttl_seconds=1800,
            vnstock_community_news_timeout_seconds=10,
            mozyfin_enabled=False,
            mozyfin_news_enabled=False,
        ),
        ssi_fetcher=FakeSsiFetcher(),
    )

    watchlist = service.build_watchlist(["FPT", "HPG"], force_refresh=True)
    assert calls == []
    assert all(row["news"] == [] for row in watchlist["watchlist"])
    assert all(row["latest_price_source"] == "SSI DailyOhlc" for row in watchlist["watchlist"])

    selected = service.get_company_news("FPT")
    cached = service.get_company_news("FPT")
    assert calls == ["FPT"]
    assert selected["status"] == "ok"
    assert selected["news"][0]["ticker"] == "FPT"
    assert selected["news"][0]["url"] is None
    assert selected["news"][0]["raw_url"] == "/relative-company-news"
    assert cached["cache"]["status"] == "hit"


def test_vnstock_community_news_is_available_to_one_company_snapshot(monkeypatch):
    clear_vietnam_cache()
    clear_vnstock_community_news_cache()

    class FakeReference:
        def company(self, ticker):
            self.ticker = ticker
            return self

        def news(self):
            return [{"article_id": "fpt-1", "title": "FPT company update", "publish_time": "2026-07-10T09:00:00+07:00", "url": "/news"}]

    monkeypatch.setitem(sys.modules, "vnstock", SimpleNamespace(Reference=FakeReference))
    service = VietnamMarketService(
        manager=ExplodingManager(),
        config=VietnamDashboardConfig(news_provider="vnstock_community"),
        ssi_fetcher=FakeSsiFetcher(),
    )

    snapshot = VietnamCompanyResearchService(market_service=service).get_company_research_snapshot("FPT")

    assert snapshot["price"]["canonical_source"] == "SSI DailyOhlc"
    assert snapshot["news"]["status"] == "ok"
    assert len(snapshot["news"]["items"]) == 1


def test_company_research_uses_ssi_and_disabled_news_placeholder():
    snapshot = VietnamCompanyResearchService(market_service=_service()).get_company_research_snapshot(
        "FPT",
        force_refresh=True,
    )

    assert snapshot["ticker"] == "FPT"
    assert snapshot["price"]["source"] == "SSI DailyOhlc"
    assert snapshot["price"]["canonical_source"] == "SSI DailyOhlc"
    assert snapshot["price"]["reference_source"] == "SSI DailyStockPrice"
    assert snapshot["trading_stats"]["source"] == "SSI DailyOhlc"
    assert snapshot["foreign_flow"]["source"] == "SSI DailyStockPrice"
    assert snapshot["technical"]["source"] == "SSI-derived"
    assert snapshot["news"]["source"] != "SSI"
    assert snapshot["financials"]["source"] != "SSI"
    assert snapshot["events"]["source"] != "SSI"
    assert snapshot["news"]["status"] == "disabled"
    assert snapshot["financials"]["status"] == "not_implemented"
    assert snapshot["events"]["status"] == "not_implemented"
    assert snapshot["data_quality_summary"]["canonical_price_source"] == "SSI DailyOhlc"
    assert snapshot["data_quality_summary"]["checks"]["daily_ohlc"] == "ok"
    assert snapshot["data_quality_summary"]["checks"]["daily_stock_price"] == "partial"
    assert snapshot["status"] != "unavailable"

def test_default_vn_service_does_not_construct_mozyfin_manager_when_disabled(monkeypatch):
    def fail_manager(*args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("DataFetcherManager must not be constructed for strict VN runtime")

    monkeypatch.setattr(vn_market_service, "DataFetcherManager", fail_manager)

    service = VietnamMarketService(
        config=VietnamDashboardConfig(
            daily_data_provider="ssi",
            chart_data_provider="ssi",
            daily_stock_price_provider="ssi",
            index_data_provider="ssi",
            intraday_data_provider="ssi",
            news_provider="disabled",
            mozyfin_enabled=False,
            mozyfin_news_enabled=False,
            allow_legacy_mozyfin_provider=False,
        ),
        ssi_fetcher=FakeSsiFetcher(),
    )
    actions = service.build_corporate_actions(["FPT"])

    assert actions["status"] == "disabled"
    assert actions["source"] == "CorporateActionsProvider disabled"
    assert actions["events"] == []
    assert actions["items"] == []
    assert "Mozyfin" not in str(actions)


def test_index_components_service_uses_ssi_without_mozyfin_manager(monkeypatch):
    def fail_manager(*args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("DataFetcherManager must not be constructed for SSI index components")

    monkeypatch.setattr(vn_market_service, "DataFetcherManager", fail_manager)

    service = VietnamMarketService(
        config=VietnamDashboardConfig(
            index_data_provider="ssi",
            news_provider="disabled",
            mozyfin_enabled=False,
            mozyfin_news_enabled=False,
            allow_legacy_mozyfin_provider=False,
        ),
        ssi_fetcher=FakeSsiFetcher(),
    )
    payload = service.build_index_components("VN30", market="HOSE")

    assert payload["status"] == "ok"
    assert payload["source"] == "SSI IndexComponents"
    assert payload["fallback_used"] is False
    assert payload["rows"][0]["symbol"] == "FPT"
