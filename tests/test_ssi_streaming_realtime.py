# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest

from data_provider.ssi_fastconnect_fetcher import SsiFastConnectFetcher
from data_provider.ssi_streaming_realtime import (
    MANAGER_ERRORED,
    MANAGER_RUNNING,
    OfficialSsiRealtimeStreamClient,
    RealtimeSnapshotCache,
    RUNTIME_RECONNECTING,
    RUNTIME_RUNNING_IDLE,
    SsiStreamingRealtimeManager,
    SSI_STREAMING_REALTIME_CACHE_EMPTY_REASON,
    SSI_STREAMING_REALTIME_CACHE_STALE_REASON,
    SSI_STREAMING_REALTIME_CONFIG_INCOMPLETE_REASON,
    SSI_STREAMING_REALTIME_DISABLED_REASON,
    SSI_STREAMING_REALTIME_MANAGER_ERROR_REASON,
    SSI_STREAMING_REALTIME_NOT_STARTED_REASON,
    SSI_STREAMING_REALTIME_PACKAGE_UNAVAILABLE_REASON,
    build_symbol_channel,
)
from src.services.vietnam_market_service import VietnamDashboardConfig, VietnamMarketService, clear_vietnam_cache


SECRET_TOKEN = "SECRET_STREAM_TOKEN_DO_NOT_EXPOSE"


class NoNetworkSession:
    def __init__(self):
        self.calls = []

    def post(self, *args, **kwargs):  # pragma: no cover - failure path
        self.calls.append(("POST", args, kwargs))
        raise AssertionError("Realtime streaming cache reads must not request REST tokens.")

    def get(self, *args, **kwargs):  # pragma: no cover - failure path
        self.calls.append(("GET", args, kwargs))
        raise AssertionError("Realtime streaming cache reads must not probe REST endpoints.")


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


class FakeOfficialClient:
    instances = []

    def __init__(self, config):
        self.config = config
        FakeOfficialClient.instances.append(self)


class FakeOfficialTransport:
    def __init__(self):
        self.stop_calls = 0

    def stop(self):
        self.stop_calls += 1


class FakeOfficialStream:
    instances = []

    def __init__(self, config, client):
        self.config = config
        self.client = client
        self.transport = FakeOfficialTransport()
        self.connection = SimpleNamespace()
        setattr(self.connection, "_Connection__transport", self.transport)
        self.started_channels = []
        FakeOfficialStream.instances.append(self)

    def start(self, on_message, on_error, channel):
        print(f"Authorization: Bearer {SECRET_TOKEN}")
        self.on_message = on_message
        self.on_error = on_error
        self.started_channels.append(channel)


def _fake_official_import(name):
    if name == "ssi_fc_data.fc_md_client":
        return SimpleNamespace(MarketDataClient=FakeOfficialClient)
    if name == "ssi_fc_data.fc_md_stream":
        return SimpleNamespace(MarketDataStream=FakeOfficialStream)
    raise ImportError(name)


