"""Explicit capability routing for SSI FastConnect V2 and gated V3 REST."""

from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import Any, Optional, Tuple
from zoneinfo import ZoneInfo

from data_provider.ssi_provider_models import ProviderDiagnostics, ProviderResult
from data_provider.ssi_provider_protocol import SsiRestProvider
from data_provider.ssi_v2_adapter import SsiFastConnectV2Adapter
from data_provider.ssi_v3_adapter import (
    SsiFastConnectV3Adapter,
    SsiV3RestSettings,
    validate_v3_selection,
)
from src.config import parse_ssi_fastconnect_rest_version


V3_SUPPORTED_B2 = frozenset(
    {
        "securities_by_board",
        "security_basic_info",
        "securities_by_index_normalization",
        "daily_ohlcv",
        "completed_historical_intraday_ohlcv",
        "index_list",
        "index_summary",
    }
)

V3_IMPLEMENTED_DISABLED_B3 = frozenset(
    {
        "daily_security_summary",
        "foreign_flow",
        "foreign_flow_history",
        "foreign_flow_analytics_input",
        "vn30_foreign_flow_input",
    }
)

V2_PINNED = frozenset(
    {
        "security_extended_metadata",
        "current_session_intraday",
        "daily_security_summary",
        "foreign_flow",
        "foreign_flow_history",
        "foreign_flow_analytics_input",
        "vn30_foreign_flow_input",
        "daily_index_series",
        "index_membership_production",
        "realtime",
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
    """Route each capability to its explicit owner; never perform fallback."""

    def __init__(
        self,
        provider: SsiRestProvider,
        *,
        selected_version: str = "v2",
        v3_provider: Optional[SsiRestProvider] = None,
    ) -> None:
        self._selected_version = parse_ssi_fastconnect_rest_version(selected_version)
        self._v2_provider = provider
        self._v3_provider = v3_provider
        if self._selected_version == "v3" and self._v3_provider is None:
            raise ValueError("SSI V3 provider is required when REST version v3 is selected")
        self._closed = False

    @property
    def selected_version(self) -> str:
        return self._selected_version

    @property
    def provider(self) -> SsiRestProvider:
        """Compatibility alias for the production V2 adapter/fetcher owner."""
        return self._v2_provider

    @property
    def v2_provider(self) -> SsiRestProvider:
        return self._v2_provider

    @property
    def v3_provider(self) -> Optional[SsiRestProvider]:
        return self._v3_provider

    def _route(self, capability: str) -> Tuple[SsiRestProvider, bool, str]:
        if self._selected_version == "v3" and capability in V3_SUPPORTED_B2:
            assert self._v3_provider is not None
            return self._v3_provider, False, "explicit_v3_b2_capability"
        if capability in V2_PINNED:
            reason = (
                "v3_implemented_disabled_v2_production_owner"
                if capability in V3_IMPLEMENTED_DISABLED_B3
                else "explicit_v2_capability_pin"
            )
            return self._v2_provider, self._selected_version == "v3", reason
        if self._selected_version == "v2":
            return self._v2_provider, False, "configured_v2"
        raise ValueError(f"SSI REST capability {capability!r} is unsupported for V3 phase B3")

    def routing_diagnostics(self, capability: Optional[str] = None) -> ProviderDiagnostics:
        if capability is None:
            selected_version = self._selected_version
            return {
                "capability": None,
                "requested_rest_version": self._selected_version,
                "selected_provider": f"ssi_fastconnect_{selected_version}",
                "selected_version": selected_version,
                "routing_reason": f"configured_{selected_version}",
                "v2_pinned": False,
                "fallback_used": False,
            }
        normalized = capability or "unspecified"
        provider, v2_pinned, reason = self._route(normalized)
        selected_version = "v2" if provider is self._v2_provider else "v3"
        diagnostics: ProviderDiagnostics = {
            "capability": capability,
            "requested_rest_version": self._selected_version,
            "selected_provider": (
                "ssi_fastconnect_v2" if selected_version == "v2" else "ssi_fastconnect_v3"
            ),
            "selected_version": selected_version,
            "routing_reason": reason,
            "v2_pinned": v2_pinned,
            "fallback_used": False,
        }
        if normalized in V3_IMPLEMENTED_DISABLED_B3:
            diagnostics.update(
                {
                    "implementation_status": "implemented_disabled",
                    "production_owner": "ssi_fastconnect_v2",
                    "v3_implementation_available": True,
                }
            )
        return diagnostics

    def get_securities(self, market: Optional[str] = None) -> ProviderResult:
        provider, _, _ = self._route("securities_by_board")
        return provider.get_securities(market=market)

    def get_security_metadata(
        self,
        symbol: Optional[str] = None,
        market: Optional[str] = None,
    ) -> ProviderResult:
        provider, _, _ = self._route("security_extended_metadata")
        return provider.get_security_metadata(symbol=symbol, market=market)

    def get_security_basic_info(self, symbol: str) -> ProviderResult:
        provider, _, _ = self._route("security_basic_info")
        return provider.get_security_basic_info(symbol)

    def get_securities_by_index(self, index_code: str) -> ProviderResult:
        provider, _, _ = self._route("securities_by_index_normalization")
        return provider.get_securities_by_index(index_code)

    def get_daily_ohlcv(
        self,
        symbol: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
        force_refresh: bool = False,
    ) -> ProviderResult:
        provider, _, _ = self._route("daily_ohlcv")
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
        provider, _, _ = self._route("current_session_intraday")
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
        provider, _, _ = self._route(capability)
        return provider.get_completed_intraday_1m(symbol, trading_date)

    def get_daily_stock_price(
        self,
        symbol: str,
        market: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
    ) -> ProviderResult:
        provider, _, _ = self._route("daily_security_summary")
        return provider.get_daily_stock_price(
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
        provider, _, _ = self._route("index_list")
        return provider.get_index_list(market=market, force_refresh=force_refresh)

    def get_daily_index(
        self,
        index_code: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
        force_refresh: bool = False,
    ) -> ProviderResult:
        provider, _, _ = self._route("daily_index_series")
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
        provider, _, _ = self._route("index_summary")
        return provider.get_index_summary(
            board,
            index_code=index_code,
            trading_date=trading_date,
        )

    def get_index_components(
        self,
        index_code: str,
        market: Optional[str] = None,
        force_refresh: bool = False,
    ) -> ProviderResult:
        provider, _, _ = self._route("index_membership_production")
        return provider.get_index_components(
            index_code,
            market=market,
            force_refresh=force_refresh,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._v2_provider.close()
        if self._v3_provider is not None and self._v3_provider is not self._v2_provider:
            self._v3_provider.close()


def create_ssi_rest_provider_router(
    *,
    version: Optional[str] = None,
    v2_fetcher: Optional[Any] = None,
    config: Optional[Any] = None,
    v3_provider: Optional[SsiRestProvider] = None,
) -> SsiRestProviderRouter:
    """Create explicit V2/V3 capability routes without automatic fallback."""

    configured_version = version
    if configured_version is None and config is None and v2_fetcher is not None:
        configured_version = "v2"
    if configured_version is None and config is None:
        from src.config import get_config

        config = get_config()
    if configured_version is None and config is not None:
        configured_version = getattr(config, "ssi_fastconnect_rest_version", None)
    selected_version = parse_ssi_fastconnect_rest_version(configured_version)

    if selected_version == "v3":
        if config is None:
            from src.config import get_config

            config = get_config()
        settings = SsiV3RestSettings.from_config(config)
        validate_v3_selection(settings)
        if v3_provider is None:
            v3_provider = _get_shared_v3_adapter(settings)

    if v2_fetcher is None:
        from data_provider.ssi_fastconnect_fetcher import SsiFastConnectFetcher

        v2_fetcher = SsiFastConnectFetcher(config=config)
    v2_adapter = SsiFastConnectV2Adapter(v2_fetcher)
    return SsiRestProviderRouter(
        v2_adapter,
        selected_version=selected_version,
        v3_provider=v3_provider,
    )
