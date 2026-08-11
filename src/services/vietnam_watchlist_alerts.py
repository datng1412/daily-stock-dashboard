# -*- coding: utf-8 -*-
"""Completed-session Vietnam market intelligence alert rules.

These helpers deliberately reuse the existing alert worker.  They never read
the provisional ForeignRoom stream and they cache expensive service results in
the worker-cycle cache supplied by :mod:`alert_service`.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Mapping, Optional

from src.services.portfolio_alerts import RuntimeAlertPayload


VN_ALERT_TYPES = frozenset({
    "vn_foreign_flow",
    "vn_breadth",
    "vn_sector",
    "vn_relative_strength",
})
VN_OPERATORS = frozenset({"gt", "gte", "lt", "lte", "eq"})
VN_FLOW_WINDOWS = frozenset({1, 5, 20})
VN_RS_WINDOWS = frozenset({1, 5, 20})
VN_RS_BENCHMARKS = frozenset({"vnindex", "vn30", "industry"})
VN_FLOW_STATES = frozenset({"accumulating", "distributing", "neutral"})
VN_BREADTH_METRICS = frozenset({
    "advances", "declines", "advance_decline_spread",
    "percent_above_ma20", "percent_above_ma50",
})
VN_SECTOR_METRICS = frozenset({
    "return_1d_pct", "percent_above_ma20", "percent_above_ma50", "foreign_net_value",
})
VN_RS_METRICS = frozenset({"relative_performance_pp", "stock_return_pct", "benchmark_return_pct"})
VN_FLOW_METRICS = frozenset({"net_value", "direction_state"})
VN_DATA_SOURCE = "SSI completed-session analytics"


@dataclass
class VietnamWatchlistAlert:
    target_scope: str
    target: str
    alert_type: str
    parameters: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    stock_code: str = ""

    def __post_init__(self) -> None:
        self.stock_code = self.target


def normalize_vietnam_alert_target(alert_type: str, target: str) -> str:
    value = str(target or "").strip().upper()
    if alert_type in {"vn_foreign_flow", "vn_relative_strength"}:
        if not re.fullmatch(r"[A-Z0-9]{2,10}", value):
            raise ValueError("target must be a valid Vietnam ticker")
        return value
    if alert_type == "vn_breadth":
        if value != "VN30":
            raise ValueError("vn_breadth target must be VN30")
        return value
    if alert_type == "vn_sector":
        if not re.fullmatch(r"[A-Z0-9._-]{1,24}", value):
            raise ValueError("target must be a valid SSI ICB sector code")
        return value
    raise ValueError(f"unsupported Vietnam alert_type: {alert_type}")


def normalize_vietnam_alert_parameters(alert_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    if alert_type not in VN_ALERT_TYPES:
        raise ValueError(f"unsupported Vietnam alert_type: {alert_type}")
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")
    metric = str(parameters.get("metric") or "").strip().lower()

    if alert_type == "vn_foreign_flow":
        _require_choice(metric, VN_FLOW_METRICS, "metric")
        window = _integer_choice(parameters.get("window"), VN_FLOW_WINDOWS, "window")
        if metric == "direction_state":
            expected_state = str(parameters.get("expected_state") or "").strip().lower()
            _require_choice(expected_state, VN_FLOW_STATES, "expected_state")
            return {"metric": metric, "window": window, "operator": "eq", "expected_state": expected_state}
        return {"metric": metric, "window": window, **_numeric_condition(parameters)}

    if alert_type == "vn_breadth":
        _require_choice(metric, VN_BREADTH_METRICS, "metric")
        return {"metric": metric, **_numeric_condition(parameters)}

    if alert_type == "vn_sector":
        _require_choice(metric, VN_SECTOR_METRICS, "metric")
        normalized = {"metric": metric, **_numeric_condition(parameters)}
        if metric == "foreign_net_value":
            normalized["window"] = _integer_choice(parameters.get("window"), VN_FLOW_WINDOWS, "window")
        return normalized

    _require_choice(metric, VN_RS_METRICS, "metric")
    benchmark = str(parameters.get("benchmark") or "").strip().lower()
    _require_choice(benchmark, VN_RS_BENCHMARKS, "benchmark")
    return {
        "metric": metric,
        "window": _integer_choice(parameters.get("window"), VN_RS_WINDOWS, "window"),
        "benchmark": benchmark,
        **_numeric_condition(parameters),
    }


def make_vietnam_alert_payload(*, parent_key: str, data: Dict[str, Any]) -> RuntimeAlertPayload:
    target = normalize_vietnam_alert_target(data["alert_type"], data["target"])
    rule = VietnamWatchlistAlert(
        target_scope=data["target_scope"],
        target=target,
        alert_type=data["alert_type"],
        parameters=dict(data.get("parameters") or {}),
        metadata={"persisted_rule_id": data["id"], "effective_target": target},
        description=data.get("name") or data["alert_type"],
    )
    return RuntimeAlertPayload(
        key=f"{parent_key}|{target}", rule=rule, effective_target=target, display_target=target,
    )


def evaluate_vietnam_alert(rule: VietnamWatchlistAlert, *, cache: Optional[Dict[Any, Any]] = None) -> Dict[str, Any]:
    try:
        payload, cache_hit = _load_payload(rule, cache)
        observation = _extract_observation(rule, payload)
    except Exception as exc:
        return _result(rule, False, None, _threshold(rule), f"Vietnam alert input unavailable: {exc}",
                       "degraded", None, {"failure_class": type(exc).__name__})

    if not observation.get("evaluable"):
        reason = str(observation.get("reason") or "completed-session input is not evaluable")
        return _result(rule, False, None, _threshold(rule), reason, "skipped",
                       observation.get("session"), _diagnostics(rule, payload, observation, cache_hit))

    observed = observation["value"]
    if rule.parameters["metric"] == "direction_state":
        triggered = observed == rule.parameters["expected_state"]
        numeric_observed = None
    else:
        numeric_observed = float(observed)
        triggered = _compare(numeric_observed, rule.parameters["operator"], float(rule.parameters["threshold"]))
    condition = _condition_label(rule)
    message = f"{rule.target} {rule.parameters['metric']}={observed} {'matched' if triggered else 'did not match'} {condition}"
    return _result(rule, triggered, numeric_observed, _threshold(rule), message, None,
                   observation["session"], _diagnostics(rule, payload, observation, cache_hit))


def _load_payload(rule: VietnamWatchlistAlert, cache: Optional[Dict[Any, Any]]) -> tuple[Dict[str, Any], bool]:
    key = ("vn_alert", rule.alert_type, rule.target)
    if cache is not None and key in cache:
        return cache[key], True
    if rule.alert_type == "vn_foreign_flow":
        from src.services.vietnam_foreign_flow_service import VietnamForeignFlowService
        payload = VietnamForeignFlowService().get_symbol_history(rule.target, limit=60, force_refresh=False)
    elif rule.alert_type == "vn_breadth":
        from src.services.vietnam_market_breadth_service import VietnamMarketBreadthService
        payload = VietnamMarketBreadthService().build("VN30", force_refresh=False)
    elif rule.alert_type == "vn_sector":
        from src.services.vietnam_sector_strength_service import VietnamSectorStrengthService
        payload = VietnamSectorStrengthService().build("VN30", force_refresh=False)
    else:
        from src.services.vietnam_relative_strength_service import VietnamRelativeStrengthService
        payload = VietnamRelativeStrengthService().build(rule.target, force_refresh=False)
    if cache is not None:
        cache[key] = payload
    return payload, False


def _extract_observation(rule: VietnamWatchlistAlert, payload: Mapping[str, Any]) -> Dict[str, Any]:
    if rule.alert_type == "vn_foreign_flow":
        return _foreign_observation(rule, payload)
    if rule.alert_type == "vn_breadth":
        return _breadth_observation(rule, payload)
    if rule.alert_type == "vn_sector":
        return _sector_observation(rule, payload)
    return _rs_observation(rule, payload)


def _foreign_observation(rule: VietnamWatchlistAlert, payload: Mapping[str, Any]) -> Dict[str, Any]:
    window = int(rule.parameters["window"])
    coverage = payload.get("coverage") or {}
    analytics = payload.get("analytics") or {}
    signal = ((analytics.get("signals") or {}).get(f"direction_{window}d") or {})
    value_family = analytics.get("value") or {}
    if window == 1:
        latest = value_family.get("latest") or {}
        source_window = {
            "complete": latest.get("value") is not None,
            "net_sum": latest.get("value"),
            "end_date": latest.get("trading_date"),
            "requested_sessions": 1,
            "covered_sessions": int(latest.get("value") is not None),
        }
    else:
        source_window = (value_family.get("windows") or {}).get(str(window)) or {}
    session = signal.get("end_date") or source_window.get("end_date")
    complete = bool(signal.get("complete") if rule.parameters["metric"] == "direction_state" else source_window.get("complete"))
    value = signal.get("state") if rule.parameters["metric"] == "direction_state" else source_window.get("net_sum")
    valid = (payload.get("finality") == "daily_available" and complete and value is not None
             and payload.get("data_state") in {"ready", "partial"})
    return {"evaluable": valid, "value": value, "session": session,
            "coverage": coverage, "finality": payload.get("finality"),
            "reason": None if valid else "completed accepted foreign-flow window is incomplete or unavailable"}


def _breadth_observation(rule: VietnamWatchlistAlert, payload: Mapping[str, Any]) -> Dict[str, Any]:
    metric = rule.parameters["metric"]
    direction = payload.get("direction") or {}
    values = {
        "advances": direction.get("advances"), "declines": direction.get("declines"),
        "advance_decline_spread": (direction.get("advances") - direction.get("declines"))
        if direction.get("advances") is not None and direction.get("declines") is not None else None,
        "percent_above_ma20": (payload.get("ma20") or {}).get("percent_above"),
        "percent_above_ma50": (payload.get("ma50") or {}).get("percent_above"),
    }
    coverage = payload.get("coverage") or {}
    required = "direction_usable_count" if metric in {"advances", "declines", "advance_decline_spread"} else f"{metric[-4:]}_usable_count"
    valid = (payload.get("finality") == "completed_daily" and payload.get("usable") is True
             and values[metric] is not None and int(coverage.get(required) or 0) == 30)
    return {"evaluable": valid, "value": values[metric], "session": payload.get("provider_session_date"),
            "coverage": coverage, "finality": payload.get("finality"),
            "reason": None if valid else "completed VN30 breadth coverage is incomplete or unavailable"}


def _sector_observation(rule: VietnamWatchlistAlert, payload: Mapping[str, Any]) -> Dict[str, Any]:
    group = next((item for item in payload.get("groups") or [] if str(item.get("icb_code") or "").upper() == rule.target), None)
    if not group:
        return {"evaluable": False, "value": None, "session": payload.get("price_session_date"),
                "coverage": {}, "finality": payload.get("price_finality"), "reason": "SSI ICB sector is absent from current VN30 membership"}
    metric = rule.parameters["metric"]
    coverage: Dict[str, Any]
    if metric == "return_1d_pct":
        row = group.get("return_1d") or {}; value = float(row["value"]) * 100 if row.get("value") is not None else None
        coverage = row; session = payload.get("price_session_date"); finality = payload.get("price_finality")
        complete = row.get("usable_count") == group.get("member_count")
    elif metric.startswith("percent_above_ma"):
        row = group.get("ma20" if metric.endswith("20") else "ma50") or {}; value = row.get("percent_above")
        coverage = row; session = payload.get("price_session_date"); finality = payload.get("price_finality")
        complete = row.get("usable_count") == group.get("member_count")
    else:
        row = (((group.get("foreign_flow") or {}).get("windows") or {}).get(str(rule.parameters["window"])) or {})
        value = row.get("net_value"); coverage = row; session = row.get("end_date"); finality = (group.get("foreign_flow") or {}).get("finality")
        complete = bool(row.get("complete"))
    valid = value is not None and complete and finality in {"completed_daily", "completed_accepted"}
    return {"evaluable": valid, "value": value, "session": session, "coverage": coverage, "finality": finality,
            "reason": None if valid else "completed sector metric coverage is incomplete or unavailable"}


def _rs_observation(rule: VietnamWatchlistAlert, payload: Mapping[str, Any]) -> Dict[str, Any]:
    comparison = (payload.get("comparisons") or {}).get(rule.parameters["benchmark"]) or {}
    row = (comparison.get("windows") or {}).get(f"{rule.parameters['window']}d") or {}
    value = row.get(rule.parameters["metric"])
    valid = bool(row.get("complete")) and row.get("status") == "ready" and value is not None
    return {"evaluable": valid, "value": value, "session": row.get("end_session"), "coverage": row,
            "finality": "completed_daily", "reason": None if valid else "exact-session relative-strength window is incomplete or unavailable"}


def _diagnostics(rule: VietnamWatchlistAlert, payload: Mapping[str, Any], observation: Mapping[str, Any], cache_hit: bool) -> Dict[str, Any]:
    return {
        "family": rule.alert_type, "scope": rule.target, "metric": rule.parameters.get("metric"),
        "window": rule.parameters.get("window"), "operator": rule.parameters.get("operator"),
        "threshold": rule.parameters.get("threshold") or rule.parameters.get("expected_state"),
        "observed": observation.get("value"), "session": observation.get("session"),
        "source": payload.get("source") or VN_DATA_SOURCE, "source_endpoint": payload.get("source_endpoint"),
        "finality": observation.get("finality"), "coverage": observation.get("coverage"),
        "cache_hit": cache_hit, "deep_link": _deep_link(rule), "dedup_key": f"rule:{rule.metadata.get('persisted_rule_id')}:{observation.get('session')}",
        "provider_calls": (payload.get("diagnostics") or {}).get("provider_call_count"),
    }


def _deep_link(rule: VietnamWatchlistAlert) -> str:
    if rule.alert_type == "vn_relative_strength":
        return f"/vietnam?ticker={rule.target}"
    if rule.alert_type == "vn_foreign_flow":
        return f"/foreign-flow?mode=ticker&ticker={rule.target}"
    return "/vietnam"


def _result(rule: VietnamWatchlistAlert, triggered: bool, observed: Optional[float], threshold: Optional[float],
            message: str, record_status: Optional[str], session: Optional[str], diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    timestamp = datetime.fromisoformat(session) if session else None
    return {"rule_id": int(rule.metadata.get("persisted_rule_id") or 0),
            "status": "triggered" if triggered else "not_triggered", "record_status": "triggered" if triggered else record_status,
            "triggered": triggered, "observed_value": observed, "threshold": threshold, "data_source": VN_DATA_SOURCE,
            "data_timestamp": timestamp, "reason": message, "message": message,
            "diagnostics": json.dumps(diagnostics, ensure_ascii=False, sort_keys=True, default=str)}


def _numeric_condition(parameters: Mapping[str, Any]) -> Dict[str, Any]:
    operator = str(parameters.get("operator") or "").strip().lower()
    _require_choice(operator, VN_OPERATORS, "operator")
    try:
        threshold = float(parameters.get("threshold"))
    except (TypeError, ValueError) as exc:
        raise ValueError("threshold must be a finite number") from exc
    if not math.isfinite(threshold):
        raise ValueError("threshold must be a finite number")
    return {"operator": operator, "threshold": threshold}


def _integer_choice(value: Any, choices: frozenset[int], field_name: str) -> int:
    try: result = int(value)
    except (TypeError, ValueError) as exc: raise ValueError(f"invalid {field_name}") from exc
    if result not in choices: raise ValueError(f"{field_name} must be one of {sorted(choices)}")
    return result


def _require_choice(value: str, choices: frozenset[str], field_name: str) -> None:
    if value not in choices: raise ValueError(f"{field_name} must be one of {sorted(choices)}")


def _compare(value: float, operator: str, threshold: float) -> bool:
    return {"gt": value > threshold, "gte": value >= threshold, "lt": value < threshold,
            "lte": value <= threshold, "eq": value == threshold}[operator]


def _threshold(rule: VietnamWatchlistAlert) -> Optional[float]:
    value = rule.parameters.get("threshold")
    return float(value) if value is not None else None


def _condition_label(rule: VietnamWatchlistAlert) -> str:
    return str(rule.parameters.get("expected_state") if rule.parameters["metric"] == "direction_state"
               else f"{rule.parameters['operator']} {rule.parameters['threshold']}")
