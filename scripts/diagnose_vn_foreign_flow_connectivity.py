"""Bounded, secret-safe SSI V3 foreign-flow connectivity diagnostic.

The default mode performs no network work. ``--live`` permits one DNS, TCP,
and verified TLS probe for the configured REST host, one authentication
lifecycle, and at most one request for each bounded capability. Output is
compact JSON metadata only; credentials, tokens, headers, URLs with query
parameters, and provider payloads are never emitted.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date, datetime, timedelta
import importlib.metadata
import json
import os
from pathlib import Path
import queue
import socket
import ssl
import sys
import threading
import time
from typing import Any, Callable, Mapping, Optional
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_provider.ssi_v3_adapter import (  # noqa: E402
    SsiFastConnectV3Adapter,
    SsiV3RestSettings,
)
from src.config import Config, get_config, setup_env  # noqa: E402


_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DNS_TIMEOUT_SECONDS = 5.0
TCP_TIMEOUT_SECONDS = 5.0
TLS_TIMEOUT_SECONDS = 10.0
AUTH_TIMEOUT_SECONDS = 15.0
PROVIDER_TIMEOUT_SECONDS = 20.0
GLOBAL_TIMEOUT_SECONDS = 120.0
SDK_REQUEST_TIMEOUT_SECONDS = 10

_CONFIG_DEFAULTS: dict[str, Optional[str]] = {
    "SSI_V3_REST_ENABLED": "false",
    "SSI_V3_CLIENT_ID": None,
    "SSI_V3_API_KEY": None,
    "SSI_V3_API_SECRET": None,
    "SSI_V3_API_URL": "https://api.ssi.com.vn/api/v3",
    "SSI_V3_REQUEST_TIMEOUT": "10",
    "SSI_V3_MAX_RETRIES": "2",
    "SSI_V3_RETRY_DELAY": "1",
    "SSI_V3_RATE_LIMIT_PER_SECOND": "5",
    "HTTP_PROXY": None,
    "HTTPS_PROXY": None,
    "ALL_PROXY": None,
    "NO_PROXY": None,
    "REQUESTS_CA_BUNDLE": None,
    "SSL_CERT_FILE": None,
    "CURL_CA_BUNDLE": None,
}
_REPOSITORY_READ_KEYS = frozenset(
    {
        "SSI_V3_REST_ENABLED",
        "SSI_V3_CLIENT_ID",
        "SSI_V3_API_KEY",
        "SSI_V3_API_SECRET",
        "SSI_V3_API_URL",
        "SSI_V3_REQUEST_TIMEOUT",
        "SSI_V3_MAX_RETRIES",
        "SSI_V3_RETRY_DELAY",
        "SSI_V3_RATE_LIMIT_PER_SECOND",
    }
)
_HTTP_ENV_KEYS = frozenset(
    {
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "SSL_CERT_FILE",
    }
)
_CAPABILITIES = (
    ("exact_security_lookup", "securitiesByBoard?symbol=", "get_security_basic_info"),
    ("daily_stock_price", "securitiesSummary?symbol=", "get_daily_stock_price"),
    ("index_components", "securitiesByBoard?index=", "get_index_components"),
    ("securities_summary_index", "securitiesSummary?index=", "get_securities_summary_by_index"),
    ("index_summary", "indexSummary?index=", "get_index_summary"),
)


def _emit(event: str, **values: Any) -> None:
    print(
        json.dumps({"event": event, **values}, separators=(",", ":"), sort_keys=True),
        flush=True,
    )


def _active_env_path() -> Path:
    configured = os.environ.get("ENV_FILE")
    return Path(configured) if configured else ROOT / ".env"


def _value_state(value: Optional[str]) -> dict[str, bool]:
    return {
        "present": value is not None,
        "empty": value is not None and not str(value).strip(),
        "edge_whitespace": value is not None and str(value) != str(value).strip(),
    }


def configuration_inventory(
    initial_environment: Mapping[str, str],
    dotenv: Mapping[str, Optional[str]],
) -> list[dict[str, Any]]:
    """Return configuration provenance without returning any values."""

    inventory: list[dict[str, Any]] = []
    for name, default in _CONFIG_DEFAULTS.items():
        process_value = initial_environment.get(name)
        dotenv_value = dotenv.get(name)
        if process_value is not None:
            source = "process_environment"
            effective = process_value
        elif dotenv_value is not None:
            source = "dotenv"
            effective = str(dotenv_value)
        elif default is not None:
            source = "config_default"
            effective = default
        else:
            source = "missing"
            effective = None
        inventory.append(
            {
                "name": name,
                "source": source,
                "application_reads": (
                    name in _REPOSITORY_READ_KEYS or name in _HTTP_ENV_KEYS
                ),
                "process_dotenv_conflict": (
                    process_value is not None
                    and dotenv_value is not None
                    and process_value != str(dotenv_value)
                ),
                **_value_state(effective),
            }
        )
    return inventory


def _exception_chain(exc: BaseException) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    seen: set[int] = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen and len(chain) < 8:
        seen.add(id(current))
        item: dict[str, Any] = {"exception_class": type(current).__name__}
        error_number = getattr(current, "errno", None)
        if isinstance(error_number, int):
            item["errno"] = error_number
        chain.append(item)
        current = current.__cause__ or current.__context__
    return chain


def classify_exception(exc: BaseException, *, stage: str) -> str:
    """Classify a transport/auth failure from types and safe status metadata."""

    status_code = getattr(exc, "status_code", None)
    names = {type(item).__name__ for item in _walk_exception_chain(exc)}
    if status_code == 401:
        return "authentication"
    if status_code == 403:
        return "authorization"
    if "ProxyError" in names:
        return "proxy_error"
    if "SSLCertVerificationError" in names or "CertificateVerifyError" in names:
        return "tls_certificate_error"
    if "CertificateError" in names:
        return "tls_hostname_error"
    if names & {"SSLError", "SSLEOFError"}:
        return "tls_handshake_error"
    if "gaierror" in names:
        return "dns_error"
    if "ConnectionRefusedError" in names:
        return "connection_refused"
    if "ConnectTimeout" in names:
        return "connect_timeout"
    if names & {"ReadTimeout", "TimeoutError", "socket.timeout"}:
        return "read_timeout" if stage not in {"dns", "tcp", "tls"} else f"{stage}_timeout"
    if "AuthenticationError" in names:
        return "authentication"
    if "ConnectError" in names or "OSError" in names:
        return "network_error"
    return "unknown"


def _walk_exception_chain(exc: BaseException) -> list[BaseException]:
    result: list[BaseException] = []
    seen: set[int] = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen and len(result) < 8:
        seen.add(id(current))
        result.append(current)
        current = current.__cause__ or current.__context__
    return result


def _bounded_call(
    operation: Callable[[], Any],
    timeout_seconds: float,
) -> tuple[bool, Any, int]:
    """Run one operation in a daemon thread without waiting past its bound."""

    started = time.monotonic()
    result_queue: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def runner() -> None:
        try:
            result_queue.put((True, operation()), block=False)
        except BaseException as exc:  # noqa: BLE001 - diagnostic boundary
            result_queue.put((False, exc), block=False)

    thread = threading.Thread(target=runner, name="ssi-r3-bounded-call", daemon=True)
    thread.start()
    thread.join(timeout=max(0.0, timeout_seconds))
    elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
    if thread.is_alive():
        return False, TimeoutError("bounded diagnostic stage timed out"), elapsed_ms
    try:
        return (*result_queue.get_nowait(), elapsed_ms)
    except queue.Empty:
        return False, RuntimeError("diagnostic stage returned no result"), elapsed_ms


def _dns_probe(hostname: str) -> dict[str, Any]:
    ok, value, elapsed_ms = _bounded_call(
        lambda: socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM),
        DNS_TIMEOUT_SECONDS,
    )
    if not ok:
        return {
            "success": False,
            "failure_class": classify_exception(value, stage="dns"),
            "exception_chain": _exception_chain(value),
            "elapsed_ms": elapsed_ms,
        }
    families = sorted(
        {
            "ipv6" if item[0] == socket.AF_INET6 else "ipv4"
            for item in value
            if item[0] in {socket.AF_INET, socket.AF_INET6}
        }
    )
    return {"success": True, "address_families": families, "elapsed_ms": elapsed_ms}


def _tcp_probe(hostname: str, port: int) -> dict[str, Any]:
    def connect() -> None:
        with socket.create_connection((hostname, port), timeout=TCP_TIMEOUT_SECONDS):
            return None

    ok, value, elapsed_ms = _bounded_call(connect, TCP_TIMEOUT_SECONDS)
    if not ok:
        return {
            "success": False,
            "failure_class": classify_exception(value, stage="tcp"),
            "exception_chain": _exception_chain(value),
            "elapsed_ms": elapsed_ms,
        }
    return {"success": True, "elapsed_ms": elapsed_ms}


def _tls_probe(hostname: str, port: int) -> dict[str, Any]:
    def handshake() -> dict[str, Any]:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=TLS_TIMEOUT_SECONDS) as raw:
            raw.settimeout(TLS_TIMEOUT_SECONDS)
            with context.wrap_socket(raw, server_hostname=hostname) as secured:
                certificate = secured.getpeercert()
                subject_name = next(
                    (
                        value
                        for group in certificate.get("subject", ())
                        for key, value in group
                        if key == "commonName"
                    ),
                    None,
                )
                issuer_org = next(
                    (
                        value
                        for group in certificate.get("issuer", ())
                        for key, value in group
                        if key == "organizationName"
                    ),
                    None,
                )
                return {
                    "tls_version": secured.version(),
                    "subject_hostname": subject_name,
                    "issuer_organization": issuer_org,
                    "not_before": certificate.get("notBefore"),
                    "not_after": certificate.get("notAfter"),
                }

    ok, value, elapsed_ms = _bounded_call(handshake, TLS_TIMEOUT_SECONDS)
    if not ok:
        return {
            "success": False,
            "certificate_verified": False,
            "failure_class": classify_exception(value, stage="tls"),
            "exception_chain": _exception_chain(value),
            "elapsed_ms": elapsed_ms,
        }
    return {
        "success": True,
        "certificate_verified": True,
        **value,
        "elapsed_ms": elapsed_ms,
    }


def _provider_summary(
    capability: str,
    endpoint: str,
    result: Mapping[str, Any],
    elapsed_ms: int,
) -> dict[str, Any]:
    rows = result.get("rows")
    safe_rows = rows if isinstance(rows, list) else []
    latest_session = next(
        (
            row.get("date") or row.get("trading_date")
            for row in reversed(safe_rows)
            if isinstance(row, Mapping)
        ),
        None,
    )
    diagnostics = result.get("diagnostics")
    safe_diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
    return {
        "capability": capability,
        "provider_endpoint": endpoint,
        "request_attempted": True,
        "status": result.get("status"),
        "row_count": len(safe_rows),
        "latest_provider_session": latest_session,
        "failure_class": result.get("failure_class"),
        "http_status": safe_diagnostics.get("http_status"),
        "exception_class": safe_diagnostics.get("exception_class"),
        "elapsed_ms": elapsed_ms,
    }


def _latest_completed_weekday(now: datetime) -> datetime:
    candidate = now - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def select_completed_session(
    now: datetime,
    *,
    provider_latest_date: Optional[str] = None,
) -> tuple[date, str]:
    """Prefer proven provider freshness, else use the prior Vietnam weekday."""

    if provider_latest_date:
        return date.fromisoformat(provider_latest_date), "explicit_provider_latest"
    return _latest_completed_weekday(now).date(), "latest_completed_weekday"


def _proprietary_provider_summary(
    result: Mapping[str, Any],
    *,
    selected_date: date,
    elapsed_ms: int,
) -> dict[str, Any]:
    fields = (
        "proprietary_buy_volume",
        "proprietary_sell_volume",
        "proprietary_net_volume",
        "proprietary_buy_value",
        "proprietary_sell_value",
        "proprietary_net_value",
    )
    rows = result.get("rows")
    safe_rows = rows if isinstance(rows, list) else []
    present = [
        field
        for field in fields
        if any(isinstance(row, Mapping) and row.get(field) is not None for row in safe_rows)
    ]
    latest_session = next(
        (
            row.get("date") or row.get("trading_date")
            for row in reversed(safe_rows)
            if isinstance(row, Mapping)
        ),
        None,
    )
    diagnostics = result.get("diagnostics")
    safe_diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
    return {
        "capability": "index_summary",
        "provider_endpoint": "indexSummary?index=",
        "selected_date": selected_date.isoformat(),
        "request_attempted": True,
        "status": result.get("status"),
        "row_count": len(safe_rows),
        "proprietary_fields_present": present,
        "proprietary_fields_missing": [field for field in fields if field not in present],
        "latest_provider_session": latest_session,
        "failure_class": result.get("failure_class"),
        "http_status": safe_diagnostics.get("http_status"),
        "exception_class": safe_diagnostics.get("exception_class"),
        "elapsed_ms": elapsed_ms,
    }


def _skipped_capability(capability: str, endpoint: str) -> dict[str, Any]:
    return {
        "capability": capability,
        "provider_endpoint": endpoint,
        "request_attempted": False,
        "status": "not_run",
        "row_count": 0,
        "latest_provider_session": None,
        "failure_class": "authentication_not_available",
        "http_status": None,
        "exception_class": None,
        "elapsed_ms": 0,
    }


def _proxy_inventory(hostname: str) -> list[dict[str, Any]]:
    no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    no_proxy_names = {
        part.strip().lstrip(".").lower()
        for part in no_proxy.split(",")
        if part.strip()
    }
    covered = any(
        hostname.lower() == item or hostname.lower().endswith("." + item)
        for item in no_proxy_names
    )
    return [
        {
            "name": name,
            "present": bool(os.environ.get(name) or os.environ.get(name.lower())),
            "target_covered_by_no_proxy": covered if name == "NO_PROXY" else None,
        }
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")
    ]


def _trust_store() -> dict[str, Any]:
    paths = ssl.get_default_verify_paths()
    result: dict[str, Any] = {
        "openssl_cafile": paths.cafile,
        "openssl_capath": paths.capath,
        "openssl_env_cafile": paths.openssl_cafile_env,
        "openssl_env_capath": paths.openssl_capath_env,
        "requests_ca_bundle_present": bool(os.environ.get("REQUESTS_CA_BUNDLE")),
        "ssl_cert_file_present": bool(os.environ.get("SSL_CERT_FILE")),
        "curl_ca_bundle_present": bool(os.environ.get("CURL_CA_BUNDLE")),
    }
    try:
        import certifi

        result["certifi_cafile"] = certifi.where()
    except ImportError:
        result["certifi_cafile"] = None
    return result


def run_index_summary_only(*, provider_latest_date: str) -> int:
    """Run authentication plus exactly one bounded indexSummary provider call."""

    started = time.monotonic()
    setup_env()
    Config.reset_instance()
    settings = SsiV3RestSettings.from_config(get_config())
    selected_date, selection_basis = select_completed_session(
        datetime.now(_VN_TZ),
        provider_latest_date=provider_latest_date,
    )
    _emit(
        "selection",
        selected_date=selected_date.isoformat(),
        selection_basis=selection_basis,
        holiday_calendar_used=False,
    )
    if not settings.enabled or settings.missing_required_names:
        _emit(
            "final",
            authentication_count=0,
            total_provider_requests=0,
            failure_class=(
                "credentials_missing"
                if settings.missing_required_names
                else "environment_configuration"
            ),
            elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
        )
        return 2

    bounded_settings = replace(
        settings,
        request_timeout=min(
            max(int(settings.request_timeout), 1),
            SDK_REQUEST_TIMEOUT_SECONDS,
        ),
        max_retries=0,
    )
    adapter: Optional[SsiFastConnectV3Adapter] = None
    request_count = 0
    try:
        adapter = SsiFastConnectV3Adapter(bounded_settings)
        auth_ok, auth_value, auth_elapsed = _bounded_call(
            adapter.initialize_rest_access,
            AUTH_TIMEOUT_SECONDS,
        )
        auth_result = (
            auth_value
            if auth_ok
            else {
                "status": "unavailable",
                "failure_class": classify_exception(auth_value, stage="auth"),
            }
        )
        _emit(
            "authentication",
            request_attempted=True,
            credentials_present=True,
            status=auth_result.get("status"),
            failure_class=auth_result.get("failure_class"),
            elapsed_ms=auth_elapsed,
        )
        if auth_result.get("status") != "ok":
            _emit(
                "final",
                authentication_count=1,
                total_provider_requests=0,
                failure_class=auth_result.get("failure_class"),
                elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
            )
            return 2

        request_count = 1
        ok, value, elapsed_ms = _bounded_call(
            lambda: adapter.get_index_summary(
                "HOSE",
                index_code="VN30",
                trading_date=selected_date.isoformat(),
            ),
            PROVIDER_TIMEOUT_SECONDS,
        )
        result = (
            value
            if ok
            else {
                "status": "unavailable",
                "failure_class": classify_exception(value, stage="provider"),
                "diagnostics": {"exception_class": type(value).__name__},
            }
        )
        summary = _proprietary_provider_summary(
            result,
            selected_date=selected_date,
            elapsed_ms=elapsed_ms,
        )
        _emit("capability", **summary)
        _emit(
            "final",
            authentication_count=1,
            total_provider_requests=request_count,
            failure_class=summary.get("failure_class"),
            elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
        )
        return 0
    finally:
        if adapter is not None:
            adapter.close()


def run(*, live: bool) -> int:
    started = time.monotonic()
    global_deadline = started + GLOBAL_TIMEOUT_SECONDS
    initial_environment = dict(os.environ)
    env_path = _active_env_path()
    dotenv = dotenv_values(env_path) if env_path.exists() else {}
    for item in configuration_inventory(initial_environment, dotenv):
        _emit("configuration", **item)

    setup_env()
    Config.reset_instance()
    config = get_config()
    settings = SsiV3RestSettings.from_config(config)
    parsed = urlparse(settings.sdk_api_url)
    hostname = parsed.hostname or ""
    port = parsed.port or 443
    _emit(
        "runtime",
        mode="live" if live else "offline",
        sdk_version=importlib.metadata.version("ssi-sdk"),
        python_version=sys.version.split()[0],
        rest_scheme=parsed.scheme,
        rest_hostname=hostname,
        rest_port=port,
        rest_path_prefix="/api/v3",
        base_url_source=next(
            (
                item["source"]
                for item in configuration_inventory(initial_environment, dotenv)
                if item["name"] == "SSI_V3_API_URL"
            ),
            "unknown",
        ),
        rest_enabled=settings.enabled,
        credentials_present=not settings.missing_required_names,
        client_id_present=bool(settings.client_id),
    )
    try:
        from ssi_sdk.constant import DEFAULT_STREAMING_URL

        stream = urlparse(DEFAULT_STREAMING_URL)
        _emit(
            "streaming_host",
            scheme=stream.scheme,
            hostname=stream.hostname,
            port=stream.port or 443,
            source="ssi_sdk_default",
            probed=False,
        )
    except ImportError:
        _emit("streaming_host", source="package_unavailable", probed=False)

    _emit("proxy", sdk_http_transport="httpx_trust_env", items=_proxy_inventory(hostname))
    _emit("trust_store", **_trust_store())
    if not live:
        _emit(
            "final",
            live_requests_performed=0,
            elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
        )
        return 0
    if not settings.enabled or settings.missing_required_names or not hostname:
        failure = (
            "credentials_missing"
            if settings.missing_required_names
            else "invalid_base_url"
            if not hostname
            else "environment_configuration"
        )
        _emit(
            "final",
            failure_class=failure,
            live_requests_performed=0,
            elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
        )
        return 2

    dns = _dns_probe(hostname)
    _emit("dns", hostname=hostname, **dns)
    tcp = _tcp_probe(hostname, port)
    _emit("tcp", hostname=hostname, port=port, **tcp)
    tls = _tls_probe(hostname, port)
    _emit("tls", hostname=hostname, port=port, **tls)

    bounded_settings = replace(
        settings,
        request_timeout=min(
            max(int(settings.request_timeout), 1),
            SDK_REQUEST_TIMEOUT_SECONDS,
        ),
        max_retries=0,
    )
    adapter: Optional[SsiFastConnectV3Adapter] = None
    request_counts = {name: 0 for name, _endpoint, _method in _CAPABILITIES}
    authentication_count = 0
    capability_results: list[dict[str, Any]] = []
    try:
        adapter = SsiFastConnectV3Adapter(bounded_settings)
        authentication_count = 1
        ok, auth_value, auth_elapsed = _bounded_call(
            adapter.initialize_rest_access,
            min(AUTH_TIMEOUT_SECONDS, max(0.0, global_deadline - time.monotonic())),
        )
        if ok:
            auth_result = auth_value
        else:
            auth_result = {
                "status": "unavailable",
                "failure_class": classify_exception(auth_value, stage="auth"),
                "diagnostics": {
                    "exception_class": type(auth_value).__name__,
                    "exception_chain": _exception_chain(auth_value),
                },
            }
        auth_diagnostics = auth_result.get("diagnostics")
        safe_auth_diagnostics = (
            auth_diagnostics if isinstance(auth_diagnostics, Mapping) else {}
        )
        auth_ok = auth_result.get("status") == "ok"
        auth_client = getattr(adapter, "_auth", None)
        token = getattr(getattr(auth_client, "token_manager", None), "token", None)
        _emit(
            "authentication",
            request_attempted=True,
            credentials_present=True,
            status=auth_result.get("status"),
            token_received=bool(getattr(token, "access_token", None)),
            token_type_present=bool(getattr(token, "token_type", None)),
            token_expiry_present=bool(getattr(token, "expires_at", None)),
            failure_class=auth_result.get("failure_class"),
            http_status=safe_auth_diagnostics.get("http_status"),
            exception_class=safe_auth_diagnostics.get("exception_class"),
            exception_chain=safe_auth_diagnostics.get("exception_chain"),
            elapsed_ms=auth_elapsed,
        )

        now = datetime.now(_VN_TZ)
        to_date, _selection_basis = select_completed_session(now)
        from_date = to_date - timedelta(days=30)
        operations: dict[str, Callable[[], Mapping[str, Any]]] = {
            "exact_security_lookup": lambda: adapter.get_security_basic_info("FPT"),
            "daily_stock_price": lambda: adapter.get_daily_stock_price(
                "FPT",
                market="HOSE",
                from_date=from_date.isoformat(),
                to_date=to_date.isoformat(),
                limit=20,
            ),
            "index_components": lambda: adapter.get_index_components(
                "VN30", market="HOSE"
            ),
            "securities_summary_index": lambda: adapter.get_securities_summary_by_index(
                "VN30",
                from_date=from_date.isoformat(),
                to_date=to_date.isoformat(),
                page_index=1,
                page_size=20,
                limit=20,
            ),
            "index_summary": lambda: adapter.get_index_summary(
                "HOSE",
                index_code="VN30",
                trading_date=to_date.isoformat(),
            ),
        }
        for capability, endpoint, _method in _CAPABILITIES:
            if not auth_ok:
                summary = _skipped_capability(capability, endpoint)
            elif time.monotonic() >= global_deadline:
                summary = {
                    **_skipped_capability(capability, endpoint),
                    "failure_class": "global_timeout",
                }
            else:
                request_counts[capability] += 1
                ok, value, elapsed_ms = _bounded_call(
                    operations[capability],
                    min(
                        PROVIDER_TIMEOUT_SECONDS,
                        max(0.0, global_deadline - time.monotonic()),
                    ),
                )
                if ok:
                    result = value
                else:
                    result = {
                        "status": "unavailable",
                        "failure_class": classify_exception(value, stage="provider"),
                        "diagnostics": {
                            "exception_class": type(value).__name__,
                            "exception_chain": _exception_chain(value),
                        },
                    }
                summary = _provider_summary(
                    capability, endpoint, result, elapsed_ms
                )
            capability_results.append(summary)
            _emit("capability", **summary)
    finally:
        if adapter is not None:
            adapter.close()

    failed_classes = [
        str(item.get("failure_class"))
        for item in capability_results
        if item.get("failure_class")
    ]
    _emit(
        "final",
        authentication_count=authentication_count,
        provider_request_counts=request_counts,
        total_provider_requests=sum(request_counts.values()),
        successful_capabilities=sum(
            item.get("status") == "ok" for item in capability_results
        ),
        failure_classes=sorted(set(failed_classes)),
        elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--live",
        action="store_true",
        help="Permit the single bounded SSI connectivity/capability run.",
    )
    modes.add_argument(
        "--index-summary-only",
        action="store_true",
        help="Permit authentication plus one bounded indexSummary request only.",
    )
    parser.add_argument(
        "--provider-latest-date",
        help="Explicit proven provider session in YYYY-MM-DD format.",
    )
    args = parser.parse_args()
    if args.index_summary_only:
        if not args.provider_latest_date:
            parser.error("--index-summary-only requires --provider-latest-date")
        return run_index_summary_only(
            provider_latest_date=args.provider_latest_date,
        )
    return run(live=args.live)


if __name__ == "__main__":
    raise SystemExit(main())
