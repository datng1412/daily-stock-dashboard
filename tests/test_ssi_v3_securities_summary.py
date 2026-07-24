"""Offline SSI-V3-B3 securities-summary and foreign-flow contract tests."""

from __future__ import annotations

from importlib import metadata
import inspect
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from data_provider.ssi_provider_router import SsiRestProviderRouter
from data_provider.ssi_v3_adapter import (
    SSI_V3_MAX_PAGES,
    SSI_V3_MAX_ROWS,
    SSI_V3_PAGE_SIZE,
    SSI_V3_SECURITIES_SUMMARY_PATH,
    SSI_V3_SOURCE,
    SsiFastConnectV3Adapter,
    SsiV3RestSettings,
)


class FakeRestClient:
    def __init__(self) -> None:
        self.calls: List[Any] = []
        self.payload: Any = {"data": [], "pagesCount": 0}
        self.pages: Dict[int, Any] = {}
        self.error: Optional[BaseException] = None

    def get(self, path: str, **kwargs: Any) -> Any:
        self.calls.append((path, kwargs))
        if self.error is not None:
            raise self.error
        page = kwargs.get("params", {}).get("pageIndex", 1)
        return self.pages.get(page, self.payload)


class FakeAuth:
    def __init__(self) -> None:
        self.rest_client = FakeRestClient()
        self.authenticate_calls = 0
        self.close_calls = 0

    def authenticate(self) -> object:
        self.authenticate_calls += 1
        return object()

    def close(self) -> None:
        self.close_calls += 1


class FakeData:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


def make_adapter() -> tuple[SsiFastConnectV3Adapter, FakeAuth, FakeData]:
    auth = FakeAuth()
    data = FakeData()
    settings = SsiV3RestSettings(
        enabled=True,
        client_id="<client-id>",
        api_key="<api-key>",
        api_secret="<api-secret>",
    )
    return (
        SsiFastConnectV3Adapter(
            settings,
            auth_factory=lambda _settings: auth,
            data_factory=lambda _auth: data,
        ),
        auth,
        data,
    )


def summary_row(**overrides: Any) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "symbol": "FPT",
        "tradingDate": "2026/07/21",
        "open": "100.25",
        "high": "102.5",
        "low": "99.75",
        "close": "101.0",
        "totalMatch": "1234",
        "totalMatchValue": "125000.5",
        "totalDeal": "12",
        "totalDealValue": "2400.5",
        "remainForeignRoom": "789",
        "totalForeignRoom": "1000",
        "average": "100.75",
        "priceChange": "1.25",
        "priceChangePercentage": "1.26",
        "totalForeignBuy": "100",
        "totalForeignSell": "40",
        "totalForeignBuyValue": "1000.5",
        "totalForeignSellValue": "400.25",
        # A similarly named provider field must not override gross derivation.
        "foreignNetVolume": "999999",
        "foreignNetValue": "999999",
    }
    row.update(overrides)
    return row


def test_installed_sdk_summary_signatures_and_model_field_gap_are_pinned() -> None:
    from ssi_sdk.models.market_data import SecuritiesSummary
    from ssi_sdk.services.market_data import MarketDataService

    assert metadata.version("ssi-sdk") == "3.0.5"
    assert str(inspect.signature(MarketDataService.get_securities_summary)) == (
        "(self, symbol: 'str') -> 'list[SecuritiesSummary]'"
    )
    assert str(
        inspect.signature(MarketDataService.get_securities_summary_historical)
    ) == (
        "(self, symbol: 'str', from_date: 'str', to_date: 'str') "
        "-> 'list[SecuritiesSummary]'"
    )
    assert str(inspect.signature(MarketDataService.get_securities_summary_by_index)) == (
        "(self, index: 'str') -> 'list[SecuritiesSummary]'"
    )
    assert str(
        inspect.signature(MarketDataService.get_securities_summary_by_index_historical)
    ) == (
        "(self, index: 'str', from_date: 'str', to_date: 'str') "
        "-> 'list[SecuritiesSummary]'"
    )
    assert not {
        "total_foreign_buy",
        "total_foreign_sell",
        "total_foreign_buy_value",
        "total_foreign_sell_value",
    } & set(SecuritiesSummary.__annotations__)


