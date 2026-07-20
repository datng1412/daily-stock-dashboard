from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Lock
from time import sleep

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
        max_concurrency=2,
    )

    payload = service.get_vn30_aggregate(top_n=2)
    validated = VietnamVn30ForeignFlowResponse(**payload)

    assert validated.data_state == "partial"
    assert payload["aggregate_session_dates"] == ["2026-07-17", "2026-07-20"]
    assert payload["latest"]["foreign_net_value"] == 50
    assert payload["latest"]["value_coverage_count"] == 1
    assert payload["latest"]["value_breadth"]["net_buy_count"] == 1
    assert payload["latest"]["volume_breadth"]["net_sell_count"] == 1
    assert payload["latest"]["missing_components"] == 2
    assert payload["windows"]["5"]["foreign_net_value"] == 110
    assert payload["windows"]["5"]["value_component_sessions"] == 3
    hpg = next(row for row in payload["components"] if row["ticker"] == "HPG")
    assert hpg["aggregate_latest_date"] == "2026-07-20"
    assert hpg["latest_trading_date"] == "2026-07-17"
    assert hpg["foreign_net_value"] is None
    assert hpg["foreign_net_value_5d"] == 0
    assert payload["rankings"]["latest_net_value"]["top_buy"][0]["ticker"] == "FPT"
    assert payload["source_endpoint"] == "DailyStockPrice"


def test_vn30_aggregate_cache_and_force_refresh_are_deterministic():
    histories = {
        ticker: _history(ticker, [_row("2026-07-20", buy_value=10, sell_value=5, buy_volume=2, sell_volume=1)])
        for ticker in ("FPT", "HPG")
    }
    symbol_service = FakeSymbolService(histories)
    market_service = FakeMarketService(["fpt", "FPT", "HPG"])
    service = VietnamForeignFlowVn30Service(symbol_service, market_service)

    first = service.get_vn30_aggregate(top_n=1)
    second = service.get_vn30_aggregate(top_n=1)
    refreshed = service.get_vn30_aggregate(top_n=1, force_refresh=True)

    assert first["membership"]["member_tickers"] == ["FPT", "HPG"]
    assert first["cache"]["status"] == "miss"
    assert second["cache"]["status"] == "hit"
    assert refreshed["cache"]["status"] == "refresh"
    assert len(symbol_service.calls) == 4
    assert all(call[1] == 20 for call in symbol_service.calls)
    assert symbol_service.calls[-1][2] is True


def test_vn30_membership_unavailable_does_not_call_symbol_history():
    symbol_service = FakeSymbolService({})
    payload = VietnamForeignFlowVn30Service(
        symbol_service,
        FakeMarketService(available=False),
    ).get_vn30_aggregate()

    assert payload["data_state"] == "unavailable"
    assert payload["membership"]["failure_class"] == "index_components_unavailable"
    assert payload["series"] == []
    assert payload["components"] == []
    assert payload["cache"]["negative"] is True
    assert symbol_service.calls == []


def test_vn30_concurrent_requests_coalesce_aggregate_build():
    histories = {
        ticker: _history(ticker, [_row("2026-07-20", buy_value=10, sell_value=5, buy_volume=2, sell_volume=1)])
        for ticker in ("FPT", "HPG")
    }
    symbol_service = FakeSymbolService(histories, delay=0.03)
    service = VietnamForeignFlowVn30Service(symbol_service, FakeMarketService(["FPT", "HPG"]), max_concurrency=1)

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
        max_concurrency=99,
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
    payload = VietnamForeignFlowVn30Service(symbol_service, MismatchedMarketService()).get_vn30_aggregate()

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
    ).get_vn30_aggregate()

    assert payload["membership"]["failure_class"] == "membership_count_exceeded"
    assert payload["membership"]["member_tickers"] == []
    assert payload["membership"]["component_count"] == 0
    assert payload["components"] == []
    assert symbol_service.calls == []
