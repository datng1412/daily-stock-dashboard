"""Sole-provider routing for SSI FastConnect V3 Market Data REST."""

from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import Any, Optional, Tuple
from zoneinfo import ZoneInfo

from data_provider.ssi_provider_models import ProviderDiagnostics, ProviderResult
from data_provider.ssi_provider_protocol import SsiRestProvider
from data_provider.ssi_v3_adapter import (
    SsiFastConnectV3Adapter,
    SsiV3RestSettings,
    validate_v3_selection,
)


V3_PRODUCT_CAPABILITIES = frozenset(
    {
        "securities_by_board",
        "security_basic_info",
        "security_extended_metadata",
        "securities_by_index_normalization",
        "daily_ohlcv",
        "completed_historical_intraday_ohlcv",
        "current_session_intraday",
        "daily_security_summary",
        "foreign_flow",
        "foreign_flow_history",
        "foreign_flow_by_index",
        "foreign_flow_analytics_input",
        "vn30_foreign_flow_input",
        "index_list",
        "index_summary",
        "market_summary",
        "daily_index_series",
        "index_membership_production",
    }
)

_SHARED_V3_LOCK = RLock()
_SHARED_V3_ADAPTER: Optional[SsiFastConnectV3Adapter] = None
_SHARED_V3_SETTINGS: Optional[SsiV3RestSettings] = None
_VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def _is_completed_vietnam_date(value: str) -> bool:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(text, fmt).date()
            return parsed < datetime.now(_VN_TIMEZONE).date()
        except ValueError:
            continue
    return False


def _get_shared_v3_adapter(settings: SsiV3RestSettings) -> SsiFastConnectV3Adapter:
    """Create one process-shared lazy adapter without initializing SDK clients."""
    global _SHARED_V3_ADAPTER, _SHARED_V3_SETTINGS
    with _SHARED_V3_LOCK:
        if _SHARED_V3_ADAPTER is None or _SHARED_V3_SETTINGS != settings:
            if _SHARED_V3_ADAPTER is not None:
                _SHARED_V3_ADAPTER.close()
            _SHARED_V3_ADAPTER = SsiFastConnectV3Adapter(settings)
            _SHARED_V3_SETTINGS = settings
        return _SHARED_V3_ADAPTER


def close_shared_ssi_v3_adapter() -> None:
    """Close an existing V3 lifecycle without creating one."""
    global _SHARED_V3_ADAPTER, _SHARED_V3_SETTINGS
    with _SHARED_V3_LOCK:
        adapter = _SHARED_V3_ADAPTER
        _SHARED_V3_ADAPTER = None
        _SHARED_V3_SETTINGS = None
    if adapter is not None:
        adapter.close()


