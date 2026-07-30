from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from scripts import diagnose_vn_current_foreign_flow as diagnostic


def test_symbol_parser_normalizes_and_deduplicates():
    assert diagnostic.parse_symbols(" fpt,FPT,ssi ") == ("FPT", "SSI")


@pytest.mark.parametrize("value", ["", "FPT,SSI,HPG", "F", "FPT,$$$"])
def test_symbol_parser_enforces_bounds_and_shape(value):
    with pytest.raises(ValueError):
        diagnostic.parse_symbols(value)


@pytest.mark.parametrize("value", [0, 9])
def test_sample_count_bounds(value):
    with pytest.raises(SystemExit):
        diagnostic.parse_options(["--sample-count", str(value)])


@pytest.mark.parametrize("value", [4, 31])
def test_interval_bounds(value):
    with pytest.raises(SystemExit):
        diagnostic.parse_options(["--interval-seconds", str(value)])


def test_runtime_bound_is_enforced():
    with pytest.raises(SystemExit):
        diagnostic.parse_options(["--max-runtime-seconds", "121"])


def test_unknown_candidate_source_is_rejected():
    with pytest.raises(ValueError):
        diagnostic.parse_sources("daily_stock_price,undocumented")


@pytest.mark.parametrize(
    "text",
    [
        "Authorization: Bearer abc123",
        "consumerSecret=secret-value",
        "privateKey: value",
        "accessToken=token",
        "refreshToken=token",
        "password=hunter2",
    ],
)
def test_secret_shaped_values_are_redacted(text):
    sanitized = diagnostic.sanitize_text(text)
    assert "[REDACTED]" in sanitized
    assert text.split()[-1] not in sanitized


def test_offline_run_performs_no_network(monkeypatch, capsys):
    def fail_adapter(*_args, **_kwargs):
        raise AssertionError("adapter must not be constructed offline")

    monkeypatch.setattr(diagnostic, "SsiFastConnectV3Adapter", fail_adapter)
    options = diagnostic.parse_options(
        ["--output-format", "json", "--max-runtime-seconds", "1"]
    )
    assert diagnostic.run(options) == 0
    events = json.loads(capsys.readouterr().out)
    final = events[-1]
    assert final["provider_request_count"] == 0
    assert final["surviving_owned_threads"] == 0


def test_after_hours_live_opt_in_performs_no_network(monkeypatch, capsys):
    monkeypatch.setattr(
        diagnostic,
        "vietnam_market_session_from_epoch",
        lambda _epoch: {"market_session": "closed", "market_session_active": False},
    )

    def fail_adapter(*_args, **_kwargs):
        raise AssertionError("adapter must not be constructed after hours")

    monkeypatch.setattr(diagnostic, "SsiFastConnectV3Adapter", fail_adapter)
    options = diagnostic.parse_options(
        ["--allow-live", "--output-format", "json", "--max-runtime-seconds", "1"]
    )
    assert diagnostic.run(options) == 0
    events = json.loads(capsys.readouterr().out)
    assert events[-1]["primary_outcome"].endswith("ACTIVE_SESSION_PENDING")
    assert events[-1]["provider_request_count"] == 0


class _FakeConfig:
    pass


class _FakeAdapter:
    instance = None

    def __init__(self, settings):
        self.settings = settings
        self.closed = False
        type(self).instance = self

    def initialize_rest_access(self):
        return {"status": "ok"}

    def get_daily_stock_price(self, symbol, **_kwargs):
        return {
            "status": "ok",
            "rows": [
                {
                    "date": diagnostic.datetime.now(
                        diagnostic.VN_TIMEZONE
                    ).date().isoformat(),
                    "foreign_buy_volume": 10,
                    "foreign_sell_volume": 5,
                    "foreign_buy_value": 1_000,
                    "foreign_sell_value": 500,
                }
            ],
        }

    def close(self):
        self.closed = True


