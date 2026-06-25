# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib
import json
import sys
from typing import Any, Dict, List

import pytest


SECRET_VALUE = "SECRET_STREAM_TOKEN_DO_NOT_EXPOSE"


class FakeManager:
    instances: List["FakeManager"] = []

    def __init__(self, *, config, parser, fail_start: bool = False, quotes: List[Dict[str, Any]] | None = None):
        self.config = config
        self.parser = parser
        self.fail_start = fail_start
        self.quotes = quotes or []
        self.started_symbols = []
        self.stop_calls = 0
        self.snapshot_calls = 0
        self.channels = []
        self.latest_error = None
        self.messages_observed = 0
        self.parser_rows_observed = 0
        FakeManager.instances.append(self)

    def start(self, symbols):
        self.started_symbols = list(symbols)
        self.channels = [self.config["channel_template"].format(symbol=symbol) for symbol in symbols]
        if self.fail_start:
            self.latest_error = f"Authorization: Bearer {SECRET_VALUE}"
            return self.status() | {"manager_state": "errored"}
        return self.status() | {"manager_state": "running"}

    def snapshot(self, symbols):
        self.snapshot_calls += 1
        if self.quotes:
            self.messages_observed = 1
            self.parser_rows_observed = len(self.quotes)
            return {
                "status": "ok",
                "cache_status": "hit",
                "quotes": self.quotes,
                "count": len(self.quotes),
            }
        return {
            "status": "unavailable",
            "cache_status": "empty",
            "quotes": [],
            "count": 0,
        }

    def status(self):
        return {
            "manager_state": "running" if self.started_symbols and not self.latest_error else "stopped",
            "channels": list(self.channels),
            "latest_error": self.latest_error,
            "messages_observed": self.messages_observed,
            "parser_rows_observed": self.parser_rows_observed,
        }

    def stop(self):
        self.stop_calls += 1
        return self.status() | {"manager_state": "stopped"}


def _load_script(monkeypatch):
    sys.modules.pop("scripts.verify_ssi_streaming_realtime", None)
    imported_fastapi = False
    original_import = __import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        nonlocal imported_fastapi
        if name == "api.app" or name.startswith("fastapi"):
            imported_fastapi = True
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", guarded_import)
    module = importlib.import_module("scripts.verify_ssi_streaming_realtime")
    assert not imported_fastapi
    return module


def _set_valid_env(monkeypatch):
    monkeypatch.setenv("SSI_FASTCONNECT_CONSUMER_ID", "consumer-id-test")
    monkeypatch.setenv("SSI_FASTCONNECT_CONSUMER_SECRET", SECRET_VALUE)
    monkeypatch.setenv("SSI_FASTCONNECT_BASE_URL", "https://fc-data.ssi.com.vn/api/v2/Market")
    monkeypatch.setenv("SSI_STREAMING_REALTIME_STREAM_URL", "https://fc-datahub.ssi.com.vn/")


def _last_json(capsys):
    output = capsys.readouterr().out.strip().splitlines()
    assert output
    return json.loads(output[-1]), "\n".join(output)


def test_script_can_be_imported_without_starting_stream(monkeypatch):
    module = _load_script(monkeypatch)
    assert hasattr(module, "main")
    assert not hasattr(module, "_started")


def test_check_config_only_does_not_start_manager_or_client(monkeypatch, capsys):
    module = _load_script(monkeypatch)
    monkeypatch.setattr(module, "load_dotenv_if_available", lambda: None)
    _set_valid_env(monkeypatch)

    def fail_manager_factory(**kwargs):  # pragma: no cover - should not be called
        raise AssertionError("manager must not be constructed in config-only mode")

    monkeypatch.setattr(module, "make_manager", fail_manager_factory)
    code = module.main(["--symbols", "fpt,hpg", "--check-config-only"])
    payload, output = _last_json(capsys)

    assert code == 0
    assert payload["started"] is False
    assert payload["requested_symbols"] == ["FPT", "HPG"]
    assert payload["channels"] == ["X: FPT", "X: HPG"]
    assert payload["script_cache_only"] is True
    assert payload["backend_cache_populated"] is False
    assert SECRET_VALUE not in output


def test_cli_parses_and_normalizes_comma_symbols(monkeypatch):
    module = _load_script(monkeypatch)
    assert module.parse_symbols(" fpt,HPG,ssi,fpt ") == ["FPT", "HPG", "SSI"]


