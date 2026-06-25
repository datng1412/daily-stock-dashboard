# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests

from data_provider.ssi_fastconnect_fetcher import (
    DISABLED_REASON,
    MISSING_CREDENTIALS_REASON,
    REQUEST_FAILED_REASON,
    SSI_REALTIME_ENDPOINT_CANDIDATES,
    SSI_REALTIME_STREAMING_DATA_TYPES,
    SSI_CHUNK_MAX_DAYS,
    SsiFastConnectFetcher,
    build_ssi_date_windows,
    format_ssi_date,
)
from data_provider.ssi_streaming_realtime import SSI_STREAMING_REALTIME_DISABLED_REASON
from src.config import Config


SECRET_TOKEN = "SECRET_ACCESS_TOKEN_DO_NOT_EXPOSE"


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, json_error=None):
        self.status_code = status_code
        self.payload = payload
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


class _FakeSession:
    def __init__(self, post_items=None, get_items=None):
        self.post_items = list(post_items or [])
        self.get_items = list(get_items or [])
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        item = self.post_items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        item = self.get_items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _token_response():
    return _FakeResponse(
        payload={
            "data": {
                "accessToken": SECRET_TOKEN,
                "expiresIn": 1200,
            }
        }
    )


def _fetcher(session=None, **kwargs):
    defaults = {
        "enabled": True,
        "base_url": "https://example.test/Market",
        "consumer_id": "test-consumer",
        "consumer_secret": "test-secret",
        "timeout_seconds": 3,
        "cache_ttl_seconds": 0,
        "token_ttl_seconds": 900,
        "session": session or _FakeSession(post_items=[_token_response()]),
        "config": SimpleNamespace(),
    }
    defaults.update(kwargs)
    return SsiFastConnectFetcher(**defaults)


def test_provider_disabled_returns_unavailable_cleanly():
    fetcher = _fetcher(enabled=False)

    assert fetcher.health_check() == {
        "status": "unavailable",
        "source": "SSI",
        "reason": DISABLED_REASON,
    }
    assert fetcher.get_daily_ohlcv("FPT") == {
        "status": "unavailable",
        "source": "SSI",
        "reason": DISABLED_REASON,
    }


def test_missing_credentials_returns_unavailable_cleanly():
    fetcher = _fetcher(consumer_id="", consumer_secret="")

    assert fetcher.health_check() == {
        "status": "unavailable",
        "source": "SSI",
        "reason": MISSING_CREDENTIALS_REASON,
    }
    assert fetcher.get_daily_stock_price("FPT") == {
        "status": "unavailable",
        "source": "SSI",
        "reason": MISSING_CREDENTIALS_REASON,
    }


def test_config_defaults_keep_ssi_disabled(monkeypatch):
    with patch.dict("os.environ", {"STOCK_LIST": "600519"}, clear=True), patch(
        "src.config.setup_env"
    ), patch.object(Config, "_parse_litellm_yaml", return_value=[]):
        config = Config._load_from_env()

    assert config.ssi_fastconnect_enabled is False
    assert config.ssi_fastconnect_base_url == "https://fc-data.ssi.com.vn/api/v2/Market"
    assert config.ssi_fastconnect_consumer_id is None
    assert config.ssi_fastconnect_consumer_secret is None
    assert config.ssi_fastconnect_timeout_seconds == 10
    assert config.ssi_fastconnect_cache_ttl_seconds == 300
    assert config.ssi_fastconnect_token_ttl_seconds == 900
    assert config.ssi_fastconnect_intraday_enabled is True
    assert config.ssi_fastconnect_realtime_enabled is True
    assert config.ssi_fastconnect_trade_tape_enabled is True
    assert config.ssi_streaming_realtime_enabled is False
    assert config.ssi_streaming_realtime_cache_ttl_seconds == 15
    assert config.ssi_streaming_realtime_channel_template == "X: {symbol}"
    assert config.vn_intraday_data_provider == "ssi"
    assert config.vn_realtime_data_provider == "ssi"
    assert config.vn_trade_tape_provider == "ssi"
    assert config.kbs_enabled is False
    assert config.vn_allow_legacy_kbs_provider is False


def test_access_token_success_stores_token_without_public_exposure():
    fetcher = _fetcher()

    result = fetcher.get_access_token()

    assert result["status"] == "ok"
    assert fetcher._access_token == SECRET_TOKEN
    assert SECRET_TOKEN not in str(result)


def test_token_is_not_present_in_error_output():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[requests.exceptions.Timeout(f"timed out with {SECRET_TOKEN}")],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_daily_ohlcv("FPT")

    assert payload["status"] == "unavailable"
    assert payload["source"] == "SSI"
    assert payload["reason"] == REQUEST_FAILED_REASON
    assert SECRET_TOKEN not in str(payload)


def test_format_ssi_date_outputs_dd_mm_yyyy():
    assert format_ssi_date("2026-06-17") == "17/06/2026"
    assert format_ssi_date("17/06/2026") == "17/06/2026"


def test_date_window_helper_splits_range_into_safe_chronological_windows():
    windows = build_ssi_date_windows("2025-06-17", "2026-06-17")

    assert windows[0] == ("17/06/2025", "15/07/2025")
    assert windows[1] == ("16/07/2025", "13/08/2025")
    assert len(windows) == 13
    previous_end = None
    for from_value, to_value in windows:
        start_ts = datetime.strptime(from_value, "%d/%m/%Y").date()
        end_ts = datetime.strptime(to_value, "%d/%m/%Y").date()
        assert start_ts <= end_ts
        assert (end_ts - start_ts).days + 1 <= SSI_CHUNK_MAX_DAYS
        if previous_end:
            assert start_ts == previous_end + timedelta(days=1)
        previous_end = end_ts


def test_daily_ohlc_sends_explicit_paged_date_params():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[_FakeResponse(payload={"data": [{"TradingDate": "2026-06-17", "Close": "124.6"}]})],
    )
    fetcher = _fetcher(session=session)

    fetcher.get_daily_ohlcv("fpt", from_date="01/01/2026", to_date="17/06/2026", limit=1000)

    _, _, kwargs = session.calls[-1]
    assert kwargs["params"] == {
        "symbol": "FPT",
        "fromDate": "01/01/2026",
        "toDate": "17/06/2026",
        "pageIndex": 1,
        "pageSize": 1000,
        "ascending": "true",
    }


