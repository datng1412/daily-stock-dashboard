from __future__ import annotations

from typing import Any, Dict, Optional
from unittest.mock import patch

import pytest

from src.services.vietnam_flow_data_service import (
    VietnamFlowDataService,
    reset_vietnam_flow_data_capability_cache,
)
from src.services.vietnam_foreign_flow_service import (
    reset_vietnam_foreign_flow_state,
)


@pytest.fixture(autouse=True)
def _reset_direct_index_capability_cache():
    reset_vietnam_flow_data_capability_cache()
    reset_vietnam_foreign_flow_state()
    yield
    reset_vietnam_flow_data_capability_cache()
    reset_vietnam_foreign_flow_state()


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


def test_current_vn30_aggregate_uses_one_cohort_and_excludes_mixed_session_dates() -> None:
    class MembershipProvider(FakeProvider):
        def get_securities_by_index(self, index_code: str) -> Dict[str, Any]:
            assert index_code == "VN30"
            return {
                "status": "ok",
                "rows": [
                    {"symbol": "FPT", "icb_code": "9530", "icb_name": "Software"},
                    {"symbol": "SSI", "icb_code": "8770", "icb_name": "Financial Services"},
                    {"symbol": "HPG", "icb_code": "1750", "icb_name": "Industrial Metals"},
                ],
            }

    class CurrentReader:
        cohort_calls = []

        def ensure_current_foreign_flow_cohort(
            self,
            symbols: list[str],
            *,
            recovery_trigger: str,
        ) -> Dict[str, Any]:
            self.cohort_calls.append((list(symbols), recovery_trigger))
            return {
                "status": "ok",
                "symbols": list(symbols),
                "subscription_added_count": len(symbols),
            }

        def get_current_foreign_flow(self, symbol: str) -> Dict[str, Any]:
            rows = {
                "FPT": {
                    "foreign_buy_volume": 10,
                    "foreign_sell_volume": 4,
                    "foreign_buy_value": 100,
                    "foreign_sell_value": 40,
                    "raw_field_presence": {},
                },
                "SSI": {
                    "foreign_buy_volume": 0,
                    "foreign_sell_volume": 0,
                    "foreign_buy_value": 0,
                    "foreign_sell_value": 0,
                    "raw_field_presence": {
                        "foreign_buy_volume": "explicit_zero",
                        "foreign_sell_volume": "explicit_zero",
                    },
                },
                "HPG": {
                    "foreign_buy_volume": 999,
                    "foreign_sell_volume": 1,
                    "foreign_buy_value": 999,
                    "foreign_sell_value": 1,
                    "raw_field_presence": {},
                },
            }
            session = "2026-07-28" if symbol == "HPG" else "2026-07-29"
            return {
                "status": "ok",
                "data_state": "ready",
                "usable": True,
                "failure_class": None,
                "provider_session_date": session,
                "current": rows[symbol],
                "stream_status": "cache_hit",
                "market_session": {"market_session_active": True},
            }

    reader = CurrentReader()
    payload = VietnamFlowDataService(
        MembershipProvider(),
        streaming_reader=reader,
    ).current_foreign_aggregate(
        index_code="VN30",
        include_industries=True,
    )

    assert reader.cohort_calls == [(["FPT", "SSI", "HPG"], "route_touch")]
    assert payload["provider_session_date"] == "2026-07-29"
    assert payload["status"] == "partial"
    assert payload["aggregate"]["foreign_buy_volume"] == 10
    assert payload["aggregate"]["foreign_sell_volume"] == 4
    assert payload["aggregate"]["foreign_net_volume"] == 6
    assert payload["aggregate"]["foreign_buy_value"] == 100
    assert payload["aggregate"]["foreign_sell_value"] == 40
    assert payload["aggregate"]["foreign_net_value"] == 60
    assert payload["coverage"]["requested_symbol_count"] == 3
    assert payload["coverage"]["observed_symbol_count"] == 2
    assert payload["coverage"]["complete_volume_count"] == 2
    assert payload["coverage"]["complete_value_count"] == 2
    assert payload["coverage"]["missing_symbols"] == ["HPG"]
    assert payload["diagnostics"]["mixed_provider_session_dates_excluded"] == [
        "2026-07-28"
    ]
    assert {group["icb_code"] for group in payload["groups"]} == {
        "1750",
        "8770",
        "9530",
    }
    assert payload["diagnostics"]["industry_group_requested_count"] == 3
    assert payload["diagnostics"]["industry_group_observed_count"] == 2
    assert payload["diagnostics"]["industry_group_reconciliation"] == {
        "foreign_buy_volume": True,
        "foreign_sell_volume": True,
        "foreign_buy_value": True,
        "foreign_sell_value": True,
    }
    assert payload["display_series"][-1]["source_kind"] == "current"
    assert payload["display_series"][-1]["is_partial"] is True


