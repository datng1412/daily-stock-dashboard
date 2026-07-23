"""Bounded, secret-safe SSI FastConnect V3 Market Data REST acceptance.

The default mode is a zero-network NOT_RUN report. Live work requires both
``--live`` and ``SSI_V3_LIVE_ACCEPTANCE_ENABLED=true``. Credentials are read
only through the repository configuration path and are never rendered.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from importlib import metadata as importlib_metadata
import json
import os
from pathlib import Path
import platform
import sys
from time import perf_counter
from typing import Any, Callable, Dict, Mapping, Optional, Sequence
from uuid import uuid4
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_provider.ssi_v3_adapter import (  # noqa: E402
    SsiFastConnectV3Adapter,
    SsiV3RestSettings,
)
from src.config import Config, get_config  # noqa: E402


LIVE_GUARD_ENV = "SSI_V3_LIVE_ACCEPTANCE_ENABLED"
LIVE_SYMBOL = "FPT"
LIVE_BOARD = "HOSE"
LIVE_WINDOW_DAYS = 14
LIVE_PAGE_SIZE = 20
LIVE_TIMEOUT_MAX_SECONDS = 10
VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
OUTCOMES = {
    "A": "REST_ACCESS_CONFIRMED",
    "B": "REST_ACCESS_PARTIAL",
    "C": "AUTHENTICATION_REJECTED",
    "D": "CLIENT_ID_OR_SDK_CONTRACT_BLOCKED",
    "E": "ENTITLEMENT_UNAVAILABLE",
    "F": "NETWORK_OR_PROVIDER_UNAVAILABLE",
    "G": "NOT_RUN",
}


AdapterFactory = Callable[[SsiV3RestSettings], SsiFastConnectV3Adapter]


def _env_enabled(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _text(value: Any) -> Optional[str]:
    normalized = str(value or "").strip()
    return normalized or None


def _http_status(result: Mapping[str, Any]) -> Optional[int]:
    value = (result.get("diagnostics") or {}).get("http_status")
    return value if isinstance(value, int) else None


def _exception_class(result: Mapping[str, Any]) -> Optional[str]:
    value = (result.get("diagnostics") or {}).get("exception_class")
    if not isinstance(value, str):
        return None
    # Exception class names are safe; arbitrary provider text is never copied.
    return value if value.replace("_", "").isalnum() else None


def _base_report(*, requested_live: bool, config: Any, environment: Mapping[str, str]) -> Dict[str, Any]:
    client_id_supplied = bool(_text(getattr(config, "ssi_v3_client_id", None)))
    guards = {
        "cli_live": requested_live,
        "environment_live_acceptance": _env_enabled(environment.get(LIVE_GUARD_ENV)),
        "v3_rest_enabled": bool(getattr(config, "ssi_v3_rest_enabled", False)),
        "api_key_present": bool(_text(getattr(config, "ssi_v3_api_key", None))),
        "api_secret_present": bool(_text(getattr(config, "ssi_v3_api_secret", None))),
    }
    guards["all_satisfied"] = all(guards.values())
    return {
        "acceptance_id": str(uuid4()),
        "started_at": datetime.now(VN_TIMEZONE).isoformat(),
        "completed_at": None,
        "sdk_version": importlib_metadata.version("ssi-sdk"),
        "python_version": platform.python_version(),
        "outcome": "G",
        "outcome_label": OUTCOMES["G"],
        "mode": "live" if requested_live else "default",
        "guards": guards,
        "client_id_supplied": client_id_supplied,
        "client_id_effective": "non_empty" if client_id_supplied else "empty",
        "authentication": {
            "attempted": False,
            "status": "not_run",
            "latency_ms": None,
            "failure_class": None,
            "http_status": None,
            "exception_class": None,
            "safe_error_class": None,
        },
        "operations": [],
        "totals": {
            "authentication_count": 0,
            "data_operation_count": 0,
            "successful_data_operations": 0,
        },
        "lifecycle_close_status": "not_created",
        "constraints": {
            "v2_calls": 0,
            "fallback_used": False,
            "otp_supplied": False,
            "private_key_supplied": False,
            "private_key_used": False,
            "token_persisted": False,
            "raw_payload_persisted": False,
            "raw_payload_emitted": False,
        },
    }


def _field_presence(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> Dict[str, bool]:
    return {field: any(field in row for row in rows) for field in fields}


def _date_bounds(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Optional[str]]:
    values = sorted(
        value
        for row in rows
        for value in [row.get("date")]
        if isinstance(value, str) and value
    )
    return {
        "minimum": values[0] if values else None,
        "maximum": values[-1] if values else None,
    }


def _foreign_field_counts(rows: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    fields = (
        "foreign_buy_volume",
        "foreign_sell_volume",
        "foreign_buy_value",
        "foreign_sell_value",
    )
    counts = {
        f"{field}_present_rows": sum(row.get(field) is not None for row in rows)
        for field in fields
    }
    counts.update(
        {
            "gross_fields_present": sum(
                any(field in row for row in rows) for field in fields
            ),
            "rows_with_non_null_volume": sum(
                row.get("foreign_buy_volume") is not None
                and row.get("foreign_sell_volume") is not None
                for row in rows
            ),
            "rows_with_non_null_value": sum(
                row.get("foreign_buy_value") is not None
                and row.get("foreign_sell_value") is not None
                for row in rows
            ),
            "rows_with_explicit_zero": sum(
                any(row.get(field) == 0 for field in fields) for row in rows
            ),
            "rows_with_missing_values": sum(
                any(row.get(field) is None for field in fields) for row in rows
            ),
            "rows_with_non_zero": sum(
                any(
                    isinstance(row.get(field), (int, float))
                    and row.get(field) != 0
                    for field in fields
                )
                for row in rows
            ),
            "complete_gross_volume_pair_rows": sum(
                row.get("foreign_buy_volume") is not None
                and row.get("foreign_sell_volume") is not None
                for row in rows
            ),
            "complete_gross_value_pair_rows": sum(
                row.get("foreign_buy_value") is not None
                and row.get("foreign_sell_value") is not None
                for row in rows
            ),
            "derived_net_volume_rows": sum(
                row.get("_foreign_net_volume_source") == "derived" for row in rows
            ),
            "derived_net_value_rows": sum(
                row.get("_foreign_net_value_source") == "derived" for row in rows
            ),
            "net_derivation_success_count": sum(
                row.get("_foreign_net_volume_source") == "derived"
                and row.get("_foreign_net_value_source") == "derived"
                for row in rows
            ),
        }
    )
    return counts


def _operation_report(
    name: str,
    result: Mapping[str, Any],
    latency_ms: float,
    *,
    expected_fields: Sequence[str],
    include_dates: bool = False,
    include_foreign_counts: bool = False,
) -> Dict[str, Any]:
    raw_rows = result.get("rows")
    rows = [row for row in raw_rows if isinstance(row, Mapping)] if isinstance(raw_rows, list) else []
    presence = _field_presence(rows, expected_fields)
    status = str(result.get("status") or "unavailable")
    structure_status = (
        "validated"
        if status == "ok" and rows and all(presence.values())
        else "empty"
        if status == "ok" and not rows
        else "unexpected"
        if status == "ok"
        else "unavailable"
    )
    report: Dict[str, Any] = {
        "name": name,
        "status": status,
        "latency_ms": round(latency_ms, 2),
        "row_count": len(rows),
        "pages_used": result.get("pages_used") if isinstance(result.get("pages_used"), int) else None,
        "structure_status": structure_status,
        "expected_fields_present": presence,
        "failure_class": result.get("failure_class") if isinstance(result.get("failure_class"), str) else None,
        "http_status": _http_status(result),
        "exception_class": _exception_class(result),
        "safe_error_class": _exception_class(result),
    }
    if include_dates:
        bounds = _date_bounds(rows)
        report["date_bounds"] = bounds
        report["date_min"] = bounds["minimum"]
        report["date_max"] = bounds["maximum"]
    if include_foreign_counts:
        report["foreign_field_counts"] = _foreign_field_counts(rows)
    return report


def _classify_outcome(report: Mapping[str, Any]) -> str:
    authentication = report["authentication"]
    if authentication["status"] != "ok":
        failure_class = authentication.get("failure_class")
        if failure_class == "validation_error" and not report["client_id_supplied"]:
            return "D"
        if failure_class in {"network_error", "request_timeout", "provider_unavailable", "rate_limited"}:
            return "F"
        return "C"

    operations = report["operations"]
    if any(item.get("failure_class") == "entitlement_unavailable" for item in operations):
        return "E"
    unavailable_classes = {"network_error", "request_timeout", "provider_unavailable", "rate_limited"}
    if operations and all(item.get("failure_class") in unavailable_classes for item in operations):
        return "F"
    all_contracts_valid = bool(operations) and all(
        item.get("status") == "ok" and item.get("structure_status") == "validated"
        for item in operations
    )
    if all_contracts_valid and not report["client_id_supplied"]:
        return "A"
    return "B"


def run_acceptance(
    *,
    config: Any,
    requested_live: bool,
    environment: Optional[Mapping[str, str]] = None,
    adapter_factory: AdapterFactory = SsiFastConnectV3Adapter,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Run at most one auth lifecycle and four bounded data operations."""

    env = os.environ if environment is None else environment
    report = _base_report(requested_live=requested_live, config=config, environment=env)
    if not report["guards"]["all_satisfied"]:
        report["completed_at"] = datetime.now(VN_TIMEZONE).isoformat()
        return report

    settings = SsiV3RestSettings(
        enabled=True,
        client_id=_text(getattr(config, "ssi_v3_client_id", None)),
        api_key=_text(getattr(config, "ssi_v3_api_key", None)),
        api_secret=_text(getattr(config, "ssi_v3_api_secret", None)),
        api_url=_text(getattr(config, "ssi_v3_api_url", None)) or "https://api.ssi.com.vn/api/v3",
        request_timeout=min(
            max(int(getattr(config, "ssi_v3_request_timeout", LIVE_TIMEOUT_MAX_SECONDS)), 1),
            LIVE_TIMEOUT_MAX_SECONDS,
        ),
        max_retries=0,
        retry_delay=float(getattr(config, "ssi_v3_retry_delay", 1.0)),
        rate_limit_per_second=int(getattr(config, "ssi_v3_rate_limit_per_second", 5)),
    )

    adapter: Optional[SsiFastConnectV3Adapter] = None
    try:
        try:
            adapter = adapter_factory(settings)
        except Exception as exc:
            report["authentication"].update(
                {
                    "status": "unavailable",
                    "failure_class": (
                        "validation_error" if isinstance(exc, ValueError) else "internal_error"
                    ),
                    "exception_class": type(exc).__name__,
                    "safe_error_class": type(exc).__name__,
                }
            )
            outcome = _classify_outcome(report)
            report["outcome"] = outcome
            report["outcome_label"] = OUTCOMES[outcome]
            return report
        report["lifecycle_close_status"] = "pending"
        report["totals"]["authentication_count"] = 1
        report["authentication"]["attempted"] = True
        started = perf_counter()
        authentication_result = adapter.initialize_rest_access()
        report["authentication"].update(
            {
                "status": authentication_result.get("status", "unavailable"),
                "latency_ms": round((perf_counter() - started) * 1000, 2),
                "failure_class": authentication_result.get("failure_class"),
                "http_status": _http_status(authentication_result),
                "exception_class": _exception_class(authentication_result),
                "safe_error_class": _exception_class(authentication_result),
            }
        )
        if authentication_result.get("status") != "ok":
            outcome = _classify_outcome(report)
            report["outcome"] = outcome
            report["outcome_label"] = OUTCOMES[outcome]
            return report

        vietnam_today = today or datetime.now(VN_TIMEZONE).date()
        end_day = vietnam_today - timedelta(days=1)
        start_day = end_day - timedelta(days=LIVE_WINDOW_DAYS)
        report["requested_window"] = {
            "from": start_day.isoformat(),
            "to": end_day.isoformat(),
            "calendar_days": LIVE_WINDOW_DAYS,
        }
        operations = (
            (
                "securities_fpt",
                lambda: adapter.get_security_basic_info(LIVE_SYMBOL),
                ("symbol", "exchange"),
                False,
                False,
            ),
            (
                "daily_ohlc_fpt",
                lambda: adapter.get_daily_ohlcv(
                    LIVE_SYMBOL,
                    from_date=start_day.isoformat(),
                    to_date=end_day.isoformat(),
                    limit=LIVE_PAGE_SIZE,
                ),
                ("date", "open", "high", "low", "close", "volume"),
                True,
                False,
            ),
            (
                "securities_summary_fpt",
                lambda: adapter.get_securities_summary(
                    symbol=LIVE_SYMBOL,
                    from_date=start_day.isoformat(),
                    to_date=end_day.isoformat(),
                    page_index=1,
                    page_size=LIVE_PAGE_SIZE,
                    limit=LIVE_PAGE_SIZE,
                ),
                (
                    "symbol",
                    "date",
                    "foreign_buy_volume",
                    "foreign_sell_volume",
                    "foreign_buy_value",
                    "foreign_sell_value",
                ),
                True,
                True,
            ),
            (
                "index_list_hose",
                lambda: adapter.get_index_list(LIVE_BOARD),
                ("index_code", "exchange"),
                False,
                False,
            ),
        )
        for name, operation, expected_fields, include_dates, include_foreign in operations:
            started = perf_counter()
            result = operation()
            report["operations"].append(
                _operation_report(
                    name,
                    result,
                    (perf_counter() - started) * 1000,
                    expected_fields=expected_fields,
                    include_dates=include_dates,
                    include_foreign_counts=include_foreign,
                )
            )
            report["totals"]["data_operation_count"] += 1

        report["totals"]["successful_data_operations"] = sum(
            item["status"] == "ok" for item in report["operations"]
        )
        outcome = _classify_outcome(report)
        report["outcome"] = outcome
        report["outcome_label"] = OUTCOMES[outcome]
        return report
    finally:
        if adapter is not None:
            try:
                adapter.close()
                report["lifecycle_close_status"] = "closed"
            except Exception:
                report["lifecycle_close_status"] = "close_failed"
                if report["outcome"] == "A":
                    report["outcome"] = "B"
                    report["outcome_label"] = OUTCOMES["B"]
        report["completed_at"] = datetime.now(VN_TIMEZONE).isoformat()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Request the bounded live acceptance; the environment guard is also required.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    Config.reset_instance()
    report = run_acceptance(
        config=get_config(),
        requested_live=args.live,
        environment=os.environ,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