def test_daily_stock_price_sends_market_and_explicit_paged_date_params():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[_FakeResponse(payload={"data": [{"TradingDate": "2026-06-17", "Close": "124.6"}]})],
    )
    fetcher = _fetcher(session=session)

    fetcher.get_daily_stock_price("fpt", market="hose", from_date="2026-01-01", to_date="2026-01-29", limit=1000)

    _, _, kwargs = session.calls[-1]
    assert kwargs["params"] == {
        "symbol": "FPT",
        "market": "HOSE",
        "Fromdate": "01/01/2026",
        "Todate": "29/01/2026",
        "pageIndex": 1,
        "pageSize": 1000,
    }


def test_daily_index_sends_index_id_and_explicit_paged_date_params():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[_FakeResponse(payload={"data": [{"TradingDate": "2026-06-17", "IndexValue": "1315.22"}]})],
    )
    fetcher = _fetcher(session=session)

    fetcher.get_daily_index("vnindex", from_date="01/01/2026", to_date="29/01/2026", limit=1000)

    _, _, kwargs = session.calls[-1]
    assert kwargs["params"] == {
        "indexID": "VNINDEX",
        "Fromdate": "01/01/2026",
        "Todate": "29/01/2026",
        "pageIndex": 1,
        "pageSize": 1000,
    }


def test_intraday_ohlcv_sends_ssi_params_and_maps_sorted_candles():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(
                payload={
                    "data": [
                        {
                            "TradingTime": "2026-06-17 10:00:00",
                            "OpenPrice": "101",
                            "HighPrice": "103",
                            "LowPrice": "100",
                            "ClosePrice": "102",
                            "TotalVolume": "2000",
                        },
                        {
                            "TradingTime": "2026-06-17 09:00:00",
                            "OpenPrice": "100",
                            "HighPrice": "102",
                            "LowPrice": "99",
                            "ClosePrice": "101",
                            "TotalVolume": "1000",
                        },
                    ]
                }
            )
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_intraday_ohlcv("fpt", from_date="2026-06-17", to_date="2026-06-17", limit=10, interval="1h")

    _, _, kwargs = session.calls[-1]
    assert kwargs["params"] == {
        "symbol": "FPT",
        "timeFrame": "1h",
        "fromDate": "17/06/2026",
        "toDate": "17/06/2026",
        "pageIndex": 1,
        "pageSize": 1000,
        "ascending": "true",
    }
    assert payload["status"] == "ok"
    assert payload["source"] == "SSI"
    assert [row["close"] for row in payload["rows"]] == [101.0, 102.0]
    assert payload["rows"][0]["ticker"] == "FPT"
    assert payload["request_page_size"] == 1000


def test_intraday_ohlcv_keeps_latest_rows_after_sorting_oldest_first_response():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(
                payload={
                    "data": [
                        {
                            "TradingTime": "2026-06-17 09:00:00",
                            "OpenPrice": "100",
                            "HighPrice": "101",
                            "LowPrice": "99",
                            "ClosePrice": "100.5",
                            "TotalVolume": "1000",
                        },
                        {
                            "TradingTime": "2026-06-24 10:00:00",
                            "OpenPrice": "110",
                            "HighPrice": "111",
                            "LowPrice": "109",
                            "ClosePrice": "110.5",
                            "TotalVolume": "2000",
                        },
                        {
                            "TradingTime": "2026-06-24 10:01:00",
                            "OpenPrice": "111",
                            "HighPrice": "112",
                            "LowPrice": "110",
                            "ClosePrice": "111.5",
                            "TotalVolume": "3000",
                        },
                    ]
                }
            )
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_intraday_ohlcv("FPT", from_date="2026-06-17", to_date="2026-06-24", limit=2, interval="1h")

    assert payload["status"] == "ok"
    assert [row["date_time"] for row in payload["rows"]] == [
        "2026-06-24T10:00:00",
        "2026-06-24T10:01:00",
    ]
    assert [row["close"] for row in payload["rows"]] == [110.5, 111.5]


def test_intraday_ohlcv_paginates_before_applying_public_limit():
    old_rows = []
    for index in range(1000):
        old_rows.append(
            {
                "TradingTime": f"2026-06-17 09:{index % 60:02d}:00",
                "OpenPrice": "100",
                "HighPrice": "101",
                "LowPrice": "99",
                "ClosePrice": str(100 + index / 1000),
                "TotalVolume": "1000",
            }
        )
    latest_rows = [
        {
            "TradingTime": "2026-06-24 10:00:00",
            "OpenPrice": "110",
            "HighPrice": "111",
            "LowPrice": "109",
            "ClosePrice": "110.5",
            "TotalVolume": "2000",
        },
        {
            "TradingTime": "2026-06-24 10:01:00",
            "OpenPrice": "111",
            "HighPrice": "112",
            "LowPrice": "110",
            "ClosePrice": "111.5",
            "TotalVolume": "3000",
        },
    ]
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(payload={"data": old_rows, "totalRecord": 1002}),
            _FakeResponse(payload={"data": latest_rows, "totalRecord": 1002}),
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_intraday_ohlcv("FPT", from_date="2026-06-17", to_date="2026-06-24", limit=2, interval="1h")

    get_calls = [call for call in session.calls if call[0] == "GET"]
    assert get_calls[0][2]["params"]["pageIndex"] == 1
    assert get_calls[1][2]["params"]["pageIndex"] == 2
    assert payload["pages_used"] == 2
    assert [row["date_time"] for row in payload["rows"]] == [
        "2026-06-24T10:00:00",
        "2026-06-24T10:01:00",
    ]


def test_intraday_ohlcv_disabled_does_not_request_token():
    session = _FakeSession()
    fetcher = _fetcher(session=session, intraday_enabled=False)

    payload = fetcher.get_intraday_ohlcv("FPT")

    assert payload["status"] == "disabled"
    assert payload["source"] == "SSI"
    assert payload["rows"] == []
    assert session.calls == []