def _active_run_patches(monkeypatch):
    monkeypatch.setattr(
        diagnostic,
        "vietnam_market_session_from_epoch",
        lambda _epoch: {
            "market_session": "continuous_afternoon",
            "market_session_active": True,
        },
    )
    monkeypatch.setattr(diagnostic, "setup_env", lambda: None)
    monkeypatch.setattr(diagnostic.Config, "reset_instance", lambda: None)
    monkeypatch.setattr(diagnostic, "get_config", lambda: _FakeConfig())
    monkeypatch.setattr(
        diagnostic.SsiV3RestSettings,
        "from_config",
        classmethod(
            lambda _cls, _config: diagnostic.SsiV3RestSettings(
                enabled=True,
                api_key="configured",
                api_secret="configured",
                request_timeout=10,
                max_retries=2,
            )
        ),
    )
    monkeypatch.setattr(diagnostic, "SsiFastConnectV3Adapter", _FakeAdapter)


def test_active_run_closes_owned_client(monkeypatch, capsys):
    _active_run_patches(monkeypatch)
    options = diagnostic.parse_options(
        [
            "--allow-live",
            "--symbols",
            "FPT",
            "--sample-count",
            "1",
            "--interval-seconds",
            "5",
            "--max-runtime-seconds",
            "5",
            "--output-format",
            "json",
            "--candidate-sources",
            "daily_stock_price",
        ]
    )
    diagnostic.run(options)
    capsys.readouterr()
    assert _FakeAdapter.instance is not None
    assert _FakeAdapter.instance.closed is True
    assert _FakeAdapter.instance.settings.max_retries == 0


def test_active_run_stops_on_rate_limit_and_closes(monkeypatch, capsys):
    class RateLimitedAdapter(_FakeAdapter):
        def get_daily_stock_price(self, symbol, **_kwargs):
            return {"status": "unavailable", "failure_class": "rate_limited"}

    _active_run_patches(monkeypatch)
    monkeypatch.setattr(diagnostic, "SsiFastConnectV3Adapter", RateLimitedAdapter)
    options = diagnostic.parse_options(
        [
            "--allow-live",
            "--symbols",
            "FPT,SSI",
            "--sample-count",
            "4",
            "--interval-seconds",
            "5",
            "--max-runtime-seconds",
            "10",
            "--output-format",
            "json",
            "--candidate-sources",
            "daily_stock_price",
        ]
    )
    assert diagnostic.run(options) == 2
    events = json.loads(capsys.readouterr().out)
    assert events[-1]["failure_class"] == "rate_limited"
    assert events[-1]["provider_request_count"] == 1
    assert RateLimitedAdapter.instance.closed is True


def test_active_run_stops_on_authentication_failure(monkeypatch, capsys):
    class AuthFailedAdapter(_FakeAdapter):
        def initialize_rest_access(self):
            return {"status": "unavailable", "failure_class": "authentication"}

    _active_run_patches(monkeypatch)
    monkeypatch.setattr(diagnostic, "SsiFastConnectV3Adapter", AuthFailedAdapter)
    options = diagnostic.parse_options(
        [
            "--allow-live",
            "--symbols",
            "FPT",
            "--sample-count",
            "1",
            "--interval-seconds",
            "5",
            "--max-runtime-seconds",
            "5",
            "--output-format",
            "json",
            "--candidate-sources",
            "daily_stock_price",
        ]
    )
    assert diagnostic.run(options) == 2
    events = json.loads(capsys.readouterr().out)
    assert events[-1]["failure_class"] == "authentication"
    assert events[-1]["provider_request_count"] == 0
    assert AuthFailedAdapter.instance.closed is True


def test_reconciliation_loader_rejects_oversized_artifact(tmp_path: Path):
    path = tmp_path / "evidence.json"
    path.write_text("x" * (128 * 1024 + 1), encoding="utf-8")
    with pytest.raises(ValueError, match="exceeds"):
        diagnostic._load_reconciliation(path)


