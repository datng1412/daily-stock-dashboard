# -*- coding: utf-8 -*-

import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from data_provider.base import DataFetcherManager
from data_provider.base import DataFetchError
from data_provider.mozyfin_fetcher import MozyfinFetcher
from src.config import Config
from src.services import vietnam_market_service as vn_service
from src.services.vietnam_market_service import (
    VietnamDashboardConfig,
    VietnamMarketService,
    calculate_intraday_pulse,
    calculate_rsi14,
    calculate_liquidity_score,
    calculate_price_limit_state,
    calculate_vietnam_indicators,
    build_corporate_action_reference,
    derive_neutral_status_details,
    derive_intraday_details,
    clear_vietnam_cache,
    derive_neutral_status_labels,
    filter_chart_points_by_range,
    normalize_intraday_candles,
    normalize_daily_chart_data,
    normalize_vietnam_tickers,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mozyfin"


@pytest.fixture(autouse=True)
def _clear_vn_cache_between_tests():
    clear_vietnam_cache()
    yield
    clear_vietnam_cache()


class _StubFetcher:
    fixture_dir = Path("__missing_fixture_dir__")
    foreign = {"buy": 10, "sell": 15, "net": -5}
    foreign_history = None
    quote_calls = 0
    news_calls = 0
    intraday_calls = 0
    fail_quote = False
    fail_news = False
    fail_intraday = False
    intraday = None

    def get_foreign_trading(self, symbol):
        self.quote_calls += 1
        if self.fail_quote:
            raise RuntimeError("quote failed")
        return self.foreign

    def get_foreign_trading_history(self, symbol, limit=20):
        self.quote_calls += 1
        if self.fail_quote:
            raise RuntimeError("quote failed")
        if self.foreign_history is not None:
            return self.foreign_history[:limit]
        return [self.foreign]

    def get_news(self, symbol, limit=3):
        self.news_calls += 1
        if not hasattr(self, "news_limits"):
            self.news_limits = []
        self.news_limits.append(limit)
        if self.fail_news:
            raise RuntimeError("news failed")
        return []

    def get_intraday_ohlcv(self, symbol, timeframe="1h", limit=8):
        self.intraday_calls += 1
        if self.fail_intraday:
            raise RuntimeError("intraday failed")
        return (self.intraday if self.intraday is not None else _sample_intraday_rows()).copy()


class _StubManager:
    def __init__(self, df, fixture_dir=None, foreign=None, foreign_history=None, fail_daily=False, intraday=None, daily_delay=0):
        self.df = df
        self.daily_calls = 0
        self.fail_daily = fail_daily
        self.daily_delay = daily_delay
        self.fetcher = _StubFetcher()
        self.fetcher.intraday = intraday
        if foreign is not None:
            self.fetcher.foreign = foreign
        if foreign_history is not None:
            self.fetcher.foreign_history = foreign_history
        if fixture_dir is not None:
            self.fetcher.fixture_dir = Path(fixture_dir)

    def get_daily_data(self, stock_code, days=30):
        self.daily_calls += 1
        if self.daily_delay:
            time.sleep(self.daily_delay)
        if self.fail_daily:
            raise RuntimeError("ohlcv failed")
        return self.df.copy(), "MozyfinFetcher"

    def _get_fetcher_by_name(self, name):
        return self.fetcher if name == "MozyfinFetcher" else None


def _sample_vn_rows():
    return pd.DataFrame(
        [
            {"date": f"2026-05-{day:02d}", "open": 10 + day, "high": 11 + day, "low": 9 + day, "close": 10 + day, "volume": 100 + day}
            for day in range(1, 22)
        ]
    )


def _sample_vn_rows_count(count=60):
    return pd.DataFrame(
        [
            {
                "date": (pd.Timestamp("2026-01-01") + pd.Timedelta(days=index)).strftime("%Y-%m-%d"),
                "open": 100 + index,
                "high": 102 + index,
                "low": 98 + index,
                "close": 100 + index,
                "volume": 1000 + index * 10,
            }
            for index in range(count)
        ]
    )


def _sample_intraday_rows():
    return pd.DataFrame(
        [
            {"timestamp": 1780459200, "date_time": "2026-06-03T04:00:00+00:00", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
            {"timestamp": 1780462800, "date_time": "2026-06-03T05:00:00+00:00", "open": 100, "high": 102, "low": 100, "close": 101, "volume": 1100},
            {"timestamp": 1780466400, "date_time": "2026-06-03T06:00:00+00:00", "open": 101, "high": 102, "low": 100, "close": 101, "volume": 900},
            {"timestamp": 1780470000, "date_time": "2026-06-03T07:00:00+00:00", "open": 101, "high": 105, "low": 100, "close": 104, "volume": 2500},
        ]
    )


def _mixed_session_intraday_rows():
    return pd.DataFrame(
        [
            {"timestamp": 1780372800, "date_time": "2026-06-02T04:00:00+00:00", "open": 90, "high": 120, "low": 80, "close": 95, "volume": 10000},
            {"timestamp": 1780376400, "date_time": "2026-06-02T05:00:00+00:00", "open": 95, "high": 130, "low": 90, "close": 100, "volume": 20000},
            {"timestamp": 1780459200, "date_time": "2026-06-03T04:00:00+00:00", "open": 100, "high": 104, "low": 99, "close": 102, "volume": 3000},
            {"timestamp": 1780462800, "date_time": "2026-06-03T05:00:00+00:00", "open": 102, "high": 106, "low": 101, "close": 105, "volume": 4000},
        ]
    )


def _foreign_history_rows(count=20, latest_day=21):
    rows = []
    for offset in range(count):
        day = latest_day - offset
        net = 1000 + offset
        rows.append(
            {
                "buy": 5000 + offset,
                "sell": 4000,
                "net": net,
                "date": f"2026-05-{day:02d}",
                "net_unit": "shares",
                "buy_raw_field": "buy_foreign_quantity",
                "sell_raw_field": "sell_foreign_quantity",
            }
        )
    return rows


def _expire_cache_entry(data_type, symbol="FPT", **params):
    key = vn_service._cache_key(data_type, symbol, **params)
    with vn_service._VN_CACHE_LOCK:
        vn_service._VN_CACHE[key].expires_at = vn_service._utc_now() - timedelta(seconds=1)


def test_default_vietnam_news_limit_is_five(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    manager = _StubManager(rows)
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30))

    service.build_watchlist(["FPT"])

    assert manager.fetcher.news_limits == [5]


def test_normalize_vietnam_tickers_dedupes_preserving_first_seen_order():
    assert normalize_vietnam_tickers(["fpt", "FPT", "FPT.VN", " acb", "", "bad-value", "ACB.VN"]) == ["FPT", "ACB"]


def test_watchlist_dedupes_before_fetching(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    manager = _StubManager(rows)
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=0))

    payload = service.build_watchlist(["fpt", "FPT", "FPT.VN", " acb"], include_intraday=False)

    assert [item["ticker"] for item in payload["watchlist"]] == ["FPT", "ACB"]
    assert manager.daily_calls == 2


