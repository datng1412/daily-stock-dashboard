"""Bounded P0 capability gate for non-SSI Vietnam proprietary-flow providers.

This is a manual diagnostic only. It never mutates application caches, never
prints credentials, and does not enable a production provider. The FiinGroup
DataFeed contract is reported from its official public schema; live FiinGroup
access remains gated until an official client/auth contract is configured.
Installed FiinQuantX access is a separate product and is probed through its
public ``FiinSession`` and ``PriceStatistics`` interfaces only with ``--live``.
The optional Sponsor ``vnstock_data`` package is probed only with ``--live``.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import hashlib
import importlib.util
import io
import json
import logging
import multiprocessing as mp
import os
from pathlib import Path
import queue
import sys
import traceback
from time import monotonic, sleep
from typing import Any, Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_SYMBOLS = ("FPT", "SSI", "HPG", "VPB", "VIC")
MAX_SYMBOLS = 30
MIN_INTERVAL_SECONDS = 5.0
MAX_DURATION_SECONDS = 1_800.0
DEFAULT_INTERVAL_SECONDS = 15.0
DEFAULT_DURATION_SECONDS = 1_200.0
FIIN_ENDPOINT = "/Financial/GetProprietaryTradingStock"
FIINQUANT_OPERATION = "FiinSession.PriceStatistics().get_value_by_investor()"
FIINQUANT_PACKAGE = "FiinQuantX"
FIINQUANT_TIMEOUT_SECONDS = 60.0
FIINQUANT_HISTORY_DAYS = 14
VNSTOCK_SYMBOL_OPERATION = "Market().equity(symbol).proprietary_flow()"
VNSTOCK_BULK_OPERATION = "Insights().flow.proprietary(exchange='HOSE', group_by='stock')"
CAPABILITIES = {
    "REALTIME",
    "NEAR_REALTIME_POLLING",
    "POST_CLOSE_SAME_DAY",
    "END_OF_DAY_ONLY",
    "HISTORICAL_ONLY",
    "UNAVAILABLE",
}
GROSS_ALIASES = {
    "buy_volume": (
        "proprietaryTotalBuyTradeVolume", "TotalBuyTradeVolume",
        "total_buy_trade_volume", "buy_volume",
    ),
    "sell_volume": (
        "proprietaryTotalSellTradeVolume", "TotalSellTradeVolume",
        "total_sell_trade_volume", "sell_volume",
    ),
    "buy_value": (
        "proprietaryTotalBuyTradeValue", "TotalBuyTradeValue",
        "total_buy_trade_value", "buy_value",
    ),
    "sell_value": (
        "proprietaryTotalSellTradeValue", "TotalSellTradeValue",
        "total_sell_trade_value", "sell_value",
    ),
    "match_buy_volume": (
        "proprietaryTotalMatchBuyTradeVolume", "TotalMatchBuyTradeVolume",
        "total_match_buy_trade_volume", "match_buy_volume",
    ),
    "match_sell_volume": (
        "proprietaryTotalMatchSellTradeVolume", "TotalMatchSellTradeVolume",
        "total_match_sell_trade_volume", "match_sell_volume",
    ),
    "match_buy_value": (
        "proprietaryTotalMatchBuyTradeValue", "TotalMatchBuyTradeValue",
        "total_match_buy_trade_value", "match_buy_value",
    ),
    "match_sell_value": (
        "proprietaryTotalMatchSellTradeValue", "TotalMatchSellTradeValue",
        "total_match_sell_trade_value", "match_sell_value",
    ),
    "deal_buy_volume": (
        "proprietaryTotalDealBuyTradeVolume", "TotalDealBuyTradeVolume",
        "total_deal_buy_trade_volume", "deal_buy_volume",
    ),
    "deal_sell_volume": (
        "proprietaryTotalDealSellTradeVolume", "TotalDealSellTradeVolume",
        "total_deal_sell_trade_volume", "deal_sell_volume",
    ),
    "deal_buy_value": (
        "proprietaryTotalDealBuyTradeValue", "TotalDealBuyTradeValue",
        "total_deal_buy_trade_value", "deal_buy_value",
    ),
    "deal_sell_value": (
        "proprietaryTotalDealSellTradeValue", "TotalDealSellTradeValue",
        "total_deal_sell_trade_value", "deal_sell_value",
    ),
}
FIINQUANT_PROPRIETARY_FIELDS = tuple(aliases[0] for aliases in GROSS_ALIASES.values())
DATE_ALIASES = ("TradingDate", "tradingDate", "trading_date", "date", "time")
SYMBOL_ALIASES = ("Ticker", "ticker", "code", "symbol")
TIMESTAMP_ALIASES = ("UpdateDate", "update_date", "provider_time", "last_updated")
CSV_FIELDS = (
    "local_received_at", "provider", "provider_operation", "symbol", "trading_date",
    "provider_timestamp", "buy_volume", "sell_volume", "net_volume", "buy_value",
    "sell_value", "net_value", "match_buy_volume", "match_sell_volume",
    "match_buy_value", "match_sell_value", "deal_buy_volume", "deal_sell_volume",
    "deal_buy_value", "deal_sell_value", "row_hash", "raw_schema_hash", "status",
    "error_class", "field_presence", "aliases_used",
)


@dataclass(frozen=True)
class ProbeResult:
    provider: str
    operation: str
    capability: str
    observations: tuple[dict[str, Any], ...]
    request_count: int = 0
    failure_class: str | None = None
    package_version: str | None = None
    routed_source: str | None = None
    note: str | None = None
    authentication: str | None = None
    contract_fields: tuple[str, ...] = ()
    observed_fields: tuple[str, ...] = ()
    error_type: str | None = None
    error_location: str | None = None


def _first(row: Mapping[str, Any], aliases: Sequence[str]) -> tuple[Any, str | None]:
    for alias in aliases:
        if alias in row:
            return row.get(alias), alias
    return None, None


def _numeric(value: Any, alias: str | None) -> tuple[int | float | None, str]:
    if alias is None:
        return None, "FIELD_ABSENT"
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, "FIELD_NULL"
    if isinstance(value, bool):
        return None, "PARSE_FAILURE"
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None, "PARSE_FAILURE"
    if not parsed == parsed or parsed in {float("inf"), float("-inf")}:
        return None, "PARSE_FAILURE"
    number: int | float = int(parsed) if parsed.is_integer() else parsed
    return number, "FIELD_PRESENT_ZERO" if number == 0 else "FIELD_PRESENT_VALUE"


def _text_date(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        try:
            return date.fromisoformat(text[:10]).isoformat()
        except ValueError:
            return None


def _hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def normalize_observation(
    provider: str,
    operation: str,
    row: Mapping[str, Any] | None,
    *,
    received_at: str | None = None,
    error_class: str | None = None,
) -> dict[str, Any]:
    """Normalize one raw row while retaining field-presence evidence."""

    received = received_at or datetime.now().astimezone().isoformat(timespec="seconds")
    if row is None:
        return {
            **{field: None for field in CSV_FIELDS},
            "local_received_at": received,
            "provider": provider,
            "provider_operation": operation,
            "status": "unavailable",
            "error_class": error_class or "PROVIDER_ROW_MISSING",
            "field_presence": {field: "PROVIDER_ROW_MISSING" for field in GROSS_ALIASES},
        }
    values: dict[str, int | float | None] = {}
    presence: dict[str, str] = {}
    aliases_used: dict[str, str | None] = {}
    for canonical, aliases in GROSS_ALIASES.items():
        raw_value, alias = _first(row, aliases)
        values[canonical], presence[canonical] = _numeric(raw_value, alias)
        aliases_used[canonical] = alias
    buy_volume, sell_volume = values["buy_volume"], values["sell_volume"]
    buy_value, sell_value = values["buy_value"], values["sell_value"]
    symbol, _ = _first(row, SYMBOL_ALIASES)
    trading_date, _ = _first(row, DATE_ALIASES)
    provider_timestamp, _ = _first(row, TIMESTAMP_ALIASES)
    schema = sorted(str(key) for key in row)
    normalized = {
        "local_received_at": received,
        "provider": provider,
        "provider_operation": operation,
        "symbol": str(symbol or "").strip().upper() or None,
        "trading_date": _text_date(trading_date),
        "provider_timestamp": str(provider_timestamp).strip() if provider_timestamp is not None else None,
        **values,
        "net_volume": buy_volume - sell_volume if buy_volume is not None and sell_volume is not None else None,
        "net_value": buy_value - sell_value if buy_value is not None and sell_value is not None else None,
        "raw_schema_hash": _hash(schema),
        "status": "ok",
        "error_class": error_class,
        "field_presence": presence,
        "aliases_used": aliases_used,
    }
    normalized["row_hash"] = _hash({key: value for key, value in normalized.items() if key != "row_hash"})
    return normalized


def classify_error(value: Any) -> str:
    text = str(value or "").lower()
    if any(marker in text for marker in ("401", "unauthorized", "authentication", "api key")):
        return "AUTHENTICATION_FAILURE"
    if any(marker in text for marker in ("403", "entitlement", "membership", "forbidden", "licence")):
        return "ENTITLEMENT_FAILURE"
    if any(marker in text for marker in ("429", "rate limit", "too many requests")):
        return "RATE_LIMITED"
    if any(marker in text for marker in (
        "connection", "connecterror", "timeout", "timed out", "dns", "ssl",
        "proxy", "name resolution", "network", "max retries",
    )):
        return "NETWORK_FAILURE"
    if any(marker in text for marker in (
        "modulenotfound", "importerror", "attributeerror", "keyerror", "typeerror",
    )):
        return "PROVIDER_PACKAGE_ERROR"
    return "PROVIDER_ERROR"


def classify_capability(
    observations: Sequence[Mapping[str, Any]],
    *,
    current_date: str,
    market_phase: str,
    push_proven: bool = False,
) -> str:
    usable = [row for row in observations if row.get("status") == "ok" and row.get("trading_date")]
    if not usable:
        return "UNAVAILABLE"
    current = [row for row in usable if row.get("trading_date") == current_date]
    if not current:
        return "HISTORICAL_ONLY"
    gross = [
        row for row in current
        if row.get("buy_volume") is not None and row.get("sell_volume") is not None
        and row.get("buy_value") is not None and row.get("sell_value") is not None
    ]
    if not gross:
        return "UNAVAILABLE"
    if market_phase in {"post_close", "closed"}:
        return "POST_CLOSE_SAME_DAY"
    hashes = {str(row.get("row_hash")) for row in gross}
    timestamps = {str(row.get("provider_timestamp")) for row in gross if row.get("provider_timestamp")}
    if len(hashes) > 1 and (len(timestamps) > 1 or push_proven):
        return "REALTIME" if push_proven else "NEAR_REALTIME_POLLING"
    return "UNAVAILABLE"


def reconciliation(total: Mapping[str, Any], match: Mapping[str, Any], deal: Mapping[str, Any]) -> bool | None:
    compared = False
    for side in ("buy_volume", "sell_volume", "buy_value", "sell_value"):
        total_value = total.get(side)
        match_value = match.get(f"match_{side}")
        deal_value = deal.get(f"deal_{side}")
        if total_value is None or match_value is None or deal_value is None:
            continue
        compared = True
        if total_value != match_value + deal_value:
            return False
    return True if compared else None


def bounded_retry_delays(retry_after: float | None = None) -> tuple[float, ...]:
    if retry_after is not None:
        return (max(1.0, min(float(retry_after), 60.0)),)
    return (1.0, 2.0)


def _frame_records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        records = frame.to_dict(orient="records")
        return [dict(row) for row in records if isinstance(row, Mapping)]
    if isinstance(frame, Mapping):
        return [dict(frame)]
    if isinstance(frame, Iterable) and not isinstance(frame, (str, bytes)):
        return [dict(row) for row in frame if isinstance(row, Mapping)]
    return []


def inspect_fiinquant_contract() -> dict[str, Any]:
    """Inspect the installed public field registry without authenticating."""

    if importlib.util.find_spec(FIINQUANT_PACKAGE) is None:
        return {
            "package_available": False,
            "operation_available": False,
            "contract_fields": (),
        }
    try:
        from FiinQuantX import FiinSession
        from FiinQuantX.helper.PriceStatistics import PriceStatistics

        registry = PriceStatistics(lambda: "redacted").fields
        declared = tuple(str(field) for field in registry.get("ValueByInvestor", ()))
        public_methods = {
            name for name in dir(FiinSession)
            if not name.startswith("_") and callable(getattr(FiinSession, name, None))
        }
        price_methods = {
            name for name in dir(PriceStatistics)
            if not name.startswith("_") and callable(getattr(PriceStatistics, name, None))
        }
        return {
            "package_available": True,
            "operation_available": (
                "login" in public_methods
                and "PriceStatistics" in public_methods
                and "get_value_by_investor" in price_methods
            ),
            "contract_fields": tuple(
                field for field in FIINQUANT_PROPRIETARY_FIELDS if field in declared
            ),
        }
    except Exception:
        return {
            "package_available": True,
            "operation_available": False,
            "contract_fields": (),
        }


def _load_repo_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


def _safe_error_location(exc: BaseException) -> str | None:
    frames = traceback.extract_tb(exc.__traceback__)
    if not frames:
        return None
    frame = frames[-1]
    return f"{Path(frame.filename).name}:{frame.name}:{frame.lineno}"


def _fiinquant_logged_in(client: Any) -> bool:
    """Use the package's public login-state flag; never inspect token values."""

    return getattr(client, "is_login", None) is True


