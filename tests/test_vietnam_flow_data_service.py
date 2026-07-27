from __future__ import annotations

from typing import Any, Dict, Optional
from unittest.mock import patch

import pytest

from src.services.vietnam_flow_data_service import (
    VietnamFlowDataService,
    reset_vietnam_flow_data_capability_cache,
)


@pytest.fixture(autouse=True)
def _reset_direct_index_capability_cache():
    reset_vietnam_flow_data_capability_cache()
    yield
    reset_vietnam_flow_data_capability_cache()


class FakeProvider:
    def get_securities_by_index(self, index_code: str) -> Dict[str, Any]:
        return {
            "status": "ok",
            "rows": [
                {"symbol": "FPT", "icb_code": "9530", "icb_name": "Software"},
                {"symbol": "SSI", "icb_code": "8770", "icb_name": "Financial Services"},
            ],
        }

    def get_securities_summary_by_index(self, index_code: str, **kwargs: Any) -> Dict[str, Any]:
        return {
            "status": "ok",
            "rows": [
                {
                    "symbol": index_code, "date": "2026-07-23",
                    "foreign_buy_volume": 30, "foreign_sell_volume": 14,
                    "foreign_buy_value": 300, "foreign_sell_value": 140,
                },
                {
                    "symbol": "FPT", "date": "2026-07-23",
                    "foreign_buy_volume": 10, "foreign_sell_volume": 4,
                    "foreign_buy_value": 100, "foreign_sell_value": 40,
                },
                {
                    "symbol": "SSI", "date": "2026-07-23",
                    "foreign_buy_volume": 0, "foreign_sell_volume": 0,
                    "foreign_buy_value": 0, "foreign_sell_value": 0,
                },
            ],
        }

    def get_daily_stock_price(
        self,
        symbol: str,
        market: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 260,
    ) -> Dict[str, Any]:
        row = {
            "date": "2026-07-23",
            "foreign_buy_volume": 10 if symbol == "FPT" else 0,
            "foreign_sell_volume": 4 if symbol == "FPT" else None,
            "foreign_buy_value": 100 if symbol == "FPT" else 0,
            "foreign_sell_value": 40 if symbol == "FPT" else None,
            "matched_volume": 1_000,
            "matched_value": 10_000,
        }
        return {"status": "ok", "rows": [row]}

    def get_security_basic_info(self, symbol: str) -> Dict[str, Any]:
        if symbol == "FPT":
            return {"status": "ok", "rows": [{"symbol": symbol, "icb_code": "9530", "icb_name": "Software"}]}
        return {"status": "ok", "rows": [{"symbol": symbol, "icb_code": None, "icb_name": None}]}

    def get_market_summary(self, scope: str, identifier: str, *, trading_date: Optional[str] = None) -> Dict[str, Any]:
        return {
            "status": "ok",
            "rows": [{
                "date": trading_date or "2026-07-24",
                "proprietary_buy_volume": 10,
                "proprietary_sell_volume": 3,
                "proprietary_net_volume": 7,
                "proprietary_buy_value": 100,
                "proprietary_sell_value": 30,
                "proprietary_net_value": 70,
            }],
        }

    def get_index_summary(
        self,
        board: str,
        index_code: Optional[str] = None,
        trading_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.get_market_summary(
            "index",
            index_code or board,
            trading_date=trading_date,
        )


def test_index_foreign_history_uses_only_direct_provider_aggregate() -> None:
    payload = VietnamFlowDataService(FakeProvider()).foreign_history_by_index(
        "VN30", from_date="2026-07-23", to_date="2026-07-23"
    )

    row = payload["rows"][0]
    assert row["foreign_buy_volume"] == 30
    assert row["foreign_sell_volume"] == 14
    assert row["foreign_net_value"] == 160
    assert row["coverage_mode"] == "provider_aggregate"
    assert row["constituent_coverage"] == "not_applicable"
    assert row["status"] == "ok"


def test_provider_index_aggregate_is_retained_without_claiming_constituent_coverage() -> None:
    class AggregateProvider(FakeProvider):
        def get_securities_summary_by_index(self, index_code: str, **kwargs: Any) -> Dict[str, Any]:
            return {
                "status": "ok",
                "rows": [{
                    "symbol": index_code,
                    "date": "2026-07-23",
                    "foreign_buy_volume": 100,
                    "foreign_sell_volume": 40,
                    "foreign_buy_value": 1_000,
                    "foreign_sell_value": 400,
                }],
            }

    payload = VietnamFlowDataService(AggregateProvider()).foreign_history_by_index(
        "VN30", from_date="2026-07-23", to_date="2026-07-23"
    )

    assert payload["diagnostics"]["aggregate_shape"] == "provider_index_rows"
    assert payload["rows"][0]["provider_aggregate_row"] is True
    assert payload["rows"][0]["foreign_net_value"] == 600
    assert payload["rows"][0]["constituent_coverage"] == "not_applicable"
    assert payload["rows"][0]["status"] == "ok"
    assert payload["diagnostics"]["provider_operation_count"] == 1


def test_direct_index_all_null_fields_are_unsupported_and_negatively_cached() -> None:
    class NullForeignProvider(FakeProvider):
        calls = 0

        def get_securities_summary_by_index(
            self, index_code: str, **kwargs: Any
        ) -> Dict[str, Any]:
            self.calls += 1
            return {
                "status": "ok",
                "rows": [
                    {
                        "symbol": index_code,
                        "date": "2026-07-23",
                        "foreign_buy_volume": None,
                        "foreign_sell_volume": None,
                        "foreign_buy_value": None,
                        "foreign_sell_value": None,
                    }
                ],
            }

    provider = NullForeignProvider()
    service = VietnamFlowDataService(provider)
    first = service.foreign_history_by_index(
        "VN30", from_date="2026-07-01", to_date="2026-07-23"
    )
    second = service.foreign_history_by_index(
        "VN30", from_date="2026-07-01", to_date="2026-07-23"
    )

    assert first["status"] == "unavailable"
    assert first["capability_status"] == "unsupported"
    assert first["failure_class"] == "DIRECT_INDEX_FOREIGN_FIELDS_UNSUPPORTED"
    assert first["usable_session_count"] == 0
    assert first["diagnostics"]["capability_cache_status"] == "stored"
    assert second["diagnostics"]["capability_cache_status"] == "hit"
    assert second["diagnostics"]["provider_operation_count"] == 0
    assert provider.calls == 1


def test_force_capability_refresh_bypasses_negative_cache() -> None:
    class NullForeignProvider(FakeProvider):
        calls = 0

        def get_securities_summary_by_index(
            self, index_code: str, **kwargs: Any
        ) -> Dict[str, Any]:
            self.calls += 1
            return {
                "status": "ok",
                "rows": [{"symbol": index_code, "date": "2026-07-23"}],
            }

    provider = NullForeignProvider()
    service = VietnamFlowDataService(provider)
    service.foreign_history_by_index(
        "VN30", from_date="2026-07-01", to_date="2026-07-23"
    )
    refreshed = service.foreign_history_by_index(
        "VN30",
        from_date="2026-07-01",
        to_date="2026-07-23",
        force_capability_refresh=True,
    )

    assert provider.calls == 2
    assert refreshed["diagnostics"]["capability_refresh_reason"] == (
        "explicit_capability_refresh"
    )


def test_auth_failure_and_timeout_do_not_create_unsupported_classification() -> None:
    class AuthProvider(FakeProvider):
        calls = 0

        def get_securities_summary_by_index(
            self, index_code: str, **kwargs: Any
        ) -> Dict[str, Any]:
            self.calls += 1
            return {
                "status": "unavailable",
                "rows": [],
                "diagnostics": {"failure_class": "auth_failed"},
            }

    auth_provider = AuthProvider()
    auth_service = VietnamFlowDataService(auth_provider)
    first = auth_service.foreign_history_by_index(
        "VN30", from_date="2026-07-01", to_date="2026-07-23"
    )
    second = auth_service.foreign_history_by_index(
        "VN30", from_date="2026-07-01", to_date="2026-07-23"
    )
    assert first["capability_status"] == "unavailable"
    assert second["capability_status"] == "unavailable"
    assert auth_provider.calls == 2

    class TimeoutProvider(FakeProvider):
        calls = 0

        def get_securities_summary_by_index(
            self, index_code: str, **kwargs: Any
        ) -> Dict[str, Any]:
            self.calls += 1
            raise TimeoutError("bounded timeout")

    timeout_provider = TimeoutProvider()
    timeout_service = VietnamFlowDataService(timeout_provider)
    with pytest.raises(TimeoutError):
        timeout_service.foreign_history_by_index(
            "VN30", from_date="2026-07-01", to_date="2026-07-23"
        )
    with pytest.raises(TimeoutError):
        timeout_service.foreign_history_by_index(
            "VN30", from_date="2026-07-01", to_date="2026-07-23"
        )
    assert timeout_provider.calls == 2


def test_provider_version_change_bypasses_old_capability_entry(monkeypatch) -> None:
    import src.services.vietnam_flow_data_service as module

    class NullForeignProvider(FakeProvider):
        calls = 0

        def get_securities_summary_by_index(
            self, index_code: str, **kwargs: Any
        ) -> Dict[str, Any]:
            self.calls += 1
            return {
                "status": "ok",
                "rows": [{"symbol": index_code, "date": "2026-07-23"}],
            }

    provider = NullForeignProvider()
    service = VietnamFlowDataService(provider)
    service.foreign_history_by_index(
        "VN30", from_date="2026-07-01", to_date="2026-07-23"
    )
    monkeypatch.setattr(module, "_PROVIDER_VERSION", "v3-next")
    service.foreign_history_by_index(
        "VN30", from_date="2026-07-01", to_date="2026-07-23"
    )
    assert provider.calls == 2


def test_industry_history_excludes_and_counts_missing_icb_without_synthesizing_flow() -> None:
    payload = VietnamFlowDataService(FakeProvider()).industry_history(
        symbols=["FPT", "SSI"],
        from_date="2026-07-23",
        to_date="2026-07-23",
    )

    assert payload["classified_symbol_count"] == 1
    assert payload["unclassified_symbol_count"] == 1
    assert len(payload["rows"]) == 1
    row = payload["rows"][0]
    assert row["icb_code"] == "9530"
    assert row["foreign_net_value"] == 60
    assert row["matched_value"] == 10_000
    assert "net_cash_flow" not in row
    assert payload["diagnostics"]["reconciliation"]["foreign_buy_value"]["matches"] is True
    assert payload["diagnostics"]["reconciliation"]["foreign_sell_value"]["matches"] is True
    assert payload["diagnostics"]["reconciliation"]["matched_value"]["matches"] is True


def test_index_industry_history_reuses_direct_membership_and_summary_operations() -> None:
    payload = VietnamFlowDataService(FakeProvider()).industry_history(
        index_code="VN30",
        from_date="2026-07-23",
        to_date="2026-07-23",
    )

    assert payload["universe"] == "index:VN30"
    assert payload["diagnostics"]["provider_operation_count"] == 2
    assert {row["icb_code"] for row in payload["rows"]} == {"9530", "8770"}


@pytest.mark.parametrize(
    ("provider_result", "failure_class"),
    [
        (
            {
                "status": "unavailable",
                "rows": [],
                "failure_class": "authentication_failed",
            },
            "authentication_failed",
        ),
        (
            {
                "status": "unavailable",
                "rows": [],
                "diagnostics": {"failure_class": "network_error"},
            },
            "network_error",
        ),
        (
            {
                "status": "unavailable",
                "rows": [],
                "failure_class": "request_timeout",
            },
            "request_timeout",
        ),
        (
            {
                "status": "unavailable",
                "rows": [],
                "failure_class": "internal_error",
            },
            "provider_unavailable",
        ),
    ],
)
def test_index_industry_membership_failure_is_typed_not_unsupported(
    provider_result, failure_class
) -> None:
    class UnavailableMembershipProvider(FakeProvider):
        def get_securities_by_index(self, index_code: str) -> Dict[str, Any]:
            return provider_result

    payload = VietnamFlowDataService(
        UnavailableMembershipProvider()
    ).industry_history(
        index_code="VN30",
        from_date="2026-07-01",
        to_date="2026-07-23",
    )

    assert payload["status"] == "unavailable"
    assert payload["data_state"] == "unavailable"
    assert payload["usable"] is False
    assert payload["failure_class"] == failure_class
    assert payload["rows"] == []
    assert "unsupported" not in failure_class


def test_index_industry_empty_membership_is_typed_unavailable() -> None:
    class EmptyMembershipProvider(FakeProvider):
        def get_securities_by_index(self, index_code: str) -> Dict[str, Any]:
            return {"status": "ok", "rows": []}

    payload = VietnamFlowDataService(EmptyMembershipProvider()).industry_history(
        index_code="VN30",
        from_date="2026-07-01",
        to_date="2026-07-23",
    )

    assert payload["status"] == "unavailable"
    assert payload["failure_class"] == "membership_unavailable"
    assert payload["diagnostics"]["provider_operation_count"] == 1


def test_proprietary_scope_is_board_or_index_and_unsupported_symbol_is_explicit() -> None:
    payload = VietnamFlowDataService(FakeProvider()).proprietary_flow("board", "HOSE")

    assert payload["status"] == "ok"
    assert payload["rows"][0]["proprietary_net_value"] == 70
    assert payload["unsupported_scopes"] == ["symbol", "icb_industry"]


def test_completed_proprietary_summary_is_reused_without_provider_failure_poisoning() -> None:
    service = VietnamFlowDataService(FakeProvider())
    first = service.proprietary_flow(
        "index", "HNX30", from_date="2026-07-23", to_date="2026-07-23"
    )
    second = service.proprietary_flow(
        "index", "HNX30", from_date="2026-07-23", to_date="2026-07-23"
    )

    assert first["diagnostics"]["provider_operation_count"] == 1
    assert second["diagnostics"]["provider_operation_count"] == 0
    assert second["diagnostics"]["cache_hit_count"] == 1


def test_index_proprietary_flow_uses_proven_direct_index_summary_path() -> None:
    class RecordingIndexProvider(FakeProvider):
        index_calls = []
        market_calls = []

        def get_index_summary(
            self,
            board: str,
            index_code: Optional[str] = None,
            trading_date: Optional[str] = None,
        ) -> Dict[str, Any]:
            self.index_calls.append((board, index_code, trading_date))
            return FakeProvider.get_market_summary(
                self,
                "index",
                index_code or board,
                trading_date=trading_date,
            )

        def get_market_summary(
            self,
            scope: str,
            identifier: str,
            *,
            trading_date: Optional[str] = None,
        ) -> Dict[str, Any]:
            self.market_calls.append((scope, identifier, trading_date))
            return super().get_market_summary(
                scope,
                identifier,
                trading_date=trading_date,
            )

    provider = RecordingIndexProvider()
    payload = VietnamFlowDataService(provider).proprietary_flow(
        "index",
        "VN30",
        from_date="2026-07-24",
        to_date="2026-07-24",
        force_refresh=True,
    )

    assert payload["status"] == "ok"
    assert provider.index_calls == [("VN30", "VN30", "2026-07-24")]
    assert provider.market_calls == []


def test_current_foreign_does_not_promote_previous_session_or_blend_stream() -> None:
    payload = VietnamFlowDataService(FakeProvider()).current_foreign_by_symbol("FPT")

    assert payload["status"] == "unavailable"
    assert payload["current"] is None
    assert payload["latest_completed_comparison"]["foreign_buy_value"] == 100
    assert payload["stream_status"] == "CURRENT_FOREIGN_STREAM_BLOCKED_SEMANTICS"


def test_missing_runtime_credentials_degrade_to_typed_unavailable_without_provider_calls() -> None:
    with patch(
        "src.services.vietnam_flow_data_service.create_ssi_rest_provider_router",
        side_effect=ValueError("not configured"),
    ):
        service = VietnamFlowDataService()

    assert service.foreign_history_by_index(
        "VN30", from_date="2026-07-23", to_date="2026-07-23"
    )["status"] == "unavailable"
    assert service.current_foreign_by_symbol("FPT")["status"] == "unavailable"
    assert service.proprietary_flow("index", "VN30")["status"] == "unavailable"
    industry = service.industry_history(
        symbols=["FPT"], from_date="2026-07-23", to_date="2026-07-23"
    )
    assert industry["status"] == "unavailable"
    assert industry["diagnostics"]["provider_operation_count"] == 0