def test_concurrent_identical_watchlist_requests_singleflight_daily_fetch(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    manager = _StubManager(rows, daily_delay=0.2)
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=0))

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(service.build_watchlist, ["FPT"], False, False),
            executor.submit(service.build_watchlist, ["FPT"], False, False),
        ]
        results = [future.result() for future in futures]

    assert manager.daily_calls == 1
    assert [result["watchlist"][0]["ticker"] for result in results] == ["FPT", "FPT"]
    assert {result["watchlist"][0]["cache_status"]["ohlcv_cache"] for result in results} == {"miss", "hit"}


def test_mozyfin_fetcher_maps_fixture_to_standard_ohlcv():
    fetcher = MozyfinFetcher(fixture_dir=str(FIXTURE_DIR))

    df = fetcher.get_daily_data("FPT", days=30)

    assert {"date", "open", "high", "low", "close", "volume", "amount", "pct_chg"}.issubset(df.columns)
    assert len(df) == 22
    assert df.iloc[-1]["close"] == 132.4
    assert df.iloc[-1]["exchange"] == "HOSE"
    assert df.iloc[-1]["market_index"] == "VNINDEX.VN"
    assert df.iloc[-1]["foreign_net"] == 80000


def test_mozyfin_quote_history_derives_foreign_net_from_buy_sell(monkeypatch):
    fetcher = MozyfinFetcher()
    calls = []

    def fake_run_csv_command(*args):
        calls.append(args)
        return [
            {"date": "2026-05-20", "buy_foreign_quantity": "1500", "sell_foreign_quantity": "400"},
            {"date": "2026-05-21", "buy_foreign_quantity": "2100", "sell_foreign_quantity": "900"},
        ]

    monkeypatch.setattr(fetcher, "_run_csv_command", fake_run_csv_command)

    history = fetcher.get_foreign_trading_history("FPT", limit=5)

    assert calls == [("quote", "FPT.VN", "--limit", "5")]
    assert [row["date"] for row in history] == ["2026-05-21", "2026-05-20"]
    assert history[0]["buy"] == 2100
    assert history[0]["sell"] == 900
    assert history[0]["net"] == 1200
    assert history[0]["net_unit"] == "shares"
    assert history[0]["buy_raw_field"] == "buy_foreign_quantity"
    assert history[0]["sell_raw_field"] == "sell_foreign_quantity"


def test_manager_uses_mozyfin_when_market_vn(monkeypatch):
    monkeypatch.setenv("MARKET", "VN")
    monkeypatch.setenv("MOZYFIN_FIXTURE_DIR", str(FIXTURE_DIR))
    Config.reset_instance()

    manager = DataFetcherManager()
    df, source = manager.get_daily_data("VPB", days=30)

    assert source == "MozyfinFetcher"
    assert not df.empty
    assert df.iloc[-1]["exchange"] == "HOSE"


def test_vietnam_dashboard_formulas_and_warnings(monkeypatch):
    monkeypatch.setenv("MARKET", "VN")
    monkeypatch.setenv("MOZYFIN_FIXTURE_DIR", str(FIXTURE_DIR))
    Config.reset_instance()
    manager = DataFetcherManager()

    payload = VietnamMarketService(
        manager=manager,
        config=VietnamDashboardConfig(history_days=30, news_limit=1),
    ).build_watchlist(["FPT", "VPB", "ACV"])

    assert payload["market"] == "VN"
    assert len(payload["watchlist"]) == 3
    fpt = next(item for item in payload["watchlist"] if item["ticker"] == "FPT")
    acv = next(item for item in payload["watchlist"] if item["ticker"] == "ACV")
    assert fpt["liquidity"]["score"] == 100
    assert fpt["foreign"]["signal"] == "foreign_net_positive"
    assert acv["exchange"] == "UPCoM"
    assert acv["price_limit"]["limit_pct"] == 15.0
    assert any("adjusted or ex-dividend" in warning for warning in acv["warnings"])
    assert payload["fixture_mode"] is True
    assert payload["data_quality"]["source"] == "Mozyfin fixture"
    assert payload["data_quality"]["symbols_loaded"] == 3
    assert payload["units"]["close"] == "VND"
    assert payload["units"]["foreign_net"] == "row-specific"
    assert fpt["indicators"]["ma20"] is not None
    assert fpt["indicators"]["ma50"] is None
    assert fpt["indicators"]["rsi14"] is not None
    assert fpt["indicators"]["bollinger"]["upper"] is not None
    assert fpt["indicators"]["avg_volume_20d"] > 0
    assert fpt["indicators"]["volume_ratio"] > 0
    assert fpt["indicators"]["high_20d"] >= fpt["close"]
    assert fpt["indicators"]["low_20d"] <= fpt["close"]
    assert fpt["indicators"]["foreign_net_5d"] is not None
    assert fpt["indicators"]["foreign_net_20d"] is not None
    assert fpt["status_labels"]


def test_daily_chart_data_order_and_indicator_gaps():
    rows = _sample_vn_rows_count(60)

    chart_data = normalize_daily_chart_data(rows)

    assert len(chart_data) == 60
    assert chart_data[0]["date"] == "2026-01-01"
    assert chart_data[-1]["date"] == "2026-03-01"
    assert chart_data[0]["ma20"] is None
    assert chart_data[0]["ma50"] is None
    assert chart_data[0]["rsi14"] is None
    assert chart_data[19]["ma20"] is not None
    assert chart_data[19]["bb_upper"] is not None
    assert chart_data[19]["bb_mid"] == chart_data[19]["ma20"]
    assert chart_data[49]["ma50"] is not None
    assert chart_data[-1]["rsi14"] is not None
    assert chart_data[-1]["volume_ma20"] is not None
    assert chart_data[-1]["volume_ma50"] is not None