def test_realtime_snapshot_maps_ssi_like_quote_row():
    fetcher = _fetcher()

    row = fetcher._map_realtime_snapshot(
        {
            "Symbol": "FPT",
            "LastPrice": "130.5",
            "Change": "1.5",
            "ChangePercent": "1.16",
            "RefPrice": "129",
            "CeilingPrice": "138",
            "FloorPrice": "120",
            "OpenPrice": "129.5",
            "HighPrice": "132",
            "LowPrice": "128",
            "TotalVolume": "1234567",
            "TotalValue": "123456789000",
            "BidPrice1": "130.4",
            "BidVol1": "1000",
            "AskPrice1": "130.6",
            "AskVol1": "2000",
        },
        fallback_symbol="FPT",
    )

    assert row["source"] == "SSI"
    assert row["ticker"] == "FPT"
    assert row["price"] == 130.5
    assert row["reference_price"] == 129.0
    assert row["bid_levels"][0] == {"price": 130.4, "volume": 1000.0}
    assert SECRET_TOKEN not in str(row)


def test_realtime_snapshot_accepts_safe_field_aliases():
    fetcher = _fetcher()

    row = fetcher._map_realtime_snapshot(
        {
            "StockCode": "FPT",
            "MatchPrice": "130.5",
            "ChangeValue": "1.5",
            "RatioChange": "1.16",
            "BasicPrice": "129",
            "TotalVol": "1234567",
            "TotalVal": "123456789000",
            "bidLevels": [{"price": "130.4", "volume": "1000"}],
            "askLevels": [{"price": "130.6", "volume": "2000"}],
        },
        fallback_symbol="FPT",
    )

    assert row["ticker"] == "FPT"
    assert row["price"] == 130.5
    assert row["reference_price"] == 129.0
    assert row["volume"] == 1_234_567
    assert row["value"] == 123_456_789_000.0
    assert row["bid_levels"][0] == {"price": 130.4, "volume": 1000.0}


def test_streaming_x_trade_content_maps_latest_trade_snapshot():
    fetcher = _fetcher()

    rows = fetcher.normalize_streaming_realtime_messages(
        [
            {
                "DataType": "X-TRADE",
                "Content": (
                    '{"RType":"X-TRADE","TradingDate":"14/08/2023","Time":"14:07:53",'
                    '"Symbol":"ACB","LastPrice":"22.45","LastVol":"1000","TotalVol":"123456",'
                    '"TotalVal":"2760000000","Change":"0.15","RatioChange":"0.67","Side":"B"}'
                ),
            }
        ],
        ["ACB"],
    )

    assert len(rows) == 1
    assert rows[0]["ticker"] == "ACB"
    assert rows[0]["stream_data_type"] == "X-TRADE"
    assert rows[0]["price"] == 22.45
    assert rows[0]["last_volume"] == 1000.0
    assert rows[0]["volume"] == 123456
    assert rows[0]["value"] == 2760000000.0
    assert rows[0]["has_last_trade"] is True
    assert rows[0]["quote_only"] is False
    assert rows[0]["stream_timestamp"] == "2023-08-14T14:07:53"
    assert "trades" not in rows[0]


def test_streaming_x_content_maps_combined_quote_and_trade():
    fetcher = _fetcher()

    rows = fetcher.normalize_streaming_realtime_messages(
        [
            {
                "DataType": "X",
                "Content": {
                    "RType": "X",
                    "TradingDate": "14/08/2023",
                    "Time": "14:07:53",
                    "Symbol": "ACB",
                    "LastPrice": "22.45",
                    "BidPrice1": "22.4",
                    "BidVol1": "2000",
                    "AskPrice1": "22.5",
                    "AskVol1": "3000",
                },
            }
        ],
        ["ACB"],
    )

    assert len(rows) == 1
    assert rows[0]["stream_data_type"] == "X"
    assert rows[0]["price"] == 22.45
    assert rows[0]["bid_levels"][0] == {"price": 22.4, "volume": 2000.0}
    assert rows[0]["ask_levels"][0] == {"price": 22.5, "volume": 3000.0}
    assert rows[0]["has_last_trade"] is True


def test_streaming_x_quote_maps_quote_context_without_last_trade():
    fetcher = _fetcher()

    rows = fetcher.normalize_streaming_realtime_messages(
        [
            {
                "DataType": "X-QUOTE",
                "Content": (
                    '{"RType":"X-QUOTE","TradingDate":"14/08/2023","Time":"14:07:53",'
                    '"Symbol":"ACB","RefPrice":"22.3","BidPrice1":"22.4","BidVol1":"2000",'
                    '"AskPrice1":"22.5","AskVol1":"3000"}'
                ),
            }
        ],
        ["ACB"],
    )

    assert len(rows) == 1
    assert rows[0]["stream_data_type"] == "X-QUOTE"
    assert rows[0]["price"] is None
    assert rows[0]["realtime_price"] is None
    assert rows[0]["snapshot_price"] is None
    assert rows[0]["reference_price"] == 22.3
    assert rows[0]["bid_levels"][0] == {"price": 22.4, "volume": 2000.0}
    assert rows[0]["ask_levels"][0] == {"price": 22.5, "volume": 3000.0}
    assert rows[0]["has_last_trade"] is False
    assert rows[0]["quote_only"] is True


def test_streaming_parser_ignores_malformed_and_unrequested_messages():
    fetcher = _fetcher()

    rows = fetcher.normalize_streaming_realtime_messages(
        [
            {"DataType": "X-TRADE", "Content": '{"RType":"X-TRADE",'},
            {"DataType": "MI", "Content": {"RType": "MI", "Symbol": "ACB", "LastPrice": "22.45"}},
            {"DataType": "X-TRADE", "Content": {"RType": "X-TRADE", "Symbol": "SSI", "LastPrice": "32"}},
            {"DataType": "X-TRADE", "Content": {"RType": "X-TRADE", "Symbol": "ACB"}},
        ],
        ["ACB"],
    )

    assert rows == []


