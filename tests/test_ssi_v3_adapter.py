"""Deterministic offline contract tests for the SSI-V3-B2 foundation."""

from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from importlib import metadata
import importlib
import inspect
import os
from pathlib import Path
from types import SimpleNamespace
import threading
import time
from typing import Any, Dict, List, Optional
from unittest.mock import patch
from zoneinfo import ZoneInfo

import httpx
import pytest

from data_provider.ssi_provider_router import (
    SsiRestProviderRouter,
    close_shared_ssi_v3_adapter,
    create_ssi_rest_provider_router,
)
from data_provider.ssi_v2_adapter import SsiFastConnectV2Adapter
from data_provider.ssi_v3_adapter import (
    SSI_V3_MAX_ROWS,
    SSI_V3_SOURCE,
    SsiFastConnectV3Adapter,
    SsiV3RestSettings,
)
from src.config import Config, parse_ssi_fastconnect_rest_version
from src.services.vietnam_market_service import (
    VietnamDashboardConfig,
    VietnamMarketService,
    _intraday_chart_cache_key,
    normalize_completed_intraday_chart_rows,
)


ROOT = Path(__file__).resolve().parents[1]


def complete_settings(**overrides: Any) -> SsiV3RestSettings:
    values = {
        "enabled": True,
        "client_id": "<client-id>",
        "api_key": "<api-key>",
        "api_secret": "<api-secret>",
    }
    values.update(overrides)
    return SsiV3RestSettings(**values)


class FakeRestClient:
    def __init__(self) -> None:
        self.calls: List[Any] = []
        self.payload: Any = []
        self.error: Optional[BaseException] = None

    def get(self, path: str, **kwargs: Any) -> Any:
        self.calls.append((path, kwargs))
        if self.error is not None:
            raise self.error
        return self.payload


class FakeAuth:
    def __init__(self, events: Optional[List[str]] = None) -> None:
        self.events = events if events is not None else []
        self.authenticate_calls = 0
        self.close_calls = 0
        self.authenticate_error: Optional[BaseException] = None
        self.rest_client = FakeRestClient()

    def authenticate(self) -> object:
        self.authenticate_calls += 1
        self.events.append("authenticate")
        if self.authenticate_error is not None:
            raise self.authenticate_error
        return object()

    def close(self) -> None:
        self.close_calls += 1
        self.events.append("auth.close")


class FakeMarketData:
    def __init__(self) -> None:
        self.calls: List[Any] = []
        self.securities: Any = []
        self.indexes: Any = []
        self.ohlc_pages: Dict[int, Any] = {}
        self.error: Optional[BaseException] = None

    def _raise(self) -> None:
        if self.error is not None:
            raise self.error

    def get_securities_info_by_board(self, board: Any) -> Any:
        self.calls.append(("securities_board", getattr(board, "value", board)))
        self._raise()
        return self.securities

    def get_securities_info(self, symbol: str) -> Any:
        self.calls.append(("security_symbol", symbol))
        self._raise()
        if isinstance(self.securities, list):
            return self.securities[0] if self.securities else None
        return self.securities

    def get_securities_info_by_index(self, index: str) -> Any:
        self.calls.append(("securities_index", index))
        self._raise()
        return self.securities

    def get_indexes(self) -> Any:
        self.calls.append(("indexes", None))
        self._raise()
        return self.indexes

    def get_indexes_by_board(self, board: Any) -> Any:
        self.calls.append(("indexes_board", getattr(board, "value", board)))
        self._raise()
        return self.indexes

    def _ohlc(self, name: str, symbol: str, start: str, end: str, page: int, size: int) -> Any:
        self.calls.append((name, symbol, start, end, page, size))
        self._raise()
        return self.ohlc_pages.get(page, [])

    def get_ohlc_1day_historical(
        self, symbol: str, start: str, end: str, *, page: int, size: int
    ) -> Any:
        return self._ohlc("daily", symbol, start, end, page, size)

    def get_ohlc_1minute_historical(
        self, symbol: str, start: str, end: str, *, page: int, size: int
    ) -> Any:
        return self._ohlc("1m", symbol, start, end, page, size)