class FakeMarketFetcher:
    def __init__(self, realtime_fetcher: SsiFastConnectFetcher):
        self.realtime_fetcher = realtime_fetcher

    def get_daily_ohlcv(self, symbol: str, **kwargs):
        rows = []
        for index in range(30):
            close = 101 + index
            rows.append(
                {
                    "date": f"2026-06-{index + 1:02d}",
                    "open": close - 1,
                    "high": close + 1,
                    "low": close - 2,
                    "close": close,
                    "volume": 1_000_000 + index,
                    "value": close * 1_000_000,
                    "source": "SSI",
                }
            )
        return {"status": "ok", "source": "SSI", "rows": rows}

    def get_daily_stock_price(self, symbol: str, **kwargs):
        return {
            "status": "ok",
            "source": "SSI",
            "rows": [
                {
                    "symbol": symbol,
                    "date": "2026-06-30",
                    "reference_price": 129.0,
                    "ceiling_price": 138.0,
                    "floor_price": 120.0,
                    "close": 130.0,
                    "matched_volume": 1_234_567,
                    "matched_value": 123_456_789_000,
                    "source": "SSI",
                }
            ],
        }

    def get_intraday_ohlcv(self, symbol: str, **kwargs):
        return {"status": "unavailable", "source": "SSI", "reason": "SSI intraday unavailable", "rows": []}

    def get_realtime_snapshot(self, symbols):
        return self.realtime_fetcher.get_realtime_snapshot(symbols)

    def get_trade_tape(self, symbol: str, **kwargs):
        return {"status": "unavailable", "source": "SSI", "symbol": symbol, "reason": "SSI trade tape unavailable", "trades": []}

    def get_securities_details(self, **kwargs):
        symbol = kwargs.get("symbol") or "FPT"
        return {"status": "ok", "source": "SSI", "rows": [{"symbol": symbol, "exchange": "HOSE", "market": "HOSE", "source": "SSI"}]}

    def get_securities(self, **kwargs):
        return self.get_securities_details(symbol="FPT")


def _fetcher(**kwargs) -> SsiFastConnectFetcher:
    defaults = {
        "enabled": True,
        "base_url": "https://example.test/Market",
        "consumer_id": "test-consumer",
        "consumer_secret": "test-secret",
        "cache_ttl_seconds": 0,
        "session": NoNetworkSession(),
        "config": SimpleNamespace(),
    }
    defaults.update(kwargs)
    return SsiFastConnectFetcher(**defaults)


def _manager(
    *,
    enabled: bool = True,
    client: FakeStreamClient | None = None,
    now=None,
    **overrides,
) -> SsiStreamingRealtimeManager:
    parser_fetcher = _fetcher()
    time_func = (lambda: now[0]) if now is not None else None
    kwargs = {
        "enabled": enabled,
        "parser": parser_fetcher.normalize_streaming_realtime_messages,
        "client_factory": (lambda: client) if client is not None else None,
    }
    if time_func is not None:
        kwargs["cache"] = RealtimeSnapshotCache(15, time_func=time_func)
        kwargs["time_func"] = time_func
    kwargs.update(overrides)
    return SsiStreamingRealtimeManager(**kwargs)


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


def _x_quote(symbol: str = "FPT"):
    return {
        "DataType": "X-QUOTE",
        "Content": {
            "RType": "X-QUOTE",
            "TradingDate": "25/06/2026",
            "Time": "10:01:03",
            "Symbol": symbol,
            "RefPrice": "129",
            "BidPrice1": "130.4",
            "BidVol1": "1000",
            "AskPrice1": "130.6",
            "AskVol1": "2000",
        },
    }


def _x_combined(symbol: str = "FPT"):
    payload = _x_quote(symbol)
    payload["DataType"] = "X"
    payload["Content"]["RType"] = "X"
    payload["Content"]["LastPrice"] = "130.7"
    return payload


def _service_with_fetcher(fetcher, *, streaming_enabled: bool = True) -> VietnamMarketService:
    clear_vietnam_cache()
    return VietnamMarketService(
        config=VietnamDashboardConfig(
            daily_data_provider="ssi",
            chart_data_provider="ssi",
            daily_stock_price_provider="ssi",
            index_data_provider="ssi",
            intraday_data_provider="ssi",
            ssi_intraday_enabled=True,
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
        ),
        ssi_fetcher=fetcher,
    )


def test_streaming_manager_default_disabled_returns_unavailable_and_does_not_start_client():
    calls = {"factory": 0}

    def factory():
        calls["factory"] += 1
        return FakeStreamClient()

    manager = SsiStreamingRealtimeManager(enabled=False, client_factory=factory)

    start_status = manager.start(["FPT"])
    payload = manager.snapshot(["FPT"])

    assert start_status["manager_state"] == "disabled"
    assert payload["status"] == "unavailable"
    assert payload["reason"] == SSI_STREAMING_REALTIME_DISABLED_REASON
    assert calls["factory"] == 0