def test_historical_symbol_request_uses_public_rest_transport_and_normalizes() -> None:
    adapter, auth, _data = make_adapter()
    auth.rest_client.payload = {"data": [summary_row()], "pagesCount": 1}

    result = adapter.get_daily_stock_price(
        " fpt ",
        market="HOSE",
        from_date="2026-07-01",
        to_date="2026-07-21",
        limit=2,
    )

    assert auth.authenticate_calls == 1
    assert auth.rest_client.calls == [
        (
            SSI_V3_SECURITIES_SUMMARY_PATH,
            {
                "params": {
                    "from": "2026/07/01",
                    "to": "2026/07/21",
                    "pageIndex": 1,
                    "pageSize": 4,
                    "symbol": "FPT",
                }
            },
        )
    ]
    row = result["rows"][0]
    assert row["symbol"] == "FPT"
    assert row["date"] == "2026-07-21"
    assert row["matched_volume"] == 1234
    assert row["matched_value"] == 125000.5
    assert row["put_through_volume"] == 12
    assert row["put_through_value"] == 2400.5
    assert row["remaining_foreign_room"] == 789
    assert row["total_foreign_room"] == 1000
    assert row["average_price"] == 100.75
    assert row["price_change"] == 1.25
    assert row["price_change_pct"] == 1.26
    assert row["foreign_buy_volume"] == 100
    assert row["foreign_sell_volume"] == 40
    assert row["foreign_net_volume"] == 60
    assert row["foreign_buy_value"] == 1000.5
    assert row["foreign_sell_value"] == 400.25
    assert row["foreign_net_value"] == 600.25
    assert row["source"] == SSI_V3_SOURCE
    assert row["source_version"] == "v3"
    expected_diagnostics = {
        "capability": "daily_stock_price",
        "source_version": "v3",
        "implementation_status": "implemented",
        "units_verified": True,
        "finality_verified": False,
        "operational_finality_policy_validated": True,
        "provider_finality_verified": False,
        "foreign_value_domain": "HOSE_EQUITY_VALUE",
        "foreign_value_scale": 1,
        "foreign_volume_unit": "shares",
        "foreign_value_unit": "VND",
        "foreign_value_scale_confidence": "PROVEN",
        "foreign_finality_policy": "stockclock_completed_session_rank_operational",
        "foreign_provider_finality_guaranteed": False,
        "provisional_row_count": 0,
        "provisional_rows_included": True,
        "finality_contract": "stockclock_completed_session_rank_operational",
    }
    assert expected_diagnostics.items() <= result["diagnostics"].items()
    assert result["diagnostics"]["page_count"] == 1
    assert result["diagnostics"]["min_date"] == "2026-07-21"
    assert result["diagnostics"]["max_date"] == "2026-07-21"


def test_current_symbol_and_index_requests_are_bounded_and_index_is_direct_only() -> None:
    symbol_adapter, symbol_auth, _data = make_adapter()
    symbol_auth.rest_client.payload = {"data": []}
    assert symbol_adapter.get_securities_summary(symbol="fpt")["status"] == "ok"
    assert symbol_adapter.get_securities_summary(symbol="fpt")["status"] == "ok"
    assert symbol_auth.authenticate_calls == 1
    symbol_params = symbol_auth.rest_client.calls[0][1]["params"]
    assert symbol_params["symbol"] == "FPT"
    assert symbol_params["from"] == symbol_params["to"]

    index_adapter, index_auth, _data = make_adapter()
    index_auth.rest_client.payload = {
        "data": [summary_row(symbol="VCB")],
        "pagesCount": 1,
    }
    result = index_adapter.get_securities_summary_by_index(
        "vn30", from_date="2026-07-21", to_date="2026-07-21", limit=10
    )
    params = index_auth.rest_client.calls[0][1]["params"]
    assert params["index"] == "VN30"
    assert "symbol" not in params
    assert result["rows"][0]["symbol"] == "VCB"
    assert result["diagnostics"]["implementation_status"] == "implemented"


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"symbol": ""},
        {"symbol": "FPT", "index": "VN30"},
        {"symbol": "FPT", "from_date": "bad-date"},
        {
            "symbol": "FPT",
            "from_date": "2026-07-22",
            "to_date": "2026-07-21",
        },
        {"symbol": "FPT", "page_index": 0},
        {"symbol": "FPT", "page_index": SSI_V3_MAX_PAGES + 1},
        {"symbol": "FPT", "page_size": 0},
        {"symbol": "FPT", "page_size": SSI_V3_PAGE_SIZE + 1},
        {"symbol": "FPT", "page_size": True},
        {"symbol": "FPT", "limit": 0},
        {"symbol": "FPT", "limit": SSI_V3_MAX_ROWS + 1},
        {"symbol": "FPT", "limit": True},
    ],
)
def test_invalid_summary_input_fails_before_authentication(kwargs: Dict[str, Any]) -> None:
    adapter, auth, _data = make_adapter()
    result = adapter.get_securities_summary(**kwargs)
    assert result["failure_class"] == "validation_error"
    assert auth.authenticate_calls == 0
    assert auth.rest_client.calls == []


