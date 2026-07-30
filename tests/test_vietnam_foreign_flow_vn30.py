from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Lock
from datetime import datetime
from time import sleep
from zoneinfo import ZoneInfo

from api.v1.schemas.stocks import VietnamVn30ForeignFlowResponse
from src.services.vietnam_foreign_flow_service import (
    VietnamForeignFlowService,
    VietnamForeignFlowVn30Service,
    reset_vietnam_foreign_flow_state,
    vietnam_foreign_flow_observability_snapshot,
)


def _row(day, *, buy_value, sell_value, buy_volume, sell_volume):
    return {
        "trading_date": day,
        "foreign_buy_value": buy_value,
        "foreign_sell_value": sell_value,
        "foreign_net_value": None if buy_value is None or sell_value is None else buy_value - sell_value,
        "foreign_buy_volume": buy_volume,
        "foreign_sell_volume": sell_volume,
        "foreign_net_volume": None if buy_volume is None or sell_volume is None else buy_volume - sell_volume,
    }


def _history(ticker, rows, state="ready", freshness="fresh"):
    return {
        "ticker": ticker,
        "source": "ssi_fastconnect",
        "source_endpoint": "daily_stock_price",
        "volume_unit": "shares",
        "value_unit": "VND",
        "finality": "daily_available",
        "data_state": state,
        "freshness": freshness,
        "rows": rows,
        "latest_row": rows[-1] if rows else None,
        "failure_class": None if rows else "empty_response",
        "stale_reason": None,
        "fetched_at": "2026-07-20T01:00:00+00:00",
    }


class FakeMarketService:
    def __init__(self, members=None, available=True):
        self.members = members or ["FPT", "HPG", "SSI"]
        self.available = available
        self.calls = []

    def build_index_components(self, index_code, force_refresh=False):
        self.calls.append((index_code, force_refresh))
        return {
            "status": "ok" if self.available else "unavailable",
            "index_code": index_code,
            "rows": [{"index_code": "VN30", "symbol": ticker} for ticker in self.members] if self.available else [],
            "diagnostics": {
                "cache_status": "refresh" if force_refresh else "miss",
                "failure_class": None if self.available else "index_components_unavailable",
            },
        }


class FakeSymbolService:
    def __init__(self, histories, delay=0):
        self.histories = histories
        self.delay = delay
        self.calls = []
        self._lock = Lock()
        self.active = 0
        self.max_active = 0

    def get_symbol_history(self, ticker, *, limit, force_refresh):
        with self._lock:
            self.calls.append((ticker, limit, force_refresh))
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        if self.delay:
            sleep(self.delay)
        result = deepcopy(self.histories[ticker])
        with self._lock:
            self.active -= 1
        return result


class FakeFlowDataService:
    def __init__(
        self,
        rows=None,
        status="ok",
        capability_status=None,
        failure_class=None,
    ):
        self.rows = rows or []
        self.status = status
        self.capability_status = capability_status
        self.failure_class = failure_class
        self.calls = []

    def foreign_history_by_index(self, index_code, **kwargs):
        self.calls.append((index_code, kwargs))
        return {
            "status": self.status,
            "capability_status": self.capability_status,
            "failure_class": self.failure_class,
            "rows": deepcopy(self.rows),
            "diagnostics": {
                "provider_operation_count": 1,
                "capability_cache_status": "stored"
                if self.capability_status == "unsupported"
                else "miss",
            },
        }


def _direct_row(day, *, buy_value=1_000, sell_value=400, buy_volume=100, sell_volume=40):
    return {
        "trading_date": day,
        "foreign_buy_value": buy_value,
        "foreign_sell_value": sell_value,
        "foreign_net_value": buy_value - sell_value,
        "foreign_buy_volume": buy_volume,
        "foreign_sell_volume": sell_volume,
        "foreign_net_volume": buy_volume - sell_volume,
        "field_presence": {
            "foreign_buy_value": "FIELD_PRESENT_NONZERO",
            "foreign_sell_value": "FIELD_PRESENT_NONZERO",
            "foreign_buy_volume": "FIELD_PRESENT_NONZERO",
            "foreign_sell_volume": "FIELD_PRESENT_NONZERO",
        },
    }


