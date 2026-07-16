from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event, Lock
import time

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from src.services import vietnam_market_service as service_module
from src.services.vietnam_intraday_observability import (
    observe_intraday_provider_fetch,
    reset_vietnam_intraday_observability,
)
from src.services.vietnam_market_service import (
    VietnamMarketService,
    clear_vietnam_cache,
    vietnam_intraday_chart_health_snapshot,
)


def _row(
    symbol: str = "FPT",
    *,
    date_value: str = "16/07/2026",
    time_value: str = "09:16:45",
    close: float = 71_050,
    volume: float = 12_300,
):
    return {
        "TradingDate": date_value,
        "Time": time_value,
        "Open": 71_000,
        "High": max(71_100, close),
        "Low": 70_900,
        "Close": close,
        "Volume": volume,
        "Symbol": symbol,
    }


class StaticFetcher:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get_completed_intraday_1m(self, symbol: str, trading_date: str):
        self.calls.append((symbol, trading_date))
        return self.payload


class BlockingFetcher:
    def __init__(self, payload, *, fail: bool = False):
        self.payload = payload
        self.fail = fail
        self.calls = []
        self.entered = Event()
        self.release = Event()
        self._lock = Lock()

    def get_completed_intraday_1m(self, symbol: str, trading_date: str):
        with self._lock:
            self.calls.append((symbol, trading_date))
        self.entered.set()
        assert self.release.wait(timeout=5)
        if self.fail:
            raise RuntimeError("provider payload must not enter health output")
        return self.payload


@pytest.fixture(autouse=True)
def _reset_intraday_state():
    clear_vietnam_cache()
    reset_vietnam_intraday_observability()
    yield
    clear_vietnam_cache()
    reset_vietnam_intraday_observability()


def _wait_for_coalesced(expected: int) -> None:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if vietnam_intraday_chart_health_snapshot()["requests"]["coalesced"] >= expected:
            return
        time.sleep(0.01)
    raise AssertionError(f"Expected {expected} coalesced requests")


def test_health_is_read_only_unknown_process_local_and_secret_free(monkeypatch, tmp_path):
    class ForbiddenService:
        def __init__(self):  # pragma: no cover - failure guard
            raise AssertionError("health must not construct the market service")

    monkeypatch.setattr("api.v1.endpoints.stocks.VietnamMarketService", ForbiddenService)
    client = TestClient(create_app(static_dir=tmp_path / "static"))
    response = client.get("/api/v1/stocks/vn/intraday-chart/health")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["status"] == "unknown"
    assert payload["process_scope"] == {"metrics_scope": "process_local", "resets_on_restart": True}
    assert datetime.fromisoformat(payload["current_vietnam_time"]).utcoffset().total_seconds() == 7 * 3600
    assert payload["provider"]["calls"] == 0
    assert payload["last_provider_result"] is None
    serialized = str(payload).lower()
    for forbidden in ("authorization", "bearer", "access_token", "consumer_secret", "cookie", "bars"):
        assert forbidden not in serialized


def test_health_routes_are_distinct_and_health_has_no_metrics_or_cache_side_effect(monkeypatch, tmp_path):
    fixed_now = datetime(2026, 7, 16, 2, 17, 5, tzinfo=timezone.utc)
    monkeypatch.setattr(service_module, "_utc_now", lambda: fixed_now)
    app = create_app(static_dir=tmp_path / "static")
    paths = app.openapi()["paths"]
    canonical = "/api/v1/stocks/vn/intraday-chart/health"
    broader = "/api/v1/stocks/vn/observability"

    assert paths[canonical]["get"]["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/VietnamIntradayChartHealthResponse"
    }
    assert paths[broader]["get"]["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/VietnamObservabilityResponse"
    }

    before_health = vietnam_intraday_chart_health_snapshot()
    before_cache = list(service_module._VN_INTRADAY_CHART_CACHE.items())
    response = TestClient(app).get(canonical)
    after_health = vietnam_intraday_chart_health_snapshot()

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert after_health == before_health
    assert list(service_module._VN_INTRADAY_CHART_CACHE.items()) == before_cache
    assert after_health["requests"]["total"] == 0
    assert after_health["provider"]["calls"] == 0
    assert after_health["cache_activity"] == {
        "hits": 0,
        "misses": 0,
        "refreshes": 0,
        "empty_hits": 0,
        "negative_hits": 0,
        "stale_recoveries": 0,
        "stale_recovery_rejected_too_old": 0,
    }


