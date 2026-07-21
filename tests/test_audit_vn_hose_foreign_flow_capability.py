from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "audit_vn_hose_foreign_flow_capability.py"


def load_module():
    spec = importlib.util.spec_from_file_location("audit_vn_hose_foreign_flow_capability", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def audit():
    return load_module()


def row(symbol, exchange="HOSE", security_type="common stock", **extra):
    return {"symbol": symbol, "exchange": exchange, "security_type": security_type, **extra}


def test_import_is_safe_and_has_no_live_fetcher(monkeypatch, tmp_path):
    before = set(tmp_path.iterdir())
    module = load_module()
    assert set(tmp_path.iterdir()) == before
    assert "SsiFastConnectFetcher" not in module.__dict__


@pytest.mark.parametrize(
    ("raw", "expected", "status"),
    [
        ("common stock", "common_stock", "verified"),
        ("ETF", "etf", "verified"),
        ("covered warrant", "covered_warrant", "verified"),
        ("fund", "fund", "verified"),
        ("bond", "bond", "verified"),
        ("future", "derivative", "verified"),
        ("preferred stock", "preferred_stock", "verified"),
        ("mystery", "other", "unrecognized"),
        (None, "unknown", "missing"),
    ],
)
def test_security_type_classification(audit, raw, expected, status):
    assert audit.classify_security_type(raw) == (expected, status)


def test_universe_is_hose_only_sorted_deduped_and_conservative(audit):
    result = audit.normalize_universe_rows(
        [
            row("bbb", "HSX"),
            row("AAA", "HOSE"),
            row("AAA", "HOSE"),
            row("ETF1", "HOSE", "ETF"),
            row("CW1", "HOSE", "covered warrant"),
            row("HNX1", "HNX"),
            row("bad symbol", "HOSE"),
        ]
    )
    assert result["authority"] is True
    assert result["eligible_symbols"] == ["AAA", "BBB"]
    assert result["duplicate_rows"] == 1
    assert result["invalid_symbol_rows"] == 1
    assert result["non_hose_rows"] == 1
    assert result["etf_count"] == 1
    assert result["covered_warrant_count"] == 1


def test_unknown_or_conflicting_type_blocks_authority(audit):
    missing = audit.normalize_universe_rows([row("AAA", security_type=None)])
    conflict = audit.normalize_universe_rows([row("AAA"), row("AAA", security_type="ETF")])
    assert missing["authority"] is False
    assert missing["missing_security_type_count"] == 1
    assert conflict["authority"] is False
    assert conflict["ambiguous_type_count"] == 1


def test_missing_exchange_is_not_included(audit):
    result = audit.normalize_universe_rows([row("AAA", exchange=None)])
    assert result["normalized_rows"] == 0
    assert result["missing_exchange_count"] == 1
    assert result["authority"] is False


def test_sdk_model_is_single_symbol_and_no_bulk_candidate(audit):
    result = audit.inspect_sdk_capability()
    assert result["installed"] is True
    assert "symbol" in result["daily_stock_price_fields"]
    assert "symbols" not in result["daily_stock_price_fields"]
    assert result["bulk_candidate_count"] == 0
    assert result["bulk_state"] == "unsupported"


def test_bulk_page_assessment_accepts_complete_identity_safe_pages(audit):
    pages = [
        {"rows": [{"symbol": "AAA", "date": "2026-07-20", "market": "HOSE"}], "total": 2},
        {"rows": [{"symbol": "BBB", "date": "2026-07-20", "market": "HSX"}], "total": 2},
    ]
    result = audit.assess_bulk_pages(pages, page_size=1)
    assert result["state"] == "verified"
    assert result["unique_symbol_count"] == 2
    assert result["unique_date_count"] == 1
    assert result["truncation_detected"] is False


@pytest.mark.parametrize(
    "pages,reason_key",
    [
        ([{"rows": [{"date": "2026-07-20", "market": "HOSE"}]}], "missing_identity_rows"),
        ([{"rows": [{"symbol": "AAA", "date": "2026-07-20", "market": "HNX"}]}], "mismatched_market_rows"),
        ([{"rows": [{"symbol": "AAA", "date": "2026-07-20", "market": "HOSE"}], "total": 2}], "truncation_detected"),
    ],
)
def test_bulk_page_assessment_rejects_unsafe_identity_or_truncation(audit, pages, reason_key):
    result = audit.assess_bulk_pages(pages, page_size=100)
    assert result["state"] == "rejected"
    assert result[reason_key]


def test_bulk_page_assessment_dedupes_pages(audit):
    item = {"symbol": "AAA", "date": "2026-07-20", "market": "HOSE"}
    result = audit.assess_bulk_pages([{"rows": [item, item], "total": 1}], page_size=100)
    assert result["duplicate_rows"] == 1
    assert result["accepted_row_count"] == 1


def test_bulk_provider_rate_limit_is_rejected(audit):
    result = audit.assess_bulk_pages([{"status": "unavailable", "code": 429}], page_size=100)
    assert result == {"state": "rejected", "failure_class": "rate_limited", "safe_to_use": False}


def test_even_sampling_is_deterministic_and_not_prefix_biased(audit):
    symbols = [f"S{index:03d}" for index in range(120)]
    first = audit.select_even_sample(symbols, 10)
    assert first == audit.select_even_sample(reversed(symbols), 10)
    assert first[0] == "S000"
    assert first[-1] == "S119"
    assert first != symbols[:10]


def test_sampling_validation(audit):
    with pytest.raises(ValueError, match="one of"):
        audit.select_even_sample(["AAA"] * 100, 5)
    with pytest.raises(ValueError, match="exceeds"):
        audit.select_even_sample(["AAA"], 10)


def test_measurement_counts_coverage_failures_dates_and_span(audit):
    payloads = {
        "AAA": {"status": "ok", "rows": [{"date": "2026-07-20", "foreign_net_value": 0, "foreign_net_volume": 0}]},
        "BBB": {"status": "ok", "rows": [{"date": "2026-07-19", "foreign_net_value": 1, "foreign_net_volume": None}]},
        "CCC": {"status": "unavailable", "code": 429},
    }
    result = audit.measure_symbol_sample(["AAA", "BBB", "CCC"], 1, lambda symbol, _: payloads[symbol])
    assert result["provider_call_count"] == 3
    assert result["success_count"] == 2
    assert result["partial_count"] == 1
    assert result["unavailable_count"] == 1
    assert result["value_covered_count"] == 2
    assert result["volume_covered_count"] == 1
    assert result["rate_limit_count"] == 1
    assert result["latest_date_distribution"] == {"2026-07-19": 1, "2026-07-20": 1}
    assert result["capture_span_seconds"] >= 0


def test_measurement_sanitizes_unhandled_exception(audit):
    result = audit.measure_symbol_sample(["AAA"], 1, lambda *_: (_ for _ in ()).throw(RuntimeError("secret body")))
    assert result["unhandled_failure_count"] == 1
    assert "secret body" not in json.dumps(result)


def test_projection_is_explicitly_projected(audit):
    projected = audit.project_full_universe({"sample_size": 10, "total_duration_seconds": 2, "provider_call_count": 10}, 400)
    assert projected["status"] == "projected"
    assert projected["duration_seconds"] == 80
    assert projected["provider_call_count"] == 400


def evidence(universe=True, bulk=None, full=None):
    return {
        "universe": {"status": "ready", "authority": universe},
        "bulk_capability": bulk or {},
        "full_universe_result": full or {},
    }


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (evidence(bulk={"state": "verified", "safe_to_use": True}), "A"),
        (evidence(full={"status": "measured", "value_coverage_ratio": 1, "volume_coverage_ratio": 1, "rate_limit_count": 0, "unhandled_failure_count": 0, "total_duration_seconds": 10, "repeat_duration_seconds": 2, "capture_span_seconds": 5}), "B"),
        (evidence(full={"status": "measured", "value_coverage_ratio": .97, "volume_coverage_ratio": .96, "rate_limit_count": 0, "unhandled_failure_count": 0, "total_duration_seconds": 120, "repeat_duration_seconds": 10, "capture_span_seconds": 100}), "C"),
        (evidence(full={"status": "measured", "value_coverage_ratio": .5, "volume_coverage_ratio": .5, "rate_limit_count": 1, "unhandled_failure_count": 0, "total_duration_seconds": 400, "repeat_duration_seconds": 20, "capture_span_seconds": 300}), "D"),
        (evidence(universe=False), "E"),
        ({"universe": {"status": "unavailable", "failure_class": "network_error"}}, "F"),
    ],
)
def test_exact_decision_outcomes(audit, payload, code):
    assert audit.decide(payload)["code"] == code


