# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import FastAPI

from data_provider.ssi_streaming_realtime import (
    SSI_STREAMING_REALTIME_BOOTSTRAP_EMPTY_REASON,
    SSI_STREAMING_REALTIME_DISABLED_REASON,
)
from src.services.ssi_streaming_realtime_lifecycle import (
    bootstrap_ssi_streaming_realtime,
    get_existing_ssi_streaming_realtime_manager,
    is_ssi_streaming_realtime_monitor_running,
    parse_bootstrap_symbols,
    reset_ssi_streaming_realtime_lifecycle_for_tests,
    run_ssi_streaming_realtime_monitor_tick,
    shutdown_ssi_streaming_realtime,
)
from src.services.vietnam_market_service import (
    VietnamDashboardConfig,
    VietnamMarketService,
    clear_vietnam_cache,
)


SECRET_TOKEN = "SECRET_BOOTSTRAP_TOKEN"


class FakeStreamClient:
    def __init__(self, *, fail_start: bool = False):
        self.fail_start = fail_start
        self.channels = []
        self.started = False
        self.stop_calls = 0
        self.on_message = None
        self.on_error = None

    def start(self, on_message, on_error, channels):
        if self.fail_start:
            raise RuntimeError(f"Authorization: Bearer {SECRET_TOKEN}; consumerSecret={SECRET_TOKEN}")
        self.started = True
        self.on_message = on_message
        self.on_error = on_error
        self.channels = list(channels)

    def stop(self):
        self.stop_calls += 1