def test_idle_membership_auth_failure_retains_cohort_completed_rows_and_stale_current() -> None:
    class MembershipProvider(FakeProvider):
        available = True
        calls = 0

        def get_securities_by_index(self, index_code: str) -> Dict[str, Any]:
            self.calls += 1
            if not self.available:
                return {
                    "status": "unavailable",
                    "failure_class": "authentication_failed",
                    "rows": [],
                }
            return super().get_securities_by_index(index_code)

        def request_auth_recovery(self, *, trigger: str) -> Dict[str, Any]:
            assert trigger == "visibility_resume"
            return {
                "status": "scheduled",
                "recovery_scheduled": True,
                "negative_cache_bypassed": True,
            }

    class CurrentReader:
        failed = False
        cohort_calls: list[tuple[list[str], str]] = []

        def ensure_current_foreign_flow_cohort(
            self,
            symbols: list[str],
            *,
            recovery_trigger: str,
        ) -> Dict[str, Any]:
            self.cohort_calls.append((list(symbols), recovery_trigger))
            return {
                "status": "unavailable" if self.failed else "ok",
                "recovery_requested": self.failed,
                "recovery_status": "already_scheduled" if self.failed else None,
                "subscription_added_count": 0,
            }

        def get_current_foreign_flow(self, symbol: str) -> Dict[str, Any]:
            if self.failed:
                return {
                    "status": "partial",
                    "data_state": "stale",
                    "usable": True,
                    "failure_class": "authentication_failed_retryable",
                    "provider_session_date": "2026-07-29",
                    "current": {
                        "foreign_buy_volume": 10,
                        "foreign_sell_volume": 4,
                        "foreign_buy_value": 100,
                        "foreign_sell_value": 40,
                    },
                    "stream_status": "reconnecting",
                    "market_session": {"market_session_active": True},
                }
            return {
                "status": "ok",
                "data_state": "ready",
                "usable": True,
                "failure_class": None,
                "provider_session_date": "2026-07-29",
                "current": {
                    "foreign_buy_volume": 10,
                    "foreign_sell_volume": 4,
                    "foreign_buy_value": 100,
                    "foreign_sell_value": 40,
                },
                "stream_status": "cache_hit",
                "market_session": {"market_session_active": True},
            }

    accepted = {
        ticker: [{
            "trading_date": "2026-07-28",
            "foreign_buy_volume": 5,
            "foreign_sell_volume": 2,
            "foreign_net_volume": 3,
            "foreign_buy_value": 50,
            "foreign_sell_value": 20,
            "foreign_net_value": 30,
        }]
        for ticker in ("FPT", "SSI")
    }
    provider = MembershipProvider()
    reader = CurrentReader()
    service = VietnamFlowDataService(provider, streaming_reader=reader)

    with patch(
        "src.services.vietnam_foreign_flow_service.accepted_vietnam_foreign_flow_history",
        return_value=accepted,
    ):
        initial = service.current_foreign_aggregate(
            index_code="VN30",
            include_industries=True,
        )
        provider.available = False
        reader.failed = True
        after_idle = service.current_foreign_aggregate(
            index_code="VN30",
            include_industries=True,
            force_refresh=True,
            recovery_trigger="visibility_resume",
        )

    assert initial["coverage"]["requested_symbol_count"] == 2
    assert after_idle["status"] == "partial"
    assert after_idle["usable"] is True
    assert after_idle["data_state"] == "stale"
    assert after_idle["coverage"]["requested_symbol_count"] == 2
    assert after_idle["coverage"]["observed_symbol_count"] == 2
    assert after_idle["display_series"]
    assert [row["trading_date"] for row in after_idle["display_series"]] == [
        "2026-07-28",
        "2026-07-29",
    ]
    assert after_idle["display_series"][-1]["status"] == "Mất kết nối"
    diagnostics = after_idle["diagnostics"]
    assert diagnostics["membership_retained"] is True
    assert diagnostics["membership_refresh_failure_class"] == (
        "authentication_failed_retryable"
    )
    assert diagnostics["negative_cache_bypassed"] is True
    assert diagnostics["recovery_scheduled"] is True
    assert diagnostics["current_snapshot_retained"] is True
    assert reader.cohort_calls[-1] == (
        ["FPT", "SSI"],
        "visibility_resume",
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


def test_current_stream_failure_does_not_poison_completed_index_flow() -> None:
    class FailedCurrentReader:
        ensure_calls = 0

        def ensure_current_foreign_flow(
            self,
            _symbol: str,
            *,
            recovery_trigger: str,
        ) -> Dict[str, Any]:
            self.ensure_calls += 1
            assert recovery_trigger == "manual_refresh"
            return {
                "status": "unavailable",
                "recovery_requested": True,
            }

        def get_current_foreign_flow(self, symbol: str) -> Dict[str, Any]:
            return {
                "status": "unavailable",
                "data_state": "unavailable",
                "usable": False,
                "failure_class": "authentication_rejected",
                "provider_session_date": "2026-07-29",
                "is_current_session": False,
                "is_provisional": False,
                "current": None,
                "stream_status": "reconnecting",
                "stream_reason": "Current stream unavailable.",
                "cache": {"status": "empty", "age_seconds": None},
                "market_session": {},
                "diagnostics": {},
            }

    reader = FailedCurrentReader()
    service = VietnamFlowDataService(
        FakeProvider(),
        streaming_reader=reader,
    )

    current = service.current_foreign_by_symbol(
        "FPT",
        force_refresh=True,
    )
    completed = service.foreign_history_by_index(
        "VN30",
        from_date="2026-07-23",
        to_date="2026-07-23",
    )

    assert current["status"] == "unavailable"
    assert current["failure_class"] == "authentication_rejected"
    assert reader.ensure_calls == 1
    assert completed["status"] == "ok"
    assert completed["rows"][0]["foreign_net_value"] == 160


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


def test_proprietary_scope_is_truthfully_unsupported_without_provider_call() -> None:
    payload = VietnamFlowDataService(FakeProvider()).proprietary_flow("board", "HOSE")

    assert payload["status"] == "unavailable"
    assert payload["data_state"] == "unavailable"
    assert payload["usable"] is False
    assert payload["capability_status"] == "unsupported"
    assert payload["failure_class"] == "proprietary_fields_unsupported"
    assert payload["rows"] == []
    assert payload["endpoint"] == "none"
    assert payload["unsupported_scopes"] == ["symbol", "icb_industry"]
    assert payload["diagnostics"]["attempted_operation"] == "none"
    assert payload["diagnostics"]["reason"] == "no_proven_proprietary_flow_fields"


def test_proprietary_flow_does_not_call_or_reinterpret_index_summary() -> None:
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

    assert payload["status"] == "unavailable"
    assert payload["capability_status"] == "unsupported"
    assert payload["rows"] == []
    assert provider.index_calls == []
    assert provider.market_calls == []


def test_current_foreign_does_not_promote_previous_session_or_blend_stream(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        "src.services.ssi_streaming_realtime_lifecycle."
        "get_existing_ssi_streaming_realtime_manager",
        lambda: None,
    )
    payload = VietnamFlowDataService(FakeProvider()).current_foreign_by_symbol("FPT")

    assert payload["status"] == "unavailable"
    assert payload["data_state"] == "unavailable"
    assert payload["current"] is None
    assert payload["latest_completed_comparison"]["foreign_buy_value"] == 100
    assert payload["stream_status"] == "manager_not_started"
    assert payload["diagnostics"]["provisional_appended_to_history"] is False


def test_current_foreign_uses_stream_snapshot_and_keeps_daily_as_completed_comparison() -> None:
    class ReadyReader:
        def get_current_foreign_flow(self, symbol: str) -> Dict[str, Any]:
            return {
                "status": "ok",
                "data_state": "ready",
                "usable": True,
                "failure_class": None,
                "provider_session_date": "2026-07-29",
                "is_current_session": True,
                "is_provisional": True,
                "current": {
                    "symbol": symbol,
                    "provider_session_date": "2026-07-29",
                    "foreign_buy_volume": 20,
                    "foreign_sell_volume": 5,
                    "foreign_buy_value": 2_000,
                    "foreign_sell_value": 500,
                    "foreign_net_volume": 15,
                    "foreign_net_value": 1_500,
                    "raw_field_presence": {
                        "foreign_buy_volume": "nonzero",
                        "foreign_sell_volume": "nonzero",
                        "foreign_buy_value": "nonzero",
                        "foreign_sell_value": "nonzero",
                    },
                },
                "stream_status": "cache_hit",
                "stream_reason": None,
                "cache": {"status": "hit", "age_seconds": 1},
                "market_session": {"market_session": "continuous_morning"},
                "diagnostics": {"replacement_snapshot": True},
            }

    payload = VietnamFlowDataService(
        FakeProvider(),
        streaming_reader=ReadyReader(),
    ).current_foreign_by_symbol("FPT")

    assert payload["status"] == "ok"
    assert payload["data_state"] == "ready"
    assert payload["current"]["foreign_net_value"] == 1_500
    assert payload["latest_completed_comparison"]["date"] == "2026-07-23"
    assert payload["latest_completed_comparison"]["finality"] == "completed_session_authority"
    assert payload["finality"] == "current_session_provisional"
    assert payload["update_semantics"] == "cumulative_replacement_snapshot"
    assert payload["diagnostics"]["provisional_appended_to_history"] is False


def test_missing_runtime_credentials_degrade_to_typed_unavailable_without_provider_calls(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        "src.services.ssi_streaming_realtime_lifecycle."
        "get_existing_ssi_streaming_realtime_manager",
        lambda: None,
    )
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