def test_chart_endpoint_data_uses_daily_ohlcv_without_changing_latest_price(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows_count(60)
    manager = _StubManager(
        rows,
        foreign={
            "buy": 100,
            "sell": 40,
            "net": 60,
            "date": "2026-03-01",
            "latest_price": 999,
            "price_raw_field": "match_price",
            "price_date": "2026-03-01",
        },
    )
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=90, news_limit=1))

    item = service.build_watchlist(["FPT"], include_intraday=False)["watchlist"][0]
    chart = service.build_chart("FPT", "1Y")

    assert item["latest_price"] == 999
    assert item["latest_price_source"] == "quote"
    assert item["ohlcv_close"] == 159
    assert "chart_data" not in item
    assert chart["source"] == "Mozyfin"
    assert chart["timeframe"] == "1d"
    assert chart["points"][-1]["close"] == 159
    assert chart["points"][-1]["ma20"] is not None
    assert chart["points"][-1]["ma50"] is not None
    assert chart["points"][-1]["bb_upper"] is not None
    assert chart["points"][-1]["rsi14"] is not None
    assert chart["points"][-1]["volume_ma20"] is not None
    assert chart["points"][-1]["volume_ma50"] is not None


def test_chart_range_filter_preserves_indicator_warmup():
    rows = _sample_vn_rows_count(260)
    all_points = normalize_daily_chart_data(rows)

    filtered = filter_chart_points_by_range(all_points, "1M")

    assert 20 < len(filtered) < len(all_points)
    assert filtered[0]["date"] > all_points[0]["date"]
    assert filtered[0]["ma20"] is not None
    assert filtered[0]["ma50"] is not None
    assert filtered[0]["rsi14"] is not None
    assert filtered[0]["volume_ma20"] is not None
    assert filtered[0]["volume_ma50"] is not None


def test_build_chart_returns_more_than_100_ordered_points_for_one_year(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows_count(260)
    service = VietnamMarketService(
        manager=_StubManager(rows),
        config=VietnamDashboardConfig(history_days=90, news_limit=1),
    )

    chart = service.build_chart("FPT", "1Y")

    assert chart["symbol"] == "FPT"
    assert chart["range"] == "1Y"
    assert len(chart["points"]) > 100
    assert [point["date"] for point in chart["points"]] == sorted(point["date"] for point in chart["points"])
    assert chart["latest_date"] == chart["points"][-1]["date"]
    assert chart["points"][0]["ma20"] is None
    assert chart["points"][-1]["ma20"] is not None
    assert chart["points"][-1]["ma50"] is not None
    assert chart["points"][-1]["bb_upper"] is not None
    assert chart["points"][-1]["rsi14"] is not None


def test_vietnam_chart_api_returns_ordered_points(monkeypatch, tmp_path):
    class StubVietnamMarketService:
        def build_chart(self, symbol, range_label="6M"):
            return {
                "symbol": symbol,
                "source": "Mozyfin",
                "timeframe": "1d",
                "range": range_label,
                "latest_date": "2026-01-03",
                "points": [
                    {
                        "date": "2026-01-02",
                        "time": 1767312000,
                        "open": 10,
                        "high": 12,
                        "low": 9,
                        "close": 11,
                        "volume": 1000,
                        "volume_ma20": None,
                        "volume_ma50": None,
                        "ma20": None,
                        "ma50": None,
                        "rsi14": None,
                        "bb_upper": None,
                        "bb_mid": None,
                        "bb_lower": None,
                    },
                    {
                        "date": "2026-01-03",
                        "time": 1767398400,
                        "open": 11,
                        "high": 13,
                        "low": 10,
                        "close": 12,
                        "volume": 1200,
                        "volume_ma20": 1100,
                        "volume_ma50": None,
                        "ma20": 11,
                        "ma50": None,
                        "rsi14": 55,
                        "bb_upper": 13,
                        "bb_mid": 11,
                        "bb_lower": 9,
                    },
                ],
            }

    monkeypatch.setattr("api.v1.endpoints.stocks.VietnamMarketService", StubVietnamMarketService)
    client = TestClient(create_app(static_dir=tmp_path / "static"))

    response = client.get("/api/v1/stocks/vn/chart?symbol=ACB&range=6M")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "ACB"
    assert payload["source"] == "Mozyfin"
    assert payload["timeframe"] == "1d"
    assert payload["range"] == "6M"
    assert [point["date"] for point in payload["points"]] == ["2026-01-02", "2026-01-03"]
    assert payload["points"][1]["close"] == 12
    assert payload["points"][1]["volume_ma20"] == 1100


def test_price_semantics_and_foreign_date_match(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    manager = _StubManager(
        rows,
        foreign={
            "buy": 100,
            "sell": 40,
            "net": 60,
            "date": "2026-05-21",
            "net_unit": "shares",
            "buy_raw_field": "buy_foreign_quantity",
            "sell_raw_field": "sell_foreign_quantity",
        },
    )
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=1))

    payload = service.build_watchlist(["FPT"])
    item = payload["watchlist"][0]

    assert item["latest_price"] == item["ohlcv_close"] == item["close"]
    assert item["latest_price_source"] == "ohlcv"
    assert item["latest_price_raw_field"] == "close"
    assert item["latest_price_date"] == "2026-05-21"
    assert item["quote_price_date"] is None
    assert item["price_source_warning"] == "Quote does not provide a reliable latest price field; latest price uses OHLCV close."
    assert item["price_date"] == "2026-05-21"
    assert item["ohlcv_date"] == "2026-05-21"
    assert item["quote_date"] == "2026-05-21"
    assert item["foreign_net_date"] == "2026-05-21"
    assert item["foreign_date_match"] == "matched"
    assert item["candle_status"] == "unknown"
    assert item["final_close_status"] == "unknown"
    assert item["foreign_net_unit"] == "shares"
    assert item["foreign"]["net_unit"] == "shares"
    assert item["corporate_action"]["status"] == "unavailable"
    assert item["corporate_action"]["adjusted_reference_price"] is None
    assert item["corporate_action"]["adjustment_source"] == "manual_unavailable"
    assert item["foreign_buy_raw_field"] == "buy_foreign_quantity"
    assert item["foreign_sell_raw_field"] == "sell_foreign_quantity"
    assert any("Final close status is unknown" in warning for warning in item["warnings"])
    assert any("daily candle whose final status is unknown" in warning for warning in item["warnings"])
    assert payload["cache_metadata"]["cache_miss_count"] == 4


def test_corporate_action_reference_unavailable_does_not_change_raw_price():
    corporate_action = build_corporate_action_reference(previous_close=27000, current_price=27000)

    assert corporate_action["status"] == "unavailable"
    assert corporate_action["previous_close"] == 27000
    assert corporate_action["adjusted_reference_price"] is None
    assert corporate_action["price_vs_adjusted_reference"] is None
    assert corporate_action["adjustment_source"] == "manual_unavailable"