def test_health_tracks_success_cache_hit_force_refresh_and_distinct_age(monkeypatch):
    clock = [datetime(2026, 7, 16, 2, 17, 0, tzinfo=timezone.utc)]
    monkeypatch.setattr(service_module, "_utc_now", lambda: clock[0])
    fetcher = StaticFetcher({"status": "ok", "rows": [_row()]})
    service = VietnamMarketService(ssi_fetcher=fetcher)

    first = service.build_intraday_chart("FPT", interval="1m", trading_date="2026-07-16")
    clock[0] = datetime(2026, 7, 16, 2, 17, 10, tzinfo=timezone.utc)
    cached = service.build_intraday_chart("FPT", interval="1m", trading_date="2026-07-16")
    refreshed = service.build_intraday_chart(
        "FPT", interval="1m", trading_date="2026-07-16", force_refresh=True
    )
    health = vietnam_intraday_chart_health_snapshot()

    assert first["newest_bar_age_seconds"] == 15
    assert first["provider_snapshot_age_seconds"] == 0
    assert cached["provider_snapshot_age_seconds"] == 10
    assert cached["last_provider_refresh_at"] == first["last_provider_refresh_at"]
    assert refreshed["provider_snapshot_age_seconds"] == 0
    assert len(fetcher.calls) == 2
    assert health["status"] == "ok"
    assert health["requests"] == {
        "total": 3,
        "current_date": 3,
        "completed_date": 0,
        "force_refresh": 1,
        "coalesced": 0,
    }
    assert health["provider"]["calls"] == 2
    assert health["cache_activity"]["hits"] == 1
    assert health["cache_activity"]["misses"] == 1
    assert health["cache_activity"]["refreshes"] == 1


def test_newest_bar_age_uses_accepted_raw_time_while_candle_stays_at_minute_start(monkeypatch):
    clock = [datetime(2026, 7, 16, 2, 17, 5, tzinfo=timezone.utc)]
    monkeypatch.setenv("TZ", "America/New_York")
    monkeypatch.setattr(service_module, "_utc_now", lambda: clock[0])
    fetcher = StaticFetcher({"status": "ok", "rows": [_row(time_value="09:16:55")]})
    service = VietnamMarketService(ssi_fetcher=fetcher)

    first = service.build_intraday_chart("FPT", interval="1m", trading_date="2026-07-16")
    expected_bucket = int(
        datetime(2026, 7, 16, 9, 16, tzinfo=service_module.VN_TIMEZONE).timestamp()
    )
    health = vietnam_intraday_chart_health_snapshot()

    assert first["bars"][0]["time"] == expected_bucket
    assert first["newest_bar_age_seconds"] == 10
    assert first["newest_bar_age_seconds"] != 65
    assert first["current_bar_state"] == "inferred_final"
    assert first["freshness"] == "updating"
    assert health["last_provider_result"]["newest_bar_age_seconds"] == 10

    clock[0] += timedelta(seconds=5)
    cached = service.build_intraday_chart("FPT", interval="1m", trading_date="2026-07-16")
    assert cached["newest_bar_age_seconds"] == 15
    assert cached["provider_snapshot_age_seconds"] == 5
    assert cached["last_provider_refresh_at"] == first["last_provider_refresh_at"]
    assert len(fetcher.calls) == 1


def test_duplicate_minute_winner_owns_raw_age_and_observability_value(monkeypatch):
    monkeypatch.setattr(
        service_module,
        "_utc_now",
        lambda: datetime(2026, 7, 16, 2, 17, 5, tzinfo=timezone.utc),
    )
    fetcher = StaticFetcher(
        {
            "status": "ok",
            "rows": [
                _row(time_value="09:16:05", close=71_025, volume=10_000),
                _row(time_value="09:16:55", close=71_075, volume=12_500),
            ],
        }
    )
    result = VietnamMarketService(ssi_fetcher=fetcher).build_intraday_chart(
        "FPT", interval="1m", trading_date="2026-07-16"
    )
    health = vietnam_intraday_chart_health_snapshot()

    assert len(result["bars"]) == 1
    assert result["bars"][0]["time"] == int(
        datetime(2026, 7, 16, 9, 16, tzinfo=service_module.VN_TIMEZONE).timestamp()
    )
    assert result["bars"][0]["close"] == 71_075
    assert result["bars"][0]["volume"] == 12_500
    assert result["diagnostics"]["duplicate_minute_buckets"] == 1
    assert result["newest_bar_age_seconds"] == 10
    assert health["last_provider_result"]["newest_bar_age_seconds"] == result["newest_bar_age_seconds"]
    assert "_newest_provider_timestamp" not in str(health)