class FakeData:
    def __init__(self, market_data: FakeMarketData, events: Optional[List[str]] = None) -> None:
        self.market_data = market_data
        self.events = events if events is not None else []
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1
        self.events.append("data.close")


def make_adapter(
    *,
    auth: Optional[FakeAuth] = None,
    market: Optional[FakeMarketData] = None,
    settings: Optional[SsiV3RestSettings] = None,
    events: Optional[List[str]] = None,
) -> tuple[SsiFastConnectV3Adapter, FakeAuth, FakeMarketData, FakeData]:
    shared_events = events if events is not None else []
    fake_auth = auth or FakeAuth(shared_events)
    fake_market = market or FakeMarketData()
    fake_data = FakeData(fake_market, shared_events)
    adapter = SsiFastConnectV3Adapter(
        settings or complete_settings(),
        auth_factory=lambda _settings: fake_auth,
        data_factory=lambda _auth: fake_data,
    )
    return adapter, fake_auth, fake_market, fake_data


def security(**overrides: Any) -> SimpleNamespace:
    values = {
        "symbol": "FPT",
        "board": SimpleNamespace(value="HOSE"),
        "symbol_name_vi": "Cong ty FPT",
        "symbol_name_en": "FPT Corporation",
        "lot_size": 100,
        "listed_shares": 0,
        "first_trading_date": "2006/12/13",
        "icb_name": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def candle(**overrides: Any) -> SimpleNamespace:
    values = {
        "symbol": "FPT",
        "trading_date": "2026/07/21",
        "open_price": "100.5",
        "high_price": "101.5",
        "low_price": "99.5",
        "close_price": "100.0",
        "volume": "0",
        "value": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_pinned_sdk_dependency_namespace_python_and_docker_contract() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    dockerfile = (ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
    package = metadata.metadata("ssi-sdk")

    assert "ssi-sdk==3.0.5" in requirements
    assert "ssi-fc-data" in requirements and "v2.2.2" in requirements
    assert metadata.version("ssi-sdk") == "3.0.5"
    assert package["Requires-Python"] == ">=3.10"
    assert "SSI-Securities-Inc" in " ".join(package.get_all("Project-URL") or [])
    assert "COPY requirements.txt" in dockerfile
    assert "pip install --no-cache-dir -r requirements.txt" in dockerfile


def test_pinned_sdk_symbols_and_required_signatures() -> None:
    from ssi_sdk import Auth, Config as SdkConfig, Data
    from ssi_sdk.services.market_data import MarketDataService
    from ssi_sdk.services.token_manager import TokenManager

    assert str(inspect.signature(SdkConfig)).startswith("(client_id: 'str' = ''")
    assert str(inspect.signature(Auth)) == "(config: 'Config | None' = None, **kwargs: 'object') -> 'None'"
    assert str(inspect.signature(TokenManager.authenticate)) == "(self, otp: 'str | None' = None) -> 'Token'"
    assert str(inspect.signature(Data)) == "(auth: 'Auth') -> 'None'"
    assert not hasattr(Data, "close")
    assert str(inspect.signature(MarketDataService.get_ohlc_1day_historical)).endswith(
        "page: 'int' = 1, size: 'int' = 1000) -> 'list[OHLCData]'"
    )
    assert str(inspect.signature(MarketDataService.get_securities_info_by_board)) == (
        "(self, board: 'Board') -> 'list[SecuritiesInfo]'"
    )


def test_v3_defaults_disabled_and_secrets_are_repr_safe() -> None:
    settings = SsiV3RestSettings(
        client_id="<client-id>", api_key="<api-key>", api_secret="<api-secret>"
    )
    rendered = repr(settings)
    assert settings.enabled is False
    assert "<client-id>" not in rendered
    assert "<api-key>" not in rendered
    assert "<api-secret>" not in rendered
    assert SsiV3RestSettings().api_url == "https://api.ssi.com.vn/api/v3"


@patch("src.config.setup_env")
@patch.object(Config, "_parse_litellm_yaml", return_value=[])
def test_v3_environment_configuration_is_parsed_without_exposing_secrets(
    _mock_parse_yaml: Any,
    _mock_setup_env: Any,
) -> None:
    env = {
        "SSI_FASTCONNECT_REST_VERSION": "v3",
        "SSI_V3_REST_ENABLED": "true",
        "SSI_V3_CLIENT_ID": "<client-id>",
        "SSI_V3_API_KEY": "<api-key>",
        "SSI_V3_API_SECRET": "<api-secret>",
        "SSI_V3_API_URL": "https://api.ssi.com.vn/api/v3/",
        "SSI_V3_REQUEST_TIMEOUT": "12",
        "SSI_V3_MAX_RETRIES": "1",
        "SSI_V3_RETRY_DELAY": "0.5",
        "SSI_V3_RATE_LIMIT_PER_SECOND": "4",
    }
    with patch.dict(os.environ, env, clear=True):
        config = Config._load_from_env()

    assert config.ssi_fastconnect_rest_version == "v3"
    assert config.ssi_v3_rest_enabled is True
    assert config.ssi_v3_api_url == "https://api.ssi.com.vn/api/v3"
    assert config.ssi_v3_request_timeout == 12
    assert config.ssi_v3_max_retries == 1
    assert config.ssi_v3_retry_delay == 0.5
    assert config.ssi_v3_rate_limit_per_second == 4
    rendered = repr(config)
    assert "<client-id>" not in rendered
    assert "<api-key>" not in rendered
    assert "<api-secret>" not in rendered


def test_v3_selected_while_disabled_or_incomplete_fails_with_names_only() -> None:
    disabled = Config(ssi_fastconnect_rest_version="v3", ssi_v3_rest_enabled=False)
    with pytest.raises(ValueError, match="SSI_V3_REST_ENABLED=true"):
        create_ssi_rest_provider_router(config=disabled, v2_fetcher=object())

    incomplete = Config(
        ssi_fastconnect_rest_version="v3",
        ssi_v3_rest_enabled=True,
        ssi_v3_client_id=None,
        ssi_v3_api_key="<api-key>",
        ssi_v3_api_secret=None,
    )
    with pytest.raises(ValueError) as exc_info:
        create_ssi_rest_provider_router(config=incomplete, v2_fetcher=object())
    message = str(exc_info.value)
    assert "SSI_V3_CLIENT_ID" in message and "SSI_V3_API_SECRET" in message
    assert "<api-key>" not in message


def test_v2_selection_never_requires_v3_configuration() -> None:
    router = create_ssi_rest_provider_router(version="v2", v2_fetcher=MinimalV2Fetcher())
    assert router.selected_version == "v2"
    assert parse_ssi_fastconnect_rest_version(None) == "v2"
    with pytest.raises(ValueError, match="unsupported"):
        parse_ssi_fastconnect_rest_version("future")


def test_config_validation_lists_v3_names_without_values() -> None:
    config = Config(
        ssi_fastconnect_rest_version="v3",
        ssi_v3_rest_enabled=True,
        ssi_v3_client_id="<client-id>",
        ssi_v3_api_key=None,
        ssi_v3_api_secret=None,
    )
    messages = [issue.message for issue in config.validate_structured()]
    match = next(message for message in messages if "SSI FastConnect V3 REST configuration" in message)
    assert "SSI_V3_API_KEY" in match and "SSI_V3_API_SECRET" in match
    assert "<client-id>" not in match


def test_v3_env_names_are_intentionally_hidden_from_web_registry() -> None:
    from src.core.config_registry import WEB_SETTINGS_HIDDEN_FROM_UI

    expected = {
        "SSI_V3_REST_ENABLED",
        "SSI_V3_CLIENT_ID",
        "SSI_V3_API_KEY",
        "SSI_V3_API_SECRET",
        "SSI_V3_API_URL",
        "SSI_V3_REQUEST_TIMEOUT",
        "SSI_V3_MAX_RETRIES",
        "SSI_V3_RETRY_DELAY",
        "SSI_V3_RATE_LIMIT_PER_SECOND",
    }
    assert expected <= WEB_SETTINGS_HIDDEN_FROM_UI


def test_market_service_passes_dedicated_v3_settings_to_router() -> None:
    config = VietnamDashboardConfig(
        ssi_fastconnect_rest_version="v3",
        ssi_v3_rest_enabled=True,
        ssi_v3_client_id="<client-id>",
        ssi_v3_api_key="<api-key>",
        ssi_v3_api_secret="<api-secret>",
    )
    service = VietnamMarketService(
        config=config,
        ssi_fetcher=MinimalV2Fetcher(),  # type: ignore[arg-type]
    )
    try:
        router = service._get_ssi_rest_provider()
        assert isinstance(router, SsiRestProviderRouter)
        assert isinstance(router.v3_provider, SsiFastConnectV3Adapter)
        assert router.v3_provider.initialized is False
        assert router.v3_provider.settings.client_id == "<client-id>"
    finally:
        close_shared_ssi_v3_adapter()


def test_adapter_constructor_is_lazy_and_first_call_authenticates_once() -> None:
    adapter, auth, market, _data = make_adapter()
    market.indexes = []
    assert adapter.initialized is False
    assert auth.authenticate_calls == 0

    assert adapter.get_index_list()["status"] == "ok"
    assert adapter.get_index_list()["status"] == "ok"
    assert adapter.initialized is True
    assert auth.authenticate_calls == 1


def test_concurrent_first_calls_create_one_auth_data_lifecycle() -> None:
    auth = FakeAuth()
    market = FakeMarketData()
    market.indexes = []
    factory_calls = 0

    def auth_factory(_settings: SsiV3RestSettings) -> FakeAuth:
        nonlocal factory_calls
        factory_calls += 1
        time.sleep(0.02)
        return auth

    data = FakeData(market)
    adapter = SsiFastConnectV3Adapter(
        complete_settings(), auth_factory=auth_factory, data_factory=lambda _auth: data
    )
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: adapter.get_index_list(), range(12)))

    assert all(result["status"] == "ok" for result in results)
    assert factory_calls == 1
    assert auth.authenticate_calls == 1


def test_failed_initialization_leaves_no_partial_client_and_can_retry() -> None:
    attempts: List[FakeAuth] = []
    market = FakeMarketData()
    market.indexes = []

    def auth_factory(_settings: SsiV3RestSettings) -> FakeAuth:
        auth = FakeAuth()
        if not attempts:
            auth.authenticate_error = httpx.ReadTimeout("offline-timeout")
        attempts.append(auth)
        return auth

    adapter = SsiFastConnectV3Adapter(
        complete_settings(),
        auth_factory=auth_factory,
        data_factory=lambda _auth: FakeData(market),
    )
    first = adapter.get_index_list()
    second = adapter.get_index_list()

    assert first["failure_class"] == "request_timeout"
    assert attempts[0].close_calls == 1
    assert second["status"] == "ok"
    assert len(attempts) == 2


def test_close_is_idempotent_and_releases_data_before_auth() -> None:
    events: List[str] = []
    adapter, auth, market, data = make_adapter(events=events)
    market.indexes = []
    adapter.get_index_list()
    events.clear()

    adapter.close()
    adapter.close()

    assert events == ["data.close", "auth.close"]
    assert data.close_calls == 1
    assert auth.close_calls == 1


def test_import_is_network_and_thread_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    import data_provider.ssi_v3_adapter as module

    monkeypatch.setattr(
        httpx.Client,
        "request",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network on import")),
    )
    monkeypatch.setattr(
        threading.Thread,
        "start",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("thread on import")),
    )
    importlib.reload(module)


