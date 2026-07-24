"""Offline daily-history freshness and canonical-price regression tests."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List

import pytest

from src.services.vietnam_market_service import (
    VietnamDashboardConfig,
    VietnamMarketService,
    clear_vietnam_cache,
)


def _daily_rows(end_date: str, count: int = 40) -> List[Dict[str, Any]]:
    candidate = date.fromisoformat(end_date)
    dates: List[date] = []
    while len(dates) < count:
        if candidate.weekday() < 5:
            dates.append(candidate)
        candidate -= timedelta(days=1)
    dates.reverse()
    return [
        {
            "date": value.isoformat(),
            "open": 60_000 + index,
            "high": 60_100 + index,
            "low": 59_900 + index,
            "close": 60_050 + index,
            "volume": 1_000_000 + index,
            "value": 60_000_000_000 + index,
        }
        for index, value in enumerate(dates)
    ]


class DailyFreshnessProvider:
    def __init__(
        self,
        *,
        daily_rows: List[Dict[str, Any]],
        daily_status: str = "ok",
        daily_stock_date: str = "2026-07-23",
        daily_stock_close: float = 64_700,
    ) -> None:
        self.daily_rows = daily_rows
        self.daily_status = daily_status
        self.daily_stock_date = daily_stock_date
        self.daily_stock_close = daily_stock_close
        self.daily_calls = 0

    def get_daily_ohlcv(self, _symbol: str, **_kwargs: Any) -> Dict[str, Any]:
        self.daily_calls += 1
        return {
            "status": self.daily_status,
            "reason": (
                "SSI V3 daily history is incomplete."
                if self.daily_status != "ok"
                else None
            ),
            "rows": list(self.daily_rows),
            "diagnostics": {
                "provider_version": "v3",
                "source_endpoint": "securitiesSummary",
                "adapter": "SsiFastConnectV3Adapter",
                "normalized_row_count": len(self.daily_rows),
                "min_date": self.daily_rows[0]["date"] if self.daily_rows else None,
                "max_date": self.daily_rows[-1]["date"] if self.daily_rows else None,
                "freshness_status": (
                    "fresh" if self.daily_status == "ok" else "stale"
                ),
            },
        }

    def get_daily_stock_price(
        self, _symbol: str, **_kwargs: Any
    ) -> Dict[str, Any]:
        return {
            "status": "ok",
            "rows": [
                {
                    "date": self.daily_stock_date,
                    "close": self.daily_stock_close,
                    "reference_price": 64_000,
                    "foreign_buy_volume": None,
                    "foreign_sell_volume": None,
                    "foreign_net_volume": None,
                    "foreign_buy_value": None,
                    "foreign_sell_value": None,
                    "foreign_net_value": None,
                }
            ],
            "diagnostics": {"provider_version": "v3"},
        }

    def get_security_basic_info(self, _symbol: str) -> Dict[str, Any]:
        return {
            "status": "ok",
            "rows": [
                {
                    "symbol": "FPT",
                    "exchange": "HOSE",
                    "market": "HOSE",
                    "name": "FPT",
                }
            ],
        }


def _service(provider: DailyFreshnessProvider) -> VietnamMarketService:
    return VietnamMarketService(
        config=VietnamDashboardConfig(
            daily_data_provider="ssi",
            chart_data_provider="ssi",
            daily_stock_price_provider="ssi",
            include_intraday=False,
            ssi_intraday_enabled=False,
            ssi_realtime_enabled=False,
            ssi_streaming_realtime_enabled=False,
            ssi_trade_tape_enabled=False,
            news_provider="disabled",
            mozyfin_enabled=False,
            allow_legacy_mozyfin_provider=False,
        ),
        ssi_fetcher=provider,
    )


@pytest.fixture(autouse=True)
def _isolated_cache() -> None:
    clear_vietnam_cache()
    yield
    clear_vietnam_cache()


def test_months_old_daily_history_cannot_be_canonical_or_drive_indicators() -> None:
    provider = DailyFreshnessProvider(daily_rows=_daily_rows("2026-03-05"))

    row = _service(provider).build_watchlist(
        ["FPT"], force_refresh=True, include_intraday=False
    )["watchlist"][0]

    assert row["status"] == "partial"
    assert row["ohlcv_date"] == "2026-03-05"
    assert row["latest_price"] == 64_700
    assert row["latest_price_source"] == "SSI DailyStockPrice"
    assert row["latest_price_date"] == "2026-07-23"
    assert row["indicators"] == {}
    assert row["diagnostics"]["daily_history"]["freshness_status"] == "stale"
    assert row["data_quality_summary"]["checks"]["daily_ohlc"] == "stale"
    assert (
        row["data_quality_summary"]["canonical_price_source"]
        == "SSI DailyStockPrice"
    )


def test_fresh_daily_history_keeps_daily_ohlc_canonical_and_restores_indicators() -> None:
    provider = DailyFreshnessProvider(daily_rows=_daily_rows("2026-07-23"))

    row = _service(provider).build_watchlist(
        ["FPT"], force_refresh=True, include_intraday=False
    )["watchlist"][0]

    assert row["status"] == "ok"
    assert row["latest_price"] == row["ohlcv_close"]
    assert row["latest_price_source"] == "SSI DailyOhlc"
    assert row["diagnostics"]["daily_history"]["freshness_status"] == "fresh"
    assert row["indicators"]["ma20"] is not None
    assert row["indicators"]["rsi14_wilder"] is not None


def test_foreign_nulls_remain_null_instead_of_becoming_zero() -> None:
    provider = DailyFreshnessProvider(daily_rows=_daily_rows("2026-07-23"))

    row = _service(provider).build_watchlist(
        ["FPT"], force_refresh=True, include_intraday=False
    )["watchlist"][0]

    assert row["ssi_foreign_net_volume"] is None
    assert row["ssi_foreign_net_value"] is None
    assert row["foreign"]["buy"] is None
    assert row["foreign"]["sell"] is None
    assert row["foreign"]["net"] is None


def test_incomplete_daily_result_is_not_cached_as_ok_and_force_refresh_preserves_valid_stale() -> None:
    complete = DailyFreshnessProvider(daily_rows=_daily_rows("2026-07-23"))
    first = _service(complete).build_watchlist(
        ["FPT"], force_refresh=True, include_intraday=False
    )["watchlist"][0]
    incomplete = DailyFreshnessProvider(
        daily_rows=_daily_rows("2026-03-05"),
        daily_status="partial",
    )

    refreshed = _service(incomplete).build_watchlist(
        ["FPT"], force_refresh=True, include_intraday=False
    )["watchlist"][0]

    assert first["cache_status"]["ohlcv_cache"] == "refresh"
    assert incomplete.daily_calls == 1
    assert refreshed["cache_status"]["ohlcv_cache"] == "stale"
    assert refreshed["ohlcv_date"] == "2026-07-23"
    assert refreshed["latest_price_source"] == "SSI DailyOhlc"