def test_vietnam_corporate_actions_unavailable_without_verified_provider(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    service = VietnamMarketService(manager=_StubManager(_sample_vn_rows()), config=VietnamDashboardConfig(history_days=30, news_limit=1))

    payload = service.build_corporate_actions(["FPT", "ACB"], months_back=6)

    assert payload["market"] == "VN"
    assert payload["status"] == "unavailable"
    assert payload["requested_tickers"] == ["FPT", "ACB"]
    assert payload["months_back"] == 6
    assert payload["items"] == []
    assert payload["source"] is None
    assert payload["error"] == "Corporate action calendar unavailable."
    assert "not inferred from KBS reference price" in payload["error_detail"]


def test_cash_dividend_reference_adjustment_is_separate_from_raw_close():
    corporate_action = build_corporate_action_reference(
        previous_close=27000,
        current_price=26500,
        event={
            "type": "cash_dividend",
            "ex_date": "2026-06-12",
            "cash_dividend_per_share": 1000,
            "adjustment_source": "provider_event",
        },
    )

    assert corporate_action["status"] == "detected"
    assert corporate_action["type"] == "cash_dividend"
    assert corporate_action["ex_date"] == "2026-06-12"
    assert corporate_action["cash_dividend_per_share"] == 1000
    assert corporate_action["previous_close"] == 27000
    assert corporate_action["adjusted_reference_price"] == 26000
    assert corporate_action["price_vs_adjusted_reference"] == 500
    assert corporate_action["price_vs_adjusted_reference_pct"] == pytest.approx(1.92)
    assert corporate_action["adjustment_source"] == "provider_event"


def test_quote_price_field_sets_latest_price_source_quote(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    manager = _StubManager(
        rows,
        foreign={
            "buy": 100,
            "sell": 40,
            "net": 60,
            "date": "2026-05-21",
            "net_unit": "shares",
            "buy_raw_field": "buy_foreign_quantity",
            "sell_raw_field": "sell_foreign_quantity",
            "latest_price": 99,
            "price_raw_field": "match_price",
            "price_date": "2026-05-21",
        },
    )
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=1))

    payload = service.build_watchlist(["FPT"])
    item = payload["watchlist"][0]

    assert item["latest_price"] == 99
    assert item["latest_price_source"] == "quote"
    assert item["latest_price_raw_field"] == "match_price"
    assert item["latest_price_date"] == "2026-05-21"
    assert item["quote_price_date"] == "2026-05-21"
    assert item["ohlcv_close"] == 31
    assert item["indicators"]["close"] == 31
    assert item["price_source_warning"] is None
    assert payload["cache_metadata"]["cache_miss_count"] == 4
    assert item["status_labels"]


def test_status_labels_match_status_details(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    manager = _StubManager(
        rows,
        foreign={
            "buy": 100,
            "sell": 40,
            "net": 60,
            "date": "2026-05-21",
            "net_unit": "shares",
            "buy_raw_field": "buy_foreign_quantity",
            "sell_raw_field": "sell_foreign_quantity",
        },
    )
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=1))

    item = service.build_watchlist(["FPT"])["watchlist"][0]
    detail_labels = [detail["label"] for detail in item["status_details"]]

    assert len(item["status_labels"]) == len(item["status_details"])
    assert set(item["status_labels"]) == set(detail_labels)


def test_missing_quote_price_falls_back_to_ohlcv_with_warning(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    manager = _StubManager(
        rows,
        foreign={
            "buy": 100,
            "sell": 40,
            "net": 60,
            "date": "2026-05-21",
            "net_unit": "shares",
            "buy_raw_field": "buy_foreign_quantity",
            "sell_raw_field": "sell_foreign_quantity",
            "latest_price": None,
            "price_raw_field": None,
            "price_date": None,
        },
    )
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=1))

    item = service.build_watchlist(["FPT"])["watchlist"][0]

    assert item["latest_price"] == item["ohlcv_close"] == 31
    assert item["latest_price_source"] == "ohlcv"
    assert item["latest_price_raw_field"] == "close"
    assert item["latest_price_date"] == "2026-05-21"
    assert item["quote_price_date"] is None
    assert "Quote does not provide a reliable latest price field" in item["price_source_warning"]
    assert any("Quote does not provide a reliable latest price field" in warning for warning in item["warnings"])


def test_foreign_date_mismatch_warns(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    manager = _StubManager(
        rows,
        foreign={
            "buy": 100,
            "sell": 40,
            "net": 60,
            "date": "2026-05-20",
            "net_unit": "shares",
            "buy_raw_field": "buy_foreign_quantity",
            "sell_raw_field": "sell_foreign_quantity",
        },
    )
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=1))

    item = service.build_watchlist(["FPT"])["watchlist"][0]

    assert item["ohlcv_date"] == "2026-05-21"
    assert item["foreign_net_date"] == "2026-05-20"
    assert item["foreign_date_match"] == "mismatched"
    assert any("Foreign net date does not match OHLCV date." in warning for warning in item["warnings"])
    assert any("Foreign net is not confirmed as same-day flow." in warning for warning in item["warnings"])


def test_latest_available_foreign_history_sums_and_preserves_mismatch(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    history = _foreign_history_rows(20, latest_day=20)
    manager = _StubManager(rows, foreign_history=history)
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=1))

    item = service.build_watchlist(["FPT"])["watchlist"][0]

    assert item["ohlcv_date"] == "2026-05-21"
    assert item["foreign_net_date"] == "2026-05-20"
    assert item["foreign_date_match"] == "mismatched"
    assert item["indicators"]["foreign_net_5d_latest_available"] == sum(row["net"] for row in history[:5])
    assert item["indicators"]["foreign_net_20d_latest_available"] == sum(row["net"] for row in history[:20])
    assert item["indicators"]["foreign_net_latest_available_date"] == "2026-05-20"
    assert item["indicators"]["foreign_net_history_count"] == 20
    assert any("Foreign net date does not match OHLCV date." in warning for warning in item["warnings"])
    assert any("Foreign net is not confirmed as same-day flow." in warning for warning in item["warnings"])