def _fiinquant_worker(output: Any, symbols: tuple[str, ...], history_days: int) -> None:
    """Authenticate and make one bounded logical proprietary-history request.

    Provider stdout/stderr are captured in-process and discarded so an
    upstream login implementation cannot leak credentials or tokens into the
    diagnostic output.
    """

    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    try:
        with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
            logging.disable(logging.CRITICAL)
            _load_repo_dotenv()
            username = (os.getenv("FIINQUANT_USERNAME") or "").strip()
            password = (os.getenv("FIINQUANT_PASSWORD") or "").strip()
            if not username or not password:
                output.put({
                    "failure_class": "CONFIGURATION_REQUIRED",
                    "authentication": "NOT_ATTEMPTED",
                })
                return

            import importlib.metadata as metadata
            from FiinQuantX import FiinSession

            try:
                session = FiinSession(username=username, password=password)
                client = session.login()
                if client is None:
                    client = session
            except BaseException as exc:
                output.put({
                    "failure_class": classify_error(
                        type(exc).__name__ + ":" + str(exc)[:160]
                    ),
                    "authentication": "FAILED",
                    "package_version": metadata.version(FIINQUANT_PACKAGE),
                    "error_type": type(exc).__name__,
                    "error_location": _safe_error_location(exc),
                })
                return

            if not _fiinquant_logged_in(client):
                output.put({
                    "failure_class": "AUTHENTICATION_FAILURE",
                    "authentication": "FAILED",
                    "package_version": metadata.version(FIINQUANT_PACKAGE),
                    "request_count": 0,
                    "error_type": "LoginStateFalse",
                })
                return

            to_date = datetime.now().astimezone().date()
            from_date = to_date - timedelta(days=max(1, history_days))
            request_started = False
            try:
                statistics = client.PriceStatistics()
                request_started = True
                frame = statistics.get_value_by_investor(
                    tickers=list(symbols),
                    from_date=from_date.isoformat(),
                    to_date=to_date.isoformat(),
                )
            except BaseException as exc:
                output.put({
                    "failure_class": classify_error(
                        type(exc).__name__ + ":" + str(exc)[:160]
                    ),
                    "authentication": "AUTHENTICATED",
                    "package_version": metadata.version(FIINQUANT_PACKAGE),
                    "request_count": int(request_started),
                    "error_type": type(exc).__name__,
                    "error_location": _safe_error_location(exc),
                })
                return

            rows = _frame_records(frame)
            observed_fields = tuple(sorted({str(key) for row in rows for key in row}))
            received = datetime.now().astimezone().isoformat(timespec="seconds")
            observations = tuple(
                normalize_observation(
                    "FiinQuantX",
                    FIINQUANT_OPERATION,
                    row,
                    received_at=received,
                )
                for row in rows
            )
            output.put({
                "authentication": "AUTHENTICATED",
                "package_version": metadata.version(FIINQUANT_PACKAGE),
                "request_count": 1,
                "observations": observations,
                "observed_fields": observed_fields,
            })
    except ModuleNotFoundError:
        output.put({
            "failure_class": "PROVIDER_PACKAGE_MISSING",
            "authentication": "NOT_ATTEMPTED",
        })
    except BaseException as exc:
        output.put({
            "failure_class": classify_error(type(exc).__name__ + ":" + str(exc)[:160]),
            "authentication": "UNKNOWN",
            "error_type": type(exc).__name__,
            "error_location": _safe_error_location(exc),
        })
    finally:
        logging.disable(logging.NOTSET)


