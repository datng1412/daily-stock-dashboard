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


def _full_metadata_row(**overrides):
    row = {
        "symbol": "FPT",
        "exchange": "HOSE",
        "market": "HOSE",
        "security_type": "stock",
        "name": "Công ty Cổ phần FPT",
        "name_en": "FPT Corporation",
        "industry": "Information Technology",
        "sector": "Technology",
        "issuer": "FPT",
        "lot_size": 100,
        "listed_shares": 1_471_000_000,
        "listed_date": "2006-12-13",
        "source": "SSI",
    }
    row.update(overrides)
    return row


def _daily_stock_price_row():
    return {
        "date": "2026-06-30",
        "reference_price": 129.0,
        "ceiling_price": 138.0,
        "floor_price": 120.0,
        "close": 130.0,
        "adjusted_close": 130.0,
        "matched_volume": 1_234_567,
        "matched_value": 123_456_789_000,
        "put_through_volume": 0,
        "put_through_value": 0,
        "foreign_buy_volume": 100_000,
        "foreign_sell_volume": 80_000,
        "foreign_net_volume": 20_000,
        "foreign_buy_value": 1_000_000_000,
        "foreign_sell_value": 800_000_000,
        "foreign_net_value": 200_000_000,
        "source": "SSI",
    }


class FakeSsiFetcher:
    def __init__(self, *, details_payload=None, securities_payload=None):
        self.details_payload = details_payload or {
            "status": "ok",
            "source": "SSI",
            "rows": [_full_metadata_row()],
        }
        self.securities_payload = securities_payload or {
            "status": "ok",
            "source": "SSI",
            "rows": [_full_metadata_row()],
        }
        self.details_calls = 0
        self.securities_calls = 0

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
            for index in range(30)
        ]
        return {"status": "ok", "source": "SSI", "rows": rows}

    def get_daily_stock_price(self, symbol: str, **kwargs):
        return {
            "status": "ok",
            "source": "SSI",
            "rows": [_daily_stock_price_row()],
        }

    def get_securities_details(self, **kwargs):
        self.details_calls += 1
        return self.details_payload

    def get_securities(self, **kwargs):
        self.securities_calls += 1
        return self.securities_payload


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


def test_securities_details_complete_metadata_is_source_labeled_and_sanitized():
    fetcher = FakeSsiFetcher()
    item = _watch_item(fetcher)
    metadata = item["symbol_metadata"]

    assert item["status"] == "ok"
    assert item["latest_price"] == 130.0
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["daily_stock_price"]["status"] == "ok"
    assert metadata["status"] == "ok"
    assert metadata["quality_status"] == "complete"
    assert metadata["completeness"] == 1.0
    assert metadata["source"] == "SSI SecuritiesDetails"
    assert metadata["symbol"] == "FPT"
    assert metadata["name"] == "Công ty Cổ phần FPT"
    assert metadata["name_en"] == "FPT Corporation"
    assert metadata["industry"] == "Information Technology"
    assert metadata["sector"] == "Technology"
    assert metadata["security_type"] == "stock"
    assert metadata["issuer"] == "FPT"
    assert metadata["lot_size"] == 100
    assert metadata["listed_shares"] == 1_471_000_000
    assert metadata["listed_date"] == "2006-12-13"
    assert metadata["missing_fields"] == []
    assert metadata["diagnostics"]["endpoint"] == "SecuritiesDetails"
    assert metadata["diagnostics"]["requested_symbol"] == "FPT"
    assert metadata["diagnostics"]["normalized_row_count"] == 1
    assert metadata["diagnostics"]["selected_row_source"] == "SSI SecuritiesDetails"
    assert "token" not in str(metadata["diagnostics"]).lower()
    assert "authorization" not in str(metadata["diagnostics"]).lower()
    assert fetcher.details_calls == 1
    assert fetcher.securities_calls == 0


def test_partial_metadata_keeps_missing_values_null_and_daily_row_usable():
    partial_row = _full_metadata_row(
        name=None,
        name_en=None,
        industry=None,
        sector=None,
        security_type=None,
        issuer=None,
        lot_size=None,
        listed_shares=None,
        listed_date=None,
    )
    item = _watch_item(
        FakeSsiFetcher(
            details_payload={"status": "ok", "source": "SSI", "rows": [partial_row]}
        )
    )
    metadata = item["symbol_metadata"]

    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["daily_stock_price"]["status"] == "ok"
    assert metadata["status"] == "ok"
    assert metadata["quality_status"] == "partial"
    assert metadata["symbol"] == "FPT"
    assert metadata["exchange"] == "HOSE"
    assert metadata["market"] == "HOSE"
    assert metadata["name"] is None
    assert metadata["industry"] is None
    assert metadata["issuer"] is None
    assert metadata["lot_size"] is None
    assert metadata["listed_shares"] is None
    assert metadata["listed_date"] is None
    assert "name" in metadata["missing_fields"]
    assert metadata["field_coverage"]["name"] is False
    assert item["data_quality_summary"]["checks"]["profile"] == "partial"
    assert "profile_partial" in _issue_codes(item)


