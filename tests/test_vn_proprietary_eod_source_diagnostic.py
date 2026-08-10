from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook

from scripts import diagnose_vn_proprietary_eod_source as diagnostic


HEADERS = [
    "Trading Date",
    "Exchange",
    "Ticker",
    "Row Type",
    "Buy Volume (shares)",
    "Sell Volume (shares)",
    "Net Volume",
    "Buy Value (VND)",
    "Sell Value (VND)",
    "Net Value",
]


def row(
    ticker="FPT",
    row_type="detail",
    exchange="HOSE",
    buy_volume=10,
    sell_volume=4,
    net_volume=6,
    buy_value=100,
    sell_value=40,
    net_value=60,
    trading_date="2026-08-05",
):
    return [
        trading_date,
        exchange,
        ticker,
        row_type,
        buy_volume,
        sell_volume,
        net_volume,
        buy_value,
        sell_value,
        net_value,
    ]


def inspect(*rows, headers=HEADERS, filename="hose_sample.csv", **kwargs):
    return diagnostic.inspect_rows([headers, *rows], filename=filename, **kwargs)


def make_csv(path: Path, *, delimiter=",", encoding="utf-8", rows=None):
    content = "\n".join(delimiter.join(str(value) for value in item) for item in (rows or [HEADERS, row()]))
    path.write_text(content, encoding=encoding)
    return path


def test_valid_authoritative_hose_total_row():
    report = inspect(row(ticker="TOTAL", row_type="total"))
    assert report["quality_classification"] == "COMPLETE_GROSS_HOSE_TOTAL"
    assert report["scope_classification"] == "HOSE_TOTAL_ONLY"


def test_valid_hose_symbol_detail_file():
    report = inspect(row("FPT"), row("HPG", buy_volume=20, sell_volume=5, net_volume=15))
    assert report["quality_classification"] == "COMPLETE_GROSS_HOSE_DETAIL"
    assert report["detail_row_count"] == 2


def test_multi_exchange_file_with_explicit_exchange_column():
    report = inspect(row("FPT", exchange="HOSE"), row("PVS", exchange="HNX"))
    assert report["scope_classification"] == "SYMBOL_ROWS_MULTI_EXCHANGE"
    assert report["scope_proven"] is True
    assert report["detail_row_count"] == 1


def test_multi_exchange_file_without_exchange_column_is_rejected():
    headers = [value for value in HEADERS if value != "Exchange"]
    values = [value for index, value in enumerate(row()) if index != 1]
    report = inspect(values, headers=headers, filename="mixed_sample.csv")
    assert report["quality_classification"] == "MIXED_EXCHANGE_UNFILTERABLE"


def test_details_plus_grand_total_reconcile():
    report = inspect(row("FPT"), row("TOTAL", "total"))
    assert report["scope_classification"] == "TOTAL_PLUS_SYMBOL_ROWS"
    assert report["reconciliation"]["status"] == "EXACT"


def test_total_already_includes_matched_and_deal_values_without_double_count():
    total = row("FPT", "total", buy_volume=10, sell_volume=4, buy_value=100, sell_value=40)
    matched = row("FPT", "matched", buy_volume=6, sell_volume=2, buy_value=60, sell_value=20)
    deal = row("FPT", "deal", buy_volume=4, sell_volume=2, buy_value=40, sell_value=20)
    report = inspect(total, matched, deal)
    assert report["component_reconciliation"] == "EXACT"
    assert report["stated_total"]["buy_volume"] == 10


def test_duplicate_ticker_rows_with_explicit_component_types_are_safe():
    report = inspect(row("FPT", "total"), row("FPT", "matched"), row("FPT", "deal"))
    assert report["duplicate_or_double_count_risk"] is False


def test_duplicate_ticker_rows_with_ambiguous_meaning_are_rejected():
    report = inspect(row("FPT"), row("FPT"))
    assert report["quality_classification"] == "DUPLICATE_OR_DOUBLE_COUNT_RISK"


def test_gross_buy_sell_volume_fields_are_present():
    report = inspect(row())
    assert {"buy_volume", "sell_volume"} <= set(report["candidate_mapping"].values())


def test_gross_buy_sell_value_fields_are_present():
    report = inspect(row())
    assert {"buy_value", "sell_value"} <= set(report["candidate_mapping"].values())


def test_net_only_source_is_rejected():
    headers = ["Trading Date", "Exchange", "Ticker", "Net Volume", "Net Value (VND)"]
    report = inspect(["2026-08-05", "HOSE", "FPT", 6, 60], headers=headers)
    assert report["quality_classification"] == "NET_ONLY"


def test_missing_buy_field_is_rejected():
    headers = [value for value in HEADERS if "Buy Volume" not in value]
    values = [value for index, value in enumerate(row()) if index != 4]
    report = inspect(values, headers=headers)
    assert report["quality_classification"] == "MISSING_VOLUME"
    assert report["records"][0]["field_presence"]["buy_volume"] == "FIELD_ABSENT"