def test_sample_escalation_stops_on_rate_limit_timeout_auth_or_long_projection(audit):
    assert audit.should_escalate_sample({"total_duration_seconds": 2}, 30)
    assert not audit.should_escalate_sample({"rate_limit_count": 1}, 30)
    assert not audit.should_escalate_sample({"timeout_count": 1}, 100)
    assert not audit.should_escalate_sample({"auth_failed_count": 1}, 30)
    assert not audit.should_escalate_sample({"projected_duration_seconds": 301}, 30)


def test_sanitize_removes_secret_keys_and_inline_values(audit):
    value = {
        "accessToken": "token-value",
        "consumer_secret": "secret-value",
        "Authorization": "Bearer token-value",
        "safe": "Bearer: token-value provider result",
    }
    encoded = json.dumps(audit.sanitize(value))
    for secret in ("token-value", "secret-value", "Authorization", "accessToken", "consumer_secret"):
        assert secret not in encoded


def test_cli_config_mode_needs_no_live_provider(audit, monkeypatch, capsys):
    monkeypatch.setattr(audit, "_load_live_fetcher", lambda: pytest.fail("provider constructed"))
    assert audit.main(["--mode", "config"]) == 0
    assert json.loads(capsys.readouterr().out)["network_used"] is False


@pytest.mark.parametrize(
    "argv",
    [
        ["--mode", "universe"],
        ["--mode", "sample", "--allow-live"],
        ["--mode", "config", "--concurrency", "5"],
        ["--mode", "config", "--history-sessions", "3"],
        ["--mode", "config", "--allow-full-universe"],
        ["--mode", "config", "--output", "outside.json"],
    ],
)
def test_invalid_cli_exits_before_provider_construction(audit, monkeypatch, argv):
    monkeypatch.setattr(audit, "_load_live_fetcher", lambda: pytest.fail("provider constructed"))
    with pytest.raises(SystemExit) as exc:
        audit.main(argv)
    assert exc.value.code == 2


