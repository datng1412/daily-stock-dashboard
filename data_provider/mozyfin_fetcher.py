# -*- coding: utf-8 -*-
"""Vietnam market data adapter backed by mozyfin-cli.

The adapter keeps the existing DataFetcher contract intact:
daily history returns the standard OHLCV dataframe columns and any Vietnam-
specific signals are carried as extra columns/metadata for dashboard consumers.
"""

from __future__ import annotations

import csv
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from .base import BaseFetcher, DataFetchError
from .realtime_types import RealtimeSource, UnifiedRealtimeQuote

logger = logging.getLogger(__name__)


VN_WATCHLIST = ("FPT", "VPB", "MSB", "SCS", "ACV", "ACB")
VN_EXCHANGE_MAP = {
    "FPT": "HOSE",
    "VPB": "HOSE",
    "MSB": "HOSE",
    "SCS": "HOSE",
    "ACV": "UPCoM",
    "ACB": "HNX",
}
VN_REFERENCE_INDEX = {
    "HOSE": "VNINDEX.VN",
    "HNX": "HNXINDEX.VN",
    "UPCOM": "UPCOMINDEX.VN",
    "UPCoM": "UPCOMINDEX.VN",
}
VN_PRICE_LIMIT_PCT = {
    "HOSE": 7.0,
    "HNX": 10.0,
    "UPCOM": 15.0,
    "UPCoM": 15.0,
}


def normalize_vn_symbol(symbol: str) -> str:
    """Return Mozy entity id for a Vietnam ticker."""
    value = (symbol or "").strip().upper()
    if value.endswith(".VN"):
        return value
    return f"{value}.VN"


def vn_ticker(symbol: str) -> str:
    """Return bare Vietnam ticker from a ticker or Mozy entity id."""
    return (symbol or "").strip().upper().removesuffix(".VN")


def is_vn_symbol(symbol: str) -> bool:
    ticker = vn_ticker(symbol)
    return bool(ticker) and ticker.isalpha() and 2 <= len(ticker) <= 5


def get_vn_exchange(symbol: str) -> str:
    return VN_EXCHANGE_MAP.get(vn_ticker(symbol), "HOSE")


def get_vn_price_limit_pct(symbol: str) -> float:
    exchange = get_vn_exchange(symbol)
    return VN_PRICE_LIMIT_PCT.get(exchange, 7.0)


def _clean_key(key: Any) -> str:
    return str(key or "").strip().lower().replace(" ", "_").replace("-", "_")


def _first_value(row: Dict[str, Any], *keys: str) -> Any:
    normalized = {_clean_key(k): v for k, v in row.items()}
    for key in keys:
        value = normalized.get(_clean_key(key))
        if value not in (None, ""):
            return value
    return None


def _first_present_key(row: Dict[str, Any], *keys: str) -> Optional[str]:
    normalized = {_clean_key(k): k for k in row.keys()}
    for key in keys:
        raw_key = normalized.get(_clean_key(key))
        if raw_key is not None and row.get(raw_key) not in (None, ""):
            return str(raw_key)
    return None


def _to_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        text = str(value).strip().replace(",", "")
        if text in {"-", "--", "nan", "NaN"}:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    numeric = _to_float(value)
    return int(numeric) if numeric is not None else None


def _normalize_date_value(value: Any) -> Any:
    if value in (None, ""):
        return value
    text = str(value).strip()
    try:
        numeric = float(text)
    except ValueError:
        return value
    if numeric > 1_000_000_000:
        return datetime.utcfromtimestamp(numeric).strftime("%Y-%m-%d")
    return value


def _normalize_datetime_value(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        numeric = float(text)
    except ValueError:
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.isna(parsed):
            return text
        timestamp = parsed.to_pydatetime()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc).isoformat()
    if numeric > 1_000_000_000:
        return datetime.fromtimestamp(numeric, tz=timezone.utc).isoformat()
    return text


