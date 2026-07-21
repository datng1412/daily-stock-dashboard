#!/usr/bin/env python
"""Secret-safe capability gate for an SSI-derived HOSE foreign-flow aggregate.

The module is intentionally import-safe. Provider construction and network work
occur only from ``main`` after ``--allow-live`` has passed CLI validation.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import sys
from time import perf_counter
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence


PHASE = "4.12F-A"
SOURCE = "SSI FastConnect"
SDK_MODULE = "ssi_fc_data.model.model"
MODES = ("config", "universe", "bulk", "sample", "decision", "security-type", "details-contract")
TYPE_SOURCES = ("auto", "securities", "details")
SAMPLE_SIZES = (10, 30, 100)
HISTORY_SESSIONS = (1, 5, 20)
MAX_CONCURRENCY = 4
MAX_BULK_CANDIDATES = 3
INTERACTIVE_COLD_SECONDS = 20.0
INTERACTIVE_REPEAT_SECONDS = 3.0
INTERACTIVE_CAPTURE_SPAN_SECONDS = 30.0
MATERIALIZATION_SECONDS = 300.0
MIN_COVERAGE_RATIO = 0.95
SAFE_FAILURE_CLASSES = {
    "auth_failed",
    "permission_denied",
    "rate_limited",
    "network_error",
    "timeout",
    "parse_failed",
    "empty_response",
    "provider_unavailable",
    "provider_exception",
}
SECRET_KEYS = {
    "authorization",
    "bearer",
    "accesstoken",
    "access_token",
    "consumerid",
    "consumer_id",
    "consumersecret",
    "consumer_secret",
    "cookie",
    "accountid",
    "account_id",
    "api_key",
    "apikey",
    "raw_payload",
    "response_body",
    "exception",
}
HOSE_ALIASES = {"HOSE", "HSX", "HO"}
TYPE_ALIASES = {
    "common_stock": {
        "common_stock", "common stock", "common", "ordinary_stock",
        "ordinary stock", "stock", "equity",
    },
    "preferred_stock": {"preferred_stock", "preferred stock", "preference share"},
    "etf": {"etf", "exchange traded fund", "exchange-traded fund"},
    "fund": {"fund", "closed end fund", "open end fund", "mutual fund"},
    "covered_warrant": {"covered_warrant", "covered warrant", "warrant"},
    "bond": {"bond", "corporate bond", "government bond"},
    "derivative": {"derivative", "future", "futures", "option"},
}
TYPE_FIELD_ALIASES = {
    "securitytype",
    "securitiestype",
    "stocktype",
    "instrumenttype",
    "securitygroup",
    "sectype",
    "assettype",
    "producttype",
    "type",
    "typename",
    "securitytypename",
}
REPOSITORY_MAPPED_TYPE_FIELDS = {"SecurityType", "SecuritiesType", "Type", "StockType"}
TYPE_OUTCOMES = {
    "A": "AUTHORITY RESOLVED FROM SECURITIES",
    "B": "AUTHORITY RESOLVED FROM SECURITIESDETAILS",
    "C": "AUTHORITY POSSIBLE ONLY THROUGH MATERIALIZED CLASSIFICATION",
    "D": "TYPE SEMANTICS AMBIGUOUS",
    "E": "PROVIDER SCALE UNSAFE",
    "F": "INCONCLUSIVE",
}
DETAILS_CONTRACT_OUTCOMES = {
    "A": "EXACT CONTRACT RESOLVED, TYPE FIELD PRESENT",
    "B": "EXACT CONTRACT RESOLVED, TYPE FIELD ABSENT",
    "C": "EXACT CONTRACT RESOLVED, TYPE SEMANTICS AMBIGUOUS",
    "D": "DIRECT REQUEST/FETCHER/PARSER DEFECT FIXED",
    "E": "SECURITIESDETAILS EXACT-SYMBOL CONTRACT UNSUPPORTED",
    "F": "INCONCLUSIVE",
}
DETAILS_COLLECTION_KEYS = (
    "data", "Data", "items", "Items", "rows", "Rows",
    "securities", "Securities", "securitiesDetails", "SecuritiesDetails",
)
OUTCOMES = {
    "A": "GO: VERIFIED SSI BULK PATH",
    "B": "GO: SAFE BOUNDED PER-SYMBOL PATH",
    "C": "GO ONLY WITH MATERIALIZED SNAPSHOT",
    "D": "NO-GO: PROVIDER BUDGET OR SCALE UNSAFE",
    "E": "HOSE UNIVERSE AUTHORITY UNRESOLVED",
    "F": "INCONCLUSIVE",
}


@dataclass(frozen=True)
class UniverseRow:
    symbol: str
    exchange: str
    market: Optional[str]
    security_type: str
    security_type_status: str
    active_status: str
    source: str
    provider_identifier: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _pick(row: Mapping[str, Any], *keys: str) -> Any:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        if key in row:
            return row[key]
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def normalize_exchange(value: Any) -> Optional[str]:
    normalized = (_text(value) or "").upper()
    return "HOSE" if normalized in HOSE_ALIASES else normalized or None


def classify_security_type(value: Any) -> tuple[str, str]:
    normalized = re.sub(r"\s+", " ", (_text(value) or "").lower().replace("-", " ").replace("_", " "))
    if not normalized:
        return "unknown", "missing"
    for category, aliases in TYPE_ALIASES.items():
        normalized_aliases = {re.sub(r"\s+", " ", alias.lower().replace("-", " ").replace("_", " ")) for alias in aliases}
        if normalized in normalized_aliases:
            return category, "verified"
    return "other", "unrecognized"


def normalize_symbol(value: Any) -> Optional[str]:
    normalized = (_text(value) or "").upper()
    if normalized.endswith(".VN"):
        normalized = normalized[:-3]
    return normalized if re.fullmatch(r"[A-Z0-9]{1,10}", normalized) else None


def normalize_field_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def is_type_candidate_field(value: Any) -> bool:
    return normalize_field_name(value) in TYPE_FIELD_ALIASES


def _bounded_scalar(value: Any) -> Optional[str]:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return None
    text = str(value).strip()
    return text[:80] if text else None


def inventory_type_fields(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return field-name/value evidence only; never retain or expose raw rows."""
    materialized = [row for row in rows if isinstance(row, Mapping)]
    all_field_names = sorted({str(key) for row in materialized for key in row})
    candidate_names = sorted({name for name in all_field_names if is_type_candidate_field(name)})
    fields_result: list[dict[str, Any]] = []
    for field_name in candidate_names:
        presence = 0
        non_null = 0
        distinct: set[str] = set()
        classifications: set[str] = set()
        statuses: set[str] = set()
        for row in materialized:
            actual = next((key for key in row if str(key).lower() == field_name.lower()), None)
            if actual is None:
                continue
            presence += 1
            value = _bounded_scalar(row.get(actual))
            if value is None:
                continue
            non_null += 1
            distinct.add(value)
            classification, status = classify_security_type(value)
            classifications.add(classification)
            statuses.add(status)
        if non_null == 0:
            semantic_status = "absent"
        elif statuses == {"verified"}:
            semantic_status = "verified"
        elif all(re.fullmatch(r"[A-Z0-9_-]{1,8}", value.upper()) for value in distinct):
            semantic_status = "ambiguous"
        else:
            semantic_status = "plausible_unverified"
        fields_result.append(
            {
                "field_name": field_name,
                "presence_count": presence,
                "non_null_count": non_null,
                "distinct_value_count": len(distinct),
                "bounded_distinct_values": sorted(distinct)[:20],
                "documentation_evidence": False,
                "sdk_evidence": False,
                "repository_evidence": field_name in REPOSITORY_MAPPED_TYPE_FIELDS,
                "semantic_status": semantic_status,
                "mapped_classifications": sorted(classifications - {"unknown", "other"}),
            }
        )
    return {
        "raw_field_names": all_field_names,
        "candidate_field_count": len(fields_result),
        "candidate_fields": fields_result,
    }


