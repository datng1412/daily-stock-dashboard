"""Provider-session freshness tests for SSI V3 DailyStockPrice foreign flow."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.services.vietnam_market_service import VietnamMarketService


VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _row(date: str, **overrides):
    return {
        "date": date,
        "foreign_buy_volume": 0,
        "foreign_sell_volume": 0,
        "foreign_net_volume": 0,
        "foreign_buy_value": 0,
        "foreign_sell_value": 0,
        "foreign_net_value": 0,
        **overrides,
    }


def _normalize(
    date: str,
    *,
    now: datetime,
    requested_date: str = "2026-07-24",
    provider_dates=None,
    daily_ohlc_date: str = "2026-07-24",
):
    return VietnamMarketService._normalize_ssi_daily_stock_price_enrichment(
        _row(date),
        daily_ohlc_date=daily_ohlc_date,
        diagnostics={
            "to_date": requested_date,
            "provider_session_dates": provider_dates or [date],
        },
        now_epoch=now.timestamp(),
    )


def test_previous_session_during_active_market_is_partial_and_keeps_actual_date_and_zero():
    result = _normalize(
        "2026-07-23",
        now=datetime(2026, 7, 24, 10, 0, tzinfo=VN_TZ),
    )

    assert result["status"] == "partial"
    assert result["freshness_status"] == "previous_session_during_live_market"
    assert result["data_date"] == "2026-07-23"
    assert result["requested_date"] == "2026-07-24"
    assert result["is_current_session"] is False
    assert result["is_completed_session"] is True
    assert result["session_lag"] == 1
    assert result["foreign_net_value"] == 0.0


def test_current_session_row_is_provisional():
    result = _normalize(
        "2026-07-24",
        now=datetime(2026, 7, 24, 10, 0, tzinfo=VN_TZ),
    )

    assert result["status"] == "ok"
    assert result["freshness_status"] == "current_session_provisional"
    assert result["is_current_session"] is True
    assert result["is_provisional"] is True
    assert result["is_completed_session"] is False


def test_latest_completed_session_outside_market_is_ok():
    result = _normalize(
        "2026-07-23",
        now=datetime(2026, 7, 24, 16, 0, tzinfo=VN_TZ),
        daily_ohlc_date="2026-07-23",
    )

    assert result["status"] == "ok"
    assert result["freshness_status"] == "latest_completed_session"
    assert result["is_completed_session"] is True
    assert result["is_stale"] is False


def test_older_provider_row_is_stale_history():
    result = _normalize(
        "2026-07-22",
        now=datetime(2026, 7, 24, 16, 0, tzinfo=VN_TZ),
        provider_dates=["2026-07-22", "2026-07-23"],
        daily_ohlc_date="2026-07-23",
    )

    assert result["status"] == "partial"
    assert result["freshness_status"] == "stale_history"
    assert result["is_stale"] is True
    assert result["session_lag"] == 1


def test_missing_row_contract_is_unavailable_and_does_not_synthesize_current_values():
    result = VietnamMarketService._unavailable_ssi_daily_stock_price(
        reason="empty",
        daily_ohlc_date="2026-07-24",
        diagnostics={"to_date": "2026-07-24"},
    )

    assert result["status"] == "unavailable"
    assert result["freshness_status"] == "unavailable"
    assert result["data_date"] is None
    assert result.get("foreign_net_value") is None