def inspect_fiinquant(*, live: bool, symbols: tuple[str, ...]) -> ProbeResult:
    contract = inspect_fiinquant_contract()
    contract_fields = tuple(contract["contract_fields"])
    if not contract["package_available"]:
        return ProbeResult(
            provider="FiinQuantX",
            operation=FIINQUANT_OPERATION,
            capability="UNAVAILABLE",
            observations=(),
            failure_class="PROVIDER_PACKAGE_MISSING",
            authentication="NOT_ATTEMPTED",
        )
    if not contract["operation_available"] or len(contract_fields) != len(
        FIINQUANT_PROPRIETARY_FIELDS
    ):
        return ProbeResult(
            provider="FiinQuantX",
            operation=FIINQUANT_OPERATION,
            capability="UNAVAILABLE",
            observations=(),
            failure_class="PROVIDER_CONTRACT_MISSING",
            authentication="NOT_ATTEMPTED",
            contract_fields=contract_fields,
        )
    if not live:
        return ProbeResult(
            provider="FiinQuantX",
            operation=FIINQUANT_OPERATION,
            capability="UNAVAILABLE",
            observations=(),
            failure_class="LIVE_PROBE_DISABLED",
            authentication="NOT_ATTEMPTED",
            contract_fields=contract_fields,
            note="Use --live for the bounded authenticated manual proof.",
        )

    context = mp.get_context("spawn")
    output = context.Queue(maxsize=1)
    process = context.Process(
        target=_fiinquant_worker,
        args=(output, symbols, FIINQUANT_HISTORY_DAYS),
    )
    process.start()
    try:
        process.join(timeout=FIINQUANT_TIMEOUT_SECONDS)
    except KeyboardInterrupt:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5.0)
        raise
    if process.is_alive():
        process.terminate()
        process.join(timeout=5.0)
        return ProbeResult(
            provider="FiinQuantX",
            operation=FIINQUANT_OPERATION,
            capability="UNAVAILABLE",
            observations=(),
            failure_class="NETWORK_FAILURE",
            authentication="UNKNOWN",
            contract_fields=contract_fields,
            note="Hard 60-second deadline reached; owned child was terminated.",
        )
    try:
        payload = output.get_nowait()
    except queue.Empty:
        payload = {"failure_class": "NETWORK_FAILURE", "authentication": "UNKNOWN"}
    observations = tuple(payload.get("observations") or ())
    capability = classify_capability(
        observations,
        current_date=datetime.now().astimezone().date().isoformat(),
        market_phase=market_phase(datetime.now().astimezone()),
    )
    return ProbeResult(
        provider="FiinQuantX",
        operation=FIINQUANT_OPERATION,
        capability=capability,
        observations=observations,
        request_count=int(payload.get("request_count") or 0),
        failure_class=payload.get("failure_class"),
        package_version=payload.get("package_version"),
        authentication=payload.get("authentication"),
        contract_fields=contract_fields,
        observed_fields=tuple(payload.get("observed_fields") or ()),
        error_type=payload.get("error_type"),
        error_location=payload.get("error_location"),
        note=(
            "Historical/post-close request only; active-session publication cadence "
            "and update semantics remain unproven."
        ),
    )