NOW = lambda: datetime(2026, 7, 21, 10, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))


def setup_function():
    reset_vietnam_foreign_flow_state()


def test_vn30_aggregate_uses_common_date_axis_and_preserves_partial_coverage():
    histories = {
        "FPT": _history(
            "FPT",
            [
                _row("2026-07-17", buy_value=100, sell_value=40, buy_volume=10, sell_volume=4),
                _row("2026-07-20", buy_value=80, sell_value=30, buy_volume=3, sell_volume=8),
            ],
        ),
        "HPG": _history(
            "HPG",
            [_row("2026-07-17", buy_value=20, sell_value=20, buy_volume=2, sell_volume=2)],
        ),
        "SSI": _history("SSI", [], state="unavailable", freshness="unavailable"),
    }
    service = VietnamForeignFlowVn30Service(
        FakeSymbolService(histories),
        FakeMarketService(),
        flow_data_service=FakeFlowDataService([
            _direct_row("2026-07-17", buy_value=900, sell_value=300),
            _direct_row("2026-07-20", buy_value=1_000, sell_value=400),
        ]),
        max_concurrency=2,
        now_fn=NOW,
    )

    payload = service.get_vn30_aggregate(top_n=2)
    validated = VietnamVn30ForeignFlowResponse(**payload)

    assert validated.data_state == "partial"
    assert payload["aggregate_session_dates"] == ["2026-07-17", "2026-07-20"]
    assert payload["latest"]["foreign_net_value"] == 600
    assert payload["latest"]["constituent_coverage"] == "not_applicable"
    assert payload["decomposition"]["latest"]["value_coverage_count"] == 1
    assert payload["decomposition"]["latest"]["value_breadth"]["net_buy_count"] == 1
    assert payload["decomposition"]["latest"]["volume_breadth"]["net_sell_count"] == 1
    assert payload["decomposition"]["latest"]["missing_components"] == 2
    assert payload["windows"]["5"]["foreign_net_value"] == 1_200
    assert payload["decomposition"]["windows"]["5"]["value_component_sessions"] == 3
    hpg = next(row for row in payload["components"] if row["ticker"] == "HPG")
    assert hpg["aggregate_latest_date"] == "2026-07-20"
    assert hpg["latest_trading_date"] == "2026-07-17"
    assert hpg["foreign_net_value"] is None
    assert hpg["foreign_net_value_5d"] == 0
    assert payload["rankings"]["latest_net_value"]["top_buy"][0]["ticker"] == "FPT"
    assert payload["source_endpoint"] == "securitiesSummary?index="
    assert payload["canonical_aggregation_mode"] == "DIRECT_INDEX_CANONICAL"


def test_vn30_aggregate_cache_and_force_refresh_are_deterministic():
    histories = {
        ticker: _history(ticker, [_row("2026-07-20", buy_value=10, sell_value=5, buy_volume=2, sell_volume=1)])
        for ticker in ("FPT", "HPG")
    }
    symbol_service = FakeSymbolService(histories)
    market_service = FakeMarketService(["fpt", "FPT", "HPG"])
    service = VietnamForeignFlowVn30Service(
        symbol_service,
        market_service,
        flow_data_service=FakeFlowDataService([_direct_row("2026-07-20")]),
        now_fn=NOW,
    )

    first = service.get_vn30_aggregate(top_n=1)
    second = service.get_vn30_aggregate(top_n=1)
    refreshed = service.get_vn30_aggregate(top_n=1, force_refresh=True)

    assert first["membership"]["member_tickers"] == ["FPT", "HPG"]
    assert first["cache"]["status"] == "miss"
    assert second["cache"]["status"] == "hit"
    assert refreshed["cache"]["status"] == "refresh"
    assert len(symbol_service.calls) == 4
    assert all(call[1] == 60 for call in symbol_service.calls)
    assert symbol_service.calls[-1][2] is True


