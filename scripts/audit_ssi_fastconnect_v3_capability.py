"""Secret-safe SSI FastConnect V3 capability and migration-gate audit.

This is an audit utility, not a runtime provider.  Importing it creates no
provider, sends no request, starts no thread, and writes no file.  The default
mode is configuration-only.  A caller must explicitly opt into the small,
one-shot live probe with ``--allow-live``.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, timedelta
from importlib import metadata as importlib_metadata
from importlib.util import find_spec
import json
import os
from pathlib import Path
import re
import sys
from time import perf_counter
from typing import Any, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SCRIPT_NAME = "audit_ssi_fastconnect_v3_capability"
DEFAULT_MODE = "config"
MODES = ("config", "sdk", "contracts", "live-smoke", "decision", "change-impact")

V2_DISTRIBUTION = "ssi-fc-data"
V2_MODULE = "ssi_fc_data"
V3_DISTRIBUTION = "ssi-sdk"
V3_MODULE = "ssi_sdk"
V3_API_BASE_URL = "https://api.ssi.com.vn"
V3_AUTH_URL = f"{V3_API_BASE_URL}/api/v3/auth/token"
V3_STREAM_PORTAL_URL = "wss://stream.ssi.com.vn"
V3_STREAM_SDK_URL = "wss://api.ssi.com.vn/ws/v3"
LIVE_TIMEOUT_SECONDS = 10
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024
MAX_REPORT_BYTES = 512 * 1024

OFFICIAL_SOURCES = {
    "developer_portal": "https://developers.ssi.com.vn/",
    "api_overview": "https://developers.ssi.com.vn/docs/api-reference",
    "auth_token": "https://developers.ssi.com.vn/docs/api-reference/auth-token",
    "securities_by_board": "https://developers.ssi.com.vn/docs/api-reference/data-securitiesByBoard",
    "securities_summary": "https://developers.ssi.com.vn/docs/api-reference/data-securitiesSummary",
    "ohlc": "https://developers.ssi.com.vn/docs/api-reference/data-ohlc",
    "market_file": "https://developers.ssi.com.vn/docs/api-reference/data-marketFile",
    "websocket": "https://developers.ssi.com.vn/docs/api-reference/connectWebSocket",
    "subscriptions": "https://developers.ssi.com.vn/docs/api-reference/subscribeUnsubscribeMarketData",
    "sdk_overview": "https://developers.ssi.com.vn/docs/sdk/overview",
    "python_sdk": "https://pypi.org/project/ssi-sdk/",
    "tutorials": "https://github.com/SSI-Securities-Inc/ssi-fastconnect-v3-tutorials",
}

# These names are deliberately audit-only.  They are not read by production
# configuration and adding them does not alter the V2 runtime.
V3_AUDIT_ENV_NAMES = {
    "api_key": "SSI_FASTCONNECT_V3_API_KEY",
    "api_secret": "SSI_FASTCONNECT_V3_API_SECRET",
    "audit_symbol": "SSI_FASTCONNECT_V3_AUDIT_SYMBOL",
    "audit_index": "SSI_FASTCONNECT_V3_AUDIT_INDEX",
}
V2_ENV_NAMES = (
    "SSI_FASTCONNECT_ENABLED",
    "SSI_FASTCONNECT_BASE_URL",
    "SSI_FASTCONNECT_CONSUMER_ID",
    "SSI_FASTCONNECT_CONSUMER_SECRET",
)

SUB_GATES = (
    "official_sdk_package",
    "authentication",
    "api_base_url_and_versioning",
    "security_master",
    "exact_symbol_metadata",
    "instrument_type_authority",
    "hose_common_stock_authority",
    "daily_historical_price",
    "foreign_buy_sell_history",
    "broad_market_or_multi_symbol_history",
    "historical_file_zip_access",
    "index_list",
    "index_components",
    "realtime_quote",
    "index_market_stream",
    "websocket_model",
    "rate_limit_contract",
    "pagination_model",
    "side_by_side_operation",
    "migration_adapter_viability",
)
VALID_GATE_STATUSES = {
    "verified",
    "partial",
    "unavailable",
    "unsupported",
    "inconclusive",
    "not_tested",
}

SECRET_KEY_PATTERN = re.compile(
    r"(?:secret|token|authorization|cookie|private.?key|api.?key|account.?id)",
    re.IGNORECASE,
)
BEARER_PATTERN = re.compile(r"Bearer\s+[^\s,;]+", re.IGNORECASE)


def _distribution_version(name: str) -> Optional[str]:
    """Return an installed distribution version without importing its module."""
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None


def package_inventory() -> dict[str, dict[str, Any]]:
    """Return package metadata only; no package is imported or installed."""
    return {
        "v2": {
            "distribution": V2_DISTRIBUTION,
            "module": V2_MODULE,
            "installed_version": _distribution_version(V2_DISTRIBUTION),
            "module_discoverable": find_spec(V2_MODULE) is not None,
            "role": "current repository runtime dependency",
        },
        "v3": {
            "distribution": V3_DISTRIBUTION,
            "module": V3_MODULE,
            "installed_version": _distribution_version(V3_DISTRIBUTION),
            "module_discoverable": find_spec(V3_MODULE) is not None,
            "official_documented_version": "3.0.5",
            "official_python_requirement": ">=3.10",
            "role": "official candidate for an audit or future migration only",
        },
    }


def configuration_presence(environment: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    """Describe configured names without emitting their values."""
    env = os.environ if environment is None else environment
    v3 = {name: bool(env.get(variable)) for name, variable in V3_AUDIT_ENV_NAMES.items()}
    v2 = {variable: bool(env.get(variable)) for variable in V2_ENV_NAMES}
    existing_key_ready = bool(
        v2["SSI_FASTCONNECT_CONSUMER_ID"]
        and v2["SSI_FASTCONNECT_CONSUMER_SECRET"]
    )
    return {
        "v2_configured_name_presence": v2,
        "v3_audit_configured_name_presence": v3,
        "v3_live_minimum_present": bool(v3["api_key"] and v3["api_secret"] and v3["audit_symbol"]),
        "existing_key_v3_auth_mapping_present": existing_key_ready,
        "production_v3_configuration_support": "absent: current src/config.py and .env.example define V2 names only",
        "credential_values": "excluded",
    }


def cli_environment(
    base_environment: Optional[Mapping[str, str]] = None,
    dotenv_path: Path = Path(".env"),
    *,
    retain_values: bool = False,
) -> dict[str, str]:
    """Merge local dotenv names without ever rendering their values.

    This is intentionally called only from ``main``.  Importing or using the
    audit helpers does not read a dotenv file.  Values are retained in memory
    only for an explicitly authorized live probe; all report builders reduce
    them to booleans or fixed classification labels.
    """
    environment = dict(os.environ if base_environment is None else base_environment)
    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return environment
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, raw_value = stripped.split("=", 1)
        name = name.strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) and name not in environment:
            value = raw_value.strip().strip('"').strip("'")
            environment[name] = value if retain_values else ("configured" if value else "")
    return environment


def redact_text(value: Any, known_secrets: Optional[list[str]] = None) -> str:
    """Render diagnostics without credentials, headers, bodies, or long tokens."""
    text = str(value or "")
    for secret in known_secrets or []:
        if secret:
            text = text.replace(secret, "[redacted]")
    text = BEARER_PATTERN.sub("Bearer [redacted]", text)
    text = re.sub(r"(?i)(authorization|cookie)\s*[:=]\s*[^\r\n]+", r"\1: [redacted]", text)
    text = re.sub(
        r"(?i)(api[_-]?key|api[_-]?secret|consumer[_-]?secret|access[_-]?token|refresh[_-]?token|private[_-]?key|account[_-]?id)\s*[:=]\s*[^,\s}\]]+",
        r"\1=[redacted]",
        text,
    )
    return text


def sanitize_value(value: Any, known_secrets: Optional[list[str]] = None) -> Any:
    """Remove sensitive keys and raw response bodies from a report value."""
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if key_text in {"raw", "body", "response"}:
                result[key_text] = "[redacted]"
            elif SECRET_KEY_PATTERN.search(key_text):
                # Presence booleans and static documentation labels are safe;
                # values under sensitive names are not.
                if (
                    isinstance(child, bool)
                    or key_text in {"credential_values", "response_tokens"}
                    or (isinstance(child, str) and child.startswith(("https://", "wss://")))
                ):
                    result[key_text] = sanitize_value(child, known_secrets)
                else:
                    result[key_text] = "[redacted]"
            else:
                result[key_text] = sanitize_value(child, known_secrets)
        return result
    if isinstance(value, list):
        return [sanitize_value(item, known_secrets) for item in value]
    if isinstance(value, tuple):
        return [sanitize_value(item, known_secrets) for item in value]
    if isinstance(value, str):
        return redact_text(value, known_secrets)
    return value


def documented_contracts() -> dict[str, Any]:
    """Return only official-documentation findings; it performs no live work."""
    return {
        "evidence_level": "documented",
        "v2_to_v3": {
            "Securities": {
                "v3_contract": "GET /api/v3/data/securitiesByBoard using exactly one symbol, board, or index query",
                "parity": "partial",
                "reason": "V3 provides identity/board rows, but its documented row does not establish an instrument-type authority.",
            },
            "SecuritiesDetails": {
                "v3_contract": "No direct documented field-level equivalent identified; securitiesByBoard has limited descriptive fields.",
                "parity": "partial",
                "reason": "Exact-symbol identity is documented; complete V2 metadata parity is not documented.",
            },
            "DailyStockPrice": {
                "v3_contract": "GET /api/v3/data/securitiesSummary with symbol/index plus dates and page controls",
                "parity": "transformed_partial",
                "reason": "Documented foreign buy/sell totals and value totals exist, but units, finality, direct-net semantics, and exact V2 field parity need live proof.",
            },
            "DailyOhlc": {
                "v3_contract": "GET /api/v3/data/ohlc with symbol, dates, timeFrame, pageIndex, and pageSize",
                "parity": "transformed_partial",
                "reason": "OHLCV history is documented; date, price, and volume semantics require live normalization proof.",
            },
            "IndexList": {
                "v3_contract": "GET /api/v3/data/indexList",
                "parity": "partial",
                "reason": "Catalog endpoint is documented but no live identity proof was run.",
            },
            "IndexComponents": {
                "v3_contract": "securitiesByBoard?index=<index>",
                "parity": "transformed_partial",
                "reason": "Current component rows are documented; historical membership is not documented.",
            },
            "Realtime": {
                "v3_contract": "V3 WebSocket SUBSCRIBE/UNSUBSCRIBE messages with DATA/TRADING/HEARTBEAT channels and scoped topics",
                "parity": "partial",
                "reason": "Topic families are documented, but production semantics and endpoint consistency need live proof.",
            },
        },
        "auth": {
            "endpoint": V3_AUTH_URL,
            "request": "apiKey, apiSecret, optional otp",
            "market_data_without_otp": "documented",
            "response_tokens": "access/refresh token names documented; values must never be logged or persisted by this audit",
        },
        "pagination": {
            "securities_summary": "pageIndex is 1-based; response documents pageSize, pageIndex, pagesCount, itemsCount, and data",
            "ohlc": "pageIndex is 1-based; pageSize controls bounded history retrieval",
        },
        "rate_limits": {
            "headers": ["X-RATELIMIT-LIMIT", "X-RATELIMIT-REMAINING", "X-RATELIMIT-RESET"],
            "live_policy": "observe normal bounded responses only; never provoke 429",
        },
        "file_history": {
            "endpoint": "GET /api/v3/data/file",
            "documented_result": "temporary dataLink for CSV-style OHLCV fields",
            "zip_or_broad_market_proof": "not documented",
        },
        "websocket_endpoint_discrepancy": {
            "developer_portal": V3_STREAM_PORTAL_URL,
            "python_sdk_metadata": V3_STREAM_SDK_URL,
            "status": "inconclusive until a bounded authenticated live connection confirms the active endpoint",
        },
        "sources": deepcopy(OFFICIAL_SOURCES),
    }


def initial_sub_gates() -> dict[str, dict[str, str]]:
    """Return the conservative current decision sub-gates from documented evidence."""
    statuses = {
        "official_sdk_package": ("verified", "Official ssi-sdk package and ssi_sdk namespace are documented; not installed locally."),
        "authentication": ("not_tested", "No V3 credentials were used and no live auth request was sent."),
        "api_base_url_and_versioning": ("verified", "Official V3 REST base and /api/v3 paths are documented."),
        "security_master": ("partial", "securitiesByBoard is documented, but its full authority and pagination have not been live-proven."),
        "exact_symbol_metadata": ("partial", "Exact-symbol query is documented; V2 field-level parity is not."),
        "instrument_type_authority": ("inconclusive", "Documented V3 security rows do not expose an authoritative type field or code mapping."),
        "hose_common_stock_authority": ("inconclusive", "No live full-universe type evidence; V2 A2 remains deferred."),
        "daily_historical_price": ("partial", "V3 OHLC and securitiesSummary history are documented but not live-verified."),
        "foreign_buy_sell_history": ("partial", "Summary fields are documented; units, finality, and net semantics are unverified."),
        "broad_market_or_multi_symbol_history": ("unsupported", "Official documented history requests are symbol/index scoped; no broad or multi-symbol contract was identified."),
        "historical_file_zip_access": ("partial", "A symbol-required temporary CSV dataLink is documented; ZIP and broad-market capability are not."),
        "index_list": ("partial", "IndexList is documented but not live-verified."),
        "index_components": ("partial", "Index query through securitiesByBoard is documented; current versus historical membership remains unresolved."),
        "realtime_quote": ("partial", "Scoped quote/trade topics are documented but no V3 live message was retained."),
        "index_market_stream": ("partial", "Market topics are documented but no V3 live message was retained."),
        "websocket_model": ("partial", "Subscription model is documented; endpoint discrepancy and entitlement/OTP behavior remain unresolved."),
        "rate_limit_contract": ("verified", "Named rate-limit headers are documented; no live values were observed."),
        "pagination_model": ("verified", "1-based pagination is documented for history endpoints."),
        "side_by_side_operation": ("partial", "Separate V2/V3 credentials and no automatic fallback make shadow reads feasible after V3 access is enabled."),
        "migration_adapter_viability": ("inconclusive", "A/B is required before implementing a version-neutral adapter; live V3 access is absent."),
    }
    return {name: {"status": status, "reason": reason} for name, (status, reason) in statuses.items()}


def classify_instrument_type(value: Any, *, documented_mapping: Optional[Mapping[str, str]] = None) -> str:
    """Classify only explicit labels or an explicitly supplied official mapping.

    Numeric provider codes and unrecognised strings remain ``unknown``.  The
    function deliberately has no implicit SSI-specific code table.
    """
    if value is None or isinstance(value, bool):
        return "unknown"
    text = str(value).strip()
    if not text:
        return "unknown"
    if documented_mapping and text in documented_mapping:
        return str(documented_mapping[text])
    normalized = text.casefold().replace("-", " ").replace("_", " ")
    labels = {
        "common stock": "common_stock",
        "stock": "common_stock",
        "etf": "etf",
        "covered warrant": "covered_warrant",
        "fund": "fund",
        "bond": "bond",
        "preferred stock": "preferred_stock",
    }
    return labels.get(normalized, "unknown")


def assess_security_master_row(row: Mapping[str, Any], symbol: str, board: str) -> dict[str, Any]:
    """Require exact identity; do not infer common stock from a board alone."""
    exact_symbol = str(row.get("symbol") or "").strip().upper() == symbol.strip().upper()
    exact_board = str(row.get("board") or "").strip().upper() == board.strip().upper()
    raw_type_values = [
        row.get(key)
        for key in ("securityType", "instrumentType", "type", "security_type", "instrument_type")
        if row.get(key) is not None
    ]
    classifications = {classify_instrument_type(value) for value in raw_type_values}
    classifications.discard("unknown")
    type_status = "conflicting" if len(classifications) > 1 else next(iter(classifications), "unknown")
    return {
        "exact_symbol": exact_symbol,
        "exact_board": exact_board,
        "instrument_type": type_status,
        "hose_common_stock_authoritative": bool(exact_symbol and exact_board and type_status == "common_stock"),
    }


def normalize_foreign_history_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve V3 summary foreign fields without inventing units, finality, or net."""
    def numeric(name: str) -> Optional[float]:
        value = row.get(name)
        if value is None or isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    buy_volume = numeric("totalForeignBuy")
    sell_volume = numeric("totalForeignSell")
    buy_value = numeric("totalForeignBuyValue")
    sell_value = numeric("totalForeignSellValue")
    direct_net_volume = numeric("foreignNetVolume")
    direct_net_value = numeric("foreignNetValue")
    return {
        "date": row.get("tradingDate") or row.get("date"),
        "foreign_buy_volume": buy_volume,
        "foreign_sell_volume": sell_volume,
        "foreign_net_volume": direct_net_volume if direct_net_volume is not None else None,
        "foreign_buy_value": buy_value,
        "foreign_sell_value": sell_value,
        "foreign_net_value": direct_net_value if direct_net_value is not None else None,
        "net_source": "direct" if direct_net_volume is not None or direct_net_value is not None else "not_documented",
        "volume_unit": "unknown_pending_live_proof",
        "value_unit": "unknown_pending_live_proof",
        "finality": "unknown_pending_live_proof",
    }