def test_output_contract_does_not_include_raw_payload_or_secrets(monkeypatch, capsys):
    _active_run_patches(monkeypatch)
    options = diagnostic.parse_options(
        [
            "--allow-live",
            "--symbols",
            "FPT",
            "--sample-count",
            "1",
            "--interval-seconds",
            "5",
            "--max-runtime-seconds",
            "5",
            "--output-format",
            "json",
            "--candidate-sources",
            "daily_stock_price",
        ]
    )
    diagnostic.run(options)
    output = capsys.readouterr().out.lower()
    assert "authorization" not in output
    assert "bearer " not in output
    assert "consumersecret" not in output
    assert "raw_payload" not in output


class _FakeRoomStream:
    instance = None
    messages = []
    error = None

    def __init__(self, settings):
        self.settings = settings
        self.stopped = False
        type(self).instance = self

    def start(
        self,
        on_message,
        on_error,
        channels,
        *,
        on_open=None,
        on_subscription_error=None,
    ):
        assert channels == ["R:FPT"]
        if self.error is not None:
            if on_subscription_error:
                on_subscription_error(channels[0], self.error)
            on_error(self.error)
            return
        if on_open:
            on_open(channels[0])
        for message in self.messages:
            on_message(message)

    def stop(self):
        self.stopped = True


def _active_room_run_patches(monkeypatch, *, messages=None, error=None):
    _active_run_patches(monkeypatch)
    _FakeRoomStream.messages = list(messages or [])
    _FakeRoomStream.error = error
    _FakeRoomStream.instance = None
    monkeypatch.setattr(
        diagnostic, "OfficialSsiV3RealtimeStreamClient", _FakeRoomStream
    )


def _room_message(**overrides):
    data = {
        "t": "10:00:00",
        "s": "FPT",
        "tr": 1_000,
        "cr": 800,
        "bq": 100,
        "sq": 80,
        "bv": 1_000_000,
        "sv": 800_000,
    }
    data.update(overrides)
    return {"topic": "room.FPT", "data": data}


def test_room_live_run_owns_one_subscription_and_closes_client(monkeypatch, capsys):
    _active_room_run_patches(monkeypatch, messages=[_room_message()])
    options = diagnostic.parse_options(
        [
            "--allow-live",
            "--candidate-sources",
            "room",
            "--symbols",
            "FPT",
            "--sample-count",
            "1",
            "--max-runtime-seconds",
            "5",
            "--output-format",
            "json",
        ]
    )
    assert diagnostic.run(options) == 0
    events = json.loads(capsys.readouterr().out)
    final = events[-1]
    assert final["provider_subscription_count"] == 1
    assert final["provider_event_count"] == 1
    assert final["client_closed"] is True
    assert final["surviving_owned_threads"] == 0
    assert _FakeRoomStream.instance.stopped is True


def test_room_live_run_closes_on_callback_payload_error(monkeypatch, capsys):
    malformed = {"topic": "room.FPT", "data": {"t": "10:00:00"}}
    _active_room_run_patches(monkeypatch, messages=[malformed])
    options = diagnostic.parse_options(
        [
            "--allow-live",
            "--candidate-sources",
            "room",
            "--symbols",
            "FPT",
            "--sample-count",
            "1",
            "--max-runtime-seconds",
            "1",
            "--output-format",
            "json",
        ]
    )
    assert diagnostic.run(options) == 0
    events = json.loads(capsys.readouterr().out)
    assert any(event.get("status") == "rejected" for event in events)
    assert _FakeRoomStream.instance.stopped is True


def test_room_live_run_closes_on_authentication_failure(monkeypatch, capsys):
    _active_room_run_patches(monkeypatch, error=RuntimeError("401 authentication failed"))
    options = diagnostic.parse_options(
        [
            "--allow-live",
            "--candidate-sources",
            "room",
            "--symbols",
            "FPT",
            "--sample-count",
            "1",
            "--max-runtime-seconds",
            "5",
            "--output-format",
            "json",
        ]
    )
    assert diagnostic.run(options) == 2
    events = json.loads(capsys.readouterr().out)
    assert events[-1]["failure_class"] == "authentication"
    assert events[-1]["authentication_status"] == "unavailable"
    assert _FakeRoomStream.instance.stopped is True
