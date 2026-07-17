# -*- coding: utf-8 -*-

from __future__ import annotations

import importlib
import json
import sys
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest


SECRET_VALUE = "SECRET_STREAM_TOKEN_DO_NOT_EXPOSE"


class FakeManager:
    instances: List["FakeManager"] = []

    def __init__(
        self,
        *,
        config,
        parser,
        fail_start: bool = False,
        quotes: List[Dict[str, Any]] | None = None,
        messages: List[Any] | None = None,
        errors: List[Any] | None = None,
    ):
        self.config = config
        self.parser = parser
        self.fail_start = fail_start
        self.quotes = quotes or []
        self.messages = messages or []
        self.errors = errors or []
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
        if self.errors:
            self.handle_error(self.errors.pop(0))
        if self.messages:
            self.handle_message(self.messages.pop(0))
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

    def handle_message(self, message):
        self.messages_observed += 1
        rows = self.parser([message], self.started_symbols)
        self.parser_rows_observed += len(rows or [])
        if rows:
            self.quotes = rows

    def handle_error(self, error):
        self.latest_error = str(error)

    def status(self):
        return {
            "manager_state": "errored" if self.latest_error else ("running" if self.started_symbols else "stopped"),
            "channels": list(self.channels),
            "latest_error": self.latest_error,
            "messages_observed": self.messages_observed,
            "parser_rows_observed": self.parser_rows_observed,
        }

    def stop(self):
        self.stop_calls += 1
        return self.status() | {"manager_state": "stopped"}


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
    callback_mode = "message"
    print_secret = True

    def __init__(self, config, client):
        self.config = config
        self.client = client
        self.transport = FakeOfficialTransport()
        self.connection = SimpleNamespace()
        setattr(self.connection, "_Connection__transport", self.transport)
        self.started_args = []
        FakeOfficialStream.instances.append(self)

    def start(self, on_message, on_error, selected_channel):
        if self.print_secret:
            print(f"Authorization: Bearer {SECRET_VALUE}")
        self.started_args.append(selected_channel)
        if self.callback_mode == "message":
            on_message({"DataType": "X-TRADE", "Content": json.dumps({"RType": "X-TRADE", "Symbol": "FPT", "LastPrice": 100.0, "Secret": SECRET_VALUE})})
        elif self.callback_mode == "error":
            on_error(f"consumerSecret={SECRET_VALUE}")
        elif self.callback_mode == "raise":
            raise RuntimeError(f"Authorization: Bearer {SECRET_VALUE}")


def _fake_official_import(name):
    if name == "ssi_fc_data.fc_md_client":
        return SimpleNamespace(MarketDataClient=FakeOfficialClient, __file__="fake/fc_md_client.py")
    if name == "ssi_fc_data.fc_md_stream":
        return SimpleNamespace(MarketDataStream=FakeOfficialStream, __file__="fake/fc_md_stream.py")
    if name == "ssi_fc_data":
        return SimpleNamespace(__file__="fake/ssi_fc_data/__init__.py", __version__="0.test")
    raise ImportError(name)


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
    monkeypatch.delenv("SSI_STREAMING_REALTIME_CHANNEL_TEMPLATE", raising=False)


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
    assert payload["channels"] == ["X:FPT", "X:HPG"]
    assert "channel_format_warning" not in payload
    assert payload["script_cache_only"] is True
    assert payload["backend_cache_populated"] is False
    assert SECRET_VALUE not in output