def compare_one_symbol_parity(v2_row: Mapping[str, Any], v3_row: Mapping[str, Any]) -> dict[str, Any]:
    """Compare already-normalized bounded evidence without inferring units."""
    fields = (
        "foreign_buy_value",
        "foreign_sell_value",
        "foreign_buy_volume",
        "foreign_sell_volume",
    )
    comparisons = {
        field: {
            "v2": v2_row.get(field),
            "v3": v3_row.get(field),
            "equal": v2_row.get(field) == v3_row.get(field),
        }
        for field in fields
    }
    return {
        "same_symbol": str(v2_row.get("symbol") or "").upper() == str(v3_row.get("symbol") or "").upper(),
        "same_trading_date": v2_row.get("trading_date") == v3_row.get("trading_date"),
        "fields": comparisons,
        "missing_remains_null": all(
            item["v3"] is None for item in comparisons.values() if item["v2"] is None
        ),
        "explicit_zero_remains_zero": all(
            item["v3"] == 0 for item in comparisons.values() if item["v2"] == 0
        ),
        "unit_compatibility": "unverified_until_live_provider_evidence",
        "finality_compatibility": "unverified_until_completed_session_evidence",
        "scope": "one_symbol_field_level_only_not_market_coverage",
    }


def compare_index_components(v2_symbols: list[Any], v3_symbols: list[Any]) -> dict[str, Any]:
    """Compare normalized current-membership symbols without assuming dates."""
    normalize = lambda values: sorted({str(value).strip().upper() for value in values if str(value).strip()})
    v2 = normalize(v2_symbols)
    v3 = normalize(v3_symbols)
    return {
        "v2_count": len(v2),
        "v3_count": len(v3),
        "common_count": len(set(v2) & set(v3)),
        "missing_from_v3": sorted(set(v2) - set(v3)),
        "new_in_v3": sorted(set(v3) - set(v2)),
        "exact_symbol_set_match": v2 == v3,
        "weights": "unverified",
        "effective_or_current_date": "unverified",
    }