def test_latest_available_foreign_history_requires_twenty_rows_for_20d(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    history = _foreign_history_rows(5, latest_day=21)
    manager = _StubManager(rows, foreign_history=history)
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=1))

    item = service.build_watchlist(["FPT"])["watchlist"][0]

    assert item["foreign_date_match"] == "matched"
    assert item["indicators"]["foreign_net_5d_latest_available"] == sum(row["net"] for row in history)
    assert item["indicators"]["foreign_net_20d_latest_available"] is None
    assert item["indicators"]["foreign_net_history_count"] == 5


def test_foreign_unit_unknown_without_quantity_fields(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    manager = _StubManager(
        rows,
        foreign={
            "buy": 100,
            "sell": 40,
            "net": 60,
            "date": "2026-05-21",
            "net_unit": "unknown",
            "buy_raw_field": "foreign_buy",
            "sell_raw_field": "foreign_sell",
        },
    )
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=1))

    item = service.build_watchlist(["FPT"])["watchlist"][0]

    assert item["foreign_net_unit"] == "unknown"
    assert item["foreign_buy_raw_field"] == "foreign_buy"
    assert item["foreign_sell_raw_field"] == "foreign_sell"


def test_wilder_rsi14_deterministic_result():
    close = pd.Series([44, 44.15, 43.9, 44.35, 44.8, 45.1, 45.05, 45.6, 45.9, 46.2, 45.7, 46.1, 46.5, 46.9, 47.2, 47.0, 47.4, 47.8, 48.1, 47.9])

    assert calculate_rsi14(close) == pytest.approx(80.4396199158)


def _labels(details):
    return [detail["label"] for detail in details]


def _base_rule_indicators(**overrides):
    values = {
        "close": 100,
        "ma20": 100,
        "ma50": 100,
        "rsi14_wilder": 50,
        "bollinger": {"upper": 120, "middle": 100, "lower": 80},
        "avg_volume_20d": 200000,
        "volume_ratio": 1.0,
        "high_20d": 110,
        "low_20d": 90,
    }
    values.update(overrides)
    return values


def test_neutral_rule_default_watch_label():
    details = derive_neutral_status_details(
        _base_rule_indicators(ma20=105, ma50=100, high_20d=120, low_20d=80),
        change_pct=0,
        latest_price=100,
        final_close_status="final",
        candle_status="final",
        adjusted_price_status="unadjusted",
        foreign_date_match="matched",
        foreign_net_date="2026-05-21",
        foreign_net_unit="unknown",
        rows_loaded=30,
    )

    assert "Watch" in _labels(details)


def test_neutral_rule_stronger_than_short_term_average():
    details = derive_neutral_status_details(
        _base_rule_indicators(ma20=100, ma50=95),
        change_pct=0.5,
        latest_price=105,
        final_close_status="final",
        candle_status="final",
        adjusted_price_status="unadjusted",
        foreign_date_match="matched",
        foreign_net_date="2026-05-21",
        rows_loaded=30,
    )

    assert "Stronger than short-term average" in _labels(details)


def test_neutral_rule_weak_short_term():
    details = derive_neutral_status_details(
        _base_rule_indicators(ma20=105, ma50=110),
        change_pct=-1,
        latest_price=100,
        final_close_status="final",
        candle_status="final",
        adjusted_price_status="unadjusted",
        foreign_date_match="matched",
        foreign_net_date="2026-05-21",
        rows_loaded=30,
    )

    assert "Weak short-term" in _labels(details)


def test_neutral_rule_near_support_and_resistance():
    support = derive_neutral_status_details(
        _base_rule_indicators(low_20d=98, high_20d=130),
        latest_price=100,
        final_close_status="final",
        candle_status="final",
        adjusted_price_status="unadjusted",
        foreign_date_match="matched",
        foreign_net_date="2026-05-21",
        rows_loaded=30,
    )
    resistance = derive_neutral_status_details(
        _base_rule_indicators(low_20d=70, high_20d=102),
        latest_price=100,
        final_close_status="final",
        candle_status="final",
        adjusted_price_status="unadjusted",
        foreign_date_match="matched",
        foreign_net_date="2026-05-21",
        rows_loaded=30,
    )

    assert "Near support" in _labels(support)
    assert "Near resistance" in _labels(resistance)


def test_neutral_rule_breakout_candidate_with_volume_expansion():
    details = derive_neutral_status_details(
        _base_rule_indicators(high_20d=100.2, volume_ratio=1.6),
        latest_price=100,
        final_close_status="unknown",
        candle_status="unknown",
        adjusted_price_status="unadjusted",
        foreign_date_match="matched",
        foreign_net_date="2026-05-21",
        rows_loaded=30,
    )
    labels = _labels(details)
    breakout = next(detail for detail in details if detail["label"] == "Breakout candidate")

    assert "Breakout candidate" in labels
    assert "Volume expansion" in labels
    assert breakout["severity"] == "caution"


def test_neutral_rule_low_liquidity():
    details = derive_neutral_status_details(
        _base_rule_indicators(avg_volume_20d=90000),
        latest_price=100,
        final_close_status="final",
        candle_status="final",
        adjusted_price_status="unadjusted",
        foreign_date_match="matched",
        foreign_net_date="2026-05-21",
        rows_loaded=30,
    )

    assert "Low liquidity" in _labels(details)


def test_neutral_rule_overextended_from_rsi_and_bollinger():
    rsi_details = derive_neutral_status_details(
        _base_rule_indicators(rsi14_wilder=72),
        latest_price=100,
        final_close_status="final",
        candle_status="final",
        adjusted_price_status="unadjusted",
        foreign_date_match="matched",
        foreign_net_date="2026-05-21",
        rows_loaded=30,
    )
    bollinger_details = derive_neutral_status_details(
        _base_rule_indicators(bollinger={"upper": 99, "middle": 90, "lower": 80}),
        latest_price=100,
        final_close_status="final",
        candle_status="final",
        adjusted_price_status="unadjusted",
        foreign_date_match="matched",
        foreign_net_date="2026-05-21",
        rows_loaded=30,
    )

    assert "Overextended" in _labels(rsi_details)
    assert "Overextended" in _labels(bollinger_details)