def test_securities_filters_validate_and_construct_exact_sdk_calls() -> None:
    adapter, auth, market, _data = make_adapter()
    market.securities = [security()]

    assert adapter.get_securities(None)["failure_class"] == "validation_error"
    assert adapter.get_securities_filtered(symbol="FPT", board="HOSE")["failure_class"] == "validation_error"
    assert adapter.get_securities("INVALID")["failure_class"] == "validation_error"
    assert auth.authenticate_calls == 0
    assert adapter.get_securities("hose")["rows"][0]["symbol"] == "FPT"
    assert adapter.get_security_basic_info("fpt")["rows"][0]["symbol"] == "FPT"
    assert adapter.get_securities_by_index("vn30")["rows"][0]["symbol"] == "FPT"
    assert ("securities_board", "HOSE") in market.calls
    assert ("security_symbol", "FPT") in market.calls
    assert ("securities_index", "VN30") in market.calls


def test_security_normalization_preserves_missing_zero_and_no_type_heuristic() -> None:
    adapter, _auth, market, _data = make_adapter()
    market.securities = [
        security(lot_size=None, listed_shares=0, first_trading_date=None, icb_name=None)
    ]
    row = adapter.get_securities("HOSE")["rows"][0]

    assert row["lot_size"] is None
    assert row["listed_shares"] == 0
    assert row["listed_date"] is None
    assert row["security_type"] is None
    assert row["source"] == SSI_V3_SOURCE


