"""Thin provider-neutral adapter over the production FastConnect V2 fetcher."""

from __future__ import annotations

from typing import Any, Optional

from data_provider.ssi_provider_models import ProviderDiagnostics, ProviderResult


class SsiFastConnectV2Adapter:
    """Delegate current REST capabilities without remapping or extra caching."""

    def __init__(self, fetcher: Any) -> None:
        self._fetcher = fetcher
        self._closed = False

    @property
    def fetcher(self) -> Any:
        return self._fetcher

    def get_securities(self, market: Optional[str] = None) -> ProviderResult:
        return self._fetcher.get_securities(market=market)

    def get_security_metadata(
        self,
        symbol: Optional[str] = None,
        market: Optional[str] = None,
    ) -> ProviderResult:
        return self._fetcher.get_securities_details(symbol=symbol, market=market)

    def get_security_basic_info(self, symbol: str) -> ProviderResult:
        return self._fetcher.get_securities_details(symbol=symbol, market=None)

    def get_securities_by_index(self, index_code: str) -> ProviderResult:
        return {
            "status": "unavailable",
            "source": "SSI",
            "reason": "V2 securities-by-index normalization is not exposed by this adapter.",
            "failure_class": "unsupported_capability",
            "rows": [],
            "count": 0,
        }

    def get_daily_ohlcv(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
        force_refresh: bool = False,
    ) -> ProviderResult:
        kwargs = {"limit": limit}
        if from_date is not None:
            kwargs["from_date"] = from_date
        if to_date is not None:
            kwargs["to_date"] = to_date
        if force_refresh:
            kwargs["force_refresh"] = True
        return self._fetcher.get_daily_ohlcv(symbol, **kwargs)

    def get_intraday_ohlcv(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 64,
        interval: Optional[str] = None,
    ) -> ProviderResult:
        kwargs = {"limit": limit}
        if from_date is not None:
            kwargs["from_date"] = from_date
        if to_date is not None:
            kwargs["to_date"] = to_date
        if interval is not None:
            kwargs["interval"] = interval
        return self._fetcher.get_intraday_ohlcv(symbol, **kwargs)

    def get_completed_intraday_1m(self, symbol: str, trading_date: str) -> ProviderResult:
        return self._fetcher.get_completed_intraday_1m(symbol, trading_date)

    def get_daily_stock_price(
        self,
        symbol: str,
        market: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
    ) -> ProviderResult:
        kwargs = {"limit": limit}
        if market is not None:
            kwargs["market"] = market
        if from_date is not None:
            kwargs["from_date"] = from_date
        if to_date is not None:
            kwargs["to_date"] = to_date
        return self._fetcher.get_daily_stock_price(symbol, **kwargs)

    def get_index_list(
        self,
        market: Optional[str] = None,
        force_refresh: bool = False,
    ) -> ProviderResult:
        kwargs = {"market": market}
        if force_refresh:
            kwargs["force_refresh"] = True
        return self._fetcher.get_index_list(**kwargs)

    def get_daily_index(
        self,
        index_code: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
        force_refresh: bool = False,
    ) -> ProviderResult:
        kwargs = {"limit": limit}
        if from_date is not None:
            kwargs["from_date"] = from_date
        if to_date is not None:
            kwargs["to_date"] = to_date
        if force_refresh:
            kwargs["force_refresh"] = True
        return self._fetcher.get_daily_index(index_code, **kwargs)

    def get_index_summary(
        self,
        board: str,
        index_code: Optional[str] = None,
        trading_date: Optional[str] = None,
    ) -> ProviderResult:
        return {
            "status": "unavailable",
            "source": "SSI",
            "reason": "V2 index summary requires the existing DailyIndex route.",
            "failure_class": "unsupported_capability",
            "rows": [],
            "count": 0,
        }

    def get_index_components(
        self,
        index_code: str,
        market: Optional[str] = None,
        force_refresh: bool = False,
    ) -> ProviderResult:
        kwargs = {"market": market}
        if force_refresh:
            kwargs["force_refresh"] = True
        return self._fetcher.get_index_components(index_code, **kwargs)

    def routing_diagnostics(self, capability: Optional[str] = None) -> ProviderDiagnostics:
        return {
            "capability": capability,
            "requested_rest_version": "v2",
            "selected_provider": "ssi_fastconnect",
            "selected_version": "v2",
            "routing_reason": "delegating_v2_adapter",
            "v2_pinned": False,
            "fallback_used": False,
        }

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close = getattr(self._fetcher, "close", None)
        if callable(close):
            close()
