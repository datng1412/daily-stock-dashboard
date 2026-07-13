"""Deterministic SSI DailyOhlc-only short-term zone tests."""

from __future__ import annotations

import pandas as pd

from src.services.vietnam_market_service import (
    _normalized_short_term_zone_history,
    calculate_short_term_zones,
    calculate_vietnam_indicators,
)


def _daily_history() -> pd.DataFrame:
    rows = []
    for index, date in enumerate(pd.date_range("2026-01-01", periods=60, freq="B")):
        rows.append({"date": date.date().isoformat(), "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1_000})
    for index, low in ((10, 90.0), (20, 92.0)):
        rows[index]["low"] = low
    for index, high in ((30, 110.0), (40, 112.0)):
        rows[index]["high"] = high
    return pd.DataFrame(rows)


def test_short_term_zones_use_exactly_sixty_valid_daily_rows_and_are_nearest_first():
    zones = calculate_short_term_zones(_daily_history())

    assert zones["status"] == "ok"
    assert zones["reason_code"] == "short_term_zones_ready"
    assert zones["source"] == "derived from SSI DailyOhlc"
    assert zones["timeframe"] == "D1"
    assert zones["lookback_sessions"] == 60
    assert len(zones["support"]) == 2
    assert len(zones["resistance"]) == 2
    assert zones["support"][0]["upper"] > zones["support"][1]["upper"]
    assert zones["resistance"][0]["lower"] < zones["resistance"][1]["lower"]


def test_short_term_zones_reject_short_or_malformed_daily_history_without_fake_rows():
    short = _daily_history().iloc[:59]
    malformed = _daily_history().astype({"high": "object"})
    malformed.loc[0, "high"] = "bad"

    assert calculate_short_term_zones(short)["reason_code"] == "insufficient_daily_history"
    result = calculate_short_term_zones(malformed)
    assert result["reason_code"] == "insufficient_daily_history"
    assert result["support"] == []
    assert result["resistance"] == []


def test_short_term_zone_history_sorts_deduplicates_and_keeps_the_latest_sixty_valid_sessions():
    history = _daily_history().iloc[::-1].reset_index(drop=True)
    duplicate_latest = history.loc[history["date"] == "2026-03-25"].copy()
    duplicate_latest.loc[:, "high"] = 105.0
    invalid = pd.DataFrame([{"date": "2026-03-26", "high": 90.0, "low": 100.0, "close": 95.0}])

    rows = _normalized_short_term_zone_history(pd.concat([history, duplicate_latest, invalid], ignore_index=True))

    assert len(rows) == 60
    assert [row["date"] for row in rows] == sorted(row["date"] for row in rows)
    assert rows[-1] == {"date": "2026-03-25", "high": 105.0, "low": 99.0, "close": 100.0}


def test_indicator_contract_adds_zones_without_changing_existing_daily_indicator_values():
    history = _daily_history()
    indicators = calculate_vietnam_indicators(history)

    assert indicators["close"] == 100.0
    assert indicators["ma20"] == 100.0
    assert indicators["short_term_zones"]["source"] == "derived from SSI DailyOhlc"
    assert "atr" not in indicators["short_term_zones"]
