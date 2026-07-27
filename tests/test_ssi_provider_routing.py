"""V3-only SSI provider routing contract."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from data_provider.ssi_provider_router import (
    SsiRestProviderRouter,
    V3_PRODUCT_CAPABILITIES,
    create_ssi_rest_provider_router,
)


class RecordingProvider:
    def __init__(self) -> None:
        self.calls = []
        self.close_calls = 0
        self.result = {"status": "ok", "rows": [], "fallback_used": False}

    def __getattr__(self, name):
        if not name.startswith("get_"):
            raise AttributeError(name)

        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return self.result

        return call

    def close(self) -> None:
        self.close_calls += 1


def test_router_has_one_v3_owner_and_no_fallback_state() -> None:
    provider = RecordingProvider()
    router = SsiRestProviderRouter(provider)

    assert router.provider is provider
    assert router.v3_provider is provider
    assert router.selected_version == "v3"
    assert router.routing_diagnostics() == {
        "capability": None,
        "requested_rest_version": "v3",
        "selected_provider": "ssi_fastconnect_v3",
        "selected_version": "v3",
        "routing_reason": "sole_v3_provider",
        "fallback_used": False,
    }
    diagnostics = router.routing_diagnostics("daily_ohlcv")
    assert diagnostics["routing_reason"] == "sole_v3_product_capability"
    assert diagnostics["fallback_used"] is False
    assert "v2_pinned" not in diagnostics


def test_router_delegates_retained_capabilities_without_transforming_results() -> None:
    provider = RecordingProvider()
    router = SsiRestProviderRouter(provider)

    calls = [
        (lambda: router.get_securities("HOSE"), "get_securities", (), {"market": "HOSE"}),
        (
            lambda: router.get_security_metadata("FPT", "HOSE"),
            "get_security_metadata",
            (),
            {"symbol": "FPT", "market": "HOSE"},
        ),
        (lambda: router.get_security_basic_info("FPT"), "get_security_basic_info", ("FPT",), {}),
        (lambda: router.get_securities_by_index("VN30"), "get_securities_by_index", ("VN30",), {}),
        (
            lambda: router.get_daily_ohlcv("FPT", "2026-07-01", "2026-07-22", 20, True),
            "get_daily_ohlcv",
            ("FPT",),
            {
                "from_date": "2026-07-01",
                "to_date": "2026-07-22",
                "limit": 20,
                "force_refresh": True,
            },
        ),
        (
            lambda: router.get_intraday_ohlcv("FPT", limit=10, interval="1m"),
            "get_intraday_ohlcv",
            ("FPT",),
            {"from_date": None, "to_date": None, "limit": 10, "interval": "1m"},
        ),
        (
            lambda: router.get_completed_intraday_1m("FPT", "2026-07-22"),
            "get_completed_intraday_1m",
            ("FPT", "2026-07-22"),
            {},
        ),
        (
            lambda: router.get_daily_stock_price("FPT", market="HOSE", limit=20),
            "get_daily_stock_price",
            ("FPT",),
            {"market": "HOSE", "from_date": None, "to_date": None, "limit": 20},
        ),
        (
            lambda: router.get_index_list("HOSE", True),
            "get_index_list",
            (),
            {"market": "HOSE", "force_refresh": True},
        ),
        (
            lambda: router.get_daily_index("VNINDEX", limit=20),
            "get_daily_index",
            ("VNINDEX",),
            {"from_date": None, "to_date": None, "limit": 20, "force_refresh": False},
        ),
        (
            lambda: router.get_index_summary("HOSE", "VNINDEX"),
            "get_index_summary",
            ("HOSE",),
            {"index_code": "VNINDEX", "trading_date": None},
        ),
        (
            lambda: router.get_index_components("VN30", "HOSE", True),
            "get_index_components",
            ("VN30",),
            {"market": "HOSE", "force_refresh": True},
        ),
    ]

    for invoke, expected_name, expected_args, expected_kwargs in calls:
        assert invoke() is provider.result
        assert provider.calls[-1] == (expected_name, expected_args, expected_kwargs)


def test_router_rejects_capability_outside_retained_v3_contract() -> None:
    router = SsiRestProviderRouter(RecordingProvider())
    with pytest.raises(ValueError, match="outside the V3 product contract"):
        router.routing_diagnostics("trading_account")
    assert "trading_account" not in V3_PRODUCT_CAPABILITIES


def test_router_propagates_v3_failure_and_closes_once() -> None:
    provider = RecordingProvider()
    provider.result = {
        "status": "unavailable",
        "failure_class": "network_error",
        "rows": [],
    }
    router = SsiRestProviderRouter(provider)

    assert router.get_daily_ohlcv("FPT") is provider.result
    router.close()
    router.close()
    assert provider.close_calls == 1


def test_factory_constructs_only_shared_v3_provider(monkeypatch) -> None:
    provider = RecordingProvider()
    settings = SimpleNamespace()
    monkeypatch.setattr(
        "data_provider.ssi_provider_router.SsiV3RestSettings.from_config",
        lambda config: settings,
    )
    validate = Mock()
    monkeypatch.setattr("data_provider.ssi_provider_router.validate_v3_selection", validate)
    shared = Mock(return_value=provider)
    monkeypatch.setattr("data_provider.ssi_provider_router._get_shared_v3_adapter", shared)
    config = object()

    router = create_ssi_rest_provider_router(config=config)

    validate.assert_called_once_with(settings)
    shared.assert_called_once_with(settings)
    assert router.provider is provider
    router.close()
    assert provider.close_calls == 0


def test_factory_injected_provider_retains_owned_close_behavior(monkeypatch) -> None:
    provider = RecordingProvider()
    settings = SimpleNamespace()
    monkeypatch.setattr(
        "data_provider.ssi_provider_router.SsiV3RestSettings.from_config",
        lambda config: settings,
    )
    monkeypatch.setattr(
        "data_provider.ssi_provider_router.validate_v3_selection",
        lambda value: None,
    )

    router = create_ssi_rest_provider_router(
        config=object(),
        v3_provider=provider,
    )
    router.close()

    assert provider.close_calls == 1
