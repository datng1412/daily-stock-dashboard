from datetime import datetime
from zoneinfo import ZoneInfo

from src.services.vietnam_company_research_service import VietnamCompanyResearchService


VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _epoch(value: str) -> float:
    return datetime.fromisoformat(value).replace(tzinfo=VN_TZ).timestamp()


def _row(
    *,
    daily_date: str = "2026-07-27",
    live_date: str | None = "2026-07-28",
) -> dict:
    return {
        "ticker": "FPT",
        "status": "ok",
        "company_name": "FPT Corporation",
        "exchange": "HOSE",
        "market": "HOSE",
        "latest_price": 101.0,
        "daily_close": 101.0,
        "latest_price_date": daily_date,
        "open": 99.0,
        "high": 102.0,
        "low": 98.0,
        "close": 101.0,
        "volume": 1_000,
        "amount": 101_000,
        "latest_price_source": "SSI DailyOhlc",
        "symbol_metadata": {
            "status": "ok",
            "name": "FPT Corporation",
            "exchange": "HOSE",
            "market": "HOSE",
            "industry": "Software",
            "sector": "Information Technology",
            "source": "SSI SecuritiesDetails",
            "quality_status": "partial",
            "missing_fields": ["name_en", "listed_date"],
        },
        "daily_stock_price": {
            "status": "ok",
            "quality_status": "partial",
            "date": daily_date,
            "reference_price": 97.0,
            "ceiling_price": 113.0,
            "floor_price": 83.0,
            "matched_volume": 1_000,
            "matched_value": 101_000,
            "foreign_buy_volume": 20,
            "foreign_sell_volume": 10,
            "foreign_net_volume": 10,
        },
        # Deliberately different: this exchange-derived block must never win.
        "price_limit": {
            "reference_price": 777.0,
            "ceiling_price": 888.0,
            "floor_price": 666.0,
            "source": "derived",
        },
        "foreign": {},
        "indicators": {"ma20": 100.0, "rsi14_wilder": 51.0},
        "intraday_status": {"status": "unavailable", "message": "No rows."},
        "intraday_candles": [],
        "intraday_pulse": None,
        "realtime_status": {
            "status": "unavailable",
            "reason_code": "stream_cache_empty",
        },
        "realtime_snapshot": None,
        "trade_tape_status": {
            "status": "unavailable",
            "reason_code": "recovering",
        },
        "trade_tape": [],
        "order_book_status": {"status": "ok", "source": "SSI X-QUOTE"},
        "order_book": {
            "ticker": "FPT",
            "trading_date": live_date,
            "stream_timestamp": (
                f"{live_date}T09:20:10+07:00" if live_date is not None else None
            ),
            "age_seconds": 0,
            "bids": [{"level": 1, "price": 100.0, "volume": 10}],
            "asks": [{"level": 1, "price": 101.0, "volume": 20}],
        },
        "diagnostics": {"daily_history": {"freshness_status": "fresh"}},
        "data_quality_summary": {
            "overall_status": "partial",
            "issues": [
                {"code": "profile_partial", "severity": "info"},
                {"code": "profile_partial", "severity": "info"},
                {"code": "daily_stock_price_partial", "severity": "warning"},
            ],
            "checks": {},
        },
        "warnings": [
            "Final close status is unknown; daily candle may still be in progress.",
            "Adjusted/unadjusted price status is unknown.",
        ],
        "news": [],
    }


class _StubMarketService:
    def __init__(self, row: dict) -> None:
        self.row = row

    def build_watchlist(self, symbols=None, **kwargs):
        return {"watchlist": [self.row]}


def _snapshot(row: dict, now: str) -> dict:
    service = VietnamCompanyResearchService(
        market_service=_StubMarketService(row),
        time_func=lambda: _epoch(now),
    )
    return service.get_company_research_snapshot("FPT")