def test_daily_ohlc_request_dates_pagination_and_normalization() -> None:
    adapter, _auth, market, _data = make_adapter()
    market.ohlc_pages = {1: [candle()], 2: []}
    result = adapter.get_daily_ohlcv(
        "fpt", from_date="2026-07-01", to_date="2026-07-21", limit=2
    )
    row = result["rows"][0]

    assert market.calls[0] == ("daily", "FPT", "2026/07/01", "2026/07/21", 1, 2)
    assert result["pages_used"] == 1
    assert row == {
        "date": "2026-07-21",
        "open": 100.5,
        "high": 101.5,
        "low": 99.5,
        "close": 100.0,
        "volume": 0,
        "value": None,
        "source": SSI_V3_SOURCE,
    }


def test_completed_intraday_uses_datetime_bounds_and_normalized_contract() -> None:
    adapter, _auth, market, _data = make_adapter()
    market.ohlc_pages = {1: [candle(trading_date="2026/07/21 09:15:42")]}
    result = adapter.get_completed_intraday_1m("fpt", "2026-07-21")
    row = result["rows"][0]

    assert market.calls[0] == (
        "1m",
        "FPT",
        "2026/07/21 00:00:00",
        "2026/07/21 23:59:59",
        1,
        1000,
    )
    assert row["date_time"] == "2026-07-21T09:15:42+07:00"
    assert isinstance(row["timestamp"], int)
    assert row["ticker"] == "FPT"