def test_importing_streaming_module_does_not_import_official_client_or_start_network():
    sys.modules.pop("ssi_fc_data.fc_md_stream", None)

    module = importlib.reload(importlib.import_module("data_provider.ssi_streaming_realtime"))

    assert "ssi_fc_data.fc_md_stream" not in sys.modules
    assert not hasattr(module, "STREAMING_MANAGER")
    assert not hasattr(module, "STREAMING_CLIENT")


def test_manager_start_uses_symbol_scoped_channel_only():
    client = FakeStreamClient()
    manager = _manager(client=client)

    status = manager.start(["fpt"])

    assert status["manager_state"] == MANAGER_RUNNING
    assert client.started is True
    assert client.channels == ["X:FPT"]
    assert all("ALL" not in channel for channel in client.channels)


def test_explicit_old_space_channel_template_remains_respected():
    assert build_symbol_channel("fpt", "X: {symbol}") == "X: FPT"


def test_manager_rejects_all_channel_subscription_without_starting_client():
    client = FakeStreamClient()
    manager = _manager(client=client)

    status = manager.start(["ALL"])

    assert status["manager_state"] == MANAGER_ERRORED
    assert client.started is False
    assert "ALL channel" in str(status["latest_error"])


def test_manager_stop_is_idempotent():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.stop()
    manager.stop()

    assert client.stop_calls == 1


def test_manager_start_error_is_sanitized():
    client = FakeStreamClient(fail_start=True)
    manager = _manager(client=client)

    status = manager.start(["FPT"])
    payload = manager.snapshot(["FPT"])

    assert status["manager_state"] == MANAGER_ERRORED
    assert payload["reason"] == SSI_STREAMING_REALTIME_MANAGER_ERROR_REASON
    assert SECRET_TOKEN not in str(status)
    assert SECRET_TOKEN not in str(payload)
    assert "<redacted>" in str(status)


def test_x_trade_message_updates_cache_for_requested_symbol_without_trade_history():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.handle_message(_x_trade())
    payload = manager.snapshot(["FPT"])

    assert payload["status"] == "ok"
    assert payload["streaming_status"] == "cache_hit"
    assert payload["quotes"][0]["ticker"] == "FPT"
    assert payload["quotes"][0]["stream_data_type"] == "X-TRADE"
    assert payload["quotes"][0]["price"] == 130.5
    assert payload["quotes"][0]["has_last_trade"] is True
    assert "trades" not in payload["quotes"][0]


def test_x_quote_message_updates_quote_context_without_inventing_last_trade():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.handle_message(_x_quote())
    payload = manager.snapshot(["FPT"])

    assert payload["status"] == "ok"
    assert payload["quotes"][0]["price"] is None
    assert payload["quotes"][0]["has_last_trade"] is False
    assert payload["quotes"][0]["quote_only"] is True
    assert payload["quotes"][0]["bid_levels"][0] == {"price": 130.4, "volume": 1000.0}


def test_x_message_updates_snapshot_when_fields_exist():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.handle_message(_x_combined())
    payload = manager.snapshot(["FPT"])

    assert payload["status"] == "ok"
    assert payload["quotes"][0]["stream_data_type"] == "X"
    assert payload["quotes"][0]["price"] == 130.7
    assert payload["quotes"][0]["ask_levels"][0] == {"price": 130.6, "volume": 2000.0}


def test_malformed_message_does_not_crash_manager():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.handle_message({"DataType": "X-TRADE", "Content": '{"RType":"X-TRADE",'})
    payload = manager.snapshot(["FPT"])

    assert manager.state == MANAGER_RUNNING
    assert payload["status"] == "unavailable"
    assert payload["reason"] == SSI_STREAMING_REALTIME_CACHE_EMPTY_REASON