def test_bulk_mode_makes_no_speculative_live_attempt(audit, monkeypatch):
    monkeypatch.setattr(audit, "_load_live_fetcher", lambda: pytest.fail("provider constructed"))
    args = audit.build_parser().parse_args(["--mode", "bulk", "--allow-live"])
    audit.validate_args(audit.build_parser(), args)
    result = audit.execute(args)
    assert result["bulk_capability"]["live_attempt_count"] == 0
    assert result["network_used"] is False


def test_type_inventory_is_field_name_only_bounded_and_marks_labels_verified(audit):
    rows = [
        {"Symbol": "AAA", "Market": "HOSE", "InstrumentType": "Common Stock", "IssuerName": "private issuer"},
        {"Symbol": "ETF1", "Market": "HOSE", "InstrumentType": "ETF", "IssuerName": "private issuer 2"},
    ]
    result = audit.inventory_type_fields(rows)
    assert result["raw_field_names"] == ["InstrumentType", "IssuerName", "Market", "Symbol"]
    assert result["candidate_field_count"] == 1
    field = result["candidate_fields"][0]
    assert field["presence_count"] == 2
    assert field["non_null_count"] == 2
    assert field["bounded_distinct_values"] == ["Common Stock", "ETF"]
    assert field["semantic_status"] == "verified"
    assert "private issuer" not in json.dumps(result)