def extract_rate_limit_metadata(headers: Mapping[str, Any]) -> dict[str, Optional[str]]:
    """Extract named rate headers from a normal response without logging others."""
    lower = {str(key).lower(): str(value) for key, value in headers.items()}
    return {
        "limit": lower.get("x-ratelimit-limit"),
        "remaining": lower.get("x-ratelimit-remaining"),
        "reset": lower.get("x-ratelimit-reset"),
        "retry_after": lower.get("retry-after"),
    }


def live_smoke_plan(*, allow_websocket: bool, allow_small_download: bool) -> dict[str, Any]:
    """State the strict maximum work before a live probe is allowed."""
    return {
        "authentication_sequences_max": 1,
        "security_master_requests_max": 1,
        "historical_requests_max": 1,
        "index_component_requests_max": 1,
        "rate_limit_observations_max": 1,
        "websocket_connections_max": 1 if allow_websocket else 0,
        "websocket_subscriptions_max": 1 if allow_websocket else 0,
        "websocket_timeout_seconds_max": LIVE_TIMEOUT_SECONDS if allow_websocket else 0,
        "small_download_enabled": bool(allow_small_download),
        "small_download_bytes_max": MAX_DOWNLOAD_BYTES if allow_small_download else 0,
        "automatic_retries": 0,
        "full_market_subscription": "rejected",
        "stop_conditions": ["429", "auth_rejection", "entitlement_rejection", "timeout", "unexpected_pagination", "oversized_download"],
    }


def credential_mapping(environment: Optional[Mapping[str, str]] = None) -> list[dict[str, Any]]:
    """Map credential concepts without copying any credential value to output."""
    env = os.environ if environment is None else environment
    consumer_id_present = bool(env.get("SSI_FASTCONNECT_CONSUMER_ID"))
    consumer_secret_present = bool(env.get("SSI_FASTCONNECT_CONSUMER_SECRET"))
    return [
        {
            "concept": "application identifier / API key",
            "current_environment_name": "SSI_FASTCONNECT_CONSUMER_ID",
            "configured": consumer_id_present,
            "current_v2_meaning": "ConsumerID supplied to the V2 access-token request",
            "v3_sdk_meaning": "api_key candidate; the separately documented client_id mapping remains unresolved",
            "v3_raw_rest_meaning": "apiKey in POST /api/v3/auth/token",
            "same_value_reusable": "live_auth_result_required",
            "alias_or_config_change": "required_for_a_future_V3_adapter_only",
            "status": "reuse_with_name_mapping",
            "production_exposure_risk": "low_if_read_in_memory_and_never_logged",
        },
        {
            "concept": "API secret",
            "current_environment_name": "SSI_FASTCONNECT_CONSUMER_SECRET",
            "configured": consumer_secret_present,
            "current_v2_meaning": "ConsumerSecret supplied to the V2 access-token request",
            "v3_sdk_meaning": "api_secret",
            "v3_raw_rest_meaning": "apiSecret in POST /api/v3/auth/token",
            "same_value_reusable": "live_auth_result_required",
            "alias_or_config_change": "required_for_a_future_V3_adapter_only",
            "status": "reuse_with_name_mapping",
            "production_exposure_risk": "high_if_logged_or_persisted; prohibited by this audit",
        },
        {
            "concept": "SDK client identifier",
            "current_environment_name": None,
            "configured": False,
            "current_v2_meaning": "no separate current production concept",
            "v3_sdk_meaning": "client_id Config field",
            "v3_raw_rest_meaning": "not required by documented raw market-data auth request",
            "same_value_reusable": "unresolved",
            "alias_or_config_change": "unresolved_until_official_account_mapping_is_proven",
            "status": "unresolved",
            "production_exposure_risk": "do_not_guess_or_duplicate_an_existing_value",
        },
        {
            "concept": "private key",
            "current_environment_name": None,
            "configured": False,
            "current_v2_meaning": "not used by current market-data adapter",
            "v3_sdk_meaning": "documented SDK configuration for signed/trading flows",
            "v3_raw_rest_meaning": "not required by documented market-data token request",
            "same_value_reusable": "not_applicable",
            "alias_or_config_change": "none_for_raw_market_data_audit",
            "status": "V3_only",
            "production_exposure_risk": "never introduce for data-only migration without a contract need",
        },
        {
            "concept": "OTP / two-factor data",
            "current_environment_name": None,
            "configured": False,
            "current_v2_meaning": "not used by current market-data adapter",
            "v3_sdk_meaning": "required for Trading and documented SDK Stream use",
            "v3_raw_rest_meaning": "optional; omitted token is market-data-only",
            "same_value_reusable": "not_applicable",
            "alias_or_config_change": "none_for_REST_market_data",
            "status": "not_required_for_market_data",
            "production_exposure_risk": "do_not_request_or_store_in_this_audit",
        },
        {
            "concept": "V2 access token",
            "current_environment_name": None,
            "configured": False,
            "current_v2_meaning": "V2 access token is an in-memory runtime result",
            "v3_sdk_meaning": "not reusable",
            "v3_raw_rest_meaning": "not accepted as a credential input",
            "same_value_reusable": "no",
            "alias_or_config_change": "replace_runtime_lifecycle_only_after_cutover",
            "status": "V2_only",
            "production_exposure_risk": "never persist or reuse across API versions",
        },
        {
            "concept": "V3 access and refresh tokens",
            "current_environment_name": None,
            "configured": False,
            "current_v2_meaning": "no V2 equivalent value may be reused",
            "v3_sdk_meaning": "V3 Auth-managed runtime results",
            "v3_raw_rest_meaning": "tokenType, accessToken, refreshToken, and expiry fields",
            "same_value_reusable": "generated_by_V3_only",
            "alias_or_config_change": "new_token_lifecycle_required",
            "status": "V3_only",
            "production_exposure_risk": "token_values_must_remain_in_memory_only",
        },
    ]