def classify_authority_rows(rows: Iterable[Mapping[str, Any]], inventory: Mapping[str, Any]) -> dict[str, Any]:
    verified_names = {
        str(field.get("field_name"))
        for field in inventory.get("candidate_fields", [])
        if isinstance(field, Mapping) and field.get("semantic_status") == "verified"
    }
    counts: Counter[str] = Counter()
    exact_hose_count = 0
    invalid_symbol_count = 0
    duplicate_count = 0
    mismatched_market_count = 0
    seen: set[str] = set()
    samples: list[dict[str, Any]] = []
    for row in rows:
        symbol = normalize_symbol(_pick(row, "symbol", "Symbol", "ticker", "SecurityCode"))
        if not symbol:
            invalid_symbol_count += 1
            continue
        if symbol in seen:
            duplicate_count += 1
            continue
        seen.add(symbol)
        exchange = normalize_exchange(_pick(row, "exchange", "Exchange", "market", "Market"))
        if exchange != "HOSE":
            mismatched_market_count += 1
            continue
        exact_hose_count += 1
        row_classes: set[str] = set()
        sample_values: dict[str, str] = {}
        for key, value in row.items():
            matching_name = next((name for name in verified_names if name.lower() == str(key).lower()), None)
            if not matching_name:
                continue
            bounded = _bounded_scalar(value)
            if bounded is None:
                continue
            classification, status = classify_security_type(bounded)
            if status == "verified":
                row_classes.add(classification)
                sample_values[matching_name] = bounded
        if len(row_classes) > 1:
            counts["conflicting"] += 1
            classification = "conflicting"
        elif len(row_classes) == 1:
            classification = next(iter(row_classes))
            counts[classification] += 1
            counts["classified"] += 1
        else:
            classification = "unknown"
            counts["unknown"] += 1
        if len(samples) < 5:
            samples.append({"symbol": symbol, "exchange": "HOSE", "classification": classification, "candidate_values": sample_values})
    authority = bool(exact_hose_count) and counts["classified"] == exact_hose_count and counts["unknown"] == 0 and counts["conflicting"] == 0
    return {
        "authority": authority,
        "attempted_count": len(seen),
        "exact_match_count": exact_hose_count,
        "classified_count": counts["classified"],
        "classification_coverage_ratio": counts["classified"] / exact_hose_count if exact_hose_count else 0.0,
        "common_stock_count": counts["common_stock"],
        "preferred_stock_count": counts["preferred_stock"],
        "etf_count": counts["etf"],
        "fund_count": counts["fund"],
        "covered_warrant_count": counts["covered_warrant"],
        "bond_count": counts["bond"],
        "derivative_count": counts["derivative"],
        "other_count": counts["other"],
        "unknown_count": counts["unknown"],
        "conflicting_count": counts["conflicting"],
        "invalid_symbol_count": invalid_symbol_count,
        "duplicate_count": duplicate_count,
        "mismatched_market_count": mismatched_market_count,
        "samples": samples,
    }