def test_message_for_unrequested_symbol_is_ignored():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])

    manager.handle_message(_x_trade("SSI", "32"))
    payload = manager.snapshot(["FPT"])

    assert payload["status"] == "unavailable"
    assert payload["reason"] == SSI_STREAMING_REALTIME_CACHE_EMPTY_REASON


def test_empty_and_stale_cache_return_unavailable():
    now = [100.0]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now)
    manager.start(["FPT"])

    assert manager.snapshot(["FPT"])["reason"] == SSI_STREAMING_REALTIME_CACHE_EMPTY_REASON
    manager.handle_message(_x_trade())
    now[0] = 120.0
    stale_payload = manager.snapshot(["FPT"])

    assert stale_payload["status"] == "unavailable"
    assert stale_payload["reason"] == SSI_STREAMING_REALTIME_CACHE_STALE_REASON
    assert stale_payload["cache_status"] == "stale"


def test_running_manager_with_no_messages_past_idle_timeout_reports_idle():
    now = [100.0]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now, idle_timeout_seconds=10)
    manager.start(["FPT"])

    now[0] = 111.0
    status = manager.status()
    payload = manager.snapshot(["FPT"])

    assert status["is_idle"] is True
    assert status["runtime_status"] == RUNTIME_RUNNING_IDLE
    assert payload["diagnostics"]["is_idle"] is True
    assert payload["diagnostics"]["runtime_status"] == RUNTIME_RUNNING_IDLE


def test_running_manager_with_recent_message_reports_not_idle():
    now = [100.0]
    client = FakeStreamClient()
    manager = _manager(client=client, now=now, idle_timeout_seconds=10)
    manager.start(["FPT"])
    now[0] = 105.0
    manager.handle_message(_x_trade())
    now[0] = 112.0

    status = manager.status()

    assert status["is_idle"] is False
    assert status["runtime_status"] == MANAGER_RUNNING


def test_idle_without_market_hours_utility_is_diagnostic_only_not_reconnect_loop():
    now = [100.0]
    clients = [FakeStreamClient()]
    manager = _manager(
        client=clients[0],
        now=now,
        idle_timeout_seconds=10,
        reconnect_enabled=True,
    )
    manager.start(["FPT"])
    now[0] = 120.0

    status = manager.monitor_tick(wants_streaming=True)

    assert status["is_idle"] is True
    assert status["runtime_status"] == RUNTIME_RUNNING_IDLE
    assert status["reconnect_attempt_count"] == 0
    assert status["next_reconnect_at"] is None
    assert clients[0].stop_calls == 0


def test_running_idle_realtime_does_not_make_daily_data_invalid():
    now = [100.0]
    client = FakeStreamClient()
    parser_fetcher = _fetcher(streaming_realtime_enabled=True)
    manager = SsiStreamingRealtimeManager(
        enabled=True,
        cache=RealtimeSnapshotCache(15, time_func=lambda: now[0]),
        parser=parser_fetcher.normalize_streaming_realtime_messages,
        client_factory=lambda: client,
        idle_timeout_seconds=10,
        time_func=lambda: now[0],
    )
    manager.start(["FPT"])
    now[0] = 120.0
    fetcher = _fetcher(
        streaming_realtime_enabled=True,
        streaming_realtime_manager=manager,
    )
    service = _service_with_fetcher(FakeMarketFetcher(fetcher))

    item = service.build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert item["status"] == "ok"
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["realtime_status"]["status"] == "unavailable"
    assert item["diagnostics"]["realtime"]["runtime_status"] == RUNTIME_RUNNING_IDLE
    assert item["data_quality_summary"]["checks"]["daily_ohlc"] == "ok"


def test_reconnect_enabled_schedules_reconnect_after_start_failure():
    now = [100.0]
    manager = _manager(
        client=FakeStreamClient(fail_start=True),
        now=now,
        reconnect_initial_delay_seconds=2,
        reconnect_max_delay_seconds=10,
    )
    manager.start(["FPT"])

    status = manager.monitor_tick(wants_streaming=True)

    assert status["manager_state"] == MANAGER_ERRORED
    assert status["runtime_status"] == RUNTIME_RECONNECTING
    assert status["reconnect_attempt_count"] == 0
    assert status["last_reconnect_reason"] == "start_error"
    assert status["next_reconnect_at"] is not None


