"""Deterministic coverage for the bounded SSI V3 connectivity diagnostic."""

from __future__ import annotations

from datetime import datetime

import httpx

from scripts import diagnose_vn_foreign_flow_connectivity as diagnostic


def test_configuration_inventory_uses_process_then_dotenv_then_default() -> None:
    inventory = {
        item["name"]: item
        for item in diagnostic.configuration_inventory(
            {
                "SSI_V3_API_KEY": " process-key ",
                "SSI_V3_REQUEST_TIMEOUT": "7",
            },
            {
                "SSI_V3_API_KEY": "dotenv-key",
                "SSI_V3_API_SECRET": "",
                "SSI_V3_REQUEST_TIMEOUT": "7",
            },
        )
    }

    assert inventory["SSI_V3_API_KEY"] == {
        "name": "SSI_V3_API_KEY",
        "source": "process_environment",
        "application_reads": True,
        "process_dotenv_conflict": True,
        "present": True,
        "empty": False,
        "edge_whitespace": True,
    }
    assert inventory["SSI_V3_API_SECRET"]["source"] == "dotenv"
    assert inventory["SSI_V3_API_SECRET"]["empty"] is True
    assert inventory["SSI_V3_API_URL"]["source"] == "config_default"
    assert inventory["SSI_V3_CLIENT_ID"]["source"] == "missing"


def test_configuration_inventory_never_contains_values() -> None:
    rendered = repr(
        diagnostic.configuration_inventory(
            {"SSI_V3_API_KEY": "do-not-render-process"},
            {"SSI_V3_API_SECRET": "do-not-render-dotenv"},
        )
    )

    assert "do-not-render-process" not in rendered
    assert "do-not-render-dotenv" not in rendered


def test_transport_failure_classification_is_specific() -> None:
    assert (
        diagnostic.classify_exception(
            socket_error := socket_gaierror(),
            stage="dns",
        )
        == "dns_error"
    )
    assert type(socket_error).__name__ == "gaierror"
    assert (
        diagnostic.classify_exception(
            ConnectionRefusedError(10061, "refused"),
            stage="tcp",
        )
        == "connection_refused"
    )
    assert (
        diagnostic.classify_exception(
            httpx.ConnectTimeout("connect timed out"),
            stage="provider",
        )
        == "connect_timeout"
    )
    assert (
        diagnostic.classify_exception(
            httpx.ReadTimeout("read timed out"),
            stage="provider",
        )
        == "read_timeout"
    )
    assert (
        diagnostic.classify_exception(
            httpx.ProxyError("proxy failed"),
            stage="provider",
        )
        == "proxy_error"
    )


def socket_gaierror() -> OSError:
    import socket

    return socket.gaierror(11001, "name not found")


def test_tls_and_auth_failure_classification_is_specific() -> None:
    from ssi_sdk.exceptions import AuthenticationError
    import ssl

    assert (
        diagnostic.classify_exception(
            ssl.SSLCertVerificationError(1, "verify failed"),
            stage="tls",
        )
        == "tls_certificate_error"
    )
    assert (
        diagnostic.classify_exception(
            AuthenticationError("rejected", status_code=401),
            stage="auth",
        )
        == "authentication"
    )
    assert (
        diagnostic.classify_exception(
            AuthenticationError("forbidden", status_code=403),
            stage="provider",
        )
        == "authorization"
    )


def test_exception_chain_contains_only_safe_type_and_errno() -> None:
    secret = "do-not-render-secret"
    try:
        try:
            raise OSError(10060, secret)
        except OSError as inner:
            raise httpx.ConnectError(secret) from inner
    except httpx.ConnectError as exc:
        chain = diagnostic._exception_chain(exc)

    rendered = repr(chain)
    assert chain == [
        {"exception_class": "ConnectError"},
        {"exception_class": "TimeoutError", "errno": 10060},
    ]
    assert secret not in rendered


def test_capability_matrix_is_unique_and_bounded_to_one_method_each() -> None:
    names = [name for name, _endpoint, _method in diagnostic._CAPABILITIES]
    methods = [method for _name, _endpoint, method in diagnostic._CAPABILITIES]

    assert names == [
        "exact_security_lookup",
        "daily_stock_price",
        "index_components",
        "securities_summary_index",
        "index_summary",
    ]
    assert len(names) == len(set(names)) == len(set(methods)) == 5


def test_provider_summary_is_aggregate_only() -> None:
    result = {
        "status": "ok",
        "rows": [
            {
                "date": "2026-07-24",
                "foreign_buy_value": 123456,
                "private_provider_field": "do-not-render",
            }
        ],
        "diagnostics": {"capability": "daily_stock_price"},
    }

    summary = diagnostic._provider_summary(
        "daily_stock_price",
        "securitiesSummary?symbol=",
        result,
        12,
    )

    assert summary == {
        "capability": "daily_stock_price",
        "provider_endpoint": "securitiesSummary?symbol=",
        "request_attempted": True,
        "status": "ok",
        "row_count": 1,
        "latest_provider_session": "2026-07-24",
        "failure_class": None,
        "http_status": None,
        "exception_class": None,
        "elapsed_ms": 12,
    }
    assert "do-not-render" not in repr(summary)


def test_bounded_call_returns_without_waiting_for_daemon_after_timeout() -> None:
    import threading

    release = threading.Event()
    ok, value, elapsed_ms = diagnostic._bounded_call(
        lambda: release.wait(1.0),
        0.01,
    )
    release.set()

    assert ok is False
    assert isinstance(value, TimeoutError)
    assert elapsed_ms < 500


def test_latest_completed_weekday_skips_weekend() -> None:
    assert diagnostic._latest_completed_weekday(
        datetime(2026, 7, 27, 9, 0)
    ).date().isoformat() == "2026-07-24"
    assert diagnostic._latest_completed_weekday(
        datetime(2026, 7, 24, 9, 0)
    ).date().isoformat() == "2026-07-23"