def test_streaming_quote_after_trade_does_not_clear_last_trade_price():
    fetcher = _fetcher()

    rows = fetcher.normalize_streaming_realtime_messages(
        [
            {
                "DataType": "X-TRADE",
                "Content": {"RType": "X-TRADE", "Symbol": "ACB", "LastPrice": "22.45"},
            },
            {
                "DataType": "X-QUOTE",
                "Content": {"RType": "X-QUOTE", "Symbol": "ACB", "BidPrice1": "22.4", "AskPrice1": "22.5"},
            },
        ],
        ["ACB"],
    )

    assert len(rows) == 1
    assert rows[0]["price"] == 22.45
    assert rows[0]["has_last_trade"] is True
    assert rows[0]["bid_levels"][0]["price"] == 22.4


def test_realtime_snapshot_returns_streaming_disabled_state_without_http_calls():
    session = _FakeSession(post_items=[_token_response()])
    fetcher = _fetcher(session=session)

    payload = fetcher.get_realtime_snapshot(["FPT", "VPB"])

    assert payload["status"] == "unavailable"
    assert payload["source"] == "SSI"
    assert payload["reason"] == SSI_STREAMING_REALTIME_DISABLED_REASON
    assert payload["requested_tickers"] == ["FPT", "VPB"]
    assert payload["quotes"] == []
    assert payload["count"] == 0
    assert payload["attempted_endpoints"] == []
    assert payload["candidate_endpoints"] == []
    assert payload["rest_candidate_endpoints"] == list(SSI_REALTIME_ENDPOINT_CANDIDATES)
    assert payload["endpoint_attempts"] == []
    assert payload["discovery_status"] == "streaming_manager_disabled"
    assert payload["rest_status"] == "unsupported"
    assert payload["streaming_status"] == "disabled"
    assert payload["streaming_data_types"] == list(SSI_REALTIME_STREAMING_DATA_TYPES)
    assert payload["parsed_streaming_rows"] == 0
    assert payload["cache_status"] == "disabled"
    assert payload["manager_state"] == "disabled"
    assert session.calls == []
    assert SECRET_TOKEN not in str(payload)


def test_realtime_snapshot_disabled_does_not_request_token():
    session = _FakeSession()
    fetcher = _fetcher(session=session, realtime_enabled=False)

    payload = fetcher.get_realtime_snapshot(["FPT"])

    assert payload["status"] == "disabled"
    assert payload["source"] == "SSI"
    assert payload["quotes"] == []
    assert session.calls == []


def test_trade_tape_maps_ssi_like_rows():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(
                payload={
                    "data": [
                        {
                            "MatchedTime": "10:00:00",
                            "MatchedPrice": "130.5",
                            "MatchedVolume": "1000",
                            "MatchedValue": "130500000",
                            "Side": "matched",
                            "Sequence": "1",
                        }
                    ]
                }
            )
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_trade_tape("fpt", limit=10)

    assert payload["status"] == "ok"
    assert payload["source"] == "SSI"
    assert payload["symbol"] == "FPT"
    assert payload["trades"][0] == {
        "time": "10:00:00",
        "price": 130.5,
        "volume": 1000.0,
        "value": 130500000.0,
        "side_if_available": "matched",
        "sequence_if_available": "1",
        "source": "SSI",
    }
    assert SECRET_TOKEN not in str(payload)


def test_trade_tape_disabled_does_not_request_token():
    session = _FakeSession()
    fetcher = _fetcher(session=session, trade_tape_enabled=False)

    payload = fetcher.get_trade_tape("FPT")

    assert payload["status"] == "disabled"
    assert payload["source"] == "SSI"
    assert payload["trades"] == []
    assert session.calls == []


def test_trade_tape_failure_returns_actionable_unavailable_without_secrets():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[requests.exceptions.Timeout(f"timeout {SECRET_TOKEN}") for _ in range(6)],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_trade_tape("FPT", limit=10)

    assert payload["status"] == "unavailable"
    assert payload["source"] == "SSI"
    assert payload["symbol"] == "FPT"
    assert "trade tape unavailable" in payload["reason"]
    assert "TradeTape" in payload["reason"]
    assert payload["attempted_endpoints"] == ["TradeTape", "MatchedTrades", "SecuritiesTrades"]
    assert SECRET_TOKEN not in str(payload)


def test_empty_rows_retry_alternate_param_casing():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(payload={"data": []}),
            _FakeResponse(payload={"data": [{"TradingDate": "2026-06-17", "Close": "124.6"}]}),
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_daily_ohlcv("FPT", from_date="01/01/2026", to_date="17/06/2026", limit=1000)

    assert payload["count"] == 1
    _, _, retry_kwargs = session.calls[-1]
    assert retry_kwargs["params"]["Symbol"] == "FPT"
    assert retry_kwargs["params"]["Fromdate"] == "01/01/2026"
    assert retry_kwargs["params"]["Todate"] == "17/06/2026"


def test_daily_stock_price_retries_hose_market_aliases_without_provider_fallback():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(payload={"data": []}),
            _FakeResponse(payload={"data": []}),
            _FakeResponse(payload={"data": [{"TradingDate": "2026-06-17", "Close": "124.6"}]}),
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_daily_stock_price("FPT", market="HOSE", from_date="01/01/2026", to_date="29/01/2026", limit=1000)

    assert payload["count"] == 1
    assert [call[1].rsplit("/", 1)[-1] for call in session.calls if call[0] == "GET"] == [
        "DailyStockPrice",
        "DailyStockPrice",
        "DailyStockPrice",
    ]
    _, _, retry_kwargs = session.calls[-1]
    assert retry_kwargs["params"]["market"] == "HSX"


def test_status_like_daily_stock_price_payload_does_not_count_as_data_row():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(payload={"status": "Success", "message": "No data"}),
            _FakeResponse(payload={"status": "Success", "message": "No data"}),
            _FakeResponse(payload={"status": "Success", "message": "No data"}),
            _FakeResponse(payload={"status": "Success", "message": "No data"}),
            _FakeResponse(payload={"status": "Success", "message": "No data"}),
            _FakeResponse(payload={"status": "Success", "message": "No data"}),
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_daily_stock_price("FPT", market="HOSE", from_date="01/01/2026", to_date="29/01/2026", limit=1000)

    assert payload["status"] == "ok"
    assert payload["count"] == 0
    assert payload["rows"] == []


