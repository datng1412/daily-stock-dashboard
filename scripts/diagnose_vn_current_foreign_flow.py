"""Bounded, manual-only SSI V3 current-session foreign-flow evidence gate.

The script is deliberately outside production runtime.  Offline mode inventories
only documented candidates.  Live mode is allowed only during an active Vietnam
market window and samples either the V3 foreign-room stream or the existing V3
``DailyStockPrice`` adapter.  Sources that lack explicit ticker-level
foreign-flow fields are rejected without a network call.

Output is sanitized JSON/JSONL evidence.  Credentials, headers, tokens, complete
provider payloads, and unrelated market fields are never emitted.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
import importlib.metadata
import json
import math
from pathlib import Path
import queue
import re
import sys
import threading
import time
from typing import Any, Iterable, Mapping, Optional, Sequence
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_provider.ssi_streaming_realtime import (  # noqa: E402
    vietnam_market_session_from_epoch,
)
from data_provider.ssi_v3_adapter import (  # noqa: E402
    SsiFastConnectV3Adapter,
    SsiV3RestSettings,
)
from data_provider.ssi_v3_streaming import (  # noqa: E402
    OfficialSsiV3RealtimeStreamClient,
)
from data_provider.ssi_v3_foreign_policy import (  # noqa: E402
    SSI_V3_FOREIGN_VALUE_UNIT,
    SSI_V3_FOREIGN_VOLUME_UNIT,
)
from src.config import Config, get_config, setup_env  # noqa: E402


VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
MIN_SYMBOLS = 1
MAX_SYMBOLS = 2
MIN_SAMPLES = 1
MAX_SAMPLES = 8
MIN_INTERVAL_SECONDS = 5
MAX_INTERVAL_SECONDS = 30
MAX_RUNTIME_SECONDS = 120
DELAY_NEAR_REALTIME_SECONDS = 15
DELAY_MATERIAL_SECONDS = 300
DEFAULT_SYMBOLS = ("FPT", "SSI")
DEFAULT_SAMPLE_COUNT = 3
DEFAULT_INTERVAL_SECONDS = 20
DEFAULT_MAX_RUNTIME_SECONDS = 90
DEFAULT_SOURCES = (
    "daily_stock_price",
    "x",
    "x_quote",
    "x_trade",
    "r",
    "f",
    "mi",
)
GROSS_FIELDS = (
    "foreign_buy_volume",
    "foreign_sell_volume",
    "foreign_buy_value",
    "foreign_sell_value",
)
VOLUME_FIELDS = ("foreign_buy_volume", "foreign_sell_volume")
VALUE_FIELDS = ("foreign_buy_value", "foreign_sell_value")
NET_FIELDS = ("foreign_net_volume", "foreign_net_value")
ALL_AUDITED_FIELDS = GROSS_FIELDS + NET_FIELDS
STOP_FAILURE_CLASSES = {
    "authentication",
    "authorization",
    "rate_limited",
    "provider_rate_limited",
}
_SAFE_FAILURE_CLASSES = {
    "authentication",
    "authorization",
    "rate_limited",
    "provider_rate_limited",
    "network_error",
    "timeout",
    "provider_unavailable",
    "malformed_response",
    "configuration",
    "credentials_missing",
    "unknown",
}
_AUTHORIZATION_RE = re.compile(
    r"(?i)([\"']?authorization[\"']?\s*[:=]\s*[\"']?bearer\s+)"
    r"[^\s,;}\]\"']+"
)
_SECRET_RE = re.compile(
    r"(?i)([\"']?(?:authorization|bearer|consumer(?:id|secret)|privatekey|"
    r"api[_-]?(?:key|secret)|access(?:token)?|refresh(?:token)?|password)"
    r"[\"']?)(\s*[:=]\s*|\s+)[^\s,;}\]\"']+"
)


@dataclass(frozen=True)
class Candidate:
    key: str
    source: str
    official_identifier: str
    current_purpose: str
    explicit_foreign_fields: bool
    ticker_scope: bool
    volume: bool
    value: bool
    timestamp: bool
    session_date: bool
    snapshot_delta_known: bool
    gate_status: str
    rejection_reason: Optional[str] = None

    def safe_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "source": self.source,
            "official_identifier": self.official_identifier,
            "current_purpose": self.current_purpose,
            "explicit_foreign_fields": self.explicit_foreign_fields,
            "ticker_scope": self.ticker_scope,
            "volume": self.volume,
            "value": self.value,
            "provider_timestamp": self.timestamp,
            "session_date": self.session_date,
            "snapshot_delta_known": self.snapshot_delta_known,
            "gate_status": self.gate_status,
            "rejection_reason": self.rejection_reason,
        }


CANDIDATES: dict[str, Candidate] = {
    "daily_stock_price": Candidate(
        key="daily_stock_price",
        source="SSI V3 Securities Summary / DailyStockPrice adapter",
        official_identifier="get_securities_summary_historical",
        current_purpose="completed-session foreign flow",
        explicit_foreign_fields=True,
        ticker_scope=True,
        volume=True,
        value=True,
        timestamp=False,
        session_date=True,
        snapshot_delta_known=False,
        gate_status="active_session_pending",
    ),
    "x": Candidate(
        key="x",
        source="SSI V3 trade topic",
        official_identifier="trade.{symbol}",
        current_purpose="matched trade event / quote context",
        explicit_foreign_fields=False,
        ticker_scope=True,
        volume=False,
        value=False,
        timestamp=True,
        session_date=False,
        snapshot_delta_known=False,
        gate_status="failed",
        rejection_reason="no explicit foreign participant or foreign buy/sell fields",
    ),
    "x_quote": Candidate(
        key="x_quote",
        source="SSI V3 quote topic",
        official_identifier="quote.{symbol}",
        current_purpose="order book",
        explicit_foreign_fields=False,
        ticker_scope=True,
        volume=False,
        value=False,
        timestamp=True,
        session_date=False,
        snapshot_delta_known=False,
        gate_status="failed",
        rejection_reason="bid/ask liquidity is not foreign flow",
    ),
    "x_trade": Candidate(
        key="x_trade",
        source="SSI V3 trade topic",
        official_identifier="trade.{symbol}",
        current_purpose="recent matched trades",
        explicit_foreign_fields=False,
        ticker_scope=True,
        volume=False,
        value=False,
        timestamp=True,
        session_date=False,
        snapshot_delta_known=True,
        gate_status="failed",
        rejection_reason="TradeMessage has no foreign participant identity",
    ),
    "r": Candidate(
        key="r",
        source="SSI V3 foreign-room topic",
        official_identifier="room.{symbol}",
        current_purpose="foreign room capacity and separate current-session foreign counters",
        explicit_foreign_fields=True,
        ticker_scope=True,
        volume=True,
        value=True,
        timestamp=True,
        session_date=False,
        snapshot_delta_known=False,
        gate_status="active_session_pending",
        rejection_reason=None,
    ),
    "f": Candidate(
        key="f",
        source="SSI V3 market-status topic",
        official_identifier="market.{board}",
        current_purpose="market session/status context",
        explicit_foreign_fields=False,
        ticker_scope=False,
        volume=False,
        value=False,
        timestamp=False,
        session_date=True,
        snapshot_delta_known=False,
        gate_status="failed",
        rejection_reason="session context has no foreign buy/sell values",
    ),
    "mi": Candidate(
        key="mi",
        source="SSI V3 index/board summary",
        official_identifier="get_index_summary / get_board_summary",
        current_purpose="index pulse and proprietary aggregate",
        explicit_foreign_fields=False,
        ticker_scope=False,
        volume=False,
        value=False,
        timestamp=False,
        session_date=True,
        snapshot_delta_known=False,
        gate_status="failed",
        rejection_reason="no explicit foreign aggregate and no ticker-level authority",
    ),
}


def sanitize_text(value: Any) -> str:
    """Return a one-line diagnostic string with credential-shaped values redacted."""

    text = str(value or "").replace("\r", " ").replace("\n", " ")
    text = _AUTHORIZATION_RE.sub(r"\1[REDACTED]", text)
    return _SECRET_RE.sub(r"\1\2[REDACTED]", text)[:300]


def parse_symbols(value: str) -> tuple[str, ...]:
    symbols: list[str] = []
    for raw in str(value or "").split(","):
        symbol = raw.strip().upper()
        if not symbol:
            continue
        if not re.fullmatch(r"[A-Z0-9]{2,12}", symbol):
            raise ValueError("symbols must contain only 2-12 uppercase letters or digits")
        if symbol not in symbols:
            symbols.append(symbol)
    if not MIN_SYMBOLS <= len(symbols) <= MAX_SYMBOLS:
        raise ValueError(f"symbols must contain between {MIN_SYMBOLS} and {MAX_SYMBOLS} items")
    return tuple(symbols)


def parse_sources(value: str) -> tuple[str, ...]:
    sources: list[str] = []
    for raw in str(value or "").split(","):
        key = raw.strip().lower().replace("-", "_")
        if key == "room":
            key = "r"
        if key and key not in sources:
            sources.append(key)
    unknown = [source for source in sources if source not in CANDIDATES]
    if unknown:
        raise ValueError(f"unsupported candidate source: {unknown[0]}")
    if not sources:
        raise ValueError("at least one candidate source is required")
    return tuple(sources)


def candidate_inventory(sources: Sequence[str] = DEFAULT_SOURCES) -> list[dict[str, Any]]:
    return [CANDIDATES[source].safe_dict() for source in sources]


def _raw_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, Decimal):
        return "decimal"
    return type(value).__name__[:40]


def classify_numeric(
    value: Any,
    *,
    present: bool,
    presence_hint: Optional[str] = None,
) -> dict[str, Any]:
    """Classify one provider numeric field without converting missing/null to zero."""

    hint = str(presence_hint or "").strip().lower()
    if not present or hint == "missing":
        return {"present": False, "raw_type": "missing", "semantic": "missing", "value": None}
    if hint == "malformed":
        return {"present": True, "raw_type": _raw_type(value), "semantic": "malformed", "value": None}
    if value is None or hint == "null":
        return {"present": True, "raw_type": "null", "semantic": "null", "value": None}
    if isinstance(value, str) and not value.strip():
        return {"present": True, "raw_type": "str", "semantic": "blank", "value": None}
    if isinstance(value, bool):
        return {"present": True, "raw_type": "bool", "semantic": "malformed", "value": None}
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return {"present": True, "raw_type": _raw_type(value), "semantic": "malformed", "value": None}
    if not number.is_finite() or number < 0:
        return {"present": True, "raw_type": _raw_type(value), "semantic": "malformed", "value": None}
    normalized: int | float
    if number == number.to_integral_value():
        normalized = int(number)
    else:
        normalized = float(number)
    return {
        "present": True,
        "raw_type": _raw_type(value),
        "semantic": "explicit_zero" if number == 0 else "nonzero",
        "value": normalized,
    }


def _derive_net(buy: Mapping[str, Any], sell: Mapping[str, Any]) -> dict[str, Any]:
    buy_value = buy.get("value")
    sell_value = sell.get("value")
    if buy_value is None or sell_value is None:
        return {
            "present": False,
            "raw_type": "derived",
            "semantic": "missing",
            "value": None,
        }
    result = float(buy_value) - float(sell_value)
    value: int | float = int(result) if result.is_integer() else result
    return {
        "present": True,
        "raw_type": "derived",
        "semantic": "derived_zero" if result == 0 else "derived_nonzero",
        "value": value,
    }


def sample_from_row(
    row: Optional[Mapping[str, Any]],
    *,
    symbol: str,
    sample_number: int,
    sampled_at: str,
    expected_session_date: str,
) -> dict[str, Any]:
    source = dict(row or {})
    presence = source.get("_foreign_field_presence")
    hints = presence if isinstance(presence, Mapping) else {}
    raw_types = source.get("_foreign_field_raw_types")
    audited_raw_types = raw_types if isinstance(raw_types, Mapping) else {}
    fields: dict[str, dict[str, Any]] = {}
    for field in GROSS_FIELDS:
        classified = classify_numeric(
            source.get(field),
            present=field in source,
            presence_hint=str(hints.get(field) or ""),
        )
        if field in audited_raw_types:
            classified["raw_type"] = sanitize_text(audited_raw_types[field])
        fields[field] = classified
    fields["foreign_net_volume"] = _derive_net(
        fields["foreign_buy_volume"], fields["foreign_sell_volume"]
    )
    fields["foreign_net_value"] = _derive_net(
        fields["foreign_buy_value"], fields["foreign_sell_value"]
    )
    provider_date = str(source.get("date") or source.get("trading_date") or "") or None
    provider_timestamp = (
        str(source.get("provider_event_timestamp") or source.get("timestamp") or "").strip()
        or None
    )
    return {
        "source": "SSI V3 Securities Summary / DailyStockPrice adapter",
        "sdk_method": "get_securities_summary_historical",
        "symbol": symbol,
        "sample_number": sample_number,
        "sampled_at": sampled_at,
        "expected_session_date": expected_session_date,
        "provider_session_date": provider_date,
        "provider_event_timestamp": provider_timestamp,
        "current_date_row": provider_date == expected_session_date,
        "fields": fields,
        "volume_unit": SSI_V3_FOREIGN_VOLUME_UNIT,
        "value_unit": SSI_V3_FOREIGN_VALUE_UNIT,
    }


ROOM_FLOW_ALIASES = {
    "foreign_buy_volume": ("bq", "buy_quantity", "BuyQuantity"),
    "foreign_sell_volume": ("sq", "sell_quantity", "SellQuantity"),
    "foreign_buy_value": ("bv", "buy_value", "BuyValue"),
    "foreign_sell_value": ("sv", "sell_value", "SellValue"),
}
ROOM_CAPACITY_ALIASES = {
    "total_foreign_room": ("tr", "total_room", "TotalRoom"),
    "current_foreign_room": ("cr", "current_room", "CurrentRoom"),
}
V2_TO_V3_FIELD_MAP = {
    "room_capacity": {
        "TotalRoom": "total_room",
        "CurrentRoom": "current_room",
    },
    "current_foreign_flow": {
        "FBuyVol": "buy_quantity",
        "FSellVol": "sell_quantity",
        "FBuyVal": "buy_value",
        "FSellVal": "sell_value",
    },
    "context": {
        "TradingDate": None,
        "Time": "trading_time",
        "Symbol": "symbol",
    },
}


def _present_value(source: Any, aliases: Sequence[str]) -> tuple[bool, Any]:
    if isinstance(source, Mapping):
        for alias in aliases:
            if alias in source:
                return True, source.get(alias)
        return False, None
    for alias in aliases:
        if hasattr(source, alias):
            return True, getattr(source, alias)
    return False, None


def _text_value(source: Any, aliases: Sequence[str]) -> Optional[str]:
    present, value = _present_value(source, aliases)
    if not present:
        return None
    text = str(value or "").strip()
    return text or None


def _parse_provider_datetime(
    provider_date: Optional[str],
    provider_time: Optional[str],
    *,
    received_at: datetime,
) -> tuple[Optional[datetime], bool]:
    """Parse comparable provider time without inventing a provider date.

    A time-only V3 room message may be safely attributed to the local receipt
    date only while both the receipt and provider clock fall in an active
    Vietnam trading/auction window. The returned boolean records that bounded
    attribution rather than presenting it as a provider-supplied date.
    """

    text = str(provider_time or "").strip()
    if not text:
        return None, False
    parsed: Optional[datetime] = None
    provider_time_includes_date = bool(
        re.match(r"^\d{4}[-/]\d{2}[-/]\d{2}[ T]", text)
    )
    try:
        if "T" in text or " " in text:
            parsed = datetime.fromisoformat(
                text.replace("/", "-").replace("Z", "+00:00")
            )
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=VN_TIMEZONE)
            else:
                parsed = parsed.astimezone(VN_TIMEZONE)
        else:
            parsed_time = datetime.strptime(text, "%H:%M:%S").time()
            base_date = (
                datetime.fromisoformat(provider_date).date()
                if provider_date
                else received_at.date()
            )
            parsed = datetime.combine(base_date, parsed_time, tzinfo=VN_TIMEZONE)
    except (TypeError, ValueError):
        return None, False
    if provider_date or provider_time_includes_date:
        return parsed, False
    receipt_session = vietnam_market_session_from_epoch(received_at.timestamp())
    event_session = vietnam_market_session_from_epoch(parsed.timestamp())
    safely_attributed = bool(
        receipt_session.get("market_session_active")
        and event_session.get("market_session_active")
        and parsed.date() == received_at.date()
    )
    return parsed, safely_attributed


def classify_delay(delay_seconds: Optional[float]) -> str:
    if delay_seconds is None or not math.isfinite(delay_seconds) or delay_seconds < 0:
        return "unknown"
    if delay_seconds <= DELAY_NEAR_REALTIME_SECONDS:
        return "near_realtime"
    if delay_seconds <= DELAY_MATERIAL_SECONDS:
        return "delayed"
    return "materially_delayed"


def room_sample_from_message(
    message: Any,
    *,
    received_at: datetime,
    sample_number: int,
) -> dict[str, Any]:
    """Normalize one complete V3 room snapshot candidate without accumulation."""

    envelope = message if isinstance(message, Mapping) else {}
    topic = str(envelope.get("topic") or "").strip().lower()
    data = envelope.get("data") if topic else message
    if isinstance(data, list):
        if len(data) != 1:
            raise ValueError("room evidence requires one payload per callback")
        data = data[0]
    if topic and not topic.startswith("room."):
        raise ValueError("non-room topic received by room diagnostic")
    typed_message = None
    if isinstance(data, Mapping):
        from ssi_sdk.models import ForeignRoomMessage

        typed_message = ForeignRoomMessage.from_dict(dict(data))
    symbol = _text_value(data, ("s", "symbol", "Symbol"))
    if not symbol:
        raise ValueError("room message symbol is missing")
    symbol = symbol.upper()
    if typed_message is not None and typed_message.symbol.upper() != symbol:
        raise ValueError("typed room-message symbol mismatch")
    provider_date = _text_value(
        data, ("td", "trading_date", "TradingDate", "date")
    )
    provider_time = _text_value(
        data, ("t", "trading_time", "TradingTime", "time")
    )
    provider_dt, receipt_date_attributed = _parse_provider_datetime(
        provider_date,
        provider_time,
        received_at=received_at,
    )
    delay_seconds = (
        max(0.0, (received_at - provider_dt).total_seconds())
        if provider_dt is not None and provider_dt <= received_at
        else None
    )

    flow_fields: dict[str, dict[str, Any]] = {}
    for normalized, aliases in ROOM_FLOW_ALIASES.items():
        present, value = _present_value(data, aliases)
        flow_fields[normalized] = classify_numeric(value, present=present)
    flow_fields["foreign_net_volume"] = _derive_net(
        flow_fields["foreign_buy_volume"], flow_fields["foreign_sell_volume"]
    )
    flow_fields["foreign_net_value"] = _derive_net(
        flow_fields["foreign_buy_value"], flow_fields["foreign_sell_value"]
    )
    room_capacity: dict[str, dict[str, Any]] = {}
    for normalized, aliases in ROOM_CAPACITY_ALIASES.items():
        present, value = _present_value(data, aliases)
        room_capacity[normalized] = classify_numeric(value, present=present)

    provider_time_includes_date = bool(
        re.match(r"^\d{4}[-/]\d{2}[-/]\d{2}[ T]", str(provider_time or ""))
    )
    effective_date = provider_date or (
        provider_dt.date().isoformat()
        if provider_dt is not None and provider_time_includes_date
        else received_at.date().isoformat()
        if receipt_date_attributed
        else None
    )
    return {
        "source": "SSI_V3_FOREIGN_ROOM_STREAM",
        "channel": topic or f"room.{symbol}",
        "sdk_message_class": "ForeignRoomMessage",
        "sdk_typed_decoded": typed_message is not None,
        "symbol": symbol,
        "sample_number": sample_number,
        "provider_session_date": effective_date,
        "provider_date_supplied": bool(provider_date or provider_time_includes_date),
        "receipt_date_attributed": receipt_date_attributed,
        "provider_event_time": provider_time,
        "provider_event_at": (
            provider_dt.isoformat(timespec="seconds") if provider_dt else None
        ),
        "received_at": received_at.isoformat(timespec="seconds"),
        "delay_ms": round(delay_seconds * 1000) if delay_seconds is not None else None,
        "delay_classification": classify_delay(delay_seconds),
        "room_capacity": room_capacity,
        "fields": flow_fields,
        "volume_unit": SSI_V3_FOREIGN_VOLUME_UNIT,
        "value_unit": SSI_V3_FOREIGN_VALUE_UNIT,
        "snapshot_handling": "replace_previous_never_accumulate",
        "finality": "current_provisional",
    }


def _numeric_values(sample: Mapping[str, Any], fields: Iterable[str]) -> tuple[Any, ...]:
    sample_fields = sample.get("fields")
    mapping = sample_fields if isinstance(sample_fields, Mapping) else {}
    return tuple(
        (mapping.get(field) or {}).get("value")
        if isinstance(mapping.get(field), Mapping)
        else None
        for field in fields
    )


def classify_sample_changes(samples: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    changes: dict[str, list[str]] = {field: [] for field in GROSS_FIELDS}
    for previous, current in zip(samples, samples[1:]):
        previous_values = dict(zip(GROSS_FIELDS, _numeric_values(previous, GROSS_FIELDS)))
        current_values = dict(zip(GROSS_FIELDS, _numeric_values(current, GROSS_FIELDS)))
        for field in GROSS_FIELDS:
            left = previous_values[field]
            right = current_values[field]
            if left is None or right is None:
                changes[field].append("unknown")
            elif float(right) > float(left):
                changes[field].append("increased")
            elif float(right) < float(left):
                changes[field].append("decreased")
            else:
                changes[field].append("equal")
    flattened = [state for states in changes.values() for state in states]
    return {
        "by_field": changes,
        "any_increase": "increased" in flattened,
        "any_decrease": "decreased" in flattened,
        "all_observed_equal": bool(flattened)
        and all(state in {"equal", "unknown"} for state in flattened)
        and "equal" in flattened,
    }


def evaluate_daily_stock_price_samples(
    samples: Sequence[Mapping[str, Any]],
    *,
    expected_session_date: str,
) -> dict[str, Any]:
    current = [
        sample
        for sample in samples
        if sample.get("provider_session_date") == expected_session_date
        and bool(sample.get("current_date_row"))
    ]
    changes = classify_sample_changes(current)
    volume_complete = any(
        all(value is not None for value in _numeric_values(sample, VOLUME_FIELDS))
        for sample in current
    )
    value_complete = any(
        all(value is not None for value in _numeric_values(sample, VALUE_FIELDS))
        for sample in current
    )
    observed_values = [
        value
        for sample in current
        for value in _numeric_values(sample, GROSS_FIELDS)
        if value is not None
    ]
    zero_only = bool(observed_values) and all(float(value) == 0 for value in observed_values)
    timestamp_known = any(bool(sample.get("provider_event_timestamp")) for sample in current)
    if not current:
        candidate_status = "inconclusive"
        gate_status = "inconclusive"
        reason = "no current-date provider row observed"
    elif not (volume_complete or value_complete):
        candidate_status = "inconclusive"
        gate_status = "inconclusive"
        reason = "no complete explicit foreign buy/sell pair observed"
    elif zero_only:
        candidate_status = "inconclusive"
        gate_status = "inconclusive"
        reason = "zero-only samples do not prove an active cumulative source"
    elif len(current) < 2:
        candidate_status = "inconclusive"
        gate_status = "inconclusive"
        reason = "one current-date sample cannot prove update semantics"
    elif changes["any_increase"] or changes["any_decrease"]:
        candidate_status = "candidate_found"
        gate_status = "provider_contract_blocked"
        reason = (
            "explicit current-date fields changed, but provider timestamp, "
            "snapshot/delta, reset, and reconciliation gates remain unresolved"
        )
    else:
        candidate_status = "inconclusive"
        gate_status = "inconclusive"
        reason = "unchanged samples do not prove current-session updates"
    return {
        "candidate_status": candidate_status,
        "gate_status": gate_status,
        "reason": reason,
        "sample_count": len(samples),
        "current_date_sample_count": len(current),
        "volume_pair_observed": volume_complete,
        "value_pair_observed": value_complete,
        "zero_only": zero_only,
        "provider_timestamp_known": timestamp_known,
        "snapshot_delta": "unknown",
        "cumulative_behavior": (
            "counter_change_observed_semantics_unproven"
            if changes["any_increase"] or changes["any_decrease"]
            else "not_proven"
        ),
        "counter_decrease_behavior": (
            "correction_or_reset_candidate" if changes["any_decrease"] else "not_observed"
        ),
        "session_reset": "pending",
        "reconnect_replay": "not_applicable_rest",
        "reconciliation": "pending",
        "changes": changes,
    }


def select_latest_room_snapshot(
    samples: Sequence[Mapping[str, Any]],
) -> Optional[Mapping[str, Any]]:
    """Return the latest complete candidate; snapshots are never summed."""

    return samples[-1] if samples else None


def evaluate_room_samples(
    samples: Sequence[Mapping[str, Any]],
    *,
    expected_session_date: str,
) -> dict[str, Any]:
    current = [
        sample
        for sample in samples
        if sample.get("provider_session_date") == expected_session_date
    ]
    changes = classify_sample_changes(current)
    volume_complete = any(
        all(value is not None for value in _numeric_values(sample, VOLUME_FIELDS))
        for sample in current
    )
    value_complete = any(
        all(value is not None for value in _numeric_values(sample, VALUE_FIELDS))
        for sample in current
    )
    observed_values = [
        value
        for sample in current
        for value in _numeric_values(sample, GROSS_FIELDS)
        if value is not None
    ]
    zero_only = bool(observed_values) and all(float(value) == 0 for value in observed_values)
    any_nonzero = any(float(value) != 0 for value in observed_values)
    replay_count = 0
    for previous, current_sample in zip(current, current[1:]):
        if _numeric_values(previous, GROSS_FIELDS) == _numeric_values(
            current_sample, GROSS_FIELDS
        ):
            replay_count += 1
    delay_labels = [
        str(sample.get("delay_classification") or "unknown") for sample in current
    ]
    if "materially_delayed" in delay_labels:
        delay_classification = "materially_delayed"
    elif "delayed" in delay_labels:
        delay_classification = "delayed"
    elif "near_realtime" in delay_labels:
        delay_classification = "near_realtime"
    else:
        delay_classification = "unknown"

    if not current:
        candidate_status = "active_session_pending"
        gate_status = "inconclusive"
        reason = "no safely attributable current-session room message observed"
        snapshot_delta = "unknown"
    elif not (volume_complete or value_complete):
        candidate_status = "inconclusive"
        gate_status = "inconclusive"
        reason = "room capacity was observed without a complete explicit buy/sell pair"
        snapshot_delta = "point_snapshot"
    elif zero_only:
        candidate_status = "inconclusive"
        gate_status = "inconclusive"
        reason = "explicit zero-only counters do not prove active update behavior"
        snapshot_delta = "cumulative_snapshot_candidate"
    elif changes["any_decrease"]:
        candidate_status = "candidate_found"
        gate_status = "passed"
        reason = "explicit current-session counters observed; decrease retained as correction/reset candidate"
        snapshot_delta = "correction_or_reset_candidate"
    elif changes["any_increase"]:
        candidate_status = "candidate_found"
        gate_status = "passed"
        reason = "changing current-session counters support cumulative snapshot behavior"
        snapshot_delta = "cumulative_snapshot_observed"
    elif any_nonzero:
        candidate_status = "candidate_found"
        gate_status = "passed"
        reason = "static nonzero current-session counters are a cumulative snapshot candidate"
        snapshot_delta = "cumulative_snapshot_candidate"
    else:
        candidate_status = "inconclusive"
        gate_status = "inconclusive"
        reason = "room message semantics remain unresolved"
        snapshot_delta = "unknown"

    return {
        "candidate_status": candidate_status,
        "gate_status": gate_status,
        "reason": reason,
        "sample_count": len(samples),
        "current_date_sample_count": len(current),
        "volume_pair_observed": volume_complete,
        "value_pair_observed": value_complete,
        "zero_only": zero_only,
        "provider_timestamp_known": any(
            bool(sample.get("provider_event_time")) for sample in current
        ),
        "snapshot_delta": snapshot_delta,
        "cumulative_behavior": snapshot_delta,
        "counter_decrease_behavior": (
            "correction_or_reset_candidate" if changes["any_decrease"] else "not_observed"
        ),
        "counter_movement": (
            "mixed"
            if changes["any_increase"] and changes["any_decrease"]
            else "decreased"
            if changes["any_decrease"]
            else "increased"
            if changes["any_increase"]
            else "equal"
            if changes["all_observed_equal"]
            else "not_observed"
        ),
        "delay_classification": delay_classification,
        "session_reset": "next_session_reset_pending",
        "reconnect_replay": "pending",
        "replay_count": replay_count,
        "local_accumulation": False,
        "latest_snapshot": select_latest_room_snapshot(current),
        "reconciliation": "reconciliation_pending",
        "accepted_daily_authority": "DailyStockPrice",
        "changes": changes,
    }


def evaluate_semantic_gate(
    *,
    snapshot_delta: str,
    cumulative_behavior_observed: bool = False,
    stable_event_sequence: bool = False,
    reconnect_replay_known: bool = False,
) -> dict[str, str]:
    """Evaluate only the snapshot/delta sub-gate without inferring semantics."""

    normalized = str(snapshot_delta or "").strip().lower()
    if normalized == "cumulative_snapshot":
        if cumulative_behavior_observed:
            return {"status": "passed", "reason": "known cumulative snapshot behavior"}
        return {"status": "pending", "reason": "cumulative behavior not observed"}
    if normalized == "delta_event":
        if stable_event_sequence and reconnect_replay_known:
            return {"status": "passed", "reason": "delta accumulation can be idempotent"}
        return {
            "status": "failed",
            "reason": "delta source lacks stable sequence or reconnect/replay proof",
        }
    return {"status": "inconclusive", "reason": "snapshot/delta semantics unknown"}


def reconcile_evidence(
    provisional: Mapping[str, Any],
    accepted: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare sanitized like-for-like rows while keeping accepted daily authoritative."""

    for key in ("symbol", "provider_session_date"):
        if provisional.get(key) != accepted.get(key):
            raise ValueError(f"{key} mismatch")
    for key in ("volume_unit", "value_unit"):
        if provisional.get(key) != accepted.get(key):
            raise ValueError(f"{key} mismatch")
    provisional_fields = provisional.get("fields")
    accepted_fields = accepted.get("fields")
    if not isinstance(provisional_fields, Mapping) or not isinstance(accepted_fields, Mapping):
        raise ValueError("reconciliation fields are required")
    comparisons: dict[str, Any] = {}
    for field in ALL_AUDITED_FIELDS:
        left = provisional_fields.get(field)
        right = accepted_fields.get(field)
        provisional_value = left.get("value") if isinstance(left, Mapping) else None
        accepted_value = right.get("value") if isinstance(right, Mapping) else None
        if provisional_value is None or accepted_value is None:
            absolute = None
            percentage = None
        else:
            absolute = float(provisional_value) - float(accepted_value)
            percentage = (
                None
                if float(accepted_value) == 0
                else absolute / abs(float(accepted_value)) * 100
            )
        comparisons[field] = {
            "provisional_value": provisional_value,
            "accepted_daily_value": accepted_value,
            "absolute_difference": absolute,
            "percentage_difference": percentage,
        }
    return {
        "symbol": provisional["symbol"],
        "provider_session_date": provisional["provider_session_date"],
        "accepted_daily_authoritative": True,
        "provisional_remains_separate": True,
        "comparisons": comparisons,
    }


