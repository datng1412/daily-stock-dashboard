from __future__ import annotations

from datetime import date, timedelta

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


class FakeIndexFetcher:
    def __init__(
        self,
        *,
        index_list_payload=None,
        daily_payloads=None,
        components_payload=None,
    ):
        self.index_list_payload = index_list_payload or {
            "status": "ok",
            "source": "SSI",
            "rows": [
                {
                    "index_id": "VNINDEX_ID",
                    "index_code": "VNINDEX",
                    "index_name": "VN Index",
                    "exchange": "HOSE",
                    "market": "HOSE",
                    "source": "SSI",
                },
                {
                    "index_id": "VN30_ID",
                    "index_code": "VN30",
                    "index_name": "VN30 Index",
                    "exchange": "HOSE",
                    "market": "HOSE",
                    "source": "SSI",
                },
                {
                    "index_id": "HNX30",
                    "index_code": "HNX30",
                    "index_name": "HNX30 Index",
                    "exchange": "HNX",
                    "market": "HNX",
                    "source": "SSI",
                },
            ],
            "count": 3,
        }
        self.daily_payloads = daily_payloads or {
            "VNINDEX_ID": {
                "status": "ok",
                "source": "SSI",
                "rows": [
                    {
                        "date": "2026-06-27",
                        "index_code": "VNINDEX_ID",
                        "index_value": 1380.25,
                        "change": 5.5,
                        "change_pct": 0.4,
                        "total_volume": 123_000_000,
                        "total_value": 12_300_000_000_000,
                        "matched_volume": 120_000_000,
                        "matched_value": 12_000_000_000_000,
                        "put_through_volume": 3_000_000,
                        "put_through_value": 300_000_000_000,
                        "advances": 210,
                        "unchanged": 60,
                        "declines": 175,
                        "ceiling": 12,
                        "floor": 8,
                        "trading_session": "ATC",
                        "exchange": "HOSE",
                        "source": "SSI",
                    }
                ],
                "count": 1,
                "chunks_used": 2,
                "pages_used": 2,
            },
            "VN30_ID": {
                "status": "ok",
                "source": "SSI",
                "rows": [
                    {
                        "date": "2026-06-26",
                        "index_code": "VN30_ID",
                        "index_value": 1450.75,
                        "change": None,
                        "change_pct": None,
                        "total_volume": 50_000_000,
                        "total_value": None,
                        "matched_volume": None,
                        "matched_value": None,
                        "put_through_volume": 0,
                        "put_through_value": 0,
                        "advances": None,
                        "unchanged": None,
                        "declines": None,
                        "ceiling": None,
                        "floor": None,
                        "trading_session": None,
                        "exchange": "HOSE",
                        "source": "SSI",
                    }
                ],
                "count": 1,
                "chunks_used": 2,
                "pages_used": 2,
            },
        }
        self.components_payload = components_payload or {
            "status": "ok",
            "source": "SSI",
            "rows": [
                {
                    "index_code": "VN30_ID",
                    "symbol": "FPT",
                    "exchange": "HOSE",
                    "market": "HOSE",
                    "weight": 7.25,
                    "name": None,
                    "source": "SSI",
                }
            ],
            "count": 1,
        }
        self.index_list_calls = []
        self.daily_calls = []
        self.components_calls = []

    def get_index_list(self, market=None, **kwargs):
        self.index_list_calls.append({"market": market, **kwargs})
        return self.index_list_payload

    def get_daily_index(self, index_code, **kwargs):
        self.daily_calls.append({"index_code": index_code, **kwargs})
        return self.daily_payloads.get(
            index_code,
            {
                "status": "unavailable",
                "source": "SSI",
                "reason": "SSI FastConnect request failed",
                "rows": [],
            },
        )

    def get_index_components(self, index_code, market=None, **kwargs):
        self.components_calls.append(
            {"index_code": index_code, "market": market, **kwargs}
        )
        return self.components_payload

    def get_daily_ohlcv(self, symbol: str, **kwargs):
        start = date(2026, 5, 29)
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
            "status": "unavailable",
            "source": "SSI",
            "reason": "SSI FastConnect request failed",
            "rows": [],
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
                    "source": "SSI",
                }
            ],
        }

    def get_securities(self, **kwargs):
        return self.get_securities_details(symbol="FPT")


def _service(fetcher: FakeIndexFetcher) -> VietnamMarketService:
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
            include_intraday=False,
            news_provider="disabled",
            mozyfin_enabled=False,
            mozyfin_news_enabled=False,
            kbs_enabled=False,
            allow_legacy_kbs_provider=False,
        ),
        ssi_fetcher=fetcher,
    )