def normalize_universe_rows(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    provider_rows = 0
    invalid_symbol_rows = 0
    duplicate_rows = 0
    missing_exchange_count = 0
    missing_security_type_count = 0
    non_hose_rows = 0
    by_symbol: dict[str, UniverseRow] = {}
    conflicts: set[str] = set()
    for raw in rows:
        provider_rows += 1
        symbol = normalize_symbol(_pick(raw, "symbol", "Symbol", "ticker", "SecurityCode"))
        if not symbol:
            invalid_symbol_rows += 1
            continue
        exchange = normalize_exchange(_pick(raw, "exchange", "Exchange", "market", "Market"))
        if exchange is None:
            missing_exchange_count += 1
            continue
        if exchange != "HOSE":
            non_hose_rows += 1
            continue
        raw_type = _pick(raw, "security_type", "SecurityType", "SecuritiesType", "StockType", "Type")
        security_type, type_status = classify_security_type(raw_type)
        if type_status == "missing":
            missing_security_type_count += 1
        active_value = _pick(raw, "active_status", "ActiveStatus", "status", "Status", "isActive")
        active_status = "unknown" if active_value in (None, "") else str(active_value).strip().lower()
        candidate = UniverseRow(
            symbol=symbol,
            exchange="HOSE",
            market=normalize_exchange(_pick(raw, "market", "Market")),
            security_type=security_type,
            security_type_status=type_status,
            active_status=active_status,
            source=SOURCE,
            provider_identifier=symbol,
        )
        previous = by_symbol.get(symbol)
        if previous is not None:
            duplicate_rows += 1
            if previous != candidate:
                conflicts.add(symbol)
            continue
        by_symbol[symbol] = candidate

    normalized = [asdict(by_symbol[symbol]) for symbol in sorted(by_symbol)]
    counts = Counter(row["security_type"] for row in normalized)
    unknown_count = counts["unknown"]
    ambiguous_type_count = counts["other"] + len(conflicts)
    authority = bool(normalized) and unknown_count == 0 and ambiguous_type_count == 0
    universe_hash = hashlib.sha256(",".join(row["symbol"] for row in normalized).encode("utf-8")).hexdigest()
    return {
        "status": "ready" if authority else "unresolved",
        "authority": authority,
        "provider_rows": provider_rows,
        "normalized_rows": len(normalized),
        "eligible_symbols": [row["symbol"] for row in normalized if row["security_type"] == "common_stock"],
        "eligible_common_stock_count": counts["common_stock"],
        "preferred_stock_count": counts["preferred_stock"],
        "etf_count": counts["etf"],
        "fund_count": counts["fund"],
        "covered_warrant_count": counts["covered_warrant"],
        "bond_count": counts["bond"],
        "derivative_count": counts["derivative"],
        "other_count": counts["other"],
        "unknown_count": unknown_count,
        "invalid_symbol_rows": invalid_symbol_rows,
        "duplicate_rows": duplicate_rows,
        "non_hose_rows": non_hose_rows,
        "missing_exchange_count": missing_exchange_count,
        "missing_security_type_count": missing_security_type_count,
        "ambiguous_type_count": ambiguous_type_count,
        "conflicting_duplicate_symbols": sorted(conflicts)[:5],
        "universe_hash": universe_hash,
        "sample_rows": normalized[:5],
    }


def inspect_sdk_capability() -> dict[str, Any]:
    result: dict[str, Any] = {
        "module": SDK_MODULE,
        "installed": False,
        "daily_stock_price_fields": [],
        "securities_fields": [],
        "securities_details_fields": [],
        "bulk_candidate_count": 0,
        "bulk_state": "inconclusive",
    }
    try:
        model = importlib.import_module(SDK_MODULE)
    except (ImportError, ModuleNotFoundError):
        result["bulk_state"] = "inconclusive"
        return result
    result["installed"] = True
    for name in ("daily_stock_price", "securities", "securities_details"):
        cls = getattr(model, name, None)
        if cls is None:
            continue
        names = [field.name for field in fields(cls)] if is_dataclass(cls) else []
        result[f"{name}_fields"] = names
    daily_fields = result["daily_stock_price_fields"]
    supports_multi = any(name.lower() in {"symbols", "symbol_list", "tickers"} for name in daily_fields)
    result["bulk_state"] = "verified_model_candidate" if supports_multi else "unsupported"
    result["bulk_candidate_count"] = 1 if supports_multi else 0
    result["evidence"] = (
        "Official installed request model exposes an explicit multi-symbol field."
        if supports_multi
        else "Official installed request model and existing fetcher expose one symbol field only; no broad shape is evidence-backed."
    )
    return result


def assess_bulk_pages(pages: Sequence[Mapping[str, Any]], page_size: int) -> dict[str, Any]:
    """Assess already-sanitized/mock broad pages without issuing a request."""
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    seen: set[tuple[str, str]] = set()
    symbols: set[str] = set()
    dates: set[str] = set()
    duplicate_rows = 0
    mismatched_market_rows = 0
    missing_identity_rows = 0
    total_hint: Optional[int] = None
    accepted_rows = 0
    for page in pages:
        if str(page.get("status") or "ok").lower() != "ok":
            return {
                "state": "rejected",
                "failure_class": _failure_class(page),
                "safe_to_use": False,
            }
        rows = page.get("rows") if isinstance(page.get("rows"), list) else []
        hint = page.get("total") or page.get("total_record") or page.get("totalRecord")
        if hint is not None:
            try:
                total_hint = int(hint)
            except (TypeError, ValueError):
                return {"state": "rejected", "reason": "invalid_total_hint", "safe_to_use": False}
        for row in rows:
            if not isinstance(row, Mapping):
                missing_identity_rows += 1
                continue
            symbol = normalize_symbol(_pick(row, "symbol", "Symbol"))
            trading_date = _text(_pick(row, "date", "TradingDate", "tradingDate"))
            market = normalize_exchange(_pick(row, "exchange", "Exchange", "market", "Market"))
            if not symbol or not trading_date:
                missing_identity_rows += 1
                continue
            if market != "HOSE":
                mismatched_market_rows += 1
                continue
            key = (symbol, trading_date)
            if key in seen:
                duplicate_rows += 1
                continue
            seen.add(key)
            symbols.add(symbol)
            dates.add(trading_date)
            accepted_rows += 1
    last_rows = pages[-1].get("rows") if pages and isinstance(pages[-1].get("rows"), list) else []
    truncation = bool(total_hint is not None and accepted_rows < total_hint)
    if total_hint is None and pages and len(last_rows) >= page_size:
        truncation = True
    safe = bool(accepted_rows) and not missing_identity_rows and not mismatched_market_rows and not truncation
    return {
        "state": "verified" if safe else "rejected",
        "safe_to_use": safe,
        "page_count": len(pages),
        "accepted_row_count": accepted_rows,
        "unique_symbol_count": len(symbols),
        "unique_date_count": len(dates),
        "duplicate_rows": duplicate_rows,
        "missing_identity_rows": missing_identity_rows,
        "mismatched_market_rows": mismatched_market_rows,
        "truncation_detected": truncation,
    }


def should_escalate_sample(result: Mapping[str, Any], next_size: int) -> bool:
    if next_size not in SAMPLE_SIZES:
        return False
    if int(result.get("rate_limit_count") or 0) > 0:
        return False
    if int(result.get("auth_failed_count") or 0) > 0:
        return False
    if int(result.get("unhandled_failure_count") or 0) > 0:
        return False
    if int(result.get("timeout_count") or 0) > 0:
        return False
    projected = float(result.get("projected_duration_seconds") or result.get("total_duration_seconds") or 0.0)
    return projected <= MATERIALIZATION_SECONDS


def select_even_sample(symbols: Sequence[str], sample_size: int) -> list[str]:
    normalized = sorted(set(filter(None, (normalize_symbol(value) for value in symbols))))
    if sample_size not in SAMPLE_SIZES:
        raise ValueError(f"sample_size must be one of {SAMPLE_SIZES}")
    if sample_size > len(normalized):
        raise ValueError("sample_size exceeds eligible provider-derived universe")
    if sample_size == 1:
        return normalized[:1]
    indexes = [round(index * (len(normalized) - 1) / (sample_size - 1)) for index in range(sample_size)]
    return [normalized[index] for index in indexes]


def _failure_class(payload: Mapping[str, Any]) -> Optional[str]:
    value = _text(payload.get("failure_class"))
    if value in SAFE_FAILURE_CLASSES:
        return value
    code = str(payload.get("code") or payload.get("http_status") or "")
    if code == "429":
        return "rate_limited"
    status = str(payload.get("status") or "").lower()
    return "provider_unavailable" if status in {"unavailable", "disabled"} else None


def measure_symbol_sample(
    symbols: Sequence[str],
    history_sessions: int,
    fetch: Callable[[str, int], Mapping[str, Any]],
) -> dict[str, Any]:
    started_wall = utc_now()
    started = perf_counter()
    latest_dates: Counter[str] = Counter()
    result = Counter()
    captures: list[datetime] = []
    for symbol in symbols:
        capture = utc_now()
        captures.append(capture)
        try:
            payload = dict(fetch(symbol, history_sessions))
        except Exception:
            result["unhandled_failure_count"] += 1
            result["unavailable_count"] += 1
            continue
        result["provider_call_count"] += 1
        failure = _failure_class(payload)
        if failure:
            result["unavailable_count"] += 1
            result[f"{failure}_count"] += 1
            continue
        rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
        if not rows:
            result["unavailable_count"] += 1
            result["empty_response_count"] += 1
            continue
        result["success_count"] += 1
        latest = rows[-1] if isinstance(rows[-1], Mapping) else {}
        latest_date = _text(latest.get("date"))
        if latest_date:
            latest_dates[latest_date] += 1
        value_present = any(row.get("foreign_net_value") is not None for row in rows if isinstance(row, Mapping))
        volume_present = any(row.get("foreign_net_volume") is not None for row in rows if isinstance(row, Mapping))
        result["value_covered_count"] += int(value_present)
        result["volume_covered_count"] += int(volume_present)
        if not value_present or not volume_present:
            result["partial_count"] += 1
    completed = utc_now()
    total = len(symbols)
    duration = perf_counter() - started
    return {
        "status": "measured",
        "sample_size": total,
        "history_sessions": history_sessions,
        "total_duration_seconds": round(duration, 6),
        "provider_call_count": result["provider_call_count"],
        "token_call_count": None,
        "token_call_count_status": "unavailable",
        "success_count": result["success_count"],
        "partial_count": result["partial_count"],
        "unavailable_count": result["unavailable_count"],
        "unhandled_failure_count": result["unhandled_failure_count"],
        "value_covered_count": result["value_covered_count"],
        "value_coverage_ratio": result["value_covered_count"] / total if total else 0.0,
        "volume_covered_count": result["volume_covered_count"],
        "volume_coverage_ratio": result["volume_covered_count"] / total if total else 0.0,
        "rate_limit_count": result["rate_limited_count"],
        "timeout_count": result["timeout_count"],
        "network_error_count": result["network_error_count"],
        "auth_failed_count": result["auth_failed_count"] + result["permission_denied_count"],
        "capture_started_at": started_wall.isoformat(),
        "capture_completed_at": completed.isoformat(),
        "capture_span_seconds": round((captures[-1] - captures[0]).total_seconds(), 6) if captures else 0.0,
        "latest_date_distribution": dict(sorted(latest_dates.items())),
        "most_common_latest_date": latest_dates.most_common(1)[0][0] if latest_dates else None,
    }


def project_full_universe(sample: Mapping[str, Any], universe_size: int) -> dict[str, Any]:
    sample_size = int(sample.get("sample_size") or 0)
    if sample_size <= 0:
        return {"status": "unavailable"}
    factor = universe_size / sample_size
    return {
        "status": "projected",
        "universe_size": universe_size,
        "duration_seconds": round(float(sample.get("total_duration_seconds") or 0.0) * factor, 3),
        "provider_call_count": round(float(sample.get("provider_call_count") or 0.0) * factor),
        "coverage_ratios_inherited_from_sample": True,
    }


def decide(evidence: Mapping[str, Any]) -> dict[str, Any]:
    universe = evidence.get("universe") if isinstance(evidence.get("universe"), Mapping) else {}
    bulk = evidence.get("bulk_capability") if isinstance(evidence.get("bulk_capability"), Mapping) else {}
    full = evidence.get("full_universe_result") if isinstance(evidence.get("full_universe_result"), Mapping) else {}
    failure = _text(universe.get("failure_class"))
    if universe.get("status") == "unavailable" or failure in {"auth_failed", "permission_denied", "network_error", "timeout"}:
        code, reason = "F", "Authoritative live universe evidence could not be collected."
    elif universe.get("authority") is False:
        code, reason = "E", "SSI rows do not prove an exact, conservatively classified HOSE common-stock universe."
    elif bulk.get("state") == "verified" and bulk.get("safe_to_use") is True:
        code, reason = "A", "An SDK-backed, identity-safe, paginated SSI bulk path met the provider budget."
    elif full.get("status") != "measured":
        code, reason = "F", "No measured full-universe result exists; sample projection alone cannot open production."
    else:
        coverage = min(float(full.get("value_coverage_ratio") or 0), float(full.get("volume_coverage_ratio") or 0))
        rate_limits = int(full.get("rate_limit_count") or 0)
        unhandled = int(full.get("unhandled_failure_count") or 0)
        duration = float(full.get("total_duration_seconds") or float("inf"))
        repeat = float(full.get("repeat_duration_seconds") or float("inf"))
        span = float(full.get("capture_span_seconds") or float("inf"))
        if coverage >= MIN_COVERAGE_RATIO and rate_limits == 0 and unhandled == 0 and duration <= INTERACTIVE_COLD_SECONDS and repeat <= INTERACTIVE_REPEAT_SECONDS and span <= INTERACTIVE_CAPTURE_SPAN_SECONDS:
            code, reason = "B", "Measured bounded per-symbol collection met every interactive threshold."
        elif coverage >= MIN_COVERAGE_RATIO and rate_limits == 0 and unhandled == 0 and duration <= MATERIALIZATION_SECONDS:
            code, reason = "C", "Measured collection is suitable only for a backend-owned materialized snapshot."
        else:
            code, reason = "D", "Measured provider budget, failure, or coverage thresholds are unsafe."
    return {
        "code": code,
        "outcome": OUTCOMES[code],
        "reason": reason,
        "production_gate_open": code in {"A", "B", "C"},
        "hose_scope_status": "future_phase_allowed" if code in {"A", "B", "C"} else "unavailable",
    }


def decide_type_authority(evidence: Mapping[str, Any]) -> dict[str, Any]:
    securities = evidence.get("securities") if isinstance(evidence.get("securities"), Mapping) else {}
    details = evidence.get("details") if isinstance(evidence.get("details"), Mapping) else {}
    for result in (securities, details):
        if result.get("status") == "unavailable":
            code = "F"
            reason = "Required live SSI metadata evidence was unavailable."
            break
    else:
        if securities.get("authority") is True:
            code = "A"
            reason = "Securities explicitly classified every exact HOSE instrument with no unknown or conflicting row."
        elif details.get("full_universe") is True and details.get("authority") is True:
            duration = float(details.get("duration_seconds") or float("inf"))
            if int(details.get("rate_limit_count") or 0) or int(details.get("unhandled_failure_count") or 0):
                code, reason = "E", "Full-universe Details classification exceeded the safe provider failure budget."
            elif duration <= INTERACTIVE_COLD_SECONDS:
                code, reason = "B", "Full-universe Details classification met the interactive authority budget."
            elif duration <= MATERIALIZATION_SECONDS:
                code, reason = "C", "Full-universe Details classification is authoritative only as materialized metadata."
            else:
                code, reason = "E", "Full-universe Details classification exceeded five minutes."
        elif details:
            projected = details.get("projected_full_universe_seconds")
            if int(details.get("rate_limit_count") or 0) or (projected is not None and float(projected) > MATERIALIZATION_SECONDS):
                code, reason = "E", "Bounded Details evidence makes the provider scale unsafe for complete classification."
            elif int(details.get("exact_symbol_mismatch_count") or 0) or int(details.get("candidate_field_count") or 0) == 0:
                code, reason = "F", "The bounded Details stage returned no exact type-bearing row, so type semantics could not be inspected."
            elif int(details.get("unknown_count") or 0) or int(details.get("conflicting_count") or 0):
                code, reason = "D", "SSI metadata type semantics are absent, ambiguous, unknown, or conflicting."
            else:
                code, reason = "F", "A partial Details sample cannot prove full-universe authority."
        elif securities:
            candidate_fields = securities.get("field_inventory", {}).get("candidate_fields", []) if isinstance(securities.get("field_inventory"), Mapping) else []
            if candidate_fields:
                code, reason = "D", "Securities contains type-like fields without complete verified semantics."
            else:
                code, reason = "F", "Securities did not resolve authority; Details evidence has not been collected."
        else:
            code, reason = "F", "No live authority evidence was collected."
    return {
        "code": code,
        "outcome": TYPE_OUTCOMES[code],
        "reason": reason,
        "production_gate_open": code in {"A", "B", "C"},
        "hose_scope_status": "future_phase_allowed" if code in {"A", "B", "C"} else "unavailable",
    }


def sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = re.sub(r"[^a-z0-9_]", "", str(key).lower())
            if normalized_key in SECRET_KEYS or any(secret in normalized_key for secret in ("token", "secret", "cookie", "authorization", "accountid")):
                continue
            safe[str(key)] = sanitize(item)
        return safe
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        scrubbed = re.sub(r"(?i)(authorization|bearer|access[_-]?token|consumer[_-]?(?:id|secret)|cookie|account[_-]?id|api[_-]?key)\s*[:=]\s*\S+", "[redacted]", value)
        return scrubbed[:500]
    return value


def config_result(mode: str) -> dict[str, Any]:
    enabled = str(os.getenv("SSI_FASTCONNECT_ENABLED", "")).strip().lower() in {"1", "true", "yes", "on"}
    credentials_present = bool(os.getenv("SSI_FASTCONNECT_CONSUMER_ID")) and bool(os.getenv("SSI_FASTCONNECT_CONSUMER_SECRET"))
    return {
        "phase": PHASE,
        "generated_at": utc_now().isoformat(),
        "mode": mode,
        "network_used": False,
        "environment": {"provider_enabled": enabled, "credentials_present": credentials_present, "credential_values_exposed": False},
        "package_capability": inspect_sdk_capability(),
        "thresholds": {
            "interactive_cold_seconds": INTERACTIVE_COLD_SECONDS,
            "interactive_cached_seconds": INTERACTIVE_REPEAT_SECONDS,
            "interactive_capture_span_seconds": INTERACTIVE_CAPTURE_SPAN_SECONDS,
            "materialization_seconds": MATERIALIZATION_SECONDS,
            "minimum_value_coverage_ratio": MIN_COVERAGE_RATIO,
            "minimum_volume_coverage_ratio": MIN_COVERAGE_RATIO,
            "maximum_concurrency": MAX_CONCURRENCY,
        },
        "limitations": ["Configuration inspection is not live provider proof.", "No production HOSE aggregate or frontend scope is implemented."],
    }


def _load_live_fetcher() -> Any:
    from data_provider.ssi_fastconnect_fetcher import SsiFastConnectFetcher
    return SsiFastConnectFetcher()


def install_live_counters(fetcher: Any) -> Counter[str]:
    """Instrument one audit-owned fetcher instance without changing production code."""
    counters: Counter[str] = Counter()
    original_request = fetcher._request
    original_post = fetcher.session.post

    def counted_request(endpoint: str, params: Optional[dict[str, Any]] = None) -> Any:
        counters["provider_calls"] += 1
        payload = original_request(endpoint, params=params)
        failure = _failure_class(payload) if isinstance(payload, Mapping) else None
        if failure:
            counters[failure] += 1
        return payload

    def counted_post(*args: Any, **kwargs: Any) -> Any:
        counters["token_http_calls"] += 1
        return original_post(*args, **kwargs)

    fetcher._request = counted_request
    fetcher.session.post = counted_post
    return counters


def run_live_universe(fetcher: Any) -> dict[str, Any]:
    payload = fetcher.get_securities(market="HOSE")
    if str(payload.get("status") or "").lower() != "ok":
        return {"status": "unavailable", "authority": None, "failure_class": _failure_class(payload), "reason": _text(payload.get("reason"))}
    return normalize_universe_rows(payload.get("rows") or [])


def extract_provider_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping) or str(payload.get("status") or "").lower() == "unavailable":
        return []
    for key in DETAILS_COLLECTION_KEYS:
        value = payload.get(key)
        if isinstance(value, list):
            return [dict(row) for row in value if isinstance(row, Mapping)]
        if isinstance(value, Mapping):
            for nested_key in DETAILS_COLLECTION_KEYS:
                nested = value.get(nested_key)
                if isinstance(nested, list):
                    return [dict(row) for row in nested if isinstance(row, Mapping)]
            if normalize_symbol(_pick(value, "symbol", "Symbol", "ticker", "SecurityCode", "StockSymbol", "StockCode")):
                return [dict(value)]
    if normalize_symbol(_pick(payload, "symbol", "Symbol", "ticker", "SecurityCode", "StockSymbol", "StockCode")):
        return [dict(payload)]
    return []


