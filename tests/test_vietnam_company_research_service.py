from fastapi.testclient import TestClient

from api.app import create_app
from src.services.vietnam_company_research_service import VietnamCompanyResearchService


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
                            "industry": "Information Technology",
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
    assert payload["session_context"]["completed_session_date"] == "2026-06-17"
    assert payload["price"]["final_close_status"] == "completed"
    assert payload["price"]["adjustment_status"] == "not_provided"
    assert payload["profile"]["source"] == "SSI SecuritiesDetails"
    assert payload["profile"]["industry"] == "Information Technology"
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
    assert "Financials" not in coverage
    assert "Corporate actions" not in coverage
    assert payload["intraday"]["status"] == "ok"
    assert payload["realtime_status"]["status"] == "ok"
    assert payload["realtime_snapshot"]["price"] == 124.8
    assert payload["trade_tape_status"]["status"] == "ok"
    assert payload["trade_tape"][0]["price"] == 124.8
    assert payload["live_market"]["status"] in {"partial", "ready"}
    assert len(payload["quality_summary"]["groups"]) == 3
    assert coverage["News"]["status"] == "not_implemented"
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
                            "industry": "Information Technology",
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
                            "diagnostics": {
                                "failure_class": "rate_limited",
                                "endpoint": "IntradayOhlc",
                                "provider_code": "429",
                            },
                        },
                        "intraday_candles": [],
                        "intraday_pulse": None,
                        "realtime_source": "SSI realtime contract",
                        "realtime_status": {
                            "status": "unavailable",
                            "source": "SSI realtime contract",
                            "message": "SSI realtime unavailable.",
                        },
                        "realtime_snapshot": None,
                        "trade_tape_source": "SSI trade-tape contract",
                        "trade_tape_status": {
                            "status": "unavailable",
                            "source": "SSI trade-tape contract",
                            "message": "SSI trade tape unavailable.",
                        },
                        "trade_tape": [],
                        "diagnostics": {
                            "realtime": {"provider_message": "attempted endpoints: RealtimeQuote"},
                            "trade_tape": {"provider_message": "attempted endpoints: TradeTape"},
                        },
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
    assert payload["intraday"]["diagnostics"]["failure_class"] == "rate_limited"
    assert payload["intraday"]["diagnostics"]["endpoint"] == "IntradayOhlc"
    assert payload["intraday"]["diagnostics"]["provider_code"] == "429"
    assert payload["realtime_status"]["status"] == "unavailable"
    assert payload["realtime_snapshot"] is None
    assert payload["realtime_status"]["message"] == "SSI realtime unavailable."
    assert payload["trade_tape_status"]["status"] == "unavailable"
    assert payload["trade_tape"] == []
    assert payload["trade_tape_status"]["message"] == "SSI trade tape unavailable."
    assert payload["diagnostics"]["realtime"]["provider_message"] == "attempted endpoints: RealtimeQuote"
    assert payload["diagnostics"]["trade_tape"]["provider_message"] == "attempted endpoints: TradeTape"
    assert payload["data_quality_summary"]["checks"]["intraday"] == "unavailable"
    assert payload["data_quality_summary"]["checks"]["realtime"] == "unavailable"
    assert payload["data_quality_summary"]["checks"]["trade_tape"] == "unavailable"


def test_company_snapshot_exposes_independent_daily_stock_price_and_zero_lineage_states():
    service = VietnamCompanyResearchService(market_service=object(), time_func=lambda: 1_753_660_800)
    snapshot = service._snapshot_from_watch_item(
        "FPT",
        {
            "ticker": "FPT",
            "status": "ok",
            "latest_price": 63_000,
            "daily_close": 63_000,
            "latest_price_date": "2026-07-28",
            "open": 62_500,
            "high": 63_500,
            "low": 62_000,
            "close": 63_000,
            "volume": 5_400_000,
            "amount": 338_000_000_000,
            "daily_stock_price": {
                "status": "ok",
                "quality_status": "partial",
                "date": "2026-07-28",
                "reference_price": None,
                "ceiling_price": None,
                "floor_price": None,
                "matched_volume": 5_400_000,
                "matched_value": 338_000_000_000,
                "put_through_volume": 2_360_000,
                "put_through_value": 156_800_000_000,
                "foreign_buy_volume": 0,
                "foreign_sell_volume": 0,
                "foreign_net_volume": 0,
                "foreign_buy_value": 0,
                "foreign_sell_value": 0,
                "foreign_net_value": 0,
                "foreign_flow_value_state": "explicit_zero",
                "foreign_field_presence": {
                    "foreign_buy_volume": "FIELD_PRESENT_EXPLICIT_ZERO",
                    "foreign_sell_volume": "FIELD_PRESENT_EXPLICIT_ZERO",
                    "foreign_net_volume": "DERIVED_FROM_PRESENT_INPUTS",
                    "foreign_buy_value": "FIELD_PRESENT_EXPLICIT_ZERO",
                    "foreign_sell_value": "FIELD_PRESENT_EXPLICIT_ZERO",
                    "foreign_net_value": "DERIVED_FROM_PRESENT_INPUTS",
                },
                "capabilities": {
                    "price_limits_status": "unavailable",
                    "matched_stats_status": "ready",
                    "put_through_status": "ready",
                    "foreign_flow_status": "ready",
                    "session_metadata_status": "ready",
                    "overall_status": "partial",
                },
            },
            "intraday_status": {"status": "ok"},
            "intraday_requested_timeframe": "1h",
            "intraday_actual_granularity": "unknown",
            "intraday_cadence_status": "irregular",
            "intraday_candles": [
                {"date_time": "2026-07-28T09:00:00+07:00", "open": 62_000, "close": 62_500},
                {"date_time": "2026-07-28T09:37:00+07:00", "open": 62_500, "close": 63_000},
            ],
            "intraday_pulse": {
                "latest_intraday_close": 63_000,
                "intraday_change": 1_000,
                "intraday_change_percent": 1.61,
                "intraday_change_baseline": "first_session_candle_open",
                "intraday_change_baseline_value": 62_000,
            },
        },
    )

    assert snapshot["daily_stock_price"]["capabilities"] == {
        "price_limits_status": "unavailable",
        "matched_stats_status": "ready",
        "put_through_status": "ready",
        "foreign_flow_status": "ready",
        "session_metadata_status": "ready",
        "overall_status": "partial",
    }
    assert snapshot["foreign_flow"]["capability_status"] == "ready"
    assert snapshot["foreign_flow"]["value_state"] == "explicit_zero"
    assert snapshot["foreign_flow"]["foreign_buy_volume"] == 0
    assert snapshot["foreign_flow"]["foreign_net_value"] == 0
    assert snapshot["intraday"]["status"] == "ok"
    assert snapshot["intraday"]["capability_status"] == "partial"
    assert snapshot["live_market"]["channels"]["intraday"] == "partial"
    assert snapshot["diagnostics"]["intraday"]["change_baseline"] == "first_session_candle_open"
    assert len(snapshot["quality_summary"]["groups"]) == 3