def test_daily_stock_price_chunking_merges_sorts_and_deduplicates_rows():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(payload={"Data": [{"TradingDate": "2026-01-02", "ClosePrice": "10"}]}),
            _FakeResponse(payload={"Data": [{"TradingDate": "2026-02-01", "ClosePrice": "20"}]}),
            _FakeResponse(payload={"Data": [{"TradingDate": "2026-01-02", "ClosePrice": "11"}]}),
            _FakeResponse(payload={"Data": [{"TradingDate": "2026-03-31", "ClosePrice": "30"}]}),
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_daily_stock_price("FPT", market="HOSE", from_date="2026-01-01", to_date="2026-03-31", limit=1000)

    assert payload["status"] == "ok"
    assert payload["chunks_used"] == 4
    assert payload["count"] == 3
    assert [row["date"] for row in payload["rows"]] == ["2026-01-02", "2026-02-01", "2026-03-31"]
    assert payload["rows"][0]["close"] == 11.0
    get_calls = [call for call in session.calls if call[0] == "GET"]
    assert len(get_calls) == 4
    assert get_calls[0][2]["params"]["Fromdate"] == "01/01/2026"
    assert get_calls[0][2]["params"]["Todate"] == "29/01/2026"
    assert get_calls[-1][2]["params"]["Fromdate"] == "29/03/2026"
    assert get_calls[-1][2]["params"]["Todate"] == "31/03/2026"


def test_daily_stock_price_chunking_filters_status_message_only_chunks():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(payload={"status": "Success", "message": "No data"}),
            _FakeResponse(payload={"Data": [{"TradingDate": "2026-02-01", "ClosePrice": "20"}]}),
            _FakeResponse(payload={"status": "Success", "message": "No data"}),
            _FakeResponse(payload={"status": "Success", "message": "No data"}),
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_daily_stock_price("FPT", market="HOSE", from_date="2026-01-01", to_date="2026-03-31", limit=1000)

    assert payload["status"] == "ok"
    assert payload["count"] == 1
    assert payload["rows"][0]["date"] == "2026-02-01"


def test_status_like_daily_index_payload_does_not_count_as_data_row():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(payload={"status": "Success", "message": "No data"}),
            _FakeResponse(payload={"status": "Success", "message": "No data"}),
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_daily_index("VN30", from_date="01/01/2026", to_date="29/01/2026", limit=1000)

    assert payload["status"] == "ok"
    assert payload["count"] == 0
    assert payload["rows"] == []


def test_daily_index_chunking_merges_sorts_and_deduplicates_rows():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(payload={"Data": [{"TradingDate": "2026-01-02", "IndexId": "VN30", "IndexValue": "100"}]}),
            _FakeResponse(payload={"Data": [{"TradingDate": "2026-02-01", "IndexId": "VN30", "IndexValue": "200"}]}),
            _FakeResponse(payload={"Data": [{"TradingDate": "2026-01-02", "IndexId": "VN30", "IndexValue": "110"}]}),
            _FakeResponse(payload={"Data": [{"TradingDate": "2026-03-31", "IndexId": "VN30", "IndexValue": "300"}]}),
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_daily_index("VN30", from_date="2026-01-01", to_date="2026-03-31", limit=1000)

    assert payload["status"] == "ok"
    assert payload["chunks_used"] == 4
    assert payload["count"] == 3
    assert [row["date"] for row in payload["rows"]] == ["2026-01-02", "2026-02-01", "2026-03-31"]
    assert payload["rows"][0]["index_value"] == 110.0
    get_calls = [call for call in session.calls if call[0] == "GET"]
    assert len(get_calls) == 4
    assert get_calls[0][2]["params"]["indexID"] == "VN30"
    assert get_calls[0][2]["params"]["Fromdate"] == "01/01/2026"
    assert get_calls[0][2]["params"]["Todate"] == "29/01/2026"


def test_daily_index_chunking_filters_status_message_only_chunks():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(payload={"status": "Success", "message": "No data"}),
            _FakeResponse(payload={"Data": [{"TradingDate": "2026-02-01", "IndexId": "VN30", "IndexValue": "200"}]}),
            _FakeResponse(payload={"status": "Success", "message": "No data"}),
            _FakeResponse(payload={"status": "Success", "message": "No data"}),
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_daily_index("VN30", from_date="2026-01-01", to_date="2026-03-31", limit=1000)

    assert payload["status"] == "ok"
    assert payload["count"] == 1
    assert payload["rows"][0]["date"] == "2026-02-01"


def test_chunked_pagination_fetches_until_total_record_is_satisfied():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(
                payload={
                    "totalRecord": 3,
                    "Data": [
                        {"TradingDate": "2026-01-02", "ClosePrice": "10"},
                        {"TradingDate": "2026-01-03", "ClosePrice": "11"},
                    ],
                }
            ),
            _FakeResponse(
                payload={
                    "totalRecord": 3,
                    "Data": [{"TradingDate": "2026-01-04", "ClosePrice": "12"}],
                }
            ),
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_daily_stock_price("FPT", market="HOSE", from_date="2026-01-01", to_date="2026-01-29", limit=1000)

    assert payload["count"] == 3
    assert payload["pages_used"] == 2
    get_calls = [call for call in session.calls if call[0] == "GET"]
    assert [call[2]["params"]["pageIndex"] for call in get_calls] == [1, 2]


def test_daily_ohlc_response_maps_to_normalized_rows():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(
                payload={
                    "data": [
                        {
                            "TradingDate": "2026-06-18T00:00:00",
                            "OpenPrice": "125.0",
                            "HighestPrice": "126.0",
                            "LowestPrice": "124.0",
                            "ClosePrice": "125.5",
                            "TotalVolume": "2000",
                            "TotalValue": "251000",
                        },
                        {
                            "TradingDate": "2026-06-17",
                            "Open": "123.4",
                            "High": "125.0",
                            "Low": "122.8",
                            "Close": "124.6",
                            "Volume": "1234567",
                            "Value": "123456789000",
                        },
                    ]
                }
            )
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_daily_ohlcv("FPT")

    assert payload["status"] == "ok"
    assert payload["source"] == "SSI"
    assert payload["symbol"] == "FPT"
    assert payload["rows"] == [
        {
            "date": "2026-06-17",
            "open": 123.4,
            "high": 125.0,
            "low": 122.8,
            "close": 124.6,
            "volume": 1234567,
            "value": 123456789000.0,
            "source": "SSI",
        },
        {
            "date": "2026-06-18",
            "open": 125.0,
            "high": 126.0,
            "low": 124.0,
            "close": 125.5,
            "volume": 2000,
            "value": 251000.0,
            "source": "SSI",
        },
    ]