class SsiRestProviderRouter:
    """Route every retained capability to V3; never perform fallback."""

    def __init__(
        self,
        provider: SsiRestProvider,
        *,
        close_provider: bool = True,
    ) -> None:
        self._provider = provider
        self._close_provider = close_provider
        self._closed = False

    @property
    def selected_version(self) -> str:
        return "v3"

    @property
    def provider(self) -> SsiRestProvider:
        return self._provider

    @property
    def v3_provider(self) -> Optional[SsiRestProvider]:
        return self._provider

    def _route(self, capability: str) -> Tuple[SsiRestProvider, str]:
        if capability not in V3_PRODUCT_CAPABILITIES:
            raise ValueError(f"SSI REST capability {capability!r} is outside the V3 product contract")
        return self._provider, "sole_v3_product_capability"

    def routing_diagnostics(self, capability: Optional[str] = None) -> ProviderDiagnostics:
        if capability is None:
            return {
                "capability": None,
                "requested_rest_version": "v3",
                "selected_provider": "ssi_fastconnect_v3",
                "selected_version": "v3",
                "routing_reason": "sole_v3_provider",
                "fallback_used": False,
            }
        normalized = capability or "unspecified"
        _, reason = self._route(normalized)
        diagnostics: ProviderDiagnostics = {
            "capability": capability,
            "requested_rest_version": "v3",
            "selected_provider": "ssi_fastconnect_v3",
            "selected_version": "v3",
            "routing_reason": reason,
            "fallback_used": False,
        }
        return diagnostics

    def get_securities(self, market: Optional[str] = None) -> ProviderResult:
        provider, _ = self._route("securities_by_board")
        return provider.get_securities(market=market)

    def get_security_metadata(
        self,
        symbol: Optional[str] = None,
        market: Optional[str] = None,
    ) -> ProviderResult:
        provider, _ = self._route("security_extended_metadata")
        return provider.get_security_metadata(symbol=symbol, market=market)

    def get_security_basic_info(self, symbol: str) -> ProviderResult:
        provider, _ = self._route("security_basic_info")
        return provider.get_security_basic_info(symbol)

    def get_securities_by_index(self, index_code: str) -> ProviderResult:
        provider, _ = self._route("securities_by_index_normalization")
        return provider.get_securities_by_index(index_code)

    def get_daily_ohlcv(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
        force_refresh: bool = False,
    ) -> ProviderResult:
        provider, _ = self._route("daily_ohlcv")
        return provider.get_daily_ohlcv(
            symbol,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            force_refresh=force_refresh,
        )

    def get_intraday_ohlcv(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 64,
        interval: Optional[str] = None,
    ) -> ProviderResult:
        provider, _ = self._route("current_session_intraday")
        return provider.get_intraday_ohlcv(
            symbol,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            interval=interval,
        )

    def get_completed_intraday_1m(self, symbol: str, trading_date: str) -> ProviderResult:
        capability = (
            "completed_historical_intraday_ohlcv"
            if _is_completed_vietnam_date(trading_date)
            else "current_session_intraday"
        )
        provider, _ = self._route(capability)
        return provider.get_completed_intraday_1m(symbol, trading_date)

    def get_daily_stock_price(
        self,
        symbol: str,
        market: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
    ) -> ProviderResult:
        provider, _ = self._route("daily_security_summary")
        return provider.get_daily_stock_price(
            symbol,
            market=market,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )

    def get_securities_summary_by_index(
        self,
        index_code: str,
        *,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page_index: int = 1,
        page_size: int = 100,
        limit: int = 260,
    ) -> ProviderResult:
        provider, _ = self._route("foreign_flow_by_index")
        return provider.get_securities_summary_by_index(
            index_code,
            from_date=from_date,
            to_date=to_date,
            page_index=page_index,
            page_size=page_size,
            limit=limit,
        )

    def get_index_list(
        self,
        market: Optional[str] = None,
        force_refresh: bool = False,
    ) -> ProviderResult:
        provider, _ = self._route("index_list")
        return provider.get_index_list(market=market, force_refresh=force_refresh)

    def get_daily_index(
        self,
        index_code: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
        force_refresh: bool = False,
    ) -> ProviderResult:
        provider, _ = self._route("daily_index_series")
        return provider.get_daily_index(
            index_code,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            force_refresh=force_refresh,
        )

    def get_index_summary(
        self,
        board: str,
        index_code: Optional[str] = None,
        trading_date: Optional[str] = None,
    ) -> ProviderResult:
        provider, _ = self._route("index_summary")
        return provider.get_index_summary(
            board,
            index_code=index_code,
            trading_date=trading_date,
        )

    def get_market_summary(
        self,
        scope: str,
        identifier: str,
        *,
        trading_date: Optional[str] = None,
    ) -> ProviderResult:
        provider, _ = self._route("market_summary")
        return provider.get_market_summary(
            scope,
            identifier,
            trading_date=trading_date,
        )

    def get_index_components(
        self,
        index_code: str,
        market: Optional[str] = None,
        force_refresh: bool = False,
    ) -> ProviderResult:
        provider, _ = self._route("index_membership_production")
        return provider.get_index_components(
            index_code,
            market=market,
            force_refresh=force_refresh,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._close_provider:
            self._provider.close()


def create_ssi_rest_provider_router(
    *,
    config: Optional[Any] = None,
    v3_provider: Optional[SsiRestProvider] = None,
) -> SsiRestProviderRouter:
    """Create the sole V3 capability route without another provider."""

    if config is None:
        from src.config import get_config

        config = get_config()
    settings = SsiV3RestSettings.from_config(config)
    validate_v3_selection(settings)
    uses_shared_provider = v3_provider is None
    if uses_shared_provider:
        v3_provider = _get_shared_v3_adapter(settings)
    return SsiRestProviderRouter(
        v3_provider,
        close_provider=not uses_shared_provider,
    )