def test_reconnect_backoff_increases_and_caps_after_failed_attempts():
    now = [100.0]
    clients = []

    def factory():
        client = FakeStreamClient(fail_start=True)
        clients.append(client)
        return client

    parser_fetcher = _fetcher()
    manager = SsiStreamingRealtimeManager(
        enabled=True,
        parser=parser_fetcher.normalize_streaming_realtime_messages,
        client_factory=factory,
        idle_timeout_seconds=10,
        reconnect_initial_delay_seconds=2,
        reconnect_max_delay_seconds=5,
        time_func=lambda: now[0],
    )
    manager.start(["FPT"])
    first = manager.monitor_tick(wants_streaming=True)
    assert first["reconnect_backoff_seconds"] == 4

    now[0] = 102.0
    second = manager.monitor_tick(wants_streaming=True)
    assert second["reconnect_attempt_count"] == 1
    assert second["reconnect_backoff_seconds"] == 5

    now[0] = 106.0
    third = manager.monitor_tick(wants_streaming=True)
    assert third["reconnect_attempt_count"] == 2
    assert third["reconnect_backoff_seconds"] == 5
    assert len(clients) == 3


def test_reconnect_max_attempts_positive_stops_after_attempt_limit():
    now = [100.0]
    manager = _manager(
        client=FakeStreamClient(fail_start=True),
        now=now,
        reconnect_initial_delay_seconds=2,
        reconnect_max_attempts=1,
    )
    manager.start(["FPT"])
    manager.monitor_tick(wants_streaming=True)
    now[0] = 102.0

    status = manager.monitor_tick(wants_streaming=True)

    assert status["reconnect_attempt_count"] == 1
    assert status["next_reconnect_at"] is None
    assert status["last_reconnect_error"] is not None


def test_reconnect_max_attempts_zero_allows_unlimited_attempts():
    now = [100.0]
    manager = _manager(
        client=FakeStreamClient(fail_start=True),
        now=now,
        reconnect_initial_delay_seconds=1,
        reconnect_max_attempts=0,
    )
    manager.start(["FPT"])
    for expected_attempts in range(1, 4):
        manager.monitor_tick(wants_streaming=True)
        now[0] += manager.status()["reconnect_backoff_seconds"]
        status = manager.monitor_tick(wants_streaming=True)
        assert status["reconnect_attempt_count"] == expected_attempts


def test_reconnect_stops_previous_stream_before_starting_new_one():
    now = [100.0]
    clients = [FakeStreamClient(), FakeStreamClient()]

    def factory():
        return clients.pop(0)

    parser_fetcher = _fetcher()
    manager = SsiStreamingRealtimeManager(
        enabled=True,
        parser=parser_fetcher.normalize_streaming_realtime_messages,
        client_factory=factory,
        reconnect_initial_delay_seconds=2,
        time_func=lambda: now[0],
    )
    manager.start(["FPT"])
    first_client = manager._client
    manager.handle_error("stream transport error")
    manager.monitor_tick(wants_streaming=True)
    now[0] = 102.0

    status = manager.monitor_tick(wants_streaming=True)

    assert status["manager_state"] == MANAGER_RUNNING
    assert first_client.stop_calls == 1
    assert status["reconnect_attempt_count"] == 1


def test_repeated_monitor_ticks_before_due_do_not_create_parallel_streams():
    now = [100.0]
    clients = [FakeStreamClient(fail_start=True)]
    manager = _manager(
        client=clients[0],
        now=now,
        reconnect_initial_delay_seconds=5,
    )
    manager.start(["FPT"])

    manager.monitor_tick(wants_streaming=True)
    manager.monitor_tick(wants_streaming=True)
    manager.monitor_tick(wants_streaming=True)

    assert manager.status()["reconnect_attempt_count"] == 0


