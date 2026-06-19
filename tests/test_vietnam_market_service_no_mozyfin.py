from __future__ import annotations

from datetime import date, timedelta

from src.services.vietnam_company_research_service import VietnamCompanyResearchService
from src.services.vietnam_market_service import VietnamDashboardConfig, VietnamMarketService


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


def _service() -> VietnamMarketService:
    return VietnamMarketService(
        manager=ExplodingManager(),
        config=VietnamDashboardConfig(
            daily_data_provider="ssi",
            chart_data_provider="ssi",
            daily_stock_price_provider="ssi",
            index_data_provider="ssi",
            include_intraday=True,
            news_provider="disabled",
            mozyfin_enabled=False,
            mozyfin_news_enabled=False,
        ),
        ssi_fetcher=FakeSsiFetcher(),
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
    assert item["latest_price_source"] == "SSI"
    assert item["daily_stock_price"]["status"] == "ok"
    assert item["news"] == []
    assert item["news_status"]["status"] == "disabled"
    assert item["cache_status"]["news_cache"] == "disabled"
    assert "news" not in item["cache_errors"]
    assert item["intraday_status"]["status"] == "not_implemented"
    assert item["cache_status"]["intraday_cache"] == "disabled"


def test_missing_mozyfin_cli_does_not_affect_vn_watchlist(monkeypatch):
    monkeypatch.delenv("MOZYFIN_API_KEY", raising=False)
    monkeypatch.setenv("MOZYFIN_COMMAND", "definitely-not-installed")

    item = _service().build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["source"] == "SSI"
    assert item["news_status"]["message"] == "News provider disabled."
    assert "Mozyfin" not in " ".join(item["cache_errors"].values())


def test_company_research_uses_ssi_and_not_implemented_placeholders():
    snapshot = VietnamCompanyResearchService(market_service=_service()).get_company_research_snapshot(
        "FPT",
        force_refresh=True,
    )

    assert snapshot["ticker"] == "FPT"
    assert snapshot["price"]["source"] == "SSI DailyStockPrice"
    assert snapshot["news"]["status"] == "not_implemented"
    assert snapshot["financials"]["status"] == "not_implemented"
    assert snapshot["events"]["status"] == "not_implemented"
    assert snapshot["status"] != "unavailable"
