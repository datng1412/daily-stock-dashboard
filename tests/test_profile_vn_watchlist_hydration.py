from __future__ import annotations

import json

import pytest

from scripts.profile_vn_watchlist_hydration import (
    MAX_PROFILE_TICKERS,
    parse_profile_tickers,
    profile_watchlist_case,
)


def test_profile_ticker_parsing_is_normalized_deduplicated_and_bounded():
    assert parse_profile_tickers(" fpt,HPG.vn,FPT ") == ["FPT", "HPG"]

    with pytest.raises(ValueError, match="invalid_ticker"):
        parse_profile_tickers("FPT,@@@")
    with pytest.raises(ValueError, match="ticker_limit_exceeded"):
        parse_profile_tickers(",".join(f"T{index:02d}" for index in range(11)))

    thirty = [f"T{index:02d}" for index in range(MAX_PROFILE_TICKERS)]
    assert parse_profile_tickers(",".join(thirty), allow_thirty=True) == thirty


class _FakeProfileService:
    def __init__(self):
        self.stage_seconds = {"daily_ohlcv_provider": 0.1}
        self.per_ticker_seconds = {"FPT": 0.2}

    def build_watchlist(self, tickers, **kwargs):
        return {
            "watchlist": [
                {
                    "ticker": tickers[0],
                    "status": "ok",
                    "latest_price_source": "SSI DailyOhlc",
                    "daily_stock_price": {"status": "ok"},
                    "cache_status": {
                        "ohlcv_cache": "miss",
                        "daily_stock_price_cache": "miss",
                        "intraday_cache": "disabled",
                        "realtime_cache": "disabled",
                        "trade_tape_cache": "disabled",
                    },
                }
            ]
        }


def test_profile_summary_contains_only_bounded_aggregate_data():
    result = profile_watchlist_case(
        "test",
        ["FPT"],
        include_intraday=False,
        service_factory=_FakeProfileService,
        clear_cache=False,
    )
    encoded = json.dumps(result)

    assert result["ticker_count"] == 1
    assert result["runs"][0]["status"] == "ok"
    assert result["runs"][0]["latest_price_sources"] == ["SSI DailyOhlc"]
    assert result["runs"][0]["cache_status_counts"]["daily_stock_price_cache"] == {"miss": 1}
    assert "consumerSecret" not in encoded
    assert "Authorization" not in encoded
    assert "Bearer " not in encoded


class _ExplodingProfileService:
    def __init__(self):
        self.stage_seconds = {}
        self.per_ticker_seconds = {}

    def build_watchlist(self, tickers, **kwargs):
        raise RuntimeError("Authorization: Bearer should-never-appear consumerSecret=should-never-appear")


def test_profile_failure_does_not_emit_exception_message_or_secret_text():
    result = profile_watchlist_case(
        "test",
        ["FPT"],
        service_factory=_ExplodingProfileService,
        clear_cache=False,
    )
    encoded = json.dumps(result)

    assert result["runs"][0]["status"] == "error"
    assert result["runs"][0]["error_type"] == "RuntimeError"
    assert "should-never-appear" not in encoded
    assert "Authorization" not in encoded