def test_fetcher_config_off_returns_unavailable_even_if_manager_cache_has_data():
    client = FakeStreamClient()
    manager = _manager(client=client)
    manager.start(["FPT"])
    manager.handle_message(_x_trade())
    fetcher = _fetcher(
        streaming_realtime_enabled=False,
        streaming_realtime_manager=manager,
    )

    payload = fetcher.get_realtime_snapshot(["FPT"])

    assert payload["status"] == "unavailable"
    assert payload["reason"] == SSI_STREAMING_REALTIME_DISABLED_REASON
    assert payload["quotes"] == []


def test_service_config_off_returns_unavailable_even_if_fetcher_cache_has_data():
    client = FakeStreamClient()
    parser_fetcher = _fetcher(streaming_realtime_enabled=True)
    manager = SsiStreamingRealtimeManager(
        enabled=True,
        parser=parser_fetcher.normalize_streaming_realtime_messages,
        client_factory=lambda: client,
    )
    manager.start(["FPT"])
    manager.handle_message(_x_trade(price="131.5"))
    fetcher = _fetcher(
        streaming_realtime_enabled=True,
        streaming_realtime_manager=manager,
    )
    service = _service_with_fetcher(FakeMarketFetcher(fetcher), streaming_enabled=False)

    payload = service.build_realtime_snapshot(["FPT"], force_refresh=True)

    assert payload["status"] == "unavailable"
    assert payload["error"] == "SSI realtime manager disabled."
    assert payload["quotes"] == []
    assert payload["streaming_status"] == "disabled"


def test_fetcher_does_not_probe_rest_when_streaming_manager_not_started():
    fetcher = _fetcher(streaming_realtime_enabled=True)

    payload = fetcher.get_realtime_snapshot(["FPT"])

    assert payload["status"] == "unavailable"
    assert payload["reason"] == SSI_STREAMING_REALTIME_NOT_STARTED_REASON
    assert fetcher.session.calls == []


def test_official_client_factory_is_not_called_when_streaming_config_is_off():
    calls = {"factory": 0}

    def factory():
        calls["factory"] += 1
        return FakeStreamClient()

    fetcher = _fetcher(
        streaming_realtime_enabled=False,
        streaming_realtime_client_factory=factory,
    )

    payload = fetcher.get_realtime_snapshot(["FPT"])

    assert payload["reason"] == SSI_STREAMING_REALTIME_DISABLED_REASON
    assert calls["factory"] == 0


def test_fetcher_config_off_does_not_check_or_import_official_package(monkeypatch):
    def fail_find_spec(name):  # pragma: no cover - should not be called
        raise AssertionError("official package lookup must not run when streaming is disabled")

    monkeypatch.setattr("data_provider.ssi_fastconnect_fetcher.importlib.util.find_spec", fail_find_spec)
    fetcher = _fetcher(streaming_realtime_enabled=False)

    payload = fetcher.get_realtime_snapshot(["FPT"])

    assert payload["reason"] == SSI_STREAMING_REALTIME_DISABLED_REASON


def test_fetcher_config_on_missing_streaming_config_fails_closed():
    fetcher = _fetcher(
        streaming_realtime_enabled=True,
        consumer_id="",
        consumer_secret="",
    )

    payload = fetcher.get_realtime_snapshot(["FPT"])

    assert payload["status"] == "unavailable"
    assert payload["reason"] == SSI_STREAMING_REALTIME_CONFIG_INCOMPLETE_REASON
    assert payload["diagnostics"]["live_adapter_status"] == "configuration_incomplete"


