from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from data_provider.ssi_fastconnect_fetcher import SsiFastConnectFetcher
from src.services import vietnam_market_service as service_module
from src.services.vietnam_market_service import (
    VietnamMarketService,
    clear_vietnam_cache,
    normalize_completed_intraday_chart_rows,
    vietnam_intraday_session_state,
)


def _raw_row(time_value: str, *, close: float = 71_000, volume: float = 12_300, date_value: str = "24/06/2026"):
    return {
        "TradingDate": date_value,
        "Time": time_value,
        "Open": 71_000,
        "High": max(71_100, close),
        "Low": min(70_900, close),
        "Close": close,
        "Volume": volume,
        "Value": 123,
        "Symbol": "FPT",
    }


class FakeCompletedIntradayFetcher:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get_completed_intraday_1m(self, symbol: str, trading_date: str):
        self.calls.append((symbol, trading_date))
        return self.payload


def test_fetcher_uses_one_fixed_completed_session_request(monkeypatch):
    fetcher = SsiFastConnectFetcher(enabled=True, intraday_enabled=True, consumer_id="x", consumer_secret="y")
    calls = []

    def fake_request(endpoint, params):
        calls.append((endpoint, params))
        return {"data": {"totalRecord": 0, "items": []}}

    monkeypatch.setattr(fetcher, "_request", fake_request)
    result = fetcher.get_completed_intraday_1m("FPT", "2026-06-24")

    assert result["status"] == "ok"
    assert result["rows"] == []
    assert calls == [
        (
            "IntradayOhlc",
            {
                "symbol": "FPT",
                "fromDate": "24/06/2026",
                "toDate": "24/06/2026",
                "pageIndex": 1,
                "pageSize": 1000,
                "ascending": True,
                "resolution": 1,
            },
        )
    ]


def test_normalizer_uses_vietnam_time_keeps_gaps_and_deduplicates_latest_raw_timestamp():
    result = normalize_completed_intraday_chart_rows(
        [
            _raw_row("09:00:10", close=70_950),
            _raw_row("09:02:00", close=71_200),
            _raw_row("09:00:50", close=71_050),
            _raw_row("09:00:50", close=71_075),
        ],
        "2026-06-24",
    )

    expected_time = int(datetime(2026, 6, 24, 9, 0, tzinfo=service_module.VN_TIMEZONE).timestamp())
    assert result["status"] == "ready"
    assert [bar["time"] for bar in result["bars"]] == [expected_time, expected_time + 120]
    assert result["bars"][0]["close"] == 71_075
    assert result["duplicate_minute_buckets"] == 2
    assert result["rejected_rows"] == 0
    assert result["newest_provider_timestamp"] == "2026-06-24T09:02:00+07:00"


def test_normalizer_rejects_bad_and_mismatched_rows_but_keeps_usable_rows():
    invalid_ohlc = _raw_row("09:01:00")
    invalid_ohlc["High"] = 1
    malformed_time = _raw_row("9:02")
    result = normalize_completed_intraday_chart_rows(
        [_raw_row("09:00:00"), invalid_ohlc, malformed_time, _raw_row("09:03:00", date_value="23/06/2026")],
        "2026-06-24",
    )

    assert result["status"] == "ready"
    assert len(result["bars"]) == 1
    assert result["rejected_rows"] == 3


def test_normalizer_fails_wholly_malformed_nonempty_payload_and_accepts_confirmed_empty():
    malformed = normalize_completed_intraday_chart_rows([{"TradingDate": "bad"}], "2026-06-24")
    empty = normalize_completed_intraday_chart_rows([], "2026-06-24")

    assert malformed["status"] == "failed"
    assert malformed["bars"] == []
    assert empty["status"] == "ready"
    assert empty["bars"] == []


