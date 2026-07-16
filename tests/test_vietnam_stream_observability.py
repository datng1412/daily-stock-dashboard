# -*- coding: utf-8 -*-
"""Read-only API coverage for SSI streaming lifecycle observability."""

from types import SimpleNamespace

from api.v1.endpoints.stocks import get_vietnam_intraday_chart_health, get_vietnam_observability
from fastapi import Response
from src.services.ssi_streaming_realtime_lifecycle import (
    bootstrap_ssi_streaming_realtime,
    reset_ssi_streaming_realtime_lifecycle_for_tests,
)


class FakeObservableClient:
    def __init__(self):
        self.start_calls = 0
        self.stop_calls = 0
        self.channels = []

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
        self.channels = list(channels)
        if on_open:
            for channel in self.channels:
                on_open(channel)

    def stop(self):
        self.stop_calls += 1


def _config():
    return SimpleNamespace(
        ssi_fastconnect_enabled=True,
        ssi_fastconnect_base_url="https://example.test/api/v2/Market",
        ssi_fastconnect_consumer_id="placeholder",
        ssi_fastconnect_consumer_secret="placeholder",
        ssi_fastconnect_realtime_enabled=True,
        ssi_fastconnect_trade_tape_enabled=True,
        ssi_fastconnect_intraday_enabled=True,
        ssi_streaming_realtime_enabled=True,
        ssi_streaming_realtime_bootstrap_symbols="FPT",
        ssi_streaming_realtime_channel_template="X:{symbol}",
        ssi_streaming_realtime_cache_ttl_seconds=15,
        ssi_streaming_realtime_idle_timeout_seconds=45,
        ssi_streaming_realtime_reconnect_enabled=True,
        ssi_streaming_realtime_reconnect_initial_delay_seconds=2,
        ssi_streaming_realtime_reconnect_max_delay_seconds=30,
        ssi_streaming_realtime_reconnect_max_attempts=0,
        ssi_streaming_snapshot_enabled=False,
    )


def setup_function():
    reset_ssi_streaming_realtime_lifecycle_for_tests()


def teardown_function():
    reset_ssi_streaming_realtime_lifecycle_for_tests()


def test_observability_exposes_typed_process_local_streaming_without_side_effects():
    client = FakeObservableClient()
    bootstrap_ssi_streaming_realtime(config=_config(), client_factory=lambda: client, start_monitor=False)
    before = (client.start_calls, client.stop_calls, list(client.channels))

    response = Response()
    payload = get_vietnam_observability(response).model_dump()
    second = get_vietnam_observability().model_dump()

    assert payload["streaming"]["scope"] == "process_local"
    assert response.headers["Cache-Control"] == "no-store"
    assert payload["streaming"]["overall_state"] == "recovering"
    assert len(payload["streaming"]["transports"]) == 1
    assert payload["streaming"]["transports"][0]["generation"] == 1
    assert payload["streaming"]["contexts"]["x"]["state"] == "recovering"
    assert (client.start_calls, client.stop_calls, list(client.channels)) == before
    assert second["streaming"] == payload["streaming"]
    serialized = str(payload["streaming"]).lower()
    assert "authorization" not in serialized
    assert "consumer_secret" not in serialized
    assert "websocket" not in serialized
    assert "x:fpt" not in serialized


def test_intraday_health_remains_separate_from_streaming_lifecycle():
    response = Response()
    payload = get_vietnam_intraday_chart_health(response).model_dump()

    assert response.headers["Cache-Control"] == "no-store"
    assert "streaming" not in payload