def test_metadata_falls_back_only_to_ssi_securities():
    fetcher = FakeSsiFetcher(
        details_payload={
            "status": "unavailable",
            "source": "SSI",
            "reason": "SSI FastConnect request failed",
            "rows": [],
        },
        securities_payload={
            "status": "ok",
            "source": "SSI",
            "rows": [_full_metadata_row()],
        },
    )
    item = _watch_item(fetcher)
    metadata = item["symbol_metadata"]

    assert metadata["status"] == "ok"
    assert metadata["quality_status"] == "complete"
    assert metadata["source"] == "SSI Securities"
    assert metadata["diagnostics"]["attempted_endpoints"] == [
        "SecuritiesDetails",
        "Securities",
    ]
    assert metadata["diagnostics"]["fallback_within_ssi"] is True
    assert fetcher.details_calls == 1
    assert fetcher.securities_calls == 1
    assert item["fallback_used"] is False


def test_metadata_unavailable_is_non_fatal_and_does_not_infer_fields():
    unavailable = {
        "status": "unavailable",
        "source": "SSI",
        "reason": "private provider response must not be exposed",
        "rows": [],
    }
    item = _watch_item(
        FakeSsiFetcher(
            details_payload=unavailable,
            securities_payload=unavailable,
        )
    )
    metadata = item["symbol_metadata"]

    assert item["status"] == "ok"
    assert item["latest_price"] == 130.0
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["daily_stock_price"]["status"] == "ok"
    assert metadata["status"] == "unavailable"
    assert metadata["quality_status"] == "unavailable"
    assert metadata["completeness"] == 0.0
    assert metadata["name"] is None
    assert metadata["industry"] is None
    assert metadata["sector"] is None
    assert metadata["issuer"] is None
    assert metadata["diagnostics"]["failure_class"] == "provider_unavailable"
    assert "private provider response" not in str(metadata)
    assert item["data_quality_summary"]["checks"]["profile"] == "unavailable"
    assert "profile_unavailable" in _issue_codes(item)


def test_metadata_row_without_requested_symbol_is_not_silently_selected():
    wrong_row = _full_metadata_row(symbol=None, name="Wrong company")
    item = _watch_item(
        FakeSsiFetcher(
            details_payload={"status": "ok", "source": "SSI", "rows": [wrong_row]},
            securities_payload={"status": "ok", "source": "SSI", "rows": [wrong_row]},
        )
    )

    assert item["status"] == "ok"
    assert item["symbol_metadata"]["status"] == "unavailable"
    assert item["symbol_metadata"]["diagnostics"]["failure_class"] == "no_matching_symbol"
    assert item["company_name"] is None


def test_company_snapshot_preserves_partial_profile_without_hiding_market_data():
    partial_row = _full_metadata_row(
        name=None,
        name_en=None,
        industry=None,
        sector=None,
        issuer=None,
        security_type=None,
        lot_size=None,
        listed_shares=None,
        listed_date=None,
    )
    snapshot = VietnamCompanyResearchService(
        market_service=_service(
            FakeSsiFetcher(
                details_payload={"status": "ok", "source": "SSI", "rows": [partial_row]}
            )
        )
    ).get_company_research_snapshot("FPT", force_refresh=True)

    assert snapshot["status"] == "ok"
    assert snapshot["profile"]["status"] == "ok"
    assert snapshot["profile"]["quality_status"] == "partial"
    assert snapshot["profile"]["name"] is None
    assert snapshot["profile"]["exchange"] == "HOSE"
    assert snapshot["profile"]["market"] == "HOSE"
    assert snapshot["profile"]["industry"] is None
    assert snapshot["price"]["canonical_source"] == "SSI DailyOhlc"
    assert snapshot["daily_stock_price"]["source"] == "SSI DailyStockPrice"
    coverage = {item["block"]: item for item in snapshot["source_coverage"]}
    assert coverage["Profile"]["status"] == "partial"
