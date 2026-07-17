from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import stocks


def _payload(ticker="FPT"):
    row = {
        "trading_date": "2026-07-17",
        "foreign_buy_volume": 10,
        "foreign_sell_volume": 4,
        "foreign_net_volume": 6,
        "foreign_buy_value": 100,
        "foreign_sell_value": 40,
        "foreign_net_value": 60,
    }
    window = {
        "requested_sessions": 5,
        "covered_sessions": 1,
        "complete": False,
        "start_date": "2026-07-17",
        "end_date": "2026-07-17",
        "cumulative_foreign_net_volume": 6,
        "cumulative_foreign_net_value": 60,
        "net_volume_contributing_sessions": 1,
        "net_value_contributing_sessions": 1,
        "positive_net_volume_sessions": 1,
        "negative_net_volume_sessions": 0,
        "zero_net_volume_sessions": 0,
        "null_net_volume_sessions": 0,
        "positive_net_value_sessions": 1,
        "negative_net_value_sessions": 0,
        "zero_net_value_sessions": 0,
        "null_net_value_sessions": 0,
    }
    windows = {
        key: {**window, "requested_sessions": int(key)}
        for key in ("5", "20", "60")
    }
    return {
        "ticker": ticker,
        "source": "ssi_fastconnect",
        "source_endpoint": "daily_stock_price",
        "volume_unit": "shares",
        "value_unit": "VND",
        "finality": "daily_available",
        "data_state": "ready",
        "freshness": "fresh",
        "rows": [row],
        "windows": windows,
        "latest_row": row,
        "requested": {
            "mode": "recent_sessions",
            "requested_limit": 20,
            "requested_from_date": None,
            "requested_to_date": None,
            "returned_session_count": 1,
        },
        "coverage": {
            "requested_sessions": 20,
            "covered_sessions": 1,
            "complete": False,
            "start_date": "2026-07-17",
            "end_date": "2026-07-17",
        },
        "fetched_at": "2026-07-17T10:00:00+00:00",
        "stale_reason": None,
        "failure_class": None,
    }


def _client():
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    return TestClient(app)


def test_http_endpoint_exposes_typed_contract(monkeypatch):
    calls = []

    class StubService:
        def get_symbol_history(self, ticker, **kwargs):
            calls.append((ticker, kwargs))
            return _payload(ticker.upper())

    monkeypatch.setattr(stocks, "VietnamForeignFlowService", StubService)
    response = _client().get("/api/v1/stocks/vn/foreign-flow/symbol/fpt?limit=20&force_refresh=true")

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "FPT"
    assert body["source"] == "ssi_fastconnect"
    assert body["finality"] == "daily_available"
    assert body["rows"][0]["foreign_net_value"] == 60
    assert calls == [("fpt", {"limit": 20, "from_date": None, "to_date": None, "force_refresh": True})]


def test_http_endpoint_returns_422_for_invalid_query_shape(monkeypatch):
    class StubService:
        def get_symbol_history(self, ticker, **kwargs):
            raise ValueError("from_date and to_date must be provided together")

    monkeypatch.setattr(stocks, "VietnamForeignFlowService", StubService)
    response = _client().get("/api/v1/stocks/vn/foreign-flow/symbol/FPT?from_date=2026-01-01")

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "vn_foreign_flow_invalid_request"


def test_openapi_registers_foreign_flow_route_and_response_schema():
    schema = _client().get("/openapi.json").json()
    route = schema["paths"]["/api/v1/stocks/vn/foreign-flow/symbol/{ticker}"]["get"]
    assert route["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/VietnamForeignFlowSymbolHistoryResponse"
    }