def test_explicit_old_space_channel_template_override_is_respected_with_warning(monkeypatch, capsys):
    module = _load_script(monkeypatch)
    monkeypatch.setattr(module, "load_dotenv_if_available", lambda: None)
    _set_valid_env(monkeypatch)
    monkeypatch.setenv("SSI_STREAMING_REALTIME_CHANNEL_TEMPLATE", "X: {symbol}")

    code = module.main(["--symbols", "fpt,hpg", "--check-config-only"])
    payload, output = _last_json(capsys)

    assert code == 0
    assert payload["channels"] == ["X: FPT", "X: HPG"]
    assert payload["channel_format_warning"].startswith("SSI streaming channels with a space after ':'")
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

    code, payload = module.run_verification(
        symbols=["FPT"],
        config=module.load_config(module.build_arg_parser().parse_args([])),
        wait_seconds=0,
        poll_interval_seconds=0,
        manager_factory=manager_factory,
        sleep_func=lambda _: None,
        monotonic_func=lambda: 0.0,
    )
    output = capsys.readouterr().out

    assert code == 0
    assert FakeManager.instances[0].started_symbols == ["FPT"]
    assert FakeManager.instances[0].channels == ["X:FPT"]
    assert FakeManager.instances[0].parser.__name__ == "normalize_streaming_realtime_messages"
    assert FakeManager.instances[0].stop_calls == 1
    assert payload["quote_count"] == 1
    assert payload["diagnosis"] == "cache_hit"
    assert payload["symbols_with_quotes"] == ["FPT"]
    assert payload["script_cache_only"] is True
    assert payload["backend_cache_populated"] is False
    assert SECRET_VALUE not in output


def test_real_manager_factory_keeps_diagnostic_to_requested_x_context(monkeypatch):
    module = _load_script(monkeypatch)
    _set_valid_env(monkeypatch)
    config = module.load_config(module.build_arg_parser().parse_args([]))

    manager = module.make_manager(config=config, parser=lambda messages, symbols: [])

    assert manager.order_book_enabled is False
    assert manager.foreign_room_enabled is False
    assert manager.market_index_enabled is False
    assert manager.trade_tape_enabled is False
    assert manager.session_status_enabled is False


def test_verifier_instrumentation_forwards_generation_keyword(monkeypatch):
    module = _load_script(monkeypatch)
    _set_valid_env(monkeypatch)
    observed_generations = []

    class GenerationManager(FakeManager):
        def snapshot(self, symbols):
            if self.messages:
                self.handle_message(self.messages.pop(0), generation=7)
            return super().snapshot(symbols)

        def handle_message(self, message, *, generation=None):
            observed_generations.append(generation)
            return super().handle_message(message)

    def manager_factory(**kwargs):
        return GenerationManager(
            config=kwargs["config"],
            parser=kwargs["parser"],
            messages=[{"DataType": "X", "Content": {"Symbol": "FPT", "LastPrice": 100.0}}],
        )

    code, payload = module.run_verification(
        symbols=["FPT"],
        config=module.load_config(module.build_arg_parser().parse_args([])),
        wait_seconds=0,
        poll_interval_seconds=0,
        manager_factory=manager_factory,
        sleep_func=lambda _: None,
        monotonic_func=lambda: 0.0,
    )

    assert code == 0
    assert payload["callback_invoked_count"] == 1
    assert observed_generations == [7]


def test_no_message_case_classifies_no_message_after_start(monkeypatch):
    module = _load_script(monkeypatch)
    _set_valid_env(monkeypatch)

    def manager_factory(**kwargs):
        return FakeManager(config=kwargs["config"], parser=kwargs["parser"])

    code, payload = module.run_verification(
        symbols=["FPT"],
        config=module.load_config(module.build_arg_parser().parse_args([])),
        wait_seconds=0,
        poll_interval_seconds=0,
        manager_factory=manager_factory,
        sleep_func=lambda _: None,
        monotonic_func=lambda: 0.0,
    )

    assert code == 0
    assert payload["diagnosis"] == "no_message_after_start"
    assert payload["callback_invoked_count"] == 0
    assert payload["on_message_count"] == 0


