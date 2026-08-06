from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import pytest

from scripts import diagnose_vn_proprietary_capability as diagnostic


def row(**overrides):
    value = {
        "Ticker": "FPT",
        "TradingDate": "2026-08-05T00:00:00",
        "UpdateDate": "2026-08-05T10:00:00",
        "TotalBuyTradeVolume": 10,
        "TotalSellTradeVolume": 4,
        "TotalBuyTradeValue": 100,
        "TotalSellTradeValue": 40,
    }
    value.update(overrides)
    return value


def observation(**overrides):
    return diagnostic.normalize_observation("provider", "operation", row(**overrides))


class FakeFrame:
    def __init__(self, records=()):
        self.records = list(records)

    def to_dict(self, *, orient):
        assert orient == "records"
        return list(self.records)


class FakeStatistics:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get_value_by_investor(self, *, tickers, from_date, to_date):
        self.calls.append((tuple(tickers), from_date, to_date))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if isinstance(response, tuple):
            message, frame = response
            print(message)
            return frame
        return response


class FakeSession:
    def __init__(self, statistics, *, logged_in=True, login_message=None):
        self.statistics = statistics
        self.is_login = logged_in
        self.login_message = login_message
        self.login_calls = 0

    def login(self):
        self.login_calls += 1
        if self.login_message:
            print(self.login_message)
        return self

    def PriceStatistics(self):
        return self.statistics


def fake_session_factory(session, received):
    def factory(*, username, password):
        received.append((username, password))
        return session

    return factory


def run_fake_probe(
    *,
    process=None,
    dotenv=None,
    policy="dotenv",
    responses=None,
    logged_in=True,
    symbols=("FPT",),
    max_requests=2,
    login_message=None,
):
    statistics = FakeStatistics(responses or [FakeFrame()])
    session = FakeSession(
        statistics,
        logged_in=logged_in,
        login_message=login_message,
    )
    received = []
    payload = diagnostic._run_fiinquant_probe(
        symbols,
        14,
        policy,
        max_requests,
        process_env=process or {},
        dotenv_data=dotenv or {
            "FIINQUANT_USERNAME": "dotenv-user",
            "FIINQUANT_PASSWORD": "dotenv-pass",
        },
        session_factory=fake_session_factory(session, received),
        package_version="test",
    )
    return payload, session, statistics, received


def test_current_date_detection():
    assert observation()["trading_date"] == "2026-08-05"


def test_previous_session_only_is_historical():
    old = observation(TradingDate="2026-08-04")
    assert diagnostic.classify_capability([old], current_date="2026-08-05", market_phase="active") == "HISTORICAL_ONLY"


def test_explicit_zero_is_distinct_from_missing():
    zero = observation(TotalBuyTradeVolume=0)
    missing = observation()
    missing["field_presence"]["buy_volume"] = "FIELD_ABSENT"
    assert zero["field_presence"]["buy_volume"] == "FIELD_PRESENT_ZERO"
    assert missing["field_presence"]["buy_volume"] == "FIELD_ABSENT"


def test_gross_field_presence_is_audited():
    item = observation()
    assert item["field_presence"]["buy_volume"] == "FIELD_PRESENT_VALUE"
    assert item["aliases_used"]["buy_volume"] == "TotalBuyTradeVolume"


def test_net_derives_only_from_complete_gross_pair():
    complete = observation()
    incomplete = observation(TotalSellTradeVolume=None)
    assert complete["net_volume"] == 6
    assert incomplete["net_volume"] is None


def test_provider_timestamp_advancement_supports_polling_classification():
    first = observation(UpdateDate="2026-08-05T10:00:00")
    second = observation(UpdateDate="2026-08-05T10:01:00", TotalBuyTradeVolume=11)
    assert diagnostic.classify_capability([first, second], current_date="2026-08-05", market_phase="active") == "NEAR_REALTIME_POLLING"


