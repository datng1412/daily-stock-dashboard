# -*- coding: utf-8 -*-
"""Optional vnstock KBS realtime snapshot fetcher.

This module is deliberately separate from Mozyfin daily/intraday providers.
Realtime prices returned here must not be written into OHLCV caches or used as
the dashboard daily ``latest_price``.
"""

from __future__ import annotations

import importlib
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo


VNSTOCK_REALTIME_SOURCE = "vnstock_kbs"
DEFAULT_REALTIME_TTL_SECONDS = 10
DEFAULT_TRADES_TTL_SECONDS = 10
VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
STALE_THRESHOLD_SECONDS = 60


@dataclass
class _CacheEntry:
    value: Any
    expires_at: datetime
    fetched_at: datetime


_CACHE: Dict[str, _CacheEntry] = {}
_CACHE_LOCK = threading.Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _vn_now() -> datetime:
    return _utc_now().astimezone(VN_TIMEZONE)


def clear_vnstock_realtime_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def _read_cache(key: str, ttl_seconds: int, loader: Callable[[], Any]) -> Tuple[Any, Dict[str, Any]]:
    now = _utc_now()
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry and entry.expires_at > now:
            return entry.value, {
                "cache_status": "hit",
                "cache_key": key,
                "last_fetched_at": entry.fetched_at.isoformat(),
                "next_refresh_at": entry.expires_at.isoformat(),
                "ttl_seconds": ttl_seconds,
            }

    value = loader()
    fetched_at = _utc_now()
    expires_at = fetched_at + timedelta(seconds=ttl_seconds)
    with _CACHE_LOCK:
        _CACHE[key] = _CacheEntry(value=value, expires_at=expires_at, fetched_at=fetched_at)
    return value, {
        "cache_status": "miss",
        "cache_key": key,
        "last_fetched_at": fetched_at.isoformat(),
        "next_refresh_at": expires_at.isoformat(),
        "ttl_seconds": ttl_seconds,
    }


def _safe_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    return str(value)


def _parse_realtime_time(value: Any, now: Optional[datetime] = None) -> Dict[str, Any]:
    raw_value = _safe_str(value)
    if not raw_value:
        return {
            "realtime_time": None,
            "realtime_time_display": None,
            "age_seconds": None,
            "is_stale": None,
            "stale_reason": "timestamp_unparseable",
        }

    parsed: Optional[datetime] = None
    try:
        if isinstance(value, (int, float)) or raw_value.isdigit():
            number = float(raw_value)
            seconds = number / 1000 if number >= 1_000_000_000_000 else number
            parsed = datetime.fromtimestamp(seconds, tz=timezone.utc).astimezone(VN_TIMEZONE)
        else:
            normalized = raw_value.replace("T", " ")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=VN_TIMEZONE)
            else:
                parsed = parsed.astimezone(VN_TIMEZONE)
    except Exception:
        parsed = None

    if parsed is None:
        return {
            "realtime_time": raw_value,
            "realtime_time_display": raw_value,
            "age_seconds": None,
            "is_stale": None,
            "stale_reason": "timestamp_unparseable",
        }

    reference_now = (now or _vn_now()).astimezone(VN_TIMEZONE)
    age_seconds = max(0, int((reference_now - parsed).total_seconds()))
    is_stale = age_seconds > STALE_THRESHOLD_SECONDS
    return {
        "realtime_time": raw_value,
        "realtime_time_display": parsed.isoformat(timespec="seconds"),
        "age_seconds": age_seconds,
        "is_stale": is_stale,
        "stale_reason": "age_gt_60s" if is_stale else None,
    }


def _column_name(column: Any) -> str:
    if isinstance(column, tuple):
        parts = [str(part) for part in column if part not in (None, "")]
        return "_".join(parts)
    return str(column)


def _records_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if hasattr(payload, "to_dataFrame"):
        payload = payload.to_dataFrame()
    elif hasattr(payload, "to_dataframe"):
        payload = payload.to_dataframe()

    if hasattr(payload, "columns") and hasattr(payload, "to_dict"):
        try:
            payload = payload.copy()
            payload.columns = [_column_name(column) for column in payload.columns]
        except Exception:
            pass
        return [dict(row) for row in payload.to_dict("records")]

    if isinstance(payload, dict):
        return [payload]

    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, dict)]

    return []


def _row_symbol(row: Dict[str, Any]) -> Optional[str]:
    for key in ("symbol", "ticker", "code", "Symbol", "Ticker"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value).upper()
    return None