def test_neutral_rule_foreign_stale_and_matched_net_labels():
    stale = derive_neutral_status_details(
        _base_rule_indicators(),
        latest_price=100,
        final_close_status="final",
        candle_status="final",
        adjusted_price_status="unadjusted",
        foreign_date_match="mismatched",
        foreign_net_date="2026-05-20",
        foreign_net_unit="shares",
        foreign_net=100,
        rows_loaded=30,
    )
    positive = derive_neutral_status_details(
        _base_rule_indicators(),
        latest_price=100,
        final_close_status="final",
        candle_status="final",
        adjusted_price_status="unadjusted",
        foreign_date_match="matched",
        foreign_net_date="2026-05-21",
        foreign_net_unit="shares",
        foreign_net=100,
        rows_loaded=30,
    )
    negative = derive_neutral_status_details(
        _base_rule_indicators(),
        latest_price=100,
        final_close_status="final",
        candle_status="final",
        adjusted_price_status="unadjusted",
        foreign_date_match="matched",
        foreign_net_date="2026-05-21",
        foreign_net_unit="shares",
        foreign_net=-100,
        rows_loaded=30,
    )

    assert "Foreign data stale" in _labels(stale)
    assert "Foreign net positive" not in _labels(stale)
    assert "Foreign net positive" in _labels(positive)
    assert "Foreign net negative" in _labels(negative)


def test_neutral_rule_finality_adjustment_and_forbidden_labels():
    details = derive_neutral_status_details(
        _base_rule_indicators(),
        latest_price=100,
        final_close_status="unknown",
        candle_status="unknown",
        adjusted_price_status="unknown",
        foreign_date_match="matched",
        foreign_net_date="2026-05-21",
        rows_loaded=30,
    )
    labels = set(_labels(details))

    assert "Price finality unknown" in labels
    assert "Adjusted price unknown" in labels
    assert "Indicator caution" in labels
    assert labels.isdisjoint({"Buy", "Sell", "Hold", "Accumulate", "Cut loss", "Take profit", "Target price", "Entry price"})


def test_formula_helpers_are_stable():
    fetcher = MozyfinFetcher(fixture_dir=str(FIXTURE_DIR))
    df = fetcher.get_daily_data("ACV", days=30)

    liquidity = calculate_liquidity_score(df)
    limit_state = calculate_price_limit_state(df, "ACV")

    assert liquidity["score"] < 50
    assert liquidity["avg_volume_20d"] > 0
    assert limit_state["limit_pct"] == 15.0
    assert limit_state["ceiling_price"] is not None


def test_indicator_helpers_are_stable():
    fetcher = MozyfinFetcher(fixture_dir=str(FIXTURE_DIR))
    df = fetcher.get_daily_data("FPT", days=30)

    indicators = calculate_vietnam_indicators(df, {"net": 80000})
    labels = derive_neutral_status_labels(indicators, 1.15)

    assert indicators["ma20"] is not None
    assert indicators["ma50"] is None
    assert indicators["rsi14"] is not None
    assert indicators["bollinger"]["middle"] == indicators["ma20"]
    assert indicators["avg_volume_20d"] > 0
    assert indicators["volume_ratio"] > 0
    assert indicators["distance_to_20d_high_pct"] <= 0
    assert indicators["distance_to_20d_low_pct"] >= 0
    assert indicators["foreign_net_5d"] is not None
    assert indicators["foreign_net_20d"] is not None
    assert set(labels).issubset(
        {
            "Watch",
            "Stronger than short-term average",
            "Weak short-term",
            "Near support",
            "Near resistance",
            "Breakout candidate",
            "Overextended",
            "Volume expansion",
            "Low liquidity",
            "Foreign data stale",
            "Foreign net positive",
            "Foreign net negative",
            "Indicator caution",
            "Price finality unknown",
            "Adjusted price unknown",
        }
    )


def test_intraday_candle_normalization():
    raw = pd.DataFrame(
        [
            {"timestamp": "1780470000", "open": "77500", "high": "77600", "low": "76500", "close": "76600", "volume": "4622300"},
        ]
    )
    fetcher = MozyfinFetcher(fixture_dir=str(FIXTURE_DIR))

    normalized = fetcher._normalize_intraday_data(raw, "FPT")

    assert normalized.iloc[0]["timestamp"] == 1780470000
    assert normalized.iloc[0]["date_time"].startswith("2026-06-03T")
    assert normalized.iloc[0]["open"] == 77500
    assert normalized.iloc[0]["volume"] == 4622300


def test_intraday_pulse_calculation_and_labels():
    candles = normalize_intraday_candles(_sample_intraday_rows(), 8)
    pulse = calculate_intraday_pulse(candles)
    details = derive_intraday_details(candles, pulse)
    labels = _labels(details)

    assert pulse["latest_1h_close"] == 104
    assert pulse["latest_1h_open"] == 101
    assert pulse["latest_1h_change"] == 3
    assert pulse["latest_1h_change_percent"] == pytest.approx(2.97)
    assert pulse["session_high_from_1h"] == 105
    assert pulse["session_low_from_1h"] == 99
    assert pulse["session_range_pct_from_1h"] == pytest.approx(6.0)
    assert pulse["session_volume_from_1h"] == 5500
    assert pulse["session_candles_count"] == 4
    assert pulse["cumulative_1h_volume"] == 5500
    assert pulse["loaded_candles_total_volume"] == 5500
    assert pulse["direction"] == "up"
    assert pulse["range_percent"] == pytest.approx(4.95)
    assert pulse["volume_vs_avg_1h"] == pytest.approx(2.5)
    assert "Intraday up" in labels
    assert "Intraday volume expansion" in labels
    assert "Intraday wide range" in labels
    assert "Not realtime quote" in labels


def test_intraday_session_fields_use_latest_vn_date_only():
    candles = normalize_intraday_candles(_mixed_session_intraday_rows(), 8)
    pulse = calculate_intraday_pulse(candles)

    assert pulse["latest_1h_close"] == 105
    assert pulse["latest_1h_volume"] == 4000
    assert pulse["loaded_candles_total_volume"] == 37000
    assert pulse["cumulative_1h_volume"] == 37000
    assert pulse["session_candles_count"] == 2
    assert pulse["session_high_from_1h"] == 106
    assert pulse["session_low_from_1h"] == 99
    assert pulse["session_range_pct_from_1h"] == pytest.approx(7.0)
    assert pulse["session_volume_from_1h"] == 7000


def test_intraday_session_fields_are_empty_when_timestamps_are_unusable():
    candles = [
        {"date_time": "not-a-date", "open": 100, "high": 105, "low": 99, "close": 104, "volume": 1000},
    ]
    pulse = calculate_intraday_pulse(candles)

    assert pulse["latest_1h_close"] == 104
    assert pulse["latest_1h_volume"] == 1000
    assert pulse["loaded_candles_total_volume"] == 1000
    assert pulse["session_candles_count"] == 0
    assert pulse["session_high_from_1h"] is None
    assert pulse["session_low_from_1h"] is None
    assert pulse["session_range_pct_from_1h"] is None
    assert pulse["session_volume_from_1h"] is None


