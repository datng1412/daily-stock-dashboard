"""Structural contract for StockClock's current SSI REST capabilities."""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from data_provider.ssi_provider_models import ProviderDiagnostics, ProviderResult


@runtime_checkable
class SsiRestProvider(Protocol):
    """Provider-neutral REST surface used by current Vietnam services.

    Streaming and trading capabilities are intentionally excluded.  Method
    signatures remain synchronous because current services call the V2 REST
    fetcher synchronously (or place those calls in their existing executors).
    """

    def get_securities(self, market: Optional[str] = None) -> ProviderResult: ...

    def get_security_metadata(
        self,
        symbol: Optional[str] = None,
        market: Optional[str] = None,
    ) -> ProviderResult: ...

    def get_security_basic_info(self, symbol: str) -> ProviderResult: ...

    def get_securities_by_index(self, index_code: str) -> ProviderResult: ...

    def get_daily_ohlcv(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
        force_refresh: bool = False,
    ) -> ProviderResult: ...

    def get_intraday_ohlcv(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 64,
        interval: Optional[str] = None,
    ) -> ProviderResult: ...

    def get_completed_intraday_1m(self, symbol: str, trading_date: str) -> ProviderResult: ...

    def get_daily_stock_price(
        self,
        symbol: str,
        market: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
    ) -> ProviderResult: ...

    def get_index_list(
        self,
        market: Optional[str] = None,
        force_refresh: bool = False,
    ) -> ProviderResult: ...

    def get_daily_index(
        self,
        index_code: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
        force_refresh: bool = False,
    ) -> ProviderResult: ...

    def get_index_summary(
        self,
        board: str,
        index_code: Optional[str] = None,
        trading_date: Optional[str] = None,
    ) -> ProviderResult: ...

    def get_index_components(
        self,
        index_code: str,
        market: Optional[str] = None,
        force_refresh: bool = False,
    ) -> ProviderResult: ...

    def routing_diagnostics(self, capability: Optional[str] = None) -> ProviderDiagnostics: ...

    def close(self) -> None: ...