def _config(**overrides):
    values = {
        "ssi_fastconnect_enabled": True,
        "ssi_fastconnect_base_url": "https://fc-data.ssi.com.vn/api/v2/Market",
        "ssi_fastconnect_consumer_id": "test-consumer",
        "ssi_fastconnect_consumer_secret": "test-secret",
        "ssi_fastconnect_timeout_seconds": 1,
        "ssi_fastconnect_cache_ttl_seconds": 0,
        "ssi_fastconnect_token_ttl_seconds": 900,
        "ssi_fastconnect_realtime_enabled": True,
        "ssi_streaming_realtime_enabled": True,
        "ssi_streaming_realtime_cache_ttl_seconds": 15,
        "ssi_streaming_realtime_channel_template": "X:{symbol}",
        "ssi_streaming_realtime_stream_url": "https://fc-datahub.ssi.com.vn/",
        "ssi_streaming_realtime_bootstrap_symbols": "FPT",
        "ssi_streaming_realtime_idle_timeout_seconds": 45,
        "ssi_streaming_realtime_reconnect_enabled": True,
        "ssi_streaming_realtime_reconnect_initial_delay_seconds": 2,
        "ssi_streaming_realtime_reconnect_max_delay_seconds": 30,
        "ssi_streaming_realtime_reconnect_max_attempts": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _x_trade(symbol: str = "FPT", price: str = "130.5"):
    return {
        "DataType": "X-TRADE",
        "Content": {
            "RType": "X-TRADE",
            "TradingDate": "25/06/2026",
            "Time": "10:01:02",
            "Symbol": symbol,
            "LastPrice": price,
            "LastVol": "1000",
            "TotalVol": "123456",
        },
    }


def _dashboard_config(*, streaming_enabled: bool = True) -> VietnamDashboardConfig:
    return VietnamDashboardConfig(
        daily_data_provider="ssi",
        chart_data_provider="ssi",
        daily_stock_price_provider="ssi",
        index_data_provider="ssi",
        intraday_data_provider="ssi",
        realtime_data_provider="ssi",
        trade_tape_provider="ssi",
        ssi_realtime_enabled=True,
        ssi_streaming_realtime_enabled=streaming_enabled,
        ssi_trade_tape_enabled=True,
        kbs_enabled=False,
        allow_legacy_kbs_provider=False,
        news_provider="disabled",
        mozyfin_enabled=False,
        mozyfin_news_enabled=False,
    )


def setup_function():
    clear_vietnam_cache()
    reset_ssi_streaming_realtime_lifecycle_for_tests()


def teardown_function():
    clear_vietnam_cache()
    reset_ssi_streaming_realtime_lifecycle_for_tests()


def test_disabled_bootstrap_does_not_create_manager_or_client():
    def fail_factory():  # pragma: no cover - should not be called
        raise AssertionError("client factory must not run when streaming is disabled")

    status = bootstrap_ssi_streaming_realtime(
        config=_config(ssi_streaming_realtime_enabled=False),
        client_factory=fail_factory,
    )

    assert status["bootstrap_status"] == "disabled"
    assert status["reason"] == SSI_STREAMING_REALTIME_DISABLED_REASON
    assert get_existing_ssi_streaming_realtime_manager() is None
    assert is_ssi_streaming_realtime_monitor_running() is False


def test_enabled_empty_symbols_does_not_start_client_and_explains_cache_read():
    def fail_factory():  # pragma: no cover - should not be called
        raise AssertionError("client factory must not run without bootstrap symbols")

    status = bootstrap_ssi_streaming_realtime(
        config=_config(ssi_streaming_realtime_bootstrap_symbols=""),
        client_factory=fail_factory,
    )
    manager = get_existing_ssi_streaming_realtime_manager()

    assert manager is not None
    assert status["bootstrap_status"] == "symbols_empty"
    payload = manager.snapshot(["FPT"])
    assert payload["status"] == "unavailable"
    assert payload["reason"] == SSI_STREAMING_REALTIME_BOOTSTRAP_EMPTY_REASON
    assert payload["streaming_status"] == "bootstrap_symbols_empty"
    assert is_ssi_streaming_realtime_monitor_running() is False


def test_bootstrap_rejects_unsafe_symbols_and_starts_no_space_channels():
    client = FakeStreamClient()

    status = bootstrap_ssi_streaming_realtime(
        config=_config(ssi_streaming_realtime_bootstrap_symbols="ALL,*,FPT,$BAD,HPG"),
        client_factory=lambda: client,
    )

    assert status["manager_state"] == "running"
    assert client.started is True
    assert client.channels == [
        "X:FPT",
        "X-QUOTE:FPT",
        "R:FPT",
        "X-TRADE:FPT",
        "F:FPT",
        "X:HPG",
        "X-QUOTE:HPG",
        "R:HPG",
        "X-TRADE:HPG",
        "F:HPG",
        "MI:VNINDEX",
        "MI:VN30",
        "MI:HNX",
        "MI:UPCOM",
    ]
    assert "ALL" in status["bootstrap_rejected_symbols"]
    assert "$BAD" in status["bootstrap_rejected_symbols"]
    assert "*" in status["bootstrap_rejected_symbols"]
    assert is_ssi_streaming_realtime_monitor_running() is True


def test_bootstrap_respects_explicit_old_space_channel_override():
    client = FakeStreamClient()

    bootstrap_ssi_streaming_realtime(
        config=_config(ssi_streaming_realtime_channel_template="X: {symbol}"),
        client_factory=lambda: client,
    )

    assert client.channels == [
        "X: FPT",
        "X-QUOTE:FPT",
        "R:FPT",
        "X-TRADE:FPT",
        "F:FPT",
        "MI:VNINDEX",
        "MI:VN30",
        "MI:HNX",
        "MI:UPCOM",
    ]


def test_service_reads_backend_lifecycle_cache_without_dynamic_subscription():
    client = FakeStreamClient()
    bootstrap_ssi_streaming_realtime(config=_config(), client_factory=lambda: client)
    assert client.channels == [
        "X:FPT",
        "X-QUOTE:FPT",
        "R:FPT",
        "X-TRADE:FPT",
        "F:FPT",
        "MI:VNINDEX",
        "MI:VN30",
        "MI:HNX",
        "MI:UPCOM",
    ]

    client.on_message(_x_trade(price="131.5"))
    service = VietnamMarketService(config=_dashboard_config())
    payload = service.build_realtime_snapshot(["FPT"])

    assert payload["status"] == "ok"
    assert payload["quotes"][0]["price"] == 131.5
    assert payload["quotes"][0]["age_seconds"] == 0
    assert payload["quotes"][0]["cache_ttl_seconds"] == 15
    assert payload["cache"]["response_cache_status"] == "bypassed"
    assert payload["cache"]["streaming_cache_status"] == "hit"
    assert payload["streaming_status"] == "cache_hit"
    assert payload["runtime_status"] == "running"
    assert client.channels == [
        "X:FPT",
        "X-QUOTE:FPT",
        "R:FPT",
        "X-TRADE:FPT",
        "F:FPT",
        "MI:VNINDEX",
        "MI:VN30",
        "MI:HNX",
        "MI:UPCOM",
    ]

    client.on_message(_x_trade(price="132.5"))
    refreshed_payload = service.build_realtime_snapshot(["FPT"])
    assert refreshed_payload["quotes"][0]["price"] == 132.5
    assert refreshed_payload["cache"]["response_cache_status"] == "bypassed"

    outside_payload = service.build_realtime_snapshot(["HPG"])
    assert outside_payload["status"] == "unavailable"
    assert outside_payload["quotes"] == []
    assert client.channels == [
        "X:FPT",
        "X-QUOTE:FPT",
        "R:FPT",
        "X-TRADE:FPT",
        "F:FPT",
        "MI:VNINDEX",
        "MI:VN30",
        "MI:HNX",
        "MI:UPCOM",
    ]


def test_service_config_off_still_wins_over_backend_cache():
    client = FakeStreamClient()
    bootstrap_ssi_streaming_realtime(config=_config(), client_factory=lambda: client)
    client.on_message(_x_trade(price="131.5"))

    service = VietnamMarketService(config=_dashboard_config(streaming_enabled=False))
    payload = service.build_realtime_snapshot(["FPT"], force_refresh=True)

    assert payload["status"] == "unavailable"
    assert payload["error"] == "SSI realtime manager disabled."
    assert payload["quotes"] == []


def test_start_error_is_sanitized_and_nonfatal():
    status = bootstrap_ssi_streaming_realtime(
        config=_config(),
        client_factory=lambda: FakeStreamClient(fail_start=True),
        start_monitor=False,
    )

    assert status["manager_state"] == "errored"
    assert SECRET_TOKEN not in str(status.get("latest_error"))
    assert "<redacted>" in str(status.get("latest_error"))


def test_lifecycle_monitor_tick_schedules_reconnect_after_start_error():
    status = bootstrap_ssi_streaming_realtime(
        config=_config(),
        client_factory=lambda: FakeStreamClient(fail_start=True),
        start_monitor=False,
    )

    tick = run_ssi_streaming_realtime_monitor_tick()

    assert status["manager_state"] == "errored"
    assert tick["runtime_status"] == "reconnecting"
    assert tick["last_reconnect_reason"] == "start_error"
    assert tick["reconnect_attempt_count"] == 0


def test_shutdown_is_idempotent_for_lifecycle_started_manager():
    client = FakeStreamClient()
    bootstrap_ssi_streaming_realtime(config=_config(), client_factory=lambda: client)

    first = shutdown_ssi_streaming_realtime()
    second = shutdown_ssi_streaming_realtime()

    assert first["manager_state"] == "stopped"
    assert first["runtime_status"] == "shutdown"
    assert second["bootstrap_status"] == "not_started"
    assert client.stop_calls == 1
    assert is_ssi_streaming_realtime_monitor_running() is False


def test_shutdown_prevents_monitor_tick_from_reviving_manager():
    client = FakeStreamClient()
    bootstrap_ssi_streaming_realtime(config=_config(), client_factory=lambda: client)

    shutdown_ssi_streaming_realtime()
    tick = run_ssi_streaming_realtime_monitor_tick()

    assert tick["runtime_status"] == "shutdown"
    assert client.stop_calls == 1


def test_parse_bootstrap_symbols_dedupes_and_rejects_all_or_wildcards():
    accepted, rejected = parse_bootstrap_symbols("fpt,FPT,ALL,*,HPG, bad space ")

    assert accepted == ["FPT", "HPG"]
    assert rejected == ["ALL", "*", "BAD SPACE"]


def test_fastapi_lifespan_calls_streaming_bootstrap_and_shutdown(monkeypatch):
    import api.app as app_module

    calls = []

    monkeypatch.setattr(app_module, "_schedule_stock_index_background_refresh", lambda app, reason: None)
    monkeypatch.setattr(
        app_module,
        "bootstrap_ssi_streaming_realtime",
        lambda: calls.append("bootstrap") or {"bootstrap_status": "disabled"},
    )
    monkeypatch.setattr(
        app_module,
        "shutdown_ssi_streaming_realtime",
        lambda: calls.append("shutdown") or {"bootstrap_status": "not_started"},
    )

    async def run_lifespan():
        app = FastAPI()
        async with app_module.app_lifespan(app):
            for _ in range(20):
                if calls:
                    break
                await asyncio.sleep(0.01)
            assert app.state.ssi_streaming_realtime_bootstrap_status["bootstrap_status"] == "disabled"

    asyncio.run(run_lifespan())

    assert calls == ["bootstrap", "shutdown"]
