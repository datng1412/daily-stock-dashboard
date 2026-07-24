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

    def current_foreign_by_symbol(self, ticker):
        return {
            "status": "unavailable",
            "symbol": ticker,
            "trading_date": "2026-07-23",
            "freshness_status": "previous_session_during_live_market",
            "is_current_session": False,
            "is_provisional": False,
            "current": None,
            "latest_completed_comparison": {"foreign_buy_value": 0},
            "stream_status": "CURRENT_FOREIGN_STREAM_BLOCKED_SEMANTICS",
            "stream_reason": "unproven",
            "source": "ssi_fastconnect",
            "provider_version": "v3",
            "endpoint": "securitiesSummary",
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
    assert current.json()["stream_status"] == "CURRENT_FOREIGN_STREAM_BLOCKED_SEMANTICS"
    assert prop.json()["rows"][0]["proprietary_net_value"] == 0
    assert industry.json()["rows"][0]["matched_value"] == 0
    assert industry.json()["proprietary_industry_status"] == "unsupported"


def test_flow_routes_are_registered_in_openapi(monkeypatch):
    paths = _client(monkeypatch).get("/openapi.json").json()["paths"]
    assert "/api/v1/stocks/vn/foreign-flow/index/{index_code}" in paths
    assert "/api/v1/stocks/vn/foreign-flow/current/{ticker}" in paths
    assert "/api/v1/stocks/vn/proprietary-flow" in paths
    assert "/api/v1/stocks/vn/industry-flow" in paths
