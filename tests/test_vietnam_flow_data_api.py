from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import stocks


class FakeFlowService:
    def close(self):
        return None

    def foreign_history_by_index(self, index_code, **kwargs):
        return {
            "status": "partial",
            "scope": "index",
            "identifier": index_code,
            "requested_from_date": kwargs["from_date"],
            "requested_to_date": kwargs["to_date"],
            "rows": [{"index": index_code, "coverage_ratio": 0.5}],
            "source": "ssi_fastconnect",
            "provider_version": "v3",
            "endpoint": "securitiesSummary?index=",
            "diagnostics": {},
        }

    def current_foreign_by_symbol(self, ticker, *, force_refresh=False):
        assert force_refresh is False
        return {
            "status": "unavailable",
            "data_state": "waiting",
            "usable": False,
            "failure_class": None,
            "symbol": ticker,
            "trading_date": "2026-07-23",
            "freshness_status": "previous_session_during_live_market",
            "is_current_session": False,
            "is_provisional": False,
            "current": None,
            "latest_completed_comparison": {"foreign_buy_value": 0},
            "stream_status": "subscribed_no_event",
            "stream_reason": "Waiting for the first current-session room update.",
            "source": "ssi_fastconnect",
            "provider_version": "v3",
            "endpoint": f"room.{ticker}",
            "cache": {"status": "empty", "age_seconds": None},
            "market_session": {"market_session": "continuous_morning"},
            "diagnostics": {"provisional_appended_to_history": False},
        }

    def proprietary_flow(self, scope, identifier, **kwargs):
        return {
            "status": "ok",
            "scope": scope,
            "identifier": identifier,
            "rows": [{"proprietary_net_value": 0}],
            "source": "ssi_fastconnect",
            "provider_version": "v3",
            "endpoint": "indexSummary",
            "unsupported_scopes": ["symbol", "icb_industry"],
            "diagnostics": {},
        }

    def industry_history(self, **kwargs):
        return {
            "status": "partial",
            "data_state": "partial",
            "usable": True,
            "failure_class": None,
            "universe": "custom_symbols",
            "requested_symbol_count": 2,
            "classified_symbol_count": 1,
            "unclassified_symbol_count": 1,
            "rows": [{"icb_code": "9530", "matched_value": 0, "coverage_ratio": 0.5}],
            "current_session_status": "CURRENT_FOREIGN_STREAM_BLOCKED_SEMANTICS",
            "proprietary_industry_status": "unsupported",
            "source": "ssi_fastconnect",
            "provider_version": "v3",
            "diagnostics": {},
        }


def _client(monkeypatch):
    monkeypatch.setattr(stocks, "VietnamFlowDataService", FakeFlowService)
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    return TestClient(app)


def test_flow_routes_preserve_zero_partial_coverage_and_blocked_stream(monkeypatch):
    client = _client(monkeypatch)

    index = client.get(
        "/api/v1/stocks/vn/foreign-flow/index/VN30",
        params={"from_date": "2026-07-01", "to_date": "2026-07-23"},
    )
    current = client.get("/api/v1/stocks/vn/foreign-flow/current/FPT")
    prop = client.get(
        "/api/v1/stocks/vn/proprietary-flow",
        params={"scope": "board", "identifier": "HOSE"},
    )
    industry = client.post(
        "/api/v1/stocks/vn/industry-flow",
        json={
            "symbols": ["FPT", "SSI"],
            "from_date": "2026-07-01",
            "to_date": "2026-07-23",
        },
    )

    assert index.status_code == 200
    assert index.json()["rows"][0]["coverage_ratio"] == 0.5
    assert current.json()["current"] is None
    assert current.json()["latest_completed_comparison"]["foreign_buy_value"] == 0
    assert current.json()["data_state"] == "waiting"
    assert current.json()["stream_status"] == "subscribed_no_event"
    assert current.json()["diagnostics"]["provisional_appended_to_history"] is False
    assert prop.json()["rows"][0]["proprietary_net_value"] == 0
    assert industry.json()["rows"][0]["matched_value"] == 0
    assert industry.json()["proprietary_industry_status"] == "unsupported"


def test_flow_routes_are_registered_in_openapi(monkeypatch):
    paths = _client(monkeypatch).get("/openapi.json").json()["paths"]
    assert "/api/v1/stocks/vn/foreign-flow/index/{index_code}" in paths
    assert "/api/v1/stocks/vn/foreign-flow/current/{ticker}" in paths
    assert "/api/v1/stocks/vn/proprietary-flow" in paths
    assert "/api/v1/stocks/vn/industry-flow" in paths


def test_industry_invalid_request_remains_validation_error(monkeypatch):
    class ValidatingService(FakeFlowService):
        def industry_history(self, **kwargs):
            from src.services.vietnam_flow_data_service import (
                ForeignFlowRequestValidationError,
            )

            raise ForeignFlowRequestValidationError(
                "provide exactly one of symbols or index_code"
            )

    monkeypatch.setattr(stocks, "VietnamFlowDataService", ValidatingService)
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    client = TestClient(app)
    response = client.post(
        "/api/v1/stocks/vn/industry-flow",
        json={
            "symbols": ["FPT"],
            "index_code": "VN30",
            "from_date": "2026-07-01",
            "to_date": "2026-07-23",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "vn_industry_flow_invalid_request"


def test_industry_provider_unavailable_is_typed_http_200(monkeypatch):
    class ProviderUnavailableService(FakeFlowService):
        def industry_history(self, **kwargs):
            return {
                "status": "unavailable",
                "data_state": "unavailable",
                "usable": False,
                "failure_class": "network_error",
                "universe": "index:VN30",
                "requested_symbol_count": 0,
                "classified_symbol_count": 0,
                "unclassified_symbol_count": 0,
                "rows": [],
                "current_session_status": "CURRENT_FOREIGN_STREAM_BLOCKED_SEMANTICS",
                "proprietary_industry_status": "unsupported",
                "source": "ssi_fastconnect",
                "provider_version": "v3",
                "diagnostics": {"failure_class": "network_error"},
            }

    monkeypatch.setattr(stocks, "VietnamFlowDataService", ProviderUnavailableService)
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    response = TestClient(app).post(
        "/api/v1/stocks/vn/industry-flow",
        json={
            "index_code": "VN30",
            "from_date": "2026-07-01",
            "to_date": "2026-07-23",
        },
    )

    assert response.status_code == 200
    assert response.json()["data_state"] == "unavailable"
    assert response.json()["usable"] is False
    assert response.json()["failure_class"] == "network_error"


def test_industry_unexpected_service_failure_is_not_validation(monkeypatch):
    class BrokenService(FakeFlowService):
        def industry_history(self, **kwargs):
            raise RuntimeError("internal invariant detail")

    monkeypatch.setattr(stocks, "VietnamFlowDataService", BrokenService)
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/stocks/vn/industry-flow",
        json={
            "index_code": "VN30",
            "from_date": "2026-07-01",
            "to_date": "2026-07-23",
        },
    )

    assert response.status_code == 500
    body = response.json()
    assert body["detail"]["error"] == "vn_industry_flow_internal_error"
    assert "invariant detail" not in body["detail"]["message"]