def _parse_markdown_table(text: str) -> List[Dict[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return []
    headers = [cell.strip() for cell in lines[0].strip("|").split("|")]
    rows: List[Dict[str, str]] = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def _sanitize_cli_error_output(text: str, *, max_lines: int = 6, max_chars: int = 700) -> str:
    """Keep actionable CLI diagnostics without leaking bundled Node internals."""
    if not text:
        return ""
    noisy_markers = (
        "file:///usr/local/lib/node_modules/mozyfin-cli/dist/index.js",
        "node_modules/mozyfin-cli/dist/index.js",
        "Symbol(\"",
        "Symbol.for(\"",
        "undici.error.",
        "llhttp",
        "AGFzbQE",
        "wasm_",
        "var ",
        "Uf.exports",
        "id.exports",
    )
    lines: List[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if len(line) > 300 or any(marker in line for marker in noisy_markers):
            continue
        lines.append(line)
        if len(lines) >= max_lines:
            break
    compact = "\n".join(lines).strip()
    if len(compact) > max_chars:
        compact = compact[:max_chars].rstrip() + "..."
    return compact


def _format_cli_failure(
    command: str,
    entity: str,
    *,
    returncode: Optional[int] = None,
    stderr: str = "",
    stdout: str = "",
) -> str:
    detail = _sanitize_cli_error_output(stderr) or _sanitize_cli_error_output(stdout)
    status = f" exited with code {returncode}" if returncode is not None else " failed"
    message = f"mozyfin-cli {command} for {entity}{status}"
    if detail:
        return f"{message}: {detail}"
    return f"{message}; internal Node.js stack output was suppressed"


class MozyfinFetcher(BaseFetcher):
    """Vietnam OHLCV, quote, index, and news adapter using mozyfin-cli."""

    name = "MozyfinFetcher"
    priority = -10

    def __init__(self, fixture_dir: Optional[str] = None):
        fixture_value = fixture_dir if fixture_dir is not None else os.getenv("MOZYFIN_FIXTURE_DIR")
        self.fixture_dir = Path(fixture_value).expanduser() if fixture_value else None
        self.command = (os.getenv("MOZYFIN_COMMAND") or "").strip()
        self.api_key = (os.getenv("MOZYFIN_API_KEY") or "").strip()

    def is_available_for_request(self, capability: str = "") -> bool:
        if self.fixture_dir is not None and self.fixture_dir.is_dir():
            return True
        return bool(self._command_prefix())

    def _command_prefix(self) -> List[str]:
        if self.command:
            return self.command.split()
        for executable in ("mozyfin.cmd", "mozyfin"):
            if shutil.which(executable):
                return [executable]
        for executable in ("mozyfin-cli.cmd", "mozyfin-cli"):
            if shutil.which(executable):
                return [executable]
        for executable in ("npx.cmd", "npx"):
            if shutil.which(executable):
                return [executable, "mozyfin-cli"]
        return []

    def _fixture_file(self, command: str, entity: str) -> Optional[Path]:
        if self.fixture_dir is None:
            return None
        ticker = vn_ticker(entity).lower()
        candidate = self.fixture_dir / f"{ticker}_{command}.csv"
        return candidate if candidate.is_file() else None

    def _read_csv_file(self, path: Path) -> List[Dict[str, Any]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def _run_csv_command(self, command: str, entity: str, *args: str) -> List[Dict[str, Any]]:
        fixture = self._fixture_file(command, entity)
        if fixture is not None:
            return self._read_csv_file(fixture)
        if self.fixture_dir is not None:
            ticker = vn_ticker(entity).lower()
            raise DataFetchError(
                f"Fixture mode is active but missing fixture file: {ticker}_{command}.csv"
            )

        prefix = self._command_prefix()
        if not prefix:
            raise DataFetchError("mozyfin-cli not found; install it or use MOZYFIN_FIXTURE_DIR")

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            csv_path = Path(tmp.name)

        try:
            cmd = [*prefix]
            if self.api_key:
                cmd.extend(["--api-key", self.api_key])
            cmd.append(command)
            if command not in {"news", "indices"}:
                cmd.append(entity)
            cmd.extend([*args, "--csv", str(csv_path)])
            timeout_seconds = int(os.getenv("MOZYFIN_TIMEOUT_SECONDS", "45"))
            try:
                result = subprocess.run(
                    cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise DataFetchError(
                    f"mozyfin-cli {command} for {entity} timed out after {timeout_seconds}s"
                ) from exc
            if result.returncode != 0:
                raise DataFetchError(
                    _format_cli_failure(
                        command,
                        entity,
                        returncode=result.returncode,
                        stderr=result.stderr or "",
                        stdout=result.stdout or "",
                    )
                )
            if csv_path.exists() and csv_path.stat().st_size > 0:
                return self._read_csv_file(csv_path)
            return _parse_markdown_table(result.stdout)
        finally:
            try:
                csv_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        entity = normalize_vn_symbol(stock_code)
        rows = self._run_csv_command("ohlcv", entity, "--timeframe", "1d", "--limit", "260")
        return pd.DataFrame(rows)

    def get_intraday_ohlcv(self, stock_code: str, timeframe: str = "1h", limit: int = 8) -> pd.DataFrame:
        """Return latest intraday OHLCV candles from Mozyfin."""
        entity = normalize_vn_symbol(stock_code)
        rows = self._run_csv_command("ohlcv", entity, "--timeframe", timeframe, "--limit", str(limit))
        return self._normalize_intraday_data(pd.DataFrame(rows), stock_code)

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []
        prev_close: Optional[float] = None
        exchange = get_vn_exchange(stock_code)
        limit_pct = get_vn_price_limit_pct(stock_code)

        for raw in df.to_dict("records"):
            date_value = _normalize_date_value(_first_value(raw, "date", "trading_date", "time", "timestamp", "datetime"))
            open_price = _to_float(_first_value(raw, "open", "o"))
            high = _to_float(_first_value(raw, "high", "h"))
            low = _to_float(_first_value(raw, "low", "l"))
            close = _to_float(_first_value(raw, "close", "c", "price"))
            volume = _to_int(_first_value(raw, "volume", "vol", "v"))
            amount = _to_float(_first_value(raw, "amount", "value", "turnover", "trading_value"))
            pct_chg = _to_float(_first_value(raw, "pct_chg", "change_percent", "change_pct", "pct_change"))
            row_prev_close = _to_float(_first_value(raw, "prev_close", "pre_close", "reference_price"))
            if pct_chg is None and close is not None:
                denominator = row_prev_close or prev_close
                if denominator:
                    pct_chg = (close - denominator) / denominator * 100
            if amount is None and close is not None and volume is not None:
                amount = close * volume

            foreign_buy = _to_float(_first_value(raw, "foreign_buy", "foreign_buy_volume", "buy_foreign_quantity"))
            foreign_sell = _to_float(_first_value(raw, "foreign_sell", "foreign_sell_volume", "sell_foreign_quantity"))
            foreign_net = _to_float(_first_value(raw, "foreign_net", "foreign_net_volume", "foreign_net_quantity"))
            if foreign_net is None and foreign_buy is not None and foreign_sell is not None:
                foreign_net = foreign_buy - foreign_sell

            limit_distance = None
            reference = row_prev_close or prev_close
            if close is not None and reference:
                limit_price = reference * (1 + limit_pct / 100)
                floor_price = reference * (1 - limit_pct / 100)
                limit_distance = min(abs(limit_price - close), abs(close - floor_price)) / reference * 100

            adjustment_raw = _first_value(raw, "adjusted", "is_adjusted", "ex_dividend", "corporate_action")
            adjusted_or_ex_dividend = bool(
                str(adjustment_raw or "")
                .strip()
                .lower()
                in {"1", "true", "yes", "y", "ex_dividend", "adjusted"}
            )
            if adjustment_raw in (None, ""):
                price_adjustment_status = "unknown"
            elif adjusted_or_ex_dividend:
                price_adjustment_status = "adjusted_or_ex_dividend"
            else:
                price_adjustment_status = "unadjusted"

            rows.append(
                {
                    "date": date_value,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                    "amount": amount,
                    "pct_chg": pct_chg,
                    "exchange": exchange,
                    "market_index": VN_REFERENCE_INDEX.get(exchange, "VNINDEX.VN"),
                    "price_limit_pct": limit_pct,
                    "near_price_limit": bool(limit_distance is not None and limit_distance <= 0.5),
                    "ex_dividend_warning": adjusted_or_ex_dividend,
                    "price_adjustment_status": price_adjustment_status,
                    "foreign_buy": foreign_buy,
                    "foreign_sell": foreign_sell,
                    "foreign_net": foreign_net,
                }
            )
            if close is not None:
                prev_close = close

        return pd.DataFrame(rows)

    def _normalize_intraday_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []
        for raw in df.to_dict("records"):
            timestamp = _first_value(raw, "timestamp", "time", "datetime", "date_time", "date")
            rows.append(
                {
                    "timestamp": _to_int(timestamp),
                    "date_time": _normalize_datetime_value(timestamp),
                    "open": _to_float(_first_value(raw, "open", "o")),
                    "high": _to_float(_first_value(raw, "high", "h")),
                    "low": _to_float(_first_value(raw, "low", "l")),
                    "close": _to_float(_first_value(raw, "close", "c", "price")),
                    "volume": _to_int(_first_value(raw, "volume", "vol", "v")),
                    "ticker": vn_ticker(stock_code),
                }
            )
        result = pd.DataFrame(rows)
        if not result.empty and "date_time" in result.columns:
            result = result.sort_values("date_time").reset_index(drop=True)
        return result

    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        entity = normalize_vn_symbol(stock_code)
        rows = self._run_csv_command("quote", entity, "--limit", "1")
        if not rows:
            return None
        normalized = self._normalize_data(pd.DataFrame(rows), stock_code)
        if normalized.empty:
            return None
        latest = normalized.iloc[-1]
        close = _to_float(latest.get("close"))
        pct_chg = _to_float(latest.get("pct_chg"))
        prev_close = None
        if close is not None and pct_chg not in (None, -100):
            prev_close = close / (1 + pct_chg / 100)
        return UnifiedRealtimeQuote(
            code=vn_ticker(stock_code),
            name=vn_ticker(stock_code),
            source=RealtimeSource.FALLBACK,
            fetched_at=datetime.now().isoformat(),
            price=close,
            change_pct=pct_chg,
            change_amount=(close - prev_close) if close is not None and prev_close else None,
            volume=_to_int(latest.get("volume")),
            amount=_to_float(latest.get("amount")),
            open_price=_to_float(latest.get("open")),
            high=_to_float(latest.get("high")),
            low=_to_float(latest.get("low")),
            pre_close=prev_close,
        )

    def get_foreign_trading(self, stock_code: str) -> Dict[str, Any]:
        rows = self._run_csv_command("quote", normalize_vn_symbol(stock_code), "--limit", "1")
        if not rows:
            return {
                "buy": None,
                "sell": None,
                "net": None,
                "date": None,
                "net_unit": "unknown",
                "buy_raw_field": None,
                "sell_raw_field": None,
                "latest_price": None,
                "price_raw_field": None,
                "price_date": None,
            }
        latest = rows[-1]
        price_raw_field = _first_present_key(latest, "last_price", "latest_price", "match_price", "matched_price", "current_price", "price", "close")
        quote_price = _to_float(_first_value(latest, "last_price", "latest_price", "match_price", "matched_price", "current_price", "price", "close"))
        quote_date = _normalize_date_value(_first_value(latest, "date", "trading_date", "timestamp", "time", "datetime"))
        buy_raw_field = _first_present_key(latest, "foreign_buy", "foreign_buy_volume", "buy_foreign_quantity")
        sell_raw_field = _first_present_key(latest, "foreign_sell", "foreign_sell_volume", "sell_foreign_quantity")
        buy = _to_float(_first_value(latest, "foreign_buy", "foreign_buy_volume", "buy_foreign_quantity"))
        sell = _to_float(_first_value(latest, "foreign_sell", "foreign_sell_volume", "sell_foreign_quantity"))
        net = _to_float(_first_value(latest, "foreign_net", "foreign_net_volume", "foreign_net_quantity"))
        derived_from_quantity = buy_raw_field == "buy_foreign_quantity" and sell_raw_field == "sell_foreign_quantity"
        if net is None and buy is not None and sell is not None:
            net = buy - sell
        net_unit = "shares" if derived_from_quantity else "unknown"
        return {
            "buy": buy,
            "sell": sell,
            "net": net,
            "date": quote_date,
            "net_unit": net_unit,
            "buy_raw_field": buy_raw_field,
            "sell_raw_field": sell_raw_field,
            "latest_price": quote_price,
            "price_raw_field": price_raw_field,
            "price_date": quote_date,
        }

    def get_main_indices(self, region: str = "vn") -> Optional[List[Dict[str, Any]]]:
        if region.lower() not in {"vn", "vietnam"}:
            return None
        fixture = self._fixture_file("indices", "vn")
        rows = self._read_csv_file(fixture) if fixture else self._run_csv_command("indices", "VN")
        result = []
        for row in rows:
            result.append(
                {
                    "code": _first_value(row, "id", "symbol", "code") or "",
                    "name": _first_value(row, "name", "title") or "",
                    "current": _to_float(_first_value(row, "current", "close", "price")),
                    "change_pct": _to_float(_first_value(row, "change_pct", "pct_chg", "change_percent")),
                    "volume": _to_float(_first_value(row, "volume")),
                    "amount": _to_float(_first_value(row, "amount", "value")),
                }
            )
        return result

    def get_news(self, stock_code: str, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            rows = self._run_csv_command(
                "news",
                normalize_vn_symbol(stock_code),
                "--entities",
                normalize_vn_symbol(stock_code),
                "--limit",
                str(limit),
            )
        except Exception as exc:
            logger.debug("[MozyfinFetcher] news unavailable for %s: %s", stock_code, exc)
            return []
        news = []
        for row in rows[:limit]:
            news.append(
                {
                    "title": _first_value(row, "title", "headline") or "",
                    "url": _first_value(row, "url", "link") or "",
                    "published_at": _first_value(row, "published_at", "date", "time") or "",
                    "source": _first_value(row, "source", "publisher") or "Mozyfin",
                    "summary": _first_value(row, "summary", "snippet", "description") or "",
                }
            )
        return [item for item in news if item["title"]]

    def get_stock_name(self, stock_code: str) -> str:
        return vn_ticker(stock_code)
