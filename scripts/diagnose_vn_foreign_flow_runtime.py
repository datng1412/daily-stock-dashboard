"""Run one bounded, sanitized Foreign Flow runtime diagnostic.

This manual script intentionally owns the backend child process directly. It
prints only normalized contract metadata and never prints response bodies,
headers, credentials, or provider payloads.
"""

from __future__ import annotations

import json
import argparse
from collections import deque
from datetime import date, datetime, timedelta
import http.client
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / ".tmp"
READINESS_SECONDS = 20.0
READINESS_REQUEST_SECONDS = 2.0
READINESS_POLL_SECONDS = 0.25
REQUEST_SECONDS = 15.0
GLOBAL_SECONDS = 120.0
CLEANUP_RESERVE_SECONDS = 8.0
MAX_BODY_BYTES = 1_000_000
MAX_LOG_BYTES = 64 * 1024
MAX_LOG_TAIL_LINES = 20
_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_HOST_PORT_KEYS = frozenset({"host", "port", "webui_host", "webui_port"})
_SENSITIVE_LOG_VALUE = re.compile(
    r"(?i)\b(api[_-]?key|api[_-]?secret|authorization|bearer|"
    r"access[_-]?token|refresh[_-]?token|accountId)\b(\s*[:=]\s*)\S+"
)
_PROPRIETARY_FIELDS = (
    "proprietary_buy_volume",
    "proprietary_sell_volume",
    "proprietary_net_volume",
    "proprietary_buy_value",
    "proprietary_sell_value",
    "proprietary_net_value",
)


def _emit(**values: Any) -> None:
    print(json.dumps(values, separators=(",", ":"), sort_keys=True), flush=True)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _deduplicated_environment(*, enable_streaming: bool = False) -> dict[str, str]:
    by_lower_name: dict[str, tuple[str, str]] = {}
    for name, value in os.environ.items():
        if name.lower() in _HOST_PORT_KEYS:
            continue
        by_lower_name[name.lower()] = (name, value)
    environment = {name: value for name, value in by_lower_name.values()}
    environment["SSI_STREAMING_REALTIME_ENABLED"] = (
        "true" if enable_streaming else "false"
    )
    environment["SSI_V3_MAX_RETRIES"] = "0"
    environment["PYTHONUTF8"] = "1"
    return environment


def _child_command(port: int) -> list[str]:
    return [
        sys.executable,
        "main.py",
        "--serve-only",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]


def _creation_flags() -> int:
    return subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0


class _BoundedLogCapture:
    """Continuously drain one child stream while retaining only a bounded tail."""

    def __init__(self, path: Path, *, max_bytes: int = MAX_LOG_BYTES) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self._chunks: deque[bytes] = deque()
        self._size = 0
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self, stream: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self._thread = threading.Thread(
            target=self._drain,
            args=(stream,),
            name=f"bounded-log-{self.path.stem}",
            daemon=True,
        )
        self._thread.start()

    def _drain(self, stream: Any) -> None:
        try:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                with self._lock:
                    self._chunks.append(bytes(chunk))
                    self._size += len(chunk)
                    snapshot = b"".join(self._chunks)[-self.max_bytes :]
                    self._chunks = deque([snapshot])
                    self._size = len(snapshot)
                self.path.write_bytes(snapshot)
        finally:
            stream.close()

    def join(self, timeout: float = 2.0) -> None:
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def tail(self) -> list[str]:
        try:
            text = self.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        safe = _SENSITIVE_LOG_VALUE.sub(r"\1\2[REDACTED]", text)
        return safe.splitlines()[-MAX_LOG_TAIL_LINES:]


