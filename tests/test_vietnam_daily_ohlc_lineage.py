"""Offline lineage guards for the production SSI V3 daily-OHLC path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.services.vietnam_market_service import (
    VietnamDashboardConfig,
    VietnamMarketService,
    clear_vietnam_cache,
)


ROOT = Path(__file__).resolve().parents[1]


class RecordingDailyProvider:
    """Controlled SSI V3 boundary used without files, credentials, or network."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def get_daily_ohlcv(self, symbol: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"symbol": symbol, **kwargs})
        return self.payload

    def get_daily_stock_price(self, _symbol: str, **_kwargs: Any) -> dict[str, Any]:
        return {"status": "unavailable", "rows": [], "reason": "not part of daily-OHLC lineage"}

    def get_security_basic_info(self, _symbol: str) -> dict[str, Any]:
        return {"status": "unavailable", "rows": [], "reason": "not part of daily-OHLC lineage"}


class MetadataFailureProvider(RecordingDailyProvider):
    """Exercises the outer watchlist guard used when an optional SSI read fails."""

    def get_security_basic_info(self, _symbol: str) -> dict[str, Any]:
        raise RuntimeError("SSI V3 REST disabled")


def _service(provider: RecordingDailyProvider) -> VietnamMarketService:
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


def _provider_rows() -> list[dict[str, Any]]:
    return [
        {
            "date": "2026-07-20",
            "open": 100.25,
            "high": 102.5,
            "low": 99.75,
            "close": 101.0,
            "volume": 1234,
            "value": 124_634.0,
            "source": "ssi_fastconnect_v3",
        },
        {
            "date": "2026-07-21",
            "open": 101.0,
            "high": 103.0,
            "low": 100.5,
            "close": 102.25,
            "volume": 0,
            "value": None,
            "source": "ssi_fastconnect_v3",
        },
    ]


@pytest.fixture(autouse=True)
def _isolated_process_cache() -> None:
    clear_vietnam_cache()
    yield
    clear_vietnam_cache()


def test_daily_chart_uses_injected_ssi_rows_even_when_legacy_fixture_env_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The obsolete Mozyfin fixture switch cannot enter the SSI-only chart path."""
    monkeypatch.setenv("MOZYFIN_FIXTURE_DIR", str(ROOT / "tests" / "fixtures" / "mozyfin"))
    provider = RecordingDailyProvider({"status": "ok", "rows": _provider_rows()})

    chart = _service(provider).build_chart("FPT", "1M")

    assert provider.calls == [{"symbol": "FPT", "from_date": None, "to_date": None, "limit": 260, "force_refresh": False}]
    assert chart["status"] == "ok"
    assert chart["source"] == "SSI"
    assert chart["actual_source"] == "SSI"
    assert chart["fallback_used"] is False
    assert [(row["date"], row["open"], row["high"], row["low"], row["close"], row["volume"]) for row in chart["points"]] == [
        ("2026-07-20", 100.25, 102.5, 99.75, 101.0, 1234.0),
        ("2026-07-21", 101.0, 103.0, 100.5, 102.25, 0.0),
    ]


def test_empty_cache_and_unavailable_provider_returns_no_daily_candles() -> None:
    provider = RecordingDailyProvider(
        {"status": "unavailable", "rows": [], "reason": "SSI V3 provider unavailable"}
    )

    chart = _service(provider).build_chart("FPT")

    assert len(provider.calls) == 1
    assert chart["status"] == "unavailable"
    assert chart["points"] == []
    assert chart["candles"] == []
    assert chart["fallback_used"] is False


def test_empty_cache_and_unavailable_provider_marks_watchlist_row_unavailable() -> None:
    """A no-data daily response cannot be serialized as a successful watchlist row."""
    provider = RecordingDailyProvider(
        {"status": "unavailable", "rows": [], "reason": "SSI V3 provider unavailable"}
    )

    row = _service(provider).build_watchlist(["FPT"], include_intraday=False)["watchlist"][0]

    assert len(provider.calls) == 1
    assert row["status"] == "unavailable"
    assert row["rows_loaded"] == 0
    assert row["ohlcv_close"] is None
    assert row["fallback_used"] is False
    assert row["cache_status"]["ohlcv_cache"] == "error"


def test_outer_watchlist_guard_does_not_default_provider_failure_to_ok() -> None:
    provider = MetadataFailureProvider(
        {"status": "unavailable", "rows": [], "reason": "SSI V3 provider unavailable"}
    )

    row = _service(provider).build_watchlist(["FPT"], include_intraday=False)["watchlist"][0]

    assert row["status"] == "unavailable"
    assert row["reason"]
    assert row["rows_loaded"] == 0
    assert row["fallback_used"] is False


def test_stale_daily_watchlist_data_is_only_reused_after_a_provider_backed_cache_write() -> None:
    provider_backed = RecordingDailyProvider({"status": "ok", "rows": _provider_rows()})
    first_row = _service(provider_backed).build_watchlist(["FPT"], include_intraday=False)["watchlist"][0]
    unavailable = RecordingDailyProvider(
        {"status": "unavailable", "rows": [], "reason": "SSI V3 provider unavailable"}
    )

    stale_row = _service(unavailable).build_watchlist(
        ["FPT"], force_refresh=True, include_intraday=False
    )["watchlist"][0]

    assert first_row["status"] == "ok"
    assert len(provider_backed.calls) == 1
    assert len(unavailable.calls) == 1
    assert stale_row["cache_status"]["ohlcv_cache"] == "stale"
    assert stale_row["ohlcv_close"] == first_row["ohlcv_close"]
    assert stale_row["source"] == "SSI"
    assert stale_row["fallback_used"] is False


def test_force_refresh_calls_ssi_and_keeps_an_older_provider_backed_cache_on_failure() -> None:
    provider_backed = RecordingDailyProvider({"status": "ok", "rows": _provider_rows()})
    service = _service(provider_backed)
    service.build_watchlist(["FPT"], force_refresh=True, include_intraday=False)
    unavailable = RecordingDailyProvider(
        {"status": "unavailable", "rows": [], "reason": "SSI V3 provider unavailable"}
    )
    retry_service = _service(unavailable)

    payload = retry_service.build_watchlist(["FPT"], force_refresh=True, include_intraday=False)
    row = payload["watchlist"][0]

    assert len(provider_backed.calls) == 1
    assert len(unavailable.calls) == 1
    assert row["cache_status"]["ohlcv_cache"] == "stale"
    assert row["latest_price_source"] == "SSI DailyOhlc"
    assert row["fallback_used"] is False


def test_daily_ohlc_runtime_modules_do_not_reference_test_fixture_paths() -> None:
    runtime_files = [
        ROOT / "api" / "v1" / "endpoints" / "stocks.py",
        ROOT / "data_provider" / "ssi_provider_router.py",
        ROOT / "data_provider" / "ssi_v3_adapter.py",
        ROOT / "src" / "services" / "vietnam_market_service.py",
    ]
    forbidden = ("tests/fixtures", "tests\\fixtures", "MOZYFIN_FIXTURE_DIR")

    for path in runtime_files:
        text = path.read_text(encoding="utf-8")
        assert not any(marker in text for marker in forbidden), path
