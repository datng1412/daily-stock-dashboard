"""Deterministic HTTP-readiness coverage for the normal backend launcher."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

import api.app as app_module
import main
from src.startup_trace import get_startup_stages, reset_startup_trace


class _ReadyServer:
    instances = []

    def __init__(self, config):
        self.config = config
        self.started = False
        self.should_exit = False
        self.run_calls = 0
        type(self).instances.append(self)

    def run(self):
        self.run_calls += 1
        self.started = True
        while not self.should_exit:
            time.sleep(0.001)


class _FailingServer(_ReadyServer):
    def run(self):
        self.run_calls += 1
        raise RuntimeError("bind failed")


def _config():
    return SimpleNamespace(log_level="INFO")


def test_normal_launcher_starts_expected_app_once_and_waits_for_readiness(monkeypatch):
    captured = {}
    expected_app = object()
    _ReadyServer.instances = []

    class FakeConfig:
        def __init__(self, app, **kwargs):
            captured["app"] = app
            captured.update(kwargs)

    monkeypatch.setattr("uvicorn.Config", FakeConfig)
    monkeypatch.setattr("uvicorn.Server", _ReadyServer)
    monkeypatch.setattr(main, "_load_fastapi_app", lambda: expected_app)
    monkeypatch.setattr(main, "_probe_api_health", lambda port: "HEALTH_RESPONSE_READY")

    thread = main.start_api_server("127.0.0.1", 8123, _config())

    server = _ReadyServer.instances[0]
    assert captured["app"] is expected_app
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8123
    assert captured["reload"] is False
    assert captured["workers"] == 1
    assert server.run_calls == 1
    assert server.started is True
    assert thread.name == "stockclock-fastapi-server"
    assert get_startup_stages() == (
        "FASTAPI_THREAD_ENTERED",
        "FASTAPI_APP_IMPORT_START",
        "FASTAPI_APP_IMPORT_COMPLETE",
        "UVICORN_CONFIG_CREATED",
        "UVICORN_RUN_ENTERED",
        "UVICORN_SOCKET_READY",
    )
    assert main.stop_api_server(thread) is True
    assert not thread.is_alive()


def test_normal_launcher_propagates_background_startup_failure(monkeypatch):
    _FailingServer.instances = []
    monkeypatch.setattr("uvicorn.Config", lambda *args, **kwargs: object())
    monkeypatch.setattr("uvicorn.Server", _FailingServer)
    monkeypatch.setattr(main, "_load_fastapi_app", object)

    with pytest.raises(RuntimeError, match="state=CHILD_EXITED") as exc_info:
        main.start_api_server("127.0.0.1", 8123, _config())

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert "exit_code=not_applicable_in_process_thread" in str(exc_info.value)
    assert "host=127.0.0.1 port=8123" in str(exc_info.value)
    assert "diagnostic_tail=RuntimeError: bind failed" in str(exc_info.value)
    assert _FailingServer.instances[0].run_calls == 1


def test_normal_launcher_times_out_without_claiming_readiness(monkeypatch):
    class BlockingServer(_ReadyServer):
        def run(self):
            self.run_calls += 1
            while not self.should_exit:
                time.sleep(0.001)

    BlockingServer.instances = []
    monkeypatch.setattr("uvicorn.Config", lambda *args, **kwargs: object())
    monkeypatch.setattr("uvicorn.Server", BlockingServer)
    monkeypatch.setattr(main, "_load_fastapi_app", object)
    monkeypatch.setattr(main, "_probe_api_health", lambda port: "CONNECTION_REFUSED")
    monkeypatch.setattr(main, "_API_SERVER_STARTUP_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(main, "_API_SERVER_SHUTDOWN_GRACE_SECONDS", 0.05)

    with pytest.raises(RuntimeError, match="last_lifecycle_stage=UVICORN_RUN_ENTERED"):
        main.start_api_server("127.0.0.1", 8123, _config())
    assert BlockingServer.instances[0].should_exit is True
    assert not any(
        thread.name == "stockclock-fastapi-server" and thread.is_alive()
        for thread in threading.enumerate()
    )


def test_blocked_app_import_timeout_reports_exact_lifecycle_stage(monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    def blocked_import():
        entered.set()
        release.wait(timeout=1)
        raise RuntimeError("released blocked import")

    monkeypatch.setattr(main, "_load_fastapi_app", blocked_import)
    monkeypatch.setattr(main, "_probe_api_health", lambda port: "CONNECTION_REFUSED")
    monkeypatch.setattr(main, "_API_SERVER_STARTUP_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(main, "_API_SERVER_SHUTDOWN_GRACE_SECONDS", 0.01)

    try:
        with pytest.raises(RuntimeError, match="last_lifecycle_stage=FASTAPI_APP_IMPORT_START"):
            main.start_api_server("127.0.0.1", 8123, _config())
        assert entered.is_set()
    finally:
        release.set()
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline and any(
            thread.name == "stockclock-fastapi-server" and thread.is_alive()
            for thread in threading.enumerate()
        ):
            time.sleep(0.005)

    assert not any(
        thread.name == "stockclock-fastapi-server" and thread.is_alive()
        for thread in threading.enumerate()
    )


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ({}, 8000),
        ({"PORT": "10000"}, 10000),
        ({"WEBUI_PORT": "8123"}, 8123),
    ],
)
def test_port_resolution_uses_one_validated_source(environment, expected):
    assert main.resolve_api_server_port(environ=environment) == expected


@pytest.mark.parametrize("value", ["", "not-a-port", "0", "65536", "-1"])
def test_explicit_invalid_render_port_fails_clearly(value):
    with pytest.raises(ValueError, match="PORT must"):
        main.resolve_api_server_port(environ={"PORT": value})


def test_render_port_takes_precedence_over_cli_port():
    assert main.resolve_api_server_port(9000, {"PORT": "10000"}) == 10000


def test_readiness_retries_connection_refusal_and_uses_bound_port(monkeypatch):
    _ReadyServer.instances = []
    states = iter(["CONNECTION_REFUSED", "HEALTH_RESPONSE_READY"])
    probed_ports = []

    def probe(port):
        probed_ports.append(port)
        return next(states)

    monkeypatch.setattr("uvicorn.Config", lambda *args, **kwargs: object())
    monkeypatch.setattr("uvicorn.Server", _ReadyServer)
    monkeypatch.setattr(main, "_load_fastapi_app", object)
    monkeypatch.setattr(main, "_probe_api_health", probe)

    thread = main.start_api_server("0.0.0.0", 10000, _config())
    assert probed_ports == [10000, 10000]
    assert main._api_readiness_url(10000) == "http://127.0.0.1:10000/api/health"
    _ReadyServer.instances[0].should_exit = True
    thread.join(timeout=1)


def test_readiness_retries_non_ready_health_response(monkeypatch):
    _ReadyServer.instances = []
    states = iter(["HEALTH_RESPONSE_NOT_READY", "HEALTH_RESPONSE_READY"])
    monkeypatch.setattr("uvicorn.Config", lambda *args, **kwargs: object())
    monkeypatch.setattr("uvicorn.Server", _ReadyServer)
    monkeypatch.setattr(main, "_load_fastapi_app", object)
    monkeypatch.setattr(main, "_probe_api_health", lambda port: next(states))

    thread = main.start_api_server("0.0.0.0", 10000, _config())
    _ReadyServer.instances[0].should_exit = True
    thread.join(timeout=1)


def test_startup_diagnostic_is_bounded_and_redacts_secrets():
    diagnostic = main._bounded_startup_diagnostic(
        RuntimeError("prefix " + ("x" * 5000) + " apiSecret=do-not-print")
    )
    assert len(diagnostic) <= 4000
    assert "do-not-print" not in diagnostic
    assert "[REDACTED]" in diagnostic


def test_cold_app_import_completes_without_loading_optional_litellm():
    environment = os.environ.copy()
    environment.pop("LITELLM_LOCAL_MODEL_COST_MAP", None)
    environment.pop("LITELLM_LOCAL_ANTHROPIC_BETA_HEADERS", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import api.app; "
                "print('litellm' in sys.modules)"
            ),
        ],
        cwd=os.fspath(Path(__file__).resolve().parents[1]),
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    assert result.stdout.splitlines() == ["False"]


def test_required_system_config_initializer_failure_is_named(monkeypatch, tmp_path):
    class RequiredInitFailure(RuntimeError):
        pass

    def fail_system_config():
        raise RequiredInitFailure("local initialization failed")

    monkeypatch.setattr(app_module, "SystemConfigService", fail_system_config)
    reset_startup_trace()
    app = app_module.create_app(static_dir=tmp_path / "static")

    async def exercise():
        async with app_module.app_lifespan(app):
            pass

    with pytest.raises(RequiredInitFailure, match="local initialization failed"):
        asyncio.run(exercise())
    assert get_startup_stages() == (
        "LIFESPAN_START_ENTERED",
        "SYSTEM_CONFIG_INIT_START",
    )


def test_serve_only_returns_failure_instead_of_sleeping_after_server_error(monkeypatch):
    args = SimpleNamespace(
        debug=False,
        check_notify=False,
        stocks=None,
        webui=False,
        webui_only=False,
        serve=False,
        serve_only=True,
        host="127.0.0.1",
        port=8000,
    )
    config = SimpleNamespace(
        log_dir="logs",
        log_level="INFO",
        webui_enabled=False,
        validate=lambda: [],
    )
    monkeypatch.setattr(main, "parse_arguments", lambda: args)
    monkeypatch.setattr(main, "get_config", lambda: config)
    monkeypatch.setattr(main, "_setup_bootstrap_logging", lambda **kwargs: None)
    monkeypatch.setattr(main, "_setup_runtime_logging", lambda *args, **kwargs: True)
    monkeypatch.setattr(main, "prepare_webui_frontend_assets", lambda: True)
    monkeypatch.setattr(
        main,
        "start_api_server",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("startup failed")),
    )

    assert main.main() == 1


def test_render_port_forces_external_bind_and_reaches_server_launcher(monkeypatch):
    args = SimpleNamespace(
        debug=False,
        check_notify=False,
        stocks=None,
        webui=False,
        webui_only=False,
        serve=False,
        serve_only=True,
        host="127.0.0.1",
        port=9000,
    )
    config = SimpleNamespace(
        log_dir="logs",
        log_level="INFO",
        webui_enabled=False,
        validate=lambda: [],
    )
    captured = {}

    def capture_start(**kwargs):
        captured.update(kwargs)
        raise RuntimeError("stop after bind capture")

    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("WEBUI_HOST", "127.0.0.1")
    monkeypatch.setattr(main, "parse_arguments", lambda: args)
    monkeypatch.setattr(main, "get_config", lambda: config)
    monkeypatch.setattr(main, "_setup_bootstrap_logging", lambda **kwargs: None)
    monkeypatch.setattr(main, "_setup_runtime_logging", lambda *args, **kwargs: True)
    monkeypatch.setattr(main, "prepare_webui_frontend_assets", lambda: True)
    monkeypatch.setattr(main, "start_api_server", capture_start)

    assert main.main() == 1
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 10000


def test_invalid_render_port_fails_before_server_launch(monkeypatch):
    args = SimpleNamespace(
        debug=False,
        check_notify=False,
        stocks=None,
        webui=False,
        webui_only=False,
        serve=False,
        serve_only=True,
        host="0.0.0.0",
        port=8000,
    )
    config = SimpleNamespace(
        log_dir="logs",
        log_level="INFO",
        webui_enabled=False,
        validate=lambda: [],
    )
    launch_calls = []
    monkeypatch.setenv("PORT", "invalid")
    monkeypatch.setattr(main, "parse_arguments", lambda: args)
    monkeypatch.setattr(main, "get_config", lambda: config)
    monkeypatch.setattr(main, "_setup_bootstrap_logging", lambda **kwargs: None)
    monkeypatch.setattr(main, "_setup_runtime_logging", lambda *args, **kwargs: True)
    monkeypatch.setattr(main, "start_api_server", lambda **kwargs: launch_calls.append(kwargs))

    assert main.main() == 1
    assert launch_calls == []


@pytest.mark.parametrize(
    "outcome",
    [
        {"bootstrap_status": "running", "manager_state": "running"},
        {"bootstrap_status": "running", "manager_state": "connecting"},
        RuntimeError("401 Unauthorized"),
        RuntimeError("network unavailable"),
    ],
    ids=["immediate", "no-event", "authorization", "network-failure"],
)
def test_http_routes_are_ready_independently_of_stream_outcome(monkeypatch, tmp_path, outcome):
    monkeypatch.setattr(app_module, "_schedule_stock_index_background_refresh", lambda app, reason: None)
    monkeypatch.setattr(app_module, "shutdown_ssi_streaming_realtime", lambda: {"bootstrap_status": "stopped"})

    def bootstrap():
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(app_module, "bootstrap_ssi_streaming_realtime", bootstrap)
    app = app_module.create_app(static_dir=tmp_path / "static")

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        observability = client.get("/api/v1/stocks/vn/observability")
        assert observability.status_code == 200
        assert observability.headers["Cache-Control"] == "no-store"
        for _ in range(100):
            if app.state.ssi_streaming_realtime_bootstrap_task.done():
                break
            time.sleep(0.005)
        assert app.state.ssi_streaming_realtime_bootstrap_task.done()
        status = app.state.ssi_streaming_realtime_bootstrap_status
        if isinstance(outcome, Exception):
            assert status["bootstrap_status"] == "bootstrap_error"
        else:
            assert status == outcome


def test_http_routes_are_ready_while_stream_start_is_blocked(monkeypatch, tmp_path):
    entered = threading.Event()
    release = threading.Event()
    shutdown_calls = []

    def blocking_bootstrap():
        entered.set()
        assert release.wait(timeout=2)
        return {"bootstrap_status": "running", "manager_state": "running"}

    monkeypatch.setattr(app_module, "_schedule_stock_index_background_refresh", lambda app, reason: None)
    monkeypatch.setattr(app_module, "bootstrap_ssi_streaming_realtime", blocking_bootstrap)
    monkeypatch.setattr(
        app_module,
        "shutdown_ssi_streaming_realtime",
        lambda: shutdown_calls.append("shutdown") or {"bootstrap_status": "stopped"},
    )
    reset_startup_trace()
    app = app_module.create_app(static_dir=tmp_path / "static")

    try:
        with TestClient(app) as client:
            assert entered.wait(timeout=1)
            assert app.state.ssi_streaming_realtime_bootstrap_status == {"bootstrap_status": "scheduled"}
            assert client.get("/api/health").status_code == 200
            assert client.get("/api/v1/stocks/vn/observability").status_code == 200
            assert client.get("/api/v1/stocks/vn/intraday-chart/health").status_code == 200
            assert get_startup_stages() == (
                "LIFESPAN_START_ENTERED",
                "SYSTEM_CONFIG_INIT_START",
                "SYSTEM_CONFIG_INIT_COMPLETE",
                "STOCK_INDEX_BACKGROUND_INIT_START",
                "STOCK_INDEX_BACKGROUND_INIT_COMPLETE",
                "SSI_STREAMING_BACKGROUND_INIT_START",
                "SSI_STREAMING_BACKGROUND_INIT_COMPLETE",
                "LIFESPAN_START_COMPLETE",
            )
            release.set()
    finally:
        release.set()

    assert shutdown_calls == ["shutdown"]


def test_lifespan_schedules_only_one_stream_bootstrap(monkeypatch):
    calls = []
    release = threading.Event()

    def bootstrap():
        calls.append("bootstrap")
        release.wait(timeout=1)
        return {"bootstrap_status": "running"}

    monkeypatch.setattr(app_module, "_schedule_stock_index_background_refresh", lambda app, reason: None)
    monkeypatch.setattr(app_module, "bootstrap_ssi_streaming_realtime", bootstrap)
    monkeypatch.setattr(app_module, "shutdown_ssi_streaming_realtime", lambda: {"bootstrap_status": "stopped"})

    async def exercise():
        app = app_module.create_app()
        async with app_module.app_lifespan(app):
            app_module._schedule_ssi_streaming_realtime_bootstrap(app)
            for _ in range(100):
                if calls:
                    break
                await asyncio.sleep(0.005)
            assert calls == ["bootstrap"]
            release.set()

    try:
        asyncio.run(exercise())
    finally:
        release.set()