def test_daily_stock_price_maps_reference_limits_matched_and_foreign_fields():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(
                payload={
                    "Data": [
                        {
                            "TradingDate": "20260617",
                            "RefPrice": "123.0",
                            "Ceiling": "131.6",
                            "Floor": "114.4",
                            "OpenPrice": "123.4",
                            "Highest": "125.0",
                            "Lowest": "122.8",
                            "ClosePrice": "124.6",
                            "AdjustedClose": "124.6",
                            "MatchedVolume": "1234567",
                            "MatchedValue": "123456789000",
                            "PutThroughVolume": "0",
                            "PutThroughValue": "0",
                            "TotalVolume": "1234567",
                            "TotalValue": "123456789000",
                            "ForeignBuyVol": "100000",
                            "ForeignSellVol": "80000",
                            "ForeignBuyValue": "1000000000",
                            "ForeignSellValue": "800000000",
                        }
                    ]
                }
            )
        ],
    )
    fetcher = _fetcher(session=session)

    row = fetcher.get_daily_stock_price("FPT", from_date="2026-06-17", to_date="2026-06-17")["rows"][0]

    assert row["date"] == "2026-06-17"
    assert row["reference_price"] == 123.0
    assert row["ceiling_price"] == 131.6
    assert row["floor_price"] == 114.4
    assert row["open"] == 123.4
    assert row["high"] == 125.0
    assert row["low"] == 122.8
    assert row["close"] == 124.6
    assert row["adjusted_close"] == 124.6
    assert row["matched_volume"] == 1234567
    assert row["matched_value"] == 123456789000.0
    assert row["put_through_volume"] == 0
    assert row["put_through_value"] == 0.0
    assert row["total_volume"] == 1234567
    assert row["total_value"] == 123456789000.0
    assert row["foreign_buy_volume"] == 100000
    assert row["foreign_sell_volume"] == 80000
    assert row["foreign_net_volume"] == 20000
    assert row["foreign_buy_value"] == 1000000000.0
    assert row["foreign_sell_value"] == 800000000.0
    assert row["foreign_net_value"] == 200000000.0
    assert row["source"] == "SSI"


def test_daily_stock_price_accepts_documented_sample_like_row():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(
                payload={
                    "Data": [
                        {
                            "TradingDate": "19/07/2023",
                            "RefPrice": "24500",
                            "CeilingPrice": "26200",
                            "FloorPrice": "22800",
                            "OpenPrice": "24600",
                            "ClosePrice": "24700",
                            "TotalVol": "100",
                            "TotalVal": "2470000",
                        }
                    ]
                }
            )
        ],
    )
    fetcher = _fetcher(session=session)

    row = fetcher.get_daily_stock_price("SSI", market="HOSE", from_date="2023-07-19", to_date="2023-07-19")["rows"][0]

    assert row["date"] == "2023-07-19"
    assert row["reference_price"] == 24500.0
    assert row["ceiling_price"] == 26200.0
    assert row["floor_price"] == 22800.0
    assert row["open"] == 24600.0
    assert row["close"] == 24700.0
    assert row["total_volume"] == 100
    assert row["total_value"] == 2470000.0


def test_daily_index_maps_liquidity_and_breadth_fields():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(
                payload={
                    "items": [
                        {
                            "date": "2026/06/17",
                            "IndexCode": "VNINDEX",
                            "IndexValue": "1315.22",
                            "Change": "5.21",
                            "ChangePct": "0.4",
                            "TotalVolume": "123456789",
                            "TotalValue": "12345678900000",
                            "MatchedVolume": "120000000",
                            "MatchedValue": "12000000000000",
                            "PutThroughVolume": "3456789",
                            "PutThroughValue": "345678900000",
                            "Advances": "210",
                            "Unchanged": "70",
                            "Declines": "180",
                            "Ceiling": "12",
                            "Floor": "8",
                            "TradingSession": "ATC",
                            "Exchange": "HOSE",
                        }
                    ]
                }
            )
        ],
    )
    fetcher = _fetcher(session=session)

    row = fetcher.get_daily_index("VNINDEX", from_date="2026-06-17", to_date="2026-06-17")["rows"][0]

    assert row == {
        "date": "2026-06-17",
        "index_code": "VNINDEX",
        "index_value": 1315.22,
        "change": 5.21,
        "change_pct": 0.4,
        "total_volume": 123456789,
        "total_value": 12345678900000.0,
        "matched_volume": 120000000,
        "matched_value": 12000000000000.0,
        "put_through_volume": 3456789,
        "put_through_value": 345678900000.0,
        "advances": 210,
        "unchanged": 70,
        "declines": 180,
        "ceiling": 12,
        "floor": 8,
        "trading_session": "ATC",
        "exchange": "HOSE",
        "source": "SSI",
    }


def test_daily_index_accepts_documented_sample_like_row():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(
                payload={
                    "Data": [
                        {
                            "IndexId": "HNX30",
                            "TradingDate": "14/08/2023",
                            "IndexValue": "423.45",
                            "RatioChange": "0.56",
                            "TotalMatchVol": "123456",
                            "Advances": "12",
                            "Declines": "8",
                        }
                    ]
                }
            )
        ],
    )
    fetcher = _fetcher(session=session)

    row = fetcher.get_daily_index("HNX30", from_date="2023-08-14", to_date="2023-08-14")["rows"][0]

    assert row["date"] == "2023-08-14"
    assert row["index_code"] == "HNX30"
    assert row["index_value"] == 423.45
    assert row["change_pct"] == 0.56
    assert row["total_volume"] == 123456
    assert row["matched_volume"] == 123456
    assert row["advances"] == 12
    assert row["declines"] == 8