def test_service_cache_hit_force_refresh_and_stale_if_error(monkeypatch):
    clear_vietnam_cache()
    clock = [datetime(2026, 6, 25, 2, tzinfo=timezone.utc)]
    monkeypatch.setattr(service_module, "_utc_now", lambda: clock[0])
    fetcher = FakeCompletedIntradayFetcher({"status": "ok", "rows": [_raw_row("09:00:00")]})
    service = VietnamMarketService(ssi_fetcher=fetcher)

    first = service.build_intraday_chart("FPT", interval="1m", trading_date="2026-06-24")
    second = service.build_intraday_chart("FPT", interval="1m", trading_date="2026-06-24")
    assert first["cache"]["status"] == "miss"
    assert second["cache"]["status"] == "hit"
    assert len(fetcher.calls) == 1

    fetcher.payload = {"status": "ok", "rows": [_raw_row("09:00:00", close=71_050)]}
    forced_success = service.build_intraday_chart(
        "FPT", interval="1m", trading_date="2026-06-24", force_refresh=True
    )
    assert forced_success["cache"]["status"] == "refresh"
    assert forced_success["bars"][0]["close"] == 71_050
    assert len(fetcher.calls) == 2

    fetcher.payload = {"status": "unavailable", "failure_class": "timeout", "rows": []}
    refreshed = service.build_intraday_chart(
        "FPT", interval="1m", trading_date="2026-06-24", force_refresh=True
    )
    assert refreshed["status"] == "ready"
    assert refreshed["cache"]["status"] == "stale"
    assert refreshed["cache"]["is_stale"] is True
    assert refreshed["bars"][0]["close"] == 71_050
    assert len(fetcher.calls) == 3

    clock[0] += timedelta(days=8)
    unavailable = service.build_intraday_chart(
        "FPT", interval="1m", trading_date="2026-06-24", force_refresh=True
    )
    assert unavailable["status"] == "unavailable"
    assert unavailable["bars"] == []


def test_service_negative_cache_and_validation_do_not_repeat_or_make_invalid_calls(monkeypatch):
    clear_vietnam_cache()
    monkeypatch.setattr(
        service_module,
        "_utc_now",
        lambda: datetime(2026, 6, 25, 2, tzinfo=timezone.utc),
    )
    fetcher = FakeCompletedIntradayFetcher({"status": "unavailable", "failure_class": "network_error", "rows": []})
    service = VietnamMarketService(ssi_fetcher=fetcher)

    first = service.build_intraday_chart("FPT", interval="1m", trading_date="2026-06-24")
    second = service.build_intraday_chart("FPT", interval="1m", trading_date="2026-06-24")
    assert first["status"] == second["status"] == "unavailable"
    assert second["cache"]["status"] == "hit"
    assert len(fetcher.calls) == 1

    for kwargs in (
        {"ticker": "FPT!", "interval": "1m", "trading_date": "2026-06-24"},
        {"ticker": "FPT", "interval": "5m", "trading_date": "2026-06-24"},
        {"ticker": "FPT", "interval": "1m", "trading_date": "2026/06/24"},
        {"ticker": "FPT", "interval": "1m", "trading_date": "2026-6-24"},
        {"ticker": "FPT", "interval": "1m", "trading_date": "2026-06-26"},
    ):
        try:
            service.build_intraday_chart(**kwargs)
        except ValueError:
            pass
        else:  # pragma: no cover - contract failure guard
            raise AssertionError("Invalid request must fail before provider access")
    assert len(fetcher.calls) == 1


def test_intraday_chart_api_contract_and_validation(monkeypatch, tmp_path):
    class StubService:
        calls = []

        def build_intraday_chart(self, ticker, *, interval, trading_date, force_refresh=False):
            self.calls.append((ticker, interval, trading_date, force_refresh))
            return {
                "ticker": ticker,
                "interval": interval,
                "trading_date": trading_date,
                "timezone": "Asia/Ho_Chi_Minh",
                "status": "ready",
                "bars": [{"time": 1782266400, "open": 1, "high": 2, "low": 1, "close": 2, "volume": 3}],
                "source": {"provider": "ssi_fastconnect", "dataset": "IntradayOhlc"},
                "cache": {"status": "miss", "is_stale": False},
                "diagnostics": {"requested_date": trading_date, "provider_date": "24/06/2026"},
            }

    monkeypatch.setattr("api.v1.endpoints.stocks.VietnamMarketService", StubService)
    client = TestClient(create_app(static_dir=tmp_path / "static"))

    response = client.get("/api/v1/stocks/vn/intraday-chart?ticker=FPT&interval=1m&date=2026-06-24")
    assert response.status_code == 200
    assert response.json()["ticker"] == "FPT"
    assert response.json()["bars"][0]["time"] == 1782266400
    unsupported = client.get("/api/v1/stocks/vn/intraday-chart?ticker=FPT&interval=5m&date=2026-06-24")
    assert unsupported.status_code == 422
    assert unsupported.json() == {
        "error": "vn_intraday_chart_invalid_request",
        "message": "Only interval=1m is supported",
    }
    assert StubService.calls == [("FPT", "1m", "2026-06-24", False)]

    class CurrentDateRejectingService:
        def build_intraday_chart(self, ticker, *, interval, trading_date, force_refresh=False):
            raise ValueError("Intraday history date must not be after the current Vietnam date")

    monkeypatch.setattr("api.v1.endpoints.stocks.VietnamMarketService", CurrentDateRejectingService)
    current_date = client.get("/api/v1/stocks/vn/intraday-chart?ticker=FPT&interval=1m&date=2026-06-25")
    assert current_date.status_code == 422
    assert current_date.json() == {
        "error": "vn_intraday_chart_invalid_request",
        "message": "Intraday history date must not be after the current Vietnam date",
    }


