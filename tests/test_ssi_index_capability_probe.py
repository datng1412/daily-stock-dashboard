# -*- coding: utf-8 -*-

from __future__ import annotations

from datetime import date

from scripts import probe_ssi_index_capability as probe


class FakeFetcher:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def _request(self, endpoint, params=None):
        self.calls.append((endpoint, dict(params or {})))
        return self.payloads.pop(0)

    @staticmethod
    def _map_index_info(row):
        return {
            "index_id": row.get("IndexID"),
            "index_code": row.get("IndexCode"),
            "market": row.get("Market"),
            "exchange": row.get("Exchange"),
        }

    @staticmethod
    def _map_daily_index(row, index_code):
        return {
            "date": row.get("TradingDate"),
            "index_code": row.get("IndexID") or index_code,
            "index_value": row.get("IndexValue"),
            "change": None,
            "change_pct": None,
            "total_volume": None,
            "total_value": None,
        }

    @staticmethod
    def _map_index_component(row, index_code):
        return {
            "index_code": row.get("IndexID") or index_code,
            "symbol": row.get("Symbol"),
        }


def test_candidate_generation_uses_exact_provider_identifiers_and_deduplicates():
    rows = [
        {"index_id": "VN30", "index_code": "VN30", "market": "HOSE"},
        {"index_id": "VN30", "index_code": "VN30", "market": "HOSE"},
        {"index_id": "HNXINDEX", "index_code": "HNXINDEX", "market": "HNX"},
    ]

    candidates = probe.build_index_candidates(rows, ["VNINDEX", "VN30"], max_candidates=10)

    assert [(item.identifier_kind, item.identifier_value, item.parameter_key) for item in candidates] == [
        ("index_id", "VN30", "indexID"),
        ("index_code", "VN30", "indexCode"),
    ]
    assert all(item.identifier_value != "HNXINDEX" for item in candidates)


def test_candidate_generation_enforces_hard_budget():
    rows = [
        {"index_id": f"IDX{number}", "index_code": f"IDX{number}", "market": "HOSE"}
        for number in range(20)
    ]
    labels = [f"IDX{number}" for number in range(20)]

    candidates = probe.build_index_candidates(rows, labels, max_candidates=99)

    assert len(candidates) == probe.MAX_CANDIDATES


def test_date_and_market_variants_are_bounded():
    windows = probe.build_date_windows(today=date(2026, 6, 29), day_counts=[1, 7, 29, 365])
    candidate = probe.IndexCandidate("VN30", "index_id", "VN30", "indexID", "HOSE")
    markets = probe.build_market_variants(candidate, fallback_market="HNX")

    assert windows == [("29/06/2026", "29/06/2026"), ("23/06/2026", "29/06/2026")]
    assert len(windows) == probe.MAX_DATE_WINDOWS
    assert markets == [None, "HOSE"]


def test_probe_classification_covers_usable_empty_unusable_and_failure():
    assert probe.classify_probe({}, [{"date": "2026-06-29"}]) == ("usable_rows", None)
    assert probe.classify_probe(
        {},
        [{"symbol": "FPT"}],
        endpoint="IndexComponents",
    ) == ("usable_components", None)
    assert probe.classify_probe({"data": []}, []) == ("empty_response", None)
    assert probe.classify_probe(
        {"data": {"PageIndex": 1, "TotalRecord": 0, "Data": []}},
        [],
        endpoint="IndexComponents",
    ) == ("empty_response", None)
    assert probe.classify_probe({"data": [{"unexpected": 1}]}, []) == ("parse_failed", "parse_failed")
    assert probe.classify_probe(
        {"status": "unavailable", "failure_class": "permission_denied"},
        [],
    ) == ("permission_denied", "permission_denied")


def test_summary_is_whitelisted_and_does_not_emit_provider_error_text():
    secret = "SECRET_TOKEN_DO_NOT_EXPOSE"
    fetcher = FakeFetcher([])
    spec = probe.ProbeSpec(
        endpoint="DailyIndex",
        candidate_label="VN30",
        identifier_kind="index_id",
        identifier_value="VN30",
        parameter_key="indexID",
        market=None,
        from_date="23/06/2026",
        to_date="29/06/2026",
        params={},
    )

    summary = probe.summarize_probe(
        fetcher,
        spec,
        {
            "status": "unavailable",
            "failure_class": "bad_request_params",
            "reason": f"Authorization: Bearer {secret}",
            "raw": secret,
        },
    )

    rendered = str(summary)
    assert secret not in rendered
    assert "Authorization" not in rendered
    assert summary.failure_class == "bad_request_params"


def test_error_shaped_index_list_row_is_not_reported_as_identifier():
    fetcher = FakeFetcher([])
    spec = probe.ProbeSpec(
        endpoint="IndexList",
        candidate_label=None,
        identifier_kind=None,
        identifier_value=None,
        parameter_key=None,
        market=None,
        from_date=None,
        to_date=None,
        params={},
    )

    rows = probe._normalize_rows(
        fetcher,
        spec,
        {"data": [{"Code": "REQUEST_NULL", "Message": "request is invalid"}]},
    )

    assert rows == []


def test_discovery_is_sequential_and_respects_all_probe_budgets():
    index_payload = {
        "data": [
            {
                "IndexID": "VN30",
                "IndexCode": "VN30",
                "Market": "HOSE",
            }
        ]
    }
    payloads = [index_payload, index_payload, index_payload]
    payloads.extend({"data": []} for _ in range(8))
    fetcher = FakeFetcher(payloads)

    result = probe.run_discovery(
        fetcher,
        requested_labels=["VN30"],
        day_counts=[7, 29, 365],
        max_candidates=99,
        fallback_market="HOSE",
        today=date(2026, 6, 29),
        delay_seconds=0,
        sleep=lambda _: None,
    )

    endpoints = [endpoint for endpoint, _ in fetcher.calls]
    assert endpoints == ["IndexList"] * 3 + ["DailyIndex"] * 4 + ["IndexComponents"] * 4
    assert len(result.probes) == 11
    assert len(result.index_list_rows) == 3
    assert len([call for call in fetcher.calls if call[0] == "DailyIndex"]) <= (
        probe.MAX_CANDIDATES * probe.MAX_DATE_WINDOWS
    )
    assert len([call for call in fetcher.calls if call[0] == "IndexComponents"]) <= (
        probe.MAX_CANDIDATES * probe.MAX_MARKET_VARIANTS
    )
    assert fetcher.calls[0][1] == {}
    assert fetcher.calls[1][1] == {"market": "HOSE"}
    assert fetcher.calls[2][1] == {"market": "HNX"}


def test_table_output_contains_only_compact_summary_fields(capsys):
    summary = probe.ProbeSummary(
        candidate_label="VN30",
        endpoint="IndexComponents",
        identifier_kind="index_code",
        identifier_value="VN30",
        parameter_key="indexCode",
        market="HOSE",
        from_date=None,
        to_date=None,
        classification="empty_response",
        count=0,
        latest_date=None,
        failure_class=None,
    )

    probe._print_table(probe.DiscoveryResult(index_list_rows=[], probes=[summary]))
    output = capsys.readouterr().out

    assert "candidate_label\tendpoint\tidentifier_kind" in output
    assert "VN30\tIndexComponents\tindex_code\tVN30" in output
    assert "reason" not in output
    assert "payload" not in output