def test_index_list_maps_index_codes_safely():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(
                payload={
                    "Data": [
                        {"IndexID": "VNINDEX", "IndexCode": "VNINDEX", "IndexName": "VN Index", "Market": "HOSE"},
                        {"IndexId": "VN30", "Name": "VN30 Index", "Exchange": "HOSE"},
                    ]
                }
            )
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_index_list("HOSE")

    assert payload["status"] == "ok"
    assert payload["market"] == "HOSE"
    assert payload["rows"] == [
        {
            "index_id": "VNINDEX",
            "index_code": "VNINDEX",
            "index_name": "VN Index",
            "exchange": "HOSE",
            "market": "HOSE",
            "source": "SSI",
        },
        {
            "index_id": "VN30",
            "index_code": "VN30",
            "index_name": "VN30 Index",
            "exchange": "HOSE",
            "market": "HOSE",
            "source": "SSI",
        },
    ]
    _, _, kwargs = session.calls[-1]
    assert kwargs["params"] == {"market": "HOSE"}


def test_index_components_maps_component_rows_safely():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(
                payload={
                    "Data": [
                        {
                            "IndexID": "VN30",
                            "Symbol": "FPT",
                            "Market": "HOSE",
                            "Weight": "7.25",
                            "Name": "FPT Corp",
                        },
                        {
                            "IndexCode": "VN30",
                            "StockSymbol": "ACB",
                            "Exchange": "HOSE",
                            "Ratio": "4.10",
                            "StockName": "ACB",
                        },
                    ]
                }
            )
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_index_components("vn30")

    assert payload["status"] == "ok"
    assert payload["source"] == "SSI"
    assert payload["index_code"] == "VN30"
    assert payload["rows"] == [
        {
            "index_code": "VN30",
            "symbol": "FPT",
            "exchange": "HOSE",
            "market": "HOSE",
            "weight": 7.25,
            "name": "FPT Corp",
            "source": "SSI",
        },
        {
            "index_code": "VN30",
            "symbol": "ACB",
            "exchange": "HOSE",
            "market": "HOSE",
            "weight": 4.10,
            "name": "ACB",
            "source": "SSI",
        },
    ]
    _, _, kwargs = session.calls[-1]
    assert kwargs["params"] == {"indexID": "VN30", "pageIndex": 1, "pageSize": 1000}


def test_index_components_retries_index_code_variant_when_first_shape_has_no_rows():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(payload={"status": "ok", "message": "No data"}),
            _FakeResponse(payload={"Data": [{"IndexCode": "VN30", "Symbol": "FPT"}]}),
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_index_components("VN30")

    assert payload["status"] == "ok"
    assert payload["rows"][0]["symbol"] == "FPT"
    assert session.calls[1][2]["params"] == {"indexID": "VN30", "pageIndex": 1, "pageSize": 1000}
    assert session.calls[2][2]["params"] == {"pageIndex": 1, "pageSize": 1000, "indexCode": "VN30"}


def test_index_components_retries_variant_after_provider_error_shape():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(status_code=400, payload={"message": "bad params"}),
            _FakeResponse(payload={"Data": [{"IndexCode": "VN30", "Symbol": "FPT"}]}),
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_index_components("VN30")

    assert payload["status"] == "ok"
    assert payload["rows"][0]["symbol"] == "FPT"
    assert session.calls[2][2]["params"] == {"pageIndex": 1, "pageSize": 1000, "indexCode": "VN30"}


def test_index_metadata_status_message_only_body_returns_clean_unavailable():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(payload={"status": "ok", "message": "No data"}),
            _FakeResponse(payload={"status": "ok", "message": "No data"}),
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_index_list("HOSE")

    assert payload["status"] == "unavailable"
    assert payload["source"] == "SSI"
    assert payload["reason"] == REQUEST_FAILED_REASON
    assert payload["rows"] == []
    assert payload["count"] == 0


def test_index_components_status_message_only_body_returns_clean_unavailable():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(payload={"status": "ok", "message": "No data"}),
            _FakeResponse(payload={"status": "ok", "message": "No data"}),
            _FakeResponse(payload={"status": "ok", "message": "No data"}),
            _FakeResponse(payload={"status": "ok", "message": "No data"}),
            _FakeResponse(payload={"status": "ok", "message": "No data"}),
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_index_components("VN30")

    assert payload["status"] == "unavailable"
    assert payload["source"] == "SSI"
    assert payload["reason"] == REQUEST_FAILED_REASON
    assert payload["rows"] == []
    assert payload["count"] == 0


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ({"status": "Error", "message": "bad params"}, "Error"),
        ({"Status": "Failed", "Message": "bad params"}, "Failed"),
        ({"code": "E001", "message": "bad params"}, "E001"),
        ({"errorCode": "E002", "message": "bad params"}, "E002"),
    ],
)
def test_parse_response_handles_ssi_error_code_casing_without_name_error(payload, expected_code):
    fetcher = _fetcher(session=_FakeSession())

    parsed = fetcher._parse_response(_FakeResponse(payload=payload), endpoint="IndexComponents")

    assert parsed["status"] == "unavailable"
    assert parsed["source"] == "SSI"
    assert parsed["reason"] == REQUEST_FAILED_REASON
    assert parsed["endpoint"] == "IndexComponents"
    assert parsed["error_type"] == "ssi_error"
    assert parsed["code"] == expected_code
    assert SECRET_TOKEN not in str(parsed)


def test_index_components_provider_error_body_returns_clean_unavailable_without_name_error():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(payload={"errorCode": "E_BAD_PARAMS", "message": "bad params"}),
            _FakeResponse(payload={"errorCode": "E_BAD_PARAMS", "message": "bad params"}),
            _FakeResponse(payload={"errorCode": "E_BAD_PARAMS", "message": "bad params"}),
            _FakeResponse(payload={"errorCode": "E_BAD_PARAMS", "message": "bad params"}),
            _FakeResponse(payload={"errorCode": "E_BAD_PARAMS", "message": "bad params"}),
        ],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_index_components("VN30")

    assert payload["status"] == "unavailable"
    assert payload["source"] == "SSI"
    assert payload["reason"] == REQUEST_FAILED_REASON
    assert payload["endpoint"] == "IndexComponents"
    assert payload["error_type"] == "ssi_error"
    assert payload["code"] == "E_BAD_PARAMS"