class VnstockRealtimeFetcher:
    """Optional vnstock KBS realtime/snapshot provider."""

    def __init__(
        self,
        realtime_ttl_seconds: int = DEFAULT_REALTIME_TTL_SECONDS,
        trades_ttl_seconds: int = DEFAULT_TRADES_TTL_SECONDS,
    ) -> None:
        self.realtime_ttl_seconds = realtime_ttl_seconds
        self.trades_ttl_seconds = trades_ttl_seconds

    def _load_classes(self) -> Tuple[Any, Any]:
        try:
            module = importlib.import_module("vnstock")
            return getattr(module, "Trading"), getattr(module, "Market")
        except ImportError as exc:
            raise RuntimeError("vnstock is not installed") from exc
        except AttributeError as exc:
            raise RuntimeError("vnstock Trading/Market classes are unavailable") from exc

    def fetch_quotes(self, tickers: List[str]) -> Dict[str, Any]:
        symbols = [ticker.strip().upper() for ticker in tickers if ticker.strip()]
        if not symbols:
            return self._response(symbols, [], status="error", error="No tickers requested")

        try:
            Trading, _ = self._load_classes()
        except RuntimeError as exc:
            return self._unavailable_response(symbols, str(exc))

        cache_key = "vnstock_realtime:" + ",".join(symbols)

        def loader() -> List[Dict[str, Any]]:
            payload = Trading(source="KBS").price_board(symbols)
            return _records_from_payload(payload)

        try:
            rows, cache = _read_cache(cache_key, self.realtime_ttl_seconds, loader)
        except Exception as exc:
            return self._response(
                symbols,
                [self._error_quote(symbol, "error", str(exc)) for symbol in symbols],
                status="error",
                error=str(exc),
            )

        quotes = self._map_quote_rows(symbols, rows)
        status = "ok" if any(quote["status"] == "ok" for quote in quotes) else "error"
        return self._response(symbols, quotes, status=status, cache=cache)

    def fetch_trades(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        ticker = symbol.strip().upper()
        if not ticker:
            return self._trades_response(ticker, [], status="error", error="No symbol requested")

        try:
            _, Market = self._load_classes()
        except RuntimeError as exc:
            return self._trades_response(
                ticker,
                [],
                status="unavailable",
                error=str(exc),
            )

        cache_key = f"vnstock_trades:{ticker}"

        def loader() -> List[Dict[str, Any]]:
            payload = Market().equity(ticker).trades()
            return _records_from_payload(payload)

        try:
            rows, cache = _read_cache(cache_key, self.trades_ttl_seconds, loader)
        except Exception as exc:
            return self._trades_response(ticker, [], status="error", error=str(exc))

        trades = [self._map_trade(row) for row in rows[:limit]]
        return self._trades_response(ticker, trades, status="ok", cache=cache)

    def _map_quote_rows(self, symbols: List[str], rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_symbol: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            symbol = _row_symbol(row)
            if symbol:
                by_symbol[symbol] = row

        quotes = []
        for symbol in symbols:
            row = by_symbol.get(symbol)
            if row is None:
                quotes.append(self._error_quote(symbol, "error", "Ticker not returned by vnstock KBS"))
            else:
                quotes.append(self._map_quote(symbol, row))
        return quotes

    def _map_quote(self, symbol: str, row: Dict[str, Any]) -> Dict[str, Any]:
        time_metadata = _parse_realtime_time(row.get("time"))
        return {
            "symbol": symbol,
            "realtime_price": _safe_float(row.get("close_price")),
            **time_metadata,
            "reference_price": _safe_float(row.get("reference_price")),
            "open_price": _safe_float(row.get("open_price")),
            "high_price": _safe_float(row.get("high_price")),
            "low_price": _safe_float(row.get("low_price")),
            "average_price": _safe_float(row.get("average_price")),
            "price_change": _safe_float(row.get("price_change")),
            "percent_change": _safe_float(row.get("percent_change")),
            "volume_accumulated": _safe_float(row.get("volume_accumulated")),
            "total_value": _safe_float(row.get("total_value")),
            "bid_price_1": _safe_float(row.get("bid_price_1")),
            "bid_vol_1": _safe_float(row.get("bid_vol_1")),
            "ask_price_1": _safe_float(row.get("ask_price_1")),
            "ask_vol_1": _safe_float(row.get("ask_vol_1")),
            "foreign_buy_volume": _safe_float(row.get("foreign_buy_volume")),
            "foreign_sell_volume": _safe_float(row.get("foreign_sell_volume")),
            "foreign_room": _safe_float(row.get("foreign_room")),
            "source": VNSTOCK_REALTIME_SOURCE,
            "status": "ok",
            "error": None,
        }

    def _error_quote(self, symbol: str, status: str, error: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "realtime_price": None,
            "realtime_time": None,
            "realtime_time_display": None,
            "age_seconds": None,
            "is_stale": None,
            "stale_reason": "timestamp_unparseable",
            "reference_price": None,
            "open_price": None,
            "high_price": None,
            "low_price": None,
            "average_price": None,
            "price_change": None,
            "percent_change": None,
            "volume_accumulated": None,
            "total_value": None,
            "bid_price_1": None,
            "bid_vol_1": None,
            "ask_price_1": None,
            "ask_vol_1": None,
            "foreign_buy_volume": None,
            "foreign_sell_volume": None,
            "foreign_room": None,
            "source": VNSTOCK_REALTIME_SOURCE,
            "status": status,
            "error": error,
        }

    def _map_trade(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "time": _safe_str(row.get("time")),
            "price": _safe_float(row.get("price")),
            "volume": _safe_float(row.get("volume")),
            "match_type": _safe_str(row.get("match_type")),
            "id": _safe_str(row.get("id")),
            "source": VNSTOCK_REALTIME_SOURCE,
        }

    def _unavailable_response(self, symbols: List[str], error: str) -> Dict[str, Any]:
        return self._response(
            symbols,
            [self._error_quote(symbol, "unavailable", error) for symbol in symbols],
            status="unavailable",
            error=error,
        )

    def _response(
        self,
        symbols: List[str],
        quotes: List[Dict[str, Any]],
        *,
        status: str,
        error: Optional[str] = None,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "market": "VN",
            "source": VNSTOCK_REALTIME_SOURCE,
            "status": status,
            "error": error,
            "requested_tickers": symbols,
            "quotes": quotes,
            "cache": cache or {
                "cache_status": "unavailable" if status == "unavailable" else "none",
                "ttl_seconds": self.realtime_ttl_seconds,
            },
        }

    def _trades_response(
        self,
        symbol: str,
        trades: List[Dict[str, Any]],
        *,
        status: str,
        error: Optional[str] = None,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "market": "VN",
            "source": VNSTOCK_REALTIME_SOURCE,
            "symbol": symbol,
            "status": status,
            "error": error,
            "trades": trades,
            "cache": cache or {
                "cache_status": "unavailable" if status == "unavailable" else "none",
                "ttl_seconds": self.trades_ttl_seconds,
            },
        }