def test_missing_sell_field_is_rejected():
    headers = [value for value in HEADERS if "Sell Value" not in value]
    values = [value for index, value in enumerate(row()) if index != 8]
    assert inspect(values, headers=headers)["quality_classification"] == "MISSING_VALUE"


def test_blank_cell_remains_null():
    report = inspect(row(buy_volume=""))
    record = report["records"][0]
    assert record["buy_volume"] is None
    assert record["field_presence"]["buy_volume"] == "FIELD_BLANK"


def test_explicit_zero_remains_zero():
    report = inspect(row(buy_volume=0, net_volume=-4))
    record = report["records"][0]
    assert record["buy_volume"] == 0
    assert record["field_presence"]["buy_volume"] == "FIELD_PRESENT_ZERO"


def test_non_numeric_parse_failure_remains_invalid():
    report = inspect(row(buy_volume="not-a-number"))
    assert report["records"][0]["field_presence"]["buy_volume"] == "PARSE_FAILURE"
    assert report["schema_proven"] is False


def test_derived_volume_net_requires_complete_gross_pair():
    record = inspect(row(net_volume=None))["records"][0]
    assert record["derived_net_volume"] == 6


def test_derived_value_net_requires_complete_gross_pair():
    record = inspect(row(net_value=None))["records"][0]
    assert record["derived_net_value"] == 60


def test_source_net_reconciles_exactly():
    record = inspect(row())["records"][0]
    assert record["net_volume_reconciliation"] == "EXACT"
    assert record["net_value_reconciliation"] == "EXACT"


def test_source_net_material_mismatch_blocks_schema():
    report = inspect(row(net_value=999))
    assert report["records"][0]["net_value_reconciliation"] == "MATERIAL_MISMATCH"
    assert report["schema_proven"] is False


def test_value_unit_vnd():
    assert inspect(row())["units"]["value"]["source_unit"] == "VND"


def test_value_unit_thousand_vnd():
    headers = [value.replace("VND", "thousand VND") for value in HEADERS]
    assert inspect(row(), headers=headers)["units"]["value"]["normalization_multiplier"] == 1_000


def test_value_unit_million_vnd():
    headers = [value.replace("VND", "million VND") for value in HEADERS]
    assert inspect(row(), headers=headers)["units"]["value"]["normalization_multiplier"] == 1_000_000


def test_ambiguous_unit_is_rejected():
    headers = [value.replace(" (VND)", "").replace(" (shares)", "") for value in HEADERS]
    report = inspect(row(), headers=headers)
    assert report["quality_classification"] == "AMBIGUOUS_UNIT"


def test_explicit_trading_date_column_has_high_confidence():
    proof = inspect(row())["date_proof"]
    assert proof == {"value": "2026-08-05", "evidence": "explicit_trading_date_field", "confidence": "HIGH"}


def test_trading_date_from_workbook_metadata_has_high_confidence():
    headers = [value for value in HEADERS if value != "Trading Date"]
    values = row()[1:]
    proof = inspect(values, headers=headers, workbook_metadata="HOSE 20260805")["date_proof"]
    assert proof["evidence"] == "workbook_metadata"
    assert proof["confidence"] == "HIGH"


def test_filename_only_date_has_lower_confidence():
    headers = [value for value in HEADERS if value != "Trading Date"]
    report = inspect(row()[1:], headers=headers, filename="hose_20260805.csv")
    assert report["date_proof"]["confidence"] == "LOW"
    assert report["schema_proven"] is False


def test_filesystem_modified_time_is_not_used_as_trading_date():
    proof = diagnostic.prove_trading_date([], workbook_metadata=None, sheet_name=None, filename="sample.csv")
    assert proof["value"] is None
    assert proof["confidence"] == "UNKNOWN"


def test_empty_worksheet_is_invalid():
    assert diagnostic.inspect_rows([], filename="hose.csv")["quality_classification"] == "INVALID_SCHEMA"


def test_multiple_sheet_candidates_default_to_first_visible(tmp_path):
    path = tmp_path / "hose_20260805.xlsx"
    workbook = Workbook()
    workbook.active.title = "Data"
    workbook.active.append(HEADERS)
    workbook.active.append(row())
    workbook.create_sheet("Other").append(["not", "data"])
    workbook.save(path)
    report = diagnostic.inspect_file(path)
    assert report["workbook_sheet_names"] == ["Data", "Other"]
    assert report["selected_sheet"] == "Data"


