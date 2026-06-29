from __future__ import annotations

from datetime import date, timedelta

from src.services.vietnam_company_research_service import VietnamCompanyResearchService
from src.services.vietnam_market_service import (
    VietnamDashboardConfig,
    VietnamMarketService,
    clear_vietnam_cache,
)


class ExplodingManager:
    def _get_fetcher_by_name(self, name: str):  # pragma: no cover - failure path
        raise AssertionError(f"Legacy provider must not be requested: {name}")

    def get_daily_data(self, *args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("Legacy daily data must not be requested")


def _full_daily_stock_price_row(**overrides):
    row = {
        "date": "2026-06-30",
        "reference_price": 129.0,
        "ceiling_price": 138.0,
        "floor_price": 120.0,
        "open": 129.5,
        "high": 132.0,
        "low": 128.0,
        "close": 130.0,
        "adjusted_close": 130.0,
        "matched_volume": 1_234_567,
        "matched_value": 123_456_789_000,
        "put_through_volume": 0,
        "put_through_value": 0,
        "total_volume": 1_234_567,
        "total_value": 123_456_789_000,
        "foreign_buy_volume": 100_000,
        "foreign_sell_volume": 80_000,
        "foreign_net_volume": 20_000,
        "foreign_buy_value": 1_000_000_000,
        "foreign_sell_value": 800_000_000,
        "foreign_net_value": 200_000_000,
        "source": "SSI",
    }
    row.update(overrides)
    return row


class FakeSsiFetcher:
    def __init__(self, daily_stock_price_payload=None, *, daily_row_count: int = 30):
        self.daily_stock_price_payload = daily_stock_price_payload or {
            "status": "ok",
            "source": "SSI",
            "rows": [_full_daily_stock_price_row()],
        }
        self.daily_row_count = daily_row_count
        self.daily_stock_price_calls = []

    def get_daily_ohlcv(self, symbol: str, **kwargs):
        start = date(2026, 6, 1)
        rows = [
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
            for index in range(self.daily_row_count)
        ]
        return {"status": "ok", "source": "SSI", "rows": rows}

    def get_daily_stock_price(self, symbol: str, **kwargs):
        self.daily_stock_price_calls.append({"symbol": symbol, "kwargs": dict(kwargs)})
        return self.daily_stock_price_payload

    def get_securities_details(self, **kwargs):
        symbol = kwargs.get("symbol") or "FPT"
        return {
            "status": "ok",
            "source": "SSI",
            "rows": [{"symbol": symbol, "exchange": "HOSE", "market": "HOSE", "source": "SSI"}],
        }

    def get_securities(self, **kwargs):
        return self.get_securities_details(symbol="FPT")


def _service(fetcher: FakeSsiFetcher) -> VietnamMarketService:
    clear_vietnam_cache()
    return VietnamMarketService(
        manager=ExplodingManager(),
        config=VietnamDashboardConfig(
            daily_data_provider="ssi",
            chart_data_provider="ssi",
            daily_stock_price_provider="ssi",
            index_data_provider="ssi",
            intraday_data_provider="ssi",
            realtime_data_provider="ssi",
            trade_tape_provider="ssi",
            ssi_intraday_enabled=False,
            ssi_realtime_enabled=False,
            ssi_streaming_realtime_enabled=False,
            ssi_trade_tape_enabled=False,
            kbs_enabled=False,
            allow_legacy_kbs_provider=False,
            include_intraday=False,
            news_provider="disabled",
            mozyfin_enabled=False,
            mozyfin_news_enabled=False,
        ),
        ssi_fetcher=fetcher,
    )


def _watch_item(fetcher: FakeSsiFetcher):
    return _service(fetcher).build_watchlist(
        ["FPT"],
        force_refresh=True,
        include_intraday=False,
    )["watchlist"][0]


def _issue_codes(item):
    return {
        issue["code"]
        for issue in item["data_quality_summary"].get("issues", [])
    }


def test_watchlist_response_reports_requested_returned_and_missing_ticker_counts():
    payload = _service(FakeSsiFetcher()).build_watchlist(
        ["FPT", "FPT", "ACB", "@@@"],
        force_refresh=True,
        include_intraday=False,
    )

    assert payload["requested_tickers_count"] == 2
    assert payload["returned_rows_count"] == 2
    assert payload["missing_tickers"] == []
    assert payload["data_quality"]["requested_tickers_count"] == 2
    assert payload["data_quality"]["returned_rows_count"] == 2
    assert payload["data_quality"]["missing_tickers"] == []
    assert [row["ticker"] for row in payload["watchlist"]] == ["FPT", "ACB"]


def test_daily_stock_price_full_enrichment_is_source_labeled_unit_safe_and_aligned():
    item = _watch_item(FakeSsiFetcher())
    enrichment = item["daily_stock_price"]

    assert item["status"] == "ok"
    assert item["latest_price"] == item["daily_close"] == 130.0
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert enrichment["status"] == "ok"
    assert enrichment["quality_status"] == "ok"
    assert enrichment["source"] == "SSI DailyStockPrice"
    assert enrichment["date"] == "2026-06-30"
    assert enrichment["date_match"] == "matched"
    assert item["daily_stock_price_date_match"] == "matched"
    assert enrichment["reference_price"] == 129.0
    assert enrichment["ceiling_price"] == 138.0
    assert enrichment["floor_price"] == 120.0
    assert enrichment["matched_volume"] == 1_234_567
    assert enrichment["matched_value"] == 123_456_789_000
    assert enrichment["put_through_volume"] == 0
    assert enrichment["put_through_value"] == 0
    assert enrichment["foreign_net_volume"] == 20_000
    assert enrichment["foreign_net_value"] == 200_000_000
    assert enrichment["units"]["matched_volume"] == "shares"
    assert enrichment["units"]["matched_value"] == "VND"
    assert enrichment["units"]["foreign_net_volume"] == "shares"
    assert enrichment["units"]["foreign_net_value"] == "VND"
    assert enrichment["missing_fields"] == []
    assert enrichment["diagnostics"]["endpoint"] == "DailyStockPrice"
    assert enrichment["diagnostics"]["normalized_row_count"] == 1
    assert enrichment["diagnostics"]["daily_ohlc_date"] == "2026-06-30"
    assert "token" not in str(enrichment["diagnostics"]).lower()
    assert "authorization" not in str(enrichment["diagnostics"]).lower()


def test_daily_stock_price_history_populates_latest_available_foreign_flow_windows():
    rows = [
        _full_daily_stock_price_row(
            date=(date(2026, 6, 11) + timedelta(days=index)).isoformat(),
            foreign_buy_volume=100_000 + index,
            foreign_sell_volume=100_000,
            foreign_net_volume=index + 1,
        )
        for index in range(20)
    ]
    fetcher = FakeSsiFetcher({"status": "ok", "source": "SSI", "rows": rows})
    item = _watch_item(fetcher)
    indicators = item["indicators"]
    diagnostics = item["daily_stock_price"]["diagnostics"]

    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["daily_stock_price"]["date"] == "2026-06-30"
    assert item["daily_stock_price"]["foreign_net_volume"] == 20.0
    assert item["foreign"]["net"] == 20.0
    assert indicators["foreign_net_5d_latest_available"] == 90.0
    assert indicators["foreign_net_20d_latest_available"] == 210.0
    assert indicators["foreign_net_latest_available_date"] == "2026-06-30"
    assert indicators["foreign_net_history_count"] == 20
    assert diagnostics["foreign_history_row_count"] == 20
    assert diagnostics["foreign_history_net_row_count"] == 20
    assert diagnostics["foreign_history_date_start"] == "2026-06-11"
    assert diagnostics["foreign_history_date_end"] == "2026-06-30"
    assert diagnostics["foreign_history_status"] == "ok"
    assert len(fetcher.daily_stock_price_calls) == 1
    assert fetcher.daily_stock_price_calls[0]["symbol"] == "FPT"
    assert fetcher.daily_stock_price_calls[0]["kwargs"]["market"] == "HOSE"
    assert fetcher.daily_stock_price_calls[0]["kwargs"]["limit"] == 260
    assert fetcher.daily_stock_price_calls[0]["kwargs"]["from_date"]
    assert fetcher.daily_stock_price_calls[0]["kwargs"]["to_date"]


def test_daily_stock_price_history_partial_preserves_explicit_zero_foreign_net():
    rows = [
        _full_daily_stock_price_row(date="2026-06-27", foreign_net_volume=10),
        _full_daily_stock_price_row(date="2026-06-28", foreign_net_volume=-5),
        _full_daily_stock_price_row(date="2026-06-29", foreign_net_volume=0),
        _full_daily_stock_price_row(date="2026-06-30", foreign_net_volume=0),
    ]
    item = _watch_item(
        FakeSsiFetcher({"status": "ok", "source": "SSI", "rows": rows})
    )
    indicators = item["indicators"]
    diagnostics = item["daily_stock_price"]["diagnostics"]

    assert item["daily_stock_price"]["foreign_net_volume"] == 0.0
    assert item["foreign"]["net"] == 0.0
    assert item["foreign"]["signal"] == "neutral_or_unavailable"
    assert indicators["foreign_net_5d_latest_available"] is None
    assert indicators["foreign_net_20d_latest_available"] is None
    assert indicators["foreign_net_latest_available_date"] == "2026-06-30"
    assert indicators["foreign_net_history_count"] == 4
    assert diagnostics["foreign_history_net_row_count"] == 4
    assert diagnostics["foreign_history_status"] == "partial"


def test_daily_stock_price_date_mismatch_is_partial_without_changing_daily_price():
    row = _full_daily_stock_price_row(date="2026-06-29", close=999.0)
    item = _watch_item(
        FakeSsiFetcher({"status": "ok", "source": "SSI", "rows": [row]})
    )
    enrichment = item["daily_stock_price"]

    assert item["status"] == "ok"
    assert item["latest_price"] == 130.0
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["daily_close"] == 130.0
    assert enrichment["close"] == 999.0
    assert enrichment["date_match"] == "mismatched"
    assert enrichment["quality_status"] == "partial"
    assert enrichment["staleness_reason"] == "DailyStockPrice date differs from DailyOhlc."
    assert item["data_quality_summary"]["checks"]["daily_stock_price"] == "partial"
    assert "daily_stock_price_date_mismatch" in _issue_codes(item)


def test_daily_stock_price_missing_date_and_fields_remain_unknown_and_null():
    row = _full_daily_stock_price_row(
        date=None,
        matched_volume=None,
        matched_value=None,
        put_through_volume=None,
        put_through_value=None,
        foreign_buy_value=None,
        foreign_sell_value=None,
        foreign_net_value=None,
    )
    item = _watch_item(
        FakeSsiFetcher({"status": "ok", "source": "SSI", "rows": [row]})
    )
    enrichment = item["daily_stock_price"]

    assert item["status"] == "ok"
    assert enrichment["status"] == "ok"
    assert enrichment["quality_status"] == "partial"
    assert enrichment["date"] is None
    assert enrichment["date_match"] == "unknown"
    assert enrichment["matched_volume"] is None
    assert enrichment["matched_value"] is None
    assert enrichment["put_through_volume"] is None
    assert enrichment["foreign_net_value"] is None
    assert "matched_volume" in enrichment["missing_fields"]
    assert "matched_volume" not in enrichment["units"]
    assert "foreign_net_value" not in enrichment["units"]
    assert item["latest_price_source"] == "SSI DailyOhlc"


def test_daily_stock_price_unavailable_does_not_invalidate_daily_ohlcv():
    item = _watch_item(
        FakeSsiFetcher(
            {
                "status": "unavailable",
                "source": "SSI",
                "reason": "SSI FastConnect unavailable",
                "rows": [],
            }
        )
    )
    enrichment = item["daily_stock_price"]

    assert item["status"] == "ok"
    assert item["latest_price"] == 130.0
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert enrichment["status"] == "unavailable"
    assert enrichment["quality_status"] == "unavailable"
    assert enrichment["date_match"] == "unavailable"
    assert enrichment["units"] == {}
    assert item["data_quality_summary"]["checks"]["daily_stock_price"] == "unavailable"
    assert "daily_stock_price_missing" in _issue_codes(item)
    assert "foreign_flow_missing" in _issue_codes(item)


def test_short_daily_ohlc_history_exposes_ta_missing_reasons_without_changing_latest_price():
    item = _watch_item(FakeSsiFetcher(daily_row_count=10))

    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["rows_loaded"] == 10
    codes = _issue_codes(item)
    assert "ta_insufficient_history" in codes
    assert "rsi_missing" in codes
    assert "ma_state_insufficient_data" in codes


def test_daily_stock_price_close_mismatch_is_diagnostic_only_and_volume_stays_separate():
    row = _full_daily_stock_price_row(close=131.0, matched_volume=1_500_000)
    item = _watch_item(
        FakeSsiFetcher({"status": "ok", "source": "SSI", "rows": [row]})
    )
    mismatch = next(
        issue
        for issue in item["data_quality_summary"]["issues"]
        if issue["code"] == "daily_ohlc_vs_daily_stock_price_mismatch"
    )

    assert item["latest_price"] == 130.0
    assert item["volume"] == 1_000_029
    assert item["daily_stock_price"]["matched_volume"] == 1_500_000
    assert mismatch["fields"]["daily_ohlc_source"] == "SSI DailyOhlc"
    assert mismatch["fields"]["daily_stock_price_source"] == "SSI DailyStockPrice"
    assert "daily_ohlc_vs_daily_stock_price_volume_mismatch" not in _issue_codes(item)


def test_company_snapshot_preserves_daily_stock_price_block_and_units():
    snapshot = VietnamCompanyResearchService(
        market_service=_service(FakeSsiFetcher())
    ).get_company_research_snapshot("FPT", force_refresh=True)

    assert snapshot["price"]["canonical_source"] == "SSI DailyOhlc"
    assert snapshot["daily_stock_price"]["source"] == "SSI DailyStockPrice"
    assert snapshot["daily_stock_price"]["date_match"] == "matched"
    assert snapshot["foreign_flow"]["source"] == "SSI DailyStockPrice"
    assert snapshot["foreign_flow"]["volume_unit"] == "shares"
    assert snapshot["foreign_flow"]["value_unit"] == "VND"
    assert snapshot["foreign_flow"]["date_match"] == "matched"