def _vnstock_worker(output: Any, symbols: tuple[str, ...], duration: float, interval: float) -> None:
    """Own one Sponsor client lifecycle inside a hard-bounded child process."""

    try:
        import importlib.metadata as metadata
        from vnstock_data import Insights, Market  # type: ignore[import-not-found]

        market = Market()
        insights = Insights()
        observations: list[dict[str, Any]] = []
        request_count = 0
        started = monotonic()
        while True:
            received = datetime.now().astimezone().isoformat(timespec="seconds")
            for symbol in symbols:
                frame = market.equity(symbol).proprietary_flow()
                request_count += 1
                rows = _frame_records(frame)
                if not rows:
                    observations.append(normalize_observation(
                        "Vnstock Data", VNSTOCK_SYMBOL_OPERATION, None,
                        received_at=received, error_class="PROVIDER_ROW_MISSING",
                    ))
                else:
                    observations.extend(
                        normalize_observation(
                            "Vnstock Data", VNSTOCK_SYMBOL_OPERATION, row, received_at=received,
                        )
                        for row in rows
                    )
            bulk = insights.flow.proprietary(exchange="HOSE", group_by="stock")
            request_count += 1
            observations.extend(
                normalize_observation(
                    "Vnstock Data", VNSTOCK_BULK_OPERATION, row, received_at=received,
                )
                for row in _frame_records(bulk)
            )
            if monotonic() - started >= duration:
                break
            sleep(min(interval, max(0.0, duration - (monotonic() - started))))
        output.put({
            "observations": observations,
            "request_count": request_count,
            "package_version": metadata.version("vnstock-data"),
        })
    except BaseException as exc:  # child returns only a typed, sanitized class
        output.put({"failure_class": classify_error(type(exc).__name__ + ":" + str(exc)[:120])})


