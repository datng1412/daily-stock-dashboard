"""Offline contract, routing, delegation, and parity tests for SSI-V3-B1."""

from __future__ import annotations

import importlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import pytest

from data_provider.ssi_provider_protocol import SsiRestProvider
from data_provider.ssi_provider_router import (
    SsiRestProviderRouter,
    create_ssi_rest_provider_router,
)
from data_provider.ssi_v2_adapter import SsiFastConnectV2Adapter
from src.config import parse_ssi_fastconnect_rest_version
from src.services import vietnam_foreign_flow_service as foreign_flow_module
from src.services.vietnam_market_service import VietnamDashboardConfig, VietnamMarketService


class RecordingV2Fetcher:
    def __init__(self, result: Optional[Dict[str, Any]] = None) -> None:
        self.result = result or {
            "status": "ok",
            "source": "SSI",
            "rows": [{"date": "2026-07-21", "close": 0.0, "volume": None, "source": "SSI"}],
            "count": 1,
        }
        self.calls: List[Tuple[str, Tuple[Any, ...], Dict[str, Any]]] = []
        self.close_calls = 0
        self.error: Optional[BaseException] = None

    def _record(self, name: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        self.calls.append((name, args, kwargs))
        if self.error is not None:
            raise self.error
        return self.result

    def get_securities(self, market: Optional[str] = None) -> Dict[str, Any]:
        return self._record("get_securities", market=market)

    def get_securities_details(
        self,
        symbol: Optional[str] = None,
        market: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._record("get_securities_details", symbol=symbol, market=market)

    def get_daily_ohlcv(self, symbol: str, **kwargs: Any) -> Dict[str, Any]:
        return self._record("get_daily_ohlcv", symbol, **kwargs)

    def get_intraday_ohlcv(self, symbol: str, **kwargs: Any) -> Dict[str, Any]:
        return self._record("get_intraday_ohlcv", symbol, **kwargs)

    def get_completed_intraday_1m(self, symbol: str, trading_date: str) -> Dict[str, Any]:
        return self._record("get_completed_intraday_1m", symbol, trading_date)

    def get_daily_stock_price(self, symbol: str, **kwargs: Any) -> Dict[str, Any]:
        return self._record("get_daily_stock_price", symbol, **kwargs)

    def get_index_list(self, **kwargs: Any) -> Dict[str, Any]:
        return self._record("get_index_list", **kwargs)

    def get_daily_index(self, index_code: str, **kwargs: Any) -> Dict[str, Any]:
        return self._record("get_daily_index", index_code, **kwargs)

    def get_index_components(self, index_code: str, **kwargs: Any) -> Dict[str, Any]:
        return self._record("get_index_components", index_code, **kwargs)

    def get_realtime_snapshot(self, symbols: List[str]) -> Dict[str, Any]:
        return self._record("get_realtime_snapshot", symbols)

    def close(self) -> None:
        self.close_calls += 1


@pytest.mark.parametrize("value", [None, "", "  ", "v2", "V2", " v2 "])
def test_selector_defaults_or_normalizes_to_v2(value: Optional[str]) -> None:
    assert parse_ssi_fastconnect_rest_version(value) == "v2"


def test_selector_accepts_explicit_v3_for_the_disabled_b2_adapter() -> None:
    assert parse_ssi_fastconnect_rest_version("v3") == "v3"
    assert parse_ssi_fastconnect_rest_version(" V3 ") == "v3"


@pytest.mark.parametrize("value", ["v1", "future", "ssi"])
def test_selector_rejects_unknown_values(value: str) -> None:
    with pytest.raises(ValueError, match="SSI_FASTCONNECT_REST_VERSION=.*unsupported"):
        parse_ssi_fastconnect_rest_version(value)


def test_router_defaults_to_v2_and_exposes_no_fallback_diagnostics() -> None:
    fetcher = RecordingV2Fetcher()
    router = create_ssi_rest_provider_router(version="", v2_fetcher=fetcher)

    assert router.selected_version == "v2"
    assert router.routing_diagnostics("daily_ohlcv") == {
        "capability": "daily_ohlcv",
        "requested_rest_version": "v2",
        "selected_provider": "ssi_fastconnect_v2",
        "selected_version": "v2",
        "routing_reason": "configured_v2",
        "v2_pinned": False,
        "fallback_used": False,
    }


def test_v2_runtime_error_propagates_without_another_provider_call() -> None:
    fetcher = RecordingV2Fetcher()
    failure = RuntimeError("existing-v2-failure")
    fetcher.error = failure
    router = create_ssi_rest_provider_router(version="v2", v2_fetcher=fetcher)

    with pytest.raises(RuntimeError) as exc_info:
        router.get_daily_ohlcv("FPT")

    assert exc_info.value is failure
    assert [call[0] for call in fetcher.calls] == ["get_daily_ohlcv"]
    assert router.routing_diagnostics("daily_ohlcv")["fallback_used"] is False


def test_adapter_delegates_every_capability_with_exact_arguments_and_identity() -> None:
    fetcher = RecordingV2Fetcher()
    adapter = SsiFastConnectV2Adapter(fetcher)

    calls = [
        (adapter.get_securities("HOSE"), ("get_securities", (), {"market": "HOSE"})),
        (
            adapter.get_security_metadata("FPT", "HOSE"),
            ("get_securities_details", (), {"symbol": "FPT", "market": "HOSE"}),
        ),
        (
            adapter.get_daily_ohlcv("FPT", "2026-01-01", "2026-02-01", 10, True),
            (
                "get_daily_ohlcv",
                ("FPT",),
                {
                    "from_date": "2026-01-01",
                    "to_date": "2026-02-01",
                    "limit": 10,
                    "force_refresh": True,
                },
            ),
        ),
        (
            adapter.get_intraday_ohlcv("FPT", "2026-07-20", "2026-07-21", 64, "1"),
            (
                "get_intraday_ohlcv",
                ("FPT",),
                {
                    "from_date": "2026-07-20",
                    "to_date": "2026-07-21",
                    "limit": 64,
                    "interval": "1",
                },
            ),
        ),
        (
            adapter.get_completed_intraday_1m("FPT", "2026-07-21"),
            ("get_completed_intraday_1m", ("FPT", "2026-07-21"), {}),
        ),
        (
            adapter.get_daily_stock_price("FPT", "HOSE", "2026-01-01", "2026-02-01", 120),
            (
                "get_daily_stock_price",
                ("FPT",),
                {
                    "market": "HOSE",
                    "from_date": "2026-01-01",
                    "to_date": "2026-02-01",
                    "limit": 120,
                },
            ),
        ),
        (
            adapter.get_index_list("HOSE", True),
            ("get_index_list", (), {"market": "HOSE", "force_refresh": True}),
        ),
        (
            adapter.get_daily_index("VN30", "2026-01-01", "2026-02-01", 30, True),
            (
                "get_daily_index",
                ("VN30",),
                {
                    "from_date": "2026-01-01",
                    "to_date": "2026-02-01",
                    "limit": 30,
                    "force_refresh": True,
                },
            ),
        ),
        (
            adapter.get_index_components("VN30", "HOSE", True),
            (
                "get_index_components",
                ("VN30",),
                {"market": "HOSE", "force_refresh": True},
            ),
        ),
    ]

    assert all(result is fetcher.result for result, _ in calls)
    assert fetcher.calls == [expected for _, expected in calls]


def test_adapter_and_router_reuse_one_fetcher_and_close_once() -> None:
    fetcher = RecordingV2Fetcher()
    adapter = SsiFastConnectV2Adapter(fetcher)
    router = SsiRestProviderRouter(adapter)

    assert isinstance(adapter, SsiRestProvider)
    assert isinstance(router, SsiRestProvider)
    assert adapter.fetcher is fetcher
    router.get_securities("HOSE")
    router.get_index_list("HOSE")
    router.close()
    router.close()

    assert [call[0] for call in fetcher.calls] == ["get_securities", "get_index_list"]
    assert fetcher.close_calls == 1


def test_missing_zero_empty_and_source_metadata_are_returned_unchanged() -> None:
    payload = {
        "status": "ok",
        "source": "SSI",
        "rows": [
            {
                "date": "2026-07-21",
                "foreign_buy_value": None,
                "foreign_sell_value": 0.0,
                "foreign_buy_volume": None,
                "foreign_sell_volume": 0,
                "source": "SSI",
            }
        ],
        "optional_rows": [],
        "cached": True,
    }
    fetcher = RecordingV2Fetcher(payload)
    router = create_ssi_rest_provider_router(version="v2", v2_fetcher=fetcher)

    result = router.get_daily_stock_price("FPT")

    assert result is payload
    assert result["rows"][0]["foreign_buy_value"] is None
    assert result["rows"][0]["foreign_sell_value"] == 0.0
    assert result["rows"][0]["foreign_buy_volume"] is None
    assert result["rows"][0]["foreign_sell_volume"] == 0
    assert result["optional_rows"] == []
    assert result["source"] == "SSI"


def test_market_service_rest_router_reuses_injected_fetcher_and_stream_path() -> None:
    fetcher = RecordingV2Fetcher()
    service = VietnamMarketService(
        config=VietnamDashboardConfig(ssi_fastconnect_rest_version="v2"),
        ssi_fetcher=fetcher,  # type: ignore[arg-type]
    )

    first = service._get_ssi_rest_provider()
    second = service._get_ssi_rest_provider()

    assert first is second
    assert first.provider.fetcher is fetcher  # type: ignore[attr-defined]
    assert service._get_ssi_fetcher() is fetcher
    service._load_ssi_daily_ohlcv("FPT", 1)
    fetcher.get_realtime_snapshot(["FPT"])
    assert [call[0] for call in fetcher.calls] == ["get_daily_ohlcv", "get_realtime_snapshot"]


def test_foreign_flow_service_creates_one_router_under_concurrent_first_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetcher = RecordingV2Fetcher()
    router = create_ssi_rest_provider_router(version="v2", v2_fetcher=fetcher)
    create_calls = 0

    def create_router(**kwargs: Any) -> SsiRestProviderRouter:
        nonlocal create_calls
        create_calls += 1
        time.sleep(0.02)
        return router

    monkeypatch.setattr(foreign_flow_module, "create_ssi_rest_provider_router", create_router)
    service = foreign_flow_module.VietnamForeignFlowService()

    with ThreadPoolExecutor(max_workers=4) as executor:
        providers = list(executor.map(lambda _: service._get_rest_provider(), range(8)))

    assert create_calls == 1
    assert all(provider is router for provider in providers)


def test_provider_module_imports_do_not_start_threads_or_make_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    def fail_request(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("provider module import attempted network I/O")

    def fail_thread_start(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("provider module import started a thread")

    monkeypatch.setattr(requests.sessions.Session, "request", fail_request)
    monkeypatch.setattr(threading.Thread, "start", fail_thread_start)
    for module_name in (
        "data_provider.ssi_provider_models",
        "data_provider.ssi_provider_protocol",
        "data_provider.ssi_v2_adapter",
        "data_provider.ssi_provider_router",
    ):
        importlib.reload(importlib.import_module(module_name))


def test_v2_and_streaming_modules_do_not_import_v3_sdk_or_credentials() -> None:
    root = Path(__file__).resolve().parents[1]
    production_files = (
        root / "data_provider" / "ssi_provider_models.py",
        root / "data_provider" / "ssi_provider_protocol.py",
        root / "data_provider" / "ssi_v2_adapter.py",
        root / "data_provider" / "ssi_streaming_realtime.py",
        root / "src" / "services" / "ssi_streaming_realtime_lifecycle.py",
    )
    forbidden = ("ssi_sdk", "ssi-sdk", "/api/v3", "SSI_V3_CLIENT_ID", "SSI_V3_API_KEY", "SSI_V3_API_SECRET")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in production_files)

    assert not any(token in combined for token in forbidden)