@pytest.mark.parametrize(
    ("latest_open", "latest_close", "expected_label", "expected_direction"),
    [
        (100, 101, "Intraday up", "up"),
        (100, 99, "Intraday down", "down"),
        (100, 100, "Intraday flat", "flat"),
    ],
)
def test_intraday_direction_labels(latest_open, latest_close, expected_label, expected_direction):
    rows = _sample_intraday_rows()
    rows.loc[rows.index[-1], "open"] = latest_open
    rows.loc[rows.index[-1], "close"] = latest_close
    candles = normalize_intraday_candles(rows, 8)
    pulse = calculate_intraday_pulse(candles)
    labels = _labels(derive_intraday_details(candles, pulse))

    assert pulse["direction"] == expected_direction
    assert expected_label in labels


def test_intraday_limited_data_and_forbidden_labels():
    candles = normalize_intraday_candles(_sample_intraday_rows().head(2), 8)
    pulse = calculate_intraday_pulse(candles)
    labels = set(_labels(derive_intraday_details(candles, pulse)))

    assert "Intraday data limited" in labels
    assert "Not realtime quote" in labels
    assert labels.isdisjoint({"Buy", "Sell", "Hold", "Accumulate", "Cut loss", "Take profit", "Entry", "Target"})


def test_watchlist_intraday_fields_and_latest_price_unchanged(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    manager = _StubManager(rows, intraday=_sample_intraday_rows())
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=1))

    item = service.build_watchlist(["FPT"])["watchlist"][0]

    assert item["latest_price"] == item["ohlcv_close"] == 31
    assert item["intraday_timeframe"] == "1h"
    assert item["intraday_source"] == "Mozyfin OHLCV"
    assert item["intraday_is_realtime_quote"] is False
    assert item["intraday_warning"] == "Intraday 1H candle data is not a realtime matched quote."
    assert item["intraday_candles"][-1]["close"] == 104
    assert item["intraday_pulse"]["latest_1h_close"] == 104
    assert item["intraday_pulse"]["session_volume_from_1h"] == 5500
    assert item["intraday_pulse"]["loaded_candles_total_volume"] == 5500
    assert item["intraday_pulse"]["session_candles_count"] == 4
    assert "Not realtime quote" in item["intraday_labels"]
    assert item["cache_status"]["intraday_cache"] == "miss"


def test_intraday_cache_hit_miss_behavior(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    manager = _StubManager(rows, intraday=_sample_intraday_rows())
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=1))

    first = service.build_watchlist(["FPT"])
    second = service.build_watchlist(["FPT"])
    _expire_cache_entry("intraday_ohlcv", timeframe="1h", limit=8)
    refreshed = service.build_watchlist(["FPT"])

    assert first["watchlist"][0]["cache_status"]["intraday_cache"] == "miss"
    assert second["watchlist"][0]["cache_status"]["intraday_cache"] == "hit"
    assert refreshed["watchlist"][0]["cache_status"]["intraday_cache"] == "refresh"
    assert manager.fetcher.intraday_calls == 2


def test_validation_warns_for_missing_fields_without_crashing(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = pd.DataFrame(
        [
            {"date": "2026-06-01", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 100},
            {"date": "bad-date", "open": 10, "high": 11, "low": 9, "close": None, "volume": None},
        ]
    )
    service = VietnamMarketService(
        manager=_StubManager(rows, foreign={"buy": None, "sell": None, "net": None}),
        config=VietnamDashboardConfig(history_days=2, news_limit=0),
    )

    payload = service.build_watchlist(["FPT"])
    item = payload["watchlist"][0]

    assert payload["fixture_mode"] is False
    assert payload["data_quality"]["source"] == "Mozyfin live"
    assert item["validation"]["valid"] is False
    assert set(item["validation"]["missing_fields"]) == {"date", "close", "volume", "foreign_net"}
    assert "FPT" in payload["data_quality"]["missing_fields"]
    assert any("Missing close" in warning for warning in item["warnings"])


def test_health_payload_matches_required_shape(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = pd.DataFrame(
        [
            {"date": "2026-06-01", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 100},
            {"date": "2026-06-02", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 200},
        ]
    )
    manager = _StubManager(rows, foreign={"buy": None, "sell": None, "net": None})
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=2, news_limit=0))
    service.build_watchlist(["FPT"])

    health = service.build_health(["FPT"])

    assert health["source"] == "Mozyfin live"
    assert health["fixture_mode"] is False
    assert health["symbols_loaded"] == 1
    assert health["last_trading_date"] == "2026-06-02"
    assert health["missing_fields"] == {"FPT": ["foreign_net"]}
    assert health["errors"] == {}


def test_watchlist_cache_miss_then_hit(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    manager = _StubManager(rows)
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=1))

    first = service.build_watchlist(["FPT"])
    second = service.build_watchlist(["FPT"])

    assert first["cache_metadata"]["cache_miss_count"] == 4
    assert first["watchlist"][0]["cache_status"] == {
        "ohlcv_cache": "miss",
        "quote_cache": "miss",
        "intraday_cache": "miss",
        "news_cache": "miss",
    }
    assert second["cache_metadata"]["cache_hit_count"] == 4
    assert second["watchlist"][0]["cache_status"] == {
        "ohlcv_cache": "hit",
        "quote_cache": "hit",
        "intraday_cache": "hit",
        "news_cache": "hit",
    }
    assert manager.daily_calls == 1
    assert manager.fetcher.quote_calls == 1
    assert manager.fetcher.intraday_calls == 1
    assert manager.fetcher.news_calls == 1