def v2_capability_inventory() -> list[dict[str, Any]]:
    """Inventory production-relevant V2 calls from the current repository."""
    common = {
        "production_file": "data_provider/ssi_fastconnect_fetcher.py",
        "client": "ssi_fc_data.fc_data_client.MarketDataClient / fc_md_stream.MarketDataStream",
        "cache_behavior": "service/fetcher TTL caches; force_refresh is explicit",
        "single_flight_behavior": "existing request coalescing and rate-limit guardrails remain V2-owned",
        "error_classification": "provider errors are normalized as optional/non-fatal service diagnostics",
    }
    rows = [
        ("authentication", "get_access_token", "all V2 REST market-data calls", "AccessToken", "ConsumerID, ConsumerSecret", "access token", "critical"),
        ("daily_ohlcv", "get_daily_ohlcv", "canonical latest price and daily OHLCV history", "DailyOhlc", "symbol, fromDate, toDate, pageIndex, pageSize, ascending", "TradingDate, Open, High, Low, Close, Volume, Value", "critical"),
        ("daily_stock_price", "get_daily_stock_price", "daily enrichment and foreign-flow history", "DailyStockPrice", "symbol, fromDate, toDate, pageIndex, pageSize, market", "foreign buy/sell value and volume plus daily trading fields", "critical"),
        ("daily_index", "get_daily_index", "historical index data", "DailyIndex", "indexId, dates, paging", "index OHLC/value/volume fields", "important"),
        ("intraday_ohlcv", "get_intraday_ohlcv", "completed-session and supported intraday bars", "IntradayOhlc", "symbol, fromDate, toDate, pageIndex, pageSize, resolution", "minute/hour OHLCV rows", "important"),
        ("completed_intraday_1m", "get_completed_intraday_1m", "completed-session 1m chart history", "IntradayOhlc", "symbol and completed-session range", "normalized 1m bars", "important"),
        ("securities", "get_securities", "security master and universe discovery", "Securities", "market, pageIndex, pageSize", "symbol, market, exchange identity fields", "important"),
        ("securities_details", "get_securities_details", "exact-symbol metadata", "SecuritiesDetails", "symbol, market", "descriptive, reference, lot, listed-share metadata", "important"),
        ("index_list", "get_index_list", "index discovery", "IndexList", "exchange", "index identity rows", "important"),
        ("index_components", "get_index_components", "SSI-derived current VN30 membership", "IndexComponents", "indexCode", "nested IndexComponent StockSymbol rows", "critical"),
        ("realtime_snapshot", "get_realtime_snapshot", "optional cached quote status", "V2 SignalR X channel", "bounded configured symbol channels", "quote fields and observed timestamps", "optional"),
        ("order_book", "get_order_book", "optional X-QUOTE ladder", "V2 SignalR X-QUOTE channel", "bounded configured symbol channels", "bid/ask price-volume levels", "optional"),
        ("trade_tape", "get_trade_tape", "optional X-TRADE matched rows/current-session bars", "V2 SignalR X-TRADE channel", "bounded configured symbol channels", "trade time, price, volume, side/change fields", "important"),
        ("session_status", "get_session_status", "optional F session/status diagnostics", "V2 SignalR F channel", "bounded configured market channel", "session/status payload", "optional"),
        ("foreign_room", "get_foreign_room", "optional R foreign-room snapshot", "V2 SignalR R channel", "bounded configured symbol channels", "foreign room fields", "optional"),
        ("market_index_pulse", "get_market_index_pulse", "optional MI realtime market/index pulse", "V2 SignalR MI channel", "bounded configured index channels", "index/pulse fields", "optional"),
    ]
    inventory: list[dict[str, Any]] = []
    for capability, method, purpose, endpoint, request_fields, response_fields, importance in rows:
        inventory.append(
            {
                **common,
                "capability": capability,
                "method": method,
                "caller": "src/services/vietnam_market_service.py or src/services/vietnam_foreign_flow_service.py",
                "business_purpose": purpose,
                "endpoint_or_model": endpoint,
                "request_fields": request_fields,
                "response_fields_consumed": response_fields,
                "source_label": f"SSI {endpoint}",
                "tests": "tests/test_ssi_fastconnect_fetcher.py and capability-specific Vietnam service tests",
                "production_importance": importance,
                "usage": "production",
            }
        )
    return inventory


def v2_audit_only_inventory() -> list[dict[str, str]]:
    return [
        {
            "capability": "diagnostic and verification scripts",
            "usage": "audit_only",
            "reason": "scripts probe documented V2 shapes but are not request-path dependencies",
        },
        {
            "capability": "deferred HOSE SecuritiesDetails A2 probe",
            "usage": "not_reopened",
            "reason": "explicitly excluded by SSI-V3-A1",
        },
    ]


def v3_capability_inventory() -> list[dict[str, str]]:
    """Return official V3 contracts inspected without installing the SDK."""
    return [
        {"capability": "authentication", "contract": "POST /api/v3/auth/token", "client": "Auth/AsyncAuth or raw REST", "evidence": OFFICIAL_SOURCES["auth_token"]},
        {"capability": "security master/index members", "contract": "GET /api/v3/data/securitiesByBoard", "client": "Data market_data securities methods", "evidence": OFFICIAL_SOURCES["securities_by_board"]},
        {"capability": "daily trading and foreign totals", "contract": "GET /api/v3/data/securitiesSummary", "client": "Data market_data securities summary methods", "evidence": OFFICIAL_SOURCES["securities_summary"]},
        {"capability": "daily/intraday OHLCV", "contract": "GET /api/v3/data/ohlc", "client": "Data market_data OHLC methods", "evidence": OFFICIAL_SOURCES["ohlc"]},
        {"capability": "index list/summary", "contract": "GET /api/v3/data/indexList and /indexSummary", "client": "Data index methods", "evidence": OFFICIAL_SOURCES["api_overview"]},
        {"capability": "historical market file", "contract": "GET /api/v3/data/file", "client": "raw REST/SDK data client", "evidence": OFFICIAL_SOURCES["market_file"]},
        {"capability": "realtime stream", "contract": "WebSocket subscribe/unsubscribe topics", "client": "Stream", "evidence": OFFICIAL_SOURCES["websocket"]},
        {"capability": "rate/retry/token lifecycle", "contract": "rate headers plus SDK integrated management", "client": "official SDK", "evidence": OFFICIAL_SOURCES["sdk_overview"]},
    ]


def _impact_row(
    capability: str,
    business_use: str,
    production: str,
    v2: str,
    v3: str,
    decision: str,
    *,
    credential: str = "same_existing_values_require_live_V3_auth_proof",
    request: str = "incompatible_wire_contract_adapter_required",
    response: str = "normalizer_required_and_live_parity_unverified",
    fields: str = "partial_documented_overlap_only",
    units: str = "unverified_do_not_assume",
    finality: str = "unverified_do_not_assume",
    cache: str = "preserve_existing_business_cache_keys_and_TTL_until_shadow_parity",
    errors: str = "map_V3_status_rate_and_auth_errors_without_changing_public_optional_failure_semantics",
    tests: str = "add_V2_V3_normalization_and_shadow_parity_fixtures",
    frontend: str = "none_if_normalized_API_contract_is_preserved",
    evidence: str = "repository_plus_official_V3_documentation",
    gaps: str = "bounded_live_contract_evidence",
    exit_criterion: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "capability": capability,
        "current_business_use": business_use,
        "current_production_file_or_method": production,
        "current_V2_endpoint_or_client": v2,
        "V3_endpoint_or_client": v3,
        "credential_compatibility": credential,
        "request_compatibility": request,
        "response_compatibility": response,
        "field_compatibility": fields,
        "unit_compatibility": units,
        "finality_compatibility": finality,
        "cache_impact": cache,
        "error_handling_impact": errors,
        "test_impact": tests,
        "frontend_impact": frontend,
        "migration_decision": decision,
        "evidence_level": evidence,
        "blocking_gaps": gaps,
        "exit_criterion": exit_criterion,
    }