def test_callback_called_parser_zero_rows_classification(monkeypatch):
    module = _load_script(monkeypatch)
    _set_valid_env(monkeypatch)

    def manager_factory(**kwargs):
        return FakeManager(config=kwargs["config"], parser=kwargs["parser"], messages=[{"DataType": "X", "Content": {"Symbol": "ZZZ"}}])

    code, payload = module.run_verification(
        symbols=["FPT"],
        config=module.load_config(module.build_arg_parser().parse_args([])),
        wait_seconds=0,
        poll_interval_seconds=0,
        manager_factory=manager_factory,
        sleep_func=lambda _: None,
        monotonic_func=lambda: 0.0,
    )

    assert code == 0
    assert payload["diagnosis"] == "callback_called_parser_zero_rows"
    assert payload["callback_invoked_count"] == 1
    assert payload["parser_zero_row_count"] == 1
    assert payload["parser_rows_total"] == 0


def test_on_error_callback_classifies_on_error_called(monkeypatch):
    module = _load_script(monkeypatch)
    _set_valid_env(monkeypatch)

    def manager_factory(**kwargs):
        return FakeManager(config=kwargs["config"], parser=kwargs["parser"], errors=["Authorization: Bearer " + SECRET_VALUE])

    code, payload = module.run_verification(
        symbols=["FPT"],
        config=module.load_config(module.build_arg_parser().parse_args([])),
        wait_seconds=0,
        poll_interval_seconds=0,
        manager_factory=manager_factory,
        sleep_func=lambda _: None,
        monotonic_func=lambda: 0.0,
    )

    assert code == 4
    assert payload["diagnosis"] == "on_error_called"
    assert payload["on_error_count"] == 1
    assert SECRET_VALUE not in json.dumps(payload)


def test_verbose_safe_samples_envelope_without_raw_content(monkeypatch):
    module = _load_script(monkeypatch)
    _set_valid_env(monkeypatch)
    raw_content = json.dumps({"RType": "X-TRADE", "Symbol": "FPT", "LastPrice": 100.0, "SecretLike": SECRET_VALUE})
    message = {"DataType": "X-TRADE", "Content": raw_content}

    def manager_factory(**kwargs):
        return FakeManager(config=kwargs["config"], parser=kwargs["parser"], messages=[message])

    config = module.load_config(module.build_arg_parser().parse_args([]))
    config["verbose_safe"] = True
    code, payload = module.run_verification(
        symbols=["FPT"],
        config=config,
        wait_seconds=0,
        poll_interval_seconds=0,
        manager_factory=manager_factory,
        sleep_func=lambda _: None,
        monotonic_func=lambda: 0.0,
    )
    encoded = json.dumps(payload)

    assert code == 0
    assert payload["diagnosis"] == "cache_hit"
    assert payload["message_type_samples"][:2] == ["X-TRADE"]
    assert payload["message_samples"][0]["content_type"] == "str"
    assert payload["message_samples"][0]["content_length"] == len(raw_content)
    assert "LastPrice" in payload["message_samples"][0]["content_keys"]
    assert SECRET_VALUE not in encoded
    assert raw_content not in encoded
    assert len(payload["diagnostic_events"]) <= 20


def test_sample_arrays_are_bounded(monkeypatch):
    module = _load_script(monkeypatch)
    diagnostics = module.VerificationDiagnostics(verbose_safe=True, max_samples=2, max_events=3)
    for index in range(5):
        diagnostics.record_message({"DataType": f"X-{index}", "Content": {"Symbol": f"F{index}", "RType": f"R{index}"}})
    summary = diagnostics.as_summary()
    assert len(summary["message_type_samples"]) == 2
    assert len(summary["message_samples"]) == 2
    assert len(summary["diagnostic_events"]) == 3


