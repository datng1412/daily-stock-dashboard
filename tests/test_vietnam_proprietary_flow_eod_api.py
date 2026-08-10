from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import stocks


class FakeEodService:
    def get_latest(self, exchange):
        if exchange.upper() != "HOSE":
            from src.services.vietnam_proprietary_flow_eod_service import ProprietaryFlowValidationError
            raise ProprietaryFlowValidationError("exchange must be HOSE")
        return {
            "status": "ok",
            "data_state": "ready",
            "exchange": "HOSE",
            "latest": _row(),
            "source": "official_exchange_pdf_manual_entry",
            "warnings": [],
        }

    def get_history(self, exchange, limit):
        payload = self.get_latest(exchange)
        return {
            "status": "ok",
            "data_state": "ready",
            "exchange": "HOSE",
            "count": 1,
            "series": [payload["latest"]],
            "source_summary": {"value_unit": "VND", "volume_unit": "shares"},
            "warnings": [],
        }


def _row():
    return {
        "trading_date": "2026-08-06", "exchange": "HOSE",
        "buy_volume": 0, "sell_volume": 0, "net_volume": 0,
        "buy_value": 200, "sell_value": 150, "net_value": 50,
        "source_type": "official_exchange_pdf_manual_entry",
        "source_url": "https://example.test/official.pdf",
        "source_title": "Official publication", "source_file_name": "official.pdf",
        "source_file_hash": "a" * 64, "source_file_size": 8,
        "source_evidence_strength": "OFFICIAL_PDF_HASHED", "verified_by_user": True,
        "imported_at": "2026-08-06T12:00:00+00:00", "finality": "completed_daily",
        "complete_value": True, "complete_volume": True, "complete": True,
        "data_quality": "accepted", "warnings": [],
    }


def _client(monkeypatch):
    monkeypatch.setattr(stocks, "VietnamProprietaryFlowEodService", FakeEodService)
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    return TestClient(app)


def test_latest_and_history_are_read_only_and_serialize_zero_and_source(monkeypatch):
    client = _client(monkeypatch)
    latest = client.get("/api/v1/stocks/vn/proprietary-flow/eod/latest", params={"exchange": "hose"})
    history = client.get("/api/v1/stocks/vn/proprietary-flow/eod/history", params={"exchange": "hose", "limit": 60})
    assert latest.status_code == history.status_code == 200
    assert latest.json()["latest"]["buy_volume"] == 0
    assert latest.json()["latest"]["source_url"].startswith("https://")
    assert history.json()["series"][0]["source_file_name"] == "official.pdf"
    assert not any(path.endswith("eod/latest") or path.endswith("eod/history") for path in client.post("/openapi.json").json().get("paths", {}))


def test_routes_are_registered_as_get_only(monkeypatch):
    paths = _client(monkeypatch).get("/openapi.json").json()["paths"]
    assert set(paths["/api/v1/stocks/vn/proprietary-flow/eod/latest"]) == {"get"}
    assert set(paths["/api/v1/stocks/vn/proprietary-flow/eod/history"]) == {"get"}


def test_invalid_exchange_and_limit_are_422(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/api/v1/stocks/vn/proprietary-flow/eod/latest", params={"exchange": "HNX"}).status_code == 422
    assert client.get("/api/v1/stocks/vn/proprietary-flow/eod/history", params={"limit": 251}).status_code == 422


def test_real_service_no_data_and_null_volume(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_CACHE_DIR", str(tmp_path))
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    client = TestClient(app)
    response = client.get("/api/v1/stocks/vn/proprietary-flow/eod/latest")
    assert response.status_code == 200
    assert response.json()["data_state"] == "no_data"
    assert response.json()["latest"] is None