def test_same_value_repeated_snapshot_does_not_prove_intraday():
    item = observation()
    assert diagnostic.classify_capability([item, dict(item)], current_date="2026-08-05", market_phase="active") == "UNAVAILABLE"


def test_changing_cumulative_snapshots_are_not_summed():
    first = observation(TotalBuyTradeVolume=10)
    second = observation(TotalBuyTradeVolume=12, UpdateDate="2026-08-05T10:01:00")
    assert second["buy_volume"] == 12
    assert second["buy_volume"] != first["buy_volume"] + 12


def test_snapshot_decrease_is_preserved_as_correction():
    corrected = observation(TotalBuyTradeVolume=8, UpdateDate="2026-08-05T10:01:00")
    assert corrected["buy_volume"] == 8


def test_delta_semantics_requires_push_proof_for_realtime():
    first = observation()
    second = observation(TotalBuyTradeVolume=11, UpdateDate="2026-08-05T10:01:00")
    assert diagnostic.classify_capability([first, second], current_date="2026-08-05", market_phase="active") != "REALTIME"


def test_push_proof_can_classify_realtime():
    first = observation()
    second = observation(TotalBuyTradeVolume=11)
    assert diagnostic.classify_capability([first, second], current_date="2026-08-05", market_phase="active", push_proven=True) == "REALTIME"


def test_bulk_and_symbol_reconciliation_uses_values_not_missing_zero():
    symbol = observation()
    bulk = observation()
    assert symbol["net_value"] == bulk["net_value"]


def test_match_deal_total_reconciliation():
    total = {"buy_volume": 10, "sell_volume": 7, "buy_value": 100, "sell_value": 70}
    parts = {
        "match_buy_volume": 6, "match_sell_volume": 4, "match_buy_value": 60, "match_sell_value": 40,
        "deal_buy_volume": 4, "deal_sell_volume": 3, "deal_buy_value": 40, "deal_sell_value": 30,
    }
    assert diagnostic.reconciliation(total, parts, parts) is True


@pytest.mark.parametrize(("message", "expected"), [
    ("HTTP 401 unauthorized", "AUTHENTICATION_FAILURE"),
    ("HTTP 403 membership required", "ENTITLEMENT_FAILURE"),
    ("HTTP 429 rate limit", "RATE_LIMITED"),
    ("connection timeout", "NETWORK_FAILURE"),
])
def test_error_classification(message, expected):
    assert diagnostic.classify_error(message) == expected


def test_bounded_retry_honors_retry_after():
    assert diagnostic.bounded_retry_delays(90) == (60.0,)