def test_multi_template_channel_discovery_returns_results(monkeypatch, capsys):
    module = _load_script(monkeypatch)
    monkeypatch.setattr(module, "load_dotenv_if_available", lambda: None)
    _set_valid_env(monkeypatch)
    calls = []

    def fake_run_verification(**kwargs):
        calls.append(kwargs["config"]["channel_template"])
        return 0, {
            "started": True,
            "manager_state": "running",
            "channels": [kwargs["config"]["channel_template"].format(symbol="FPT")],
            "messages_observed": 0,
            "parser_rows_observed": 0,
            "cache_status": "empty",
            "quote_count": 0,
            "symbols_with_quotes": [],
            "latest_error": None,
            "no_secrets_observed": True,
            "script_cache_only": True,
            "backend_cache_populated": False,
            "requested_symbols": ["FPT"],
            "callback_invoked_count": 0,
            "diagnosis": "no_message_after_start",
        }

    monkeypatch.setattr(module, "run_verification", fake_run_verification)
    code = module.main([
        "--symbols",
        "FPT",
        "--channel-templates",
        "X: {symbol};X-QUOTE: {symbol};X-TRADE: {symbol}",
    ])
    payload, _output = _last_json(capsys)

    assert code == 0
    assert payload["mode"] == "channel_discovery"
    assert calls == ["X: {symbol}", "X-QUOTE: {symbol}", "X-TRADE: {symbol}"]
    assert len(payload["results"]) == 3


def test_verbose_safe_output_is_single_json_object(monkeypatch, capsys):
    module = _load_script(monkeypatch)
    monkeypatch.setattr(module, "load_dotenv_if_available", lambda: None)
    _set_valid_env(monkeypatch)

    def fake_run_verification(**kwargs):
        return 0, {
            "started": True,
            "manager_state": "running",
            "channels": ["X:FPT"],
            "messages_observed": 0,
            "parser_rows_observed": 0,
            "cache_status": "empty",
            "quote_count": 0,
            "symbols_with_quotes": [],
            "latest_error": None,
            "no_secrets_observed": True,
            "script_cache_only": True,
            "backend_cache_populated": False,
            "requested_symbols": ["FPT"],
            "diagnosis": "no_message_after_start",
            "diagnostic_events": [{"event": "manager_status"}],
        }

    monkeypatch.setattr(module, "run_verification", fake_run_verification)
    code = module.main(["--symbols", "FPT", "--verbose-safe"])
    output = capsys.readouterr().out.strip().splitlines()
    assert code == 0
    assert len(output) == 1
    assert json.loads(output[0])["diagnostic_events"] == [{"event": "manager_status"}]


def test_check_config_only_check_package_does_not_start_manager(monkeypatch, capsys):
    module = _load_script(monkeypatch)
    monkeypatch.setattr(module, "load_dotenv_if_available", lambda: None)
    monkeypatch.setattr(module, "package_available", lambda: True)
    _set_valid_env(monkeypatch)

    def fail_manager_factory(**kwargs):  # pragma: no cover - should not be called
        raise AssertionError("manager must not be constructed in config-only mode")

    monkeypatch.setattr(module, "make_manager", fail_manager_factory)
    code = module.main(["--symbols", "FPT", "--check-config-only", "--check-package"])
    payload, output = _last_json(capsys)

    assert code == 0
    assert payload["package_available"] is True
    assert payload["stream_url_host"] == "fc-datahub.ssi.com.vn"
    assert payload["config"]["consumer_secret_present"] is True
    assert SECRET_VALUE not in output


def test_suppress_insecure_warning_only_targets_urllib3_warning(monkeypatch):
    module = _load_script(monkeypatch)
    calls = []

    class FakeInsecureWarning(Warning):
        pass

    monkeypatch.setitem(sys.modules, "urllib3.exceptions", type("M", (), {"InsecureRequestWarning": FakeInsecureWarning}))
    monkeypatch.setattr(module.warnings, "filterwarnings", lambda *args, **kwargs: calls.append((args, kwargs)))
    module.suppress_insecure_warning_if_requested(True)
    assert calls == [(("ignore",), {"category": FakeInsecureWarning})]