def details_contract_candidates(symbols: Sequence[str], candidate_count: int) -> list[dict[str, Any]]:
    normalized = sorted(set(filter(None, (normalize_symbol(symbol) for symbol in symbols))))
    if candidate_count not in {1, 2, 3}:
        raise ValueError("candidate_count must be between 1 and 3")
    if not normalized:
        raise ValueError("candidate selection requires a provider-derived universe")
    fractions = (0.10, 0.50, 0.90)[:candidate_count]
    candidates = []
    for fraction in fractions:
        position = int((len(normalized) - 1) * fraction)
        candidates.append({"position": position, "fraction": fraction, "symbol": normalized[position]})
    return candidates


def _collection_key_names(payload: Mapping[str, Any]) -> list[str]:
    names: set[str] = set()
    for key in DETAILS_COLLECTION_KEYS:
        if key in payload:
            names.add(key)
            value = payload.get(key)
            if isinstance(value, Mapping):
                for nested_key in DETAILS_COLLECTION_KEYS:
                    if nested_key in value:
                        names.add(f"{key}.{nested_key}")
    return sorted(names)[:30]


def inspect_details_response(
    payload: Mapping[str, Any],
    *,
    requested_symbol: str,
    requested_market: str,
    page_index: Any,
    page_size: Any,
) -> dict[str, Any]:
    normalized_symbol = normalize_symbol(requested_symbol)
    normalized_market = normalize_exchange(requested_market)
    provider_failure = _failure_class(payload)
    top_keys = sorted(str(key) for key in payload)[:30]
    collection_keys = _collection_key_names(payload)
    rows = extract_provider_rows(payload)
    exact_symbol = 0
    mismatched_symbol = 0
    missing_symbol = 0
    exact_market = 0
    mismatched_market = 0
    missing_market = 0
    exact_rows: list[Mapping[str, Any]] = []
    row_shapes: list[dict[str, Any]] = []
    for row in rows:
        symbol = normalize_symbol(_pick(row, "symbol", "Symbol", "ticker", "SecurityCode", "StockSymbol", "StockCode"))
        market = normalize_exchange(_pick(row, "exchange", "Exchange", "market", "Market", "StockExchange", "ExchangeCode"))
        if symbol is None:
            missing_symbol += 1
        elif symbol == normalized_symbol:
            exact_symbol += 1
        else:
            mismatched_symbol += 1
        if market is None:
            missing_market += 1
        elif market == normalized_market:
            exact_market += 1
        else:
            mismatched_market += 1
        if symbol == normalized_symbol and market == normalized_market:
            exact_rows.append(row)
        if len(row_shapes) < 3:
            candidate_values = {
                str(key): _bounded_scalar(value)
                for key, value in row.items()
                if is_type_candidate_field(key) and _bounded_scalar(value) is not None
            }
            row_shapes.append(
                {
                    "raw_key_names": sorted(str(key) for key in row)[:30],
                    "normalized_symbol": symbol,
                    "normalized_market": market,
                    "candidate_type_field_names": sorted(candidate_values),
                    "candidate_type_values": candidate_values,
                }
            )
    inventory = inventory_type_fields(exact_rows)
    if provider_failure:
        no_row_state = "provider_failure"
        parser_state = "not_attempted"
    elif not collection_keys and not rows:
        no_row_state = "collection_not_found"
        parser_state = "bounded_collection_not_found"
    elif collection_keys and not rows:
        no_row_state = "collection_present_empty"
        parser_state = "ok"
    elif rows and missing_symbol == len(rows):
        no_row_state = "rows_present_but_not_normalized"
        parser_state = "rows_present_but_not_normalized"
    elif rows and not exact_symbol:
        no_row_state = "normalized_rows_but_no_exact_symbol"
        parser_state = "ok"
    elif exact_symbol and not exact_rows:
        no_row_state = "exact_symbol_but_wrong_or_missing_market"
        parser_state = "ok"
    elif exact_rows:
        no_row_state = "exact_symbol_and_market"
        parser_state = "ok"
    else:
        no_row_state = "provider_success_empty"
        parser_state = "ok"
    numeric_page_size = int(page_size) if str(page_size).isdigit() and int(page_size) > 0 else None
    rejection_reasons: list[str] = []
    if mismatched_symbol:
        rejection_reasons.append("normalized_symbol_mismatch")
    if missing_symbol:
        rejection_reasons.append("missing_symbol_field")
    if exact_symbol and mismatched_market:
        rejection_reasons.append("market_mismatch")
    if exact_symbol and missing_market:
        rejection_reasons.append("missing_market_field")
    if len(exact_rows) > 1:
        rejection_reasons.append("duplicate_conflicting_rows")
    return {
        "provider_status": str(payload.get("status") or "ok"),
        "failure_class": provider_failure,
        "provider_code": str(payload.get("code"))[:40] if payload.get("code") is not None else None,
        "top_level_key_names": top_keys,
        "candidate_collection_key_names": collection_keys,
        "raw_collection_count": len(rows),
        "normalized_row_count": len(rows) - missing_symbol,
        "exact_symbol_count": exact_symbol,
        "mismatched_symbol_count": mismatched_symbol,
        "missing_symbol_count": missing_symbol,
        "exact_market_count": exact_market,
        "mismatched_market_count": mismatched_market,
        "missing_market_count": missing_market,
        "exact_symbol_and_market_count": len(exact_rows),
        "page_index": page_index,
        "page_size": page_size,
        "possible_more_pages": bool(numeric_page_size and len(rows) >= numeric_page_size),
        "candidate_type_field_names": [field["field_name"] for field in inventory["candidate_fields"]],
        "candidate_type_fields": inventory["candidate_fields"],
        "row_shape_samples": row_shapes,
        "no_row_state": no_row_state,
        "parser_state": parser_state,
        "exact_match_rejection_reasons": rejection_reasons,
        "exact_rows": [dict(row) for row in exact_rows],
    }


