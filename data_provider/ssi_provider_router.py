"""Explicit SSI REST provider selection with V2 as the only B1 route."""

from __future__ import annotations

from typing import Any, Optional

from data_provider.ssi_provider_models import ProviderDiagnostics, ProviderResult
from data_provider.ssi_provider_protocol import SsiRestProvider
from data_provider.ssi_v2_adapter import SsiFastConnectV2Adapter
from src.config import parse_ssi_fastconnect_rest_version


class SsiRestProviderRouter:
    """Route each REST capability to one explicitly selected provider.

    B1 registers only V2.  Runtime failures propagate unchanged; there is no
    alternate-provider branch and therefore no automatic fallback.
    """

    def __init__(self, provider: SsiRestProvider, *, selected_version: str = "v2") -> None:
        self._selected_version = parse_ssi_fastconnect_rest_version(selected_version)
        self._provider = provider
        self._closed = False

    @property
    def selected_version(self) -> str:
        return self._selected_version

    @property
    def provider(self) -> SsiRestProvider:
        return self._provider

    def routing_diagnostics(self, capability: Optional[str] = None) -> ProviderDiagnostics:
        return {
            "capability": capability,
            "selected_provider": "ssi_fastconnect",
            "selected_version": self._selected_version,
            "routing_reason": "configured_v2" if self._selected_version == "v2" else "configured",
            "fallback_used": False,
        }

    def get_securities(self, market: Optional[str] = None) -> ProviderResult:
        return self._provider.get_securities(market=market)

    def get_security_metadata(
        self,
        symbol: Optional[str] = None,
        market: Optional[str] = None,
    ) -> ProviderResult:
        return self._provider.get_security_metadata(symbol=symbol, market=market)

    def get_daily_ohlcv(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
        force_refresh: bool = False,
    ) -> ProviderResult:
        return self._provider.get_daily_ohlcv(
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
        return self._provider.get_intraday_ohlcv(
            symbol,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            interval=interval,
        )

    def get_completed_intraday_1m(self, symbol: str, trading_date: str) -> ProviderResult:
        return self._provider.get_completed_intraday_1m(symbol, trading_date)

    def get_daily_stock_price(
        self,
        symbol: str,
        market: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
    ) -> ProviderResult:
        return self._provider.get_daily_stock_price(
            symbol,
            market=market,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )

    def get_index_list(
        self,
        market: Optional[str] = None,
        force_refresh: bool = False,
    ) -> ProviderResult:
        return self._provider.get_index_list(market=market, force_refresh=force_refresh)

    def get_daily_index(
        self,
        index_code: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
        force_refresh: bool = False,
    ) -> ProviderResult:
        return self._provider.get_daily_index(
            index_code,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            force_refresh=force_refresh,
        )

    def get_index_components(
        self,
        index_code: str,
        market: Optional[str] = None,
        force_refresh: bool = False,
    ) -> ProviderResult:
        return self._provider.get_index_components(
            index_code,
            market=market,
            force_refresh=force_refresh,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._provider.close()


def create_ssi_rest_provider_router(
    *,
    version: Optional[str] = None,
    v2_fetcher: Optional[Any] = None,
    config: Optional[Any] = None,
) -> SsiRestProviderRouter:
    """Create the one selected B1 provider without attempting a fallback."""

    configured_version = version
    if configured_version is None and config is None and v2_fetcher is not None:
        # An explicitly injected V2 fetcher is already an explicit route.  This
        # keeps deterministic tests and callers independent from global env.
        configured_version = "v2"
    if configured_version is None and config is None:
        from src.config import get_config

        config = get_config()
    if configured_version is None and config is not None:
        configured_version = getattr(config, "ssi_fastconnect_rest_version", None)
    selected_version = parse_ssi_fastconnect_rest_version(configured_version)

    if v2_fetcher is None:
        from data_provider.ssi_fastconnect_fetcher import SsiFastConnectFetcher

        v2_fetcher = SsiFastConnectFetcher(config=config)
    adapter = SsiFastConnectV2Adapter(v2_fetcher)
    return SsiRestProviderRouter(adapter, selected_version=selected_version)