def test_prior_daily_session_is_completed_while_order_book_is_current_and_ready():
    payload = _snapshot(_row(), "2026-07-28T09:20:30")

    assert payload["session_context"]["completed_session_date"] == "2026-07-27"
    assert payload["session_context"]["live_session_date"] == "2026-07-28"
    assert payload["session_context"]["source_freshness"] == "latest_completed"
    assert payload["price"]["final_close_status"] == "completed"
    assert payload["live_market"]["status"] == "partial"
    assert payload["live_market"]["channels"] == {
        "last_price": "no_data",
        "order_book": "ready",
        "trade_tape": "reconnecting",
        "intraday": "unavailable",
    }


def test_same_session_daily_row_is_provisional_during_active_market():
    payload = _snapshot(
        _row(daily_date="2026-07-28", live_date="2026-07-28"),
        "2026-07-28T10:00:00",
    )

    assert payload["price"]["source_freshness"] == "current"
    assert payload["price"]["final_close_status"] == "provisional"


def test_weekend_daily_row_is_latest_completed_without_holiday_claim():
    payload = _snapshot(
        _row(daily_date="2026-07-24", live_date=None),
        "2026-07-25T10:00:00",
    )

    assert payload["price"]["source_freshness"] == "latest_completed"
    assert payload["price"]["final_close_status"] == "completed"
    assert payload["session_context"]["holiday_aware"] is False


def test_provider_stale_diagnostic_becomes_publication_lag_not_cache_stale():
    row = _row(daily_date="2026-07-24", live_date="2026-07-28")
    row["diagnostics"]["daily_history"]["freshness_status"] = "stale"
    payload = _snapshot(row, "2026-07-28T10:00:00")

    assert payload["price"]["source_freshness"] == "publication_lag"
    assert payload["price"]["final_close_status"] == "completed"
    assert payload["session_context"]["cache_age_seconds"] == 0


def test_price_lineage_capabilities_profile_and_quality_are_independent():
    payload = _snapshot(_row(), "2026-07-28T09:20:30")

    assert payload["price"]["reference_price"] == 97.0
    assert payload["price"]["ceiling_price"] == 113.0
    assert payload["price"]["floor_price"] == 83.0
    assert payload["price"]["reference_price_source"] == "SSI DailyStockPrice"
    assert payload["profile"]["core_profile_status"] == "ready"
    assert payload["profile"]["optional_metadata_status"] == "incomplete"
    capabilities = payload["diagnostics"]["daily_stock_price_capabilities"]
    assert capabilities["daily_price_limits_status"] == "ready"
    assert capabilities["matched_stats_status"] == "ready"
    assert capabilities["put_through_status"] == "unavailable"
    assert capabilities["foreign_flow_status"] == "ready"
    assert payload["price"]["adjustment_status"] == "not_provided"
    assert payload["warnings"] == []
    assert payload["quality_summary"]["issue_codes"] == [
        "profile_partial",
        "daily_stock_price_partial",
    ]
    assert len(payload["quality_summary"]["groups"]) == 3


def test_missing_price_limits_stay_null_while_other_daily_capabilities_remain_ready():
    row = _row()
    for field in ("reference_price", "ceiling_price", "floor_price"):
        row["daily_stock_price"][field] = None
    row["ssi_reference_price"] = None
    row["ssi_ceiling_price"] = None
    row["ssi_floor_price"] = None
    payload = _snapshot(row, "2026-07-28T09:20:30")

    assert payload["price"]["reference_price"] is None
    assert payload["price"]["ceiling_price"] is None
    assert payload["price"]["floor_price"] is None
    capabilities = payload["diagnostics"]["daily_stock_price_capabilities"]
    assert capabilities["daily_price_limits_status"] == "unavailable"
    assert capabilities["foreign_flow_status"] == "ready"
    assert capabilities["matched_stats_status"] == "ready"
    assert capabilities["put_through_status"] == "unavailable"