def test_securities_maps_symbol_metadata():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(
                payload={
                    "data": [
                        {
                            "Symbol": "FPT",
                            "Market": "HOSE",
                            "SecurityType": "stock",
                            "CompanyName": "FPT Corp",
                            "EnglishName": "FPT Corporation",
                            "Issuer": "FPT",
                            "LotSize": "100",
                            "ListedShares": "123456789",
                            "ListedDate": "2020-01-02",
                        }
                    ]
                }
            )
        ],
    )
    fetcher = _fetcher(session=session)

    row = fetcher.get_securities("HOSE")["rows"][0]

    _, _, kwargs = session.calls[-1]
    assert kwargs["params"] == {"pageIndex": 1, "pageSize": 1000, "market": "HOSE"}
    assert row == {
        "symbol": "FPT",
        "exchange": "HOSE",
        "security_type": "stock",
        "name": "FPT Corp",
        "name_en": "FPT Corporation",
        "issuer": "FPT",
        "lot_size": 100,
        "listed_shares": 123456789,
        "listed_date": "2020-01-02",
        "market": "HOSE",
        "source": "SSI",
    }


def test_securities_details_maps_symbol_metadata():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(
                payload={
                    "data": {
                        "items": [
                            {
                                "securityCode": "FPT",
                                "exchange": "HOSE",
                                "type": "stock",
                                "securityName": "FPT Corp",
                                "issuerName": "FPT",
                                "tradingUnit": "100",
                                "sharesOutstanding": "123456789",
                                "ListingDate": "2020/01/02",
                                "Market": "HOSE",
                            }
                        ]
                    }
                }
            )
        ],
    )
    fetcher = _fetcher(session=session)

    row = fetcher.get_securities_details("FPT")["rows"][0]

    _, _, kwargs = session.calls[-1]
    assert kwargs["params"] == {"pageIndex": 1, "pageSize": 1000, "symbol": "FPT"}
    assert row["symbol"] == "FPT"
    assert row["exchange"] == "HOSE"
    assert row["security_type"] == "stock"
    assert row["name"] == "FPT Corp"
    assert row["name_en"] is None
    assert row["issuer"] == "FPT"
    assert row["lot_size"] == 100
    assert row["listed_shares"] == 123456789
    assert row["listed_date"] == "2020-01-02"
    assert row["market"] == "HOSE"
    assert row["source"] == "SSI"


def test_securities_details_missing_metadata_fields_become_none():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[
            _FakeResponse(
                payload={
                    "data": [
                        {
                            "StockSymbol": "FPT",
                            "Market": "HOSE",
                        }
                    ]
                }
            )
        ],
    )
    fetcher = _fetcher(session=session)

    row = fetcher.get_securities_details("FPT", market="HOSE")["rows"][0]

    assert row["symbol"] == "FPT"
    assert row["exchange"] == "HOSE"
    assert row["market"] == "HOSE"
    assert row["security_type"] is None
    assert row["name"] is None
    assert row["name_en"] is None
    assert row["issuer"] is None
    assert row["lot_size"] is None
    assert row["listed_shares"] is None
    assert row["listed_date"] is None


def test_missing_ssi_fields_become_none():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[_FakeResponse(payload={"data": [{"TradingDate": "2026-06-17", "Symbol": "FPT"}]})],
    )
    fetcher = _fetcher(session=session)

    row = fetcher.get_daily_stock_price("FPT", from_date="2026-06-17", to_date="2026-06-17")["rows"][0]

    assert row["date"] == "2026-06-17"
    assert row["reference_price"] is None
    assert row["matched_value"] is None
    assert row["put_through_value"] is None
    assert row["foreign_net_value"] is None


def test_http_non_200_returns_clean_unavailable_without_secrets():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[_FakeResponse(status_code=500, payload={"error": SECRET_TOKEN})],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_daily_index("VNINDEX", from_date="2026-06-17", to_date="2026-06-17")

    assert payload["status"] == "unavailable"
    assert payload["reason"] == REQUEST_FAILED_REASON
    assert SECRET_TOKEN not in str(payload)


def test_timeout_returns_clean_unavailable_without_secrets():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[requests.exceptions.Timeout(f"timeout {SECRET_TOKEN}")],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_securities()

    assert payload["status"] == "unavailable"
    assert payload["reason"] == REQUEST_FAILED_REASON
    assert SECRET_TOKEN not in str(payload)


def test_invalid_json_returns_clean_unavailable_without_secrets():
    session = _FakeSession(
        post_items=[_token_response()],
        get_items=[_FakeResponse(payload=None, json_error=ValueError(f"bad json {SECRET_TOKEN}"))],
    )
    fetcher = _fetcher(session=session)

    payload = fetcher.get_daily_ohlcv("FPT")

    assert payload["status"] == "unavailable"
    assert payload["reason"] == REQUEST_FAILED_REASON
    assert SECRET_TOKEN not in str(payload)


def test_safe_probe_output_redacts_tokens_and_credentials(capsys):
    from scripts import ssi_fastconnect_smoke as smoke

    redacted = smoke._safe_message(
        {"message": f"failed token {SECRET_TOKEN} for consumerSecret"},
        (SECRET_TOKEN, "test-consumer", "test-secret"),
    )
    smoke._print_probe_result(
        {
            "endpoint": "DailyStockPrice",
            "base_url": "api/v2",
            "param_keys": ["Fromdate", "Todate", "market", "pageIndex", "pageSize", "symbol"],
            "http_status": 200,
            "top_level_keys": ["message", "status"],
            "status_field": "Success",
            "message_field": redacted,
            "totalRecord": None,
            "data_type": "missing",
            "data_length": 0,
            "first_data_row_keys": [],
            "normalized_row_count": 0,
            "normalized_keys": [],
        }
    )

    output = capsys.readouterr().out
    assert SECRET_TOKEN not in output
    assert "test-consumer" not in output
    assert "test-secret" not in output
    assert "consumerSecret" not in output