@pytest.mark.parametrize("raw_time", ["09:17:05", "09:17:06"])
def test_newest_bar_age_clamps_now_and_future_clock_skew_to_zero(monkeypatch, raw_time):
    monkeypatch.setattr(
        service_module,
        "_utc_now",
        lambda: datetime(2026, 7, 16, 2, 17, 5, tzinfo=timezone.utc),
    )
    result = VietnamMarketService(
        ssi_fetcher=StaticFetcher({"status": "ok", "rows": [_row(time_value=raw_time)]})
    ).build_intraday_chart("FPT", interval="1m", trading_date="2026-07-16")

    assert result["newest_bar_age_seconds"] == 0


def test_pre_open_no_data_is_expected_but_provider_failure_is_degraded(monkeypatch):
    clock = [datetime(2026, 7, 16, 2, 10, 0, tzinfo=timezone.utc)]
    monkeypatch.setattr(service_module, "_utc_now", lambda: clock[0])
    no_data = StaticFetcher({"status": "unavailable", "code": "NoDataFound", "rows": []})
    no_data_result = VietnamMarketService(ssi_fetcher=no_data).build_intraday_chart(
        "FPT", interval="1m", trading_date="2026-07-16"
    )
    assert no_data_result["last_provider_refresh_at"] is None
    assert no_data_result["provider_snapshot_age_seconds"] is None
    assert no_data_result["newest_bar_age_seconds"] is None
    assert vietnam_intraday_chart_health_snapshot()["status"] == "ok"

    clear_vietnam_cache()
    reset_vietnam_intraday_observability()
    unavailable = StaticFetcher(
        {"status": "unavailable", "failure_class": "network_error: secret detail", "rows": []}
    )
    unavailable_result = VietnamMarketService(ssi_fetcher=unavailable).build_intraday_chart(
        "FPT", interval="1m", trading_date="2026-07-16"
    )
    assert unavailable_result["last_provider_refresh_at"] is None
    assert unavailable_result["provider_snapshot_age_seconds"] is None
    health = vietnam_intraday_chart_health_snapshot()
    assert health["status"] == "degraded"
    assert health["last_provider_result"]["failure_class"] == "network_error_secret_detail"
    assert "secret detail" not in str(health)


@pytest.mark.parametrize("request_count", [2, 5])
def test_same_key_concurrent_misses_share_one_provider_call(monkeypatch, request_count):
    monkeypatch.setattr(
        service_module,
        "_utc_now",
        lambda: datetime(2026, 7, 16, 2, 17, 0, tzinfo=timezone.utc),
    )
    fetcher = BlockingFetcher({"status": "ok", "rows": [_row()]})
    service = VietnamMarketService(ssi_fetcher=fetcher)

    with ThreadPoolExecutor(max_workers=request_count) as executor:
        futures = [
            executor.submit(
                service.build_intraday_chart,
                "FPT",
                interval="1m",
                trading_date="2026-07-16",
            )
            for _ in range(request_count)
        ]
        assert fetcher.entered.wait(timeout=2)
        _wait_for_coalesced(request_count - 1)
        in_flight_health = vietnam_intraday_chart_health_snapshot()
        assert in_flight_health["cache"]["in_flight_fetches"] == 1
        fetcher.release.set()
        results = [future.result(timeout=3) for future in futures]

    assert len(fetcher.calls) == 1
    assert all(result["bars"] == results[0]["bars"] for result in results)
    health = vietnam_intraday_chart_health_snapshot()
    assert health["requests"]["total"] == request_count
    assert health["requests"]["coalesced"] == request_count - 1
    assert health["provider"]["calls"] == 1
    assert health["cache"]["in_flight_fetches"] == 0