def test_missing_and_explicit_zero_stay_distinct_and_net_families_are_independent() -> None:
    adapter, auth, _data = make_adapter()
    auth.rest_client.payload = {
        "data": [
            summary_row(
                tradingDate="2026/07/20",
                totalForeignBuy="0",
                totalForeignSell=0,
                totalForeignBuyValue="0.0",
                totalForeignSellValue=0,
            ),
            summary_row(
                tradingDate="2026/07/21",
                totalForeignBuy=None,
                totalForeignSell="40",
                totalForeignBuyValue="1000",
                totalForeignSellValue=None,
            ),
            summary_row(
                tradingDate="2026/07/22",
                totalForeignBuy="40",
                totalForeignSell="100",
                totalForeignBuyValue="400.25",
                totalForeignSellValue="1000.5",
            ),
        ],
        "pagesCount": 1,
    }

    rows = adapter.get_securities_summary(
        symbol="FPT", from_date="2026-07-20", to_date="2026-07-22", limit=3
    )["rows"]
    zero, missing, negative = rows
    assert (zero["foreign_buy_volume"], zero["foreign_sell_volume"]) == (0, 0)
    assert zero["foreign_net_volume"] == 0
    assert (zero["foreign_buy_value"], zero["foreign_sell_value"]) == (0.0, 0.0)
    assert zero["foreign_net_value"] == 0.0
    assert set(zero["_foreign_field_presence"].values()) == {
        "FIELD_PRESENT_EXPLICIT_ZERO"
    }
    assert missing["foreign_buy_volume"] is None
    assert missing["foreign_sell_volume"] == 40
    assert missing["foreign_net_volume"] is None
    assert missing["foreign_buy_value"] == 1000.0
    assert missing["foreign_sell_value"] is None
    assert missing["foreign_net_value"] is None
    assert missing["_foreign_field_presence"]["foreign_buy_volume"] == "FIELD_NULL"
    assert missing["_foreign_field_presence"]["foreign_sell_value"] == "FIELD_NULL"
    assert negative["foreign_net_volume"] == -60
    assert negative["foreign_net_value"] == -600.25


def test_integral_numeric_strings_do_not_round_through_float() -> None:
    adapter, auth, _data = make_adapter()
    exact = 9_007_199_254_740_993
    auth.rest_client.payload = {
        "data": [
            summary_row(
                totalMatch=str(exact),
                totalForeignBuy=str(exact),
                totalForeignSell="0",
            )
        ]
    }
    row = adapter.get_securities_summary(symbol="FPT", limit=1)["rows"][0]
    assert row["matched_volume"] == exact
    assert row["foreign_buy_volume"] == exact
    assert row["foreign_net_volume"] == exact


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("totalForeignBuy", True),
        ("totalForeignBuy", "1.5"),
        ("totalForeignSell", "NaN"),
        ("totalForeignBuyValue", "Infinity"),
        ("totalForeignSellValue", "-Infinity"),
        ("totalMatch", "not-a-number"),
    ],
)
def test_invalid_summary_numeric_values_are_malformed(field: str, value: Any) -> None:
    adapter, auth, _data = make_adapter()
    auth.rest_client.payload = {"data": [summary_row(**{field: value})]}
    result = adapter.get_securities_summary(symbol="FPT", limit=1)
    assert result["failure_class"] == "malformed_response"
    assert result["rows"] == []


@pytest.mark.parametrize("payload", [{}, {"data": None}, [], {"data": ["bad-row"]}])
def test_malformed_summary_envelopes_do_not_become_successful_empty(payload: Any) -> None:
    adapter, auth, _data = make_adapter()
    auth.rest_client.payload = payload
    result = adapter.get_securities_summary(symbol="FPT")
    assert result["failure_class"] == "malformed_response"


def test_valid_empty_and_documented_object_envelope_are_distinct() -> None:
    empty_adapter, empty_auth, _data = make_adapter()
    empty_auth.rest_client.payload = {"data": [], "pagesCount": 0}
    empty = empty_adapter.get_securities_summary(symbol="FPT")
    assert empty["status"] == "ok" and empty["rows"] == []

    object_adapter, object_auth, _data = make_adapter()
    object_auth.rest_client.payload = SimpleNamespace(
        data=[summary_row()], pages_count=1
    )
    result = object_adapter.get_securities_summary(symbol="FPT", limit=1)
    assert result["status"] == "ok"
    assert result["rows"][0]["foreign_net_volume"] == 60