def change_impact_matrix() -> list[dict[str, Any]]:
    """Map each current capability or cutover asset to exactly one decision."""
    keep = "KEEP_V2_TEMPORARILY"
    rows = [
        _impact_row("V2 authentication", "authorize all current REST reads", "ssi_fastconnect_fetcher.get_access_token", "AccessToken model", "POST /api/v3/auth/token", keep, response="token_shape_and_lifecycle_are_different", fields="access_and_refresh_expiry_fields_differ", units="not_applicable", finality="token_expiry_semantics_differ", gaps="V3 data-contract parity after auth", exit_criterion="V3 shadow auth, refresh, expiry, and error handling pass deterministic and bounded-live acceptance while V2 remains primary"),
        _impact_row("V3 shadow authentication foundation", "future disabled shadow reads only", "future audit-approved adapter", "none", "POST /api/v3/auth/token", "MIGRATE_TO_V3_FIRST", response="new_V3_token_lifecycle", fields="documented_token_presence_only", units="not_applicable", finality="expiry_fields_documented", gaps="A_or_B_gate_and_client_id_SDK_mapping", exit_criterion=None),
        _impact_row("Securities universe", "security master/universe discovery", "ssi_fastconnect_fetcher.get_securities", "Securities", "securitiesByBoard?board=...", "DUAL_RUN_FOR_PARITY", fields="identity_and_board_overlap_but_type_authority_missing", gaps="coverage_pagination_and_instrument_type_authority"),
        _impact_row("SecuritiesDetails metadata", "exact-symbol metadata", "ssi_fastconnect_fetcher.get_securities_details", "SecuritiesDetails", "securitiesByBoard?symbol=...", keep, fields="V3_documented_subset_does_not_prove_full_metadata_parity", gaps="listed_share_reference_price_and_security_type_field_parity", exit_criterion="exact-symbol V2/V3 fixture and bounded-live comparison proves every consumed metadata field or defines truthful null handling"),
        _impact_row("DailyOhlc", "canonical latest_price and daily chart/TA", "ssi_fastconnect_fetcher.get_daily_ohlcv", "DailyOhlc", "GET /api/v3/data/ohlc?timeFrame=1d", "DUAL_RUN_FOR_PARITY", fields="OHLCV_and_value_documented_with_new_envelope", gaps="price_volume_value_units_date_order_pagination_and_completed-session_finality"),
        _impact_row("completed-session intraday OHLCV", "1m historical chart", "get_intraday_ohlcv/get_completed_intraday_1m", "IntradayOhlc", "GET /api/v3/data/ohlc?timeFrame=1m", "DUAL_RUN_FOR_PARITY", fields="OHLCV_overlap", gaps="timestamp_timezone_bucket_volume_and_session_boundary_semantics"),
        _impact_row("current-session delayed 1m bars", "today chart hydration", "vietnam_market_service current-session bar path", "V2 IntradayOhlc/X-TRADE derived path", "V3 OHLC or Stream", keep, fields="source_and_finality_path_not_selected", gaps="active-session availability_delay_and_bar_finality", exit_criterion="market-hours shadow run proves newest-bar age, bucket finality, and non-regression of current-session health diagnostics"),
        _impact_row("DailyStockPrice trading summary", "daily enrichment", "ssi_fastconnect_fetcher.get_daily_stock_price", "DailyStockPrice", "GET /api/v3/data/securitiesSummary", keep, fields="many_daily_fields_overlap_but_names_and_envelope_differ", gaps="matched_put-through_reference_and_zero/null_parity", exit_criterion="one-symbol then bounded-universe completed-session parity proves consumed fields, explicit zero, missing, units, and finality"),
        _impact_row("foreign-flow history", "buy/sell value and volume history", "vietnam_foreign_flow_service via get_daily_stock_price", "DailyStockPrice", "GET /api/v3/data/securitiesSummary", keep, fields="foreign_buy_sell_value_and_volume_are_documented", gaps="live_units_scaling_finality_coverage_and_direct-net_semantics", exit_criterion="same-symbol same-date V2/V3 normalized values match or an approved deterministic unit conversion is proven across completed sessions"),
        _impact_row("foreign-flow analytics", "coverage, sign, ranking, aggregation", "src/services/vietnam_foreign_flow_service.py", "normalized V2 rows", "normalized provider-neutral rows", "REUSE_UNCHANGED", credential="not_applicable", request="not_applicable_business_logic", response="unchanged_domain_contract", fields="null_and_explicit_zero_semantics_must_remain_unchanged", units="reuse_only_after_adapter_normalizes_to_current_units", finality="reuse_only_for_completed-session_rows", cache="existing_service_cache_can_remain", errors="existing_partial_coverage_semantics_can_remain", tests="existing_analytics_tests_remain_plus_adapter_contract_tests", gaps="none_in_business_logic; provider_adapter_still_gated"),
        _impact_row("IndexList", "index identity discovery", "ssi_fastconnect_fetcher.get_index_list", "IndexList", "GET /api/v3/data/indexList", "MIGRATE_TO_V3_LATER", fields="identity_fields_require_mapping", gaps="live_identity_coverage_and_code_parity"),
        _impact_row("DailyIndex", "historical index OHLC/value/volume context", "ssi_fastconnect_fetcher.get_daily_index", "DailyIndex", "GET /api/v3/data/indexSummary", "DUAL_RUN_FOR_PARITY", fields="index_summary_fields_require_normalization", gaps="identifier_date_OHLC_breadth_value_volume_units_and_finality"),
        _impact_row("IndexComponents/current VN30 membership", "SSI-derived VN30 members", "ssi_fastconnect_fetcher.get_index_components", "IndexComponents(indexCode=VN30)", "securitiesByBoard?index=VN30", keep, fields="component_symbols_documented_but_weights/effective_date_not_proven", gaps="count_symbols_weights_effective_timestamp_and_outer-index_validation", exit_criterion="same-index bounded V2/V3 comparison proves normalized unique members and documents effective-time differences without hardcoded output"),
        _impact_row("VN30 foreign-flow aggregate", "aggregate current members only", "vietnam_foreign_flow_service aggregation", "normalized V2 membership and flow rows", "normalized V3 adapter rows", "REUSE_BUSINESS_LOGIC_WITH_ADAPTER", credential="not_applicable", request="adapter_inputs_only", response="business_output_unchanged", fields="coverage_and_membership_provenance_unchanged", units="adapter_must_supply_current_units", finality="completed-session_membership_policy_unchanged", gaps="provider input parity only"),
        _impact_row("realtime quote", "optional last-known X quote", "ssi_fastconnect_fetcher.get_realtime_snapshot", "V2 SignalR X", "V3 Stream quote topic", keep, fields="topic_and_message_schema_differ", gaps="OTP_entitlement_URL_snapshot_delta_heartbeat_symbol_limits", exit_criterion="bounded market-hours shadow stream proves auth, one-symbol subscription, heartbeat, reconnect/resubscribe, fields, timestamps, and stale preservation"),
        _impact_row("realtime trade", "X-TRADE tape/current-session inputs", "ssi_fastconnect_fetcher.get_trade_tape", "V2 SignalR X-TRADE", "V3 Stream trade topic", keep, fields="trade_side_change_and_sequence_mapping_unverified", gaps="side_codes_sequence_duplicate_policy_and_timestamp", exit_criterion="bounded market-hours shadow captures sanitized normalized trades and proves side, price, volume, sequence, dedupe, reconnect, and gap behavior"),
        _impact_row("order book", "optional X-QUOTE ladder", "ssi_fastconnect_fetcher.get_order_book", "V2 SignalR X-QUOTE", "V3 Stream quote/order-book topic", keep, fields="ladder_depth_and_delta_semantics_unverified", gaps="snapshot_delta_depth_sequence_and_stale_recovery", exit_criterion="one-symbol shadow proves full ladder reconstruction, depth, ordering, timestamps, and reconnect snapshot recovery"),
        _impact_row("foreign room realtime", "optional R snapshot", "ssi_fastconnect_fetcher.get_foreign_room", "V2 SignalR R", "V3 Stream foreign-room field/topic", keep, fields="documented_SDK_model_but_live_topic_contract_unverified", gaps="topic_entitlement_units_and_snapshot_semantics", exit_criterion="one-symbol live shadow proves topic, units, null/zero behavior, and after-hours last-known preservation"),
        _impact_row("market session/status", "F channel diagnostics", "ssi_fastconnect_fetcher.get_session_status", "V2 SignalR F", "no direct V3 equivalent proven", keep, fields="no_contract_equivalence", gaps="official_V3_session_status_topic_or_replacement", exit_criterion="official V3 contract or retained live evidence supplies equivalent market-session/status semantics"),
        _impact_row("market/index stream", "MI pulse and optional index status", "ssi_fastconnect_fetcher.get_market_index_pulse", "V2 SignalR MI", "V3 Stream market/index topics", keep, fields="index_message_mapping_unverified", gaps="topic_codes_fields_units_heartbeat_and_finality", exit_criterion="bounded index shadow proves topic, normalized index fields, timestamps, reconnect, and after-hours behavior"),
        _impact_row("cache and single-flight policy", "protect SSI and preserve last-known data", "Vietnam service/fetcher caches", "V2-specific fetch keys", "V3 adapter-specific fetch keys behind same domain cache", "REUSE_BUSINESS_LOGIC_WITH_ADAPTER", credential="not_applicable", request="provider_key_namespace_must_be_separate_during_shadow", response="domain_cache_contract_reusable", fields="cache_metadata_must_identify_provider/version", units="not_applicable", finality="existing_freshness_policy_reusable_after_timestamp_mapping", gaps="shadow_cache_isolation_and_rate-budget_design"),
        _impact_row("public API and frontend contracts", "render normalized VN data", "api/v1 and apps/dsa-web consumers", "version-neutral normalized payload", "same normalized payload", "REUSE_UNCHANGED", credential="not_applicable", request="no_public_request_change", response="no_public_response_change", fields="preserve_existing_optional_fields_and_reasons", units="preserve_current_public_units", finality="preserve_current_labels", cache="no_client_cache_change", errors="no_public_error_change", tests="existing_API_and_frontend_tests_should_remain_green", frontend="no_change", gaps="none_if_adapter_contract_is_preserved"),
        _impact_row("historical market file", "future bounded bulk history", "not currently used", "no current production equivalent", "GET /api/v3/data/file", "V3_NEW_OPTIONAL_CAPABILITY", fields="CSV_OHLCV_documented", gaps="entitlement_file_size_download_expiry_units_and_safe_ingestion"),
        _impact_row("additional OHLC intervals", "future chart intervals", "not currently used as a V3 feature", "current V2 supported set", "V3 OHLC 3m/5m/15m/30m plus documented SDK intervals", "V3_NEW_OPTIONAL_CAPABILITY", fields="interval_list_documented", gaps="product_need_live_bucket_semantics_and_rate_budget"),
        _impact_row("V3 rate-limit metadata", "future provider budget observability", "not currently exposed from V3", "V2 guardrails", "X-RATELIMIT headers and SDK limiter", "V3_NEW_OPTIONAL_CAPABILITY", credential="not_applicable", request="new_response_metadata", response="additive_internal_diagnostics_only", fields="limit_remaining_reset", units="header_values_provider_defined", finality="per_response", gaps="live_header_presence_and_reset_time_semantics"),
        _impact_row("V2 dependency/imports and credential aliases", "current V2 provider runtime", "requirements.txt, fetcher imports, config, Docker install", "ssi-fc-data==V2 path", "ssi-sdk future dependency", "REMOVE_AFTER_V3_CUTOVER", credential="remove_V2_names_only_after_cutover", request="V2_models_removed_after_parity", response="V2_normalizers_removed_after_parity", fields="not_applicable", units="not_applicable", finality="not_applicable", cache="delete_V2_only_cache_keys_after_rollback_window", errors="delete_V2_only_error_mapping_after_rollback_window", tests="retire_V2_contract_tests_only_after_V3_acceptance", frontend="none", gaps="full_cutover_acceptance_and_rollback_window_complete"),
        _impact_row("instrument-type/HOSE common-stock authority", "safe universe filtering", "current Securities/SecuritiesDetails audit logic", "V2 evidence remains incomplete and A2 is deferred", "securitiesByBoard documented rows", "INCONCLUSIVE", fields="no_authoritative_documented_type_field", gaps="official_code_mapping_or_live_authoritative_field"),
    ]
    return rows