def public_details_diagnostics(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "exact_rows"}


def decide_details_contract(evidence: Mapping[str, Any], *, defect_fixed: bool = False) -> dict[str, Any]:
    candidates = evidence.get("candidates") if isinstance(evidence.get("candidates"), list) else []
    if not candidates:
        code, reason = "F", "No live provider-derived candidate evidence was collected."
    elif any(candidate.get("failure_class") in {"network_error", "timeout", "auth_failed", "permission_denied"} for candidate in candidates):
        code, reason = "F", "Provider access failure prevented contract resolution."
    else:
        resolved = [candidate for candidate in candidates if int(candidate.get("exact_symbol_and_market_count") or 0) == 1]
        if len(resolved) == len(candidates):
            fields = [field for candidate in resolved for field in candidate.get("candidate_type_fields", []) if isinstance(field, Mapping)]
            statuses = {str(field.get("semantic_status")) for field in fields}
            if defect_fixed:
                code, reason = "D", "A direct request or parser defect was fixed and all bounded exact-row checks succeeded."
            elif not fields:
                code, reason = "B", "Exact SecuritiesDetails rows are reliable but expose no candidate type field."
            elif statuses == {"verified"}:
                code, reason = "A", "Exact SecuritiesDetails rows expose an explicit verified type field."
            else:
                code, reason = "C", "Exact rows contain type-like fields whose semantics are not verified."
        elif all(candidate.get("no_row_state") in {"collection_present_empty", "provider_success_empty", "collection_not_found"} for candidate in candidates):
            code, reason = "E", "All evidence-backed exact-symbol request shapes returned no usable row."
        else:
            code, reason = "F", "Mixed or incomplete row-shape evidence prevents a reliable contract conclusion."
    return {
        "code": code,
        "outcome": DETAILS_CONTRACT_OUTCOMES[code],
        "reason": reason,
        "production_gate_open": False,
        "hose_scope_status": "unavailable",
    }


