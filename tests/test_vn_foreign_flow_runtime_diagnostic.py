"""Offline tests for the bounded Foreign Flow application diagnostic."""

from __future__ import annotations

from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import threading
import time

from scripts import diagnose_vn_foreign_flow_runtime as diagnostic


class _Process:
    pid = 1234

    def poll(self):
        return None


class _Capture:
    def tail(self) -> list[str]:
        return []


def _serve_health(status: str) -> tuple[ThreadingHTTPServer, threading.Thread]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            payload = json.dumps({"status": status}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_child_command_uses_exact_python_and_explicit_loopback_port() -> None:
    command = diagnostic._child_command(43123)

    assert command == [
        diagnostic.sys.executable,
        "main.py",
        "--serve-only",
        "--host",
        "127.0.0.1",
        "--port",
        "43123",
    ]


def test_child_environment_removes_inherited_bind_variables(monkeypatch) -> None:
    monkeypatch.setenv("PORT", "8000")
    monkeypatch.setenv("host", "0.0.0.0")
    monkeypatch.setenv("WEBUI_PORT", "9000")
    monkeypatch.setenv("WebUi_Host", "::")

    environment = diagnostic._deduplicated_environment()
    lowered = {name.lower() for name in environment}

    assert lowered.isdisjoint({"port", "host", "webui_port", "webui_host"})
    assert environment["SSI_STREAMING_REALTIME_ENABLED"] == "false"
    assert environment["SSI_V3_MAX_RETRIES"] == "0"


def test_readiness_requires_http_200_and_status_ok(capsys) -> None:
    assert diagnostic.READINESS_SECONDS == 45.0
    server, thread = _serve_health("ok")
    try:
        assert diagnostic._wait_until_ready(
            port=server.server_port,
            deadline=time.monotonic() + 30,
            process=_Process(),
            stdout_capture=_Capture(),
            stderr_capture=_Capture(),
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)

    line = json.loads(capsys.readouterr().out)
    assert line["mode"] == "health"
    assert line["method"] == "GET"
    assert line["status"] == "ok"
    assert line["http_status"] == 200


def test_readiness_rejects_non_ok_health_and_reports_exact_probe(
    monkeypatch,
    capsys,
) -> None:
    server, thread = _serve_health("starting")
    monkeypatch.setattr(diagnostic, "READINESS_SECONDS", 0.05)
    monkeypatch.setattr(diagnostic, "READINESS_POLL_SECONDS", 0.005)
    try:
        assert not diagnostic._wait_until_ready(
            port=server.server_port,
            deadline=time.monotonic() + 10,
            process=_Process(),
            stdout_capture=_Capture(),
            stderr_capture=_Capture(),
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)

    line = json.loads(capsys.readouterr().out)
    assert line["failure_class"] == "readiness_timeout"
    assert line["last_error_class"] == "health_not_ok"
    assert line["probe_url"] == (
        f"http://127.0.0.1:{server.server_port}/api/health"
    )


def test_bounded_log_capture_redacts_and_retains_bounded_tail(tmp_path: Path) -> None:
    path = tmp_path / "child.log"
    capture = diagnostic._BoundedLogCapture(path, max_bytes=80)
    stream = io.BytesIO(
        b"old line\n"
        + (b"x" * 100)
        + b"\napi_secret=do-not-print\nlast line\n"
    )

    capture.start(stream)
    capture.join()

    assert path.stat().st_size <= 80
    rendered = repr(capture.tail())
    assert "do-not-print" not in rendered
    assert "[REDACTED]" in rendered
    assert "last line" in rendered


def test_completed_session_and_routes_use_explicit_provider_date() -> None:
    selected = diagnostic._completed_session(
        "2026-07-24",
        now=datetime(2026, 7, 27, 9, 0),
    )
    routes = diagnostic._routes(selected)

    assert selected == date(2026, 7, 24)
    assert len(routes) == 6
    assert [route[0] for route in routes] == [
        "ticker",
        "vn30",
        "industry",
        "proprietary",
        "watchlist",
        "vn30_direct",
    ]
    proprietary = next(route for route in routes if route[0] == "proprietary")
    assert "from_date=2026-07-24" in proprietary[1]
    assert "to_date=2026-07-24" in proprietary[1]
    industry = next(route for route in routes if route[0] == "industry")
    assert industry[2] == "POST"
    assert industry[3]["to_date"] == "2026-07-24"


def test_current_acceptance_routes_cover_symbol_and_vn30_industry() -> None:
    routes = diagnostic._current_acceptance_routes()
    assert [route[0] for route in routes] == ["current_symbol", "current_industry"]
    assert "/foreign-flow/current/FPT?" in routes[0][1]
    assert "scope=vn30" in routes[1][1]
    assert "include_industries=true" in routes[1][1]
    assert "force_refresh=false" in routes[0][1]

    refreshed = diagnostic._current_acceptance_routes(force_refresh=True)
    assert "force_refresh=true" in refreshed[0][1]
    assert "recovery_trigger=manual_refresh" in refreshed[1][1]


def test_provider_observed_session_takes_precedence_over_explicit_fallback() -> None:
    selected, basis, latest = diagnostic._select_observed_session(
        date(2026, 7, 24),
        [
            {"latest_session": "2026-07-24"},
            {"latest_session": "2026-07-27"},
        ],
        explicit_fallback=True,
    )

    assert selected == date(2026, 7, 27)
    assert basis == "latest_completed_provider_session_observed"
    assert latest == "2026-07-27"


def test_summary_emits_industry_proprietary_and_watchlist_acceptance_counts() -> None:
    industry = diagnostic._summary(
        mode="industry",
        method="POST",
        path="/industry",
        http_status=200,
        payload={
            "status": "partial",
            "data_state": "partial",
            "usable": True,
            "requested_symbol_count": 30,
            "classified_symbol_count": 28,
            "rows": [
                {"icb_code": "1000"},
                {"icb_code": "2000"},
                {"icb_code": "2000"},
            ],
        },
        elapsed_ms=1,
    )
    proprietary = diagnostic._summary(
        mode="proprietary",
        method="GET",
        path="/proprietary",
        http_status=200,
        payload={
            "status": "ok",
            "requested_to_date": "2026-07-24",
            "rows": [
                {
                    "trading_date": "2026-07-24",
                    "proprietary_buy_volume": 10,
                    "proprietary_sell_volume": 5,
                    "proprietary_net_volume": 5,
                    "proprietary_buy_value": 100,
                    "proprietary_sell_value": 50,
                    "proprietary_net_value": 50,
                }
            ],
        },
        elapsed_ms=1,
    )
    watchlist = diagnostic._summary(
        mode="watchlist",
        method="GET",
        path="/watchlist",
        http_status=200,
        payload={
            "status": "partial",
            "ready_symbol_count": 1,
            "partial_symbol_count": 1,
            "unavailable_symbol_count": 1,
            "items": [{}, {}, {}],
        },
        elapsed_ms=1,
    )

    assert industry["industry_count"] == 2
    assert industry["member_count"] == 30
    assert industry["covered_member_count"] == 28
    assert proprietary["row_count"] == 1
    assert proprietary["selected_session"] == "2026-07-24"
    assert proprietary["proprietary_field_count"] == 6
    assert proprietary["required_fields_present"] == list(
        diagnostic._PROPRIETARY_FIELDS
    )
    assert watchlist["item_count"] == 3
    assert watchlist["ready_count"] == 1
    assert watchlist["partial_count"] == 1
    assert watchlist["unavailable_count"] == 1


def test_summary_sanitizes_current_symbol_and_aggregate_evidence() -> None:
    symbol = diagnostic._summary(
        mode="current_symbol",
        method="GET",
        path="/current/FPT",
        http_status=200,
        payload={
            "status": "ok",
            "data_state": "ready",
            "usable": True,
            "trading_date": "2026-08-10",
            "current": {
                "foreign_buy_volume": 100,
                "foreign_sell_volume": 40,
                "foreign_buy_value": 1_000,
                "foreign_sell_value": 300,
                "stream_timestamp": "2026/08/10 10:30:00",
                "received_at": "2026-08-10T03:30:01+00:00",
                "raw_payload": "must-not-be-emitted",
            },
            "diagnostics": {
                "subscription_count": 2,
                "foreign_room_subscription_count": 1,
                "foreign_room_rows_observed": 3,
            },
        },
        elapsed_ms=1,
    )
    aggregate = diagnostic._summary(
        mode="current_industry",
        method="GET",
        path="/current-aggregate",
        http_status=200,
        payload={
            "status": "partial",
            "data_state": "partial",
            "usable": True,
            "provider_session_date": "2026-08-10",
            "aggregate": {"foreign_buy_value": 30, "foreign_sell_value": 10},
            "items": [
                {"foreign_buy_value": 20, "foreign_sell_value": 5},
                {"foreign_buy_value": 10, "foreign_sell_value": 5},
            ],
            "groups": [
                {"provider_session_date": "2026-08-10", "foreign_buy_value": 30, "foreign_sell_value": 10}
            ],
            "coverage": {
                "requested_symbol_count": 30,
                "classified_symbol_count": 30,
                "observed_symbol_count": 2,
                "complete_value_count": 2,
                "complete_volume_count": 0,
                "missing_symbols": ["ACB"],
                "stale_symbol_count": 0,
            },
        },
        elapsed_ms=1,
    )

    assert symbol["row_count"] == 1
    assert symbol["current"] == {
        "foreign_buy_volume": 100,
        "foreign_sell_volume": 40,
        "foreign_buy_value": 1_000,
        "foreign_sell_value": 300,
    }
    assert "raw_payload" not in symbol["current"]
    assert symbol["foreign_room_rows_observed"] == 3
    assert aggregate["items_reconcile"] is True
    assert aggregate["groups_reconcile"] is True
    assert aggregate["observed_symbol_count"] == 2


def test_creation_flags_are_safe_for_current_platform() -> None:
    expected = diagnostic.subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    assert diagnostic._creation_flags() == expected
