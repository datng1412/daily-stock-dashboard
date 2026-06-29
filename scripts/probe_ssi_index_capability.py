# -*- coding: utf-8 -*-
"""Bounded, secret-safe SSI index identifier and parameter discovery.

This developer-only script reads the existing SSI FastConnect environment
configuration through ``SsiFastConnectFetcher``. It prints only normalized,
whitelisted summaries; it never prints provider response bodies, credentials,
tokens, headers, account data, or provider messages.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from data_provider.ssi_fastconnect_fetcher import (  # noqa: E402
    SsiFastConnectFetcher,
    _classify_provider_failure,
    _extract_index_component_rows,
    _extract_rows,
    format_ssi_date,
)

INDEX_LIST_MARKETS: Tuple[Optional[str], ...] = (None, "HOSE", "HNX")
MAX_CANDIDATES = 10
MAX_DATE_WINDOWS = 2
MAX_MARKET_VARIANTS = 2
DEFAULT_DELAY_SECONDS = 1.15
SAFE_VALUE_RE = re.compile(r"[^A-Z0-9._-]+")
SENSITIVE_MARKERS = (
    "accesstoken",
    "access_token",
    "authorization",
    "bearer",
    "consumerid",
    "consumer_id",
    "consumersecret",
    "consumer_secret",
    "accountid",
    "account_id",
)


@dataclass(frozen=True)
class IndexCandidate:
    requested_label: str
    identifier_kind: str
    identifier_value: str
    parameter_key: str
    market: Optional[str]


@dataclass(frozen=True)
class ProbeSpec:
    endpoint: str
    candidate_label: Optional[str]
    identifier_kind: Optional[str]
    identifier_value: Optional[str]
    parameter_key: Optional[str]
    market: Optional[str]
    from_date: Optional[str]
    to_date: Optional[str]
    params: Dict[str, Any]


@dataclass(frozen=True)
class ProbeSummary:
    candidate_label: Optional[str]
    endpoint: str
    identifier_kind: Optional[str]
    identifier_value: Optional[str]
    parameter_key: Optional[str]
    market: Optional[str]
    from_date: Optional[str]
    to_date: Optional[str]
    classification: str
    count: int
    latest_date: Optional[str]
    failure_class: Optional[str]


@dataclass(frozen=True)
class IndexListRowSummary:
    requested_market: Optional[str]
    index_id: Optional[str]
    index_code: Optional[str]
    index_name: Optional[str]
    exchange: Optional[str]
    market: Optional[str]
    source: str


@dataclass(frozen=True)
class DiscoveryResult:
    index_list_rows: List[IndexListRowSummary]
    probes: List[ProbeSummary]


def _safe_value(value: Any, *, max_length: int = 48) -> Optional[str]:
    if value in (None, ""):
        return None
    cleaned = SAFE_VALUE_RE.sub("", str(value).strip().upper())
    return cleaned[:max_length] or None


def _safe_name(value: Any, *, max_length: int = 80) -> Optional[str]:
    if value in (None, ""):
        return None
    text = " ".join(str(value).split())
    if any(marker in text.lower() for marker in SENSITIVE_MARKERS):
        return "[redacted]"
    cleaned = "".join(
        character
        for character in text
        if character.isalnum() or character in " ._-/()"
    )
    return cleaned[:max_length] or None


def parse_requested_labels(value: str) -> List[str]:
    labels: List[str] = []
    for item in str(value or "").split(","):
        label = _safe_value(item)
        if label and label not in labels:
            labels.append(label)
    if not labels:
        raise ValueError("At least one index label is required")
    return labels


def _row_market(row: Dict[str, Any]) -> Optional[str]:
    return _safe_value(row.get("market") or row.get("exchange"))


def build_index_candidates(
    index_rows: Iterable[Dict[str, Any]],
    requested_labels: Sequence[str],
    *,
    max_candidates: int = MAX_CANDIDATES,
) -> List[IndexCandidate]:
    """Build exact, provider-derived identifier hypotheses without guessing."""
    safe_limit = max(0, min(int(max_candidates), MAX_CANDIDATES))
    rows = list(index_rows)
    requested = {_safe_value(label) for label in requested_labels}
    requested.discard(None)
    candidates: List[IndexCandidate] = []
    seen = set()

    for requested_label in requested_labels:
        safe_label = _safe_value(requested_label)
        if not safe_label or safe_label not in requested:
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            index_id = _safe_value(row.get("index_id"))
            index_code = _safe_value(row.get("index_code"))
            index_name = _safe_name(row.get("index_name"))
            searchable = {
                re.sub(r"[^A-Z0-9]", "", str(value).upper())
                for value in (index_id, index_code, index_name)
                if value
            }
            exact = safe_label in {index_id, index_code}
            normalized_label = re.sub(r"[^A-Z0-9]", "", safe_label)
            name_or_code_match = (
                normalized_label == "VN30"
                and any("VN30" in value for value in searchable)
            ) or (
                normalized_label == "VNINDEX"
                and any(
                    marker in value
                    for value in searchable
                    for marker in ("VNINDEX", "HOSEINDEX")
                )
            )
            if not exact and not name_or_code_match:
                continue
            for kind, value, parameter_key in (
                ("index_id", index_id, "indexID"),
                ("index_code", index_code, "indexCode"),
            ):
                if not value:
                    continue
                key = (safe_label, kind, value)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    IndexCandidate(
                        requested_label=safe_label,
                        identifier_kind=kind,
                        identifier_value=value,
                        parameter_key=parameter_key,
                        market=_row_market(row),
                    )
                )
                if len(candidates) >= safe_limit:
                    return candidates
    return candidates


def build_date_windows(
    *,
    today: date,
    day_counts: Sequence[int],
) -> List[Tuple[str, str]]:
    windows: List[Tuple[str, str]] = []
    for raw_days in day_counts[:MAX_DATE_WINDOWS]:
        days = max(1, min(int(raw_days), 29))
        from_date = format_ssi_date(today - timedelta(days=days - 1))
        to_date = format_ssi_date(today)
        if from_date and to_date and (from_date, to_date) not in windows:
            windows.append((from_date, to_date))
    return windows


def build_market_variants(
    candidate: IndexCandidate,
    *,
    fallback_market: Optional[str],
) -> List[Optional[str]]:
    markets: List[Optional[str]] = [None]
    provider_market = _safe_value(candidate.market) or _safe_value(fallback_market)
    if provider_market:
        markets.append(provider_market)
    return markets[:MAX_MARKET_VARIANTS]


def _normalize_rows(fetcher: SsiFastConnectFetcher, spec: ProbeSpec, payload: Any) -> List[Dict[str, Any]]:
    raw_rows = _extract_rows(payload)
    if spec.endpoint == "IndexList":
        rows = [
            fetcher._map_index_info(row)
            for row in raw_rows
            if any(
                re.sub(r"[^a-z0-9]", "", str(key).lower())
                in {"indexid", "indexcode", "indexname", "name"}
                for key in row
            )
        ]
        return [row for row in rows if row.get("index_id") or row.get("index_code")]
    if spec.endpoint == "DailyIndex":
        rows = [fetcher._map_daily_index(row, spec.identifier_value or "") for row in raw_rows]
        return [
            row
            for row in rows
            if any(
                row.get(key) is not None
                for key in ("date", "index_value", "change", "change_pct", "total_volume", "total_value")
            )
        ]
    if spec.endpoint == "IndexComponents":
        rows = [
            fetcher._map_index_component(row, spec.identifier_value or "")
            for row in _extract_index_component_rows(payload, spec.identifier_value or "")
        ]
        return [row for row in rows if row.get("symbol")]
    return []


def _has_explicit_empty_rows(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    for key in ("data", "Data", "items", "Items", "rows", "Rows", "result", "Result"):
        if key not in payload:
            continue
        value = payload.get(key)
        if isinstance(value, list):
            return not value
        if isinstance(value, dict) and _has_explicit_empty_rows(value):
            return True
    for key in ("totalRecord", "TotalRecord", "totalRecords", "TotalRecords"):
        if key in payload:
            try:
                return int(payload.get(key)) == 0
            except (TypeError, ValueError):
                return False
    return False


def classify_probe(
    payload: Any,
    rows: Sequence[Dict[str, Any]],
    *,
    endpoint: str = "DailyIndex",
) -> Tuple[str, Optional[str]]:
    if isinstance(payload, dict) and payload.get("status") == "unavailable":
        failure_class = _safe_value(payload.get("failure_class"), max_length=32)
        if not failure_class:
            failure_class = _safe_value(
                _classify_provider_failure(
                    error_type=payload.get("error_type"),
                    http_status=payload.get("http_status"),
                    code=payload.get("code"),
                    reason=payload.get("reason"),
                ),
                max_length=32,
            )
        normalized_failure = (failure_class or "UNKNOWN").lower()
        classification_by_failure = {
            "permission_denied": "permission_denied",
            "bad_request_params": "bad_request_params",
            "parse_failed": "parse_failed",
            "network_error": "network_error",
            "timeout": "network_error",
            "rate_limited": "rate_limited",
            "unknown": "unknown_failure",
            "unknown_failure": "unknown_failure",
        }
        return classification_by_failure.get(normalized_failure, "unavailable"), normalized_failure
    if rows:
        return ("usable_components" if endpoint == "IndexComponents" else "usable_rows"), None
    if endpoint == "IndexComponents" and any(
        isinstance(row.get("IndexComponent"), list)
        or isinstance(row.get("IndexComponents"), list)
        for row in _extract_rows(payload)
    ):
        return "empty_response", None
    if _has_explicit_empty_rows(payload):
        return "empty_response", None
    if _extract_rows(payload):
        return "parse_failed", "parse_failed"
    return "empty_response", None


def summarize_probe(
    fetcher: SsiFastConnectFetcher,
    spec: ProbeSpec,
    payload: Any,
) -> ProbeSummary:
    rows = _normalize_rows(fetcher, spec, payload)
    classification, failure_class = classify_probe(payload, rows, endpoint=spec.endpoint)
    dates = [
        str(row.get("date"))
        for row in rows
        if isinstance(row, dict) and row.get("date") not in (None, "")
    ]
    return ProbeSummary(
        candidate_label=_safe_value(spec.candidate_label),
        endpoint=spec.endpoint,
        identifier_kind=spec.identifier_kind,
        identifier_value=_safe_value(spec.identifier_value),
        parameter_key=spec.parameter_key,
        market=_safe_value(spec.market),
        from_date=spec.from_date,
        to_date=spec.to_date,
        classification=classification,
        count=len(rows),
        latest_date=max(dates) if dates else None,
        failure_class=failure_class,
    )


def _index_list_specs() -> List[ProbeSpec]:
    return [
        ProbeSpec(
            endpoint="IndexList",
            candidate_label=None,
            identifier_kind=None,
            identifier_value=None,
            parameter_key=None,
            market=market,
            from_date=None,
            to_date=None,
            params={"market": market} if market else {},
        )
        for market in INDEX_LIST_MARKETS
    ]


def _daily_index_specs(
    candidates: Sequence[IndexCandidate],
    windows: Sequence[Tuple[str, str]],
) -> List[ProbeSpec]:
    specs: List[ProbeSpec] = []
    for candidate in candidates[:MAX_CANDIDATES]:
        for from_date, to_date in windows[:MAX_DATE_WINDOWS]:
            specs.append(
                ProbeSpec(
                    endpoint="DailyIndex",
                    candidate_label=candidate.requested_label,
                    identifier_kind=candidate.identifier_kind,
                    identifier_value=candidate.identifier_value,
                    parameter_key=candidate.parameter_key,
                    market=None,
                    from_date=from_date,
                    to_date=to_date,
                    params={
                        candidate.parameter_key: candidate.identifier_value,
                        "Fromdate": from_date,
                        "Todate": to_date,
                        "pageIndex": 1,
                        "pageSize": 1000,
                    },
                )
            )
    return specs


def _component_specs(
    candidates: Sequence[IndexCandidate],
    *,
    fallback_market: Optional[str],
) -> List[ProbeSpec]:
    specs: List[ProbeSpec] = []
    for candidate in candidates[:MAX_CANDIDATES]:
        for market in build_market_variants(candidate, fallback_market=fallback_market):
            params: Dict[str, Any] = {
                candidate.parameter_key: candidate.identifier_value,
                "pageIndex": 1,
                "pageSize": 1000,
            }
            if market:
                params["market"] = market
            specs.append(
                ProbeSpec(
                    endpoint="IndexComponents",
                    candidate_label=candidate.requested_label,
                    identifier_kind=candidate.identifier_kind,
                    identifier_value=candidate.identifier_value,
                    parameter_key=candidate.parameter_key,
                    market=market,
                    from_date=None,
                    to_date=None,
                    params=params,
                )
            )
    return specs


def run_discovery(
    fetcher: SsiFastConnectFetcher,
    *,
    requested_labels: Sequence[str],
    day_counts: Sequence[int],
    max_candidates: int,
    fallback_market: Optional[str],
    today: date,
    delay_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
) -> DiscoveryResult:
    summaries: List[ProbeSummary] = []
    discovered_rows: List[Dict[str, Any]] = []
    index_list_rows: List[IndexListRowSummary] = []
    seen_index_rows = set()

    def execute(spec: ProbeSpec) -> Any:
        payload = fetcher._request(spec.endpoint, params=spec.params)
        summaries.append(summarize_probe(fetcher, spec, payload))
        if delay_seconds > 0:
            sleep(delay_seconds)
        return payload

    for spec in _index_list_specs():
        payload = execute(spec)
        normalized_rows = _normalize_rows(fetcher, spec, payload)
        discovered_rows.extend(normalized_rows)
        for row in normalized_rows:
            summary = IndexListRowSummary(
                requested_market=_safe_value(spec.market),
                index_id=_safe_value(row.get("index_id")),
                index_code=_safe_value(row.get("index_code")),
                index_name=_safe_name(row.get("index_name")),
                exchange=_safe_value(row.get("exchange")),
                market=_safe_value(row.get("market")),
                source="SSI",
            )
            key = tuple(asdict(summary).values())
            if key not in seen_index_rows:
                seen_index_rows.add(key)
                index_list_rows.append(summary)

    candidates = build_index_candidates(
        discovered_rows,
        requested_labels,
        max_candidates=max_candidates,
    )
    windows = build_date_windows(today=today, day_counts=day_counts)
    for spec in _daily_index_specs(candidates, windows):
        execute(spec)
    for spec in _component_specs(candidates, fallback_market=fallback_market):
        execute(spec)
    return DiscoveryResult(index_list_rows=index_list_rows, probes=summaries)


def _print_table(result: DiscoveryResult) -> None:
    index_columns = (
        "requested_market",
        "index_id",
        "index_code",
        "index_name",
        "exchange",
        "market",
        "source",
    )
    print("[index_list_rows]")
    print("\t".join(index_columns))
    for summary in result.index_list_rows:
        record = asdict(summary)
        print("\t".join("" if record[column] is None else str(record[column]) for column in index_columns))
    print("[probes]")
    columns = (
        "candidate_label",
        "endpoint",
        "identifier_kind",
        "identifier_value",
        "parameter_key",
        "market",
        "from_date",
        "to_date",
        "classification",
        "count",
        "latest_date",
        "failure_class",
    )
    print("\t".join(columns))
    for summary in result.probes:
        record = asdict(summary)
        print("\t".join("" if record[column] is None else str(record[column]) for column in columns))


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Bounded, secret-safe SSI index capability probe")
    parser.add_argument(
        "--candidates",
        "--indices",
        dest="candidates",
        default="VN30,VNINDEX",
        help="Comma-separated IndexList-derived candidate labels",
    )
    parser.add_argument("--days", default="7,29", help="One or two recent window lengths, capped at 29 days")
    parser.add_argument("--max-candidates", type=int, default=MAX_CANDIDATES)
    parser.add_argument("--market", default="HOSE", help="Fallback component market when IndexList has none")
    parser.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument("--json", action="store_true", help="Print compact JSON instead of a TSV table")
    args = parser.parse_args(argv)

    try:
        requested_labels = parse_requested_labels(args.candidates)
        day_counts = [int(value.strip()) for value in str(args.days).split(",") if value.strip()]
    except ValueError as exc:
        parser.error(str(exc))
    if not day_counts:
        parser.error("At least one date-window length is required")

    fetcher = SsiFastConnectFetcher(
        cache_ttl_seconds=0,
        request_delay_seconds=0,
        index_request_delay_seconds=0,
    )
    result = run_discovery(
        fetcher,
        requested_labels=requested_labels,
        day_counts=day_counts,
        max_candidates=max(0, min(args.max_candidates, MAX_CANDIDATES)),
        fallback_market=args.market,
        today=date.today(),
        delay_seconds=max(0.0, args.delay_seconds),
    )
    if args.json:
        print(
            json.dumps(
                {
                    "index_list_rows": [asdict(summary) for summary in result.index_list_rows],
                    "probes": [asdict(summary) for summary in result.probes],
                },
                separators=(",", ":"),
            )
        )
    else:
        _print_table(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