def grouped_migration_decisions(matrix: Optional[list[dict[str, Any]]] = None) -> dict[str, list[str]]:
    rows = change_impact_matrix() if matrix is None else matrix
    grouped = {decision: [] for decision in (
        "REUSE_UNCHANGED", "REUSE_BUSINESS_LOGIC_WITH_ADAPTER", "MIGRATE_TO_V3_FIRST",
        "MIGRATE_TO_V3_LATER", "DUAL_RUN_FOR_PARITY", "KEEP_V2_TEMPORARILY",
        "V3_NEW_OPTIONAL_CAPABILITY", "REMOVE_AFTER_V3_CUTOVER", "UNSUPPORTED_IN_V3", "INCONCLUSIVE",
    )}
    for row in rows:
        grouped[str(row["migration_decision"])].append(str(row["capability"]))
    return grouped


def validate_keep_v2_exit_criteria(matrix: Optional[list[dict[str, Any]]] = None) -> bool:
    rows = change_impact_matrix() if matrix is None else matrix
    return all(
        bool(row.get("exit_criterion"))
        for row in rows
        if row.get("migration_decision") == "KEEP_V2_TEMPORARILY"
    )


def file_impact_plan() -> list[dict[str, str]]:
    """Projected implementation files; no production file is modified by A1."""
    return [
        {"file": "data_provider/ssi_fastconnect_fetcher.py", "current_V2_responsibility": "V2 REST and SignalR adapter", "required_V3_change": "retain as explicit V2 adapter during shadow period", "business_logic_change": "no", "API_contract_change": "no", "test_change": "V2 regression retention", "deployment_or_config_change": "none_until_shadow_phase", "migration_phase": "SSI-V3-B_or_later"},
        {"file": "future data_provider/ssi_fastconnect_v3_fetcher.py", "current_V2_responsibility": "none", "required_V3_change": "disabled shadow-only Auth/Data normalizer", "business_logic_change": "no", "API_contract_change": "no", "test_change": "new offline contract tests", "deployment_or_config_change": "future dependency/config only after gate", "migration_phase": "only_after_outcome_A_or_B"},
        {"file": "src/services/vietnam_market_service.py", "current_V2_responsibility": "orchestration, caches, normalized domain semantics", "required_V3_change": "provider selection/shadow comparison injection only", "business_logic_change": "no", "API_contract_change": "no", "test_change": "shadow isolation and parity", "deployment_or_config_change": "future disabled flag", "migration_phase": "after_adapter_foundation"},
        {"file": "src/services/vietnam_foreign_flow_service.py", "current_V2_responsibility": "completed-session analytics", "required_V3_change": "consume normalized adapter rows only after unit/finality proof", "business_logic_change": "no", "API_contract_change": "no", "test_change": "cross-provider normalized fixtures", "deployment_or_config_change": "none_until_parity", "migration_phase": "late"},
        {"file": "src/config.py and src/core/config_registry.py", "current_V2_responsibility": "current V2 names", "required_V3_change": "future explicit aliases and shadow controls without value duplication", "business_logic_change": "no", "API_contract_change": "no", "test_change": "name mapping and secret safety", "deployment_or_config_change": "future only", "migration_phase": "adapter_foundation"},
        {"file": "requirements.txt and Docker image", "current_V2_responsibility": "install ssi-fc-data V2", "required_V3_change": "add pinned ssi-sdk only for approved shadow adapter; remove V2 only after cutover", "business_logic_change": "no", "API_contract_change": "no", "test_change": "import/compatibility smoke", "deployment_or_config_change": "yes_future_not_A1", "migration_phase": "shadow_then_cutover"},
        {"file": "apps/dsa-web", "current_V2_responsibility": "consume normalized public API", "required_V3_change": "none when public contract is preserved", "business_logic_change": "no", "API_contract_change": "no", "test_change": "existing tests only", "deployment_or_config_change": "none", "migration_phase": "none"},
    ]


def _live_credentials(environment: Mapping[str, str]) -> dict[str, str]:
    return {
        name: str(environment.get(variable) or "").strip()
        for name, variable in V3_AUDIT_ENV_NAMES.items()
    }


def _http_json(url: str, *, method: str, headers: Mapping[str, str], payload: Optional[Mapping[str, Any]] = None) -> tuple[int, dict[str, Any], dict[str, str]]:
    """Send exactly one bounded HTTPS request.  Called only by explicit live mode."""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {"Accept": "application/json", **dict(headers)}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=request_headers, method=method)
    with urlopen(request, timeout=LIVE_TIMEOUT_SECONDS) as response:  # nosec B310: fixed official HTTPS URL
        response_body = response.read(MAX_DOWNLOAD_BYTES + 1)
        if len(response_body) > MAX_DOWNLOAD_BYTES:
            raise ValueError("response exceeded the 10 MB live-audit bound")
        decoded = json.loads(response_body.decode("utf-8")) if response_body else {}
        return int(response.status), decoded if isinstance(decoded, dict) else {"data_type": type(decoded).__name__}, dict(response.headers.items())