def inspect_fiin() -> ProbeResult:
    return ProbeResult(
        provider="FiinGroup DataFeed",
        operation=FIIN_ENDPOINT,
        capability="UNAVAILABLE",
        observations=(),
        failure_class="CONFIGURATION_REQUIRED",
        note=(
            "Official gross/match/deal schema is documented, but no official DataFeed client, "
            "authentication contract, entitlement, or DataFeed configuration is available locally."
        ),
    )


def inspect_vnstock(*, live: bool, symbols: tuple[str, ...], duration: float, interval: float) -> ProbeResult:
    if importlib.util.find_spec("vnstock_data") is None:
        return ProbeResult(
            provider="Vnstock Data",
            operation=f"{VNSTOCK_SYMBOL_OPERATION}; {VNSTOCK_BULK_OPERATION}",
            capability="UNAVAILABLE",
            observations=(),
            failure_class="PROVIDER_PACKAGE_MISSING",
            note="The installed free vnstock package is not the Sponsor vnstock_data package.",
        )
    if not live:
        return ProbeResult(
            provider="Vnstock Data",
            operation=f"{VNSTOCK_SYMBOL_OPERATION}; {VNSTOCK_BULK_OPERATION}",
            capability="UNAVAILABLE",
            observations=(),
            failure_class="LIVE_PROBE_DISABLED",
            note="Use --live only in a permitted bounded observation window.",
        )
    context = mp.get_context("spawn")
    output = context.Queue(maxsize=1)
    process = context.Process(target=_vnstock_worker, args=(output, symbols, duration, interval))
    process.start()
    try:
        process.join(timeout=duration + 45.0)
    except KeyboardInterrupt:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5.0)
        raise
    if process.is_alive():
        process.terminate()
        process.join(timeout=5.0)
        return ProbeResult(
            provider="Vnstock Data", operation=VNSTOCK_SYMBOL_OPERATION,
            capability="UNAVAILABLE", observations=(), failure_class="NETWORK_FAILURE",
            note="Hard probe deadline reached; owned child was terminated.",
        )
    try:
        payload = output.get_nowait()
    except queue.Empty:
        payload = {"failure_class": "NETWORK_FAILURE"}
    observations = tuple(payload.get("observations") or ())
    phase = market_phase(datetime.now().astimezone())
    capability = classify_capability(
        observations,
        current_date=datetime.now().astimezone().date().isoformat(),
        market_phase=phase,
    )
    return ProbeResult(
        provider="Vnstock Data",
        operation=f"{VNSTOCK_SYMBOL_OPERATION}; {VNSTOCK_BULK_OPERATION}",
        capability=capability,
        observations=observations,
        request_count=int(payload.get("request_count") or 0),
        failure_class=payload.get("failure_class"),
        package_version=payload.get("package_version"),
        routed_source="VCI (official documented route); runtime source unverified" if observations else None,
    )