def evidence_matrix(
    daily: Mapping[str, Any],
    room: Optional[Mapping[str, Any]] = None,
) -> dict[str, dict[str, str]]:
    pending = "pending"
    failed = "failed"
    daily_gate = str(daily.get("gate_status") or "inconclusive")
    if daily_gate not in {
        "passed",
        "failed",
        "pending",
        "not_applicable",
        "inconclusive",
    }:
        daily_gate = "inconclusive"
    daily_current = (
        "passed" if int(daily.get("current_date_sample_count") or 0) > 0 else "pending"
    )
    daily_explicit = (
        "passed"
        if bool(daily.get("volume_pair_observed") or daily.get("value_pair_observed"))
        else "pending"
    )
    room_result = room or {}
    room_current = (
        "passed"
        if int(room_result.get("current_date_sample_count") or 0) > 0
        else "pending"
    )
    room_explicit = (
        "passed"
        if bool(
            room_result.get("volume_pair_observed")
            or room_result.get("value_pair_observed")
        )
        else "pending"
    )
    room_gate = str(room_result.get("gate_status") or "pending")
    if room_gate not in {"passed", "failed", "pending", "inconclusive"}:
        room_gate = "inconclusive"
    return {
        "official_ssi_v3_source": {
            "daily_stock_price": "passed",
            "x": "passed",
            "x_quote": "passed",
            "x_trade": "passed",
            "r": "passed",
            "f": "passed",
            "mi": "passed",
        },
        "explicit_buy_sell_fields": {
            "daily_stock_price": daily_explicit,
            "x": failed,
            "x_quote": failed,
            "x_trade": failed,
            "r": room_explicit,
            "f": failed,
            "mi": failed,
        },
        "volume_unit_known": {
            "daily_stock_price": "passed",
            "x": failed,
            "x_quote": failed,
            "x_trade": failed,
            "r": room_explicit,
            "f": failed,
            "mi": failed,
        },
        "value_unit_known": {
            "daily_stock_price": "passed",
            "x": failed,
            "x_quote": failed,
            "x_trade": failed,
            "r": room_explicit,
            "f": failed,
            "mi": failed,
        },
        "current_session_identity": {
            "daily_stock_price": daily_current,
            "x": pending,
            "x_quote": pending,
            "x_trade": pending,
            "r": room_current,
            "f": "passed",
            "mi": pending,
        },
        "provider_timestamp": {
            "daily_stock_price": (
                "passed" if daily.get("provider_timestamp_known") else pending
            ),
            "x": "passed",
            "x_quote": "passed",
            "x_trade": "passed",
            "r": "passed",
            "f": pending,
            "mi": pending,
        },
        "snapshot_delta_known": {
            "daily_stock_price": pending,
            "x": pending,
            "x_quote": pending,
            "x_trade": "passed",
            "r": pending,
            "f": "not_applicable",
            "mi": pending,
        },
        "session_reset": {
            source: (
                pending
                if source == "r"
                else "not_applicable"
                if source in {"x", "x_quote", "x_trade", "f", "mi"}
                else pending
            )
            for source in CANDIDATES
        },
        "reconnect_replay": {
            "daily_stock_price": "not_applicable",
            "x": pending,
            "x_quote": pending,
            "x_trade": pending,
            "r": pending,
            "f": pending,
            "mi": pending,
        },
        "post_close_reconciliation": {
            source: ("pending" if source == "daily_stock_price" else "not_applicable")
            for source in CANDIDATES
        },
        "ticker_level_authority": {
            "daily_stock_price": pending,
            "x": failed,
            "x_quote": failed,
            "x_trade": failed,
            "r": room_explicit,
            "f": failed,
            "mi": failed,
        },
        "final_gate_result": {
            "daily_stock_price": daily_gate,
            "x": failed,
            "x_quote": failed,
            "x_trade": failed,
            "r": room_gate,
            "f": failed,
            "mi": failed,
        },
    }