def run_live_smoke(
    environment: Optional[Mapping[str, str]] = None,
    *,
    allow_live: bool = False,
    allow_websocket: bool = False,
    allow_small_download: bool = False,
) -> dict[str, Any]:
    """Run at most one auth, one security, one history, and one index request.

    It intentionally declines WebSocket and file download operations until a
    locally installed official client plus a documented V3 credential grant are
    available.  That is safer than guessing a streaming handshake or following
    a temporary link.
    """
    env = os.environ if environment is None else environment
    credentials = _live_credentials(env)
    plan = live_smoke_plan(allow_websocket=allow_websocket, allow_small_download=allow_small_download)
    result: dict[str, Any] = {"evidence_level": "unavailable", "plan": plan, "operations": []}
    if not allow_live:
        result["reason"] = "--allow-live is required; no network operation was attempted"
        return result
    if not (credentials["api_key"] and credentials["api_secret"] and credentials["audit_symbol"]):
        result["reason"] = "V3 audit API-key, API-secret, and bounded audit-symbol names must all be present"
        return result

    known_secrets = [credentials["api_key"], credentials["api_secret"]]
    try:
        _, auth_payload, auth_headers = _http_json(
            V3_AUTH_URL,
            method="POST",
            headers={},
            payload={"apiKey": credentials["api_key"], "apiSecret": credentials["api_secret"]},
        )
    except HTTPError as error:
        result.update({"reason": f"auth_http_{error.code}", "operations": [{"auth": f"http_{error.code}"}]})
        return sanitize_value(result, known_secrets)
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
        result.update({"reason": f"auth_unavailable:{type(error).__name__}", "operations": [{"auth": "unavailable"}]})
        return sanitize_value(result, known_secrets)

    access_token = str(auth_payload.get("accessToken") or "")
    if not access_token:
        result.update({"reason": "auth_response_missing_access_token", "operations": [{"auth": "rejected_or_unexpected"}]})
        return sanitize_value(result, known_secrets)
    known_secrets.append(access_token)
    result["operations"].append({"auth": "verified", "rate_limit": extract_rate_limit_metadata(auth_headers)})

    bearer_headers = {"Authorization": f"Bearer {access_token}"}
    symbol = credentials["audit_symbol"].upper()
    today = date.today()
    from_date = (today - timedelta(days=1)).strftime("%Y/%m/%d")
    to_date = today.strftime("%Y/%m/%d")
    operations = (
        ("security_master", f"{V3_API_BASE_URL}/api/v3/data/securitiesByBoard?{urlencode({'symbol': symbol})}"),
        ("historical", f"{V3_API_BASE_URL}/api/v3/data/securitiesSummary?{urlencode({'symbol': symbol, 'from': from_date, 'to': to_date, 'pageIndex': 1, 'pageSize': 1})}"),
    )
    if credentials["audit_index"]:
        operations += (("index_components", f"{V3_API_BASE_URL}/api/v3/data/securitiesByBoard?{urlencode({'index': credentials['audit_index'].upper()})}"),)
    for operation, url in operations:
        try:
            status, payload, headers = _http_json(url, method="GET", headers=bearer_headers)
        except HTTPError as error:
            result["operations"].append({operation: f"http_{error.code}"})
            result["reason"] = f"{operation}_http_{error.code}"
            break
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            result["operations"].append({operation: "unavailable"})
            result["reason"] = f"{operation}_unavailable:{type(error).__name__}"
            break
        result["operations"].append(
            {
                operation: "verified_response_shape_only",
                "http_status": status,
                "rate_limit": extract_rate_limit_metadata(headers),
                "response_keys": sorted(str(key) for key in payload)[:20],
            }
        )
    else:
        result["evidence_level"] = "live_verified"
        result["reason"] = "bounded REST sequence completed; field semantics still require retained normalized evidence"
    result["websocket"] = "not_attempted: audit does not guess a V3 handshake or credential grant"
    result["small_download"] = "not_attempted: audit does not follow temporary file links"
    return sanitize_value(result, known_secrets)


def run_existing_key_auth(
    environment: Optional[Mapping[str, str]] = None,
    *,
    allow_live: bool = False,
) -> dict[str, Any]:
    """Try the existing V2 credential values against V3 exactly once.

    This function intentionally performs authentication only.  It does not
    select a symbol, issue a market-data request, persist a token, or retry.
    """
    env = os.environ if environment is None else environment
    application_identifier = str(env.get("SSI_FASTCONNECT_CONSUMER_ID") or "").strip()
    application_secret = str(env.get("SSI_FASTCONNECT_CONSUMER_SECRET") or "").strip()
    result: dict[str, Any] = {
        "attempted": False,
        "success": False,
        "http_status": None,
        "failure_class": "not_attempted",
        "token_type_present": False,
        "access_token_present": False,
        "refresh_token_present": False,
        "expires_at_present": False,
        "refresh_expires_at_present": False,
        "rate_limit_headers": extract_rate_limit_metadata({}),
        "elapsed_milliseconds": 0,
        "authentication_sequences": 0,
        "raw_response_retained": False,
        "token_values_retained": False,
    }
    if not allow_live:
        result["failure_class"] = "live_not_authorized"
        return result
    if not (application_identifier and application_secret):
        result["failure_class"] = "existing_credentials_not_configured"
        return result

    known_secrets = [application_identifier, application_secret]
    started = perf_counter()
    result["attempted"] = True
    result["authentication_sequences"] = 1
    try:
        status, auth_payload, auth_headers = _http_json(
            V3_AUTH_URL,
            method="POST",
            headers={},
            payload={"apiKey": application_identifier, "apiSecret": application_secret},
        )
    except HTTPError as error:
        result["http_status"] = int(error.code)
        result["rate_limit_headers"] = extract_rate_limit_metadata(dict(error.headers.items()) if error.headers else {})
        if error.code in {401, 403}:
            result["failure_class"] = "credentials_explicitly_rejected"
        elif error.code == 429:
            result["failure_class"] = "provider_rate_limited"
        elif error.code == 400:
            result["failure_class"] = "auth_request_rejected_without_safe_credential_attribution"
        else:
            result["failure_class"] = "auth_http_error"
    except (URLError, TimeoutError, OSError) as error:
        result["failure_class"] = f"network_or_tls_failure:{type(error).__name__}"
    except (ValueError, json.JSONDecodeError) as error:
        result["failure_class"] = f"auth_response_uninterpretable:{type(error).__name__}"
    else:
        result["http_status"] = int(status)
        result["rate_limit_headers"] = extract_rate_limit_metadata(auth_headers)
        result["token_type_present"] = bool(auth_payload.get("tokenType"))
        result["access_token_present"] = bool(auth_payload.get("accessToken"))
        result["refresh_token_present"] = bool(auth_payload.get("refreshToken"))
        result["expires_at_present"] = bool(auth_payload.get("expiresAt"))
        result["refresh_expires_at_present"] = bool(auth_payload.get("refreshExpiresAt"))
        if 200 <= status < 300 and result["access_token_present"]:
            result["success"] = True
            result["failure_class"] = "none"
        else:
            result["failure_class"] = "auth_response_missing_access_token"
        # Drop the only local reference to token-bearing response data before
        # sanitizing and returning aggregate evidence.
        auth_payload = {}
    finally:
        result["elapsed_milliseconds"] = max(0, round((perf_counter() - started) * 1000))
        application_identifier = ""
        application_secret = ""
    return sanitize_value(result, known_secrets)


def decide_change_impact_outcome(authentication_result: Mapping[str, Any], critical_contract: str) -> tuple[str, str]:
    """Return the exact A-F A1 outcome without treating network as rejection."""
    failure = str(authentication_result.get("failure_class") or "")
    if failure == "credentials_explicitly_rejected":
        return "D", "EXISTING CREDENTIALS REJECTED BY V3"
    if not authentication_result.get("success"):
        return "F", "INCONCLUSIVE"
    if critical_contract == "incompatible":
        return "E", "V3 CONTRACT INCOMPATIBILITY BLOCKS SAFE MIGRATION"
    if critical_contract == "fully_mapped":
        return "A", "EXISTING CREDENTIALS VERIFIED; MIGRATION IMPACT FULLY MAPPED"
    if critical_contract == "partially_mapped_adapter_can_begin":
        return "B", "EXISTING CREDENTIALS VERIFIED; PARTIAL MIGRATION MAP"
    if critical_contract == "unverified":
        return "C", "CREDENTIALS RECOGNIZED BUT REQUIRED CONTRACTS REMAIN UNVERIFIED"
    return "F", "INCONCLUSIVE"