def exact_hose_symbols(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    return sorted(
        {
            symbol
            for row in rows
            if normalize_exchange(_pick(row, "exchange", "Exchange", "market", "Market")) == "HOSE"
            if (symbol := normalize_symbol(_pick(row, "symbol", "Symbol", "ticker", "SecurityCode")))
        }
    )


def run_raw_securities_authority(fetcher: Any) -> tuple[dict[str, Any], list[str]]:
    started = perf_counter()
    payload = fetcher._request("Securities", params={"market": "HOSE", "pageIndex": 1, "pageSize": 1000})
    duration = perf_counter() - started
    if isinstance(payload, Mapping) and str(payload.get("status") or "").lower() == "unavailable":
        return (
            {
                "status": "unavailable",
                "failure_class": _failure_class(payload),
                "reason": _text(payload.get("reason")),
                "duration_seconds": round(duration, 6),
            },
            [],
        )
    rows = extract_provider_rows(payload)
    inventory = inventory_type_fields(rows)
    authority = classify_authority_rows(rows, inventory)
    symbols = exact_hose_symbols(rows)
    return (
        {
            "status": "measured",
            "provider_rows": len(rows),
            "normalized_hose_symbols": len(symbols),
            "duration_seconds": round(duration, 6),
            "field_inventory": inventory,
            **authority,
        },
        symbols,
    )


def run_details_stage(
    symbols: Sequence[str],
    fetch_detail: Callable[[str], Mapping[str, Any]],
    *,
    concurrency: int = 1,
    full_universe: bool = False,
    universe_size: Optional[int] = None,
) -> dict[str, Any]:
    if not 1 <= concurrency <= MAX_CONCURRENCY:
        raise ValueError(f"concurrency must be between 1 and {MAX_CONCURRENCY}")
    normalized_symbols = sorted(set(filter(None, (normalize_symbol(symbol) for symbol in symbols))))
    if len(normalized_symbols) != len(symbols):
        raise ValueError("details symbols must be normalized and unique")
    started = perf_counter()
    matched_rows: list[dict[str, Any]] = []
    metrics: Counter[str] = Counter()
    stopped_reason: Optional[str] = None

    def inspect_one(symbol: str) -> tuple[str, Mapping[str, Any], list[dict[str, Any]]]:
        payload = fetch_detail(symbol)
        return symbol, payload, extract_provider_rows(payload)

    for offset in range(0, len(normalized_symbols), concurrency):
        batch = normalized_symbols[offset : offset + concurrency]
        completed: list[tuple[str, Mapping[str, Any], list[dict[str, Any]]]] = []
        if concurrency == 1:
            completed.append(inspect_one(batch[0]))
        else:
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = {executor.submit(inspect_one, symbol): symbol for symbol in batch}
                for future in as_completed(futures):
                    try:
                        completed.append(future.result())
                    except Exception:
                        metrics["unhandled_failure_count"] += 1
        for symbol, payload, rows in completed:
            metrics["attempted_count"] += 1
            failure = _failure_class(payload)
            if failure:
                metrics[f"{failure}_count"] += 1
                if failure in {"rate_limited", "auth_failed", "permission_denied"}:
                    stopped_reason = failure
                continue
            exact = [
                row
                for row in rows
                if normalize_symbol(_pick(row, "symbol", "Symbol", "ticker", "SecurityCode")) == symbol
                and normalize_exchange(_pick(row, "exchange", "Exchange", "market", "Market")) == "HOSE"
            ]
            if len(exact) != 1:
                metrics["exact_symbol_mismatch_count"] += 1
                stopped_reason = "exact_symbol_mismatch"
                continue
            metrics["exact_match_count"] += 1
            matched_rows.append(exact[0])
        if stopped_reason:
            break

    duration = perf_counter() - started
    inventory = inventory_type_fields(matched_rows)
    authority = classify_authority_rows(matched_rows, inventory)
    attempted = metrics["attempted_count"]
    projected = duration * int(universe_size or len(normalized_symbols)) / attempted if attempted else None
    result = {
        **authority,
        "status": "measured",
        "requested_count": len(normalized_symbols),
        "attempted_count": attempted,
        "exact_match_count": metrics["exact_match_count"],
        "duration_seconds": round(duration, 6),
        "concurrency": concurrency,
        "full_universe": full_universe,
        "stopped_reason": stopped_reason,
        "rate_limit_count": metrics["rate_limited_count"],
        "timeout_count": metrics["timeout_count"],
        "network_error_count": metrics["network_error_count"],
        "auth_failure_count": metrics["auth_failed_count"],
        "entitlement_failure_count": metrics["permission_denied_count"],
        "unhandled_failure_count": metrics["unhandled_failure_count"],
        "exact_symbol_mismatch_count": metrics["exact_symbol_mismatch_count"],
        "candidate_field_count": inventory["candidate_field_count"],
        "field_inventory": inventory,
        "projected_full_universe_seconds": round(projected, 3) if projected is not None else None,
    }
    result["authority"] = bool(
        authority["authority"]
        and metrics["exact_match_count"] == len(normalized_symbols)
        and authority["classified_count"] == len(normalized_symbols)
    )
    if attempted:
        result["classification_coverage_ratio"] = authority["classified_count"] / attempted
    return result


def should_escalate_type_stage(result: Mapping[str, Any]) -> bool:
    return bool(
        int(result.get("attempted_count") or 0)
        and int(result.get("attempted_count") or 0) == int(result.get("exact_match_count") or 0)
        and int(result.get("attempted_count") or 0) == int(result.get("classified_count") or 0)
        and int(result.get("unknown_count") or 0) == 0
        and int(result.get("conflicting_count") or 0) == 0
        and int(result.get("rate_limit_count") or 0) == 0
        and int(result.get("timeout_count") or 0) == 0
        and int(result.get("auth_failure_count") or 0) == 0
        and int(result.get("entitlement_failure_count") or 0) == 0
        and int(result.get("unhandled_failure_count") or 0) == 0
        and float(result.get("projected_full_universe_seconds") or 0.0) <= MATERIALIZATION_SECONDS
    )


def run_live_details_contract(fetcher: Any, candidate_count: int) -> dict[str, Any]:
    securities, symbols = run_raw_securities_authority(fetcher)
    if securities.get("status") != "measured" or not symbols:
        return {"securities": securities, "candidates": [], "status": "unavailable"}
    selected = details_contract_candidates(symbols, candidate_count)
    candidate_results: list[dict[str, Any]] = []
    alternative_attempt_count = 0
    for candidate in selected:
        symbol = candidate["symbol"]
        primary_params = {"market": "HOSE", "symbol": symbol, "pageIndex": 1, "pageSize": 1000}
        primary_payload = fetcher._request("SecuritiesDetails", params=primary_params)
        primary = inspect_details_response(
            primary_payload,
            requested_symbol=symbol,
            requested_market="HOSE",
            page_index=1,
            page_size=1000,
        )
        chosen = primary
        alternative: Optional[dict[str, Any]] = None
        access_failure = primary.get("failure_class") in {
            "rate_limited", "network_error", "timeout", "auth_failed", "permission_denied",
        }
        if int(primary.get("exact_symbol_and_market_count") or 0) == 0 and not access_failure:
            alternative_params = {"market": "HOSE", "symbol": symbol, "pageIndex": "", "pageSize": ""}
            alternative_payload = fetcher._request("SecuritiesDetails", params=alternative_params)
            alternative_attempt_count += 1
            alternative = inspect_details_response(
                alternative_payload,
                requested_symbol=symbol,
                requested_market="HOSE",
                page_index="",
                page_size="",
            )
            if int(alternative.get("exact_symbol_and_market_count") or 0) == 1:
                chosen = alternative
        result = {
            **candidate,
            **public_details_diagnostics(chosen),
            "resolved_shape": "official_empty_page_defaults" if chosen is alternative else "repository_explicit_page_defaults",
            "primary": public_details_diagnostics(primary),
            "alternative": public_details_diagnostics(alternative) if alternative else None,
        }
        candidate_results.append(result)
        if access_failure or (alternative and alternative.get("failure_class") in {"rate_limited", "network_error", "timeout", "auth_failed", "permission_denied"}):
            break
    return {
        "status": "measured",
        "securities": securities,
        "universe_count": len(symbols),
        "candidate_count": len(selected),
        "candidate_positions": [{key: value for key, value in candidate.items() if key != "symbol"} for candidate in selected],
        "candidate_symbols": [candidate["symbol"] for candidate in selected],
        "primary_request_shape": {
            "endpoint": "/Market/SecuritiesDetails",
            "query_key_names": ["market", "symbol", "pageIndex", "pageSize"],
            "market": "HOSE",
            "page_index": 1,
            "page_size": 1000,
            "evidence": "Current repository get_securities_details request construction.",
        },
        "alternative_request_shape": {
            "endpoint": "/Market/SecuritiesDetails",
            "query_key_names": ["market", "symbol", "pageIndex", "pageSize"],
            "market": "HOSE",
            "page_index": "",
            "page_size": "",
            "evidence": "Official installed securities_details dataclass defaults serialized by dataclasses.asdict.",
        },
        "primary_attempt_count": len(candidate_results),
        "alternative_attempt_count": alternative_attempt_count,
        "candidates": candidate_results,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="config")
    parser.add_argument("--source", choices=TYPE_SOURCES, default="auto")
    parser.add_argument("--sample-size", type=int, choices=SAMPLE_SIZES)
    parser.add_argument("--candidate-count", type=int, choices=(1, 2, 3), default=3)
    parser.add_argument("--concurrency", type=int, choices=range(1, MAX_CONCURRENCY + 1), default=1)
    parser.add_argument("--history-sessions", type=int, choices=HISTORY_SESSIONS, default=1)
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--allow-full-universe", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    live_modes = {"universe", "bulk", "sample"}
    if args.mode in live_modes and not args.allow_live:
        parser.error(f"--mode {args.mode} requires --allow-live")
    if args.mode == "sample" and args.sample_size is None:
        parser.error("--mode sample requires --sample-size")
    if args.allow_full_universe and not args.allow_live:
        parser.error("--allow-full-universe requires --allow-live")
    if args.allow_full_universe and args.mode != "security-type":
        parser.error("--allow-full-universe is available only in security-type mode")
    if args.mode == "security-type" and args.source != "auto" and not args.allow_live:
        parser.error("explicit security-type sources require --allow-live")
    if args.output:
        root = (Path.cwd() / ".tmp").resolve()
        output = args.output.resolve()
        if root not in output.parents:
            parser.error("--output must be inside the repository .tmp directory")


def execute(args: argparse.Namespace) -> dict[str, Any]:
    # Match normal repository startup semantics without reading or printing values.
    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from src.config import setup_env
    setup_env()
    result = config_result(args.mode)
    result["guardrails"] = {
        "live_explicit": args.allow_live,
        "full_universe_explicit": args.allow_full_universe,
        "concurrency": args.concurrency,
        "provider_concurrency_implementation": "bounded_threads" if args.mode == "security-type" and args.concurrency > 1 else "sequential",
    }
    if args.mode == "details-contract":
        result["phase"] = "4.12F-A2"
        details_model = result["package_capability"].get("securities_details_fields", [])
        result["details_contract"] = {
            "request_class": "ssi_fc_data.model.model.securities_details",
            "request_model_fields": details_model,
            "field_aliases": {},
            "serializer": "dataclasses.asdict; default and empty values are included",
            "official_defaults": {"market": "", "symbol": "", "pageIndex": "", "pageSize": ""},
            "endpoint": "/Market/SecuritiesDetails",
            "candidate_fractions": [0.10, 0.50, 0.90][: args.candidate_count],
            "candidate_count": args.candidate_count,
            "maximum_details_request_sequences": args.candidate_count * 2,
            "daily_stock_price_requests": 0,
        }
        if not args.allow_live:
            result["decision"] = decide_details_contract({})
            return result
        fetcher = _load_live_fetcher()
        live_counters = install_live_counters(fetcher)
        contract = run_live_details_contract(fetcher, args.candidate_count)
        result["network_used"] = True
        result["details_contract"].update(contract)
        result["live_metrics"] = {
            "provider_call_count": live_counters["provider_calls"],
            "token_call_count": live_counters["token_http_calls"],
            "rate_limit_count": live_counters["rate_limited"],
            "timeout_count": live_counters["timeout"],
            "network_error_count": live_counters["network_error"],
            "auth_failure_count": live_counters["auth_failed"],
            "entitlement_failure_count": live_counters["permission_denied"],
        }
        result["decision"] = decide_details_contract(contract)
        return result
    if args.mode == "security-type":
        result["phase"] = "4.12F-A1"
        result["security_type_source"] = args.source
        result["planned_work"] = {
            "securities_requests": 1 if args.allow_live else 0,
            "details_requests": ("full_universe" if args.allow_full_universe else int(args.sample_size or 10)) if args.allow_live and args.source in {"auto", "details"} else 0,
            "daily_stock_price_requests": 0,
        }
        if not args.allow_live:
            result["decision"] = decide_type_authority({})
            return result
        fetcher = _load_live_fetcher()
        live_counters = install_live_counters(fetcher)
        securities, symbols = run_raw_securities_authority(fetcher)
        result["network_used"] = True
        result["securities"] = securities
        if securities.get("authority") is not True and args.source in {"auto", "details"} and symbols:
            if args.allow_full_universe:
                selected = symbols
            else:
                selected = select_even_sample(symbols, int(args.sample_size or 10))

            def fetch_detail(symbol: str) -> Mapping[str, Any]:
                return fetcher._request(
                    "SecuritiesDetails",
                    params={"market": "HOSE", "symbol": symbol, "pageIndex": 1, "pageSize": 1000},
                )

            result["details"] = run_details_stage(
                selected,
                fetch_detail,
                concurrency=args.concurrency,
                full_universe=args.allow_full_universe,
                universe_size=len(symbols),
            )
        result["live_metrics"] = {
            "provider_call_count": live_counters["provider_calls"],
            "token_call_count": live_counters["token_http_calls"],
            "rate_limit_count": live_counters["rate_limited"],
            "timeout_count": live_counters["timeout"],
            "network_error_count": live_counters["network_error"],
            "auth_failure_count": live_counters["auth_failed"],
            "entitlement_failure_count": live_counters["permission_denied"],
        }
        result["decision"] = decide_type_authority(result)
        return result
    if args.mode == "config":
        result["decision"] = decide({})
        return result
    if args.mode == "bulk":
        result["network_used"] = False
        result["bulk_capability"] = {
            "state": "unsupported",
            "live_attempted": False,
            "live_attempt_count": 0,
            "safe_to_use": False,
            "reason": result["package_capability"].get("evidence"),
        }
        result["decision"] = decide(result)
        return result
    if args.mode == "decision":
        result["decision"] = decide(result)
        return result

    fetcher = _load_live_fetcher()
    live_counters = install_live_counters(fetcher)
    universe = run_live_universe(fetcher)
    result["network_used"] = True
    result["universe"] = universe
    result["live_metrics"] = {
        "provider_call_count": live_counters["provider_calls"],
        "token_call_count": live_counters["token_http_calls"],
        "rate_limit_count": live_counters["rate_limited"],
        "timeout_count": live_counters["timeout"],
        "network_error_count": live_counters["network_error"],
        "auth_or_entitlement_count": live_counters["auth_failed"] + live_counters["permission_denied"],
    }
    if args.mode == "universe" or not universe.get("authority"):
        result["decision"] = decide(result)
        return result

    symbols = select_even_sample(universe["eligible_symbols"], args.sample_size)
    today = date.today()
    lookback_days = max(14, args.history_sessions * 3)
    from_date = (today - timedelta(days=lookback_days)).isoformat()
    to_date = today.isoformat()

    def fetch(symbol: str, sessions: int) -> Mapping[str, Any]:
        return fetcher.get_daily_stock_price(symbol=symbol, market="HOSE", from_date=from_date, to_date=to_date, limit=sessions)

    sample = measure_symbol_sample(symbols, args.history_sessions, fetch)
    sample["provider_call_count"] = live_counters["provider_calls"]
    sample["token_call_count"] = live_counters["token_http_calls"]
    sample["token_call_count_status"] = "measured"
    sample["rate_limit_count"] = live_counters["rate_limited"]
    sample["symbols"] = symbols[:5]
    result["sample_results"] = [sample]
    result["projected_full_universe"] = project_full_universe(sample, len(universe["eligible_symbols"]))
    result["full_universe_result"] = {"status": "not_run", "reason": "Full universe requires a separately safe escalation and explicit flag."}
    result["decision"] = decide(result)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(parser, args)
    result = sanitize(execute(args))
    encoded = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if result.get("decision", {}).get("code") in OUTCOMES else 2


if __name__ == "__main__":
    raise SystemExit(main())