def test_vn30_membership_unavailable_does_not_call_symbol_history():
    symbol_service = FakeSymbolService({})
    payload = VietnamForeignFlowVn30Service(
        symbol_service,
        FakeMarketService(available=False),
        flow_data_service=FakeFlowDataService(status="unavailable"),
        now_fn=NOW,
    ).get_vn30_aggregate()

    assert payload["data_state"] == "unavailable"
    assert payload["membership"]["failure_class"] == "index_components_unavailable"
    assert payload["series"] == []
    assert payload["components"] == []
    assert payload["cache"]["negative"] is True
    assert symbol_service.calls == []


def test_vn30_failed_membership_refresh_uses_last_known_good_cohort() -> None:
    histories = {
        ticker: _history(
            ticker,
            [_row(
                "2026-07-20",
                buy_value=10,
                sell_value=5,
                buy_volume=2,
                sell_volume=1,
            )],
        )
        for ticker in ("FPT", "HPG")
    }
    market_service = FakeMarketService(["FPT", "HPG"])
    symbol_service = FakeSymbolService(histories)
    service = VietnamForeignFlowVn30Service(
        symbol_service,
        market_service,
        flow_data_service=FakeFlowDataService([_direct_row("2026-07-20")]),
        now_fn=NOW,
    )

    initial = service.get_vn30_aggregate(top_n=1)
    market_service.available = False
    retained = service.get_vn30_aggregate(top_n=1, force_refresh=True)

    assert initial["membership"]["retained"] is False
    assert retained["status"] == "partial"
    assert retained["usable"] is True
    assert retained["membership"]["retained"] is True
    assert retained["membership"]["member_tickers"] == ["FPT", "HPG"]
    assert retained["membership"]["refresh_failure_class"] == (
        "index_components_unavailable"
    )
    assert retained["membership"]["cache_status"] == "stale_hit"
    assert retained["decomposition"]["series"]
    assert len(symbol_service.calls) == 4


def test_vn30_provider_initialization_failure_is_typed_unavailable():
    class FailingMarketService:
        def build_index_components(self, *args, **kwargs):
            raise ValueError("provider is not configured")

    payload = VietnamForeignFlowVn30Service(
        FakeSymbolService({}),
        FailingMarketService(),
        flow_data_service=FakeFlowDataService(status="unavailable"),
        now_fn=NOW,
    ).get_vn30_aggregate()

    assert payload["data_state"] == "unavailable"
    assert payload["canonical"]["status"] == "unavailable"
    assert payload["membership"]["failure_class"] == "provider_not_configured"


def test_vn30_concurrent_requests_coalesce_aggregate_build():
    histories = {
        ticker: _history(ticker, [_row("2026-07-20", buy_value=10, sell_value=5, buy_volume=2, sell_volume=1)])
        for ticker in ("FPT", "HPG")
    }
    symbol_service = FakeSymbolService(histories, delay=0.03)
    service = VietnamForeignFlowVn30Service(
        symbol_service,
        FakeMarketService(["FPT", "HPG"]),
        flow_data_service=FakeFlowDataService([_direct_row("2026-07-20")]),
        max_concurrency=1,
        now_fn=NOW,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: service.get_vn30_aggregate(top_n=1), range(2)))

    assert len(symbol_service.calls) == 2
    assert {result["cache"]["status"] for result in results} == {"miss", "coalesced"}
    metrics = vietnam_foreign_flow_observability_snapshot()
    assert metrics["vn30_coalesced_waiters"] == 1


def test_vn30_component_history_concurrency_is_capped_at_four():
    tickers = [f"T{index}" for index in range(6)]
    histories = {
        ticker: _history(ticker, [_row("2026-07-20", buy_value=10, sell_value=5, buy_volume=2, sell_volume=1)])
        for ticker in tickers
    }
    symbol_service = FakeSymbolService(histories, delay=0.02)

    payload = VietnamForeignFlowVn30Service(
        symbol_service,
        FakeMarketService(tickers),
        flow_data_service=FakeFlowDataService([_direct_row("2026-07-20")]),
        max_concurrency=99,
        now_fn=NOW,
    ).get_vn30_aggregate()

    assert payload["membership"]["component_count"] == 6
    assert symbol_service.max_active == 4