def test_watchlist_cache_mixed_ttl_expires_independently(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    manager = _StubManager(rows)
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=1))

    first = service.build_watchlist(["FPT"])
    second = service.build_watchlist(["FPT"])

    assert first["watchlist"][0]["cache_status"] == {
        "ohlcv_cache": "miss",
        "quote_cache": "miss",
        "intraday_cache": "miss",
        "news_cache": "miss",
    }
    assert second["watchlist"][0]["cache_status"] == {
        "ohlcv_cache": "hit",
        "quote_cache": "hit",
        "intraday_cache": "hit",
        "news_cache": "hit",
    }
    assert manager.daily_calls == 1
    assert manager.fetcher.quote_calls == 1
    assert manager.fetcher.intraday_calls == 1
    assert manager.fetcher.news_calls == 1

    _expire_cache_entry("quote", limit=vn_service.FOREIGN_HISTORY_LIMIT)
    after_quote_ttl = service.build_watchlist(["FPT"])
    assert after_quote_ttl["watchlist"][0]["cache_status"] == {
        "ohlcv_cache": "hit",
        "quote_cache": "refresh",
        "intraday_cache": "hit",
        "news_cache": "hit",
    }
    assert manager.daily_calls == 1
    assert manager.fetcher.quote_calls == 2
    assert manager.fetcher.intraday_calls == 1
    assert manager.fetcher.news_calls == 1

    _expire_cache_entry("ohlcv", timeframe="1d", limit=260, days=30)
    _expire_cache_entry("quote", limit=vn_service.FOREIGN_HISTORY_LIMIT)
    _expire_cache_entry("intraday_ohlcv", timeframe="1h", limit=8)
    after_ohlcv_ttl = service.build_watchlist(["FPT"])
    assert after_ohlcv_ttl["watchlist"][0]["cache_status"] == {
        "ohlcv_cache": "refresh",
        "quote_cache": "refresh",
        "intraday_cache": "refresh",
        "news_cache": "hit",
    }
    assert manager.daily_calls == 2
    assert manager.fetcher.quote_calls == 3
    assert manager.fetcher.intraday_calls == 2
    assert manager.fetcher.news_calls == 1

    _expire_cache_entry("news", limit=1)
    after_news_ttl = service.build_watchlist(["FPT"])
    assert after_news_ttl["watchlist"][0]["cache_status"] == {
        "ohlcv_cache": "hit",
        "quote_cache": "hit",
        "intraday_cache": "hit",
        "news_cache": "refresh",
    }
    assert manager.daily_calls == 2
    assert manager.fetcher.quote_calls == 3
    assert manager.fetcher.intraday_calls == 2
    assert manager.fetcher.news_calls == 2


def test_force_refresh_bypasses_cache(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    manager = _StubManager(rows)
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=1))

    service.build_watchlist(["FPT"])
    forced = service.build_watchlist(["FPT"], force_refresh=True)

    assert forced["watchlist"][0]["cache_status"]["ohlcv_cache"] == "refresh"
    assert forced["watchlist"][0]["cache_status"]["quote_cache"] == "refresh"
    assert forced["watchlist"][0]["cache_status"]["intraday_cache"] == "refresh"
    assert forced["watchlist"][0]["cache_status"]["news_cache"] == "refresh"
    assert manager.daily_calls == 2
    assert manager.fetcher.quote_calls == 2
    assert manager.fetcher.intraday_calls == 2
    assert manager.fetcher.news_calls == 2


def test_stale_cache_returned_when_live_refresh_fails(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = _sample_vn_rows()
    manager = _StubManager(rows)
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=1))
    service.build_watchlist(["FPT"])

    manager.fail_daily = True
    manager.fetcher.fail_quote = True
    manager.fetcher.fail_intraday = True
    manager.fetcher.fail_news = True
    stale = service.build_watchlist(["FPT"], force_refresh=True)

    item = stale["watchlist"][0]
    assert item["cache_status"] == {
        "ohlcv_cache": "stale",
        "quote_cache": "stale",
        "intraday_cache": "stale",
        "news_cache": "stale",
    }
    assert stale["cache_metadata"]["stale_cache_used_count"] == 4
    assert any("stale cached data" in warning for warning in item["warnings"])


def test_no_cache_live_error_returns_row_error(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    rows = pd.DataFrame(
        [{"date": "2026-06-01", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 100}]
    )
    manager = _StubManager(rows, fail_daily=True)
    service = VietnamMarketService(manager=manager, config=VietnamDashboardConfig(history_days=30, news_limit=1))

    payload = service.build_watchlist(["FPT"])
    item = payload["watchlist"][0]

    assert item["error"] == "ohlcv failed"
    assert item["cache_status"]["ohlcv_cache"] == "error"
    assert any("Data unavailable" in warning for warning in item["warnings"])


def test_fixture_mode_missing_file_does_not_fall_through(tmp_path):
    fetcher = MozyfinFetcher(fixture_dir=str(tmp_path))

    try:
        fetcher.get_daily_data("FPT", days=30)
    except DataFetchError as exc:
        assert "Fixture mode is active" in str(exc)
        assert "fpt_ohlcv.csv" in str(exc)
    else:
        raise AssertionError("Expected fixture-mode missing file error")


def test_mozyfin_cli_error_suppresses_bundled_node_dump(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    monkeypatch.setenv("MOZYFIN_COMMAND", "mozyfin-cli")
    huge_stderr = "\n".join(
        [
            "Request failed while fetching OHLCV",
            'file:///usr/local/lib/node_modules/mozyfin-cli/dist/index.js:24 `)}),this}_outputHelpIfRequested(e)',
            'kClose:Symbol("close"),kDestroy:Symbol("destroy"),undici.error.UND_ERR_CONNECT_TIMEOUT',
            "Retry later or check network connectivity.",
            "A" * 500,
        ]
    )

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr=huge_stderr)

    monkeypatch.setattr(subprocess, "run", fake_run)
    fetcher = MozyfinFetcher()

    with pytest.raises(DataFetchError) as exc_info:
        fetcher._run_csv_command("ohlcv", "FPT.VN", "--timeframe", "1d", "--limit", "3")

    message = str(exc_info.value)
    assert "mozyfin-cli ohlcv for FPT.VN exited with code 1" in message
    assert "Request failed while fetching OHLCV" in message
    assert "Retry later or check network connectivity." in message
    assert "node_modules/mozyfin-cli/dist/index.js" not in message
    assert "Symbol(" not in message
    assert "undici.error" not in message
    assert len(message) < 900


def test_mozyfin_cli_timeout_message_omits_full_command_and_key(monkeypatch):
    monkeypatch.delenv("MOZYFIN_FIXTURE_DIR", raising=False)
    monkeypatch.setenv("MOZYFIN_COMMAND", "mozyfin-cli")
    monkeypatch.setenv("MOZYFIN_API_KEY", "secret-value-that-must-not-appear")
    monkeypatch.setenv("MOZYFIN_TIMEOUT_SECONDS", "1")

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    fetcher = MozyfinFetcher()

    with pytest.raises(DataFetchError) as exc_info:
        fetcher._run_csv_command("ohlcv", "FPT.VN", "--timeframe", "1d", "--limit", "3")

    message = str(exc_info.value)
    assert message == "mozyfin-cli ohlcv for FPT.VN timed out after 1s"
    assert "secret-value-that-must-not-appear" not in message
    assert "--api-key" not in message