@pytest.mark.parametrize("value", [1, "1", "ST", "CW", "FU"])
def test_numeric_or_coded_type_values_are_not_guessed(audit, value):
    inventory = audit.inventory_type_fields([{"Symbol": "AAA", "Market": "HOSE", "SecurityType": value}])
    assert inventory["candidate_fields"][0]["semantic_status"] == "ambiguous"


def test_authority_requires_all_rows_classified_and_detects_conflicts(audit):
    rows = [
        {"Symbol": "AAA", "Market": "HOSE", "SecurityType": "Common Stock", "InstrumentType": "Common Stock"},
        {"Symbol": "BBB", "Market": "HOSE", "SecurityType": "Common Stock", "InstrumentType": "ETF"},
        {"Symbol": "CCC", "Market": "HOSE"},
    ]
    inventory = audit.inventory_type_fields(rows)
    result = audit.classify_authority_rows(rows, inventory)
    assert result["classified_count"] == 1
    assert result["conflicting_count"] == 1
    assert result["unknown_count"] == 1
    assert result["authority"] is False


def test_complete_explicit_securities_labels_resolve_authority(audit):
    rows = [
        {"Symbol": "AAA", "Market": "HOSE", "SecurityType": "Common Stock"},
        {"Symbol": "ETF1", "Market": "HOSE", "SecurityType": "ETF"},
    ]
    inventory = audit.inventory_type_fields(rows)
    result = audit.classify_authority_rows(rows, inventory)
    assert result["authority"] is True
    assert result["common_stock_count"] == 1
    assert result["etf_count"] == 1


def test_details_stage_requires_one_exact_hose_row_per_symbol(audit):
    payloads = {
        "AAA": {"rows": [{"Symbol": "AAA", "Market": "HOSE", "SecurityType": "Common Stock"}]},
        "BBB": {"rows": [{"Symbol": "OTHER", "Market": "HOSE", "SecurityType": "Common Stock"}]},
    }
    result = audit.run_details_stage(["AAA", "BBB"], lambda symbol: payloads[symbol])
    assert result["attempted_count"] == 2
    assert result["exact_match_count"] == 1
    assert result["exact_symbol_mismatch_count"] == 1
    assert result["authority"] is False
    assert result["stopped_reason"] == "exact_symbol_mismatch"


def test_details_stage_deduplicates_no_symbol_and_enforces_concurrency_bounds(audit):
    with pytest.raises(ValueError, match="normalized and unique"):
        audit.run_details_stage(["AAA", "AAA"], lambda _: {})
    with pytest.raises(ValueError, match="between"):
        audit.run_details_stage(["AAA"], lambda _: {}, concurrency=0)
    with pytest.raises(ValueError, match="between"):
        audit.run_details_stage(["AAA"], lambda _: {}, concurrency=5)


def test_details_rate_limit_stops_before_next_batch(audit):
    calls = []

    def fetch(symbol):
        calls.append(symbol)
        return {"status": "unavailable", "code": 429}

    result = audit.run_details_stage(["AAA", "BBB", "CCC"], fetch, concurrency=1, universe_size=736)
    assert calls == ["AAA"]
    assert result["rate_limit_count"] == 1
    assert result["stopped_reason"] == "rate_limited"