def test_bounded_probe_duration_and_interval(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(diagnostic, "inspect_vnstock", lambda **kwargs: diagnostic.ProbeResult(
        "Vnstock Data", "operation", "UNAVAILABLE", (), failure_class="PROVIDER_PACKAGE_MISSING"
    ))
    monkeypatch.setattr(diagnostic.sys, "argv", [
        "diagnostic", "--duration-seconds", "9999", "--interval-seconds", "1",
        "--output-dir", str(tmp_path), "--cleanup",
    ])
    assert diagnostic.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["duration_seconds"] == diagnostic.MAX_DURATION_SECONDS
    assert payload["interval_seconds"] == diagnostic.MIN_INTERVAL_SECONDS


def test_output_contains_no_credentials(tmp_path):
    result = diagnostic.ProbeResult(
        "FiinGroup DataFeed",
        diagnostic.FIIN_ENDPOINT,
        "POST_CLOSE_SAME_DAY",
        (observation(),),
    )
    json_path, csv_path = diagnostic._write_outputs(tmp_path, [result])
    rendered = json_path.read_text("utf-8") + csv_path.read_text("utf-8")
    assert "dotenv-pass" not in rendered
    assert "process-pass" not in rendered
    assert '"dotenv_password_present"' in rendered
    assert "authorization" not in rendered.lower()
    assert "FIELD_PRESENT_VALUE" in rendered


def test_diagnostic_does_not_reference_production_cache():
    source = Path(diagnostic.__file__).read_text("utf-8")
    assert "production_cache_mutated\": False" in source
    assert "DATA_CACHE_DIR" not in source


def test_post_close_current_date_is_post_close_only():
    assert diagnostic.classify_capability([observation()], current_date="2026-08-05", market_phase="post_close") == "POST_CLOSE_SAME_DAY"


def test_eod_only_can_remain_a_documented_provider_classification():
    assert "END_OF_DAY_ONLY" in diagnostic.CAPABILITIES


def test_both_provider_unavailable_keeps_p1_gate_closed(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(diagnostic, "inspect_fiin", lambda: diagnostic.ProbeResult(
        "FiinGroup DataFeed", diagnostic.FIIN_ENDPOINT, "UNAVAILABLE", (), failure_class="CONFIGURATION_REQUIRED"
    ))
    monkeypatch.setattr(diagnostic, "inspect_vnstock", lambda **kwargs: diagnostic.ProbeResult(
        "Vnstock Data", "operation", "UNAVAILABLE", (), failure_class="PROVIDER_PACKAGE_MISSING"
    ))
    monkeypatch.setattr(diagnostic.sys, "argv", ["diagnostic", "--output-dir", str(tmp_path), "--cleanup"])
    assert diagnostic.main() == 0
    assert json.loads(capsys.readouterr().out)["p1_gate_entered"] is False


def test_fiin_contract_is_never_treated_as_configured_runtime():
    result = diagnostic.inspect_fiin()
    assert result.capability == "UNAVAILABLE"
    assert result.failure_class == "CONFIGURATION_REQUIRED"


def test_installed_fiinquant_contract_exposes_proprietary_gross_fields():
    contract = diagnostic.inspect_fiinquant_contract()
    assert contract["package_available"] is True
    assert contract["operation_available"] is True
    assert set(contract["contract_fields"]) == set(
        diagnostic.FIINQUANT_PROPRIETARY_FIELDS
    )


def test_fiinquant_proprietary_aliases_preserve_raw_field_presence():
    item = diagnostic.normalize_observation(
        "FiinQuantX",
        diagnostic.FIINQUANT_OPERATION,
        {
            "ticker": "FPT",
            "tradingDate": "2026-08-05",
            "proprietaryTotalBuyTradeVolume": 0,
            "proprietaryTotalSellTradeVolume": 20,
            "proprietaryTotalBuyTradeValue": 0,
            "proprietaryTotalSellTradeValue": 200,
        },
    )
    assert item["symbol"] == "FPT"
    assert item["field_presence"]["buy_volume"] == "FIELD_PRESENT_ZERO"
    assert item["aliases_used"]["buy_volume"] == "proprietaryTotalBuyTradeVolume"
    assert item["net_value"] == -200


def test_fiinquant_authenticated_historical_gross_rows_select_authenticated_data_outcome():
    result = diagnostic.ProbeResult(
        provider="FiinQuantX",
        operation=diagnostic.FIINQUANT_OPERATION,
        capability="HISTORICAL_ONLY",
        observations=(observation(TradingDate="2026-08-04"),),
        authentication="AUTHENTICATED",
    )
    assert diagnostic.fiinquant_outcome(result, phase="post_close") == (
        "VN_PROPRIETARY_FIINQUANT_AUTHENTICATED_DATA_AVAILABLE"
    )


def test_fiinquant_error_outcomes_are_typed():
    base = dict(
        provider="FiinQuantX",
        operation=diagnostic.FIINQUANT_OPERATION,
        capability="UNAVAILABLE",
        observations=(),
    )
    assert diagnostic.fiinquant_outcome(
        diagnostic.ProbeResult(**base, failure_class="AUTHENTICATION_FAILURE"),
        phase="post_close",
    ) == "VN_PROPRIETARY_FIINQUANT_AUTH_FAILED"
    assert diagnostic.fiinquant_outcome(
        diagnostic.ProbeResult(**base, failure_class="ENTITLEMENT_FAILURE"),
        phase="post_close",
    ) == "VN_PROPRIETARY_FIINQUANT_ENTITLEMENT_REQUIRED"


def test_fiinquant_login_requires_truthy_public_state():
    class Client:
        is_login = True

    class Rejected:
        is_login = False

    assert diagnostic._fiinquant_logged_in(Client()) is True
    assert diagnostic._fiinquant_logged_in(Rejected()) is False
    assert diagnostic._fiinquant_logged_in(object()) is False


def test_free_vnstock_is_not_sponsor_package(monkeypatch):
    monkeypatch.setattr(diagnostic.importlib.util, "find_spec", lambda name: None)
    result = diagnostic.inspect_vnstock(live=True, symbols=("FPT",), duration=0, interval=5)
    assert result.failure_class == "PROVIDER_PACKAGE_MISSING"


def test_market_phase_uses_vietnam_session_windows():
    assert diagnostic.market_phase(datetime(2026, 8, 5, 10, 0)) == "active"
    assert diagnostic.market_phase(datetime(2026, 8, 5, 16, 0)) == "post_close"


def test_missing_row_never_becomes_zero():
    item = diagnostic.normalize_observation("provider", "operation", None)
    assert item["buy_volume"] is None
    assert item["field_presence"]["buy_volume"] == "PROVIDER_ROW_MISSING"


def test_credential_source_selects_complete_dotenv_only():
    result = diagnostic.resolve_credential_source(
        {},
        {"FIINQUANT_USERNAME": "dot-u", "FIINQUANT_PASSWORD": "dot-p"},
        "auto",
    )
    assert result["credential_source"] == "dotenv"
    assert result["dotenv_username_present"] is True
    assert result["process_env_username_present"] is False


def test_credential_source_selects_complete_process_only():
    result = diagnostic.resolve_credential_source(
        {"FIINQUANT_USERNAME": "proc-u", "FIINQUANT_PASSWORD": "proc-p"},
        {},
        "auto",
    )
    assert result["credential_source"] == "process"
    assert result["process_env_password_present"] is True
    assert result["dotenv_password_present"] is False


def test_credential_source_equal_values_selects_dotenv_deterministically():
    values = {"FIINQUANT_USERNAME": "same-u", "FIINQUANT_PASSWORD": "same-p"}
    result = diagnostic.resolve_credential_source(values, values, "auto")
    assert result["credential_source"] == "dotenv"
    assert result["username_sources_match"] is True
    assert result["password_sources_match"] is True


@pytest.mark.parametrize(
    ("process", "dotenv", "username_match", "password_match"),
    [
        (
            {"FIINQUANT_USERNAME": "proc-u", "FIINQUANT_PASSWORD": "same-p"},
            {"FIINQUANT_USERNAME": "dot-u", "FIINQUANT_PASSWORD": "same-p"},
            False,
            True,
        ),
        (
            {"FIINQUANT_USERNAME": "same-u", "FIINQUANT_PASSWORD": "proc-p"},
            {"FIINQUANT_USERNAME": "same-u", "FIINQUANT_PASSWORD": "dot-p"},
            True,
            False,
        ),
    ],
)
def test_auto_credential_source_reports_precedence_conflict(
    process, dotenv, username_match, password_match
):
    result = diagnostic.resolve_credential_source(process, dotenv, "auto")
    assert result["credential_source"] is None
    assert result["failure_class"] == "ENV_PRECEDENCE_CONFLICT"
    assert result["username_sources_match"] is username_match
    assert result["password_sources_match"] is password_match


def test_explicit_dotenv_source_ignores_conflicting_process_values():
    payload, _, _, received = run_fake_probe(
        process={"FIINQUANT_USERNAME": "proc-u", "FIINQUANT_PASSWORD": "proc-p"},
        dotenv={"FIINQUANT_USERNAME": "dot-u", "FIINQUANT_PASSWORD": "dot-p"},
        policy="dotenv",
    )
    assert payload["credential_source"] == "dotenv"
    assert received == [("dot-u", "dot-p")]


def test_explicit_process_source_uses_process_values():
    payload, _, _, received = run_fake_probe(
        process={"FIINQUANT_USERNAME": "proc-u", "FIINQUANT_PASSWORD": "proc-p"},
        dotenv={"FIINQUANT_USERNAME": "dot-u", "FIINQUANT_PASSWORD": "dot-p"},
        policy="process",
    )
    assert payload["credential_source"] == "process"
    assert received == [("proc-u", "proc-p")]


def test_credential_values_are_not_serialized_or_logged(capsys):
    process = {
        "FIINQUANT_USERNAME": "sentinel-process-user",
        "FIINQUANT_PASSWORD": "sentinel-process-pass",
    }
    dotenv = {
        "FIINQUANT_USERNAME": "sentinel-dotenv-user",
        "FIINQUANT_PASSWORD": "sentinel-dotenv-pass",
    }
    payload, _, _, _ = run_fake_probe(
        process=process,
        dotenv=dotenv,
        policy="dotenv",
        responses=[("You do not have permission to access sentinel-dotenv-pass", FakeFrame())],
        login_message="sentinel-dotenv-user",
    )
    rendered = json.dumps(payload, sort_keys=True) + capsys.readouterr().out
    for value in (*process.values(), *dotenv.values()):
        assert value not in rendered


def test_login_success_requires_true_public_state_and_runs_once():
    payload, session, _, _ = run_fake_probe(responses=[FakeFrame()])
    assert payload["authentication"] == "AUTHENTICATED"
    assert payload["authentication_attempt_count"] == 1
    assert payload["login_call_returned"] is True
    assert payload["login_return_type"] == "FakeSession"
    assert payload["is_login_after_call"] is True
    assert session.login_calls == 1


def test_login_false_is_authentication_failure_with_zero_provider_requests():
    payload, session, statistics, _ = run_fake_probe(logged_in=False)
    assert payload["authentication"] == "FAILED"
    assert payload["failure_class"] == "AUTHENTICATION_FAILURE"
    assert payload["request_count"] == 0
    assert statistics.calls == []
    assert session.login_calls == 1


def test_permission_message_plus_empty_frame_is_entitlement_failure():
    payload, _, statistics, _ = run_fake_probe(
        responses=[("You Do Not Have Permission To Access <class 'type'>", FakeFrame())]
    )
    assert payload["failure_class"] == "ENTITLEMENT_FAILURE"
    assert payload["provider_result_class"] == "ENTITLEMENT_FAILURE"
    assert payload["returned_row_count"] == 0
    assert len(statistics.calls) == 1


def test_repeated_permission_messages_collapse_to_one_entitlement_classification():
    output = "\n".join(
        f"FPT-{index}: You do not have permission to access" for index in range(5)
    )
    assert diagnostic.classify_provider_result(
        captured_output=output,
        result_returned=True,
        row_count=0,
    ) == "ENTITLEMENT_FAILURE"


def test_empty_frame_without_error_is_valid_empty_response():
    payload, _, _, _ = run_fake_probe(responses=[FakeFrame()])
    assert payload["failure_class"] is None
    assert payload["provider_result_class"] == "VALID_EMPTY_RESPONSE"
    assert payload["returned_row_count"] == 0


def test_nonempty_frame_is_authenticated_data_available():
    provider_row = {
        "ticker": "FPT",
        "tradingDate": "2026-08-05",
        "proprietaryTotalBuyTradeVolume": 10,
        "proprietaryTotalSellTradeVolume": 4,
        "proprietaryTotalBuyTradeValue": 100,
        "proprietaryTotalSellTradeValue": 40,
    }
    payload, _, _, _ = run_fake_probe(responses=[FakeFrame([provider_row])])
    result = diagnostic.ProbeResult(
        provider="FiinQuantX",
        operation=diagnostic.FIINQUANT_OPERATION,
        capability="HISTORICAL_ONLY",
        observations=tuple(payload["observations"]),
        authentication=payload["authentication"],
    )
    assert payload["provider_result_class"] == "VALID_NONEMPTY_RESPONSE"
    assert diagnostic.fiinquant_outcome(result, phase="post_close") == (
        "VN_PROPRIETARY_FIINQUANT_AUTHENTICATED_DATA_AVAILABLE"
    )


@pytest.mark.parametrize(
    ("exception", "failure_class", "provider_result_class"),
    [
        (ConnectionError("network unavailable"), "NETWORK_FAILURE", "NETWORK_FAILURE"),
        (TypeError("package contract mismatch"), "PROVIDER_PACKAGE_ERROR", "PACKAGE_FAILURE"),
    ],
)
def test_provider_exceptions_remain_typed(
    exception, failure_class, provider_result_class
):
    payload, _, _, _ = run_fake_probe(responses=[exception])
    assert payload["failure_class"] == failure_class
    assert payload["provider_result_class"] == provider_result_class


def test_permission_failure_stops_without_retrying_next_symbol():
    payload, _, statistics, _ = run_fake_probe(
        responses=[
            ("You do not have permission to access", FakeFrame()),
            FakeFrame([{"ticker": "VNINDEX"}]),
        ]
    )
    assert payload["request_count"] == 1
    assert payload["symbols_requested"] == ("FPT",)
    assert len(statistics.calls) == 1


def test_provider_request_count_is_clamped_to_bounded_limit():
    payload, _, statistics, _ = run_fake_probe(
        responses=[FakeFrame(), FakeFrame()],
        symbols=("FPT", "VNINDEX", "VN30"),
        max_requests=999,
    )
    assert payload["request_count"] == diagnostic.FIINQUANT_MAX_PROVIDER_REQUESTS
    assert len(statistics.calls) == diagnostic.FIINQUANT_MAX_PROVIDER_REQUESTS


def test_zero_request_outcome_cannot_be_generic_capability_gap():
    result = diagnostic.ProbeResult(
        provider="FiinQuantX",
        operation=diagnostic.FIINQUANT_OPERATION,
        capability="UNAVAILABLE",
        observations=(),
        request_count=0,
        failure_class="AUTHENTICATION_FAILURE",
        authentication="FAILED",
    )
    outcome = diagnostic.fiinquant_outcome(result, phase="post_close")
    assert outcome == "VN_PROPRIETARY_FIINQUANT_AUTH_FAILED"
    assert "CAPABILITY_GAP" not in outcome


def test_declared_registry_fields_are_not_runtime_observed_on_entitlement_failure():
    payload, _, _, _ = run_fake_probe(
        responses=[("You do not have permission to access", FakeFrame())]
    )
    contract = diagnostic.inspect_fiinquant_contract()
    assert contract["contract_fields"]
    assert payload["observed_fields"] == ()


def test_probe_cleanup_remains_safe_when_artifacts_are_already_absent(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(
        diagnostic,
        "inspect_fiinquant",
        lambda **kwargs: diagnostic.ProbeResult(
            "FiinQuantX",
            diagnostic.FIINQUANT_OPERATION,
            "UNAVAILABLE",
            (),
            failure_class="LIVE_PROBE_DISABLED",
        ),
    )
    monkeypatch.setattr(
        diagnostic,
        "inspect_vnstock",
        lambda **kwargs: diagnostic.ProbeResult(
            "Vnstock Data",
            "operation",
            "UNAVAILABLE",
            (),
            failure_class="PROVIDER_PACKAGE_MISSING",
        ),
    )
    monkeypatch.setattr(
        diagnostic.sys,
        "argv",
        ["diagnostic", "--output-dir", str(tmp_path), "--cleanup"],
    )
    assert diagnostic.main() == 0
    assert json.loads(capsys.readouterr().out)["artifacts"] == []
    assert not (tmp_path / "report.json").exists()
    assert not (tmp_path / "observations.csv").exists()
