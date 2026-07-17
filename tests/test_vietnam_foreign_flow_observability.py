from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.v1.endpoints import stocks
from src.services.vietnam_foreign_flow_service import (
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