def test_type_stage_escalation_requires_complete_exact_conflict_free_sample(audit):
    complete = {
        "attempted_count": 10,
        "exact_match_count": 10,
        "classified_count": 10,
        "unknown_count": 0,
        "conflicting_count": 0,
        "projected_full_universe_seconds": 100,
    }
    assert audit.should_escalate_type_stage(complete)
    assert not audit.should_escalate_type_stage({**complete, "unknown_count": 1, "classified_count": 9})
    assert not audit.should_escalate_type_stage({**complete, "conflicting_count": 1, "classified_count": 9})
    assert not audit.should_escalate_type_stage({**complete, "rate_limit_count": 1})
    assert not audit.should_escalate_type_stage({**complete, "projected_full_universe_seconds": 301})


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        ({"securities": {"status": "measured", "authority": True}}, "A"),
        ({"securities": {"status": "measured", "authority": False}, "details": {"status": "measured", "full_universe": True, "authority": True, "duration_seconds": 10}}, "B"),
        ({"securities": {"status": "measured", "authority": False}, "details": {"status": "measured", "full_universe": True, "authority": True, "duration_seconds": 120}}, "C"),
        ({"securities": {"status": "measured", "authority": False}, "details": {"status": "measured", "candidate_field_count": 1, "unknown_count": 10}}, "D"),
        ({"securities": {"status": "measured", "authority": False}, "details": {"status": "measured", "rate_limit_count": 1}}, "E"),
        ({"securities": {"status": "unavailable", "failure_class": "network_error"}}, "F"),
    ],
)
def test_type_authority_exact_outcomes(audit, evidence, expected):
    assert audit.decide_type_authority(evidence)["code"] == expected


def test_partial_details_sample_cannot_prove_full_authority(audit):
    decision = audit.decide_type_authority(
        {
            "securities": {"status": "measured", "authority": False},
            "details": {"status": "measured", "full_universe": False, "candidate_field_count": 1, "unknown_count": 0, "conflicting_count": 0},
        }
    )
    assert decision["code"] == "F"
    assert decision["production_gate_open"] is False


def test_details_missing_exact_type_bearing_row_is_inconclusive(audit):
    decision = audit.decide_type_authority(
        {
            "securities": {"status": "measured", "authority": False},
            "details": {"status": "measured", "candidate_field_count": 0, "exact_symbol_mismatch_count": 1},
        }
    )
    assert decision["code"] == "F"


def test_security_type_config_mode_is_no_network_and_plans_zero_daily_stock_price(audit, monkeypatch):
    monkeypatch.setattr(audit, "_load_live_fetcher", lambda: pytest.fail("provider constructed"))
    args = audit.build_parser().parse_args(["--mode", "security-type", "--source", "auto"])
    audit.validate_args(audit.build_parser(), args)
    result = audit.execute(args)
    assert result["network_used"] is False
    assert result["planned_work"]["daily_stock_price_requests"] == 0
    assert result["decision"]["code"] == "F"


def test_security_type_explicit_source_requires_live(audit):
    parser = audit.build_parser()
    args = parser.parse_args(["--mode", "security-type", "--source", "details"])
    with pytest.raises(SystemExit) as exc:
        audit.validate_args(parser, args)
    assert exc.value.code == 2


def test_security_type_live_branch_never_invokes_daily_stock_price(audit, monkeypatch):
    endpoints = []

    class FakeFetcher:
        def _request(self, endpoint, params=None):
            endpoints.append(endpoint)
            return {"rows": [{"Symbol": "AAA", "Market": "HOSE", "StockName": "Name"}]}

        def get_daily_stock_price(self, *args, **kwargs):
            pytest.fail("DailyStockPrice must not be called by security-type mode")

    monkeypatch.setattr(audit, "_load_live_fetcher", FakeFetcher)
    monkeypatch.setattr(audit, "install_live_counters", lambda _: audit.Counter())
    args = audit.build_parser().parse_args(["--mode", "security-type", "--source", "securities", "--allow-live"])
    result = audit.execute(args)
    assert endpoints == ["Securities"]
    assert result["planned_work"]["daily_stock_price_requests"] == 0