def test_force_refresh_and_normal_request_coalesce(monkeypatch):
    monkeypatch.setattr(
        service_module,
        "_utc_now",
        lambda: datetime(2026, 7, 16, 2, 17, 0, tzinfo=timezone.utc),
    )
    initial = StaticFetcher({"status": "ok", "rows": [_row()]})
    service = VietnamMarketService(ssi_fetcher=initial)
    service.build_intraday_chart("FPT", interval="1m", trading_date="2026-07-16")

    blocking = BlockingFetcher({"status": "ok", "rows": [_row(time_value="09:17:02")]})
    service._ssi_fetcher = blocking
    with ThreadPoolExecutor(max_workers=2) as executor:
        forced = executor.submit(
            service.build_intraday_chart,
            "FPT",
            interval="1m",
            trading_date="2026-07-16",
            force_refresh=True,
        )
        assert blocking.entered.wait(timeout=2)
        scheduled = executor.submit(
            service.build_intraday_chart,
            "FPT",
            interval="1m",
            trading_date="2026-07-16",
        )
        _wait_for_coalesced(1)
        blocking.release.set()
        forced_result = forced.result(timeout=3)
        scheduled_result = scheduled.result(timeout=3)

    assert len(blocking.calls) == 1
    assert forced_result["bars"] == scheduled_result["bars"]
    assert vietnam_intraday_chart_health_snapshot()["requests"]["coalesced"] == 1


def test_different_keys_fetch_independently_and_failures_cleanup(monkeypatch):
    monkeypatch.setattr(
        service_module,
        "_utc_now",
        lambda: datetime(2026, 7, 16, 2, 17, 0, tzinfo=timezone.utc),
    )
    fetcher = BlockingFetcher({"status": "ok", "rows": [_row()]})
    service = VietnamMarketService(ssi_fetcher=fetcher)
    with ThreadPoolExecutor(max_workers=2) as executor:
        fpt = executor.submit(service.build_intraday_chart, "FPT", interval="1m", trading_date="2026-07-16")
        hpg = executor.submit(service.build_intraday_chart, "HPG", interval="1m", trading_date="2026-07-16")
        deadline = time.monotonic() + 2
        while len(fetcher.calls) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert {call[0] for call in fetcher.calls} == {"FPT", "HPG"}
        assert vietnam_intraday_chart_health_snapshot()["cache"]["in_flight_fetches"] == 2
        fetcher.release.set()
        assert fpt.result(timeout=3)["ticker"] == "FPT"
        assert hpg.result(timeout=3)["ticker"] == "HPG"

    clear_vietnam_cache()
    reset_vietnam_intraday_observability()
    failing = BlockingFetcher({}, fail=True)
    failing_service = VietnamMarketService(ssi_fetcher=failing)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            failing_service.build_intraday_chart, "FPT", interval="1m", trading_date="2026-07-16"
        )
        assert failing.entered.wait(timeout=2)
        second = executor.submit(
            failing_service.build_intraday_chart, "FPT", interval="1m", trading_date="2026-07-16"
        )
        _wait_for_coalesced(1)
        failing.release.set()
        with pytest.raises(RuntimeError):
            first.result(timeout=3)
        with pytest.raises(RuntimeError):
            second.result(timeout=3)
    assert len(failing.calls) == 1
    assert vietnam_intraday_chart_health_snapshot()["cache"]["in_flight_fetches"] == 0


def test_latency_metrics_are_scalar_bounded_and_resettable():
    for latency in (423, 1_116, 615):
        observe_intraday_provider_fetch(
            outcome="success",
            date_kind="completed",
            trading_date="2026-06-24",
            session_state="completed",
            latency_ms=latency,
            returned_rows=226,
            usable_bars=226,
            rejected_rows=0,
            duplicate_minutes=0,
            newest_bar_age_seconds=None,
            freshness="completed",
            stale_recovery=False,
            at="2026-07-16T09:00:00+07:00",
        )
    health = vietnam_intraday_chart_health_snapshot()
    assert health["provider"]["latency_ms"] == {
        "count": 3,
        "min": 423,
        "max": 1_116,
        "average": 718.0,
        "last": 615,
    }
    assert isinstance(health["last_provider_result"], dict)
    assert all(not isinstance(value, list) for value in health.values())

    reset_vietnam_intraday_observability()
    assert vietnam_intraday_chart_health_snapshot()["status"] == "unknown"


