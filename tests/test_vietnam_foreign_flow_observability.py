from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.v1.endpoints import stocks
from src.services.vietnam_foreign_flow_service import (
    VietnamForeignFlowBatchService,
    reset_vietnam_foreign_flow_state,
    vietnam_foreign_flow_observability_snapshot,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_vietnam_foreign_flow_state()
    yield
    reset_vietnam_foreign_flow_state()


def test_broad_observability_exposes_typed_zero_state_without_provider_work(monkeypatch):
    def fail_provider(*args, **kwargs):
        raise AssertionError("observability must not construct or call an SSI provider")

    monkeypatch.setattr("data_provider.ssi_fastconnect_fetcher.SsiFastConnectFetcher.get_daily_stock_price", fail_provider)
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    with TestClient(app) as client:
        response = client.get("/api/v1/stocks/vn/observability")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    foreign_flow = response.json()["foreign_flow"]
    assert foreign_flow == vietnam_foreign_flow_observability_snapshot()
    assert foreign_flow["scope"] == "process_local"
    assert foreign_flow["provider_calls"] == 0
    assert "rows" not in foreign_flow
    assert "raw" not in str(foreign_flow).lower()


def test_batch_metrics_are_typed_sanitized_and_observability_read_is_inert(monkeypatch):
    class StubSymbolService:
        calls = 0

        def get_symbol_history(self, ticker, **kwargs):
            self.calls += 1
            return {
                "ticker": ticker,
                "source": "ssi_fastconnect",
                "source_endpoint": "daily_stock_price",
                "volume_unit": "shares",
                "value_unit": "VND",
                "finality": "daily_available",
                "data_state": "unavailable",
                "freshness": "unavailable",
                "rows": [],
                "latest_row": None,
                "windows": {
                    "5": {"covered_sessions": 0, "complete": False, "cumulative_foreign_net_volume": None, "cumulative_foreign_net_value": None},
                    "20": {"covered_sessions": 0, "complete": False, "cumulative_foreign_net_volume": None, "cumulative_foreign_net_value": None},
                },
                "fetched_at": "2026-07-17T10:00:00+00:00",
                "failure_class": "network_error",
            }

    symbol_service = StubSymbolService()
    VietnamForeignFlowBatchService(symbol_service).get_batch(["FPT", "VCB"], force_refresh=True)
    before = vietnam_foreign_flow_observability_snapshot()

    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    response = TestClient(app).get("/api/v1/stocks/vn/observability")
    after = vietnam_foreign_flow_observability_snapshot()

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["foreign_flow"] == before == after
    assert before["batch_requests"] == 1
    assert before["batch_force_refresh_requests"] == 1
    assert before["batch_normalized_symbols"] == 2
    assert before["batch_unavailable_symbols"] == 2
    assert before["batch_unavailable_results"] == 1
    assert before["batch_active_requests"] == 0
    assert before["batch_latency_count"] == 1
    assert before["ranking_build_count"] == 1
    assert symbol_service.calls == 2
    assert "FPT" not in str(before)
    assert "VCB" not in str(before)
