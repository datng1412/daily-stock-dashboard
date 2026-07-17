"""Deterministic HTTP-readiness coverage for the normal backend launcher."""

from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

import api.app as app_module
import main


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


class _FailingServer(_ReadyServer):
    def run(self):
        self.run_calls += 1
        raise RuntimeError("bind failed")


def _config():
    return SimpleNamespace(log_level="INFO")


def test_normal_launcher_starts_expected_app_once_and_waits_for_readiness(monkeypatch):
    captured = {}
    _ReadyServer.instances = []

    class FakeConfig:
        def __init__(self, app, **kwargs):
            captured["app"] = app
            captured.update(kwargs)

    monkeypatch.setattr("uvicorn.Config", FakeConfig)
    monkeypatch.setattr("uvicorn.Server", _ReadyServer)

    thread = main.start_api_server("127.0.0.1", 8123, _config())

    server = _ReadyServer.instances[0]
    thread.join(timeout=1)
    assert captured["app"] == "api.app:app"
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8123
    assert captured["reload"] is False
    assert captured["workers"] == 1
    assert server.run_calls == 1
    assert server.started is True
    assert thread.name == "stockclock-fastapi-server"


def test_normal_launcher_propagates_background_startup_failure(monkeypatch):
    _FailingServer.instances = []
    monkeypatch.setattr("uvicorn.Config", lambda *args, **kwargs: object())
    monkeypatch.setattr("uvicorn.Server", _FailingServer)

    with pytest.raises(RuntimeError, match="failed before HTTP readiness") as exc_info:
        main.start_api_server("127.0.0.1", 8123, _config())

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert _FailingServer.instances[0].run_calls == 1


def test_normal_launcher_times_out_without_claiming_readiness(monkeypatch):
    release = threading.Event()

    class BlockingServer(_ReadyServer):
        def run(self):
            self.run_calls += 1
            release.wait(timeout=1)

    BlockingServer.instances = []
    monkeypatch.setattr("uvicorn.Config", lambda *args, **kwargs: object())
    monkeypatch.setattr("uvicorn.Server", BlockingServer)
    monkeypatch.setattr(main, "_API_SERVER_STARTUP_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(main, "_API_SERVER_SHUTDOWN_GRACE_SECONDS", 0.05)

    try:
        with pytest.raises(RuntimeError, match="did not become HTTP-ready"):
            main.start_api_server("127.0.0.1", 8123, _config())
        assert BlockingServer.instances[0].should_exit is True
    finally:
        release.set()


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
    app = app_module.create_app(static_dir=tmp_path / "static")

    try:
        with TestClient(app) as client:
            assert entered.wait(timeout=1)
            assert app.state.ssi_streaming_realtime_bootstrap_status == {"bootstrap_status": "scheduled"}
            assert client.get("/api/health").status_code == 200
            assert client.get("/api/v1/stocks/vn/observability").status_code == 200
            assert client.get("/api/v1/stocks/vn/intraday-chart/health").status_code == 200
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