class Emitter:
    def __init__(self, output_format: str) -> None:
        self.output_format = output_format
        self.events: list[dict[str, Any]] = []

    def emit(self, event: str, **values: Any) -> None:
        item = {"event": event, **values}
        if self.output_format == "jsonl":
            print(json.dumps(item, separators=(",", ":"), sort_keys=True), flush=True)
        else:
            self.events.append(item)

    def finish(self) -> None:
        if self.output_format == "json":
            print(json.dumps(self.events, separators=(",", ":"), sort_keys=True), flush=True)


def _failure_class(result: Mapping[str, Any]) -> Optional[str]:
    failure = str(result.get("failure_class") or "").strip().lower()
    return failure if failure in _SAFE_FAILURE_CLASSES else ("unknown" if failure else None)


def _current_row(result: Mapping[str, Any], session_date: str) -> Optional[Mapping[str, Any]]:
    rows = result.get("rows")
    if not isinstance(rows, list):
        return None
    return next(
        (
            row
            for row in reversed(rows)
            if isinstance(row, Mapping)
            and str(row.get("date") or row.get("trading_date") or "") == session_date
        ),
        None,
    )


def _runtime_request_timeout(options: argparse.Namespace) -> int:
    sleep_budget = max(0, (options.sample_count - 1) * options.interval_seconds)
    logical_calls = max(1, options.sample_count * len(options.symbols) + 1)
    remaining = max(1, options.max_runtime_seconds - sleep_budget - 5)
    return max(1, min(10, remaining // logical_calls))


def _load_reconciliation(path: Path) -> dict[str, Any]:
    if path.stat().st_size > 128 * 1024:
        raise ValueError("reconciliation evidence exceeds 128 KiB")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("reconciliation evidence must be an object")
    provisional = payload.get("provisional")
    accepted = payload.get("accepted")
    if not isinstance(provisional, Mapping) or not isinstance(accepted, Mapping):
        raise ValueError("reconciliation evidence requires provisional and accepted")
    return reconcile_evidence(provisional, accepted)


def _stream_failure_class(value: Any) -> str:
    text = str(value or "").lower()
    if any(token in text for token in ("401", "unauthenticated", "authentication")):
        return "authentication"
    if any(token in text for token in ("403", "unauthorized", "authorization", "forbidden")):
        return "authorization"
    if "rate" in text and "limit" in text:
        return "rate_limited"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if any(token in text for token in ("dns", "name resolution", "getaddrinfo")):
        return "network_error"
    return "provider_unavailable"


def _write_sanitized_evidence(
    directory: Path,
    samples: Sequence[Mapping[str, Any]],
    evaluation: Mapping[str, Any],
) -> Path:
    safe_root = (ROOT / ".tmp" / "current-foreign-flow").resolve()
    requested = (directory if directory.is_absolute() else ROOT / directory).resolve()
    if requested != safe_root and safe_root not in requested.parents:
        raise ValueError("sanitized evidence must stay under .tmp/current-foreign-flow")
    requested.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(VN_TIMEZONE).strftime("%Y%m%dT%H%M%S")
    path = requested / f"ssi-v3-room-{stamp}.json"
    payload = {
        "source": "SSI_V3_FOREIGN_ROOM_STREAM",
        "samples": list(samples),
        "evaluation": {
            key: evaluation.get(key)
            for key in (
                "candidate_status",
                "gate_status",
                "snapshot_delta",
                "counter_movement",
                "delay_classification",
                "reconciliation",
                "session_reset",
                "local_accumulation",
                "accepted_daily_authority",
            )
        },
    }
    path.write_text(
        json.dumps(payload, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    return path


def _run_room_stream(
    options: argparse.Namespace,
    *,
    emitter: Emitter,
    started: float,
    deadline: float,
    settings: SsiV3RestSettings,
    session_date: str,
) -> tuple[int, dict[str, Any]]:
    incoming: queue.Queue[tuple[str, Any, datetime]] = queue.Queue()
    opened_channels: set[str] = set()
    samples_by_symbol: dict[str, list[dict[str, Any]]] = {
        symbol: [] for symbol in options.symbols
    }
    baseline_thread_ids = {
        thread.ident for thread in threading.enumerate() if thread.ident is not None
    }
    client: Optional[OfficialSsiV3RealtimeStreamClient] = None
    failure_class: Optional[str] = None
    authentication_status = "pending"
    subscription_count = 0

    def on_message(message: Any) -> None:
        incoming.put(("message", message, datetime.now(VN_TIMEZONE)))

    def on_error(error: Any) -> None:
        incoming.put(("error", error, datetime.now(VN_TIMEZONE)))

    def on_open(channel: str) -> None:
        incoming.put(("open", channel, datetime.now(VN_TIMEZONE)))

    def on_subscription_error(channel: str, error: Any) -> None:
        incoming.put(
            (
                "subscription_error",
                {"channel": channel, "error": error},
                datetime.now(VN_TIMEZONE),
            )
        )

    try:
        client = OfficialSsiV3RealtimeStreamClient(
            replace(settings, max_retries=0)
        )
        subscription_count = 1
        client.start(
            on_message,
            on_error,
            [f"R:{symbol}" for symbol in options.symbols],
            on_open=on_open,
            on_subscription_error=on_subscription_error,
        )
        while time.monotonic() < deadline:
            if all(
                len(samples_by_symbol[symbol]) >= options.sample_count
                for symbol in options.symbols
            ):
                break
            remaining = max(0.0, deadline - time.monotonic())
            try:
                kind, payload, received_at = incoming.get(timeout=min(1.0, remaining))
            except queue.Empty:
                continue
            if kind == "open":
                opened_channels.add(str(payload))
                authentication_status = "ok"
                emitter.emit("subscription", status="ok", channel=str(payload))
                continue
            if kind in {"error", "subscription_error"}:
                error = payload.get("error") if isinstance(payload, Mapping) else payload
                failure_class = _stream_failure_class(error)
                if failure_class in {"authentication", "authorization"}:
                    authentication_status = "unavailable"
                emitter.emit(
                    "stream_error",
                    status="unavailable",
                    failure_class=failure_class,
                    reason=sanitize_text(error),
                )
                break
            try:
                sample = room_sample_from_message(
                    payload,
                    received_at=received_at,
                    sample_number=(
                        len(
                            samples_by_symbol.get(
                                _text_value(
                                    (
                                        payload.get("data")
                                        if isinstance(payload, Mapping)
                                        else payload
                                    ),
                                    ("s", "symbol", "Symbol"),
                                )
                                or "",
                                [],
                            )
                        )
                        + 1
                    ),
                )
            except (TypeError, ValueError) as exc:
                emitter.emit(
                    "sample",
                    source="SSI_V3_FOREIGN_ROOM_STREAM",
                    status="rejected",
                    failure_class="malformed_response",
                    reason=sanitize_text(exc),
                )
                continue
            symbol = sample["symbol"]
            if symbol not in samples_by_symbol:
                continue
            if len(samples_by_symbol[symbol]) >= options.sample_count:
                continue
            samples_by_symbol[symbol].append(sample)
            emitter.emit("sample", status="ok", **sample)
    finally:
        if client is not None:
            client.stop()

    evaluations = {
        symbol: evaluate_room_samples(samples, expected_session_date=session_date)
        for symbol, samples in samples_by_symbol.items()
    }
    for symbol, evaluation in evaluations.items():
        emitter.emit("evaluation", source="r", symbol=symbol, **evaluation)
    best = next(
        (
            evaluation
            for evaluation in evaluations.values()
            if evaluation.get("candidate_status") == "candidate_found"
        ),
        None,
    )
    matrix_source = best or next(iter(evaluations.values()))
    emitter.emit("evidence_matrix", cells=evidence_matrix({}, matrix_source))

    evidence_path: Optional[str] = None
    all_samples = [
        sample for symbol_samples in samples_by_symbol.values() for sample in symbol_samples
    ]
    if options.save_sanitized_evidence is not None and all_samples:
        try:
            saved = _write_sanitized_evidence(
                options.save_sanitized_evidence, all_samples, matrix_source
            )
            evidence_path = str(saved.relative_to(ROOT))
            emitter.emit("evidence_saved", path=evidence_path, sanitized=True)
        except (OSError, ValueError) as exc:
            emitter.emit(
                "evidence_saved",
                status="rejected",
                failure_class="configuration",
                reason=sanitize_text(exc),
            )

    new_owned_threads = [
        thread.name
        for thread in threading.enumerate()
        if thread.ident is not None
        and thread.ident not in baseline_thread_ids
        and (
            "ssi" in thread.name.lower()
            or "websocket" in thread.name.lower()
        )
    ]
    if best is None:
        primary = "M2_6A_R1_V3_FOREIGN_ROOM_CANDIDATE_FOUND_ACTIVE_SESSION_PENDING"
        gate = "active_session_pending"
    elif best.get("delay_classification") in {"delayed", "materially_delayed"}:
        primary = "M2_6A_R1_V3_FOREIGN_ROOM_DELAYED_FLOW_CANDIDATE_PROVEN"
        gate = "passed"
    elif best.get("delay_classification") == "near_realtime":
        primary = "M2_6A_R1_V3_FOREIGN_ROOM_CURRENT_FLOW_CANDIDATE_PROVEN"
        gate = "passed"
    else:
        primary = "M2_6A_R1_V3_FOREIGN_ROOM_FIELDS_PRESENT_SEMANTICS_BLOCKED"
        gate = "provider_contract_blocked"
    result = {
        "primary_outcome": primary,
        "gate_status": gate,
        "failure_class": failure_class,
        "provider_request_count": 0,
        "provider_subscription_count": subscription_count,
        "provider_event_count": len(all_samples),
        "opened_channel_count": len(opened_channels),
        "authentication_status": authentication_status,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "client_closed": True,
        "surviving_owned_threads": len(new_owned_threads),
        "evidence_path": evidence_path,
    }
    emitter.emit("final", **result)
    return (0 if failure_class is None else 2), result


def run(options: argparse.Namespace) -> int:
    started = time.monotonic()
    deadline = started + options.max_runtime_seconds
    emitter = Emitter(options.output_format)
    now = datetime.now(VN_TIMEZONE)
    session = vietnam_market_session_from_epoch(now.timestamp())
    emitter.emit(
        "runtime",
        sdk_package="ssi-sdk",
        sdk_version=importlib.metadata.version("ssi-sdk"),
        mode="live" if options.allow_live else "offline",
        vietnam_time=now.isoformat(timespec="seconds"),
        market_session=session.get("market_session"),
        market_session_active=bool(session.get("market_session_active")),
        max_runtime_seconds=options.max_runtime_seconds,
    )
    for candidate in candidate_inventory(options.candidate_sources):
        emitter.emit("candidate", **candidate)

    if options.reconcile_evidence is not None:
        try:
            reconciliation = _load_reconciliation(options.reconcile_evidence)
            emitter.emit("reconciliation", status="compared", **reconciliation)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            emitter.emit(
                "reconciliation",
                status="rejected",
                failure_class="malformed_response",
                reason=sanitize_text(exc),
            )

    if not options.allow_live:
        emitter.emit(
            "final",
            primary_outcome="offline_inventory_only",
            gate_status="active_session_pending",
            provider_request_count=0,
            provider_event_count=0,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            client_closed=True,
            surviving_owned_threads=0,
        )
        emitter.finish()
        return 0
    if not bool(session.get("market_session_active")):
        emitter.emit(
            "final",
            primary_outcome=(
                "M2_6A_R1_V3_FOREIGN_ROOM_CANDIDATE_FOUND_ACTIVE_SESSION_PENDING"
                if "r" in options.candidate_sources
                else "M2_6A_CURRENT_SESSION_FOREIGN_FLOW_ACTIVE_SESSION_PENDING"
            ),
            gate_status="active_session_pending",
            provider_request_count=0,
            provider_event_count=0,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            client_closed=True,
            surviving_owned_threads=0,
        )
        emitter.finish()
        return 0

    daily_selected = "daily_stock_price" in options.candidate_sources
    room_selected = "r" in options.candidate_sources
    if not daily_selected and not room_selected:
        emitter.emit(
            "final",
            primary_outcome="M2_6A_CURRENT_SESSION_FOREIGN_FLOW_NO_VERIFIED_SOURCE",
            gate_status="failed",
            provider_request_count=0,
            provider_event_count=0,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            client_closed=True,
            surviving_owned_threads=0,
        )
        emitter.finish()
        return 0

    setup_env()
    Config.reset_instance()
    settings = SsiV3RestSettings.from_config(get_config())
    if not settings.enabled or settings.missing_required_names:
        emitter.emit(
            "final",
            primary_outcome="M2_6A_CURRENT_SESSION_FOREIGN_FLOW_PROVIDER_CONTRACT_BLOCKED",
            gate_status="provider_contract_blocked",
            failure_class=(
                "credentials_missing" if settings.missing_required_names else "configuration"
            ),
            provider_request_count=0,
            provider_event_count=0,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            client_closed=True,
            surviving_owned_threads=0,
        )
        emitter.finish()
        return 2

    bounded_settings = replace(
        settings,
        request_timeout=min(settings.request_timeout, _runtime_request_timeout(options)),
        max_retries=0,
    )
    if room_selected:
        try:
            code, _result = _run_room_stream(
                options,
                emitter=emitter,
                started=started,
                deadline=deadline,
                settings=bounded_settings,
                session_date=now.date().isoformat(),
            )
            return code
        finally:
            emitter.finish()

    adapter: Optional[SsiFastConnectV3Adapter] = None
    samples: list[dict[str, Any]] = []
    request_count = 0
    failure_class: Optional[str] = None
    try:
        adapter = SsiFastConnectV3Adapter(bounded_settings)
        authentication = adapter.initialize_rest_access()
        if authentication.get("status") != "ok":
            failure_class = _failure_class(authentication) or "authentication"
            emitter.emit(
                "authentication",
                status="unavailable",
                failure_class=failure_class,
            )
        else:
            emitter.emit("authentication", status="ok", failure_class=None)
            session_date = now.date().isoformat()
            for sample_number in range(1, options.sample_count + 1):
                if failure_class is not None or time.monotonic() >= deadline:
                    break
                for symbol in options.symbols:
                    if time.monotonic() >= deadline:
                        failure_class = "timeout"
                        break
                    request_count += 1
                    result = adapter.get_daily_stock_price(
                        symbol,
                        market="HOSE",
                        from_date=session_date,
                        to_date=session_date,
                        limit=1,
                    )
                    if result.get("status") != "ok":
                        failure_class = _failure_class(result) or "provider_unavailable"
                        emitter.emit(
                            "sample",
                            source="daily_stock_price",
                            symbol=symbol,
                            sample_number=sample_number,
                            status="unavailable",
                            failure_class=failure_class,
                        )
                        if failure_class in STOP_FAILURE_CLASSES:
                            break
                        continue
                    sampled_at = datetime.now(VN_TIMEZONE).isoformat(timespec="seconds")
                    sample = sample_from_row(
                        _current_row(result, session_date),
                        symbol=symbol,
                        sample_number=sample_number,
                        sampled_at=sampled_at,
                        expected_session_date=session_date,
                    )
                    samples.append(sample)
                    emitter.emit("sample", status="ok", **sample)
                if (
                    sample_number < options.sample_count
                    and failure_class not in STOP_FAILURE_CLASSES
                ):
                    remaining = max(0.0, deadline - time.monotonic())
                    if remaining <= 0:
                        failure_class = "timeout"
                        break
                    time.sleep(min(float(options.interval_seconds), remaining))

        session_date = now.date().isoformat()
        evaluations = {
            symbol: evaluate_daily_stock_price_samples(
                [sample for sample in samples if sample["symbol"] == symbol],
                expected_session_date=session_date,
            )
            for symbol in options.symbols
        }
        for symbol, evaluation in evaluations.items():
            emitter.emit("evaluation", symbol=symbol, **evaluation)
        best = next(
            (
                evaluation
                for evaluation in evaluations.values()
                if evaluation["candidate_status"] == "candidate_found"
            ),
            None,
        )
        if failure_class in STOP_FAILURE_CLASSES:
            primary = "M2_6A_CURRENT_SESSION_FOREIGN_FLOW_PROVIDER_CONTRACT_BLOCKED"
            gate = "provider_contract_blocked"
        elif best is not None:
            primary = "M2_6A_CURRENT_SESSION_FOREIGN_FLOW_PROVIDER_CONTRACT_BLOCKED"
            gate = "provider_contract_blocked"
        else:
            primary = "M2_6A_CURRENT_SESSION_FOREIGN_FLOW_NO_VERIFIED_SOURCE"
            gate = "inconclusive"
        matrix_source = best or next(iter(evaluations.values()))
        emitter.emit("evidence_matrix", cells=evidence_matrix(matrix_source))
        emitter.emit(
            "final",
            primary_outcome=primary,
            gate_status=gate,
            failure_class=failure_class,
            provider_request_count=request_count,
            provider_event_count=0,
            elapsed_ms=int((time.monotonic() - started) * 1000),
            client_closed=True,
            surviving_owned_threads=0,
        )
        return 0 if failure_class is None else 2
    finally:
        if adapter is not None:
            adapter.close()
        emitter.finish()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bounded SSI V3 current-session foreign-flow evidence gate"
    )
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--sample-count", type=int, default=DEFAULT_SAMPLE_COUNT)
    parser.add_argument(
        "--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS
    )
    parser.add_argument(
        "--max-runtime-seconds", type=int, default=DEFAULT_MAX_RUNTIME_SECONDS
    )
    parser.add_argument(
        "--candidate-sources", default=",".join(DEFAULT_SOURCES)
    )
    parser.add_argument("--output-format", choices=("jsonl", "json"), default="jsonl")
    parser.add_argument("--reconcile-evidence", type=Path)
    parser.add_argument(
        "--save-sanitized-evidence",
        nargs="?",
        type=Path,
        const=Path(".tmp/current-foreign-flow"),
    )
    return parser


def parse_options(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    options = build_parser().parse_args(argv)
    try:
        options.symbols = parse_symbols(options.symbols)
        options.candidate_sources = parse_sources(options.candidate_sources)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if not MIN_SAMPLES <= options.sample_count <= MAX_SAMPLES:
        raise SystemExit(
            f"sample-count must be between {MIN_SAMPLES} and {MAX_SAMPLES}"
        )
    if not MIN_INTERVAL_SECONDS <= options.interval_seconds <= MAX_INTERVAL_SECONDS:
        raise SystemExit(
            f"interval-seconds must be between {MIN_INTERVAL_SECONDS} and "
            f"{MAX_INTERVAL_SECONDS}"
        )
    if not 1 <= options.max_runtime_seconds <= MAX_RUNTIME_SECONDS:
        raise SystemExit(
            f"max-runtime-seconds must be between 1 and {MAX_RUNTIME_SECONDS}"
        )
    return options


def main(argv: Optional[Sequence[str]] = None) -> int:
    return run(parse_options(argv))


if __name__ == "__main__":
    raise SystemExit(main())