@pytest.mark.parametrize("symbols", ["ALL", "FPT,$BAD", ""])
def test_invalid_symbols_are_rejected(monkeypatch, symbols):
    module = _load_script(monkeypatch)
    with pytest.raises(ValueError):
        module.parse_symbols(symbols)


def test_channel_template_without_symbol_is_rejected(monkeypatch):
    module = _load_script(monkeypatch)
    with pytest.raises(ValueError):
        module.validate_channels(["FPT"], "X: FPT")


def test_channel_template_resulting_in_all_is_rejected(monkeypatch):
    module = _load_script(monkeypatch)
    with pytest.raises(ValueError):
        module.validate_channels(["FPT"], "X: ALL")


def test_missing_config_returns_safe_error_without_values(monkeypatch, capsys):
    module = _load_script(monkeypatch)
    monkeypatch.setattr(module, "load_dotenv_if_available", lambda: None)
    for key in (
        "SSI_CONSUMER_ID",
        "SSI_FASTCONNECT_CONSUMER_ID",
        "SSI_FC_DATA_CONSUMER_ID",
        "SSI_CONSUMER_SECRET",
        "SSI_FASTCONNECT_CONSUMER_SECRET",
        "SSI_FC_DATA_CONSUMER_SECRET",
        "SSI_FASTCONNECT_BASE_URL",
        "SSI_FC_DATA_BASE_URL",
        "SSI_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)

    code = module.main(["--symbols", "FPT", "--check-config-only"])
    payload, output = _last_json(capsys)

    assert code == 2
    assert payload["status"] == "invalid_config"
    assert payload["missing"] == ["consumer_id", "consumer_secret", "base_url"]
    assert SECRET_VALUE not in output
    assert "consumer-id-test" not in output


def test_mock_manager_starts_with_symbol_scoped_channels_and_parser(monkeypatch, capsys):
    module = _load_script(monkeypatch)
    _set_valid_env(monkeypatch)
    FakeManager.instances.clear()

    def manager_factory(**kwargs):
        return FakeManager(
            config=kwargs["config"],
            parser=kwargs["parser"],
            quotes=[{"ticker": "FPT", "last_price": 100.0}],
        )

    code = module.run_verification(
        symbols=["FPT"],
        config=module.load_config(module.build_arg_parser().parse_args([])),
        wait_seconds=0,
        poll_interval_seconds=0,
        manager_factory=manager_factory,
        sleep_func=lambda _: None,
        monotonic_func=lambda: 0.0,
    )
    payload, output = _last_json(capsys)

    assert code == 0
    assert FakeManager.instances[0].started_symbols == ["FPT"]
    assert FakeManager.instances[0].channels == ["X: FPT"]
    assert FakeManager.instances[0].parser.__name__ == "normalize_streaming_realtime_messages"
    assert FakeManager.instances[0].stop_calls == 1
    assert payload["quote_count"] == 1
    assert payload["symbols_with_quotes"] == ["FPT"]
    assert payload["script_cache_only"] is True
    assert payload["backend_cache_populated"] is False
    assert SECRET_VALUE not in output


def test_start_failure_sanitizes_secret_and_returns_manager_error(monkeypatch, capsys):
    module = _load_script(monkeypatch)
    _set_valid_env(monkeypatch)
    FakeManager.instances.clear()

    def manager_factory(**kwargs):
        return FakeManager(config=kwargs["config"], parser=kwargs["parser"], fail_start=True)

    code = module.run_verification(
        symbols=["FPT"],
        config=module.load_config(module.build_arg_parser().parse_args([])),
        wait_seconds=0,
        poll_interval_seconds=0,
        manager_factory=manager_factory,
        sleep_func=lambda _: None,
        monotonic_func=lambda: 0.0,
    )
    payload, output = _last_json(capsys)

    assert code == 4
    assert payload["started"] is False
    assert "<redacted>" in payload["latest_error"]
    assert SECRET_VALUE not in output
    assert FakeManager.instances[0].stop_calls == 1


def test_main_does_not_call_backend_endpoint(monkeypatch):
    module = _load_script(monkeypatch)
    source = open(module.__file__, "r", encoding="utf-8").read()
    assert "/realtime" not in source
    assert "requests." not in source


def test_no_public_api_start_stop_added():
    endpoint_source = open("api/v1/endpoints/stocks.py", "r", encoding="utf-8").read()
    assert "streaming/start" not in endpoint_source
    assert "streaming/stop" not in endpoint_source