@pytest.mark.parametrize(
    ("utc_value", "expected"),
    [
        (datetime(2026, 6, 25, 1, 0, tzinfo=timezone.utc), "pre_open"),
        (datetime(2026, 6, 25, 2, 16, tzinfo=timezone.utc), "continuous_morning"),
        (datetime(2026, 6, 25, 5, 0, tzinfo=timezone.utc), "lunch"),
        (datetime(2026, 6, 25, 6, 1, tzinfo=timezone.utc), "continuous_afternoon"),
        (datetime(2026, 6, 25, 7, 31, tzinfo=timezone.utc), "atc"),
        (datetime(2026, 6, 25, 7, 46, tzinfo=timezone.utc), "closed"),
        (datetime(2026, 6, 27, 2, 16, tzinfo=timezone.utc), "closed"),
    ],
)
def test_vietnam_intraday_session_state_is_clock_derived(utc_value, expected):
    assert vietnam_intraday_session_state(utc_value) == expected


def test_current_date_metadata_uses_raw_provider_time_and_short_positive_cache(monkeypatch):
    clear_vietnam_cache()
    clock = [datetime(2026, 6, 25, 2, 16, 40, tzinfo=timezone.utc)]
    monkeypatch.setattr(service_module, "_utc_now", lambda: clock[0])
    fetcher = FakeCompletedIntradayFetcher(
        {"status": "ok", "rows": [_raw_row("09:16:29", date_value="25/06/2026")]}
    )
    service = VietnamMarketService(ssi_fetcher=fetcher)

    first = service.build_intraday_chart("FPT", interval="1m", trading_date="2026-06-25")
    assert first["status"] == "ready"
    assert first["session_state"] == "continuous_morning"
    assert first["freshness"] == "updating"
    assert first["current_bar_state"] == "provisional"
    assert first["newest_bar_age_seconds"] == 11
    assert first["bars"][0]["time"] == int(
        datetime(2026, 6, 25, 9, 16, tzinfo=service_module.VN_TIMEZONE).timestamp()
    )
    fetched_at = datetime.fromisoformat(first["cache"]["fetched_at"])
    expires_at = datetime.fromisoformat(first["cache"]["expires_at"])
    assert (expires_at - fetched_at).total_seconds() == 15

    clock[0] += timedelta(seconds=14)
    cached = service.build_intraday_chart("FPT", interval="1m", trading_date="2026-06-25")
    assert cached["cache"]["status"] == "hit"
    assert cached["last_provider_refresh_at"] == first["last_provider_refresh_at"]
    assert len(fetcher.calls) == 1


def test_current_date_previous_bucket_is_inferred_final_and_delayed(monkeypatch):
    clear_vietnam_cache()
    monkeypatch.setattr(
        service_module,
        "_utc_now",
        lambda: datetime(2026, 6, 25, 2, 20, 0, tzinfo=timezone.utc),
    )
    fetcher = FakeCompletedIntradayFetcher(
        {"status": "ok", "rows": [_raw_row("09:16:58", date_value="25/06/2026")]}
    )
    result = VietnamMarketService(ssi_fetcher=fetcher).build_intraday_chart(
        "FPT", interval="1m", trading_date="2026-06-25"
    )
    assert result["current_bar_state"] == "inferred_final"
    assert result["freshness"] == "delayed"