def test_fetcher_config_on_missing_official_package_fails_closed(monkeypatch):
    monkeypatch.setattr("data_provider.ssi_fastconnect_fetcher.importlib.util.find_spec", lambda name: None)
    fetcher = _fetcher(streaming_realtime_enabled=True)

    payload = fetcher.get_realtime_snapshot(["FPT"])

    assert payload["status"] == "unavailable"
    assert payload["reason"] == SSI_STREAMING_REALTIME_PACKAGE_UNAVAILABLE_REASON
    assert payload["diagnostics"]["live_adapter_status"] == "package_unavailable"


def test_official_adapter_starts_symbol_channel_without_leaking_headers(capsys):
    FakeOfficialClient.instances.clear()
    FakeOfficialStream.instances.clear()
    adapter = OfficialSsiRealtimeStreamClient(
        consumer_id="test-consumer",
        consumer_secret="test-secret",
        base_url="https://fc-data.ssi.com.vn/api/v2/Market",
        stream_url="https://fc-datahub.ssi.com.vn/",
        import_module=_fake_official_import,
    )

    adapter.start(lambda message: None, lambda error: None, ["X:FPT"])
    captured = capsys.readouterr()

    assert SECRET_TOKEN not in captured.out
    assert SECRET_TOKEN not in captured.err
    assert FakeOfficialClient.instances[0].config.url == "https://fc-data.ssi.com.vn/"
    assert FakeOfficialClient.instances[0].config.stream_url == "https://fc-datahub.ssi.com.vn/"
    assert FakeOfficialStream.instances[0].started_channels == ["X:FPT"]
    adapter.stop()
    assert FakeOfficialStream.instances[0].transport.stop_calls == 1


def test_official_adapter_missing_package_fails_closed():
    adapter = OfficialSsiRealtimeStreamClient(
        consumer_id="test-consumer",
        consumer_secret="test-secret",
        base_url="https://fc-data.ssi.com.vn/api/v2/Market",
        import_module=lambda name: (_ for _ in ()).throw(ImportError(name)),
    )

    with pytest.raises(RuntimeError, match=SSI_STREAMING_REALTIME_PACKAGE_UNAVAILABLE_REASON):
        adapter.start(lambda message: None, lambda error: None, ["X:FPT"])


def test_manager_start_instantiates_official_wrapper_only_when_enabled():
    calls = {"factory": 0}

    def factory():
        calls["factory"] += 1
        return FakeStreamClient()

    disabled = SsiStreamingRealtimeManager(enabled=False, client_factory=factory)
    enabled = SsiStreamingRealtimeManager(enabled=True, client_factory=factory)

    disabled.start(["FPT"])
    assert calls["factory"] == 0
    enabled.start(["FPT"])
    assert calls["factory"] == 1


def test_realtime_service_reads_cache_hit_without_overwriting_daily_latest_price():
    client = FakeStreamClient()
    parser_fetcher = _fetcher(streaming_realtime_enabled=True)
    manager = SsiStreamingRealtimeManager(
        enabled=True,
        parser=parser_fetcher.normalize_streaming_realtime_messages,
        client_factory=lambda: client,
    )
    manager.start(["FPT"])
    manager.handle_message(_x_trade(price="131.5"))
    fetcher = _fetcher(
        streaming_realtime_enabled=True,
        streaming_realtime_manager=manager,
    )
    service = _service_with_fetcher(FakeMarketFetcher(fetcher))

    endpoint_payload = service.build_realtime_snapshot(["FPT"], force_refresh=True)
    item = service.build_watchlist(["FPT"], force_refresh=True)["watchlist"][0]

    assert endpoint_payload["status"] == "ok"
    assert endpoint_payload["quotes"][0]["price"] == 131.5
    assert endpoint_payload["streaming_status"] == "cache_hit"
    assert item["realtime_status"]["status"] == "ok"
    assert item["realtime_snapshot"]["price"] == 131.5
    assert item["latest_price"] == item["daily_close"]
    assert item["latest_price_source"] == "SSI DailyOhlc"
    assert item["trade_tape"] == []
    assert item["trade_tape_status"]["status"] == "unavailable"