def change_impact_report(
    environment: Optional[Mapping[str, str]] = None,
    *,
    allow_live: bool = False,
) -> dict[str, Any]:
    """Build the complete A1 map and optional one-sequence auth evidence."""
    auth = run_existing_key_auth(environment, allow_live=allow_live)
    matrix = change_impact_matrix()
    grouped = grouped_migration_decisions(matrix)
    outcome_code, outcome_label = decide_change_impact_outcome(auth, "unverified")
    keep_rows = [row for row in matrix if row["migration_decision"] == "KEEP_V2_TEMPORARILY"]
    return sanitize_value(
        {
            "baseline": {
                "production_version": "SSI FastConnect V2",
                "V2_primary": True,
                "production_migration_performed": False,
                "package_inventory": package_inventory(),
                "configuration_presence": configuration_presence(environment),
            },
            "credential_mapping": credential_mapping(environment),
            "authentication_result": auth,
            "v2_inventory": v2_capability_inventory(),
            "v2_audit_only_inventory": v2_audit_only_inventory(),
            "v3_inventory": v3_capability_inventory(),
            "contract_matrix": matrix,
            "bounded_parity_results": {
                "status": "not_attempted",
                "reason": "A1 retained only the one permitted authentication sequence; no provider-derived symbol/token was persisted for a later request",
                "partial_parity_called_full_parity": False,
            },
            "reuse_unchanged": grouped["REUSE_UNCHANGED"],
            "reuse_business_logic_with_adapter": grouped["REUSE_BUSINESS_LOGIC_WITH_ADAPTER"],
            "migrate_to_v3_first": grouped["MIGRATE_TO_V3_FIRST"],
            "migrate_to_v3_later": grouped["MIGRATE_TO_V3_LATER"],
            "dual_run_for_parity": grouped["DUAL_RUN_FOR_PARITY"],
            "keep_v2": keep_rows,
            "new_v3": grouped["V3_NEW_OPTIONAL_CAPABILITY"],
            "remove_after_cutover": grouped["REMOVE_AFTER_V3_CUTOVER"],
            "unsupported_in_v3": grouped["UNSUPPORTED_IN_V3"],
            "unresolved": grouped["INCONCLUSIVE"],
            "all_decision_groups": grouped,
            "every_retained_v2_path_has_exit_criterion": validate_keep_v2_exit_criteria(matrix),
            "file_impact": file_impact_plan(),
            "realtime_decision": [
                "requires_stream_manager_rewrite",
                "keep_V2_until_shadow_test",
                "inconclusive",
            ],
            "recommended_migration_sequence": [
                "retain V2 as sole production provider",
                "obtain A or B through bounded contract-specific V3 parity evidence",
                "add a disabled shadow-only V3 auth/data adapter",
                "dual-run daily OHLCV and security master first",
                "prove DailyStockPrice foreign-flow units/finality and IndexComponents membership",
                "rewrite and shadow-test stream lifecycle last",
                "cut over per capability with rollback window",
                "remove V2 dependency, aliases, and tests only after complete acceptance",
            ],
            "primary_outcome": {"code": outcome_code, "label": outcome_label},
            "production_migration_gate": "closed" if outcome_code not in {"A", "B"} else "open_for_shadow_adapter_only",
            "next_phase": "one bounded contract-specific V3 verification phase" if outcome_code == "C" else "one narrow evidence-recovery follow-up" if outcome_code == "F" else "SSI-V3-B shadow adapter" if outcome_code in {"A", "B"} else "keep V2 unchanged",
            "guardrails": {
                "production_adapter_implemented": False,
                "production_traffic_switched": False,
                "automatic_fallback_added": False,
                "dependency_or_lockfile_changed": False,
                "environment_file_changed": False,
                "frontend_changed": False,
                "raw_response_persisted": False,
                "token_persisted": False,
            },
        }
    )


def render_sanitized_report(report: Mapping[str, Any]) -> str:
    """Render a bounded sanitized report suitable for retained audit evidence."""
    rendered = json.dumps(sanitize_value(report), indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if len(rendered.encode("utf-8")) > MAX_REPORT_BYTES:
        raise ValueError(f"sanitized report exceeds {MAX_REPORT_BYTES} byte bound")
    return rendered


def write_sanitized_report_atomic(path: Path, report: Mapping[str, Any]) -> None:
    """Atomically retain only a bounded, sanitized JSON report."""
    rendered = render_sanitized_report(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def decide_outcome(*, documentation_available: bool, live_auth: str, critical_contract: str) -> tuple[str, str]:
    """Return exactly one A-F outcome from normalized evidence states."""
    if live_auth in {"rejected", "entitlement_rejected"}:
        return "D", "BLOCKED: V3 access or entitlement unavailable"
    if critical_contract in {"missing", "unsafe"}:
        return "E", "NO-GO: a required V3 contract is missing or unsafe"
    if not documentation_available or live_auth == "conflicting":
        return "F", "INCONCLUSIVE: official contract evidence cannot support a reliable decision"
    if live_auth in {"not_configured", "package_unavailable", "not_tested", "network_unavailable"}:
        return "C", "DEFER: official V3 contract found, but live access is not available for verification"
    if live_auth == "verified" and critical_contract == "partial":
        return "B", "PARTIAL GO: V3 access is verified but capability gaps remain"
    if live_auth == "verified" and critical_contract == "verified":
        return "A", "GO: V3 core access and migration baseline verified"
    return "F", "INCONCLUSIVE: evidence state is not recognized"


def decision_report(environment: Optional[Mapping[str, str]] = None, live: Optional[Mapping[str, Any]] = None) -> dict[str, Any]:
    """Build the current migration decision without performing live work."""
    config = configuration_presence(environment)
    packages = package_inventory()
    live_auth = "not_configured" if not config["v3_live_minimum_present"] else "not_tested"
    if live:
        operations = list(live.get("operations") or [])
        if any(item.get("auth") == "verified" for item in operations if isinstance(item, Mapping)):
            live_auth = "verified"
        elif str(live.get("reason") or "").startswith("auth_http_401") or str(live.get("reason") or "").startswith("auth_http_403"):
            live_auth = "rejected"
    code, outcome = decide_outcome(documentation_available=True, live_auth=live_auth, critical_contract="partial")
    next_phase = "SSI-V3 access-enablement follow-up" if code == "C" else "SSI-V3-B" if code in {"A", "B"} else "no production migration phase"
    return {
        "primary_outcome": {"code": code, "label": outcome},
        "migration_gate": "closed" if code not in {"A", "B"} else "open_for_adapter_foundation_only",
        "recommended_next_phase": next_phase,
        "capability_sub_gates": initial_sub_gates(),
        "evidence": {
            "documented": "official SSI portal, API reference, SDK documentation, official tutorial repository, and PyPI package metadata",
            "locally_inspected": {"packages": packages, "configuration": config},
            "live_verified": bool(live and live.get("evidence_level") == "live_verified"),
            "projected": "V2/V3 shadow comparison is a future design only",
            "unavailable": "No local V3 SDK or V3 audit credentials were used for this current decision",
            "inconclusive": "V3 instrument type, HOSE common-stock authority, foreign units/finality, historical membership, and WebSocket endpoint selection",
        },
        "limitations": [
            "No V2 A2 live probe was reopened.",
            "No V3 provider, configuration, dependency, endpoint, frontend, or fallback behavior was implemented.",
            "V2 remains the production path through its existing lifecycle; the SSI customer notice is recorded but does not deprecate runtime code.",
        ],
    }


def build_report(mode: str, *, environment: Optional[Mapping[str, str]] = None, allow_live: bool = False, allow_websocket: bool = False, allow_small_download: bool = False) -> dict[str, Any]:
    """Build one deterministic report; only explicit live mode may perform I/O."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of: {', '.join(MODES)}")
    base = {
        "audit": SCRIPT_NAME,
        "mode": mode,
        "network_attempted": False,
        "official_sources": deepcopy(OFFICIAL_SOURCES),
    }
    if mode == "config":
        base.update({"configuration": configuration_presence(environment), "packages": package_inventory(), "planned_live_bounds": live_smoke_plan(allow_websocket=False, allow_small_download=False)})
        return sanitize_value(base)
    if mode == "sdk":
        base.update({"packages": package_inventory(), "sdk_contracts": {"python_distribution": V3_DISTRIBUTION, "python_namespace": V3_MODULE, "official_clients": ["Config", "Auth", "Data", "Stream"], "official_models": ["SecuritiesInfo", "SecuritiesSummary", "OHLC", "TradeMessage", "QuoteMessage", "ForeignRoomMessage"]}, "local_sdk_import": "not_attempted: audit mode only"})
        return sanitize_value(base)
    if mode == "contracts":
        base.update({"contracts": documented_contracts(), "capability_sub_gates": initial_sub_gates()})
        return sanitize_value(base)
    if mode == "live-smoke":
        live = run_live_smoke(environment, allow_live=allow_live, allow_websocket=allow_websocket, allow_small_download=allow_small_download)
        base.update({"network_attempted": bool(allow_live and live.get("operations")), "live_smoke": live})
        return sanitize_value(base)
    if mode == "change-impact":
        impact = change_impact_report(environment, allow_live=allow_live)
        base.update(
            {
                "network_attempted": bool(impact["authentication_result"]["attempted"]),
                "change_impact": impact,
            }
        )
        return sanitize_value(base)
    live = run_live_smoke(environment, allow_live=allow_live, allow_websocket=allow_websocket, allow_small_download=allow_small_download) if allow_live else None
    base.update({"decision": decision_report(environment, live), "live_smoke": live})
    return sanitize_value(base)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default=DEFAULT_MODE)
    parser.add_argument("--allow-live", action="store_true", help="permit one bounded REST live sequence")
    parser.add_argument("--allow-websocket", action="store_true", help="record a bounded WebSocket audit plan; no handshake is guessed")
    parser.add_argument("--allow-small-download", action="store_true", help="record the <=10 MB file-audit limit; no link is followed")
    parser.add_argument("--output", type=Path, help="optional path for sanitized JSON only; no raw payload is retained")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    environment = cli_environment(retain_values=args.allow_live)
    report = build_report(
        args.mode,
        environment=environment,
        allow_live=args.allow_live,
        allow_websocket=args.allow_websocket,
        allow_small_download=args.allow_small_download,
    )
    if args.output:
        write_sanitized_report_atomic(args.output, report)
    else:
        sys.stdout.write(render_sanitized_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