def test_lunch_newest_bar_age_does_not_create_stale_classification(monkeypatch):
    monkeypatch.setattr(
        service_module,
        "_utc_now",
        lambda: datetime(2026, 7, 16, 5, 15, 0, tzinfo=timezone.utc),
    )
    fetcher = StaticFetcher(
        {"status": "ok", "rows": [_row(time_value="11:29:58")]}
    )
    result = VietnamMarketService(ssi_fetcher=fetcher).build_intraday_chart(
        "FPT", interval="1m", trading_date="2026-07-16"
    )

    assert result["session_state"] == "lunch"
    assert result["newest_bar_age_seconds"] > 90
    assert result["provider_snapshot_age_seconds"] == 0
    assert result["freshness"] == "delayed"


def test_vietnam_date_rollover_uses_a_new_provider_key_and_never_recovers_old_today(monkeypatch):
    clock = [datetime(2026, 7, 16, 16, 59, 59, tzinfo=timezone.utc)]
    monkeypatch.setattr(service_module, "_utc_now", lambda: clock[0])
    fetcher = StaticFetcher(
        {"status": "ok", "rows": [_row(time_value="14:45:00")]}
    )
    service = VietnamMarketService(ssi_fetcher=fetcher)
    old_today = service.build_intraday_chart("FPT", interval="1m", trading_date="2026-07-16")
    assert old_today["bars"]

    clock[0] = datetime(2026, 7, 16, 17, 0, 0, tzinfo=timezone.utc)
    fetcher.payload = {"status": "unavailable", "code": "NoDataFound", "rows": []}
    new_today = service.build_intraday_chart("FPT", interval="1m", trading_date="2026-07-17")

    assert new_today["bars"] == []
    assert new_today["cache"]["is_stale"] is False
    assert len(fetcher.calls) == 2
    keys = list(service_module._VN_INTRADAY_CHART_CACHE)
    assert {key[5] for key in keys} == {"2026-07-16", "2026-07-17"}
    assert all(key[1:3] == ("ssi_fastconnect", "IntradayOhlc") for key in keys)
    assert all(key[-2:] == ("page_size", 1000) for key in keys)


def test_structured_provider_log_is_one_per_actual_fetch_and_sanitized(monkeypatch, caplog):
    monkeypatch.setattr(
        service_module,
        "_utc_now",
        lambda: datetime(2026, 7, 16, 2, 17, 0, tzinfo=timezone.utc),
    )
    caplog.set_level("INFO", logger="src.services.vietnam_market_service")
    fetcher = StaticFetcher({"status": "ok", "rows": [_row()]})
    service = VietnamMarketService(ssi_fetcher=fetcher)
    service.build_intraday_chart("FPT", interval="1m", trading_date="2026-07-16")
    service.build_intraday_chart("FPT", interval="1m", trading_date="2026-07-16")

    records = [record for record in caplog.records if record.getMessage() == "vn_intraday_provider_fetch"]
    assert len(records) == 1
    event = records[0].vn_intraday
    assert event["ticker"] == "FPT"
    assert event["trading_date"] == "2026-07-16"
    assert event["cache_action"] == "miss"
    assert event["result"] == "success"
    assert event["usable_bar_count"] == 1
    assert "rows" not in event
    assert not any(secret in str(event).lower() for secret in ("authorization", "bearer", "consumer_secret", "cookie"))


def test_empty_and_negative_cache_hits_are_distinguished(monkeypatch):
    monkeypatch.setattr(
        service_module,
        "_utc_now",
        lambda: datetime(2026, 7, 16, 2, 10, 0, tzinfo=timezone.utc),
    )
    empty_fetcher = StaticFetcher({"status": "unavailable", "code": "NoDataFound", "rows": []})
    service = VietnamMarketService(ssi_fetcher=empty_fetcher)
    service.build_intraday_chart("FPT", interval="1m", trading_date="2026-07-16")
    service.build_intraday_chart("FPT", interval="1m", trading_date="2026-07-16")

    unavailable_fetcher = StaticFetcher({"status": "unavailable", "failure_class": "timeout", "rows": []})
    service._ssi_fetcher = unavailable_fetcher
    service.build_intraday_chart("HPG", interval="1m", trading_date="2026-07-16")
    service.build_intraday_chart("HPG", interval="1m", trading_date="2026-07-16")
    cache_activity = vietnam_intraday_chart_health_snapshot()["cache_activity"]
    assert cache_activity["empty_hits"] == 1
    assert cache_activity["negative_hits"] == 1
