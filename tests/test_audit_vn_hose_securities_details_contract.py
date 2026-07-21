from __future__ import annotations

from dataclasses import asdict
import importlib.util
from pathlib import Path
import sys

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "audit_vn_hose_foreign_flow_capability.py"


def load_module():
    spec = importlib.util.spec_from_file_location("audit_vn_hose_details_contract", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def audit():
    return load_module()


def inspect(audit, payload, symbol="AAA", market="HOSE", page_index=1, page_size=1000):
    return audit.inspect_details_response(
        payload,
        requested_symbol=symbol,
        requested_market=market,
        page_index=page_index,
        page_size=page_size,
    )


def test_official_model_serializes_lowercase_keys_and_empty_page_defaults():
    from ssi_fc_data.model.model import securities_details

    assert asdict(securities_details(market="HOSE", symbol="AAA")) == {
        "market": "HOSE",
        "symbol": "AAA",
        "pageIndex": "",
        "pageSize": "",
    }


def test_candidate_positions_are_provider_derived_ten_fifty_ninety_percent(audit):
    symbols = [f"S{index:03d}" for index in range(101)]
    assert audit.details_contract_candidates(symbols, 3) == [
        {"position": 10, "fraction": 0.1, "symbol": "S010"},
        {"position": 50, "fraction": 0.5, "symbol": "S050"},
        {"position": 90, "fraction": 0.9, "symbol": "S090"},
    ]


@pytest.mark.parametrize("count", [0, 4])
def test_candidate_count_is_bounded(audit, count):
    with pytest.raises(ValueError, match="between 1 and 3"):
        audit.details_contract_candidates(["AAA"], count)


def test_nested_data_items_exact_row_is_extracted_with_safe_shape(audit):
    result = inspect(
        audit,
        {
            "status": 200,
            "data": {
                "items": [
                    {
                        "SecurityCode": "AAA",
                        "Market": "HOSE",
                        "SecurityType": "Common Stock",
                        "IssuerName": "must not be copied",
                    }
                ]
            },
        },
    )
    public = audit.public_details_diagnostics(result)
    assert public["candidate_collection_key_names"] == ["data", "data.items"]
    assert public["raw_collection_count"] == 1
    assert public["exact_symbol_and_market_count"] == 1
    assert public["no_row_state"] == "exact_symbol_and_market"
    assert public["candidate_type_field_names"] == ["SecurityType"]
    assert "must not be copied" not in str(public)
    assert "exact_rows" not in public


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"status": 200, "data": []}, "collection_present_empty"),
        ({"status": 200, "message": "ok"}, "collection_not_found"),
        ({"status": "unavailable", "failure_class": "timeout"}, "provider_failure"),
    ],
)
def test_no_row_states_are_distinct(audit, payload, expected):
    assert inspect(audit, payload)["no_row_state"] == expected


def test_symbol_mismatch_and_missing_symbol_are_reported(audit):
    result = inspect(
        audit,
        {"rows": [{"Symbol": "BBB", "Market": "HOSE"}, {"Market": "HOSE"}]},
    )
    assert result["mismatched_symbol_count"] == 1
    assert result["missing_symbol_count"] == 1
    assert result["exact_symbol_count"] == 0
    assert result["no_row_state"] == "normalized_rows_but_no_exact_symbol"
    assert result["exact_match_rejection_reasons"] == [
        "normalized_symbol_mismatch",
        "missing_symbol_field",
    ]


def test_rows_without_recognizable_symbols_are_not_called_normalized(audit):
    result = inspect(audit, {"rows": [{"Market": "HOSE"}, {"Unknown": "shape"}]})
    assert result["raw_collection_count"] == 2
    assert result["normalized_row_count"] == 0
    assert result["no_row_state"] == "rows_present_but_not_normalized"
    assert result["parser_state"] == "rows_present_but_not_normalized"
    assert result["exact_match_rejection_reasons"] == ["missing_symbol_field"]


def test_exact_symbol_wrong_or_missing_market_is_rejected(audit):
    result = inspect(
        audit,
        {"rows": [{"Symbol": "AAA", "Market": "HNX"}, {"Symbol": "AAA"}]},
    )
    assert result["exact_symbol_count"] == 2
    assert result["mismatched_market_count"] == 1
    assert result["missing_market_count"] == 1
    assert result["exact_symbol_and_market_count"] == 0
    assert result["no_row_state"] == "exact_symbol_but_wrong_or_missing_market"
    assert result["exact_match_rejection_reasons"] == ["market_mismatch", "missing_market_field"]