def test_ohlc_empty_repeated_page_bounds_and_ordering(monkeypatch: pytest.MonkeyPatch) -> None:
    import data_provider.ssi_v3_adapter as module

    adapter, _auth, market, _data = make_adapter()
    assert adapter.get_daily_ohlcv("FPT", "2026-07-01", "2026-07-21", 2)["rows"] == []

    repeated = [candle(trading_date="2026/07/21")] * 1000
    market.ohlc_pages = {1: repeated, 2: repeated}
    result = adapter.get_daily_ohlcv("FPT", "2026-07-01", "2026-07-21", 1001)
    assert result["failure_class"] == "malformed_response"

    monkeypatch.setattr(module, "SSI_V3_MAX_PAGES", 1)
    market.ohlc_pages = {1: [candle()] * 1000}
    guarded = adapter.get_daily_ohlcv(
        "FPT", "2026-07-01", "2026-07-21", limit=2000
    )
    assert guarded["failure_class"] == "malformed_response"

    ordered_adapter, _auth, ordered_market, _data = make_adapter()
    ordered_market.ohlc_pages = {
        1: [candle(trading_date="2026/07/21"), candle(trading_date="2026/07/20")]
    }
    rows = ordered_adapter.get_daily_ohlcv(
        "FPT", "2026-07-01", "2026-07-21", limit=2
    )["rows"]
    assert [row["date"] for row in rows] == ["2026-07-21", "2026-07-20"]


