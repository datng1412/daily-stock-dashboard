# -*- coding: utf-8 -*-
"""Deterministic lifecycle coverage for the SSI streaming channel cohort."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from data_provider.ssi_streaming_realtime import SsiStreamingRealtimeManager


VIETNAM_TZ = timezone(timedelta(hours=7))


def _active_epoch() -> float:
    return datetime(2026, 7, 16, 10, 0, tzinfo=VIETNAM_TZ).timestamp()


class FakeLifecycleClient:
    def __init__(self, *, fail_start: Exception | None = None, fail_channel: str | None = None):
        self.fail_start = fail_start
        self.fail_channel = fail_channel
        self.channels: list[str] = []
        self.start_calls = 0
        self.stop_calls = 0
        self.on_message = None
        self.on_error = None
        self.on_open = None
        self.on_close = None
        self.on_subscription_error = None

    def start(
        self,
        on_message,
        on_error,
        channels,
        *,
        on_open=None,
        on_close=None,
        on_subscription_error=None,
    ):
        self.start_calls += 1
        if self.fail_start is not None:
            raise self.fail_start
        self.channels = list(channels)
        self.on_message = on_message
        self.on_error = on_error
        self.on_open = on_open
        self.on_close = on_close
        self.on_subscription_error = on_subscription_error
        for channel in self.channels:
            if channel == self.fail_channel:
                if self.on_subscription_error:
                    self.on_subscription_error(channel, RuntimeError("subscription rejected"))
            elif self.on_open:
                self.on_open(channel)

    def stop(self):
        self.stop_calls += 1

    def emit(self, row):
        assert self.on_message is not None
        self.on_message(row)

    def disconnect(self, channel: str = "X:FPT"):
        assert self.on_close is not None
        self.on_close(channel)


def _row(*, price: float, trading_date: str = "16/07/2026"):
    return {
        "ticker": "FPT",
        "symbol": "FPT",
        "stream_data_type": "X",
        "trading_date": trading_date,
        "price": price,
    }


def _manager(clients, now):
    return SsiStreamingRealtimeManager(
        enabled=True,
        parser=lambda messages, _symbols: list(messages),
        client_factory=lambda: clients.pop(0),
        time_func=lambda: now[0],
        jitter_func=lambda _delay: 0.0,
        reconnect_initial_delay_seconds=2,
        reconnect_max_delay_seconds=30,
    )


def test_startup_is_idempotent_and_ready_requires_current_generation_event():
    now = [_active_epoch()]
    client = FakeLifecycleClient()
    manager = _manager([client], now)

    first = manager.start(["FPT"])
    second = manager.start(["FPT"])
    lifecycle = manager.lifecycle_snapshot()

    assert first["generation"] == 1
    assert second["generation"] == 1
    assert client.start_calls == 1
    assert lifecycle["transports"][0]["physical_transport_count"] == len(client.channels)
    assert lifecycle["contexts"]["x"]["state"] == "recovering"
    assert lifecycle["overall_state"] == "recovering"

    client.emit(_row(price=100.0))
    lifecycle = manager.lifecycle_snapshot()
    public_snapshot = manager.snapshot(["FPT"])

    assert lifecycle["contexts"]["x"]["state"] == "ready"
    assert lifecycle["contexts"]["x"]["last_event_generation"] == 1
    assert public_snapshot["stream_state"] == "ready"
    assert public_snapshot["generation"] == 1
    assert public_snapshot["last_event_at"] is not None


def test_duplicate_disconnect_has_one_schedule_and_old_generation_cannot_mutate_cache():
    now = [_active_epoch()]
    first_client = FakeLifecycleClient()
    second_client = FakeLifecycleClient()
    manager = _manager([first_client, second_client], now)
    manager.start(["FPT"])
    first_client.emit(_row(price=100.0))

    first_client.disconnect()
    first_client.disconnect("X-QUOTE:FPT")
    scheduled = manager.lifecycle_snapshot()["transports"][0]

    assert scheduled["reconnect_scheduled_count"] == 1
    assert scheduled["reconnect_task_count"] == 1
    assert scheduled["disconnect_count"] == 2

    now[0] += 2
    manager.monitor_tick(wants_streaming=True)
    lifecycle = manager.lifecycle_snapshot()
    assert lifecycle["transports"][0]["generation"] == 2
    assert lifecycle["contexts"]["x"]["state"] == "recovering"

    first_client.emit(_row(price=999.0))
    cached, _, _ = manager.cache.get("FPT")
    assert cached is not None
    assert cached["price"] == 100.0
    assert manager.lifecycle_snapshot()["transports"][0]["stale_generation_callbacks_ignored"] >= 1

    second_client.emit(_row(price=101.0))
    cached, _, _ = manager.cache.get("FPT")
    lifecycle = manager.lifecycle_snapshot()
    assert cached is not None
    assert cached["price"] == 101.0
    assert lifecycle["contexts"]["x"]["state"] == "ready"
    assert lifecycle["transports"][0]["reconnect_success_count"] == 1


def test_non_retryable_authentication_failure_fails_fast():
    now = [_active_epoch()]
    client = FakeLifecycleClient(fail_start=RuntimeError("401 Unauthorized"))
    manager = _manager([client], now)

    manager.start(["FPT"])
    status = manager.monitor_tick(wants_streaming=True)
    lifecycle = manager.lifecycle_snapshot()
    trade_payload = manager.trade_tape("FPT")

    assert status["last_error_class"] == "authentication"
    assert status["next_reconnect_at"] is None
    assert lifecycle["overall_state"] == "failed"
    assert lifecycle["transports"][0]["physical_transport_count"] == 0
    assert lifecycle["transports"][0]["subscription_count"] > 0
    assert lifecycle["transports"][0]["reconnect_scheduled_count"] == 0
    assert trade_payload["stream_state"] == "failed"
    assert trade_payload["generation"] == 1


def test_previous_session_event_does_not_restore_readiness():
    now = [_active_epoch()]
    client = FakeLifecycleClient()
    manager = _manager([client], now)
    manager.start(["FPT"])

    client.emit(_row(price=99.0, trading_date="15/07/2026"))
    lifecycle = manager.lifecycle_snapshot()

    assert lifecycle["contexts"]["x"]["state"] == "recovering"
    assert lifecycle["contexts"]["x"]["accepted_event_count"] == 1
    assert lifecycle["contexts"]["x"]["last_fresh_event_at"] is None


def test_one_subscription_failure_does_not_fail_unrelated_contexts():
    now = [_active_epoch()]
    client = FakeLifecycleClient(fail_channel="X-QUOTE:FPT")
    manager = _manager([client], now)
    manager.start(["FPT"])
    client.emit(_row(price=100.0))
    lifecycle = manager.lifecycle_snapshot()

    assert lifecycle["contexts"]["x"]["state"] == "ready"
    assert lifecycle["contexts"]["x_quote"]["state"] == "failed"
    assert lifecycle["contexts"]["x_quote"]["subscription_failure_count"] == 1
    assert lifecycle["contexts"]["x_trade"]["state"] == "recovering"
    assert lifecycle["overall_state"] == "degraded"


def test_shutdown_blocks_reconnect_and_ignores_late_callbacks():
    now = [_active_epoch()]
    client = FakeLifecycleClient()
    manager = _manager([client], now)
    manager.start(["FPT"])
    manager.mark_shutdown()
    manager.stop()

    client.disconnect()
    client.emit(_row(price=500.0))
    lifecycle = manager.lifecycle_snapshot()

    assert client.stop_calls == 1
    assert lifecycle["overall_state"] == "closed"
    assert lifecycle["transports"][0]["next_retry_at"] is None
    assert lifecycle["transports"][0]["shutdown_requested"] is True
