"""Run one bounded, sanitized Foreign Flow runtime diagnostic.

This manual script intentionally owns the backend child process directly. It
prints only normalized contract metadata and never prints response bodies,
headers, credentials, or provider payloads.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from datetime import date, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / ".tmp"
READINESS_SECONDS = 45.0
REQUEST_SECONDS = 15.0
GLOBAL_SECONDS = 120.0
CLEANUP_RESERVE_SECONDS = 8.0
MAX_BODY_BYTES = 1_000_000


def _emit(**values: Any) -> None:
    print(json.dumps(values, separators=(",", ":"), sort_keys=True), flush=True)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _deduplicated_environment(port: int) -> dict[str, str]:
    by_lower_name: dict[str, tuple[str, str]] = {}
    for name, value in os.environ.items():
        by_lower_name[name.lower()] = (name, value)
    environment = {name: value for name, value in by_lower_name.values()}
    environment["PORT"] = str(port)
    environment["SSI_STREAMING_REALTIME_ENABLED"] = "false"
    environment["PYTHONUTF8"] = "1"
    return environment


def _read_json(response: Any) -> dict[str, Any]:
    raw = response.read(MAX_BODY_BYTES)
    parsed = json.loads(raw.decode("utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def _last_row(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows")
    if isinstance(rows, list) and rows and isinstance(rows[-1], dict):
        return rows[-1]
    return {}


def _summary(
    *,
    mode: str,
    path: str,
    http_status: int | None,
    payload: dict[str, Any],
    elapsed_ms: int,
) -> dict[str, Any]:
    decomposition = (
        payload.get("decomposition")
        if isinstance(payload.get("decomposition"), dict)
        else {}
    )
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    series = (
        decomposition.get("series")
        if isinstance(decomposition.get("series"), list)
        else []
    )
    latest_row = (
        payload.get("latest_row")
        if isinstance(payload.get("latest_row"), dict)
        else _last_row(payload)
    )
    requested = (
        payload.get("requested")
        if isinstance(payload.get("requested"), dict)
        else {}
    )
    coverage = (
        payload.get("coverage")
        if isinstance(payload.get("coverage"), dict)
        else {}
    )
    cache = payload.get("cache") if isinstance(payload.get("cache"), dict) else {}
    canonical = (
        payload.get("canonical")
        if isinstance(payload.get("canonical"), dict)
        else {}
    )
    first_item = items[0] if items and isinstance(items[0], dict) else {}

    row_count = len(items) if mode == "watchlist" else len(series) if mode == "vn30" else len(rows)
    latest_session = (
        decomposition.get("latest_completed_session")
        if mode == "vn30"
        else first_item.get("latest_session")
        if mode == "watchlist"
        else latest_row.get("trading_date")
    )
    requested_sessions = (
        payload.get("requested_session_count")
        if mode == "watchlist"
        else requested.get("requested_limit")
    )
    actual_sessions = (
        max(
            (
                int(item.get("actual_session_count") or 0)
                for item in items
                if isinstance(item, dict)
            ),
            default=0,
        )
        if mode == "watchlist"
        else len(series)
        if mode == "vn30"
        else coverage.get("covered_sessions")
        if mode == "ticker"
        else len(rows)
    )
    source_freshness = (
        first_item.get("source_freshness")
        if mode == "watchlist"
        else (
            decomposition.get("latest", {}).get("freshness")
            if isinstance(decomposition.get("latest"), dict)
            else None
        )
        if mode == "vn30"
        else payload.get("source_freshness") or payload.get("freshness")
    )
    failure_class = payload.get("failure_class")
    if failure_class is None and mode == "vn30":
        failure_class = canonical.get("failure_class")

    return {
        "mode": mode,
        "request_path": path,
        "http_status": http_status,
        "status": payload.get("status"),
        "data_state": payload.get("data_state"),
        "usable": payload.get("usable"),
        "failure_class": failure_class,
        "row_item_count": row_count,
        "latest_session": latest_session,
        "requested_sessions": requested_sessions,
        "actual_sessions": actual_sessions,
        "source_freshness": source_freshness,
        "cache_state": payload.get("cache_state") or cache.get("status"),
        "provider_endpoint": payload.get("source_endpoint") or payload.get("endpoint"),
        "elapsed_ms": elapsed_ms,
    }


def _request_once(
    *,
    base_url: str,
    mode: str,
    path: str,
    deadline: float,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> bool:
    started = time.monotonic()
    remaining = deadline - started - CLEANUP_RESERVE_SECONDS
    if remaining <= 0:
        _emit(
            **_summary(
                mode=mode,
                path=path,
                http_status=None,
                payload={"status": "unavailable", "failure_class": "timeout"},
                elapsed_ms=0,
            )
        )
        return False

    encoded = None
    headers: dict[str, str] = {}
    if body is not None:
        encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(base_url + path, data=encoded, headers=headers, method=method)
    http_status: int | None = None
    payload: dict[str, Any] = {}
    try:
        with urlopen(request, timeout=min(REQUEST_SECONDS, remaining)) as response:
            http_status = int(response.status)
            payload = _read_json(response)
    except HTTPError as exc:
        http_status = int(exc.code)
        try:
            payload = _read_json(exc)
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
    except (TimeoutError, URLError, OSError):
        payload = {"status": "unavailable", "failure_class": "timeout"}

    _emit(
        **_summary(
            mode=mode,
            path=path,
            http_status=http_status,
            payload=payload,
            elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
        )
    )
    return http_status == 200


def _wait_until_ready(base_url: str, deadline: float) -> bool:
    readiness_deadline = min(time.monotonic() + READINESS_SECONDS, deadline - CLEANUP_RESERVE_SECONDS)
    path = "/api/health"
    started = time.monotonic()
    while time.monotonic() < readiness_deadline:
        try:
            with urlopen(base_url + path, timeout=min(2.0, readiness_deadline - time.monotonic())) as response:
                payload = _read_json(response)
                if response.status == 200:
                    _emit(
                        **_summary(
                            mode="health",
                            path=path,
                            http_status=200,
                            payload=payload,
                            elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
                        )
                    )
                    return True
        except (HTTPError, TimeoutError, URLError, OSError, json.JSONDecodeError):
            time.sleep(0.25)
    _emit(
        **_summary(
            mode="health",
            path=path,
            http_status=None,
            payload={"status": "unavailable", "failure_class": "timeout"},
            elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
        )
    )
    return False


def _port_is_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False


def main() -> int:
    started = time.monotonic()
    deadline = started + GLOBAL_SECONDS
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    TMP.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    stdout_path = TMP / f"m24c-r1-python-{stamp}.stdout.log"
    stderr_path = TMP / f"m24c-r1-python-{stamp}.stderr.log"
    process: subprocess.Popen[bytes] | None = None

    today = date.today()
    from_date = today - timedelta(days=90)
    date_query = urlencode(
        {
            "from_date": from_date.isoformat(),
            "to_date": today.isoformat(),
            "limit": 60,
        }
    )
    routes: list[tuple[str, str, str, dict[str, Any] | None]] = [
        ("ticker", "/api/v1/stocks/vn/foreign-flow/symbol/FPT?limit=20", "GET", None),
        ("vn30", "/api/v1/stocks/vn/foreign-flow/vn30", "GET", None),
        (
            "vn30_direct",
            f"/api/v1/stocks/vn/foreign-flow/index/VN30?{date_query}",
            "GET",
            None,
        ),
        (
            "industry",
            "/api/v1/stocks/vn/industry-flow",
            "POST",
            {
                "index_code": "VN30",
                "from_date": from_date.isoformat(),
                "to_date": today.isoformat(),
            },
        ),
        (
            "proprietary",
            "/api/v1/stocks/vn/proprietary-flow?"
            + urlencode(
                {
                    "scope": "index",
                    "identifier": "VN30",
                    "from_date": from_date.isoformat(),
                    "to_date": today.isoformat(),
                }
            ),
            "GET",
            None,
        ),
        (
            "watchlist",
            "/api/v1/stocks/vn/foreign-flow/watchlist?"
            + urlencode({"tickers": "FPT,SSI,HPG", "sessions": 20}),
            "GET",
            None,
        ),
    ]

    try:
        with stdout_path.open("wb") as stdout_log, stderr_path.open("wb") as stderr_log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "main.py",
                    "--serve-only",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=ROOT,
                env=_deduplicated_environment(port),
                stdin=subprocess.DEVNULL,
                stdout=stdout_log,
                stderr=stderr_log,
                shell=False,
            )
            if not _wait_until_ready(base_url, deadline):
                return 2
            for mode, path, method, body in routes:
                _request_once(
                    base_url=base_url,
                    mode=mode,
                    path=path,
                    deadline=deadline,
                    method=method,
                    body=body,
                )
                if time.monotonic() >= deadline - CLEANUP_RESERVE_SECONDS:
                    break
        return 0
    finally:
        if process is not None and process.poll() is None:
            remaining = max(1.0, deadline - time.monotonic())
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    check=False,
                    capture_output=True,
                    timeout=min(5.0, remaining),
                )
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
            try:
                process.wait(timeout=min(3.0, max(0.1, deadline - time.monotonic())))
            except subprocess.TimeoutExpired:
                process.kill()
        verify_deadline = min(deadline, time.monotonic() + 2.0)
        while _port_is_listening(port) and time.monotonic() < verify_deadline:
            time.sleep(0.1)
        _emit(
            mode="cleanup",
            request_path=f"127.0.0.1:{port}",
            http_status=None,
            status="port_still_listening" if _port_is_listening(port) else "port_released",
            data_state=None,
            usable=None,
            failure_class=None,
            row_item_count=0,
            latest_session=None,
            requested_sessions=None,
            actual_sessions=None,
            source_freshness=None,
            cache_state=None,
            provider_endpoint=None,
            elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
        )


if __name__ == "__main__":
    raise SystemExit(main())
