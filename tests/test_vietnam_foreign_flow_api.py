from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from api.middlewares.error_handler import add_error_handlers
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


def _batch_payload(state="ready"):
    usable = state in {"ready", "stale"}
    row = {
        "ticker": "FPT",
        "data_state": state,
        "freshness": "stale" if state == "stale" else ("fresh" if state == "ready" else state),
        "failure_class": "network_error" if state == "unavailable" else None,
        "stale_reason": "cached" if state == "stale" else None,
        "latest_trading_date": "2026-07-17" if usable else None,
        "foreign_buy_volume": 10 if usable else None,
        "foreign_sell_volume": 4 if usable else None,
        "foreign_net_volume": 6 if usable else None,
        "foreign_buy_value": 100 if usable else None,
        "foreign_sell_value": 40 if usable else None,
        "foreign_net_value": 60 if usable else None,
        "foreign_net_volume_5d": 30 if usable else None,
        "foreign_net_value_5d": 300 if usable else None,
        "foreign_net_volume_20d": 120 if usable else None,
        "foreign_net_value_20d": 1_200 if usable else None,
        "covered_sessions_5d": 5 if usable else 0,
        "complete_5d": usable,
        "window_end_date_5d": "2026-07-17" if usable else None,
        "covered_sessions_20d": 20 if usable else 0,
        "complete_20d": usable,
        "window_end_date_20d": "2026-07-17" if usable else None,
        "source": "ssi_fastconnect",
        "source_endpoint": "daily_stock_price",
        "volume_unit": "shares",
        "value_unit": "VND",
        "finality": "daily_available",
        "fetched_at": "2026-07-17T10:00:00+00:00",
    }
    entry = {
        "ticker": "FPT",
        "value": 60,
        "trading_date": "2026-07-17",
        "covered_sessions": 1,
        "complete": True,
        "data_state": state,
    } if usable else None
    pair = {"top_buy": [entry] if entry else [], "top_sell": []}
    return {
        "source": "ssi_fastconnect",
        "source_endpoint": "daily_stock_price",
        "volume_unit": "shares",
        "value_unit": "VND",
        "finality": "daily_available",
        "requested_tickers": ["fpt"],
        "normalized_tickers": ["FPT"],
        "requested_count": 1,
        "normalized_count": 1,
        "returned_count": 1,
        "usable_count": 1 if usable else 0,
        "fresh_count": 1 if state == "ready" else 0,
        "stale_count": 1 if state == "stale" else 0,
        "empty_count": 1 if state == "empty" else 0,
        "unavailable_count": 1 if state == "unavailable" else 0,
        "coverage_ratio": 1 if usable else 0,
        "complete": state == "ready",
        "data_state": state,
        "rows": [row],
        "rankings": {"latest_net_value": pair, "net_value_5d": pair, "net_value_20d": pair},
        "fetched_at": "2026-07-17T10:00:00+00:00",
    }


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


def test_batch_endpoint_normalizes_through_service_and_returns_typed_response(monkeypatch):
    calls = []

    class StubBatchService:
        def get_batch(self, tickers, **kwargs):
            calls.append((tickers, kwargs))
            return _batch_payload()

    monkeypatch.setattr(stocks, "VietnamForeignFlowBatchService", StubBatchService)
    response = _client().post(
        "/api/v1/stocks/vn/foreign-flow/batch",
        json={"tickers": ["fpt"], "top_n": 5, "force_refresh": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data_state"] == "ready"
    assert body["rows"][0]["foreign_net_value_5d"] == 300
    assert "rows" not in body["rows"][0]
    assert calls == [(["fpt"], {"top_n": 5, "force_refresh": True})]


@pytest.mark.parametrize(
    "body",
    [
        {"tickers": []},
        {"tickers": ["*"]},
        {"tickers": ["ALL"]},
        {"tickers": [f"A{index:02d}" for index in range(31)]},
        {"tickers": ["FPT"], "top_n": 0},
        {"tickers": ["FPT"], "top_n": 11},
    ],
)
def test_batch_endpoint_rejects_invalid_bodies_without_constructing_service(monkeypatch, body):
    monkeypatch.setattr(
        stocks,
        "VietnamForeignFlowBatchService",
        lambda: (_ for _ in ()).throw(AssertionError("invalid body must not start batch work")),
    )
    assert _client().post("/api/v1/stocks/vn/foreign-flow/batch", json=body).status_code == 422


def test_batch_custom_ticker_validation_is_serializable_with_project_error_handlers(monkeypatch):
    monkeypatch.setattr(
        stocks,
        "VietnamForeignFlowBatchService",
        lambda: (_ for _ in ()).throw(AssertionError("invalid body must not start batch work")),
    )
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    add_error_handlers(app)

    response = TestClient(app).post("/api/v1/stocks/vn/foreign-flow/batch", json={"tickers": ["ALL"]})

    assert response.status_code == 422
    assert response.json()["error"] == "vn_foreign_flow_batch_invalid_request"


@pytest.mark.parametrize("state", ["empty", "unavailable"])
def test_batch_endpoint_returns_http_200_for_typed_nonusable_results(monkeypatch, state):
    class StubBatchService:
        def get_batch(self, tickers, **kwargs):
            return _batch_payload(state)

    monkeypatch.setattr(stocks, "VietnamForeignFlowBatchService", StubBatchService)
    response = _client().post("/api/v1/stocks/vn/foreign-flow/batch", json={"tickers": ["FPT"]})
    assert response.status_code == 200
    assert response.json()["data_state"] == state


def test_openapi_registers_foreign_flow_batch_contract():
    route = _client().get("/openapi.json").json()["paths"]["/api/v1/stocks/vn/foreign-flow/batch"]["post"]
    assert route["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/VietnamForeignFlowBatchRequest"
    }
    assert route["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/VietnamForeignFlowBatchResponse"
    }
