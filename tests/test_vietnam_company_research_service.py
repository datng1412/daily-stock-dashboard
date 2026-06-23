from fastapi.testclient import TestClient

from api.app import create_app


def test_vietnam_company_research_endpoint_returns_phase_one_contract(monkeypatch, tmp_path):
    class StubVietnamMarketService:
        def build_watchlist(self, symbols=None, **kwargs):
            assert symbols == ["FPT"]
            assert kwargs["include_intraday"] is True
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
                            "open": 200.0,
                            "high": 201.0,
                            "low": 199.0,
                            "close": 200.5,
                            "matched_volume": 1_234_567,
                            "matched_value": 123_456_789_000,
                            "total_volume": 9_999_999,
                            "total_value": 999_999_999_000,
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
                        "intraday_source": "SSI",
                        "intraday_status": {"status": "ok", "source": "SSI", "message": None},
                        "intraday_candles": [
                            {
                                "date_time": "2026-06-17T10:00:00+07:00",
                                "open": 123.0,
                                "high": 125.0,
                                "low": 122.0,
                                "close": 124.0,
                                "volume": 1000,
                            }
                        ],
                        "intraday_pulse": {
                            "latest_1h_close": 124.0,
                            "latest_1h_change": 1.0,
                            "latest_1h_change_percent": 0.81,
                            "latest_1h_volume": 1000,
                        },
                        "realtime_source": "SSI",
                        "realtime_status": {"status": "ok", "source": "SSI", "message": None},
                        "realtime_snapshot": {
                            "ticker": "FPT",
                            "price": 124.8,
                            "change": 0.2,
                            "change_pct": 0.16,
                            "reference_price": 123.0,
                            "volume": 10_000,
                            "source": "SSI",
                            "status": "ok",
                        },
                        "trade_tape_source": "SSI",
                        "trade_tape_status": {"status": "ok", "source": "SSI", "message": None},
                        "trade_tape": [
                            {
                                "time": "10:16:00",
                                "price": 124.8,
                                "volume": 1000,
                                "value": 124_800_000,
                                "source": "SSI",
                            }
                        ],
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
    assert payload["profile"]["source"] == "SSI SecuritiesDetails"
    assert payload["price"]["source"] == "SSI DailyOhlc"
    assert payload["price"]["canonical_source"] == "SSI DailyOhlc"
    assert payload["price"]["reference_source"] == "SSI DailyStockPrice"
    assert payload["price"]["latest_price"] == 124.6
    assert payload["price"]["daily_close"] == 124.6
    assert payload["price"]["reference_price"] == 123.0
    assert payload["trading_stats"]["source"] == "SSI DailyOhlc"
    assert payload["trading_stats"]["close"] == 124.6
    assert payload["trading_stats"]["volume"] == 1_234_567
    assert payload["trading_stats"]["value"] == 123_456_789_000
    assert payload["foreign_flow"]["source"] == "SSI DailyStockPrice"
    assert payload["foreign_flow"]["foreign_net_value"] == 200_000_000
    coverage = {item["block"]: item for item in payload["source_coverage"]}
    assert coverage["Daily OHLCV"]["source"] == "SSI DailyOhlc"
    assert coverage["Daily stock price"]["source"] == "SSI DailyStockPrice"
    assert coverage["Intraday OHLCV"]["source"] == "SSI IntradayOhlc"
    assert coverage["Realtime snapshot"]["source"] == "SSI realtime contract"
    assert coverage["Realtime snapshot"]["status"] == "ok"
    assert coverage["Trade tape"]["source"] == "SSI trade-tape contract"
    assert coverage["Trade tape"]["status"] == "ok"
    assert coverage["News"]["source"] == "NewsProvider future"
    assert coverage["Financials"]["source"] == "external provider future"
    assert coverage["Corporate actions"]["source"] == "external provider future"
    assert payload["intraday"]["status"] == "ok"
    assert payload["realtime"]["status"] == "ok"
    assert payload["realtime"]["snapshot"]["price"] == 124.8
    assert payload["trade_tape"]["status"] == "ok"
    assert payload["trade_tape"]["trades"][0]["price"] == 124.8
    assert coverage["News"]["status"] == "not_implemented"
    assert coverage["Financials"]["status"] == "not_implemented"
    assert payload["news"]["items"] == []
    assert payload["news"]["status"] == "not_implemented"
    assert payload["news"]["source"] != "SSI"
    assert payload["financials"]["source"] != "SSI"
    assert payload["events"]["source"] != "SSI"
    assert payload["status"] != "unavailable"


def test_vietnam_company_research_keeps_unavailable_live_sections_visible(monkeypatch, tmp_path):
    class StubVietnamMarketService:
        def build_watchlist(self, symbols=None, **kwargs):
            assert symbols == ["FPT"]
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
                        "daily_stock_price": {"status": "ok", "date": "2026-06-17", "close": 124.6, "source": "SSI"},
                        "price_limit": {},
                        "foreign": {},
                        "indicators": {},
                        "intraday_source": "SSI",
                        "intraday_status": {
                            "status": "unavailable",
                            "source": "SSI IntradayOhlc",
                            "message": "SSI IntradayOhlc latest candle date does not match latest daily trading date.",
                        },
                        "intraday_candles": [],
                        "intraday_pulse": None,
                        "realtime_source": "SSI realtime contract",
                        "realtime_status": {
                            "status": "unavailable",
                            "source": "SSI realtime contract",
                            "message": "SSI realtime unavailable.",
                            "diagnostics": {"provider_message": "attempted endpoints: RealtimeQuote"},
                        },
                        "realtime_snapshot": None,
                        "trade_tape_source": "SSI trade-tape contract",
                        "trade_tape_status": {
                            "status": "unavailable",
                            "source": "SSI trade-tape contract",
                            "message": "SSI trade tape unavailable.",
                            "diagnostics": {"provider_message": "attempted endpoints: TradeTape"},
                        },
                        "trade_tape": [],
                        "data_quality_summary": {
                            "overall_status": "partial",
                            "canonical_price_source": "SSI DailyOhlc",
                            "issues": [],
                            "checks": {
                                "daily_ohlc": "ok",
                                "daily_stock_price": "ok",
                                "final_close_status": "unknown",
                                "adjusted_price_status": "unknown",
                                "intraday": "unavailable",
                                "realtime": "unavailable",
                                "trade_tape": "unavailable",
                                "profile": "ok",
                                "news": "disabled",
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
    assert payload["status"] == "ok"
    assert payload["price"]["latest_price"] == 124.6
    assert payload["intraday"]["status"] == "unavailable"
    assert payload["intraday"]["candles"] == []
    assert payload["intraday"]["pulse"] is None
    assert payload["realtime"]["status"] == "unavailable"
    assert payload["realtime"]["snapshot"] is None
    assert payload["realtime"]["message"] == "SSI realtime unavailable."
    assert payload["trade_tape"]["status"] == "unavailable"
    assert payload["trade_tape"]["trades"] == []
    assert payload["trade_tape"]["message"] == "SSI trade tape unavailable."
    assert payload["data_quality_summary"]["checks"]["intraday"] == "unavailable"
    assert payload["data_quality_summary"]["checks"]["realtime"] == "unavailable"
    assert payload["data_quality_summary"]["checks"]["trade_tape"] == "unavailable"
