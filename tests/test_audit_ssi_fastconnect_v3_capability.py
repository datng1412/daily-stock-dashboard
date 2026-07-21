"""Deterministic tests for the SSI FastConnect V3 migration-gate audit."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_ssi_fastconnect_v3_capability.py"


def load_audit_module(name: str = "audit_ssi_fastconnect_v3_capability_test") -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def audit() -> ModuleType:
    return load_audit_module()


def test_import_has_no_network_provider_thread_or_file_side_effect(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: calls.append("network"))
    monkeypatch.setattr(Path, "write_text", lambda *args, **kwargs: calls.append("write"))
    module = load_audit_module("audit_ssi_v3_import_safety")

    assert module.DEFAULT_MODE == "config"
    assert calls == []


def test_package_inventory_is_non_importing_and_reports_absence(monkeypatch: pytest.MonkeyPatch, audit: ModuleType) -> None:
    monkeypatch.setattr(audit, "_distribution_version", lambda name: "2.2.2" if name == audit.V2_DISTRIBUTION else None)
    monkeypatch.setattr(audit, "find_spec", lambda name: object() if name == audit.V2_MODULE else None)

    inventory = audit.package_inventory()

    assert inventory["v2"]["installed_version"] == "2.2.2"
    assert inventory["v3"]["installed_version"] is None
    assert inventory["v3"]["module_discoverable"] is False


def test_package_inventory_reports_present_v3_without_installing(monkeypatch: pytest.MonkeyPatch, audit: ModuleType) -> None:
    monkeypatch.setattr(audit, "_distribution_version", lambda name: "3.0.5" if name == audit.V3_DISTRIBUTION else None)
    monkeypatch.setattr(audit, "find_spec", lambda name: object() if name == audit.V3_MODULE else None)

    assert audit.package_inventory()["v3"] == {
        "distribution": "ssi-sdk",
        "module": "ssi_sdk",
        "installed_version": "3.0.5",
        "module_discoverable": True,
        "official_documented_version": "3.0.5",
        "official_python_requirement": ">=3.10",
        "role": "official candidate for an audit or future migration only",
    }


def test_configuration_presence_excludes_values(audit: ModuleType) -> None:
    environment = {
        "SSI_FASTCONNECT_CONSUMER_ID": "v2-id",
        "SSI_FASTCONNECT_CONSUMER_SECRET": "v2-secret",
        "SSI_FASTCONNECT_V3_API_KEY": "v3-key",
        "SSI_FASTCONNECT_V3_API_SECRET": "v3-secret",
        "SSI_FASTCONNECT_V3_AUDIT_SYMBOL": "FPT",
    }

    presence = audit.configuration_presence(environment)

    assert presence["v3_live_minimum_present"] is True
    assert "v3-key" not in repr(presence)
    assert "v3-secret" not in repr(presence)
    assert presence["production_v3_configuration_support"].startswith("absent")


def test_cli_environment_reads_dotenv_presence_without_retaining_values(tmp_path: Path, audit: ModuleType) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("SSI_FASTCONNECT_V3_API_KEY=secret-value\nSSI_FASTCONNECT_V3_AUDIT_SYMBOL=\n", encoding="utf-8")

    environment = audit.cli_environment({}, dotenv)

    assert environment["SSI_FASTCONNECT_V3_API_KEY"] == "configured"
    assert environment["SSI_FASTCONNECT_V3_AUDIT_SYMBOL"] == ""
    assert "secret-value" not in repr(environment)


def test_cli_environment_retains_values_only_for_explicit_live_caller(tmp_path: Path, audit: ModuleType) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("SSI_FASTCONNECT_CONSUMER_ID=current-id\nSSI_FASTCONNECT_CONSUMER_SECRET=current-secret\n", encoding="utf-8")

    environment = audit.cli_environment({}, dotenv, retain_values=True)

    assert environment["SSI_FASTCONNECT_CONSUMER_ID"] == "current-id"
    assert environment["SSI_FASTCONNECT_CONSUMER_SECRET"] == "current-secret"
    assert "current-secret" not in repr(audit.change_impact_report(environment))


def test_current_credential_name_mapping_is_complete_and_value_free(audit: ModuleType) -> None:
    mapping = audit.credential_mapping(
        {
            "SSI_FASTCONNECT_CONSUMER_ID": "current-id",
            "SSI_FASTCONNECT_CONSUMER_SECRET": "current-secret",
        }
    )

    statuses = {row["status"] for row in mapping}
    assert {"reuse_with_name_mapping", "V2_only", "V3_only", "not_required_for_market_data", "unresolved"} <= statuses
    assert sum(row["status"] == "reuse_with_name_mapping" for row in mapping) == 2
    assert "current-id" not in repr(mapping)
    assert "current-secret" not in repr(mapping)


@pytest.mark.parametrize(
    ("text", "secret"),
    [
        ("Authorization: Bearer token-value", "token-value"),
        ("api_key=key-value", "key-value"),
        ("Cookie: session=value", "value"),
        ("accessToken=access-value", "access-value"),
    ],
)
def test_redaction_hides_sensitive_values(audit: ModuleType, text: str, secret: str) -> None:
    assert secret not in audit.redact_text(text, [secret])


def test_sanitize_value_redacts_sensitive_keys_and_raw_payload(audit: ModuleType) -> None:
    cleaned = audit.sanitize_value(
        {
            "api_secret": "never-show",
            "Authorization": "Bearer never-show",
            "raw": {"unexpected": "payload"},
            "safe": {"message": "network unavailable"},
        },
        ["never-show"],
    )

    assert cleaned["api_secret"] == "[redacted]"
    assert cleaned["Authorization"] == "[redacted]"
    assert cleaned["raw"] == "[redacted]"
    assert cleaned["safe"]["message"] == "network unavailable"


def test_contract_mapping_keeps_v3_daily_stock_price_parity_partial(audit: ModuleType) -> None:
    mapping = audit.documented_contracts()["v2_to_v3"]

    assert mapping["DailyStockPrice"]["parity"] == "transformed_partial"
    assert mapping["IndexComponents"]["v3_contract"] == "securitiesByBoard?index=<index>"
    assert "fallback" not in repr(mapping).lower()


def test_all_twenty_subgates_have_valid_statuses(audit: ModuleType) -> None:
    gates = audit.initial_sub_gates()

    assert tuple(gates) == audit.SUB_GATES
    assert len(gates) == 20
    assert {entry["status"] for entry in gates.values()} <= audit.VALID_GATE_STATUSES


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Common Stock", "common_stock"),
        ("ETF", "etf"),
        ("Covered Warrant", "covered_warrant"),
        ("Fund", "fund"),
        ("Bond", "bond"),
        ("Preferred Stock", "preferred_stock"),
        ("7", "unknown"),
        (None, "unknown"),
    ],
)
def test_instrument_type_requires_explicit_semantics(audit: ModuleType, value: object, expected: str) -> None:
    assert audit.classify_instrument_type(value) == expected


def test_instrument_type_allows_only_explicitly_supplied_documented_code_mapping(audit: ModuleType) -> None:
    assert audit.classify_instrument_type("7") == "unknown"
    assert audit.classify_instrument_type("7", documented_mapping={"7": "etf"}) == "etf"


def test_security_master_requires_exact_symbol_board_and_type(audit: ModuleType) -> None:
    row = {"symbol": "FPT", "board": "HOSE", "securityType": "Common Stock"}
    exact = audit.assess_security_master_row(row, "FPT", "HOSE")
    unknown = audit.assess_security_master_row({"symbol": "FPT", "board": "HOSE", "securityType": "7"}, "FPT", "HOSE")
    conflicting = audit.assess_security_master_row({"symbol": "FPT", "board": "HOSE", "type": "ETF", "instrumentType": "Bond"}, "FPT", "HOSE")

    assert exact["hose_common_stock_authoritative"] is True
    assert unknown["hose_common_stock_authoritative"] is False
    assert conflicting["instrument_type"] == "conflicting"


def test_foreign_history_preserves_zero_and_requires_direct_net(audit: ModuleType) -> None:
    normalized = audit.normalize_foreign_history_row(
        {
            "tradingDate": "2026-07-20",
            "totalForeignBuy": 0,
            "totalForeignSell": 2,
            "totalForeignBuyValue": 0,
            "totalForeignSellValue": 4,
            "foreignNetVolume": 0,
            "foreignNetValue": 0,
        }
    )
    missing_net = audit.normalize_foreign_history_row({"totalForeignBuy": 3, "totalForeignSell": 1})

    assert normalized["foreign_buy_volume"] == 0.0
    assert normalized["foreign_net_volume"] == 0.0
    assert normalized["net_source"] == "direct"
    assert normalized["volume_unit"] == "unknown_pending_live_proof"
    assert missing_net["foreign_net_volume"] is None
    assert missing_net["net_source"] == "not_documented"


def test_rate_limit_extraction_uses_only_known_headers(audit: ModuleType) -> None:
    metadata = audit.extract_rate_limit_metadata(
        {"X-RATELIMIT-LIMIT": "10", "x-ratelimit-remaining": "9", "X-RATELIMIT-RESET": "60", "Other": "not-logged"}
    )

    assert metadata == {"limit": "10", "remaining": "9", "reset": "60", "retry_after": None}


def test_one_symbol_parity_preserves_null_zero_and_unverified_units(audit: ModuleType) -> None:
    compared = audit.compare_one_symbol_parity(
        {
            "symbol": "AAA",
            "trading_date": "2026-07-20",
            "foreign_buy_value": None,
            "foreign_sell_value": 0,
            "foreign_buy_volume": 2,
            "foreign_sell_volume": 3,
        },
        {
            "symbol": "AAA",
            "trading_date": "2026-07-20",
            "foreign_buy_value": None,
            "foreign_sell_value": 0,
            "foreign_buy_volume": 2,
            "foreign_sell_volume": 3,
        },
    )

    assert compared["missing_remains_null"] is True
    assert compared["explicit_zero_remains_zero"] is True
    assert compared["unit_compatibility"] == "unverified_until_live_provider_evidence"
    assert compared["scope"].startswith("one_symbol")


def test_index_component_comparison_is_normalized_and_does_not_infer_dates(audit: ModuleType) -> None:
    compared = audit.compare_index_components([" aaa ", "BBB", "AAA"], ["BBB", "AAA"])

    assert compared["exact_symbol_set_match"] is True
    assert compared["v2_count"] == 2
    assert compared["weights"] == "unverified"
    assert compared["effective_or_current_date"] == "unverified"


def test_live_plan_is_bounded_and_rejects_full_market(audit: ModuleType) -> None:
    plan = audit.live_smoke_plan(allow_websocket=True, allow_small_download=True)

    assert plan["authentication_sequences_max"] == 1
    assert plan["websocket_connections_max"] == 1
    assert plan["websocket_timeout_seconds_max"] == 10
    assert plan["small_download_bytes_max"] == 10 * 1024 * 1024
    assert plan["full_market_subscription"] == "rejected"
    assert plan["automatic_retries"] == 0


def test_live_mode_without_explicit_flag_never_calls_network(monkeypatch: pytest.MonkeyPatch, audit: ModuleType) -> None:
    calls: list[str] = []
    monkeypatch.setattr(audit, "_http_json", lambda *args, **kwargs: calls.append("network"))

    result = audit.run_live_smoke({"SSI_FASTCONNECT_V3_API_KEY": "key"}, allow_live=False)

    assert calls == []
    assert "--allow-live" in result["reason"]


def test_live_mode_with_missing_credentials_never_calls_network(monkeypatch: pytest.MonkeyPatch, audit: ModuleType) -> None:
    calls: list[str] = []
    monkeypatch.setattr(audit, "_http_json", lambda *args, **kwargs: calls.append("network"))

    result = audit.run_live_smoke({}, allow_live=True)

    assert calls == []
    assert "must all be present" in result["reason"]


def test_existing_key_auth_success_uses_one_request_and_omits_tokens(monkeypatch: pytest.MonkeyPatch, audit: ModuleType) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_request(url: str, *, method: str, headers: dict[str, str], payload: dict[str, object] | None = None):
        calls.append((url, dict(payload or {})))
        return (
            200,
            {
                "tokenType": "Bearer",
                "accessToken": "never-retain-access",
                "refreshToken": "never-retain-refresh",
                "expiresAt": "later",
                "refreshExpiresAt": "later-still",
            },
            {"X-RATELIMIT-LIMIT": "10", "X-RATELIMIT-REMAINING": "9"},
        )

    monkeypatch.setattr(audit, "_http_json", fake_request)
    result = audit.run_existing_key_auth(
        {
            "SSI_FASTCONNECT_CONSUMER_ID": "current-id",
            "SSI_FASTCONNECT_CONSUMER_SECRET": "current-secret",
        },
        allow_live=True,
    )

    assert len(calls) == 1
    assert calls[0][0] == audit.V3_AUTH_URL
    assert calls[0][1] == {"apiKey": "current-id", "apiSecret": "current-secret"}
    assert result["success"] is True
    assert result["access_token_present"] is True
    assert result["refresh_token_present"] is True
    assert result["rate_limit_headers"]["remaining"] == "9"
    assert "never-retain" not in repr(result)
    assert "current-secret" not in repr(result)


def test_existing_key_auth_explicit_rejection_is_classified_without_retry(monkeypatch: pytest.MonkeyPatch, audit: ModuleType) -> None:
    calls = 0

    def reject(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise audit.HTTPError(audit.V3_AUTH_URL, 403, "forbidden", None, None)

    monkeypatch.setattr(audit, "_http_json", reject)
    result = audit.run_existing_key_auth(
        {"SSI_FASTCONNECT_CONSUMER_ID": "id", "SSI_FASTCONNECT_CONSUMER_SECRET": "secret"},
        allow_live=True,
    )

    assert calls == 1
    assert result["failure_class"] == "credentials_explicitly_rejected"
    assert audit.decide_change_impact_outcome(result, "unverified")[0] == "D"


def test_existing_key_auth_network_error_is_not_credential_rejection(monkeypatch: pytest.MonkeyPatch, audit: ModuleType) -> None:
    monkeypatch.setattr(audit, "_http_json", lambda *args, **kwargs: (_ for _ in ()).throw(audit.URLError("offline")))

    result = audit.run_existing_key_auth(
        {"SSI_FASTCONNECT_CONSUMER_ID": "id", "SSI_FASTCONNECT_CONSUMER_SECRET": "secret"},
        allow_live=True,
    )

    assert result["failure_class"].startswith("network_or_tls_failure")
    assert audit.decide_change_impact_outcome(result, "unverified")[0] == "F"


def test_bounded_live_smoke_uses_one_auth_and_scoped_requests(monkeypatch: pytest.MonkeyPatch, audit: ModuleType) -> None:
    calls: list[tuple[str, str]] = []

    def fake_request(url: str, *, method: str, headers: dict[str, str], payload: dict[str, object] | None = None):
        calls.append((method, url))
        if method == "POST":
            return 200, {"accessToken": "live-token"}, {"X-RATELIMIT-LIMIT": "10"}
        return 200, {"data": []}, {"X-RATELIMIT-REMAINING": "9"}

    monkeypatch.setattr(audit, "_http_json", fake_request)
    result = audit.run_live_smoke(
        {
            "SSI_FASTCONNECT_V3_API_KEY": "key",
            "SSI_FASTCONNECT_V3_API_SECRET": "secret",
            "SSI_FASTCONNECT_V3_AUDIT_SYMBOL": "FPT",
            "SSI_FASTCONNECT_V3_AUDIT_INDEX": "VN30",
        },
        allow_live=True,
    )

    assert result["evidence_level"] == "live_verified"
    assert len(calls) == 4
    assert calls[0][0] == "POST"
    assert all("FPT" not in item[1] or "securities" in item[1] for item in calls[1:])
    assert "live-token" not in repr(result)


@pytest.mark.parametrize(
    ("documentation_available", "live_auth", "critical_contract", "expected"),
    [
        (True, "verified", "verified", "A"),
        (True, "verified", "partial", "B"),
        (True, "not_configured", "partial", "C"),
        (True, "rejected", "partial", "D"),
        (True, "verified", "missing", "E"),
        (False, "not_tested", "partial", "F"),
    ],
)
def test_decision_outcomes_cover_a_through_f(audit: ModuleType, documentation_available: bool, live_auth: str, critical_contract: str, expected: str) -> None:
    assert audit.decide_outcome(
        documentation_available=documentation_available,
        live_auth=live_auth,
        critical_contract=critical_contract,
    )[0] == expected


def test_default_decision_is_exactly_defer_and_keeps_migration_closed(audit: ModuleType) -> None:
    decision = audit.decision_report({})

    assert decision["primary_outcome"]["code"] == "C"
    assert decision["migration_gate"] == "closed"
    assert decision["recommended_next_phase"] == "SSI-V3 access-enablement follow-up"


@pytest.mark.parametrize(
    ("auth", "contract", "expected"),
    [
        ({"success": True, "failure_class": "none"}, "fully_mapped", "A"),
        ({"success": True, "failure_class": "none"}, "partially_mapped_adapter_can_begin", "B"),
        ({"success": True, "failure_class": "none"}, "unverified", "C"),
        ({"success": False, "failure_class": "credentials_explicitly_rejected"}, "unverified", "D"),
        ({"success": True, "failure_class": "none"}, "incompatible", "E"),
        ({"success": False, "failure_class": "network_or_tls_failure:URLError"}, "unverified", "F"),
    ],
)
def test_change_impact_outcomes_cover_exact_a_through_f(audit: ModuleType, auth: dict[str, object], contract: str, expected: str) -> None:
    assert audit.decide_change_impact_outcome(auth, contract)[0] == expected


def test_change_impact_inventory_and_decisions_are_complete(audit: ModuleType) -> None:
    inventory = audit.v2_capability_inventory()
    matrix = audit.change_impact_matrix()
    decisions = set(audit.grouped_migration_decisions(matrix))

    assert {row["method"] for row in inventory} >= {
        "get_daily_ohlcv",
        "get_daily_stock_price",
        "get_index_components",
        "get_realtime_snapshot",
        "get_trade_tape",
    }
    assert len({row["capability"] for row in matrix}) == len(matrix)
    assert all(row["migration_decision"] in decisions for row in matrix)
    assert audit.validate_keep_v2_exit_criteria(matrix) is True
    assert all(row["evidence_level"] for row in matrix if row["migration_decision"] == "V3_NEW_OPTIONAL_CAPABILITY")
    matrix_capabilities = {row["capability"] for row in matrix}
    expected_matrix_row = {
        "authentication": "V2 authentication",
        "daily_ohlcv": "DailyOhlc",
        "daily_stock_price": "DailyStockPrice trading summary",
        "daily_index": "DailyIndex",
        "intraday_ohlcv": "completed-session intraday OHLCV",
        "completed_intraday_1m": "completed-session intraday OHLCV",
        "securities": "Securities universe",
        "securities_details": "SecuritiesDetails metadata",
        "index_list": "IndexList",
        "index_components": "IndexComponents/current VN30 membership",
        "realtime_snapshot": "realtime quote",
        "order_book": "order book",
        "trade_tape": "realtime trade",
        "session_status": "market session/status",
        "foreign_room": "foreign room realtime",
        "market_index_pulse": "market/index stream",
    }
    assert all(expected_matrix_row[row["capability"]] in matrix_capabilities for row in inventory)


def test_change_impact_mode_is_offline_without_flag_and_has_no_full_market_subscription(monkeypatch: pytest.MonkeyPatch, audit: ModuleType) -> None:
    calls: list[str] = []
    monkeypatch.setattr(audit, "_http_json", lambda *args, **kwargs: calls.append("network"))

    report = audit.build_report("change-impact", environment={}, allow_live=False)

    assert calls == []
    assert report["network_attempted"] is False
    assert report["change_impact"]["primary_outcome"]["code"] == "F"
    assert "X:ALL" not in repr(report)
    assert "full-market" not in repr(report).lower()


def test_change_impact_report_sanitized_atomic_output_and_size_bound(tmp_path: Path, audit: ModuleType) -> None:
    output = tmp_path / "impact.json"
    report = audit.change_impact_report(
        {"SSI_FASTCONNECT_CONSUMER_ID": "current-id", "SSI_FASTCONNECT_CONSUMER_SECRET": "current-secret"}
    )

    audit.write_sanitized_report_atomic(output, report)
    retained = output.read_text(encoding="utf-8")

    assert output.exists()
    assert '"primary_outcome"' in retained
    assert "current-id" not in retained
    assert "current-secret" not in retained
    assert not list(tmp_path.glob(".*.tmp"))
    with pytest.raises(ValueError, match="exceeds"):
        audit.render_sanitized_report({"safe": "x" * audit.MAX_REPORT_BYTES})


def test_change_impact_guardrails_prove_no_runtime_switch(audit: ModuleType) -> None:
    guardrails = audit.change_impact_report({})["guardrails"]

    assert guardrails == {
        "production_adapter_implemented": False,
        "production_traffic_switched": False,
        "automatic_fallback_added": False,
        "dependency_or_lockfile_changed": False,
        "environment_file_changed": False,
        "frontend_changed": False,
        "raw_response_persisted": False,
        "token_persisted": False,
    }


def test_report_modes_are_network_free_except_explicit_live(monkeypatch: pytest.MonkeyPatch, audit: ModuleType) -> None:
    calls: list[str] = []
    monkeypatch.setattr(audit, "_http_json", lambda *args, **kwargs: calls.append("network"))

    for mode in ("config", "sdk", "contracts", "decision", "change-impact"):
        report = audit.build_report(mode, environment={})
        assert report["network_attempted"] is False

    assert calls == []


def test_scope_guardrail_source_has_no_dependency_mutation_or_production_provider() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "pip install" not in source
    assert "class SsiFastConnectV3Fetcher" not in source
    assert "def fallback" not in source.lower()
    assert "subprocess" not in source
    assert "os.system" not in source
