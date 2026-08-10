"""Offline schema gate for user-supplied VN proprietary-flow EOD files.

The tool is diagnostic-only. It reads one local CSV/XLS/XLSX file, emits
sanitized schema evidence, and never calls a network service or writes product
history/cache. Candidate aliases are heuristics for inspection, not a proven
provider contract; only a real source sample can establish that contract.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import unicodedata
from typing import Any, Iterable, Mapping, Sequence


SUPPORTED_EXTENSIONS = {".csv", ".xls", ".xlsx"}
REQUIRED_GROSS_FIELDS = ("buy_volume", "sell_volume", "buy_value", "sell_value")
OPTIONAL_FIELDS = (
    "trading_date", "exchange", "net_volume", "net_value", "ticker", "row_type",
    "matched_buy_volume", "matched_sell_volume", "matched_buy_value",
    "matched_sell_value", "deal_buy_volume", "deal_sell_volume",
    "deal_buy_value", "deal_sell_value", "provider_updated_at",
)
CANONICAL_FIELDS = ("trading_date", "exchange", *REQUIRED_GROSS_FIELDS, *OPTIONAL_FIELDS[2:])
MAX_HEADER_SCAN_ROWS = 25
MAX_PREVIEW_ROWS = 5
MAX_CSV_BYTES = 25 * 1024 * 1024


def normalize_label(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.casefold()).split())


def _aliases(*values: str) -> set[str]:
    return {normalize_label(value) for value in values}


# Inspection candidates only. A provider alias becomes proven only after it is
# observed in a real sample and documented with source/date/unit evidence.
CANDIDATE_ALIASES = {
    "trading_date": _aliases("trading date", "date", "ngày giao dịch"),
    "exchange": _aliases("exchange", "board", "sàn giao dịch", "sàn"),
    "ticker": _aliases("ticker", "symbol", "mã chứng khoán", "mã ck"),
    "row_type": _aliases("row type", "type", "loại dòng", "loại giao dịch"),
    "buy_volume": _aliases(
        "buy volume", "proprietary buy volume", "khối lượng mua",
        "tổng klgd mua tự doanh",
    ),
    "sell_volume": _aliases(
        "sell volume", "proprietary sell volume", "khối lượng bán",
        "tổng klgd bán tự doanh",
    ),
    "net_volume": _aliases("net volume", "khối lượng ròng"),
    "buy_value": _aliases(
        "buy value", "proprietary buy value", "giá trị mua",
        "tổng gtgd mua tự doanh",
    ),
    "sell_value": _aliases(
        "sell value", "proprietary sell value", "giá trị bán",
        "tổng gtgd bán tự doanh",
    ),
    "net_value": _aliases("net value", "giá trị ròng", "mua ròng", "bán ròng"),
    "matched_buy_volume": _aliases("matched buy volume", "khớp lệnh mua khối lượng"),
    "matched_sell_volume": _aliases("matched sell volume", "khớp lệnh bán khối lượng"),
    "matched_buy_value": _aliases("matched buy value", "khớp lệnh mua giá trị"),
    "matched_sell_value": _aliases("matched sell value", "khớp lệnh bán giá trị"),
    "deal_buy_volume": _aliases("deal buy volume", "thỏa thuận mua khối lượng"),
    "deal_sell_volume": _aliases("deal sell volume", "thỏa thuận bán khối lượng"),
    "deal_buy_value": _aliases("deal buy value", "thỏa thuận mua giá trị"),
    "deal_sell_value": _aliases("deal sell value", "thỏa thuận bán giá trị"),
    "provider_updated_at": _aliases("updated at", "update time", "thời gian cập nhật"),
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify_cell(value: Any) -> tuple[int | float | None, str]:
    if value is None:
        return None, "FIELD_NULL"
    if isinstance(value, str) and not value.strip():
        return None, "FIELD_BLANK"
    if isinstance(value, bool):
        return None, "PARSE_FAILURE"
    if isinstance(value, (int, float, Decimal)):
        number = float(value)
        if number != number or number in {float("inf"), float("-inf")}:
            return None, "PARSE_FAILURE"
        normalized: int | float = int(number) if number.is_integer() else number
        return normalized, "FIELD_PRESENT_ZERO" if normalized == 0 else "FIELD_PRESENT_VALUE"
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if re.fullmatch(r"[-+]?\d{1,3}(,\d{3})+(\.\d+)?", text):
        text = text.replace(",", "")
    elif re.fullmatch(r"[-+]?\d+(\.\d+)?", text):
        pass
    else:
        return None, "PARSE_FAILURE"
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None, "PARSE_FAILURE"
    normalized = int(number) if number == number.to_integral_value() else float(number)
    return normalized, "FIELD_PRESENT_ZERO" if normalized == 0 else "FIELD_PRESENT_VALUE"


def canonical_for_header(header: Any) -> str | None:
    normalized = normalize_label(header)
    for canonical, aliases in CANDIDATE_ALIASES.items():
        if normalized in aliases:
            return canonical
        # Unit annotations are allowed around an otherwise exact candidate.
        if any(normalized.startswith(alias + " ") for alias in aliases if alias):
            return canonical
    return None


def candidate_header_row(rows: Sequence[Sequence[Any]]) -> int | None:
    best_index: int | None = None
    best_score = 0
    for index, row in enumerate(rows[:MAX_HEADER_SCAN_ROWS]):
        mapped = {canonical_for_header(value) for value in row}
        score = len(mapped - {None})
        if score > best_score:
            best_index, best_score = index, score
    return best_index if best_score >= 2 else None


def _date_from_value(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def prove_trading_date(
    records: Sequence[Mapping[str, Any]],
    *,
    workbook_metadata: str | None,
    sheet_name: str | None,
    filename: str,
) -> dict[str, Any]:
    dates = {
        parsed.isoformat()
        for record in records
        if (parsed := _date_from_value(record.get("trading_date"))) is not None
    }
    if len(dates) == 1:
        return {"value": next(iter(dates)), "evidence": "explicit_trading_date_field", "confidence": "HIGH"}
    if len(dates) > 1:
        return {"value": None, "evidence": "multiple_explicit_dates", "confidence": "UNKNOWN"}
    sources = (
        (workbook_metadata, "workbook_metadata", "HIGH"),
        (sheet_name, "sheet_name", "MEDIUM"),
        (filename, "filename", "LOW"),
    )
    for text, evidence, confidence in sources:
        match = re.search(r"(?<!\d)(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?!\d)", str(text or ""))
        if match:
            parsed = _date_from_value("".join(match.groups()))
            if parsed:
                return {"value": parsed.isoformat(), "evidence": evidence, "confidence": confidence}
    return {"value": None, "evidence": None, "confidence": "UNKNOWN"}


def prove_units(headers: Sequence[Any], notes: Sequence[str]) -> dict[str, dict[str, Any]]:
    evidence_text = " | ".join(str(value or "") for value in (*headers, *notes))
    normalized = normalize_label(evidence_text)
    volume = {"source_unit": "UNKNOWN", "normalization_multiplier": None, "evidence": None, "confidence": "UNKNOWN"}
    value = dict(volume)
    if any(marker in normalized for marker in ("shares", "share", "co phieu", " don vi cp", " klgd")):
        volume = {"source_unit": "SHARES", "normalization_multiplier": 1, "evidence": "explicit_header_or_note", "confidence": "HIGH"}
    if any(marker in normalized for marker in ("billion vnd", "ty dong")):
        value = {"source_unit": "BILLION_VND", "normalization_multiplier": 1_000_000_000, "evidence": "explicit_header_or_note", "confidence": "HIGH"}
    elif any(marker in normalized for marker in ("million vnd", "trieu dong")):
        value = {"source_unit": "MILLION_VND", "normalization_multiplier": 1_000_000, "evidence": "explicit_header_or_note", "confidence": "HIGH"}
    elif any(marker in normalized for marker in ("thousand vnd", "nghin dong")):
        value = {"source_unit": "THOUSAND_VND", "normalization_multiplier": 1_000, "evidence": "explicit_header_or_note", "confidence": "HIGH"}
    elif any(marker in normalized for marker in (" vnd", "dong", "gtgd")):
        value = {"source_unit": "VND", "normalization_multiplier": 1, "evidence": "explicit_header_or_note", "confidence": "HIGH"}
    return {"volume": volume, "value": value}


def _row_kind(record: Mapping[str, Any]) -> str:
    text = normalize_label(" ".join(str(record.get(key) or "") for key in ("row_type", "ticker")))
    if any(marker in text for marker in ("ghi chu", "note", "footnote")):
        return "note"
    if "subtotal" in text or "tong phu" in text:
        return "subtotal"
    if any(marker in text for marker in ("matched", "khop lenh")):
        return "matched"
    if any(marker in text for marker in ("deal", "negotiated", "thoa thuan")):
        return "deal"
    if text in {"total", "tong", "hose total", "tong hose", "grand total"} or str(record.get("row_type") or "").casefold() == "total":
        return "total"
    return "detail"


def _sum_fields(records: Sequence[Mapping[str, Any]]) -> dict[str, int | float | None]:
    result: dict[str, int | float | None] = {}
    for field in REQUIRED_GROSS_FIELDS:
        values = [record.get(field) for record in records]
        result[field] = sum(values) if values and all(isinstance(value, (int, float)) for value in values) else None
    return result


def reconcile(detail: Mapping[str, Any], stated: Mapping[str, Any]) -> dict[str, Any]:
    differences: dict[str, Any] = {}
    comparable = 0
    material = False
    rounding = False
    for field in REQUIRED_GROSS_FIELDS:
        left, right = detail.get(field), stated.get(field)
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            continue
        comparable += 1
        absolute = abs(left - right)
        relative = absolute / max(abs(right), 1)
        differences[field] = {"absolute_difference": absolute, "relative_difference": relative}
        if absolute:
            if relative <= 0.0001 or absolute <= 1:
                rounding = True
            else:
                material = True
    if not comparable:
        status = "INSUFFICIENT_FIELDS"
    elif material:
        status = "MATERIAL_MISMATCH"
    elif rounding:
        status = "ROUNDING_DIFFERENCE"
    else:
        status = "EXACT"
    return {"status": status, "differences": differences}


def _duplicate_risk(records: Sequence[Mapping[str, Any]]) -> bool:
    by_ticker: dict[str, list[str]] = {}
    for record in records:
        ticker = normalize_label(record.get("ticker"))
        if ticker:
            by_ticker.setdefault(ticker, []).append(str(record.get("_row_kind")))
    for kinds in by_ticker.values():
        if len(kinds) > 1 and (len(set(kinds)) != len(kinds) or not set(kinds) <= {"total", "matched", "deal"}):
            return True
    return False


def inspect_rows(
    rows: Sequence[Sequence[Any]],
    *,
    exchange: str = "HOSE",
    filename: str = "sample.csv",
    sheet_name: str | None = None,
    workbook_metadata: str | None = None,
    hidden_sheet: bool = False,
    merged_cells: bool = False,
    formula_cells: bool = False,
) -> dict[str, Any]:
    header_index = candidate_header_row(rows)
    if header_index is None:
        return _invalid_report("INVALID_SCHEMA", rows, sheet_name=sheet_name)
    headers = [str(value or "").strip() for value in rows[header_index]]
    mapping: dict[int, str] = {}
    duplicates: set[str] = set()
    for index, header in enumerate(headers):
        canonical = canonical_for_header(header)
        if canonical:
            if canonical in mapping.values():
                duplicates.add(canonical)
            else:
                mapping[index] = canonical
    raw_records: list[dict[str, Any]] = []
    blank_rows = 0
    notes: list[str] = []
    first_data_row: int | None = None
    last_data_row: int | None = None
    for row_index, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not any(value is not None and str(value).strip() for value in row):
            blank_rows += 1
            continue
        record: dict[str, Any] = {}
        presence: dict[str, str] = {}
        for column_index, canonical in mapping.items():
            value = row[column_index] if column_index < len(row) else None
            if canonical in REQUIRED_GROSS_FIELDS or canonical in {"net_volume", "net_value"}:
                parsed, state = classify_cell(value)
                record[canonical], presence[canonical] = parsed, state
            else:
                record[canonical] = value
        for required_field in REQUIRED_GROSS_FIELDS:
            if required_field not in mapping.values():
                record[required_field] = None
                presence[required_field] = "FIELD_ABSENT"
        kind = _row_kind(record)
        if kind == "note":
            notes.append(" ".join(str(value or "") for value in row))
        record.update({"_row_kind": kind, "_source_row": row_index, "field_presence": presence})
        raw_records.append(record)
        first_data_row = first_data_row or row_index
        last_data_row = row_index

    data_records = [record for record in raw_records if record["_row_kind"] not in {"note", "subtotal"}]
    detail_records = [record for record in data_records if record["_row_kind"] == "detail"]
    total_records = [record for record in data_records if record["_row_kind"] == "total"]
    matched_records = [record for record in data_records if record["_row_kind"] == "matched"]
    deal_records = [record for record in data_records if record["_row_kind"] == "deal"]

    date_proof = prove_trading_date(
        data_records,
        workbook_metadata=workbook_metadata,
        sheet_name=sheet_name,
        filename=filename,
    )
    units = prove_units(headers, notes)
    exchanges = {normalize_label(record.get("exchange")).upper() for record in data_records if record.get("exchange")}
    target = exchange.upper()
    explicit_exchange = "exchange" in mapping.values()
    context_hose = "hose" in normalize_label(" ".join(filter(None, (filename, sheet_name, workbook_metadata))))
    if explicit_exchange:
        target_records = [record for record in data_records if str(record.get("exchange") or "").upper() == target]
        scope_proven = bool(target_records)
        mixed = any(value and value != target for value in exchanges)
    else:
        target_records = data_records
        scope_proven = target == "HOSE" and context_hose
        mixed = False

    target_details = [record for record in target_records if record["_row_kind"] == "detail"]
    target_totals = [record for record in target_records if record["_row_kind"] == "total"]
    missing_required = {
        field for field in REQUIRED_GROSS_FIELDS if field not in mapping.values()
    }
    parse_failure = any(
        record["field_presence"].get(field) in {"FIELD_NULL", "FIELD_BLANK", "PARSE_FAILURE"}
        for record in target_records for field in REQUIRED_GROSS_FIELDS
        if field in mapping.values()
    )
    duplicate_risk = bool(duplicates) or _duplicate_risk(target_records)

    detail_sum = _sum_fields(target_details)
    stated_total = _sum_fields(target_totals[:1]) if target_totals else {field: None for field in REQUIRED_GROSS_FIELDS}
    reconciliation = reconcile(detail_sum, stated_total) if target_details and target_totals else {
        "status": "NOT_COMPARABLE", "differences": {}
    }

    component_check = "NOT_COMPARABLE"
    if target_totals and matched_records and deal_records:
        components = _sum_fields([*matched_records, *deal_records])
        component_check = reconcile(components, _sum_fields(target_totals[:1]))["status"]

    has_volume = {"buy_volume", "sell_volume"} <= set(mapping.values())
    has_value = {"buy_value", "sell_value"} <= set(mapping.values())
    mapped_fields = set(mapping.values())
    has_net_only = bool({"net_volume", "net_value"} & mapped_fields) and not bool(
        set(REQUIRED_GROSS_FIELDS) & mapped_fields
    )
    if has_net_only:
        quality = "NET_ONLY"
    elif not has_volume:
        quality = "MISSING_VOLUME"
    elif not has_value:
        quality = "MISSING_VALUE"
    elif not scope_proven:
        quality = "MIXED_EXCHANGE_UNFILTERABLE"
    elif units["volume"]["confidence"] == "UNKNOWN" or units["value"]["confidence"] == "UNKNOWN":
        quality = "AMBIGUOUS_UNIT"
    elif date_proof["confidence"] not in {"HIGH", "MEDIUM"}:
        quality = "AMBIGUOUS_DATE"
    elif duplicate_risk:
        quality = "DUPLICATE_OR_DOUBLE_COUNT_RISK"
    elif parse_failure or missing_required:
        quality = "INVALID_SCHEMA"
    elif reconciliation["status"] == "MATERIAL_MISMATCH":
        quality = "DUPLICATE_OR_DOUBLE_COUNT_RISK"
    elif target_totals:
        quality = "COMPLETE_GROSS_HOSE_TOTAL"
    elif target_details:
        quality = "COMPLETE_GROSS_HOSE_DETAIL"
    else:
        quality = "INVALID_SCHEMA"

    if target_totals and target_details:
        scope = "TOTAL_PLUS_SYMBOL_ROWS"
    elif target_totals:
        scope = "HOSE_TOTAL_ONLY"
    elif target_details and explicit_exchange and mixed:
        scope = "SYMBOL_ROWS_MULTI_EXCHANGE"
    elif target_details and scope_proven:
        scope = "SYMBOL_ROWS_HOSE_ONLY"
    elif has_net_only:
        scope = "NET_ONLY_SUMMARY"
    else:
        scope = "UNKNOWN_SCOPE"

    for record in data_records:
        if record.get("buy_volume") is not None and record.get("sell_volume") is not None:
            record["derived_net_volume"] = record["buy_volume"] - record["sell_volume"]
        else:
            record["derived_net_volume"] = None
        if record.get("buy_value") is not None and record.get("sell_value") is not None:
            record["derived_net_value"] = record["buy_value"] - record["sell_value"]
        else:
            record["derived_net_value"] = None
        record["net_volume_reconciliation"] = _net_status(record, "net_volume", "derived_net_volume")
        record["net_value_reconciliation"] = _net_status(record, "net_value", "derived_net_value")
    net_mismatch = any(
        record[key] == "MATERIAL_MISMATCH"
        for record in data_records
        for key in ("net_volume_reconciliation", "net_value_reconciliation")
    )
    if net_mismatch:
        quality = "DUPLICATE_OR_DOUBLE_COUNT_RISK"

    return {
        "quality_classification": quality,
        "schema_proven": quality in {"COMPLETE_GROSS_HOSE_TOTAL", "COMPLETE_GROSS_HOSE_DETAIL"},
        "scope_classification": scope,
        "scope_proven": scope_proven,
        "header_row": header_index + 1,
        "raw_columns": headers,
        "candidate_mapping": {headers[index]: canonical for index, canonical in mapping.items()},
        "row_count": len(data_records),
        "first_data_row": first_data_row,
        "last_data_row": last_data_row,
        "blank_row_count": blank_rows,
        "detail_row_count": len(target_details),
        "total_row_count": len(target_totals),
        "subtotal_row_count": sum(record["_row_kind"] == "subtotal" for record in raw_records),
        "note_row_count": sum(record["_row_kind"] == "note" for record in raw_records),
        "matched_row_count": len(matched_records),
        "deal_row_count": len(deal_records),
        "date_proof": date_proof,
        "units": units,
        "exchange_values": sorted(exchanges),
        "ticker_like_count": sum(bool(re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", str(record.get("ticker") or ""))) for record in data_records),
        "merged_cell_presence": merged_cells,
        "hidden_sheet": hidden_sheet,
        "formula_cell_presence": formula_cells,
        "duplicate_or_double_count_risk": duplicate_risk,
        "detail_sum": detail_sum,
        "stated_total": stated_total,
        "reconciliation": reconciliation,
        "component_reconciliation": component_check,
        "records": data_records,
    }


def _net_status(record: Mapping[str, Any], source_key: str, derived_key: str) -> str:
    source, derived = record.get(source_key), record.get(derived_key)
    if source is None:
        return "NOT_COMPARABLE"
    if derived is None:
        return "INSUFFICIENT_FIELDS"
    return "EXACT" if source == derived else "MATERIAL_MISMATCH"


def _invalid_report(quality: str, rows: Sequence[Sequence[Any]], *, sheet_name: str | None = None) -> dict[str, Any]:
    return {
        "quality_classification": quality,
        "schema_proven": False,
        "scope_classification": "UNKNOWN_SCOPE",
        "scope_proven": False,
        "header_row": None,
        "raw_columns": [],
        "candidate_mapping": {},
        "row_count": max(0, len(rows) - 1),
        "sheet_name": sheet_name,
        "records": [],
    }


def detect_csv_format(path: Path) -> tuple[str, str]:
    if path.stat().st_size > MAX_CSV_BYTES:
        raise ValueError("CSV exceeds diagnostic size limit")
    raw = path.read_bytes()
    encoding = next(
        (candidate for candidate in ("utf-8-sig", "utf-8", "cp1258", "cp1252") if _decodes(raw, candidate)),
        None,
    )
    if encoding is None:
        raise UnicodeError("Unsupported CSV encoding")
    sample = raw[:8192].decode(encoding)
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    return encoding, delimiter


def _decodes(raw: bytes, encoding: str) -> bool:
    try:
        raw.decode(encoding)
        return True
    except UnicodeDecodeError:
        return False


def inspect_file(path: Path, *, exchange: str = "HOSE", sheet: str | None = None) -> dict[str, Any]:
    path = path.resolve()
    extension = path.suffix.casefold()
    if extension not in SUPPORTED_EXTENSIONS:
        return {"file_type": extension or "unknown", "quality_classification": "UNSUPPORTED_FILE_FORMAT", "schema_proven": False}
    if not path.is_file():
        raise FileNotFoundError(path)
    common = {
        "input_path": str(path),
        "sanitized_filename": path.name,
        "file_type": extension,
        "file_size": path.stat().st_size,
        "file_modified_at": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
        "file_sha256": file_sha256(path),
    }
    if extension == ".csv":
        encoding, delimiter = detect_csv_format(path)
        with path.open("r", encoding=encoding, newline="") as handle:
            rows = [list(row) for row in csv.reader(handle, delimiter=delimiter)]
        report = inspect_rows(rows, exchange=exchange, filename=path.name, sheet_name="CSV")
        report.update({"workbook_sheet_names": ["CSV"], "selected_sheet": "CSV", "encoding": encoding, "delimiter": delimiter})
    elif extension == ".xlsx":
        from openpyxl import load_workbook

        workbook = load_workbook(path, data_only=False, read_only=False)
        sheet_names = list(workbook.sheetnames)
        if sheet is not None and sheet not in sheet_names:
            raise ValueError(f"Unknown sheet: {sheet}")
        selected = workbook[sheet] if sheet else next((item for item in workbook.worksheets if item.sheet_state == "visible"), workbook.active)
        rows = [[cell.value for cell in row] for row in selected.iter_rows()]
        formula_cells = any(cell.data_type == "f" for row in selected.iter_rows() for cell in row)
        report = inspect_rows(
            rows,
            exchange=exchange,
            filename=path.name,
            sheet_name=selected.title,
            workbook_metadata=workbook.properties.title,
            hidden_sheet=selected.sheet_state != "visible",
            merged_cells=bool(selected.merged_cells.ranges),
            formula_cells=formula_cells,
        )
        report.update({
            "workbook_sheet_names": sheet_names,
            "selected_sheet": selected.title,
            "hidden_sheet_names": [item.title for item in workbook.worksheets if item.sheet_state != "visible"],
        })
        workbook.close()
    else:
        try:
            import pandas as pd
            frame = pd.read_excel(path, sheet_name=sheet or 0, header=None)
        except (ImportError, ValueError) as exc:
            return {**common, "quality_classification": "UNSUPPORTED_FILE_FORMAT", "schema_proven": False, "failure_class": type(exc).__name__}
        rows = frame.where(frame.notna(), None).values.tolist()
        report = inspect_rows(rows, exchange=exchange, filename=path.name, sheet_name=sheet or "0")
        report.update({"workbook_sheet_names": [], "selected_sheet": sheet or "0"})
    return {**common, **report}


def sanitized_preview(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    for record in records[:MAX_PREVIEW_ROWS]:
        preview.append({
            "row_kind": record.get("_row_kind"),
            "source_row": record.get("_source_row"),
            "ticker_present": bool(record.get("ticker")),
            "exchange_present": bool(record.get("exchange")),
            "field_presence": record.get("field_presence", {}),
        })
    return preview


def write_reports(output_dir: Path, report: Mapping[str, Any]) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    records = report.get("records") or []
    source = {key: report.get(key) for key in (
        "sanitized_filename", "file_type", "file_size", "file_modified_at", "file_sha256",
        "workbook_sheet_names", "selected_sheet",
    )}
    schema = {key: value for key, value in report.items() if key not in {"records", "input_path", "detail_sum", "stated_total", "reconciliation"}}
    paths = [
        output_dir / "source_report.json",
        output_dir / "schema_report.json",
        output_dir / "reconciliation_report.json",
        output_dir / "sanitized_preview.csv",
    ]
    paths[0].write_text(json.dumps(source, indent=2, sort_keys=True), encoding="utf-8")
    paths[1].write_text(json.dumps(schema, indent=2, sort_keys=True, default=str), encoding="utf-8")
    paths[2].write_text(json.dumps({
        "detail_sum": report.get("detail_sum"),
        "stated_total": report.get("stated_total"),
        "reconciliation": report.get("reconciliation"),
        "component_reconciliation": report.get("component_reconciliation"),
    }, indent=2, sort_keys=True), encoding="utf-8")
    preview = sanitized_preview(records)
    with paths[3].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("row_kind", "source_row", "ticker_present", "exchange_present", "field_presence"))
        writer.writeheader()
        for row in preview:
            writer.writerow({**row, "field_presence": json.dumps(row["field_presence"], sort_keys=True)})
    return paths


def diagnostic_outcome(report: Mapping[str, Any]) -> str:
    if report.get("schema_proven"):
        return "VN_PROPRIETARY_EOD_SOURCE_SCHEMA_PROVEN"
    quality = report.get("quality_classification")
    if quality == "UNSUPPORTED_FILE_FORMAT":
        return "VN_PROPRIETARY_EOD_SOURCE_UNSUPPORTED_FORMAT"
    if quality in {"NET_ONLY", "MISSING_VOLUME", "MISSING_VALUE", "INVALID_SCHEMA"}:
        return "VN_PROPRIETARY_EOD_SOURCE_INSUFFICIENT_GROSS_FIELDS"
    if quality == "MIXED_EXCHANGE_UNFILTERABLE":
        return "VN_PROPRIETARY_EOD_SOURCE_HOSE_SCOPE_UNPROVEN"
    if quality == "AMBIGUOUS_UNIT":
        return "VN_PROPRIETARY_EOD_SOURCE_UNIT_UNPROVEN"
    if report.get("reconciliation", {}).get("status") == "MATERIAL_MISMATCH":
        return "VN_PROPRIETARY_EOD_SOURCE_RECONCILIATION_FAILED"
    return "VN_PROPRIETARY_EOD_SOURCE_SAMPLE_REQUIRED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--exchange", default="HOSE", choices=("HOSE",))
    parser.add_argument("--sheet")
    parser.add_argument("--output-dir", type=Path, default=Path(".tmp/vn-proprietary-eod0"))
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    report = inspect_file(args.file, exchange=args.exchange, sheet=args.sheet)
    paths = write_reports(args.output_dir, report)
    payload = {
        "mode": "vn_proprietary_eod_source_gate",
        "outcome": diagnostic_outcome(report),
        "schema_proven": bool(report.get("schema_proven")),
        "quality_classification": report.get("quality_classification"),
        "sanitized_filename": report.get("sanitized_filename"),
        "file_sha256": report.get("file_sha256"),
        "artifacts": [] if args.cleanup else [str(path) for path in paths],
        "production_storage_mutated": False,
        "network_calls_made": 0,
    }
    if args.cleanup:
        shutil.rmtree(args.output_dir, ignore_errors=True)
    print(json.dumps(payload, sort_keys=True), flush=True)
    return 2 if args.strict and not report.get("schema_proven") else 0


if __name__ == "__main__":
    raise SystemExit(main())
