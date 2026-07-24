"""StockClock's validated SSI V3 foreign-flow normalization policy.

SSI's tested V3 securities-summary rows do not include an exchange field,
explicit value unit, revision identifier, or daily-final flag.  The product
adapter therefore resolves the exact symbol's board before applying this
single, explicit normalization boundary.

The scales below are StockClock-validated operational units, not a claim that
SSI's public contract guarantees these units. A current-session row remains
provisional. The latest returned session before ``as_of`` is eligible as the
latest completed provider session, while provider-guaranteed finality remains
unavailable.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SSI_V3_FOREIGN_VOLUME_UNIT = "shares"
SSI_V3_FOREIGN_VALUE_UNIT = "VND"
SSI_V3_FOREIGN_FINALITY_POLICY = "stockclock_completed_session_rank_operational"
SSI_V3_FOREIGN_COMPLETED_MIN_SESSION_RANK = 1
SSI_V3_IMPLIED_PRICE_TOLERANCE = Decimal("0.05")
SSI_V3_VALUE_SCALE_CANDIDATES: Tuple[int, ...] = (1, 1_000, 1_000_000)

SSI_V3_FOREIGN_VALUE_SCALE_BY_BOARD: Dict[str, int] = {
    "HOSE": 1,
    "HNX": 1_000,
    "UPCOM": 1_000,
}
SSI_V3_FOREIGN_VALUE_DOMAIN_BY_BOARD: Dict[str, str] = {
    board: f"{board}_EQUITY_VALUE"
    for board in SSI_V3_FOREIGN_VALUE_SCALE_BY_BOARD
}


def _decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("boolean value is not numeric")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("value is not numeric") from exc
    if not parsed.is_finite():
        raise ValueError("value is not finite")
    return parsed


def _scaled_number(value: Any, scale: int) -> Optional[float]:
    parsed = _decimal(value)
    if parsed is None:
        return None
    return float(parsed * scale)


def foreign_value_policy_for_board(board: str) -> Dict[str, Any]:
    """Return the proven equity-value policy for one exact SSI board."""

    normalized = str(board or "").strip().upper()
    if normalized not in SSI_V3_FOREIGN_VALUE_SCALE_BY_BOARD:
        raise ValueError("foreign-value board must be HOSE, HNX, or UPCOM")
    return {
        "board": normalized,
        "domain": SSI_V3_FOREIGN_VALUE_DOMAIN_BY_BOARD[normalized],
        "scale": SSI_V3_FOREIGN_VALUE_SCALE_BY_BOARD[normalized],
        "volume_unit": SSI_V3_FOREIGN_VOLUME_UNIT,
        "value_unit": SSI_V3_FOREIGN_VALUE_UNIT,
        "confidence": "PROVEN",
    }


def foreign_row_finality(
    row_date: str,
    *,
    as_of: date,
    completed_session_rank: Optional[int] = None,
) -> Dict[str, Any]:
    """Classify a row under the StockClock returned-session policy.

    ``completed_session_rank`` is one-based among distinct provider dates
    strictly before ``as_of``: the latest returned completed session is 1.
    Requiring that context avoids treating weekends or holidays as sessions.
    """

    try:
        parsed = date.fromisoformat(str(row_date))
    except ValueError as exc:
        raise ValueError("foreign-flow date must use YYYY-MM-DD") from exc
    if parsed > as_of:
        raise ValueError("foreign-flow date cannot be in the future")
    if parsed == as_of:
        if completed_session_rank is not None:
            raise ValueError("current-session row cannot have a completed rank")
        state = "current_session_provisional"
        is_provisional = True
        effective_rank = 0
    else:
        if (
            isinstance(completed_session_rank, bool)
            or completed_session_rank is None
            or int(completed_session_rank) < 1
        ):
            raise ValueError(
                "historical foreign-flow row requires a positive completed-session rank"
            )
        effective_rank = int(completed_session_rank)
        is_provisional = False
    if parsed < as_of and effective_rank == 1:
        state = "latest_completed_session"
    elif parsed < as_of:
        state = "t_minus_2_or_older_completed_candidate"
    return {
        "policy": SSI_V3_FOREIGN_FINALITY_POLICY,
        "state": state,
        "is_provisional": is_provisional,
        "completed_session_rank": effective_rank,
        "provider_guaranteed": False,
    }


def normalize_foreign_value_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    board: str,
    as_of: date,
    include_provisional: bool = True,
    limit: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Normalize V3 foreign values once and attach unit/finality metadata.

    Duplicate dates are rejected instead of silently selecting one revision.
    Null gross values remain null and only complete gross pairs produce net.
    """

    policy = foreign_value_policy_for_board(board)
    source_rows = [dict(source_row) for source_row in rows]
    parsed_dates: Dict[str, date] = {}
    for row in source_rows:
        trading_date = str(row.get("date") or "")
        if not trading_date:
            raise ValueError("foreign-flow row date is required")
        if trading_date in parsed_dates:
            raise ValueError("duplicate foreign-flow date")
        try:
            parsed_date = date.fromisoformat(trading_date)
        except ValueError as exc:
            raise ValueError("foreign-flow date must use YYYY-MM-DD") from exc
        if parsed_date > as_of:
            raise ValueError("foreign-flow date cannot be in the future")
        parsed_dates[trading_date] = parsed_date
    completed_dates = sorted(
        {parsed for parsed in parsed_dates.values() if parsed < as_of},
        reverse=True,
    )
    completed_ranks = {
        parsed: rank for rank, parsed in enumerate(completed_dates, start=1)
    }

    normalized_rows: List[Dict[str, Any]] = []
    provisional_count = 0
    for row in source_rows:
        trading_date = str(row.get("date") or "")
        parsed_date = parsed_dates[trading_date]
        finality = foreign_row_finality(
            trading_date,
            as_of=as_of,
            completed_session_rank=completed_ranks.get(parsed_date),
        )
        if finality["is_provisional"]:
            provisional_count += 1

        scale = int(policy["scale"])
        buy_value = _scaled_number(row.get("foreign_buy_value"), scale)
        sell_value = _scaled_number(row.get("foreign_sell_value"), scale)
        row.update(
            {
                "market": policy["board"],
                "exchange": policy["board"],
                "foreign_buy_value": buy_value,
                "foreign_sell_value": sell_value,
                "foreign_net_value": (
                    buy_value - sell_value
                    if buy_value is not None and sell_value is not None
                    else None
                ),
                "_foreign_net_value_source": (
                    "derived"
                    if buy_value is not None and sell_value is not None
                    else None
                ),
                "foreign_volume_unit": policy["volume_unit"],
                "foreign_value_unit": policy["value_unit"],
                "foreign_value_domain": policy["domain"],
                "foreign_value_scale": scale,
                "foreign_value_scale_confidence": policy["confidence"],
                "foreign_finality_policy": finality["policy"],
                "foreign_finality": finality["state"],
                "foreign_is_provisional": finality["is_provisional"],
                "foreign_provider_finality_guaranteed": False,
            }
        )
        if include_provisional or not finality["is_provisional"]:
            normalized_rows.append(row)

    normalized_rows.sort(key=lambda item: str(item["date"]))
    if limit is not None:
        if isinstance(limit, bool) or int(limit) < 1:
            raise ValueError("limit must be a positive integer")
        normalized_rows = normalized_rows[-int(limit) :]
    return normalized_rows, {
        "foreign_value_domain": policy["domain"],
        "foreign_value_scale": policy["scale"],
        "foreign_volume_unit": policy["volume_unit"],
        "foreign_value_unit": policy["value_unit"],
        "foreign_value_scale_confidence": policy["confidence"],
        "foreign_finality_policy": SSI_V3_FOREIGN_FINALITY_POLICY,
        "foreign_provider_finality_guaranteed": False,
        "provisional_row_count": provisional_count,
        "provisional_rows_included": bool(include_provisional),
    }


