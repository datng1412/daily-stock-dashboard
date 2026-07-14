from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from api.app import create_app
from data_provider.ssi_fastconnect_fetcher import SsiFastConnectFetcher
from src.services import vietnam_market_service as service_module
from src.services.vietnam_market_service import (
    VietnamMarketService,
    clear_vietnam_cache,
    normalize_completed_intraday_chart_rows,
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
        {"ticker": "FPT", "interval": "1m", "trading_date": "2026-06-25"},
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
            raise ValueError("Intraday history date must be before the current Vietnam date")

    monkeypatch.setattr("api.v1.endpoints.stocks.VietnamMarketService", CurrentDateRejectingService)
    current_date = client.get("/api/v1/stocks/vn/intraday-chart?ticker=FPT&interval=1m&date=2026-06-25")
    assert current_date.status_code == 422
    assert current_date.json() == {
        "error": "vn_intraday_chart_invalid_request",
        "message": "Intraday history date must be before the current Vietnam date",
    }


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
