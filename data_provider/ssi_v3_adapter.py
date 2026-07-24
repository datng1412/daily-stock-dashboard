"""Disabled-by-default SSI FastConnect V3 REST adapter foundation.

The adapter imports and initializes the official SDK lazily.  Construction is
pure: no client, thread, authentication, or provider request exists until a
supported V3 capability is called after explicit configuration selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from threading import RLock
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple
from zoneinfo import ZoneInfo

import httpx

from data_provider.ssi_provider_models import ProviderDiagnostics, ProviderResult
from data_provider.ssi_v3_foreign_policy import (
    SSI_V3_FOREIGN_FINALITY_POLICY,
    normalize_foreign_value_rows,
)


SSI_V3_SOURCE = "SSI FastConnect V3"
SSI_V3_DEFAULT_API_URL = "https://api.ssi.com.vn/api/v3"
SSI_V3_PAGE_SIZE = 1000
SSI_V3_MAX_PAGES = 20
SSI_V3_MAX_ROWS = 5000
SSI_V3_DAILY_WINDOW_DAYS = 180
SSI_V3_DAILY_MAX_WINDOWS = 40
SSI_V3_DAILY_FRESHNESS_MAX_WEEKDAYS = 5
SSI_V3_SECURITIES_SUMMARY_PATH = "/api/v3/data/securitiesSummary"
_VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
_VALID_BOARDS = {"HOSE", "HNX", "UPCOM"}


class SsiV3MalformedResponse(RuntimeError):
    """Raised internally when the pinned SDK returns an invalid public shape."""


class SsiV3PaginationGuard(RuntimeError):
    """Raised internally when a bounded paging invariant is violated."""


@dataclass(frozen=True)
class SsiV3RestSettings:
    """Secret-safe configuration passed to the lazy SDK lifecycle."""

    enabled: bool = False
    client_id: Optional[str] = field(default=None, repr=False)
    api_key: Optional[str] = field(default=None, repr=False)
    api_secret: Optional[str] = field(default=None, repr=False)
    api_url: str = SSI_V3_DEFAULT_API_URL
    request_timeout: int = 10
    max_retries: int = 2
    retry_delay: float = 1.0
    rate_limit_per_second: int = 5

    @classmethod
    def from_config(cls, config: Any) -> "SsiV3RestSettings":
        return cls(
            enabled=bool(getattr(config, "ssi_v3_rest_enabled", False)),
            client_id=_optional_text(getattr(config, "ssi_v3_client_id", None)),
            api_key=_optional_text(getattr(config, "ssi_v3_api_key", None)),
            api_secret=_optional_text(getattr(config, "ssi_v3_api_secret", None)),
            api_url=(
                _optional_text(getattr(config, "ssi_v3_api_url", None))
                or SSI_V3_DEFAULT_API_URL
            ).rstrip("/"),
            request_timeout=int(getattr(config, "ssi_v3_request_timeout", 10)),
            max_retries=int(getattr(config, "ssi_v3_max_retries", 2)),
            retry_delay=float(getattr(config, "ssi_v3_retry_delay", 1.0)),
            rate_limit_per_second=int(
                getattr(config, "ssi_v3_rate_limit_per_second", 5)
            ),
        )

    @property
    def missing_required_names(self) -> Tuple[str, ...]:
        missing: List[str] = []
        for name, value in (
            ("SSI_V3_API_KEY", self.api_key),
            ("SSI_V3_API_SECRET", self.api_secret),
        ):
            if not value:
                missing.append(name)
        return tuple(missing)

    @property
    def sdk_api_url(self) -> str:
        """Return the SDK transport root; SDK endpoint constants include /api/v3."""
        suffix = "/api/v3"
        if self.api_url.lower().endswith(suffix):
            return self.api_url[: -len(suffix)]
        return self.api_url


def validate_v3_selection(settings: SsiV3RestSettings) -> None:
    """Reject disabled or incomplete V3 configuration without exposing values."""
    if not settings.enabled:
        raise ValueError("SSI V3 REST requires SSI_V3_REST_ENABLED=true")
    if settings.missing_required_names:
        raise ValueError(
            "SSI V3 REST configuration missing: "
            + ", ".join(settings.missing_required_names)
        )


def _optional_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _default_auth_factory(settings: SsiV3RestSettings) -> Any:
    from ssi_sdk import Auth, Config

    sdk_config = Config(
        client_id=settings.client_id or "",
        api_key=settings.api_key or "",
        api_secret=settings.api_secret or "",
        private_key="",
        api_url=settings.sdk_api_url,
        timeout=settings.request_timeout,
        max_retries=settings.max_retries,
        retry_delay=settings.retry_delay,
        rate_limit_per_second=settings.rate_limit_per_second,
        log_level="WARNING",
    )
    return Auth(sdk_config)


def _default_data_factory(auth: Any) -> Any:
    from ssi_sdk import Data

    return Data(auth)


def _value(row: Any, *names: str) -> Any:
    if isinstance(row, Mapping):
        for name in names:
            if name in row:
                return row[name]
        return None
    for name in names:
        if hasattr(row, name):
            return getattr(row, name)
    return None


def _field_presence(row: Any, name: str, normalized: Any) -> str:
    """Retain raw provider presence separately from its normalized value."""

    if isinstance(row, Mapping):
        if name not in row:
            return "FIELD_ABSENT"
        raw = row[name]
    elif not hasattr(row, name):
        return "FIELD_ABSENT"
    else:
        raw = getattr(row, name)
    if raw is None or raw == "":
        return "FIELD_NULL"
    if normalized is None:
        return "PARSE_FAILURE"
    return (
        "FIELD_PRESENT_EXPLICIT_ZERO"
        if normalized == 0
        else "FIELD_PRESENT_NONZERO"
    )


def _enum_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    raw = getattr(value, "value", value)
    text = str(raw).strip().upper()
    return text or None


def _number(value: Any, *, integer: bool = False) -> Optional[Any]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise SsiV3MalformedResponse("boolean provider field is not numeric")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SsiV3MalformedResponse("non-numeric provider field") from exc
    if not parsed.is_finite():
        raise SsiV3MalformedResponse("non-finite provider field")
    if integer:
        if parsed != parsed.to_integral_value():
            raise SsiV3MalformedResponse("non-integral provider field")
        return int(parsed)
    return float(parsed)


def _parse_date_value(value: Any) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise SsiV3MalformedResponse("malformed provider date")


def _parse_datetime_value(value: Any) -> Tuple[int, str]:
    text = str(value or "").strip()
    parsed: Optional[datetime] = None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        for fmt in (
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
        ):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        raise SsiV3MalformedResponse("malformed provider datetime")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_VN_TIMEZONE)
    local = parsed.astimezone(_VN_TIMEZONE)
    return int(local.timestamp()), local.isoformat()


def _provider_date(value: Optional[str], *, intraday: bool, end: bool = False) -> str:
    text = str(value or "").strip()
    parsed: Optional[datetime] = None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                parsed = datetime.combine(datetime.strptime(text, fmt).date(), datetime.min.time())
                break
            except ValueError:
                continue
    if parsed is None:
        raise ValueError("date must use YYYY-MM-DD or YYYY/MM/DD")
    if intraday:
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(_VN_TIMEZONE).replace(tzinfo=None)
        if parsed.time() == datetime.min.time() and end:
            parsed = parsed.replace(hour=23, minute=59, second=59)
        return parsed.strftime("%Y/%m/%d %H:%M:%S")
    return parsed.strftime("%Y/%m/%d")


def _previous_weekday(value: datetime) -> datetime:
    candidate = value
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def _latest_completed_daily_session(requested_to: str) -> str:
    requested = datetime.strptime(requested_to, "%Y/%m/%d").date()
    now = datetime.now(_VN_TIMEZONE)
    today = now.date()
    if requested < today:
        candidate = datetime.combine(requested, datetime.min.time())
    elif now.weekday() < 5 and now.hour >= 15:
        candidate = datetime.combine(today, datetime.min.time())
    else:
        candidate = datetime.combine(today - timedelta(days=1), datetime.min.time())
    return _previous_weekday(candidate).date().isoformat()


def _weekday_session_gap(older: str, newer: str) -> int:
    older_date = datetime.strptime(older, "%Y-%m-%d").date()
    newer_date = datetime.strptime(newer, "%Y-%m-%d").date()
    if older_date >= newer_date:
        return 0
    gap = 0
    candidate = older_date + timedelta(days=1)
    while candidate <= newer_date:
        if candidate.weekday() < 5:
            gap += 1
        candidate += timedelta(days=1)
    return gap


def _normalize_board(value: Any) -> str:
    board = str(value or "").strip().upper()
    if board not in _VALID_BOARDS:
        raise ValueError("board must be one of HOSE, HNX, or UPCOM")
    return board


def _sdk_board(value: str) -> Any:
    from ssi_sdk.enums import Board

    return Board(value)


def _ok_result(
    rows: List[Dict[str, Any]],
    *,
    pages_used: int = 1,
    duplicate_date_count: int = 0,
    diagnostics: Optional[Dict[str, Any]] = None,
) -> ProviderResult:
    result: ProviderResult = {
        "status": "ok",
        "source": SSI_V3_SOURCE,
        "rows": rows,
        "count": len(rows),
        "cached": False,
        "fetched_at": datetime.now().astimezone().isoformat(),
        "pages_used": pages_used,
        "duplicate_date_count": duplicate_date_count,
    }
    if diagnostics is not None:
        result["diagnostics"] = diagnostics
    return result


def _error_result(capability: str, exc: BaseException) -> ProviderResult:
    failure_class = "internal_error"
    status_code = getattr(exc, "status_code", None)
    class_names = {cls.__name__ for cls in type(exc).__mro__}
    if "AuthenticationError" in class_names:
        failure_class = "entitlement_unavailable" if status_code == 403 else "authentication_failed"
    elif "RateLimitError" in class_names or status_code == 429:
        failure_class = "rate_limited"
    elif isinstance(exc, httpx.TimeoutException):
        failure_class = "request_timeout"
    elif isinstance(exc, httpx.RequestError):
        failure_class = "network_error"
    elif "ValidationError" in class_names or isinstance(exc, ValueError):
        failure_class = "validation_error"
    elif isinstance(exc, (SsiV3MalformedResponse, SsiV3PaginationGuard)):
        failure_class = "malformed_response"
    elif "APIError" in class_names or "SSIError" in class_names:
        if status_code in {401, 403}:
            failure_class = "entitlement_unavailable" if status_code == 403 else "authentication_failed"
        elif isinstance(status_code, int) and status_code >= 500:
            failure_class = "provider_unavailable"
        else:
            failure_class = "provider_unavailable"
    reason_by_class = {
        "authentication_failed": "SSI V3 authentication failed.",
        "entitlement_unavailable": "SSI V3 entitlement is unavailable.",
        "request_timeout": "SSI V3 request timed out.",
        "network_error": "SSI V3 network request failed.",
        "rate_limited": "SSI V3 rate limit was reached.",
        "provider_unavailable": "SSI V3 provider is unavailable.",
        "malformed_response": "SSI V3 returned a malformed response.",
        "validation_error": "SSI V3 request validation failed.",
        "internal_error": "SSI V3 request failed internally.",
    }
    retry_after = getattr(exc, "retry_after", None)
    safe_status_code = status_code if isinstance(status_code, int) else None
    return {
        "status": "unavailable",
        "source": SSI_V3_SOURCE,
        "reason": reason_by_class[failure_class],
        "failure_class": failure_class,
        "rows": [],
        "count": 0,
        "cached": False,
        "fetched_at": datetime.now().astimezone().isoformat(),
        "diagnostics": {
            "capability": capability,
            "exception_class": type(exc).__name__,
            "http_status": safe_status_code,
            "rate_limit": {
                "limit": None,
                "remaining": None,
                "reset": None,
                "retry_after_seconds": retry_after,
            },
        },
    }


class SsiFastConnectV3Adapter:
    """Lazy synchronous adapter over official ``ssi-sdk==3.0.5`` clients."""

    def __init__(
        self,
        settings: SsiV3RestSettings,
        *,
        auth_factory: Callable[[SsiV3RestSettings], Any] = _default_auth_factory,
        data_factory: Callable[[Any], Any] = _default_data_factory,
    ) -> None:
        validate_v3_selection(settings)
        self._settings = settings
        self._auth_factory = auth_factory
        self._data_factory = data_factory
        self._lifecycle_lock = RLock()
        self._auth: Any = None
        self._data: Any = None
        self._symbol_board_cache: Dict[str, str] = {}
        self._closed = False

    @property
    def settings(self) -> SsiV3RestSettings:
        return self._settings

    @property
    def initialized(self) -> bool:
        return self._auth is not None and self._data is not None

    def _ensure_clients(self) -> Tuple[Any, Any]:
        if self._closed:
            raise RuntimeError("SSI V3 adapter is closed")
        if self.initialized:
            return self._auth, self._data
        with self._lifecycle_lock:
            if self._closed:
                raise RuntimeError("SSI V3 adapter is closed")
            if self.initialized:
                return self._auth, self._data
            auth: Any = None
            try:
                auth = self._auth_factory(self._settings)
                auth.authenticate()
                data = self._data_factory(auth)
            except Exception:
                if auth is not None:
                    close = getattr(auth, "close", None)
                    if callable(close):
                        close()
                raise
            self._auth = auth
            self._data = data
            return auth, data

    def _run(self, capability: str, operation: Callable[[Any, Any], ProviderResult]) -> ProviderResult:
        try:
            auth, data = self._ensure_clients()
            return operation(auth, data)
        except Exception as exc:
            return _error_result(capability, exc)

    def initialize_rest_access(self) -> ProviderResult:
        """Authenticate once and create the shared REST data client.

        This is intended for explicit, bounded diagnostics that need to
        distinguish authentication from later data operations. It returns only
        the normalized provider envelope and never exposes a token or client.
        """

        try:
            self._ensure_clients()
        except Exception as exc:
            return _error_result("authentication", exc)
        return _ok_result(
            [],
            diagnostics={
                "capability": "authentication",
                "client_id_supplied": bool(self._settings.client_id),
            },
        )

    @staticmethod
    def _security_row(item: Any) -> Dict[str, Any]:
        symbol = _optional_text(_value(item, "symbol"))
        if not symbol:
            raise SsiV3MalformedResponse("security symbol is missing")
        board = _enum_text(_value(item, "board"))
        listed_date_raw = _value(item, "first_trading_date", "firstTradingDate")
        return {
            "symbol": symbol.upper(),
            "exchange": board,
            "security_type": None,
            "name": _optional_text(_value(item, "symbol_name_vi", "symbolNameVi")),
            "name_en": _optional_text(_value(item, "symbol_name_en", "symbolNameEn")),
            "industry": _optional_text(_value(item, "icb_name", "icbName")),
            "icb_code": _optional_text(_value(item, "icb_code", "icbCode")),
            "icb_name": _optional_text(_value(item, "icb_name", "icbName")),
            "sector": None,
            "issuer": None,
            "lot_size": _number(_value(item, "lot_size", "lotSize"), integer=True),
            "listed_shares": _number(
                _value(item, "listed_shares", "listedShare"), integer=True
            ),
            "listed_date": _parse_date_value(listed_date_raw) if listed_date_raw else None,
            "market": board,
            "source": SSI_V3_SOURCE,
        }

    @staticmethod
    def _ohlc_row(item: Any, *, intraday: bool, symbol: str) -> Dict[str, Any]:
        trading_date = _value(item, "trading_date", "tradingDate")
        common = {
            "open": _number(_value(item, "open_price", "open")),
            "high": _number(_value(item, "high_price", "high")),
            "low": _number(_value(item, "low_price", "low")),
            "close": _number(_value(item, "close_price", "close")),
            "volume": _number(_value(item, "volume"), integer=True),
            "value": _number(_value(item, "value")),
            "source": SSI_V3_SOURCE,
        }
        if intraday:
            timestamp, date_time = _parse_datetime_value(trading_date)
            return {
                "timestamp": timestamp,
                "date_time": date_time,
                **common,
                "ticker": symbol,
            }
        return {"date": _parse_date_value(trading_date), **common}

    @staticmethod
    def _index_definition_row(item: Any) -> Dict[str, Any]:
        index_code = _optional_text(_value(item, "index"))
        if not index_code:
            raise SsiV3MalformedResponse("index identifier is missing")
        board = _enum_text(_value(item, "board"))
        return {
            "index_id": index_code.upper(),
            "index_code": index_code.upper(),
            "index_name": _optional_text(_value(item, "index_name", "indexName")),
            "exchange": board,
            "market": board,
            "source": SSI_V3_SOURCE,
        }

    @staticmethod
    def _index_summary_row(item: Any, *, board: str, index_code: Optional[str]) -> Dict[str, Any]:
        prop_buy_volume = _number(
            _value(item, "total_prop_buy", "totalPropBuy"), integer=True
        )
        prop_sell_volume = _number(
            _value(item, "total_prop_sell", "totalPropSell"), integer=True
        )
        prop_buy_value = _number(
            _value(item, "total_prop_buy_value", "totalPropBuyValue")
        )
        prop_sell_value = _number(
            _value(item, "total_prop_sell_value", "totalPropSellValue")
        )
        return {
            "date": _parse_date_value(_value(item, "trading_date", "tradingDate")),
            "index_code": index_code,
            "index_value": _number(_value(item, "index_value", "indexValue")),
            "change": _number(_value(item, "index_change", "indexChange")),
            "change_pct": _number(
                _value(item, "index_change_percent", "indexChangePercentage")
            ),
            "total_volume": _number(_value(item, "total_trade", "totalTrade"), integer=True),
            "total_value": _number(_value(item, "total_trade_value", "totalTradeValue")),
            "matched_volume": _number(_value(item, "total_match", "totalMatch"), integer=True),
            "matched_value": _number(_value(item, "total_match_value", "totalMatchValue")),
            "put_through_volume": _number(_value(item, "total_deal", "totalDeal"), integer=True),
            "put_through_value": _number(_value(item, "total_deal_value", "totalDealValue")),
            "advances": _number(
                _value(item, "total_advance_stock", "totalAdvanceStock"), integer=True
            ),
            "unchanged": _number(
                _value(item, "total_steady_stock", "totalNoChangeStock"), integer=True
            ),
            "declines": _number(
                _value(item, "total_decline_stock", "totalDeclineStock"), integer=True
            ),
            "ceiling": _number(
                _value(item, "total_ceiling_stock", "totalCeilingStock"), integer=True
            ),
            "floor": _number(
                _value(item, "total_floor_stock", "totalFloorStock"), integer=True
            ),
            "proprietary_buy_volume": prop_buy_volume,
            "proprietary_sell_volume": prop_sell_volume,
            "proprietary_net_volume": (
                prop_buy_volume - prop_sell_volume
                if prop_buy_volume is not None and prop_sell_volume is not None
                else None
            ),
            "proprietary_buy_value": prop_buy_value,
            "proprietary_sell_value": prop_sell_value,
            "proprietary_net_value": (
                prop_buy_value - prop_sell_value
                if prop_buy_value is not None and prop_sell_value is not None
                else None
            ),
            "trading_session": None,
            "exchange": board,
            "source": SSI_V3_SOURCE,
        }

    @staticmethod
    def _summary_page(
        payload: Any,
    ) -> Tuple[List[Mapping[str, Any]], Optional[int], Optional[int]]:
        """Extract the documented V3 summary envelope without SDK model loss.

        ``ssi-sdk==3.0.5`` exposes the official authenticated REST transport,
        while its ``SecuritiesSummary`` model currently omits the four foreign
        gross fields.  B3 therefore reads only the documented ``data`` envelope
        from that public transport and keeps the raw dictionaries inside this
        adapter.
        """

        if isinstance(payload, Mapping):
            if "data" not in payload:
                raise SsiV3MalformedResponse("securities summary data envelope is missing")
            data = payload["data"]
            pages_count_raw = payload.get("pagesCount")
            total_count_raw = next(
                (
                    payload.get(name)
                    for name in ("totalCount", "totalRecords", "recordsTotal", "count")
                    if payload.get(name) is not None
                ),
                None,
            )
        elif hasattr(payload, "data"):
            data = getattr(payload, "data")
            pages_count_raw = getattr(payload, "pages_count", None)
            if pages_count_raw is None:
                pages_count_raw = getattr(payload, "pagesCount", None)
            total_count_raw = next(
                (
                    getattr(payload, name, None)
                    for name in (
                        "total_count",
                        "totalCount",
                        "total_records",
                        "totalRecords",
                        "recordsTotal",
                        "count",
                    )
                    if getattr(payload, name, None) is not None
                ),
                None,
            )
        else:
            raise SsiV3MalformedResponse("expected securities summary data envelope")
        if not isinstance(data, list):
            raise SsiV3MalformedResponse("securities summary data must be a list")
        if any(not isinstance(item, Mapping) for item in data):
            raise SsiV3MalformedResponse("securities summary row must be an object")
        pages_count = _number(pages_count_raw, integer=True)
        if pages_count is not None and pages_count < 0:
            raise SsiV3MalformedResponse("securities summary pagesCount is negative")
        total_count = _number(total_count_raw, integer=True)
        if total_count is not None and total_count < 0:
            raise SsiV3MalformedResponse("securities summary total count is negative")
        return data, pages_count, total_count

    @staticmethod
    def _summary_row(
        item: Mapping[str, Any],
        *,
        expected_symbol: Optional[str],
    ) -> Dict[str, Any]:
        symbol = _optional_text(_value(item, "symbol"))
        if not symbol:
            raise SsiV3MalformedResponse("securities summary symbol is missing")
        symbol = symbol.upper()
        if expected_symbol is not None and symbol != expected_symbol:
            raise SsiV3MalformedResponse("securities summary symbol does not match request")

        foreign_buy_volume = _number(
            _value(item, "totalForeignBuy"), integer=True
        )
        foreign_sell_volume = _number(
            _value(item, "totalForeignSell"), integer=True
        )
        foreign_buy_value = _number(_value(item, "totalForeignBuyValue"))
        foreign_sell_value = _number(_value(item, "totalForeignSellValue"))
        foreign_field_presence = {
            "foreign_buy_volume": _field_presence(
                item, "totalForeignBuy", foreign_buy_volume
            ),
            "foreign_sell_volume": _field_presence(
                item, "totalForeignSell", foreign_sell_volume
            ),
            "foreign_buy_value": _field_presence(
                item, "totalForeignBuyValue", foreign_buy_value
            ),
            "foreign_sell_value": _field_presence(
                item, "totalForeignSellValue", foreign_sell_value
            ),
        }
        foreign_net_volume = (
            foreign_buy_volume - foreign_sell_volume
            if foreign_buy_volume is not None and foreign_sell_volume is not None
            else None
        )
        foreign_net_value = (
            foreign_buy_value - foreign_sell_value
            if foreign_buy_value is not None and foreign_sell_value is not None
            else None
        )
        return {
            "symbol": symbol,
            "date": _parse_date_value(_value(item, "tradingDate")),
            "reference_price": None,
            "ceiling_price": None,
            "floor_price": None,
            "open": _number(_value(item, "open")),
            "high": _number(_value(item, "high")),
            "low": _number(_value(item, "low")),
            "close": _number(_value(item, "close")),
            "adjusted_close": None,
            "matched_volume": _number(_value(item, "totalMatch"), integer=True),
            "matched_value": _number(_value(item, "totalMatchValue")),
            "put_through_volume": _number(_value(item, "totalDeal"), integer=True),
            "put_through_value": _number(_value(item, "totalDealValue")),
            "average_price": _number(_value(item, "average")),
            "price_change": _number(_value(item, "priceChange")),
            "price_change_pct": _number(_value(item, "priceChangePercentage")),
            "total_volume": None,
            "total_value": None,
            "remaining_foreign_room": _number(
                _value(item, "remainForeignRoom"), integer=True
            ),
            "total_foreign_room": _number(
                _value(item, "totalForeignRoom"), integer=True
            ),
            "foreign_buy_volume": foreign_buy_volume,
            "foreign_sell_volume": foreign_sell_volume,
            "foreign_net_volume": foreign_net_volume,
            "foreign_buy_value": foreign_buy_value,
            "foreign_sell_value": foreign_sell_value,
            "foreign_net_value": foreign_net_value,
            "_foreign_net_volume_source": (
                "derived" if foreign_net_volume is not None else None
            ),
            "_foreign_net_value_source": (
                "derived" if foreign_net_value is not None else None
            ),
            "_foreign_field_presence": foreign_field_presence,
            "source": SSI_V3_SOURCE,
            "source_version": "v3",
        }

    def _paged_summary(
        self,
        auth: Any,
        *,
        symbol: Optional[str],
        index: Optional[str],
        from_value: str,
        to_value: str,
        page_index: int,
        page_size: int,
        limit: int,
        exhaust_pages: bool,
    ) -> ProviderResult:
        effective_page_size = min(page_size, limit)
        normalized_rows: List[Dict[str, Any]] = []
        previous_fingerprint: Optional[Tuple[str, ...]] = None
        pages_used = 0
        current_page = page_index
        page_row_counts: List[int] = []
        page_date_bounds: List[Dict[str, Any]] = []
        provider_reported_total_count: Optional[int] = None
        for _ in range(SSI_V3_MAX_PAGES):
            if current_page > SSI_V3_MAX_PAGES:
                raise SsiV3PaginationGuard("maximum page bound exceeded")
            params: Dict[str, Any] = {
                "from": from_value,
                "to": to_value,
                "pageIndex": current_page,
                "pageSize": effective_page_size,
            }
            if symbol is not None:
                params["symbol"] = symbol
            else:
                assert index is not None
                params["index"] = index
            payload = auth.rest_client.get(
                SSI_V3_SECURITIES_SUMMARY_PATH,
                params=params,
            )
            page_rows, pages_count, total_count = self._summary_page(payload)
            pages_used += 1
            page_row_counts.append(len(page_rows))
            if total_count is not None:
                provider_reported_total_count = total_count
            if not page_rows:
                page_date_bounds.append(
                    {"page_index": current_page, "row_count": 0, "min_date": None, "max_date": None}
                )
                break
            fingerprint = tuple(repr(item) for item in page_rows)
            if fingerprint == previous_fingerprint:
                raise SsiV3PaginationGuard("repeated securities summary page")
            previous_fingerprint = fingerprint
            normalized_page = [
                self._summary_row(item, expected_symbol=symbol) for item in page_rows
            ]
            normalized_rows.extend(normalized_page)
            page_dates = sorted(
                str(row["date"]) for row in normalized_page if row.get("date")
            )
            page_date_bounds.append(
                {
                    "page_index": current_page,
                    "row_count": len(normalized_page),
                    "min_date": page_dates[0] if page_dates else None,
                    "max_date": page_dates[-1] if page_dates else None,
                }
            )
            if len(normalized_rows) > SSI_V3_MAX_ROWS:
                raise SsiV3PaginationGuard("maximum row bound exceeded")
            if pages_count is not None and pages_count > 0 and current_page >= pages_count:
                break
            if (
                not exhaust_pages
                and (pages_count is None or pages_count <= 0)
                and len(normalized_rows) >= limit
            ):
                break
            if (pages_count is None or pages_count <= 0) and len(page_rows) < effective_page_size:
                break
            current_page += 1
        else:
            raise SsiV3PaginationGuard("maximum page bound exceeded")

        key_names = ("date",) if symbol is not None else ("symbol", "date")
        deduped: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
        for row in normalized_rows:
            deduped[tuple(row[name] for name in key_names)] = row
        duplicate_count = len(normalized_rows) - len(deduped)
        rows = sorted(
            deduped.values(),
            key=lambda row: (row["date"], row["symbol"]),
        )
        if len(rows) > limit:
            rows = rows[-limit:]
        return _ok_result(
            rows,
            pages_used=pages_used,
            duplicate_date_count=duplicate_count,
            diagnostics={
                "capability": "securities_summary",
                "source_version": "v3",
                "implementation_status": "implemented",
                "units_verified": False,
                "finality_verified": False,
                "requested_from": from_value,
                "requested_to": to_value,
                "page_count": pages_used,
                "page_row_counts": page_row_counts,
                "page_date_bounds": page_date_bounds,
                "provider_reported_total_count": provider_reported_total_count,
                "provider_row_count": len(normalized_rows),
                "normalized_row_count": len(rows),
                "min_date": rows[0]["date"] if rows else None,
                "max_date": rows[-1]["date"] if rows else None,
                "duplicate_dates": duplicate_count,
                "sort_order": "trading_date_ascending",
            },
        )

    def _normalize_list(self, payload: Any, mapper: Callable[[Any], Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(payload, list):
            raise SsiV3MalformedResponse("expected SDK list response")
        return [mapper(item) for item in payload]

    def _paged_ohlc(
        self,
        market_data: Any,
        *,
        method_name: str,
        symbol: str,
        from_value: str,
        to_value: str,
        limit: int,
        intraday: bool,
    ) -> ProviderResult:
        safe_limit = int(limit)
        if safe_limit < 1 or safe_limit > SSI_V3_MAX_ROWS:
            raise ValueError(f"limit must be between 1 and {SSI_V3_MAX_ROWS}")
        method = getattr(market_data, method_name)
        page_size = min(safe_limit, SSI_V3_PAGE_SIZE)
        rows: List[Dict[str, Any]] = []
        previous_fingerprint: Optional[Tuple[str, ...]] = None
        pages_used = 0
        for page in range(1, SSI_V3_MAX_PAGES + 1):
            payload = method(symbol, from_value, to_value, page=page, size=page_size)
            if not isinstance(payload, list):
                raise SsiV3MalformedResponse("expected SDK OHLC list response")
            pages_used = page
            if not payload:
                break
            fingerprint = tuple(repr(item) for item in payload)
            if previous_fingerprint == fingerprint:
                raise SsiV3PaginationGuard("repeated SDK page")
            previous_fingerprint = fingerprint
            normalized = [
                self._ohlc_row(item, intraday=intraday, symbol=symbol)
                for item in payload
            ]
            rows.extend(normalized)
            if len(rows) > SSI_V3_MAX_ROWS:
                raise SsiV3PaginationGuard("maximum row bound exceeded")
            if len(rows) >= safe_limit:
                break
            if len(payload) < page_size:
                break
        else:
            raise SsiV3PaginationGuard("maximum page bound exceeded")
        key_name = "timestamp" if intraday else "date"
        deduped: Dict[Any, Dict[str, Any]] = {}
        for row in rows:
            deduped[row.get(key_name)] = row
        normalized_rows = sorted(
            deduped.values(),
            key=lambda row: row.get(key_name) or 0,
        )
        if len(normalized_rows) > safe_limit:
            normalized_rows = normalized_rows[-safe_limit:]
        return _ok_result(
            normalized_rows,
            pages_used=pages_used,
            duplicate_date_count=len(rows) - len(deduped),
        )

    def get_securities(self, market: Optional[str] = None) -> ProviderResult:
        return self.get_securities_filtered(board=market)

    def get_securities_filtered(
        self,
        *,
        symbol: Optional[str] = None,
        board: Optional[str] = None,
        index: Optional[str] = None,
    ) -> ProviderResult:
        """Apply the official exactly-one-filter securities contract."""

        try:
            filters = [value for value in (symbol, board, index) if str(value or "").strip()]
            if len(filters) != 1:
                raise ValueError("exactly one of symbol, board, or index is required")
            if symbol:
                normalized_symbol = str(symbol).strip().upper()
                normalized_board = None
                normalized_index = None
            elif board:
                normalized_symbol = None
                normalized_board = _normalize_board(board)
                normalized_index = None
            else:
                normalized_symbol = None
                normalized_board = None
                normalized_index = str(index).strip().upper()
        except Exception as exc:
            return _error_result("securities_filter", exc)

        def operation(_auth: Any, data: Any) -> ProviderResult:
            if normalized_symbol:
                payload = data.market_data.get_securities_info(normalized_symbol)
                rows = [] if payload is None else [self._security_row(payload)]
            elif normalized_board:
                payload = data.market_data.get_securities_info_by_board(
                    _sdk_board(normalized_board)
                )
                rows = self._normalize_list(payload, self._security_row)
            else:
                assert normalized_index is not None
                payload = data.market_data.get_securities_info_by_index(normalized_index)
                rows = self._normalize_list(payload, self._security_row)
            return _ok_result(rows)

        return self._run("securities_filter", operation)

    def get_security_basic_info(self, symbol: str) -> ProviderResult:
        result = self.get_securities_filtered(symbol=symbol)
        if result.get("status") == "ok":
            for row in result.get("rows") or []:
                if not isinstance(row, Mapping):
                    continue
                normalized_symbol = str(row.get("symbol") or "").strip().upper()
                board = _enum_text(row.get("exchange") or row.get("market"))
                if normalized_symbol and board in _VALID_BOARDS:
                    self._symbol_board_cache[normalized_symbol] = board
        return result

    def get_securities_by_index(self, index_code: str) -> ProviderResult:
        return self.get_securities_filtered(index=index_code)

    def get_daily_ohlcv(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
        force_refresh: bool = False,
    ) -> ProviderResult:
        del force_refresh
        try:
            normalized = str(symbol or "").strip().upper()
            if not normalized:
                raise ValueError("symbol is required")
            safe_limit = int(limit)
            if safe_limit < 1 or safe_limit > SSI_V3_MAX_ROWS:
                raise ValueError(f"limit must be between 1 and {SSI_V3_MAX_ROWS}")
            end_date = to_date or datetime.now(_VN_TIMEZONE).date().isoformat()
            end_value = _provider_date(end_date, intraday=False)
            if from_date:
                start_value = _provider_date(from_date, intraday=False)
            else:
                end_day = datetime.strptime(end_value, "%Y/%m/%d").date()
                start_value = (end_day - timedelta(days=max(safe_limit * 2, 365))).strftime(
                    "%Y/%m/%d"
                )
            if start_value > end_value:
                raise ValueError("from_date must not be after to_date")
        except Exception as exc:
            return _error_result("daily_ohlcv", exc)

        start_day = datetime.strptime(start_value, "%Y/%m/%d").date()
        end_day = datetime.strptime(end_value, "%Y/%m/%d").date()
        window_end = end_day
        summary_rows: List[Dict[str, Any]] = []
        window_diagnostics: List[Dict[str, Any]] = []
        page_row_counts: List[int] = []
        page_date_bounds: List[Dict[str, Any]] = []
        page_count = 0
        provider_row_count = 0
        provider_total_counts: List[int] = []
        duplicate_dates = 0
        reached_requested_start = False

        for window_index in range(1, SSI_V3_DAILY_MAX_WINDOWS + 1):
            window_start = max(
                start_day,
                window_end - timedelta(days=SSI_V3_DAILY_WINDOW_DAYS - 1),
            )
            summary = self.get_securities_summary(
                symbol=normalized,
                from_date=window_start.isoformat(),
                to_date=window_end.isoformat(),
                limit=safe_limit,
                exhaust_pages=True,
            )
            if summary.get("status") != "ok":
                return summary
            diagnostics = dict(summary.get("diagnostics") or {})
            rows = [
                dict(row)
                for row in summary.get("rows") or []
                if isinstance(row, Mapping)
            ]
            summary_rows.extend(rows)
            page_count += int(summary.get("pages_used") or diagnostics.get("page_count") or 0)
            provider_row_count += int(
                diagnostics.get("provider_row_count")
                if diagnostics.get("provider_row_count") is not None
                else len(rows)
            )
            duplicate_dates += int(summary.get("duplicate_date_count") or 0)
            page_row_counts.extend(
                int(value) for value in diagnostics.get("page_row_counts") or []
            )
            for bounds in diagnostics.get("page_date_bounds") or []:
                if isinstance(bounds, Mapping):
                    page_date_bounds.append(
                        {"window_index": window_index, **dict(bounds)}
                    )
            reported_total = diagnostics.get("provider_reported_total_count")
            if reported_total is not None:
                provider_total_counts.append(int(reported_total))
            window_diagnostics.append(
                {
                    "window_index": window_index,
                    "requested_from": window_start.isoformat(),
                    "requested_to": window_end.isoformat(),
                    "page_count": int(
                        summary.get("pages_used") or diagnostics.get("page_count") or 0
                    ),
                    "provider_row_count": int(
                        diagnostics.get("provider_row_count")
                        if diagnostics.get("provider_row_count") is not None
                        else len(rows)
                    ),
                    "normalized_row_count": len(rows),
                    "min_date": diagnostics.get("min_date"),
                    "max_date": diagnostics.get("max_date"),
                    "provider_reported_total_count": reported_total,
                }
            )
            reached_requested_start = window_start <= start_day
            if len({row.get("date") for row in summary_rows if row.get("date")}) >= safe_limit:
                break
            if reached_requested_start:
                break
            window_end = window_start - timedelta(days=1)
        else:
            return _error_result(
                "daily_ohlcv",
                SsiV3PaginationGuard("daily history maximum window bound exceeded"),
            )

        deduped: Dict[str, Dict[str, Any]] = {}
        for row in summary_rows:
            row_date = str(row.get("date") or "")
            if row_date:
                deduped[row_date] = row
        duplicate_dates += len(summary_rows) - len(deduped)
        normalized_summary_rows = sorted(
            deduped.values(), key=lambda row: str(row.get("date") or "")
        )
        if len(normalized_summary_rows) > safe_limit:
            normalized_summary_rows = normalized_summary_rows[-safe_limit:]

        latest_completed_session = _latest_completed_daily_session(end_value)
        min_date = (
            str(normalized_summary_rows[0].get("date"))
            if normalized_summary_rows
            else None
        )
        max_date = (
            str(normalized_summary_rows[-1].get("date"))
            if normalized_summary_rows
            else None
        )
        freshness_gap = (
            _weekday_session_gap(max_date, latest_completed_session)
            if max_date is not None
            else None
        )
        freshness_status = (
            "fresh"
            if freshness_gap is not None
            and freshness_gap <= SSI_V3_DAILY_FRESHNESS_MAX_WEEKDAYS
            else "stale"
            if max_date is not None
            else "unavailable"
        )
        provider_total_count = (
            sum(provider_total_counts) if provider_total_counts else None
        )
        incomplete_provider_count = (
            provider_total_count is not None
            and provider_total_count > provider_row_count
        )
        complete = (
            bool(normalized_summary_rows)
            and freshness_status == "fresh"
            and not incomplete_provider_count
            and (
                reached_requested_start
                or len(normalized_summary_rows) >= safe_limit
            )
        )
        candles = [
            {
                "date": row.get("date"),
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("matched_volume"),
                "value": row.get("matched_value"),
                "source": SSI_V3_SOURCE,
            }
            for row in normalized_summary_rows
            if isinstance(row, Mapping)
        ]
        result = _ok_result(
            candles,
            pages_used=page_count,
            duplicate_date_count=duplicate_dates,
            diagnostics={
                "capability": "daily_ohlcv",
                "source_version": "v3",
                "source_endpoint": "securitiesSummary",
                "adapter": type(self).__name__,
                "requested_from": start_day.isoformat(),
                "requested_to": end_day.isoformat(),
                "page_count": page_count,
                "window_count": len(window_diagnostics),
                "windows": window_diagnostics,
                "page_row_counts": page_row_counts,
                "page_date_bounds": page_date_bounds,
                "provider_reported_total_count": provider_total_count,
                "provider_row_count": provider_row_count,
                "normalized_row_count": len(candles),
                "min_date": min_date,
                "max_date": max_date,
                "duplicate_dates": duplicate_dates,
                "latest_completed_session": latest_completed_session,
                "freshness_gap_weekdays": freshness_gap,
                "freshness_max_weekdays": SSI_V3_DAILY_FRESHNESS_MAX_WEEKDAYS,
                "freshness_status": freshness_status,
                "cache_hit": False,
                "cache_source": "provider",
                "complete": complete,
                "sort_order": "trading_date_ascending",
                "volume_semantics": "matched_volume",
                "value_semantics": "matched_value",
                "provider_timestamp_semantics": "trading_date_only",
            },
        )
        if not complete:
            result["status"] = "partial" if candles else "unavailable"
            result["reason"] = (
                "SSI V3 daily history is incomplete or stale."
                if candles
                else "SSI V3 daily history returned no rows."
            )
            result["failure_class"] = "incomplete_daily_history"
        return result

    def get_completed_intraday_1m(self, symbol: str, trading_date: str) -> ProviderResult:
        try:
            normalized = str(symbol or "").strip().upper()
            if not normalized:
                raise ValueError("symbol is required")
            from_value = _provider_date(trading_date, intraday=True)
            to_value = _provider_date(trading_date, intraday=True, end=True)
            requested_day = datetime.strptime(from_value, "%Y/%m/%d %H:%M:%S").date()
            today = datetime.now(_VN_TIMEZONE).date()
            if requested_day > today:
                raise ValueError("intraday date must not be in the future")
        except Exception as exc:
            return _error_result("completed_historical_intraday_ohlcv", exc)

        def operation(_auth: Any, data: Any) -> ProviderResult:
            if requested_day == today:
                payload = data.market_data.get_ohlc_1minute(normalized)
                rows = self._normalize_list(
                    payload,
                    lambda item: self._ohlc_row(item, intraday=True, symbol=normalized),
                )
                selected = [
                    row
                    for row in rows
                    if str(row.get("date_time") or "").startswith(requested_day.isoformat())
                ]
                deduped = {
                    row.get("timestamp"): row
                    for row in selected
                    if row.get("timestamp") is not None
                }
                normalized_rows = sorted(
                    deduped.values(), key=lambda row: row.get("timestamp") or 0
                )
                return _ok_result(
                    normalized_rows[-SSI_V3_PAGE_SIZE:],
                    pages_used=1,
                    duplicate_date_count=len(selected) - len(deduped),
                )
            return self._paged_ohlc(
                data.market_data,
                method_name="get_ohlc_1minute_historical",
                symbol=normalized,
                from_value=from_value,
                to_value=to_value,
                limit=SSI_V3_PAGE_SIZE,
                intraday=True,
            )

        capability = (
            "current_session_intraday"
            if requested_day == today
            else "completed_historical_intraday_ohlcv"
        )
        return self._run(capability, operation)

    def get_securities_summary(
        self,
        *,
        symbol: Optional[str] = None,
        index: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page_index: int = 1,
        page_size: int = SSI_V3_PAGE_SIZE,
        limit: int = 260,
        exhaust_pages: bool = False,
    ) -> ProviderResult:
        """Normalize one symbol or index through authenticated raw V3 REST."""

        try:
            filters = [
                value for value in (symbol, index) if str(value or "").strip()
            ]
            if len(filters) != 1:
                raise ValueError("exactly one of symbol or index is required")
            normalized_symbol = str(symbol).strip().upper() if symbol else None
            normalized_index = str(index).strip().upper() if index else None
            if isinstance(page_index, bool) or not isinstance(page_index, int):
                raise ValueError("page_index must be an integer")
            if page_index < 1 or page_index > SSI_V3_MAX_PAGES:
                raise ValueError(
                    f"page_index must be between 1 and {SSI_V3_MAX_PAGES}"
                )
            if isinstance(page_size, bool) or not isinstance(page_size, int):
                raise ValueError("page_size must be an integer")
            if page_size < 1 or page_size > SSI_V3_PAGE_SIZE:
                raise ValueError(
                    f"page_size must be between 1 and {SSI_V3_PAGE_SIZE}"
                )
            if isinstance(limit, bool) or not isinstance(limit, int):
                raise ValueError("limit must be an integer")
            if limit < 1 or limit > SSI_V3_MAX_ROWS:
                raise ValueError(f"limit must be between 1 and {SSI_V3_MAX_ROWS}")

            today = datetime.now(_VN_TIMEZONE).date().isoformat()
            if from_date is None and to_date is None:
                start_value = end_value = _provider_date(today, intraday=False)
            else:
                end_value = _provider_date(to_date or today, intraday=False)
                start_value = _provider_date(from_date or to_date, intraday=False)
            if start_value > end_value:
                raise ValueError("from_date must not be after to_date")
        except Exception as exc:
            return _error_result("securities_summary", exc)

        def operation(auth: Any, _data: Any) -> ProviderResult:
            return self._paged_summary(
                auth,
                symbol=normalized_symbol,
                index=normalized_index,
                from_value=start_value,
                to_value=end_value,
                page_index=page_index,
                page_size=page_size,
                limit=limit,
                exhaust_pages=exhaust_pages,
            )

        return self._run("securities_summary", operation)

    def get_securities_summary_by_index(
        self,
        index_code: str,
        *,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page_index: int = 1,
        page_size: int = SSI_V3_PAGE_SIZE,
        limit: int = 260,
    ) -> ProviderResult:
        """Expose direct index normalization without market-wide fan-out."""

        return self.get_securities_summary(
            index=index_code,
            from_date=from_date,
            to_date=to_date,
            page_index=page_index,
            page_size=page_size,
            limit=limit,
            exhaust_pages=True,
        )

    def get_market_summary(
        self,
        scope: str,
        identifier: str,
        *,
        trading_date: Optional[str] = None,
    ) -> ProviderResult:
        """Return the official V3 board/index summary without conflating scopes."""

        try:
            normalized_scope = str(scope or "").strip().lower()
            normalized_identifier = str(identifier or "").strip().upper()
            if normalized_scope not in {"board", "index"}:
                raise ValueError("scope must be board or index")
            if not normalized_identifier:
                raise ValueError("identifier is required")
            normalized_board = (
                _normalize_board(normalized_identifier)
                if normalized_scope == "board"
                else None
            )
            provider_date = (
                _provider_date(trading_date, intraday=False)
                if trading_date
                else None
            )
        except Exception as exc:
            return _error_result("market_summary", exc)

        def operation(_auth: Any, data: Any) -> ProviderResult:
            if normalized_scope == "board":
                board_value = _sdk_board(normalized_board)
                payload = (
                    data.market_data.get_board_summary_historical(
                        board_value, provider_date
                    )
                    if provider_date
                    else data.market_data.get_board_summary(board_value)
                )
                board = normalized_board
                index_code = None
            else:
                payload = (
                    data.market_data.get_index_summary_historical(
                        normalized_identifier, provider_date
                    )
                    if provider_date
                    else data.market_data.get_index_summary(normalized_identifier)
                )
                board = None
                index_code = normalized_identifier
            rows = [] if payload is None else [
                self._index_summary_row(
                    payload,
                    board=board,
                    index_code=index_code,
                )
            ]
            return _ok_result(
                rows,
                diagnostics={
                    "capability": "market_summary",
                    "scope": normalized_scope,
                    "identifier": normalized_identifier,
                    "provider_endpoint": "indexSummary",
                },
            )

        return self._run("market_summary", operation)

    def get_index_list(
        self,
        market: Optional[str] = None,
        force_refresh: bool = False,
    ) -> ProviderResult:
        del force_refresh

        try:
            normalized_board = (
                _normalize_board(market) if market is not None and str(market).strip() else None
            )
        except Exception as exc:
            return _error_result("index_list", exc)

        def operation(_auth: Any, data: Any) -> ProviderResult:
            if normalized_board is None:
                payload = data.market_data.get_indexes()
            else:
                payload = data.market_data.get_indexes_by_board(_sdk_board(normalized_board))
            return _ok_result(self._normalize_list(payload, self._index_definition_row))

        return self._run("index_list", operation)

    def get_index_summary(
        self,
        board: str,
        index_code: Optional[str] = None,
        trading_date: Optional[str] = None,
    ) -> ProviderResult:
        try:
            normalized_index = str(index_code or board or "").strip().upper()
            if not normalized_index:
                raise ValueError("index_code is required")
            normalized_board = {
                "VNINDEX": "HOSE",
                "VN30": "HOSE",
                "HNXINDEX": "HNX",
                "HNX": "HNX",
                "HNX30": "HNX",
                "UPCOMINDEX": "UPCOM",
                "UPCOM": "UPCOM",
            }.get(normalized_index)
            params: Dict[str, Any] = {"index": normalized_index}
            if trading_date:
                params["tradingDate"] = _provider_date(trading_date, intraday=False)
        except Exception as exc:
            return _error_result("index_summary", exc)

        def operation(auth: Any, _data: Any) -> ProviderResult:
            payload = auth.rest_client.get("/api/v3/data/indexSummary", params=params)
            rows = self._normalize_list(
                payload,
                lambda item: self._index_summary_row(
                    item,
                    board=normalized_board,
                    index_code=normalized_index,
                ),
            )
            return _ok_result(rows)

        return self._run("index_summary", operation)

    def get_security_metadata(
        self,
        symbol: Optional[str] = None,
        market: Optional[str] = None,
    ) -> ProviderResult:
        if symbol:
            return self.get_security_basic_info(symbol)
        if market:
            return self.get_securities(market=market)
        return _error_result(
            "security_metadata",
            ValueError("symbol or market is required"),
        )

    def get_intraday_ohlcv(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 64,
        interval: Optional[str] = None,
    ) -> ProviderResult:
        del from_date
        try:
            if isinstance(limit, bool):
                raise ValueError("limit must be an integer")
            safe_limit = int(limit)
            if safe_limit < 1 or safe_limit > SSI_V3_MAX_ROWS:
                raise ValueError(f"limit must be between 1 and {SSI_V3_MAX_ROWS}")
        except (TypeError, ValueError) as exc:
            return _error_result("current_session_intraday", exc)
        if interval not in (None, "1m", "1min", "1minute"):
            return _error_result(
                "current_session_intraday",
                ValueError("V3 product contract supports interval=1m only"),
            )
        selected_date = to_date or datetime.now(_VN_TIMEZONE).date().isoformat()
        result = self.get_completed_intraday_1m(symbol, selected_date)
        if result.get("status") == "ok" and len(result.get("rows") or []) > safe_limit:
            result = dict(result)
            result["rows"] = list(result.get("rows") or [])[-safe_limit:]
            result["count"] = len(result["rows"])
        return result

    def get_daily_stock_price(
        self,
        symbol: str,
        market: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
    ) -> ProviderResult:
        try:
            normalized_symbol = str(symbol or "").strip().upper()
            if not normalized_symbol:
                raise ValueError("symbol is required")
            if isinstance(limit, bool):
                raise ValueError("limit must be an integer")
            safe_limit = int(limit)
            if safe_limit < 1 or safe_limit > SSI_V3_MAX_ROWS:
                raise ValueError(f"limit must be between 1 and {SSI_V3_MAX_ROWS}")
            normalized_board = (
                _normalize_board(market)
                if market is not None and str(market).strip()
                else self._symbol_board_cache.get(normalized_symbol)
            )
        except (TypeError, ValueError) as exc:
            return _error_result("daily_stock_price", exc)

        if normalized_board is None:
            metadata = self.get_security_basic_info(normalized_symbol)
            if metadata.get("status") != "ok":
                return metadata
            normalized_board = self._symbol_board_cache.get(normalized_symbol)
            if normalized_board is None:
                return _error_result(
                    "daily_stock_price",
                    SsiV3MalformedResponse(
                        "exact-symbol metadata did not provide a supported board"
                    ),
                )

        today = datetime.now(_VN_TIMEZONE).date()
        effective_to = to_date or today.isoformat()
        effective_from = from_date
        if effective_from is None:
            effective_end = datetime.strptime(
                _provider_date(effective_to, intraday=False), "%Y/%m/%d"
            ).date()
            effective_from = (
                effective_end - timedelta(days=max((safe_limit + 2) * 2, 365))
            ).isoformat()
        result = self.get_securities_summary(
            symbol=normalized_symbol,
            from_date=effective_from,
            to_date=effective_to,
            limit=min(SSI_V3_MAX_ROWS, safe_limit + 2),
            exhaust_pages=True,
        )
        if result.get("status") != "ok":
            return result
        if int(result.get("duplicate_date_count") or 0) > 0:
            return _error_result(
                "daily_stock_price",
                SsiV3MalformedResponse("duplicate securities-summary dates"),
            )
        try:
            rows, policy_diagnostics = normalize_foreign_value_rows(
                [
                    row
                    for row in result.get("rows") or []
                    if isinstance(row, Mapping)
                ],
                board=normalized_board,
                as_of=today,
                include_provisional=True,
                limit=safe_limit,
            )
        except ValueError as exc:
            return _error_result("daily_stock_price", exc)
        normalized_result = dict(result)
        normalized_result.update(
            {
                "rows": rows,
                "count": len(rows),
                "diagnostics": {
                    **dict(result.get("diagnostics") or {}),
                    **policy_diagnostics,
                    "capability": "daily_stock_price",
                    "units_verified": True,
                    "finality_verified": False,
                    "operational_finality_policy_validated": True,
                    "provider_finality_verified": False,
                    "finality_contract": SSI_V3_FOREIGN_FINALITY_POLICY,
                },
            }
        )
        return normalized_result

    def get_daily_index(
        self,
        index_code: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
        force_refresh: bool = False,
    ) -> ProviderResult:
        del force_refresh
        try:
            safe_limit = int(limit)
            if safe_limit < 1 or safe_limit > SSI_V3_MAX_ROWS:
                raise ValueError(f"limit must be between 1 and {SSI_V3_MAX_ROWS}")
            normalized_index = str(index_code or "").strip().upper()
            if not normalized_index:
                raise ValueError("index_code is required")
            selected_date = to_date or from_date
        except Exception as exc:
            return _error_result("daily_index", exc)
        result = self.get_index_summary(
            normalized_index,
            index_code=normalized_index,
            trading_date=selected_date,
        )
        if result.get("status") == "ok":
            result = dict(result)
            result["diagnostics"] = {
                **dict(result.get("diagnostics") or {}),
                "capability": "daily_index_latest",
                "series_contract": "latest_or_selected_session",
            }
        return result

    def get_index_components(
        self,
        index_code: str,
        market: Optional[str] = None,
        force_refresh: bool = False,
    ) -> ProviderResult:
        del force_refresh
        normalized_index = str(index_code or "").strip().upper()
        result = self.get_securities_by_index(normalized_index)
        if result.get("status") != "ok":
            return result
        normalized_market = str(market or "").strip().upper() or None
        deduped: Dict[str, Dict[str, Any]] = {}
        for row in result.get("rows") or []:
            if not isinstance(row, Mapping):
                continue
            symbol = str(row.get("symbol") or "").strip().upper()
            exchange = _enum_text(row.get("exchange") or row.get("market"))
            if not symbol or (normalized_market and exchange != normalized_market):
                continue
            deduped[symbol] = {
                "index_code": normalized_index,
                "symbol": symbol,
                "exchange": exchange,
                "market": exchange,
                "weight": None,
                "name": row.get("name") or row.get("name_en"),
                "source": SSI_V3_SOURCE,
            }
        rows = [deduped[symbol] for symbol in sorted(deduped)]
        return _ok_result(
            rows,
            diagnostics={
                "capability": "index_membership",
                "source_endpoint": "securities_by_index",
            },
        )

    def routing_diagnostics(self, capability: Optional[str] = None) -> ProviderDiagnostics:
        return {
            "capability": capability,
            "requested_rest_version": "v3",
            "selected_provider": "ssi_fastconnect_v3",
            "selected_version": "v3",
            "routing_reason": "direct_v3_adapter_capability",
            "fallback_used": False,
            "implementation_status": "implemented",
            "production_owner": "ssi_fastconnect_v3",
            "v3_implementation_available": True,
        }

    def close(self) -> None:
        with self._lifecycle_lock:
            if self._closed:
                return
            self._closed = True
            self._symbol_board_cache.clear()
            data, auth = self._data, self._auth
            self._data = None
            self._auth = None
            try:
                data_close = getattr(data, "close", None)
                if callable(data_close):
                    data_close()
            finally:
                auth_close = getattr(auth, "close", None)
                if callable(auth_close):
                    auth_close()