def test_duplicate_exact_rows_are_reported_without_weakening_selection(audit):
    result = inspect(
        audit,
        {"rows": [{"Symbol": "AAA", "Market": "HOSE"}, {"Symbol": "AAA", "Market": "HOSE"}]},
    )
    assert result["exact_symbol_and_market_count"] == 2
    assert result["exact_match_rejection_reasons"] == ["duplicate_conflicting_rows"]


def test_possible_more_pages_is_bounded_to_explicit_page_size(audit):
    rows = [{"Symbol": f"S{index}", "Market": "HOSE"} for index in range(3)]
    assert inspect(audit, {"rows": rows}, page_size=3)["possible_more_pages"] is True
    assert inspect(audit, {"rows": rows}, page_size="")["possible_more_pages"] is False


@pytest.mark.parametrize(
    ("candidates", "expected"),
    [
        ([{"exact_symbol_and_market_count": 1, "candidate_type_fields": [{"semantic_status": "verified"}]}], "A"),
        ([{"exact_symbol_and_market_count": 1, "candidate_type_fields": []}], "B"),
        ([{"exact_symbol_and_market_count": 1, "candidate_type_fields": [{"semantic_status": "ambiguous"}]}], "C"),
        ([{"exact_symbol_and_market_count": 0, "no_row_state": "collection_present_empty"}], "E"),
        ([{"failure_class": "network_error"}], "F"),
    ],
)
def test_contract_outcomes(audit, candidates, expected):
    assert audit.decide_details_contract({"candidates": candidates})["code"] == expected


def test_direct_defect_fixed_outcome_is_explicit(audit):
    evidence = {"candidates": [{"exact_symbol_and_market_count": 1, "candidate_type_fields": []}]}
    assert audit.decide_details_contract(evidence, defect_fixed=True)["code"] == "D"


def test_config_only_contract_mode_constructs_no_provider(audit, monkeypatch):
    monkeypatch.setattr(audit, "_load_live_fetcher", lambda: pytest.fail("provider constructed"))
    args = audit.build_parser().parse_args(["--mode", "details-contract", "--candidate-count", "3"])
    result = audit.execute(args)
    assert result["network_used"] is False
    assert result["details_contract"]["maximum_details_request_sequences"] == 6
    assert result["details_contract"]["daily_stock_price_requests"] == 0


def test_live_contract_uses_only_securities_and_bounded_details_shapes(audit, monkeypatch):
    calls = []
    securities_rows = [
        {"Symbol": f"S{index:03d}", "Market": "HOSE", "StockName": "Name"}
        for index in range(11)
    ]

    class FakeFetcher:
        def _request(self, endpoint, params=None):
            calls.append((endpoint, dict(params or {})))
            if endpoint == "Securities":
                return {"data": securities_rows}
            return {
                "data": {
                    "items": [
                        {"SecurityCode": params["symbol"], "Market": "HOSE", "SecurityType": "Common Stock"}
                    ]
                }
            }

        def get_daily_stock_price(self, *args, **kwargs):
            pytest.fail("details-contract mode must not call DailyStockPrice")

    monkeypatch.setattr(audit, "_load_live_fetcher", FakeFetcher)
    monkeypatch.setattr(audit, "install_live_counters", lambda _: audit.Counter())
    args = audit.build_parser().parse_args(
        ["--mode", "details-contract", "--candidate-count", "3", "--allow-live"]
    )
    result = audit.execute(args)
    assert [endpoint for endpoint, _ in calls] == ["Securities", "SecuritiesDetails", "SecuritiesDetails", "SecuritiesDetails"]
    assert all(call[1]["pageIndex"] == 1 for call in calls[1:])
    assert result["decision"]["code"] == "A"


def test_official_default_alternative_is_only_used_after_primary_empty(audit):
    calls = []
    securities_rows = [{"Symbol": f"S{index:03d}", "Market": "HOSE"} for index in range(11)]

    class FakeFetcher:
        def _request(self, endpoint, params=None):
            calls.append((endpoint, dict(params or {})))
            if endpoint == "Securities":
                return {"data": securities_rows}
            if params["pageIndex"] == 1:
                return {"data": []}
            return {"data": [{"Symbol": params["symbol"], "Market": "HOSE"}]}

    result = audit.run_live_details_contract(FakeFetcher(), 1)
    assert result["primary_attempt_count"] == 1
    assert result["alternative_attempt_count"] == 1
    assert result["candidates"][0]["resolved_shape"] == "official_empty_page_defaults"
    assert calls[-1][1]["pageIndex"] == ""
    assert calls[-1][1]["pageSize"] == ""


def test_output_sanitization_excludes_raw_exact_rows(audit):
    result = inspect(audit, {"rows": [{"Symbol": "AAA", "Market": "HOSE", "IssuerName": "private"}]})
    public = audit.public_details_diagnostics(result)
    assert "exact_rows" not in public
    assert "private" not in str(public)
