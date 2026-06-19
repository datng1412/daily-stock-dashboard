from fastapi.testclient import TestClient

from api.app import create_app


def test_vietnam_company_research_endpoint_returns_phase_one_contract(monkeypatch, tmp_path):
    class StubVietnamMarketService:
        def build_watchlist(self, symbols=None, **kwargs):
            assert symbols == ["FPT"]
            assert kwargs["include_intraday"] is False
            return {
                "market": "VN",
                "source": "SSI",
                "watchlist": [
                    {
                        "ticker": "FPT",
                        "status": "ok",
                        "source": "SSI",
                        "actual_source": "SSI",
                        "fallback_used": False,
                        "company_name": "FPT Corporation",
                        "exchange": "HOSE",
                        "symbol_metadata": {
                            "status": "ok",
                            "symbol": "FPT",
                            "exchange": "HOSE",
                            "market": "HOSE",
                            "source": "SSI",
                        },
                        "latest_price": 124.6,
                        "daily_close": 124.6,
                        "latest_price_date": "2026-06-17",
                        "open": 123.4,
                        "high": 125.0,
                        "low": 122.8,
                        "close": 124.6,
                        "volume": 1_234_567,
                        "amount": 123_456_789_000,
                        "daily_stock_price": {
                            "status": "ok",
                            "date": "2026-06-17",
                            "reference_price": 123.0,
                            "ceiling_price": 131.6,
                            "floor_price": 114.4,
                            "matched_volume": 1_234_567,
                            "matched_value": 123_456_789_000,
                            "put_through_volume": 1000,
                            "put_through_value": 25_000_000,
                            "foreign_buy_volume": 100_000,
                            "foreign_sell_volume": 80_000,
                            "foreign_net_volume": 20_000,
                            "foreign_buy_value": 1_000_000_000,
                            "foreign_sell_value": 800_000_000,
                            "foreign_net_value": 200_000_000,
                            "source": "SSI",
                        },
                        "price_limit": {},
                        "foreign": {},
                        "indicators": {
                            "ma20": 120.0,
                            "ma50": 118.0,
                            "rsi14_wilder": 55.5,
                            "bollinger": {
                                "upper": 130.0,
                                "middle": 120.0,
                                "lower": 110.0,
                            },
                        },
                        "warnings": [],
                        "news": [],
                    }
                ],
            }

    monkeypatch.setattr(
        "src.services.vietnam_company_research_service.VietnamMarketService",
        StubVietnamMarketService,
    )
    client = TestClient(create_app(static_dir=tmp_path / "static"))

    response = client.get("/api/v1/stocks/vn/company/FPT")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "FPT"
    assert payload["status"] == "ok"
    assert payload["profile"]["source"] == "SSI"
    assert payload["price"]["reference_price"] == 123.0
    assert payload["trading_stats"]["value"] == 123_456_789_000
    assert payload["foreign_flow"]["foreign_net_value"] == 200_000_000
    coverage = {item["block"]: item for item in payload["source_coverage"]}
    assert coverage["Daily OHLCV"]["source"] == "SSI DailyOhlc"
    assert coverage["Daily stock price"]["source"] == "SSI DailyStockPrice"
    assert coverage["News"]["status"] == "not_implemented"
    assert coverage["Financials"]["status"] == "not_implemented"
    assert payload["news"]["items"] == []
    assert payload["news"]["status"] == "not_implemented"
    assert payload["status"] != "unavailable"