def test_index_list_keeps_ssi_rows_and_exposes_sanitized_coverage():
    fetcher = FakeIndexFetcher()
    payload = _service(fetcher).build_index_list("HOSE", force_refresh=True)

    assert payload["status"] == "ok"
    assert payload["source"] == "SSI IndexList"
    assert payload["count"] == 3
    assert [row["index_code"] for row in payload["rows"]] == [
        "VNINDEX",
        "VN30",
        "HNX30",
    ]
    assert payload["rows"][0]["source"] == "SSI IndexList"
    assert payload["rows"][0]["field_coverage"]["index_id"] is True
    assert payload["diagnostics"]["endpoint"] == "IndexList"
    assert payload["diagnostics"]["requested_market"] == "HOSE"
    assert payload["diagnostics"]["returned_markets"] == ["HNX", "HOSE"]
    assert "token" not in str(payload).lower()
    assert fetcher.index_list_calls == [{"market": "HOSE", "force_refresh": True}]


def test_index_list_unavailable_is_empty_and_non_fatal():
    fetcher = FakeIndexFetcher(
        index_list_payload={
            "status": "unavailable",
            "source": "SSI",
            "reason": "private provider payload",
            "rows": [],
        }
    )
    payload = _service(fetcher).build_index_list("HOSE")

    assert payload["status"] == "unavailable"
    assert payload["rows"] == []
    assert payload["count"] == 0
    assert payload["diagnostics"]["failure_class"] == "provider_unavailable"
    assert "private provider payload" not in str(payload)


def test_daily_index_resolves_ssi_identifiers_and_classifies_dates_and_missing_fields():
    fetcher = FakeIndexFetcher()
    payload = _service(fetcher).build_daily_indexes(
        ["VNINDEX", "VN30"],
        from_date="2026-06-01",
        to_date="2026-06-28",
        force_refresh=True,
    )

    assert payload["status"] == "ok"
    assert payload["source"] == "SSI DailyIndex"
    assert payload["latest_date"] == "2026-06-27"
    assert payload["count"] == 2
    assert [call["index_code"] for call in fetcher.daily_calls] == [
        "VNINDEX_ID",
        "VN30_ID",
    ]
    rows = {row["index_code"]: row for row in payload["rows"]}
    assert rows["VNINDEX"]["index_value"] == 1380.25
    assert rows["VNINDEX"]["date_match"] == "matched"
    assert rows["VNINDEX"]["source"] == "SSI DailyIndex"
    assert rows["VN30"]["date_match"] == "mismatched"
    assert rows["VN30"]["change"] is None
    assert rows["VN30"]["put_through_volume"] == 0
    assert rows["VN30"]["field_coverage"]["change"] is False
    assert "change" in rows["VN30"]["missing_fields"]
    assert payload["diagnostics"]["endpoint"] == "DailyIndex"
    assert payload["diagnostics"]["per_index"]["VNINDEX"]["selected_identifier"] == "VNINDEX_ID"
    assert "token" not in str(payload["diagnostics"]).lower()
    assert payload["fallback_used"] is False


def test_daily_index_unavailable_does_not_break_watchlist_or_latest_price():
    fetcher = FakeIndexFetcher(
        daily_payloads={
            "VNINDEX_ID": {
                "status": "unavailable",
                "source": "SSI",
                "reason": "SSI FastConnect request failed",
                "rows": [],
            }
        }
    )
    service = _service(fetcher)
    index_payload = service.build_daily_indexes(["VNINDEX"])
    item = service.build_watchlist(
        ["FPT"],
        force_refresh=True,
        include_intraday=False,
    )["watchlist"][0]

    assert index_payload["status"] == "unavailable"
    assert index_payload["rows"] == []
    assert index_payload["diagnostics"]["failure_class"] == "no_usable_rows"
    assert item["status"] == "ok"
    assert item["latest_price"] == 130.0
    assert item["latest_price_source"] == "SSI DailyOhlc"


def test_index_components_use_index_list_identifier_and_preserve_nulls():
    fetcher = FakeIndexFetcher()
    payload = _service(fetcher).build_index_components(
        "VN30",
        market="HOSE",
        force_refresh=True,
    )

    assert payload["status"] == "ok"
    assert payload["source"] == "SSI IndexComponents"
    assert payload["index_code"] == "VN30"
    assert payload["count"] == 1
    assert payload["rows"][0]["symbol"] == "FPT"
    assert payload["rows"][0]["name"] is None
    assert payload["rows"][0]["source"] == "SSI IndexComponents"
    assert payload["rows"][0]["field_coverage"]["name"] is False
    assert fetcher.components_calls == [
        {
            "index_code": "VN30_ID",
            "market": "HOSE",
            "force_refresh": True,
        }
    ]
    assert payload["diagnostics"]["selected_identifier"] == "VN30_ID"
    assert payload["diagnostics"]["index_identifier_source"] == "IndexList"


def test_unknown_vn30_identifier_does_not_call_components_or_hardcode_members():
    fetcher = FakeIndexFetcher(
        index_list_payload={
            "status": "ok",
            "source": "SSI",
            "rows": [
                {
                    "index_id": "VNINDEX_ID",
                    "index_code": "VNINDEX",
                    "source": "SSI",
                }
            ],
        }
    )
    payload = _service(fetcher).build_index_components("VN30", market="HOSE")

    assert payload["status"] == "unavailable"
    assert payload["rows"] == []
    assert payload["count"] == 0
    assert payload["diagnostics"]["failure_class"] == "identifier_not_found"
    assert fetcher.components_calls == []
    assert "FPT" not in str(payload)
