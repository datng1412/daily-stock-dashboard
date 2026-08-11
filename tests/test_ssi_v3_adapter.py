"""Deterministic offline contract tests for the SSI-V3-B2 foundation."""

from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
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
from data_provider.ssi_v3_adapter import (
    SSI_V3_MAX_ROWS,
    SSI_V3_SOURCE,
    SsiFastConnectV3Adapter,
    SsiV3RestSettings,
)
from src.config import Config
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
        self.handler: Optional[Any] = None

    def get(self, path: str, **kwargs: Any) -> Any:
        self.calls.append((path, kwargs))
        if self.error is not None:
            raise self.error
        if self.handler is not None:
            return self.handler(path, kwargs)
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
        self.current_ohlc: Any = []
        self.error: Optional[BaseException] = None
        self.market_summary: Any = None

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

    def get_ohlc_1minute(self, symbol: str) -> Any:
        self.calls.append(("1m_current", symbol))
        self._raise()
        return self.current_ohlc

    def get_index_summary(self, index: str) -> Any:
        self.calls.append(("index_summary", index))
        return self.market_summary

    def get_index_summary_historical(self, index: str, trading_date: str) -> Any:
        self.calls.append(("index_summary_historical", index, trading_date))
        return self.market_summary

    def get_board_summary(self, board: Any) -> Any:
        self.calls.append(("board_summary", getattr(board, "value", board)))
        return self.market_summary

    def get_board_summary_historical(self, board: Any, trading_date: str) -> Any:
        self.calls.append(("board_summary_historical", getattr(board, "value", board), trading_date))
        return self.market_summary


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
        "icb_code": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def market_summary(**overrides: Any) -> SimpleNamespace:
    values = {
        "trading_date": "2026/07/24",
        "total_trade": 100,
        "total_trade_value": 1_000,
        "total_match": 90,
        "total_match_value": 900,
        "total_deal": 10,
        "total_deal_value": 100,
        "index_value": 1_500,
        "index_change": 5,
        "index_change_percent": 0.3,
        "total_advance_stock": 10,
        "total_decline_stock": 5,
        "total_steady_stock": 2,
        "total_ceiling_stock": 1,
        "total_floor_stock": 0,
        "total_prop_buy": 20,
        "total_prop_buy_value": 200,
        "total_prop_sell": 7,
        "total_prop_sell_value": 70,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_security_normalization_preserves_exact_ssi_icb_fields() -> None:
    adapter, _auth, market, _data = make_adapter()
    market.securities = security(icb_code="9530", icb_name="Software")

    result = adapter.get_security_basic_info("FPT")

    assert result["status"] == "ok"
    assert result["rows"][0]["icb_code"] == "9530"
    assert result["rows"][0]["icb_name"] == "Software"


def test_index_components_preserve_provider_icb_classification() -> None:
    adapter, _auth, market, _data = make_adapter()
    market.securities = [security(
        symbol="FPT",
        icb_code="9530",
        icb_name="Software",
    )]

    result = adapter.get_index_components("VN30")

    assert result["status"] == "ok"
    assert result["rows"][0]["symbol"] == "FPT"
    assert result["rows"][0]["industry"] == "Software"
    assert result["rows"][0]["icb_code"] == "9530"
    assert result["rows"][0]["icb_name"] == "Software"


def test_market_summary_keeps_board_scope_and_nullable_gross_proprietary_fields() -> None:
    adapter, _auth, market, _data = make_adapter()
    market.market_summary = market_summary()

    result = adapter.get_market_summary("board", "HOSE", trading_date="2026-07-24")

    assert result["status"] == "ok"
    row = result["rows"][0]
    assert row["index_code"] is None
    assert row["exchange"] == "HOSE"
    assert row["proprietary_buy_volume"] == 20
    assert row["proprietary_sell_volume"] == 7
    assert row["proprietary_net_volume"] == 13
    assert row["proprietary_net_value"] == 130
    assert market.calls[-1] == ("board_summary_historical", "HOSE", "2026/07/24")


def test_market_summary_does_not_derive_net_when_one_gross_side_is_missing() -> None:
    adapter, _auth, market, _data = make_adapter()
    market.market_summary = market_summary(total_prop_sell=None, total_prop_sell_value=None)

    result = adapter.get_market_summary("index", "VN30")

    row = result["rows"][0]
    assert row["proprietary_sell_volume"] is None
    assert row["proprietary_net_volume"] is None
    assert row["proprietary_sell_value"] is None
    assert row["proprietary_net_value"] is None


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
    assert "ssi-fc-data" not in requirements
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

    assert not hasattr(config, "ssi_fastconnect_rest_version")
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
    disabled = Config(ssi_v3_rest_enabled=False)
    with pytest.raises(ValueError, match="SSI_V3_REST_ENABLED=true"):
        create_ssi_rest_provider_router(config=disabled)

    incomplete = Config(
        ssi_v3_rest_enabled=True,
        ssi_v3_client_id=None,
        ssi_v3_api_key="<api-key>",
        ssi_v3_api_secret=None,
    )
    with pytest.raises(ValueError) as exc_info:
        create_ssi_rest_provider_router(config=incomplete)
    message = str(exc_info.value)
    assert "SSI_V3_CLIENT_ID" not in message and "SSI_V3_API_SECRET" in message
    assert "<api-key>" not in message


def test_global_provider_selector_and_v2_factory_input_are_removed() -> None:
    signature = inspect.signature(create_ssi_rest_provider_router)
    assert "version" not in signature.parameters
    assert "v2_fetcher" not in signature.parameters


def test_v2_runtime_modules_are_absent_after_atomic_cutover() -> None:
    retired_runtime_paths = (
        ROOT / "data_provider" / "ssi_fastconnect_fetcher.py",
        ROOT / "data_provider" / "ssi_v2_adapter.py",
    )
    assert all(not path.exists() for path in retired_runtime_paths)


def test_config_validation_lists_v3_names_without_values() -> None:
    config = Config(
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
        "SSI_V3_LIVE_ACCEPTANCE_ENABLED",
    }
    assert expected <= WEB_SETTINGS_HIDDEN_FROM_UI


def test_market_service_passes_dedicated_v3_settings_to_router() -> None:
    config = VietnamDashboardConfig(
        ssi_v3_rest_enabled=True,
        ssi_v3_client_id="<client-id>",
        ssi_v3_api_key="<api-key>",
        ssi_v3_api_secret="<api-secret>",
    )
    service = VietnamMarketService(config=config)
    try:
        router = service._get_ssi_rest_provider()
        current_router_type = importlib.import_module(
            "data_provider.ssi_provider_router"
        ).SsiRestProviderRouter
        assert isinstance(router, current_router_type)
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


def test_operation_auth_failure_invalidates_shared_client_and_recovers_once() -> None:
    class AuthenticationError(RuntimeError):
        status_code = 401

    auths = [FakeAuth(), FakeAuth()]
    first_market = FakeMarketData()
    first_market.error = AuthenticationError("401 Unauthorized")
    second_market = FakeMarketData()
    second_market.indexes = []
    data_by_auth = {
        id(auths[0]): FakeData(first_market),
        id(auths[1]): FakeData(second_market),
    }
    auth_factory_calls = 0

    def auth_factory(_settings: SsiV3RestSettings) -> FakeAuth:
        nonlocal auth_factory_calls
        auth = auths[auth_factory_calls]
        auth_factory_calls += 1
        return auth

    adapter = SsiFastConnectV3Adapter(
        complete_settings(),
        auth_factory=auth_factory,
        data_factory=lambda auth: data_by_auth[id(auth)],
    )

    failed = adapter.get_index_list()
    cooled_down = adapter.get_index_list()
    recovery = adapter.request_auth_recovery(trigger="visibility_resume")
    duplicate = adapter.request_auth_recovery(trigger="manual_refresh")
    recovered = adapter.get_index_list()

    assert failed["failure_class"] == "authentication_failed"
    assert failed["diagnostics"]["authentication_failure_retryable"] is True
    assert cooled_down["failure_class"] == "authentication_failed"
    assert auth_factory_calls == 2
    assert recovery == {
        "status": "scheduled",
        "recovery_scheduled": True,
        "negative_cache_bypassed": True,
    }
    assert duplicate["status"] == "cooldown"
    assert duplicate["recovery_scheduled"] is False
    assert recovered["status"] == "ok"
    assert auths[0].close_calls == 1
    assert data_by_auth[id(auths[0])].close_calls == 1


def test_failed_auth_recovery_reenters_cooldown_without_another_bypass() -> None:
    class AuthenticationError(RuntimeError):
        status_code = 401

    auths = [FakeAuth(), FakeAuth(), FakeAuth()]
    markets = [FakeMarketData(), FakeMarketData(), FakeMarketData()]
    for market in markets:
        market.error = AuthenticationError("401 Unauthorized")
    data_by_auth = {
        id(auth): FakeData(market)
        for auth, market in zip(auths, markets)
    }
    auth_factory_calls = 0

    def auth_factory(_settings: SsiV3RestSettings) -> FakeAuth:
        nonlocal auth_factory_calls
        auth = auths[auth_factory_calls]
        auth_factory_calls += 1
        return auth

    adapter = SsiFastConnectV3Adapter(
        complete_settings(),
        auth_factory=auth_factory,
        data_factory=lambda auth: data_by_auth[id(auth)],
    )

    assert adapter.get_index_list()["failure_class"] == "authentication_failed"
    assert adapter.request_auth_recovery(trigger="visibility_resume")["status"] == "scheduled"
    assert adapter.get_index_list()["failure_class"] == "authentication_failed"

    duplicate = adapter.request_auth_recovery(trigger="manual_refresh")
    cooled_down = adapter.get_index_list()

    assert duplicate["status"] == "cooldown"
    assert duplicate["recovery_scheduled"] is False
    assert cooled_down["failure_class"] == "authentication_failed"
    assert auth_factory_calls == 2


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
    adapter, auth, _market, _data = make_adapter()
    auth.rest_client.payload = {
        "data": [
            {
                "symbol": "FPT",
                "tradingDate": "2026/07/21",
                "open": "100.5",
                "high": "101.5",
                "low": "99.5",
                "close": "100",
                "totalMatch": "0",
                "totalMatchValue": None,
            }
        ],
        "pagesCount": 1,
    }
    result = adapter.get_daily_ohlcv(
        "fpt", from_date="2026-07-01", to_date="2026-07-21", limit=2
    )
    row = result["rows"][0]

    assert auth.rest_client.calls[0][1]["params"] == {
        "from": "2026/07/01",
        "to": "2026/07/21",
        "pageIndex": 1,
        "pageSize": 2,
        "symbol": "FPT",
    }
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


def test_current_intraday_is_sorted_and_deduplicated() -> None:
    adapter, _auth, market, _data = make_adapter()
    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%Y/%m/%d")
    market.current_ohlc = [
        candle(trading_date=f"{today} 09:16:00"),
        candle(trading_date=f"{today} 09:15:00"),
        candle(trading_date=f"{today} 09:16:00", close_price=101),
    ]

    result = adapter.get_completed_intraday_1m("FPT", today)

    assert market.calls == [("1m_current", "FPT")]
    assert [row["date_time"].split("T", 1)[1][:8] for row in result["rows"]] == [
        "09:15:00",
        "09:16:00",
    ]
    assert result["rows"][-1]["close"] == 101.0
    assert result["duplicate_date_count"] == 1


def test_daily_ohlc_empty_duplicate_date_and_ordering() -> None:
    adapter, auth, _market, _data = make_adapter()
    assert adapter.get_daily_ohlcv("FPT", "2026-07-01", "2026-07-21", 2)["rows"] == []

    auth.rest_client.payload = {
        "data": [
            {"symbol": "FPT", "tradingDate": "2026/07/21", "totalMatch": "2"},
            {"symbol": "FPT", "tradingDate": "2026/07/20", "totalMatch": "1"},
            {"symbol": "FPT", "tradingDate": "2026/07/21", "totalMatch": "3"},
        ],
        "pagesCount": 1,
    }
    rows = adapter.get_daily_ohlcv(
        "FPT", "2026-07-01", "2026-07-21", limit=3
    )["rows"]
    assert [row["date"] for row in rows] == ["2026-07-20", "2026-07-21"]
    assert rows[-1]["volume"] == 3


def _weekday_summary_rows(start: str, count: int) -> List[Dict[str, Any]]:
    candidate = datetime.strptime(start, "%Y-%m-%d").date()
    rows: List[Dict[str, Any]] = []
    while len(rows) < count:
        if candidate.weekday() < 5:
            ordinal = len(rows) + 1
            rows.append(
                {
                    "symbol": "FPT",
                    "tradingDate": candidate.strftime("%Y/%m/%d"),
                    "open": str(ordinal),
                    "high": str(ordinal + 2),
                    "low": str(ordinal - 1),
                    "close": str(ordinal + 1),
                    "totalMatch": str(ordinal * 10),
                    "totalMatchValue": str(ordinal * 100),
                }
            )
        candidate += timedelta(days=1)
    return rows


def _summary_window_handler(
    rows: List[Dict[str, Any]],
    *,
    order: str,
    provider_cap: Optional[int] = None,
    paginate: bool = False,
) -> Any:
    def handler(_path: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        params = kwargs["params"]
        start = datetime.strptime(params["from"], "%Y/%m/%d").date()
        end = datetime.strptime(params["to"], "%Y/%m/%d").date()
        selected = [
            row
            for row in rows
            if start
            <= datetime.strptime(row["tradingDate"], "%Y/%m/%d").date()
            <= end
        ]
        selected.sort(
            key=lambda row: row["tradingDate"],
            reverse=order == "descending",
        )
        if paginate:
            page_size = int(params["pageSize"])
            page_index = int(params["pageIndex"])
            pages_count = max(1, (len(selected) + page_size - 1) // page_size)
            offset = (page_index - 1) * page_size
            selected = selected[offset : offset + page_size]
        else:
            pages_count = 1
            if provider_cap is not None:
                selected = selected[:provider_cap]
        return {
            "data": selected,
            "pagesCount": pages_count,
            "totalCount": len(
                [
                    row
                    for row in rows
                    if start
                    <= datetime.strptime(row["tradingDate"], "%Y/%m/%d").date()
                    <= end
                ]
            ),
        }

    return handler


@pytest.mark.parametrize("order", ["ascending", "descending"])
def test_daily_history_windows_retain_newest_sessions_for_provider_order(order: str) -> None:
    rows = _weekday_summary_rows("2025-01-02", 400)
    adapter, auth, _market, _data = make_adapter()
    auth.rest_client.handler = _summary_window_handler(
        rows,
        order=order,
        provider_cap=252,
    )

    result = adapter.get_daily_ohlcv(
        "FPT",
        from_date=rows[0]["tradingDate"],
        to_date=rows[-1]["tradingDate"],
        limit=252,
    )

    expected_dates = [
        datetime.strptime(row["tradingDate"], "%Y/%m/%d").date().isoformat()
        for row in rows[-252:]
    ]
    assert result["status"] == "ok"
    assert [row["date"] for row in result["rows"]] == expected_dates
    assert result["diagnostics"]["window_count"] > 1
    assert result["diagnostics"]["freshness_status"] == "fresh"
    assert result["diagnostics"]["max_date"] == expected_dates[-1]


def test_daily_history_exhausts_declared_pages_before_newest_limit_selection() -> None:
    rows = _weekday_summary_rows("2026-06-01", 30)
    adapter, auth, _market, _data = make_adapter()
    auth.rest_client.handler = _summary_window_handler(
        rows,
        order="ascending",
        paginate=True,
    )

    result = adapter.get_daily_ohlcv(
        "FPT",
        from_date=rows[0]["tradingDate"],
        to_date=rows[-1]["tradingDate"],
        limit=5,
    )

    assert result["status"] == "ok"
    assert [row["date"] for row in result["rows"]] == [
        datetime.strptime(row["tradingDate"], "%Y/%m/%d").date().isoformat()
        for row in rows[-5:]
    ]
    assert result["pages_used"] == 6
    assert [call[1]["params"]["pageIndex"] for call in auth.rest_client.calls] == list(
        range(1, 7)
    )


def test_daily_history_fails_closed_when_provider_window_is_incomplete() -> None:
    rows = _weekday_summary_rows("2026-01-02", 120)
    adapter, auth, _market, _data = make_adapter()
    auth.rest_client.handler = _summary_window_handler(
        rows,
        order="ascending",
        provider_cap=20,
    )

    result = adapter.get_daily_ohlcv(
        "FPT",
        from_date=rows[0]["tradingDate"],
        to_date=rows[-1]["tradingDate"],
        limit=100,
    )

    assert result["status"] == "partial"
    assert result["failure_class"] == "incomplete_daily_history"
    assert result["diagnostics"]["provider_reported_total_count"] > result["diagnostics"][
        "provider_row_count"
    ]


@pytest.mark.parametrize(
    ("row", "failure_class"),
    [
        (candle(open_price="NaN"), "malformed_response"),
        (candle(trading_date="not-a-date"), "malformed_response"),
    ],
)
def test_ohlc_rejects_non_finite_and_malformed_dates(row: Any, failure_class: str) -> None:
    adapter, auth, _market, _data = make_adapter()
    raw = {
        "symbol": "FPT",
        "tradingDate": getattr(row, "trading_date", None),
        "open": getattr(row, "open_price", None),
    }
    auth.rest_client.payload = {"data": [raw], "pagesCount": 1}
    result = adapter.get_daily_ohlcv("FPT", "2026-07-01", "2026-07-21", 1)
    assert result["failure_class"] == failure_class


@pytest.mark.parametrize("raw_zero", [0, 0.0, "0"])
def test_securities_summary_preserves_explicit_foreign_zero_lineage(
    raw_zero: Any,
) -> None:
    row = SsiFastConnectV3Adapter._summary_row(
        {
            "symbol": "FPT",
            "tradingDate": "2026/07/28",
            "totalForeignBuy": raw_zero,
            "totalForeignSell": raw_zero,
            "totalForeignBuyValue": raw_zero,
            "totalForeignSellValue": raw_zero,
        },
        expected_symbol="FPT",
    )

    assert [row[field] for field in (
        "foreign_buy_volume",
        "foreign_sell_volume",
        "foreign_net_volume",
        "foreign_buy_value",
        "foreign_sell_value",
        "foreign_net_value",
    )] == [0, 0, 0, 0.0, 0.0, 0.0]
    assert all(
        row["_foreign_field_presence"][field]
        == "FIELD_PRESENT_EXPLICIT_ZERO"
        for field in (
            "foreign_buy_volume",
            "foreign_sell_volume",
            "foreign_buy_value",
            "foreign_sell_value",
        )
    )
    assert row["_foreign_field_presence"]["foreign_net_volume"] == "DERIVED_FROM_PRESENT_INPUTS"
    assert row["_foreign_field_presence"]["foreign_net_value"] == "DERIVED_FROM_PRESENT_INPUTS"
    assert row["_foreign_net_volume_source"] == "derived"
    assert row["_foreign_net_value_source"] == "derived"
    assert row["_foreign_normalization_issues"] == []


@pytest.mark.parametrize(
    ("foreign_value", "expected_presence"),
    [
        (None, "FIELD_NULL"),
        ("", "FIELD_NULL"),
        ("   ", "FIELD_NULL"),
    ],
)
def test_securities_summary_keeps_null_and_empty_foreign_fields_null(
    foreign_value: Any,
    expected_presence: str,
) -> None:
    row = SsiFastConnectV3Adapter._summary_row(
        {
            "symbol": "FPT",
            "tradingDate": "2026/07/28",
            "totalForeignBuy": foreign_value,
        },
        expected_symbol="FPT",
    )

    assert row["foreign_buy_volume"] is None
    assert row["foreign_net_volume"] is None
    assert row["_foreign_field_presence"]["foreign_buy_volume"] == expected_presence
    assert row["_foreign_field_presence"]["foreign_sell_volume"] == "FIELD_ABSENT"
    assert row["_foreign_field_presence"]["foreign_net_volume"] == "DERIVATION_UNAVAILABLE"


def test_securities_summary_marks_malformed_foreign_field_without_fabricating_zero() -> None:
    row = SsiFastConnectV3Adapter._summary_row(
        {
            "symbol": "FPT",
            "tradingDate": "2026/07/28",
            "totalForeignBuy": "not-a-number",
            "totalForeignSell": 0,
        },
        expected_symbol="FPT",
    )

    assert row["foreign_buy_volume"] is None
    assert row["foreign_net_volume"] is None
    assert row["_foreign_field_presence"]["foreign_buy_volume"] == "PARSE_FAILURE"
    assert row["_foreign_normalization_issues"] == [
        {
            "field": "totalForeignBuy",
            "issue": "NON_NUMERIC_PROVIDER_FIELD",
        }
    ]


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
            {"params": {"index": "VN30", "tradingDate": "2026/07/21"}},
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
        "entitlement": AuthenticationError("not entitled", status_code=403),
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
    if error == "auth":
        assert result["diagnostics"]["http_status"] == 401


def test_generic_403_is_retryable_auth_not_proven_entitlement() -> None:
    from ssi_sdk.exceptions import AuthenticationError

    adapter, _auth, market, _data = make_adapter()
    market.error = AuthenticationError("forbidden", status_code=403)

    result = adapter.get_index_list()

    assert result["failure_class"] == "authentication_failed"
    assert result["diagnostics"]["authentication_failure_retryable"] is True


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

    def get_security_metadata(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_security_metadata")

    def get_securities_by_index(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_securities_by_index")

    def get_daily_ohlcv(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_daily_ohlcv")

    def get_completed_intraday_1m(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_completed_intraday_1m")

    def get_intraday_ohlcv(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_intraday_ohlcv")

    def get_daily_stock_price(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_daily_stock_price")

    def get_index_list(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_index_list")

    def get_index_summary(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_index_summary")

    def get_daily_index(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_daily_index")

    def get_index_components(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._call("get_index_components")

    def close(self) -> None:
        self.calls.append("close")


def v3_config() -> Config:
    return Config(
        ssi_v3_rest_enabled=True,
        ssi_v3_client_id="<client-id>",
        ssi_v3_api_key="<api-key>",
        ssi_v3_api_secret="<api-secret>",
    )


def test_router_routes_all_retained_product_capabilities_to_v3_without_fallback() -> None:
    v3 = StubV3Provider()
    router = create_ssi_rest_provider_router(
        config=v3_config(), v3_provider=v3  # type: ignore[arg-type]
    )

    router.get_daily_ohlcv("FPT")
    router.get_daily_stock_price("FPT")
    router.get_intraday_ohlcv("FPT")
    router.get_index_components("VN30")
    router.get_daily_index("VN30")

    assert v3.calls == [
        "get_daily_ohlcv",
        "get_daily_stock_price",
        "get_intraday_ohlcv",
        "get_index_components",
        "get_daily_index",
    ]
    supported = router.routing_diagnostics("daily_ohlcv")
    summary = router.routing_diagnostics("foreign_flow")
    assert supported["selected_version"] == "v3" and supported["fallback_used"] is False
    assert summary["selected_version"] == "v3" and summary["fallback_used"] is False


def test_v3_failure_never_invokes_v2() -> None:
    failure = {"status": "unavailable", "source": SSI_V3_SOURCE, "failure_class": "request_timeout", "rows": []}
    v3 = StubV3Provider(failure)
    router = create_ssi_rest_provider_router(
        config=v3_config(), v3_provider=v3  # type: ignore[arg-type]
    )

    assert router.get_daily_ohlcv("FPT") is failure
    assert v3.calls == ["get_daily_ohlcv"]


def test_current_session_completed_method_routes_to_v3() -> None:
    v3 = StubV3Provider()
    router = create_ssi_rest_provider_router(
        config=v3_config(), v3_provider=v3  # type: ignore[arg-type]
    )

    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%Y-%m-%d")
    router.get_completed_intraday_1m("FPT", today)

    assert v3.calls == ["get_completed_intraday_1m"]


def test_router_source_has_no_v2_adapter_construction() -> None:
    router_text = (ROOT / "data_provider" / "ssi_provider_router.py").read_text(
        encoding="utf-8"
    )
    assert "ssi_v2_adapter" not in router_text
    assert "SsiFastConnectFetcher" not in router_text


def test_static_scope_guards_keep_v3_out_of_trading_and_preserve_no_fallback_router() -> None:
    streaming_files = [
        ROOT / "data_provider" / "ssi_streaming_realtime.py",
        ROOT / "src" / "services" / "ssi_streaming_realtime_lifecycle.py",
    ]
    assert all("ssi_sdk" not in path.read_text(encoding="utf-8") for path in streaming_files)

    adapter_text = (ROOT / "data_provider" / "ssi_v3_adapter.py").read_text(encoding="utf-8")
    assert "Trading(" not in adapter_text
    assert "request_otp" not in adapter_text
    assert 'private_key=""' in adapter_text
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
    assert production_hits == [
        "data_provider/ssi_v3_adapter.py",
        "data_provider/ssi_v3_streaming.py",
    ]


def test_service_cache_keys_are_always_v3_namespaced() -> None:
    default_intraday_key = _intraday_chart_cache_key("FPT", "2026-07-21")
    v3_intraday_key = _intraday_chart_cache_key("FPT", "2026-07-21", "v3")
    service = VietnamMarketService(config=VietnamDashboardConfig())

    assert v3_intraday_key == default_intraday_key
    assert ("provider_version", "v3") in service._daily_ohlcv_cache_key(
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