def test_current_empty_and_negative_cache_are_short_and_unavailable(monkeypatch):
    clear_vietnam_cache()
    clock = [datetime(2026, 6, 25, 2, 16, tzinfo=timezone.utc)]
    monkeypatch.setattr(service_module, "_utc_now", lambda: clock[0])
    fetcher = FakeCompletedIntradayFetcher({"status": "ok", "rows": []})
    service = VietnamMarketService(ssi_fetcher=fetcher)

    empty = service.build_intraday_chart("FPT", interval="1m", trading_date="2026-06-25")
    assert empty["status"] == "unavailable"
    assert empty["freshness"] == "unavailable"
    assert empty["current_bar_state"] == "none"
    assert (
        datetime.fromisoformat(empty["cache"]["expires_at"])
        - datetime.fromisoformat(empty["cache"]["fetched_at"])
    ).total_seconds() == 5

    clock[0] += timedelta(seconds=6)
    fetcher.payload = {"status": "unavailable", "failure_class": "network_error", "rows": []}
    negative = service.build_intraday_chart("FPT", interval="1m", trading_date="2026-06-25")
    assert negative["freshness"] == "unavailable"
    assert (
        datetime.fromisoformat(negative["cache"]["expires_at"])
        - datetime.fromisoformat(negative["cache"]["fetched_at"])
    ).total_seconds() == 10

    fetcher.payload = {"status": "unavailable", "code": "NoDataFound", "rows": []}
    no_data = service.build_intraday_chart("HPG", interval="1m", trading_date="2026-06-25")
    assert no_data["diagnostics"]["result"] == "no_data"
    assert (
        datetime.fromisoformat(no_data["cache"]["expires_at"])
        - datetime.fromisoformat(no_data["cache"]["fetched_at"])
    ).total_seconds() == 5


def test_current_force_refresh_recovers_only_bounded_stale_snapshot(monkeypatch):
    clear_vietnam_cache()
    clock = [datetime(2026, 6, 25, 2, 16, tzinfo=timezone.utc)]
    monkeypatch.setattr(service_module, "_utc_now", lambda: clock[0])
    fetcher = FakeCompletedIntradayFetcher(
        {"status": "ok", "rows": [_raw_row("09:16:00", date_value="25/06/2026")]}
    )
    service = VietnamMarketService(ssi_fetcher=fetcher)
    ready = service.build_intraday_chart("FPT", interval="1m", trading_date="2026-06-25")

    fetcher.payload = {"status": "unavailable", "failure_class": "timeout", "rows": []}
    clock[0] += timedelta(seconds=30)
    stale = service.build_intraday_chart(
        "FPT", interval="1m", trading_date="2026-06-25", force_refresh=True
    )
    assert stale["status"] == "ready"
    assert stale["freshness"] == "stale"
    assert stale["cache"]["is_stale"] is True
    assert stale["last_provider_refresh_at"] == ready["last_provider_refresh_at"]

    clock[0] += timedelta(seconds=271)
    unavailable = service.build_intraday_chart(
        "FPT", interval="1m", trading_date="2026-06-25", force_refresh=True
    )
    assert unavailable["status"] == "unavailable"
    assert unavailable["bars"] == []


def test_completed_metadata_and_cache_policy_remain_unchanged(monkeypatch):
    clear_vietnam_cache()
    monkeypatch.setattr(
        service_module,
        "_utc_now",
        lambda: datetime(2026, 6, 25, 2, tzinfo=timezone.utc),
    )
    fetcher = FakeCompletedIntradayFetcher({"status": "ok", "rows": [_raw_row("09:00:00")]})
    result = VietnamMarketService(ssi_fetcher=fetcher).build_intraday_chart(
        "FPT", interval="1m", trading_date="2026-06-24"
    )
    assert result["session_state"] == "completed"
    assert result["freshness"] == "completed"
    assert result["current_bar_state"] == "completed"
    assert result["newest_bar_age_seconds"] is None
    assert (
        datetime.fromisoformat(result["cache"]["expires_at"])
        - datetime.fromisoformat(result["cache"]["fetched_at"])
    ).total_seconds() == 86_400


def test_intraday_cache_is_bounded_lru(monkeypatch):
    clear_vietnam_cache()
    monkeypatch.setattr(service_module, "VN_INTRADAY_CHART_CACHE_MAX_ENTRIES", 2)
    monkeypatch.setattr(
        service_module,
        "_utc_now",
        lambda: datetime(2026, 6, 25, 2, tzinfo=timezone.utc),
    )
    fetcher = FakeCompletedIntradayFetcher({"status": "ok", "rows": []})
    service = VietnamMarketService(ssi_fetcher=fetcher)
    for ticker in ("FPT", "HPG", "SSI"):
        service.build_intraday_chart(ticker, interval="1m", trading_date="2026-06-24")

    assert len(service_module._VN_INTRADAY_CHART_CACHE) == 2
    assert all(key[1] != "FPT" for key in service_module._VN_INTRADAY_CHART_CACHE)