def market_phase(now: datetime) -> str:
    minutes = now.hour * 60 + now.minute
    if now.weekday() >= 5:
        return "closed"
    if 9 * 60 <= minutes <= 11 * 60 + 30 or 13 * 60 <= minutes <= 14 * 60 + 45:
        return "active"
    if minutes >= 15 * 60:
        return "post_close"
    return "closed"


def fiinquant_outcome(result: ProbeResult, *, phase: str) -> str | None:
    if result.provider != "FiinQuantX":
        return None
    if result.failure_class == "PROVIDER_PACKAGE_MISSING":
        return "VN_PROPRIETARY_FIINQUANT_PACKAGE_BLOCKED"
    if result.failure_class == "AUTHENTICATION_FAILURE":
        return "VN_PROPRIETARY_FIINQUANT_AUTH_FAILED"
    if result.failure_class == "ENTITLEMENT_FAILURE":
        return "VN_PROPRIETARY_FIINQUANT_ENTITLEMENT_REQUIRED"
    if result.failure_class in {"NETWORK_FAILURE", "RATE_LIMITED"}:
        return "VN_PROPRIETARY_FIINQUANT_NETWORK_BLOCKED"
    if result.failure_class in {"PROVIDER_PACKAGE_ERROR", "PROVIDER_ERROR"}:
        return "VN_PROPRIETARY_FIINQUANT_PACKAGE_BLOCKED"
    gross = [
        row for row in result.observations
        if row.get("buy_volume") is not None and row.get("sell_volume") is not None
        and row.get("buy_value") is not None and row.get("sell_value") is not None
    ]
    if result.authentication == "AUTHENTICATED" and gross:
        return "VN_PROPRIETARY_FIINQUANT_PROPRIETARY_CAPABILITY_FOUND_POST_CLOSE"
    if result.authentication == "AUTHENTICATED" and phase == "active":
        return "VN_PROPRIETARY_FIINQUANT_AUTHENTICATED_ACTIVE_SESSION_PENDING"
    if result.authentication == "AUTHENTICATED":
        return "VN_PROPRIETARY_FIINQUANT_AUTHENTICATED_NO_PROPRIETARY_CONTRACT"
    return "VN_PROPRIETARY_FIINQUANT_PACKAGE_BLOCKED"