def _read_json(response: Any) -> dict[str, Any]:
    raw = response.read(MAX_BODY_BYTES)
    parsed = json.loads(raw.decode("utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def _local_request(
    *,
    port: int,
    path: str,
    timeout: float,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    encoded = (
        json.dumps(body, separators=(",", ":")).encode("utf-8")
        if body is not None
        else None
    )
    headers = {"Content-Type": "application/json"} if encoded is not None else {}
    connection = http.client.HTTPConnection(
        "127.0.0.1",
        port,
        timeout=max(0.1, timeout),
    )
    try:
        connection.request(method, path, body=encoded, headers=headers)
        response = connection.getresponse()
        return int(response.status), _read_json(response)
    finally:
        connection.close()


def _last_row(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("rows")
    if isinstance(rows, list) and rows and isinstance(rows[-1], dict):
        return rows[-1]
    return {}


def _summary(
    *,
    mode: str,
    method: str,
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
    groups = payload.get("groups") if isinstance(payload.get("groups"), list) else []
    aggregate = (
        payload.get("aggregate")
        if isinstance(payload.get("aggregate"), dict)
        else {}
    )
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

    row_count = (
        1 if mode == "current_industry" and aggregate else
        len(series) if mode == "vn30" else len(rows)
    )
    item_count = len(items)
    latest_session = (
        payload.get("provider_session_date")
        if mode == "current_industry"
        else decomposition.get("latest_completed_session")
        if mode == "vn30"
        else first_item.get("latest_session")
        if mode == "watchlist"
        else latest_row.get("trading_date")
    )
    requested_sessions = (
        coverage.get("requested_symbol_count")
        if mode == "current_industry"
        else payload.get("requested_session_count")
        if mode == "watchlist"
        else requested.get("requested_limit")
    )
    actual_sessions = (
        coverage.get("observed_symbol_count")
        if mode == "current_industry"
        else max(
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
    proprietary_fields_present = [
        field
        for field in _PROPRIETARY_FIELDS
        if any(
            isinstance(row, dict) and row.get(field) is not None
            for row in rows
        )
    ]
    industry_codes = {
        str(row.get("icb_code"))
        for row in rows
        if isinstance(row, dict) and row.get("icb_code")
    }
    flow_fields = (
        "foreign_buy_volume",
        "foreign_sell_volume",
        "foreign_net_volume",
        "foreign_buy_value",
        "foreign_sell_value",
        "foreign_net_value",
    )
    safe_aggregate = {
        field: aggregate.get(field)
        for field in flow_fields
        if isinstance(aggregate.get(field), (int, float))
        and not isinstance(aggregate.get(field), bool)
    }
    group_dates = {
        str(group.get("provider_session_date"))
        for group in groups
        if isinstance(group, dict) and group.get("provider_session_date")
    }
    group_reconciles = None
    if mode == "current_industry" and groups and safe_aggregate:
        group_reconciles = all(
            sum(
                group.get(field)
                for group in groups
                if isinstance(group, dict)
                and isinstance(group.get(field), (int, float))
                and not isinstance(group.get(field), bool)
            ) == safe_aggregate.get(field)
            for field in safe_aggregate
        )

    return {
        "mode": mode,
        "method": method,
        "request_path": path,
        "http_status": http_status,
        "status": payload.get("status"),
        "data_state": payload.get("data_state"),
        "usable": payload.get("usable"),
        "failure_class": failure_class,
        "row_count": row_count,
        "item_count": item_count,
        "latest_session": latest_session,
        "requested_sessions": requested_sessions,
        "actual_sessions": actual_sessions,
        "source_freshness": source_freshness,
        "cache_state": payload.get("cache_state") or cache.get("status"),
        "source_endpoint": payload.get("source_endpoint") or payload.get("endpoint"),
        "industry_count": len(industry_codes) if mode == "industry" else None,
        "group_count": len(groups) if mode == "current_industry" else None,
        "aggregate": safe_aggregate if mode == "current_industry" else None,
        "aggregate_present": bool(aggregate) if mode == "current_industry" else None,
        "group_dates": sorted(group_dates) if mode == "current_industry" else None,
        "groups_reconcile": group_reconciles,
        "member_count": (
            payload.get("requested_symbol_count") if mode == "industry" else None
        ),
        "covered_member_count": (
            payload.get("classified_symbol_count") if mode == "industry" else None
        ),
        "selected_session": (
            payload.get("requested_to_date") if mode == "proprietary" else None
        ),
        "proprietary_field_count": (
            len(proprietary_fields_present) if mode == "proprietary" else None
        ),
        "required_fields_present": (
            proprietary_fields_present if mode == "proprietary" else None
        ),
        "ready_count": (
            payload.get("ready_symbol_count") if mode == "watchlist" else None
        ),
        "partial_count": (
            payload.get("partial_symbol_count") if mode == "watchlist" else None
        ),
        "unavailable_count": (
            payload.get("unavailable_symbol_count") if mode == "watchlist" else None
        ),
        "elapsed_ms": elapsed_ms,
    }


def _request_once(
    *,
    port: int,
    mode: str,
    path: str,
    deadline: float,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    remaining = deadline - started - CLEANUP_RESERVE_SECONDS
    if remaining <= 0:
        summary = _summary(
            mode=mode,
            method=method,
            path=path,
            http_status=None,
            payload={"status": "unavailable", "failure_class": "timeout"},
            elapsed_ms=0,
        )
        _emit(**summary)
        return summary

    http_status: int | None = None
    payload: dict[str, Any] = {}
    try:
        http_status, payload = _local_request(
            port=port,
            path=path,
            timeout=min(REQUEST_SECONDS, remaining),
            method=method,
            body=body,
        )
    except (TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        payload = {
            "status": "unavailable",
            "failure_class": (
                "timeout" if isinstance(exc, (TimeoutError, socket.timeout)) else "network_error"
            ),
        }

    summary = _summary(
        mode=mode,
        method=method,
        path=path,
        http_status=http_status,
        payload=payload,
        elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
    )
    _emit(**summary)
    return summary


def _wait_until_ready(
    *,
    port: int,
    deadline: float,
    process: subprocess.Popen[bytes],
    stdout_capture: _BoundedLogCapture,
    stderr_capture: _BoundedLogCapture,
) -> bool:
    readiness_deadline = min(time.monotonic() + READINESS_SECONDS, deadline - CLEANUP_RESERVE_SECONDS)
    path = "/api/health"
    started = time.monotonic()
    last_error_class: str | None = None
    last_http_status: int | None = None
    while time.monotonic() < readiness_deadline:
        if process.poll() is not None:
            last_error_class = "child_exited"
            break
        try:
            last_http_status, payload = _local_request(
                port=port,
                path=path,
                timeout=min(
                    READINESS_REQUEST_SECONDS,
                    max(0.1, readiness_deadline - time.monotonic()),
                ),
            )
            if last_http_status == 200 and payload.get("status") == "ok":
                _emit(
                    **_summary(
                        mode="health",
                        method="GET",
                        path=path,
                        http_status=200,
                        payload=payload,
                        elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
                    )
                )
                return True
            last_error_class = "health_not_ok"
        except (TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            last_error_class = type(exc).__name__
        time.sleep(READINESS_POLL_SECONDS)
    _emit(
        mode="health",
        method="GET",
        request_path=path,
        probe_url=f"http://127.0.0.1:{port}{path}",
        http_status=last_http_status,
        status="unavailable",
        data_state=None,
        usable=False,
        failure_class="readiness_timeout",
        last_error_class=last_error_class,
        child_pid=process.pid,
        child_alive=process.poll() is None,
        requested_port=port,
        row_count=0,
        item_count=0,
        latest_session=None,
        requested_sessions=None,
        actual_sessions=None,
        source_freshness=None,
        cache_state=None,
        source_endpoint=None,
        stdout_tail=stdout_capture.tail(),
        stderr_tail=stderr_capture.tail(),
        elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
    )
    return False


def _port_is_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.25):
            return True
    except OSError:
        return False


def _completed_session(value: str | None, *, now: datetime | None = None) -> date:
    if value:
        return date.fromisoformat(value)
    current = now or datetime.now(_VN_TZ)
    candidate = current.date() - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def _routes(completed_session: date) -> list[tuple[str, str, str, dict[str, Any] | None]]:
    from_date = completed_session - timedelta(days=90)
    date_query = urlencode(
        {
            "from_date": from_date.isoformat(),
            "to_date": completed_session.isoformat(),
            "limit": 60,
        }
    )
    return [
        ("ticker", "/api/v1/stocks/vn/foreign-flow/symbol/FPT?limit=20", "GET", None),
        ("vn30", "/api/v1/stocks/vn/foreign-flow/vn30", "GET", None),
        (
            "industry",
            "/api/v1/stocks/vn/industry-flow",
            "POST",
            {
                "index_code": "VN30",
                "from_date": from_date.isoformat(),
                "to_date": completed_session.isoformat(),
            },
        ),
        (
            "proprietary",
            "/api/v1/stocks/vn/proprietary-flow?"
            + urlencode(
                {
                    "scope": "index",
                    "identifier": "VN30",
                    "from_date": completed_session.isoformat(),
                    "to_date": completed_session.isoformat(),
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
        (
            "vn30_direct",
            f"/api/v1/stocks/vn/foreign-flow/index/VN30?{date_query}",
            "GET",
            None,
        ),
    ]


def _select_observed_session(
    fallback: date,
    summaries: list[dict[str, Any]],
    *,
    explicit_fallback: bool,
) -> tuple[date, str, str | None]:
    observed: list[date] = []
    for summary in summaries:
        value = summary.get("latest_session")
        if not isinstance(value, str):
            continue
        try:
            observed.append(date.fromisoformat(value))
        except ValueError:
            continue
    if observed:
        latest = max(observed)
        return latest, "latest_completed_provider_session_observed", latest.isoformat()
    return (
        fallback,
        (
            "previously_proven_completed_session"
            if explicit_fallback
            else "latest_completed_weekday"
        ),
        None,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--completed-session",
        help="Explicit latest completed provider session in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--current-industry",
        action="store_true",
        help="Enable SSI streaming and inspect only the current VN30 Industry aggregate.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    started = time.monotonic()
    deadline = started + GLOBAL_SECONDS
    port = _free_port()
    TMP.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    stdout_path = TMP / f"m24c-r31-python-{stamp}.stdout.log"
    stderr_path = TMP / f"m24c-r31-python-{stamp}.stderr.log"
    process: subprocess.Popen[bytes] | None = None
    completed_session = _completed_session(args.completed_session)
    stdout_capture = _BoundedLogCapture(stdout_path)
    stderr_capture = _BoundedLogCapture(stderr_path)

    try:
        process = subprocess.Popen(
            _child_command(port),
            cwd=ROOT,
            env=_deduplicated_environment(enable_streaming=args.current_industry),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            creationflags=_creation_flags(),
        )
        assert process.stdout is not None
        assert process.stderr is not None
        stdout_capture.start(process.stdout)
        stderr_capture.start(process.stderr)
        _emit(
            mode="startup",
            method=None,
            request_path=None,
            http_status=None,
            status="child_started",
            data_state=None,
            usable=None,
            failure_class=None,
            child_pid=process.pid,
            python_executable=sys.executable,
            working_directory=str(ROOT),
            requested_host="127.0.0.1",
            requested_port=port,
            probe_url=f"http://127.0.0.1:{port}/api/health",
            completed_session=completed_session.isoformat(),
            completed_session_basis=(
                "previously_proven_completed_session"
                if args.completed_session
                else "latest_completed_weekday"
            ),
            row_count=0,
            item_count=0,
            latest_session=None,
            requested_sessions=None,
            actual_sessions=None,
            source_freshness=None,
            cache_state=None,
            source_endpoint=None,
            elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
        )
        if not _wait_until_ready(
            port=port,
            deadline=deadline,
            process=process,
            stdout_capture=stdout_capture,
            stderr_capture=stderr_capture,
        ):
            return 2
        if args.current_industry:
            path = (
                "/api/v1/stocks/vn/foreign-flow/current-aggregate?"
                "scope=vn30&include_industries=true&force_refresh=true&"
                "recovery_trigger=manual_refresh"
            )
            for attempt in range(2):
                summary = _request_once(
                    port=port,
                    mode="current_industry",
                    path=path,
                    deadline=deadline,
                )
                if summary.get("usable") and summary.get("aggregate_present"):
                    break
                if attempt == 0 and time.monotonic() < deadline - 20:
                    time.sleep(10)
            return 0
        initial_summaries: list[dict[str, Any]] = []
        for mode, path, method, body in _routes(completed_session)[:2]:
            initial_summaries.append(_request_once(
                port=port,
                mode=mode,
                path=path,
                deadline=deadline,
                method=method,
                body=body,
            ))
            if time.monotonic() >= deadline - CLEANUP_RESERVE_SECONDS:
                break
        selected_session, selection_basis, latest_provider_session = (
            _select_observed_session(
                completed_session,
                initial_summaries,
                explicit_fallback=bool(args.completed_session),
            )
        )
        _emit(
            mode="session_selection",
            method=None,
            request_path=None,
            http_status=None,
            status="selected",
            data_state=None,
            usable=None,
            failure_class=None,
            selected_session=selected_session.isoformat(),
            selection_basis=selection_basis,
            latest_provider_session=latest_provider_session,
            row_count=0,
            item_count=0,
            latest_session=latest_provider_session,
            requested_sessions=None,
            actual_sessions=None,
            source_freshness=None,
            cache_state=None,
            source_endpoint=None,
            elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
        )
        for mode, path, method, body in _routes(selected_session)[2:]:
            _request_once(
                port=port,
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
        stdout_capture.join()
        stderr_capture.join()
        verify_deadline = min(deadline, time.monotonic() + 2.0)
        while _port_is_listening(port) and time.monotonic() < verify_deadline:
            time.sleep(0.1)
        _emit(
            mode="cleanup",
            method=None,
            request_path=f"127.0.0.1:{port}",
            http_status=None,
            status="port_still_listening" if _port_is_listening(port) else "port_released",
            data_state=None,
            usable=None,
            failure_class=None,
            row_count=0,
            item_count=0,
            latest_session=None,
            requested_sessions=None,
            actual_sessions=None,
            source_freshness=None,
            cache_state=None,
            source_endpoint=None,
            elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
        )


if __name__ == "__main__":
    raise SystemExit(main())