@pytest.mark.parametrize(
    ("row", "failure_class"),
    [
        (candle(open_price="NaN"), "malformed_response"),
        (candle(trading_date="not-a-date"), "malformed_response"),
    ],
)
def test_ohlc_rejects_non_finite_and_malformed_dates(row: Any, failure_class: str) -> None:
    adapter, _auth, market, _data = make_adapter()
    market.ohlc_pages = {1: [row]}
    result = adapter.get_daily_ohlcv("FPT", "2026-07-01", "2026-07-21", 1)
    assert result["failure_class"] == failure_class


def test_ohlc_limit_is_bounded() -> None:
    adapter, _auth, _market, _data = make_adapter()
    assert adapter.get_daily_ohlcv("FPT", limit=0)["failure_class"] == "validation_error"
    assert adapter.get_daily_ohlcv("FPT", limit=SSI_V3_MAX_ROWS + 1)["failure_class"] == "validation_error"


def test_index_list_all_board_and_explicit_board_normalization() -> None:
    adapter, _auth, market, _data = make_adapter()
    market.indexes = [
        SimpleNamespace(
            index="VN30", index_name="VN30 Index", board=SimpleNamespace(value="HOSE")
        )
    ]
    all_result = adapter.get_index_list()
    board_result = adapter.get_index_list("hose")

    assert market.calls == [("indexes", None), ("indexes_board", "HOSE")]
    assert all_result["rows"][0]["index_code"] == "VN30"
    assert board_result["rows"][0]["exchange"] == "HOSE"
    assert adapter.get_index_list("BAD")["failure_class"] == "validation_error"


def test_index_summary_uses_official_board_index_date_request_and_normalizes() -> None:
    adapter, auth, _market, _data = make_adapter()
    auth.rest_client.payload = [
        {
            "tradingDate": "2026/07/21",
            "totalTrade": "0",
            "totalTradeValue": None,
            "totalMatch": "10",
            "totalMatchValue": "20.5",
            "totalDeal": "1",
            "totalDealValue": "2.5",
            "indexChange": "-1.25",
            "indexChangePercentage": "-0.1",
            "indexValue": "1250.5",
            "totalAdvanceStock": "10",
            "totalDeclineStock": "12",
            "totalNoChangeStock": "3",
            "totalCeilingStock": "1",
            "totalFloorStock": "0",
        }
    ]
    result = adapter.get_index_summary("hose", "vn30", "2026-07-21")
    row = result["rows"][0]

    assert auth.rest_client.calls == [
        (
            "/api/v3/data/indexSummary",
            {"params": {"board": "HOSE", "index": "VN30", "tradingDate": "2026/07/21"}},
        )
    ]
    assert row["index_code"] == "VN30"
    assert row["total_volume"] == 0
    assert row["total_value"] is None
    assert row["exchange"] == "HOSE"


@pytest.mark.parametrize(
    ("error", "failure_class"),
    [
        (pytest.param("auth", "authentication_failed", id="auth")),
        (pytest.param("entitlement", "entitlement_unavailable", id="entitlement")),
        (pytest.param("timeout", "request_timeout", id="timeout")),
        (pytest.param("network", "network_error", id="network")),
        (pytest.param("rate", "rate_limited", id="rate")),
        (pytest.param("validation", "validation_error", id="validation")),
        (pytest.param("provider", "provider_unavailable", id="provider")),
        (pytest.param("generic", "internal_error", id="generic")),
    ],
)
def test_error_normalization(error: Any, failure_class: str) -> None:
    from ssi_sdk.exceptions import (
        APIError,
        AuthenticationError,
        RateLimitError,
        ValidationError,
    )

    errors = {
        "auth": AuthenticationError("rejected", status_code=401),
        "entitlement": AuthenticationError("forbidden", status_code=403),
        "timeout": httpx.ReadTimeout("timeout"),
        "network": httpx.ConnectError("network"),
        "rate": RateLimitError("limited", retry_after=3.0),
        "validation": ValidationError("invalid"),
        "provider": APIError("provider", status_code=503),
        "generic": RuntimeError("generic"),
    }
    adapter, _auth, market, _data = make_adapter()
    market.error = errors[error]
    result = adapter.get_index_list()

    assert result["failure_class"] == failure_class
    rendered = repr(result)
    assert "<client-id>" not in rendered
    assert "<api-key>" not in rendered
    assert "<api-secret>" not in rendered
    rate = result["diagnostics"]["rate_limit"]
    assert rate["limit"] is None and rate["remaining"] is None and rate["reset"] is None