def test_pagination_deduplicates_last_row_and_sorts_like_v2_daily_summary() -> None:
    adapter, auth, _data = make_adapter()
    auth.rest_client.pages = {
        1: {
            "data": [
                summary_row(tradingDate="2026/07/22"),
                summary_row(tradingDate="2026/07/21", totalForeignBuy="80"),
            ],
            "pagesCount": 2,
        },
        2: {
            "data": [
                summary_row(tradingDate="2026/07/21", totalForeignBuy="90")
            ],
            "pagesCount": 2,
        },
    }
    result = adapter.get_securities_summary(
        symbol="FPT",
        from_date="2026-07-01",
        to_date="2026-07-22",
        page_size=2,
        limit=4,
    )
    assert [row["date"] for row in result["rows"]] == ["2026-07-21", "2026-07-22"]
    assert result["rows"][0]["foreign_buy_volume"] == 90
    assert result["duplicate_date_count"] == 1
    assert result["pages_used"] == 2
    assert [call[1]["params"]["pageIndex"] for call in auth.rest_client.calls] == [1, 2]


def test_repeated_page_and_page_row_bounds_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repeated_adapter, repeated_auth, _data = make_adapter()
    page = {"data": [summary_row()], "pagesCount": 3}
    repeated_auth.rest_client.pages = {1: page, 2: page}
    repeated = repeated_adapter.get_securities_summary(
        symbol="FPT", page_size=1, limit=3
    )
    assert repeated["failure_class"] == "malformed_response"

    import data_provider.ssi_v3_adapter as module

    monkeypatch.setattr(module, "SSI_V3_MAX_ROWS", 2)
    bounded_adapter, bounded_auth, _data = make_adapter()
    bounded_auth.rest_client.payload = {
        "data": [
            summary_row(tradingDate="2026/07/19"),
            summary_row(tradingDate="2026/07/20"),
            summary_row(tradingDate="2026/07/21"),
        ]
    }
    bounded = bounded_adapter.get_securities_summary(
        symbol="FPT", page_size=2, limit=2
    )
    assert bounded["failure_class"] == "malformed_response"


def test_identity_mismatch_and_malformed_date_fail_closed() -> None:
    for row in (
        summary_row(symbol="HPG"),
        summary_row(symbol=""),
        summary_row(tradingDate="not-a-date"),
    ):
        adapter, auth, _data = make_adapter()
        auth.rest_client.payload = {"data": [row]}
        assert adapter.get_securities_summary(symbol="FPT")["failure_class"] == (
            "malformed_response"
        )


def test_summary_rest_errors_reuse_existing_safe_rate_limit_normalization() -> None:
    from ssi_sdk.exceptions import RateLimitError

    adapter, auth, _data = make_adapter()
    auth.rest_client.error = RateLimitError("limited", retry_after=2.5)
    result = adapter.get_securities_summary(symbol="FPT")
    assert result["failure_class"] == "rate_limited"
    assert result["diagnostics"]["rate_limit"] == {
        "limit": None,
        "remaining": None,
        "reset": None,
        "retry_after_seconds": 2.5,
    }
    rendered = repr(result)
    assert "<client-id>" not in rendered
    assert "<api-key>" not in rendered
    assert "<api-secret>" not in rendered


class RecordingProvider:
    def __init__(self, source: str) -> None:
        self.source = source
        self.calls: List[str] = []

    def get_daily_stock_price(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        self.calls.append("get_daily_stock_price")
        return {"status": "ok", "source": self.source, "rows": [], "count": 0}

    def close(self) -> None:
        self.calls.append("close")


def test_router_assigns_all_foreign_flow_owners_to_sole_v3_provider() -> None:
    v3 = RecordingProvider(SSI_V3_SOURCE)
    router = SsiRestProviderRouter(v3)  # type: ignore[arg-type]

    result = router.get_daily_stock_price("FPT")
    assert result["source"] == SSI_V3_SOURCE
    assert v3.calls == ["get_daily_stock_price"]
    for capability in (
        "daily_security_summary",
        "foreign_flow",
        "foreign_flow_history",
        "foreign_flow_analytics_input",
        "vn30_foreign_flow_input",
    ):
        diagnostics = router.routing_diagnostics(capability)
        assert diagnostics["selected_version"] == "v3"
        assert diagnostics["routing_reason"] == "sole_v3_product_capability"
        assert diagnostics["fallback_used"] is False