def test_vn30_rejects_mismatched_membership_without_history_calls():
    class MismatchedMarketService:
        def build_index_components(self, index_code, force_refresh=False):
            return {
                "status": "ok",
                "rows": [{"index_code": "VN30", "symbol": "FPT"}, {"index_code": "VN100", "symbol": "HPG"}],
                "diagnostics": {},
            }

    symbol_service = FakeSymbolService({})
    payload = VietnamForeignFlowVn30Service(
        symbol_service,
        MismatchedMarketService(),
        flow_data_service=FakeFlowDataService(status="unavailable"),
        now_fn=NOW,
    ).get_vn30_aggregate()

    assert payload["membership"]["failure_class"] == "membership_mismatch"
    assert payload["membership"]["member_tickers"] == []
    assert payload["membership"]["component_count"] == 0
    assert payload["components"] == []
    assert symbol_service.calls == []


def test_vn30_rejects_unbounded_membership_without_history_calls():
    tickers = [f"S{index:02d}" for index in range(31)]
    symbol_service = FakeSymbolService({})
    payload = VietnamForeignFlowVn30Service(
        symbol_service,
        FakeMarketService(tickers),
        flow_data_service=FakeFlowDataService(status="unavailable"),
        now_fn=NOW,
    ).get_vn30_aggregate()

    assert payload["membership"]["failure_class"] == "membership_count_exceeded"
    assert payload["membership"]["member_tickers"] == []
    assert payload["membership"]["component_count"] == 0
    assert payload["components"] == []
    assert symbol_service.calls == []