def test_inspect_package_source_does_not_require_credentials_or_start_stream(monkeypatch, capsys):
    module = _load_script(monkeypatch)
    monkeypatch.setattr(module, "load_dotenv_if_available", lambda: None)
    monkeypatch.setattr(module.importlib, "import_module", _fake_official_import)
    monkeypatch.setattr(module.importlib.metadata, "version", lambda name: "2.2.2")

    code = module.main(["--inspect-package-source"])
    payload, output = _last_json(capsys)

    assert code == 0
    assert payload["mode"] == "inspect_package_source"
    assert payload["package"]["module"] == "ssi_fc_data"
    assert payload["fc_md_stream"]["has_start"] is True
    assert "start" in payload["fc_md_stream"]["public_methods"]
    assert "Authorization" not in output
    assert SECRET_VALUE not in output
    assert FakeOfficialStream.instances == []


def test_direct_official_counts_message_and_captures_stdout(monkeypatch):
    module = _load_script(monkeypatch)
    _set_valid_env(monkeypatch)
    FakeOfficialStream.instances.clear()
    FakeOfficialStream.callback_mode = "message"
    FakeOfficialStream.print_secret = True

    config = module.load_config(module.build_arg_parser().parse_args([]))
    code, payload = module.run_direct_official(
        symbols=["FPT"],
        config=config,
        channels=["X: FPT"],
        wait_seconds=0,
        poll_interval_seconds=0,
        selected_channel_shape="string",
        import_module=_fake_official_import,
        sleep_func=lambda _: None,
        monotonic_func=lambda: 0.0,
    )
    encoded = json.dumps(payload)

    assert code == 0
    assert payload["diagnosis"] == "direct_callback_hit"
    assert payload["direct_on_message_count"] == 1
    assert payload["direct_on_error_count"] == 0
    assert payload["selected_channel_argument_type"] == "str"
    assert payload["selected_channel_argument_repr_safe"] == "X: FPT"
    assert payload["stdout_captured"] is True
    assert payload["captured_output_secret_like_detected"] is True
    assert payload["raw_stdout_printed"] is False
    assert FakeOfficialStream.instances[0].transport.stop_calls == 1
    assert SECRET_VALUE not in encoded
    assert "\"LastPrice\": 100.0" not in encoded


def test_direct_official_counts_on_error(monkeypatch):
    module = _load_script(monkeypatch)
    _set_valid_env(monkeypatch)
    FakeOfficialStream.instances.clear()
    FakeOfficialStream.callback_mode = "error"

    config = module.load_config(module.build_arg_parser().parse_args([]))
    code, payload = module.run_direct_official(
        symbols=["FPT"],
        config=config,
        channels=["X: FPT"],
        wait_seconds=0,
        poll_interval_seconds=0,
        selected_channel_shape="string",
        import_module=_fake_official_import,
        sleep_func=lambda _: None,
        monotonic_func=lambda: 0.0,
    )

    assert code == 4
    assert payload["diagnosis"] == "direct_on_error_called"
    assert payload["direct_on_error_count"] == 1
    assert "<redacted>" in payload["latest_error"]
    assert SECRET_VALUE not in json.dumps(payload)


def test_direct_official_start_failed_is_sanitized(monkeypatch):
    module = _load_script(monkeypatch)
    _set_valid_env(monkeypatch)
    FakeOfficialStream.instances.clear()
    FakeOfficialStream.callback_mode = "raise"

    config = module.load_config(module.build_arg_parser().parse_args([]))
    code, payload = module.run_direct_official(
        symbols=["FPT"],
        config=config,
        channels=["X: FPT"],
        wait_seconds=0,
        poll_interval_seconds=0,
        selected_channel_shape="string",
        import_module=_fake_official_import,
        sleep_func=lambda _: None,
        monotonic_func=lambda: 0.0,
    )

    assert code == 4
    assert payload["diagnosis"] == "direct_start_failed"
    assert payload["started"] is False
    assert SECRET_VALUE not in json.dumps(payload)