def test_hidden_support_sheet_is_ignored_unless_selected(tmp_path):
    path = tmp_path / "hose_20260805.xlsx"
    workbook = Workbook()
    workbook.active.title = "Data"
    workbook.active.append(HEADERS)
    workbook.active.append(row())
    support = workbook.create_sheet("Support")
    support.sheet_state = "hidden"
    support.append(HEADERS)
    support.append(row())
    workbook.save(path)
    default = diagnostic.inspect_file(path)
    selected = diagnostic.inspect_file(path, sheet="Support")
    assert default["selected_sheet"] == "Data"
    assert selected["hidden_sheet"] is True


def test_formula_cells_are_detected_and_not_evaluated(tmp_path):
    path = tmp_path / "hose_20260805.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(HEADERS)
    values = row()
    values[4] = "=5+5"
    sheet.append(values)
    workbook.save(path)
    report = diagnostic.inspect_file(path)
    assert report["formula_cell_presence"] is True
    assert report["schema_proven"] is False


def test_csv_delimiter_detection(tmp_path):
    path = make_csv(tmp_path / "hose_20260805.csv", delimiter=";")
    report = diagnostic.inspect_file(path)
    assert report["delimiter"] == ";"


def test_csv_encoding_handling(tmp_path):
    path = make_csv(tmp_path / "hose_20260805.csv", encoding="utf-8-sig")
    report = diagnostic.inspect_file(path)
    assert report["encoding"] == "utf-8-sig"


def test_unsupported_pdf_is_rejected_without_ocr(tmp_path):
    path = tmp_path / "sample.pdf"
    path.write_bytes(b"%PDF synthetic")
    assert diagnostic.inspect_file(path)["quality_classification"] == "UNSUPPORTED_FILE_FORMAT"


def test_unsupported_image_is_rejected_without_ocr(tmp_path):
    path = tmp_path / "sample.png"
    path.write_bytes(b"synthetic")
    assert diagnostic.inspect_file(path)["quality_classification"] == "UNSUPPORTED_FILE_FORMAT"


def test_file_hash_is_deterministic(tmp_path):
    path = make_csv(tmp_path / "hose.csv")
    assert diagnostic.file_sha256(path) == diagnostic.file_sha256(path)


def test_dry_diagnostic_does_not_mutate_production_storage(tmp_path):
    path = make_csv(tmp_path / "hose_20260805.csv")
    before = {item.name for item in tmp_path.iterdir()}
    diagnostic.inspect_file(path)
    assert {item.name for item in tmp_path.iterdir()} == before


def test_cleanup_removes_temporary_reports(monkeypatch, tmp_path, capsys):
    source = make_csv(tmp_path / "hose_20260805.csv")
    output = tmp_path / "reports"
    monkeypatch.setattr(diagnostic.os.sys, "argv", [
        "diagnostic", "--file", str(source), "--output-dir", str(output), "--cleanup", "--json",
    ])
    assert diagnostic.main() == 0
    assert json.loads(capsys.readouterr().out)["artifacts"] == []
    assert not output.exists()


def test_output_does_not_contain_local_credential_values(monkeypatch, tmp_path):
    monkeypatch.setenv("FIINQUANT_USERNAME", "synthetic-secret-user")
    monkeypatch.setenv("FIINQUANT_PASSWORD", "synthetic-secret-pass")
    source = make_csv(tmp_path / "hose_20260805.csv")
    report = diagnostic.inspect_file(source)
    paths = diagnostic.write_reports(tmp_path / "reports", report)
    rendered = "".join(path.read_text("utf-8") for path in paths)
    assert "synthetic-secret-user" not in rendered
    assert "synthetic-secret-pass" not in rendered


def test_no_network_call_exists_in_diagnostic_source():
    source = Path(diagnostic.__file__).read_text("utf-8").casefold()
    assert "requests." not in source
    assert "urlopen" not in source
    assert "socket." not in source


def test_no_real_provider_fixture_is_committed():
    fixture_root = Path("tests/fixtures/vn_proprietary_eod")
    assert not fixture_root.exists() or not list(fixture_root.glob("*"))


def test_source_classification_is_deterministic():
    rows = [HEADERS, row()]
    first = diagnostic.inspect_rows(rows, filename="hose.csv")
    second = diagnostic.inspect_rows(rows, filename="hose.csv")
    assert first["quality_classification"] == second["quality_classification"]


def test_material_reconciliation_mismatch_blocks_pass():
    total = row("TOTAL", "total", buy_volume=100, net_volume=96)
    report = inspect(row("FPT"), total)
    assert report["reconciliation"]["status"] == "MATERIAL_MISMATCH"
    assert report["schema_proven"] is False


def test_safe_detail_aggregation_produces_expected_hose_total():
    report = inspect(
        row("FPT", buy_volume=10, sell_volume=4, buy_value=100, sell_value=40),
        row("HPG", buy_volume=20, sell_volume=5, buy_value=200, sell_value=50),
    )
    assert report["detail_sum"] == {
        "buy_volume": 30,
        "sell_volume": 9,
        "buy_value": 300,
        "sell_value": 90,
    }