def test_direct_index_uses_latest_completed_session_and_excludes_current_session():
    histories = {
        "FPT": _history(
            "FPT",
            [_row("2026-07-23", buy_value=30, sell_value=10, buy_volume=3, sell_volume=1)],
        )
    }
    service = VietnamForeignFlowVn30Service(
        FakeSymbolService(histories),
        FakeMarketService(["FPT"]),
        flow_data_service=FakeFlowDataService([
            _direct_row("2026-07-22", buy_value=500, sell_value=200),
            _direct_row("2026-07-23", buy_value=700, sell_value=250),
            _direct_row("2026-07-24", buy_value=900, sell_value=300),
        ]),
        now_fn=lambda: datetime(2026, 7, 24, 10, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")),
    )

    payload = service.get_vn30_aggregate()

    assert payload["canonical_trading_date"] == "2026-07-23"
    assert payload["latest"]["foreign_net_value"] == 450
    diagnostics = payload["canonical"]["diagnostics"]
    assert diagnostics["latest_completed_provider_session"] == "2026-07-23"
    assert diagnostics["session_lag"] == 0
    assert diagnostics["source_freshness"] == "latest_completed_session"
    assert diagnostics["excluded_dates"] == ["2026-07-24"]
    assert payload["latest"]["constituent_coverage"] == "not_applicable"
    assert payload["decomposition_date"] == "2026-07-23"


def test_all_explicit_zero_component_session_is_preserved_but_suspicious():
    zero_presence = {
        name: "FIELD_PRESENT_EXPLICIT_ZERO"
        for name in (
            "foreign_buy_value",
            "foreign_sell_value",
            "foreign_buy_volume",
            "foreign_sell_volume",
        )
    }
    zero = _row(
        "2026-07-20",
        buy_value=0,
        sell_value=0,
        buy_volume=0,
        sell_volume=0,
    )
    zero["field_presence"] = zero_presence
    histories = {
        ticker: _history(ticker, [deepcopy(zero)])
        for ticker in ("FPT", "HPG")
    }
    service = VietnamForeignFlowVn30Service(
        FakeSymbolService(histories),
        FakeMarketService(["FPT", "HPG"]),
        flow_data_service=FakeFlowDataService([_direct_row("2026-07-20")]),
        now_fn=NOW,
    )

    payload = service.get_vn30_aggregate()
    day = payload["decomposition"]["latest"]

    assert day["foreign_net_value"] == 0
    assert day["all_constituents_zero"] is True
    assert day["explicit_zero_component_count"] == 2
    assert day["suspicious_zero_session"] is True
    assert day["anomaly"] == "all_constituents_explicit_zero"
    assert day["anomaly_status"] == "provider_backed_suspect"
    assert payload["decomposition"]["windows"]["5"]["complete"] is False


def test_direct_unsupported_keeps_ready_decomposition_partial_and_usable():
    histories = {
        ticker: _history(
            ticker,
            [
                _row(
                    "2026-07-23",
                    buy_value=100,
                    sell_value=40,
                    buy_volume=10,
                    sell_volume=4,
                )
            ],
        )
        for ticker in ("FPT", "HPG")
    }
    service = VietnamForeignFlowVn30Service(
        FakeSymbolService(histories),
        FakeMarketService(["FPT", "HPG"]),
        flow_data_service=FakeFlowDataService(
            status="unavailable",
            capability_status="unsupported",
            failure_class="DIRECT_INDEX_FOREIGN_FIELDS_UNSUPPORTED",
        ),
        now_fn=lambda: datetime(
            2026, 7, 24, 10, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")
        ),
    )

    payload = service.get_vn30_aggregate()

    assert payload["status"] == "partial"
    assert payload["data_state"] == "partial"
    assert payload["usable"] is True
    assert (
        payload["capability_status"]
        == "decomposition_ready_canonical_unsupported"
    )
    assert payload["canonical"]["status"] == "unavailable"
    assert payload["canonical"]["capability_status"] == "unsupported"
    assert (
        payload["canonical"]["failure_class"]
        == "DIRECT_INDEX_FOREIGN_FIELDS_UNSUPPORTED"
    )
    assert payload["canonical"]["constituent_coverage"] == "not_applicable"
    assert payload["decomposition"]["status"] == "ready"
    assert payload["decomposition"]["usable"] is True
    assert payload["latest"] == payload["decomposition"]["latest"]
    assert payload["series"] == payload["decomposition"]["series"]
    assert payload["primary_data_mode"] == "current_membership_decomposition"
    assert payload["aggregation_basis"] == "current_vn30_membership"
    assert payload["source_endpoint"] == "daily_stock_price"
    assert payload["decomposition_date"] == "2026-07-23"
    assert payload["decomposition"]["historical_constituent_correct"] is False
    assert payload["decomposition"]["latest"]["value_coverage_count"] == 2
    assert payload["source_coverage"] == [
        {
            "source": "SSI V3 Direct VN30 Foreign Aggregate",
            "capability_status": "unsupported",
            "usable": False,
            "failure_class": "DIRECT_INDEX_FOREIGN_FIELDS_UNSUPPORTED",
        },
        {
            "source": "SSI V3 Symbol Foreign Data",
            "capability_status": "available",
            "usable": True,
        },
        {
            "source": "SSI VN30 Index Components",
            "capability_status": "available",
            "usable": True,
        },
    ]


def test_direct_unsupported_and_decomposition_unavailable_is_not_usable():
    histories = {
        "FPT": _history("FPT", [], state="unavailable", freshness="unavailable")
    }
    payload = VietnamForeignFlowVn30Service(
        FakeSymbolService(histories),
        FakeMarketService(["FPT"]),
        flow_data_service=FakeFlowDataService(
            status="unavailable",
            capability_status="unsupported",
            failure_class="DIRECT_INDEX_FOREIGN_FIELDS_UNSUPPORTED",
        ),
        now_fn=NOW,
    ).get_vn30_aggregate()

    assert payload["status"] == "unavailable"
    assert payload["data_state"] == "unavailable"
    assert payload["usable"] is False
    assert (
        payload["capability_status"]
        == "canonical_unsupported_decomposition_unavailable"
    )


def test_partial_decomposition_with_one_valid_session_remains_usable():
    histories = {
        "FPT": _history(
            "FPT",
            [
                _row(
                    "2026-07-23",
                    buy_value=100,
                    sell_value=40,
                    buy_volume=10,
                    sell_volume=4,
                )
            ],
        ),
        "HPG": _history(
            "HPG", [], state="unavailable", freshness="unavailable"
        ),
    }
    payload = VietnamForeignFlowVn30Service(
        FakeSymbolService(histories),
        FakeMarketService(["FPT", "HPG"]),
        flow_data_service=FakeFlowDataService(
            status="unavailable",
            capability_status="unsupported",
            failure_class="DIRECT_INDEX_FOREIGN_FIELDS_UNSUPPORTED",
        ),
        now_fn=lambda: datetime(
            2026, 7, 24, 10, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")
        ),
    ).get_vn30_aggregate()

    assert payload["decomposition"]["status"] == "partial"
    assert payload["decomposition"]["usable"] is True
    assert payload["status"] == "partial"
    assert payload["usable"] is True


def test_provider_zero_session_stays_valid_and_sets_window_anomaly_metadata():
    days = [
        "2026-06-26",
        "2026-06-29",
        "2026-06-30",
        "2026-07-01",
        "2026-07-02",
    ]
    zero_presence = {
        name: "FIELD_PRESENT_EXPLICIT_ZERO"
        for name in (
            "foreign_buy_value",
            "foreign_sell_value",
            "foreign_buy_volume",
            "foreign_sell_volume",
        )
    }
    rows = []
    for day in days:
        row = _row(
            day,
            buy_value=0 if day in {"2026-06-29", "2026-06-30"} else 10,
            sell_value=0 if day in {"2026-06-29", "2026-06-30"} else 5,
            buy_volume=0 if day in {"2026-06-29", "2026-06-30"} else 2,
            sell_volume=0 if day in {"2026-06-29", "2026-06-30"} else 1,
        )
        if day in {"2026-06-29", "2026-06-30"}:
            row["field_presence"] = zero_presence
        rows.append(row)
    histories = {
        ticker: _history(ticker, deepcopy(rows)) for ticker in ("FPT", "HPG")
    }
    payload = VietnamForeignFlowVn30Service(
        FakeSymbolService(histories),
        FakeMarketService(["FPT", "HPG"]),
        flow_data_service=FakeFlowDataService(
            status="unavailable",
            capability_status="unsupported",
            failure_class="DIRECT_INDEX_FOREIGN_FIELDS_UNSUPPORTED",
        ),
        now_fn=lambda: datetime(
            2026, 7, 3, 10, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")
        ),
    ).get_vn30_aggregate()

    by_date = {
        row["trading_date"]: row for row in payload["decomposition"]["series"]
    }
    for day in ("2026-06-29", "2026-06-30"):
        assert by_date[day]["foreign_net_value"] == 0
        assert by_date[day]["valid_session"] is True
        assert by_date[day]["anomaly_code"] == "all_constituents_explicit_zero"
        assert by_date[day]["anomaly_status"] == "provider_backed_suspect"
        assert by_date[day]["explicit_zero_component_count"] == 2
        assert by_date[day]["missing_field_component_count"] == 0
    window = payload["decomposition"]["windows"]["5"]
    assert window["complete"] is True
    assert window["valid_sessions"] == 5
    assert window["contains_provider_anomaly"] is True
    assert window["anomaly_sessions"] == ["2026-06-29", "2026-06-30"]
    assert window["anomaly_count"] == 2


def test_component_missing_canonical_date_is_unavailable_not_backfilled():
    histories = {
        "FPT": _history(
            "FPT",
            [_row("2026-07-22", buy_value=30, sell_value=10, buy_volume=3, sell_volume=1)],
        ),
        "HPG": _history(
            "HPG",
            [_row("2026-07-23", buy_value=20, sell_value=5, buy_volume=2, sell_volume=1)],
        ),
    }
    service = VietnamForeignFlowVn30Service(
        FakeSymbolService(histories),
        FakeMarketService(["FPT", "HPG"]),
        flow_data_service=FakeFlowDataService([_direct_row("2026-07-23")]),
        now_fn=lambda: datetime(2026, 7, 24, 10, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")),
    )

    payload = service.get_vn30_aggregate()
    fpt = next(row for row in payload["components"] if row["ticker"] == "FPT")

    assert fpt["data_state"] == "unavailable"
    assert fpt["foreign_net_value"] is None
    assert payload["decomposition"]["latest"]["value_coverage_count"] == 1