def _summary(result: ProbeResult) -> dict[str, Any]:
    timestamps = [row.get("provider_timestamp") for row in result.observations if row.get("provider_timestamp")]
    current_date = datetime.now().astimezone().date().isoformat()
    current = [row for row in result.observations if row.get("trading_date") == current_date]
    gross_rows = [
        row for row in result.observations
        if row.get("buy_volume") is not None and row.get("sell_volume") is not None
        and row.get("buy_value") is not None and row.get("sell_value") is not None
    ]
    phase = market_phase(datetime.now().astimezone())
    return {
        "provider": result.provider,
        "provider_operation": result.operation,
        "outcome": fiinquant_outcome(result, phase=phase),
        "capability": result.capability,
        "failure_class": result.failure_class,
        "error_type": result.error_type,
        "error_location": result.error_location,
        "authentication": result.authentication,
        "package_version": result.package_version,
        "routed_source": result.routed_source,
        "request_count": result.request_count,
        "observation_count": len(result.observations),
        "gross_history_row_count": len(gross_rows),
        "current_date_present": bool(current),
        "gross_current_row_count": sum(
            row.get("buy_volume") is not None and row.get("sell_volume") is not None
            and row.get("buy_value") is not None and row.get("sell_value") is not None
            for row in current
        ),
        "provider_timestamp_count": len(set(timestamps)),
        "contract_field_count": len(result.contract_fields),
        "observed_contract_fields": [
            field for field in result.contract_fields if field in result.observed_fields
        ],
        "note": result.note,
    }