def evaluate_implied_price_scales(
    *,
    volumes: Sequence[Any],
    values: Sequence[Any],
    lows: Sequence[Any],
    highs: Sequence[Any],
    candidates: Sequence[int] = SSI_V3_VALUE_SCALE_CANDIDATES,
    tolerance: Decimal = SSI_V3_IMPLIED_PRICE_TOLERANCE,
) -> Dict[int, Dict[str, int]]:
    """Count economically plausible implied prices for bounded scale candidates."""

    if not (len(volumes) == len(values) == len(lows) == len(highs)):
        raise ValueError("invariant input lengths must match")
    results = {
        int(candidate): {"eligible_rows": 0, "plausible_rows": 0, "outliers": 0}
        for candidate in candidates
    }
    for volume_raw, value_raw, low_raw, high_raw in zip(
        volumes, values, lows, highs
    ):
        volume = _decimal(volume_raw)
        value = _decimal(value_raw)
        low = _decimal(low_raw)
        high = _decimal(high_raw)
        if (
            volume is None
            or value is None
            or low is None
            or high is None
            or volume <= 0
            or value <= 0
            or low <= 0
            or high < low
        ):
            continue
        lower_bound = low * (Decimal(1) - tolerance)
        upper_bound = high * (Decimal(1) + tolerance)
        for candidate in candidates:
            result = results[int(candidate)]
            result["eligible_rows"] += 1
            implied = value * int(candidate) / volume
            if lower_bound <= implied <= upper_bound:
                result["plausible_rows"] += 1
            else:
                result["outliers"] += 1
    return results


def proven_implied_price_scale(
    results: Mapping[int, Mapping[str, int]],
) -> Optional[int]:
    """Accept only a unique candidate that is plausible for every eligible row."""

    accepted = [
        int(scale)
        for scale, counts in results.items()
        if int(counts.get("eligible_rows", 0)) > 0
        and int(counts.get("plausible_rows", 0))
        == int(counts.get("eligible_rows", 0))
    ]
    return accepted[0] if len(accepted) == 1 else None