class MinimalV2Fetcher:
    def __init__(self) -> None:
        self.calls: List[str] = []
        self.close_calls = 0

    def _result(self, name: str) -> Dict[str, Any]:
        self.calls.append(name)
        return {"status": "ok", "source": "SSI", "rows": [], "count": 0}

    def get_securities(self, **kwargs: Any) -> Dict[str, Any]:
        return self._result("get_securities")

    def get_securities_details(self, **kwargs: Any) -> Dict[str, Any]:
        return self._result("get_securities_details")

    def get_daily_ohlcv(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._result("get_daily_ohlcv")

    def get_intraday_ohlcv(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._result("get_intraday_ohlcv")

    def get_completed_intraday_1m(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._result("get_completed_intraday_1m")

    def get_daily_stock_price(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._result("get_daily_stock_price")

    def get_index_list(self, **kwargs: Any) -> Dict[str, Any]:
        return self._result("get_index_list")

    def get_daily_index(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._result("get_daily_index")

    def get_index_components(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._result("get_index_components")

    def close(self) -> None:
        self.close_calls += 1


class StubV3Provider:
    def __init__(self, result: Optional[Dict[str, Any]] = None) -> None:
        self.calls: List[str] = []
        self.result = result or {"status": "ok", "source": SSI_V3_SOURCE, "rows": [], "count": 0}

    def _call(self, name: str) -> Dict[str, Any]:
        self.calls.append(name)
        return self.result

    def get_securities(self, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_securities")

    def get_security_basic_info(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_security_basic_info")

    def get_securities_by_index(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_securities_by_index")

    def get_daily_ohlcv(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_daily_ohlcv")

    def get_completed_intraday_1m(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_completed_intraday_1m")

    def get_index_list(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_index_list")

    def get_index_summary(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_index_summary")

    def close(self) -> None:
        self.calls.append("close")


def v3_config() -> Config:
    return Config(
        ssi_fastconnect_rest_version="v3",
        ssi_v3_rest_enabled=True,
        ssi_v3_client_id="<client-id>",
        ssi_v3_api_key="<api-key>",
        ssi_v3_api_secret="<api-secret>",
    )


def test_router_routes_supported_v3_and_explicit_v2_pins_without_fallback() -> None:
    v2 = MinimalV2Fetcher()
    v3 = StubV3Provider()
    router = create_ssi_rest_provider_router(
        config=v3_config(), v2_fetcher=v2, v3_provider=v3  # type: ignore[arg-type]
    )

    router.get_daily_ohlcv("FPT")
    router.get_daily_stock_price("FPT")
    router.get_intraday_ohlcv("FPT")
    router.get_index_components("VN30")
    router.get_daily_index("VN30")

    assert v3.calls == ["get_daily_ohlcv"]
    assert v2.calls == [
        "get_daily_stock_price",
        "get_intraday_ohlcv",
        "get_index_components",
        "get_daily_index",
    ]
    supported = router.routing_diagnostics("daily_ohlcv")
    pinned = router.routing_diagnostics("foreign_flow")
    assert supported["selected_version"] == "v3" and supported["fallback_used"] is False
    assert pinned["selected_version"] == "v2" and pinned["v2_pinned"] is True


def test_v3_failure_never_invokes_v2() -> None:
    v2 = MinimalV2Fetcher()
    failure = {"status": "unavailable", "source": SSI_V3_SOURCE, "failure_class": "request_timeout", "rows": []}
    v3 = StubV3Provider(failure)
    router = create_ssi_rest_provider_router(
        config=v3_config(), v2_fetcher=v2, v3_provider=v3  # type: ignore[arg-type]
    )

    assert router.get_daily_ohlcv("FPT") is failure
    assert v3.calls == ["get_daily_ohlcv"]
    assert v2.calls == []


def test_current_session_completed_method_name_remains_v2_pinned() -> None:
    v2 = MinimalV2Fetcher()
    v3 = StubV3Provider()
    router = create_ssi_rest_provider_router(
        config=v3_config(), v2_fetcher=v2, v3_provider=v3  # type: ignore[arg-type]
    )

    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%Y-%m-%d")
    router.get_completed_intraday_1m("FPT", today)

    assert v2.calls == ["get_completed_intraday_1m"]
    assert v3.calls == []


def test_v2_adapter_remains_default_and_structural_router_contract_holds() -> None:
    v2 = MinimalV2Fetcher()
    router = create_ssi_rest_provider_router(version="", v2_fetcher=v2)
    assert isinstance(router.provider, SsiFastConnectV2Adapter)
    router.get_daily_ohlcv("FPT")
    assert v2.calls == ["get_daily_ohlcv"]


def test_static_scope_guards_keep_v3_out_of_streaming_trading_and_production_foreign_flow() -> None:
    streaming_files = [
        ROOT / "data_provider" / "ssi_streaming_realtime.py",
        ROOT / "src" / "services" / "ssi_streaming_realtime_lifecycle.py",
    ]
    assert all("ssi_sdk" not in path.read_text(encoding="utf-8") for path in streaming_files)

    adapter_text = (ROOT / "data_provider" / "ssi_v3_adapter.py").read_text(encoding="utf-8")
    assert "Trading(" not in adapter_text
    assert "request_otp" not in adapter_text
    assert "private_key=" not in adapter_text
    assert "SSI_V3_SECURITIES_SUMMARY_PATH" in adapter_text
    assert "totalForeignBuy" in adapter_text

    foreign_text = (ROOT / "src" / "services" / "vietnam_foreign_flow_service.py").read_text(
        encoding="utf-8"
    )
    assert "get_index_summary" not in foreign_text
    assert "ssi_v3_adapter" not in foreign_text

    router_text = (ROOT / "data_provider" / "ssi_provider_router.py").read_text(encoding="utf-8")
    assert '"index_membership_production"' in router_text
    assert "fallback_used" in router_text
    tree = ast.parse(router_text)
    router_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SsiRestProviderRouter"
    )
    routed_methods = {
        node.name: node
        for node in router_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("get_")
    }
    assert routed_methods
    assert all(
        not any(isinstance(child, ast.Try) for child in ast.walk(method))
        for method in routed_methods.values()
    )


def test_v3_sdk_import_is_scoped_to_adapter_tests_and_dependency_references() -> None:
    production_hits: List[str] = []
    for base in (ROOT / "data_provider", ROOT / "src", ROOT / "api"):
        for path in base.rglob("*.py"):
            if "ssi_sdk" in path.read_text(encoding="utf-8"):
                production_hits.append(path.relative_to(ROOT).as_posix())
    assert production_hits == ["data_provider/ssi_v3_adapter.py"]


def test_provider_version_namespaces_only_v3_service_cache_keys() -> None:
    v2_intraday_key = _intraday_chart_cache_key("FPT", "2026-07-21")
    v3_intraday_key = _intraday_chart_cache_key("FPT", "2026-07-21", "v3")
    v2_service = VietnamMarketService(
        config=VietnamDashboardConfig(ssi_fastconnect_rest_version="v2")
    )
    v3_service = VietnamMarketService(
        config=VietnamDashboardConfig(ssi_fastconnect_rest_version="v3")
    )

    assert v3_intraday_key == (*v2_intraday_key, "provider_version", "v3")
    assert "provider_version" not in v2_service._daily_ohlcv_cache_key(
        "FPT", "ssi", limit=260, days=90
    )
    assert ("provider_version", "v3") in v3_service._daily_ohlcv_cache_key(
        "FPT", "ssi", limit=260, days=90
    )


def test_completed_intraday_normalizer_accepts_v3_normalized_rows() -> None:
    payload = normalize_completed_intraday_chart_rows(
        [
            {
                "date_time": "2026-07-21T09:15:42+07:00",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100.5,
                "volume": 0,
            }
        ],
        "2026-07-21",
    )
    assert payload["status"] == "ready"
    assert payload["bars"][0]["volume"] == 0