def _write_outputs(output_dir: Path, results: Sequence[ProbeResult]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "report.json"
    csv_path = output_dir / "observations.csv"
    report = {
        "phase": "VN-PROPRIETARY-P0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "market_phase": market_phase(datetime.now().astimezone()),
        "production_cache_mutated": False,
        "providers": [
            {**_summary(result), "observations": list(result.observations)}
            for result in results
        ],
    }
    json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for result in results:
            writer.writerows(result.observations)
    return json_path, csv_path


def _symbols(value: str) -> tuple[str, ...]:
    values: list[str] = []
    for part in value.split(","):
        symbol = part.strip().upper()
        if symbol and symbol not in values:
            values.append(symbol)
    if not values or len(values) > MAX_SYMBOLS or any(not item.isalnum() for item in values):
        raise argparse.ArgumentTypeError(f"symbols must contain 1-{MAX_SYMBOLS} alphanumeric tickers")
    return tuple(values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--symbols", type=_symbols, default=TEST_SYMBOLS)
    parser.add_argument("--duration-seconds", type=float, default=DEFAULT_DURATION_SECONDS)
    parser.add_argument("--interval-seconds", type=float, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".tmp" / "vn-proprietary-p0")
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    duration = max(0.0, min(float(args.duration_seconds), MAX_DURATION_SECONDS))
    interval = max(MIN_INTERVAL_SECONDS, float(args.interval_seconds))
    started = monotonic()
    results = [
        inspect_fiinquant(live=args.live, symbols=args.symbols),
        inspect_fiin(),
        inspect_vnstock(live=args.live, symbols=args.symbols, duration=duration, interval=interval),
    ]
    json_path, csv_path = _write_outputs(args.output_dir, results)
    payload = {
        "mode": "vn_proprietary_p0",
        "market_phase": market_phase(datetime.now().astimezone()),
        "live_requested": bool(args.live),
        "duration_seconds": duration,
        "interval_seconds": interval,
        "elapsed_ms": round((monotonic() - started) * 1_000),
        "providers": [_summary(result) for result in results],
        "artifacts": [] if args.cleanup else [str(json_path), str(csv_path)],
        "p1_gate_entered": any(
            result.capability in {"REALTIME", "NEAR_REALTIME_POLLING"} for result in results
        ),
    }
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True), flush=True)
    if args.cleanup:
        json_path.unlink(missing_ok=True)
        csv_path.unlink(missing_ok=True)
        try:
            args.output_dir.rmdir()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print(json.dumps({"mode": "vn_proprietary_p0", "status": "interrupted"}), flush=True)
        raise SystemExit(130)
