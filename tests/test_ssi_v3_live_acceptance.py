"""Offline guards and call-budget tests for the SSI V3 live acceptance tool."""

from __future__ import annotations

from datetime import date
import json
from types import SimpleNamespace
from typing import Any, Dict, Optional

from scripts.verify_ssi_v3_rest_access import (
    LIVE_GUARD_ENV,
    run_acceptance,
)


def config(**overrides: Any) -> SimpleNamespace:
    values = {
        "ssi_fastconnect_rest_version": "v3",
        "ssi_v3_rest_enabled": True,
        "ssi_v3_client_id": None,
        "ssi_v3_api_key": "<api-key>",
        "ssi_v3_api_secret": "<api-secret>",
        "ssi_v3_api_url": "https://api.ssi.com.vn/api/v3",
        "ssi_v3_request_timeout": 30,
        "ssi_v3_retry_delay": 1.0,
        "ssi_v3_rate_limit_per_second": 5,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def ok_results() -> Dict[str, Dict[str, Any]]:
    return {
        "securities": {
            "status": "ok",
            "rows": [{"symbol": "FPT", "exchange": "HOSE"}],
            "pages_used": 1,
        },
        "ohlc": {
            "status": "ok",
            "rows": [
                {
                    "date": "2026-07-21",
                    "open": 1,
                    "high": 2,
                    "low": 1,
                    "close": 2,
                    "volume": 3,
                }
            ],
            "pages_used": 1,
        },
        "summary": {
            "status": "ok",
            "rows": [
                {
                    "symbol": "FPT",
                    "date": "2026-07-21",
                    "foreign_buy_volume": 1,
                    "foreign_sell_volume": 0,
                    "foreign_buy_value": 2,
                    "foreign_sell_value": 0,
                    "_foreign_net_volume_source": "derived",
                    "_foreign_net_value_source": "derived",
                }
            ],
            "pages_used": 1,
        },
        "indexes": {
            "status": "ok",
            "rows": [{"index_code": "VNINDEX", "exchange": "HOSE"}],
            "pages_used": 1,
        },
    }


class FakeAdapter:
    def __init__(
        self,
        settings: Any,
        *,
        authentication: Optional[Dict[str, Any]] = None,
        results: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        self.settings = settings
        self.authentication = authentication or {
            "status": "ok",
            "rows": [],
            "diagnostics": {"capability": "authentication"},
        }
        self.results = results or ok_results()
        self.calls: list[Any] = []
        self.close_calls = 0

    def initialize_rest_access(self) -> Dict[str, Any]:
        self.calls.append(("authenticate",))
        return self.authentication

    def get_security_basic_info(self, symbol: str) -> Dict[str, Any]:
        self.calls.append(("securities", symbol))
        return self.results["securities"]

    def get_daily_ohlcv(self, symbol: str, **kwargs: Any) -> Dict[str, Any]:
        self.calls.append(("ohlc", symbol, kwargs))
        return self.results["ohlc"]

    def get_securities_summary(self, **kwargs: Any) -> Dict[str, Any]:
        self.calls.append(("summary", kwargs))
        return self.results["summary"]

    def get_index_list(self, board: str) -> Dict[str, Any]:
        self.calls.append(("indexes", board))
        return self.results["indexes"]

    def close(self) -> None:
        self.close_calls += 1


def test_default_mode_is_not_run_and_never_constructs_adapter() -> None:
    def forbidden_factory(_settings: Any) -> Any:
        raise AssertionError("adapter construction would permit network")

    report = run_acceptance(
        config=config(),
        requested_live=False,
        environment={LIVE_GUARD_ENV: "true"},
        adapter_factory=forbidden_factory,
    )

    assert report["outcome"] == "G"
    assert report["totals"] == {
        "authentication_count": 0,
        "data_operation_count": 0,
        "successful_data_operations": 0,
    }


def test_environment_guard_and_required_credentials_are_independent() -> None:
    factory_calls = 0

    def forbidden_factory(_settings: Any) -> Any:
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError

    missing_guard = run_acceptance(
        config=config(),
        requested_live=True,
        environment={},
        adapter_factory=forbidden_factory,
    )
    missing_secret = run_acceptance(
        config=config(ssi_v3_api_secret=None),
        requested_live=True,
        environment={LIVE_GUARD_ENV: "true"},
        adapter_factory=forbidden_factory,
    )

    assert missing_guard["outcome"] == missing_secret["outcome"] == "G"
    assert factory_calls == 0


def test_live_acceptance_uses_one_auth_four_bounded_operations_and_closes() -> None:
    created: list[FakeAdapter] = []

    def factory(settings: Any) -> FakeAdapter:
        adapter = FakeAdapter(settings)
        created.append(adapter)
        return adapter

    report = run_acceptance(
        config=config(),
        requested_live=True,
        environment={LIVE_GUARD_ENV: "true"},
        adapter_factory=factory,
        today=date(2026, 7, 22),
    )

    adapter = created[0]
    assert report["outcome"] == "A"
    assert report["client_id_supplied"] is False
    assert report["totals"] == {
        "authentication_count": 1,
        "data_operation_count": 4,
        "successful_data_operations": 4,
    }
    assert [call[0] for call in adapter.calls] == [
        "authenticate",
        "securities",
        "ohlc",
        "summary",
        "indexes",
    ]
    assert adapter.close_calls == 1
    assert adapter.settings.client_id is None
    assert adapter.settings.max_retries == 0
    assert adapter.settings.request_timeout == 10
    assert adapter.calls[2][2] == {
        "from_date": "2026-07-07",
        "to_date": "2026-07-21",
        "limit": 20,
    }
    assert adapter.calls[3][1] == {
        "symbol": "FPT",
        "from_date": "2026-07-07",
        "to_date": "2026-07-21",
        "page_index": 1,
        "page_size": 20,
        "limit": 20,
    }


def test_auth_failure_stops_before_all_data_operations() -> None:
    created: list[FakeAdapter] = []

    def factory(settings: Any) -> FakeAdapter:
        adapter = FakeAdapter(
            settings,
            authentication={
                "status": "unavailable",
                "failure_class": "authentication_failed",
                "rows": [],
                "diagnostics": {
                    "http_status": 401,
                    "exception_class": "AuthenticationError",
                },
            },
        )
        created.append(adapter)
        return adapter

    report = run_acceptance(
        config=config(),
        requested_live=True,
        environment={LIVE_GUARD_ENV: "true"},
        adapter_factory=factory,
    )

    assert report["outcome"] == "C"
    assert report["totals"]["authentication_count"] == 1
    assert report["totals"]["data_operation_count"] == 0
    assert created[0].calls == [("authenticate",)]
    assert created[0].close_calls == 1


def test_authenticated_entitlement_failure_is_outcome_e_and_stays_bounded() -> None:
    results = ok_results()
    results["summary"] = {
        "status": "unavailable",
        "failure_class": "entitlement_unavailable",
        "rows": [],
        "diagnostics": {"http_status": 403, "exception_class": "AuthenticationError"},
    }

    report = run_acceptance(
        config=config(),
        requested_live=True,
        environment={LIVE_GUARD_ENV: "true"},
        adapter_factory=lambda settings: FakeAdapter(settings, results=results),
    )

    assert report["outcome"] == "E"
    assert report["totals"]["data_operation_count"] == 4
    summary = next(item for item in report["operations"] if item["name"] == "securities_summary_fpt")
    assert summary["http_status"] == 403


def test_empty_successful_data_is_partial_outcome_b() -> None:
    results = ok_results()
    results["ohlc"] = {"status": "ok", "rows": [], "pages_used": 1}

    report = run_acceptance(
        config=config(),
        requested_live=True,
        environment={LIVE_GUARD_ENV: "true"},
        adapter_factory=lambda settings: FakeAdapter(settings, results=results),
    )

    assert report["outcome"] == "B"


def test_empty_client_id_sdk_validation_block_is_outcome_d_without_network() -> None:
    report = run_acceptance(
        config=config(),
        requested_live=True,
        environment={LIVE_GUARD_ENV: "true"},
        adapter_factory=lambda _settings: (_ for _ in ()).throw(
            ValueError("SDK rejected empty client ID")
        ),
    )

    assert report["outcome"] == "D"
    assert report["totals"]["authentication_count"] == 0
    assert report["lifecycle_close_status"] == "not_created"


def test_auth_network_failure_is_outcome_f() -> None:
    report = run_acceptance(
        config=config(),
        requested_live=True,
        environment={LIVE_GUARD_ENV: "true"},
        adapter_factory=lambda settings: FakeAdapter(
            settings,
            authentication={
                "status": "unavailable",
                "failure_class": "network_error",
                "rows": [],
                "diagnostics": {"exception_class": "ConnectError"},
            },
        ),
    )

    assert report["outcome"] == "F"
    assert report["totals"]["data_operation_count"] == 0


def test_report_contains_only_aggregates_not_raw_provider_values_or_secrets() -> None:
    secret_config = config(
        ssi_v3_api_key="sensitive-api-key-value",
        ssi_v3_api_secret="sensitive-api-secret-value",
    )
    report = run_acceptance(
        config=secret_config,
        requested_live=True,
        environment={LIVE_GUARD_ENV: "true"},
        adapter_factory=lambda settings: FakeAdapter(settings),
    )
    rendered = json.dumps(report, sort_keys=True)

    assert "sensitive-api-key-value" not in rendered
    assert "sensitive-api-secret-value" not in rendered
    assert '"foreign_buy_value": 2' not in rendered
    summary = next(item for item in report["operations"] if item["name"] == "securities_summary_fpt")
    assert summary["foreign_field_counts"]["complete_gross_volume_pair_rows"] == 1
    assert report["constraints"]["v2_calls"] == 0
    assert report["constraints"]["fallback_used"] is False