def test_direct_official_selected_channel_shapes(monkeypatch):
    module = _load_script(monkeypatch)
    assert module.build_selected_channel(["X:FPT"], "string") == "X:FPT"
    assert module.build_selected_channel(["X:FPT", "X:HPG"], "comma") == "X:FPT,X:HPG"
    assert module.build_selected_channel(["X:FPT", "X:HPG"], "list") == ["X:FPT", "X:HPG"]
    with pytest.raises(ValueError):
        module.build_selected_channel(["X: ALL"], "string")


def test_channel_format_variants_are_symbol_scoped(monkeypatch):
    module = _load_script(monkeypatch)
    variants = module.channel_format_variant_templates()
    assert variants == [
        "X: {symbol}",
        "X:{symbol}",
        "X-QUOTE: {symbol}",
        "X-QUOTE:{symbol}",
        "X-TRADE: {symbol}",
        "X-TRADE:{symbol}",
    ]
    assert all("ALL" not in variant for variant in variants)


def test_direct_channel_discovery_runs_sequentially(monkeypatch, capsys):
    module = _load_script(monkeypatch)
    monkeypatch.setattr(module, "load_dotenv_if_available", lambda: None)
    _set_valid_env(monkeypatch)
    calls = []

    def fake_run_direct(**kwargs):
        calls.append(kwargs["channels"][0])
        return 0, {
            "mode": "direct_official",
            "diagnosis": "direct_no_message_after_start",
            "started": True,
            "channels": kwargs["channels"],
            "direct_on_message_count": 0,
            "direct_on_error_count": 0,
            "no_secrets_observed": True,
            "script_cache_only": True,
            "backend_cache_populated": False,
        }

    monkeypatch.setattr(module, "run_direct_official", fake_run_direct)
    code = module.main([
        "--direct-official",
        "--symbols",
        "FPT",
        "--channel-format-variants",
        "--check-config-only",
    ])
    payload, _output = _last_json(capsys)
    assert code == 0
    assert payload["mode"] == "direct_official_channel_discovery"
    assert len(payload["results"]) == 6

    code = module.main([
        "--direct-official",
        "--symbols",
        "FPT",
        "--channel-format-variants",
        "--wait-seconds",
        "0",
    ])
    payload, _output = _last_json(capsys)
    assert code == 0
    assert calls == ["X: FPT", "X:FPT", "X-QUOTE: FPT", "X-QUOTE:FPT", "X-TRADE: FPT", "X-TRADE:FPT"]
    assert len(payload["results"]) == 6


def test_direct_mode_package_unavailable(monkeypatch):
    module = _load_script(monkeypatch)
    _set_valid_env(monkeypatch)
    config = module.load_config(module.build_arg_parser().parse_args([]))
    code, payload = module.run_direct_official(
        symbols=["FPT"],
        config=config,
        channels=["X: FPT"],
        wait_seconds=0,
        poll_interval_seconds=0,
        selected_channel_shape="string",
        import_module=lambda name: (_ for _ in ()).throw(ImportError("missing package")),
        sleep_func=lambda _: None,
        monotonic_func=lambda: 0.0,
    )
    assert code == 4
    assert payload["diagnosis"] == "package_unavailable"


def test_start_failure_sanitizes_secret_and_returns_manager_error(monkeypatch, capsys):
    module = _load_script(monkeypatch)
    _set_valid_env(monkeypatch)
    FakeManager.instances.clear()

    def manager_factory(**kwargs):
        return FakeManager(config=kwargs["config"], parser=kwargs["parser"], fail_start=True)

    code, payload = module.run_verification(
        symbols=["FPT"],
        config=module.load_config(module.build_arg_parser().parse_args([])),
        wait_seconds=0,
        poll_interval_seconds=0,
        manager_factory=manager_factory,
        sleep_func=lambda _: None,
        monotonic_func=lambda: 0.0,
    )
    output = capsys.readouterr().out

    assert code == 4
    assert payload["started"] is False
    assert "<redacted>" in payload["latest_error"]
    assert payload["diagnosis"] == "manager_start_failed"
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
