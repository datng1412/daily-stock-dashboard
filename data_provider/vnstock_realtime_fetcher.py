# -*- coding: utf-8 -*-
"""Optional vnstock KBS realtime snapshot fetcher.

This module is deliberately separate from Mozyfin daily/intraday providers.
Realtime prices returned here must not be written into OHLCV caches or used as
the dashboard daily ``latest_price``.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from src.services.vietnam_observability import (
    observe_kbs_quote_request,
    observe_kbs_quote_result,
    observe_kbs_trade_request,
    observe_kbs_trade_result,
)


logger = logging.getLogger(__name__)
VNSTOCK_REALTIME_SOURCE = "vnstock_kbs"
DEFAULT_REALTIME_TTL_SECONDS = 10
DEFAULT_TRADES_TTL_SECONDS = 5
VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
STALE_THRESHOLD_SECONDS = 60
SNAPSHOT_NOTE = "KBS board snapshot; may differ from trade tape"
TRADE_TAPE_NOTE = "Trade tape may exclude auction/ATC prints depending on provider output"
KBS_TIMEOUT_ERROR = "KBS provider timeout"
KBS_TIMEOUT_DETAIL = "The upstream KBS provider did not respond in time."
KBS_NETWORK_ERROR = "KBS network/proxy issue"
KBS_NETWORK_DETAIL = "Check provider connectivity or retry later."
KBS_UNAVAILABLE_ERROR = "KBS unavailable"
KBS_UNAVAILABLE_DETAIL = "Provider returned an unavailable state."
KBS_CANCELLED_ERROR = "KBS request cancelled"
KBS_CANCELLED_DETAIL = "The KBS request was cancelled before the provider response completed."


@dataclass
class _CacheEntry:
    value: Any
    expires_at: datetime
    fetched_at: datetime


_CACHE: Dict[str, _CacheEntry] = {}
_CACHE_LOCK = threading.Lock()


def _observe(action: Callable[..., None], *args: Any, **kwargs: Any) -> None:
    try:
        action(*args, **kwargs)
    except Exception as exc:
        logger.warning("KBS observability update failed: %s", exc)


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


def _shape_provider_error(error: Any) -> Dict[str, Optional[str]]:
    raw_error = _safe_str(error) or KBS_UNAVAILABLE_ERROR
    normalized = raw_error.lower()
    if any(token in normalized for token in ("timeout", "timed out")) or any(
        token in raw_error
        for token in (
            "\xe8\xbf\u017e\xe6\u017d\xa5\xe4\xb8\u0160\xe6\xb8\xb8\xe6\u0153\x8d\xe5\u0160\xa1\xe8\xb6\u2026\xe6\u2014\xb6",
            "\xe8\xb6\u2026\xe6\u2014\xb6",
        )
    ):
        return {
            "error": KBS_TIMEOUT_ERROR,
            "error_detail": KBS_TIMEOUT_DETAIL,
            "raw_error": raw_error,
        }
    if any(token in normalized for token in ("proxy", "network")) or any(
        token in raw_error for token in ("\xe7\xbd\u2018\xe7\xbb\u0153", "\xe4\xbb\xa3\xe7\x90\u2020")
    ):
        return {
            "error": KBS_NETWORK_ERROR,
            "error_detail": KBS_NETWORK_DETAIL,
            "raw_error": raw_error,
        }
    return {
        "error": KBS_UNAVAILABLE_ERROR,
        "error_detail": KBS_UNAVAILABLE_DETAIL,
        "raw_error": raw_error,
    }


def _shape_cancelled_error(error: Any) -> Dict[str, Optional[str]]:
    return {
        "error": KBS_CANCELLED_ERROR,
        "error_detail": KBS_CANCELLED_DETAIL,
        "raw_error": _safe_str(error) or KBS_CANCELLED_ERROR,
    }


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
        _observe(observe_kbs_quote_request, len(symbols))
        if not symbols:
            payload = self._response(symbols, [], status="error", error="No tickers requested")
            _observe(observe_kbs_quote_result, payload["status"], error=payload.get("error"), raw_error_present=bool(payload.get("raw_error")))
            return payload

        try:
            Trading, _ = self._load_classes()
        except asyncio.CancelledError as exc:
            shaped_error = _shape_cancelled_error(exc)
            payload = self._response(
                symbols,
                [self._error_quote(symbol, "unavailable", **shaped_error) for symbol in symbols],
                status="unavailable",
                **shaped_error,
            )
            _observe(observe_kbs_quote_result, payload["status"], error=payload.get("error"), raw_error_present=bool(payload.get("raw_error")))
            return payload
        except RuntimeError as exc:
            payload = self._unavailable_response(symbols, str(exc))
            _observe(observe_kbs_quote_result, payload["status"], error=payload.get("error"), raw_error_present=bool(payload.get("raw_error")))
            return payload

        cache_key = "vnstock_realtime:" + ",".join(symbols)

        def loader() -> List[Dict[str, Any]]:
            payload = Trading(source="KBS").price_board(symbols)
            return _records_from_payload(payload)

        try:
            rows, cache = _read_cache(cache_key, self.realtime_ttl_seconds, loader)
        except asyncio.CancelledError as exc:
            shaped_error = _shape_cancelled_error(exc)
            payload = self._response(
                symbols,
                [self._error_quote(symbol, "unavailable", **shaped_error) for symbol in symbols],
                status="unavailable",
                **shaped_error,
            )
            _observe(observe_kbs_quote_result, payload["status"], error=payload.get("error"), raw_error_present=bool(payload.get("raw_error")))
            return payload
        except Exception as exc:
            shaped_error = _shape_provider_error(exc)
            payload = self._response(
                symbols,
                [self._error_quote(symbol, "unavailable", **shaped_error) for symbol in symbols],
                status="unavailable",
                **shaped_error,
            )
            _observe(observe_kbs_quote_result, payload["status"], error=payload.get("error"), raw_error_present=bool(payload.get("raw_error")))
            return payload

        try:
            quotes = self._map_quote_rows(symbols, rows)
            status = "ok" if any(quote["status"] == "ok" for quote in quotes) else "error"
            payload = self._response(symbols, quotes, status=status, cache=cache)
        except Exception as exc:
            shaped_error = _shape_provider_error(exc)
            payload = self._response(
                symbols,
                [self._error_quote(symbol, "unavailable", **shaped_error) for symbol in symbols],
                status="unavailable",
                **shaped_error,
            )
        _observe(observe_kbs_quote_result, payload["status"], error=payload.get("error"), raw_error_present=bool(payload.get("raw_error")))
        return payload

    def fetch_trades(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        ticker = symbol.strip().upper()
        _observe(observe_kbs_trade_request, ticker)
        if not ticker:
            payload = self._trades_response(ticker, [], status="error", error="No symbol requested")
            _observe(observe_kbs_trade_result, payload["status"], error=payload.get("error"), raw_error_present=bool(payload.get("raw_error")))
            return payload

        try:
            _, Market = self._load_classes()
        except asyncio.CancelledError as exc:
            payload = self._trades_response(ticker, [], status="unavailable", **_shape_cancelled_error(exc))
            _observe(observe_kbs_trade_result, payload["status"], error=payload.get("error"), raw_error_present=bool(payload.get("raw_error")))
            return payload
        except RuntimeError as exc:
            payload = self._trades_response(
                ticker,
                [],
                status="unavailable",
                error=str(exc),
            )
            _observe(observe_kbs_trade_result, payload["status"], error=payload.get("error"), raw_error_present=bool(payload.get("raw_error")))
            return payload

        cache_key = f"vnstock_trades:{ticker}"

        def loader() -> List[Dict[str, Any]]:
            payload = Market().equity(ticker).trades()
            return _records_from_payload(payload)

        try:
            rows, cache = _read_cache(cache_key, self.trades_ttl_seconds, loader)
        except asyncio.CancelledError as exc:
            payload = self._trades_response(ticker, [], status="unavailable", **_shape_cancelled_error(exc))
            _observe(observe_kbs_trade_result, payload["status"], error=payload.get("error"), raw_error_present=bool(payload.get("raw_error")))
            return payload
        except Exception as exc:
            payload = self._trades_response(ticker, [], status="unavailable", **_shape_provider_error(exc))
            _observe(observe_kbs_trade_result, payload["status"], error=payload.get("error"), raw_error_present=bool(payload.get("raw_error")))
            return payload

        try:
            trades = [self._map_trade(row) for row in rows[:limit]]
            payload = self._trades_response(ticker, trades, status="ok", cache=cache)
        except Exception as exc:
            payload = self._trades_response(ticker, [], status="unavailable", **_shape_provider_error(exc))
        _observe(observe_kbs_trade_result, payload["status"], error=payload.get("error"), raw_error_present=bool(payload.get("raw_error")))
        return payload

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
                quotes.append(
                    self._error_quote(
                        symbol,
                        "error",
                        error="KBS ticker unavailable",
                        error_detail="Ticker was not returned by the KBS snapshot provider.",
                        raw_error="Ticker not returned by vnstock KBS",
                    )
                )
            else:
                quotes.append(self._map_quote(symbol, row))
        return quotes

    def _map_quote(self, symbol: str, row: Dict[str, Any]) -> Dict[str, Any]:
        time_metadata = _parse_realtime_time(row.get("time"))
        snapshot_price = _safe_float(row.get("close_price"))
        reference_price = _safe_float(row.get("reference_price"))
        price_vs_reference = (
            snapshot_price - reference_price
            if snapshot_price is not None and reference_price is not None
            else None
        )
        price_vs_reference_pct = (
            price_vs_reference / reference_price * 100
            if price_vs_reference is not None and reference_price
            else None
        )
        return {
            "symbol": symbol,
            "realtime_price": snapshot_price,
            **time_metadata,
            "snapshot_price": snapshot_price,
            "snapshot_time": time_metadata["realtime_time"],
            "snapshot_time_display": time_metadata["realtime_time_display"],
            "snapshot_note": SNAPSHOT_NOTE,
            "reference_price": reference_price,
            "reference_price_source": "kbs_board" if reference_price is not None else None,
            "price_vs_reference": round(price_vs_reference, 2) if price_vs_reference is not None else None,
            "price_vs_reference_pct": round(price_vs_reference_pct, 2) if price_vs_reference_pct is not None else None,
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
            "error_detail": None,
            "raw_error": None,
        }

    def _error_quote(
        self,
        symbol: str,
        status: str,
        error: str,
        error_detail: Optional[str] = None,
        raw_error: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "realtime_price": None,
            "realtime_time": None,
            "realtime_time_display": None,
            "snapshot_price": None,
            "snapshot_time": None,
            "snapshot_time_display": None,
            "snapshot_note": SNAPSHOT_NOTE,
            "age_seconds": None,
            "is_stale": None,
            "stale_reason": "timestamp_unparseable",
            "reference_price": None,
            "reference_price_source": None,
            "price_vs_reference": None,
            "price_vs_reference_pct": None,
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
            "error_detail": error_detail,
            "raw_error": raw_error,
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
        shaped_error = _shape_provider_error(error)
        return self._response(
            symbols,
            [self._error_quote(symbol, "unavailable", **shaped_error) for symbol in symbols],
            status="unavailable",
            **shaped_error,
        )

    def _response(
        self,
        symbols: List[str],
        quotes: List[Dict[str, Any]],
        *,
        status: str,
        error: Optional[str] = None,
        error_detail: Optional[str] = None,
        raw_error: Optional[str] = None,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "market": "VN",
            "source": VNSTOCK_REALTIME_SOURCE,
            "status": status,
            "error": error,
            "error_detail": error_detail,
            "raw_error": raw_error,
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
        error_detail: Optional[str] = None,
        raw_error: Optional[str] = None,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "market": "VN",
            "source": VNSTOCK_REALTIME_SOURCE,
            "symbol": symbol,
            "status": status,
            "error": error,
            "error_detail": error_detail,
            "raw_error": raw_error,
            "trades": trades,
            "note": TRADE_TAPE_NOTE,
            "cache": cache or {
                "cache_status": "unavailable" if status == "unavailable" else "none",
                "ttl_seconds": self.trades_ttl_seconds,
            },
        }
