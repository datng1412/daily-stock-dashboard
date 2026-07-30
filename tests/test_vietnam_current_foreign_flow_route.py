from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints import stocks
from data_provider.ssi_streaming_realtime import SsiStreamingRealtimeManager
from data_provider.ssi_v3_streaming import normalize_v3_streaming_messages
from src.services import ssi_streaming_realtime_lifecycle as lifecycle
from src.services import vietnam_flow_data_service as flow_service


VN_TZ = timezone(timedelta(hours=7))


class _RecordingStreamClient:
    def __init__(self) -> None:
        self.initial_channels: List[str] = []
        self.ensure_calls: List[List[str]] = []
        self.stop_calls = 0

    def start(
        self,
        _on_message: Any,
        _on_error: Any,
        channels: List[str],
        **kwargs: Any,
    ) -> None:
        self.initial_channels = list(channels)
        for channel in channels:
            kwargs["on_open"](channel)

    def ensure_channels(self, channels: List[str]) -> None:
        self.ensure_calls.append(list(channels))

    def stop(self) -> None:
        self.stop_calls += 1


class _DailyProvider:
    completed_rows = [
        {
            "date": "2026-07-28",
            "foreign_buy_volume": 10,
            "foreign_sell_volume": 8,
            "foreign_buy_value": 1_000,
            "foreign_sell_value": 800,
        }
    ]

    def __init__(self) -> None:
        self.close_calls = 0

    def get_daily_stock_price(self, symbol: str, limit: int = 5) -> Dict[str, Any]:
        assert symbol in {"FPT", "SSI"}
        assert limit == 5
        return {
            "status": "ok",
            "rows": [dict(row) for row in self.completed_rows],
        }

    def close(self) -> None:
        self.close_calls += 1


def _route_client(monkeypatch: Any) -> tuple[TestClient, SsiStreamingRealtimeManager, _RecordingStreamClient]:
    now = datetime(2026, 7, 29, 10, 8, tzinfo=VN_TZ).timestamp()
    stream_client = _RecordingStreamClient()
    manager = SsiStreamingRealtimeManager(
        enabled=True,
        parser=normalize_v3_streaming_messages,
        client_factory=lambda: stream_client,
        foreign_room_enabled=True,
        market_index_enabled=False,
        session_status_enabled=False,
        trade_tape_enabled=False,
        time_func=lambda: now,
    )
    manager.start(["VCB"])
    monkeypatch.setattr(
        lifecycle,
        "get_existing_ssi_streaming_realtime_manager",
        lambda: manager,
    )
    monkeypatch.setattr(
        flow_service,
        "create_ssi_rest_provider_router",
        _DailyProvider,
    )
    app = FastAPI()
    app.include_router(stocks.router, prefix="/api/v1/stocks")
    return TestClient(app), manager, stream_client


def test_raw_room_message_reaches_production_http_route_and_stays_out_of_history(
    monkeypatch: Any,
) -> None:
    client, manager, stream_client = _route_client(monkeypatch)
    original_history = [dict(row) for row in _DailyProvider.completed_rows]

    waiting = client.get("/api/v1/stocks/vn/foreign-flow/current/FPT")
    assert waiting.status_code == 200
    assert waiting.json()["data_state"] == "waiting"
    assert waiting.json()["current"] is None
    assert stream_client.ensure_calls == [
        ["X:FPT", "X-QUOTE:FPT", "R:FPT"]
    ]

    manager.handle_message(
        {
            "topic": "room.FPT",
            "data": {
                "t": "2026/07/29 10:08:00",
                "s": "FPT",
                "bq": 1_250,
                "sq": 400,
                "bv": 125_000_000,
                "sv": 40_000_000,
                "tr": 9_000,
                "cr": 8_000,
            },
        }
    )
    response = client.get(
        "/api/v1/stocks/vn/foreign-flow/current/FPT",
        params={"force_refresh": True},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, no-cache, max-age=0"
    assert response.headers["pragma"] == "no-cache"
    payload = response.json()
    current = payload["current"]
    assert payload["status"] == "ok"
    assert payload["data_state"] == "ready"
    assert payload["symbol"] == "FPT"
    assert payload["source"] == "SSI FastConnect V3 ForeignRoomMessage"
    assert payload["finality"] == "current_session_provisional"
    assert payload["update_semantics"] == "cumulative_replacement_snapshot"
    assert payload["trading_date"] == "2026-07-29"
    assert current["foreign_buy_volume"] == 1_250
    assert current["foreign_sell_volume"] == 400
    assert current["foreign_net_volume"] == 850
    assert current["foreign_buy_value"] == 125_000_000
    assert current["foreign_sell_value"] == 40_000_000
    assert current["foreign_net_value"] == 85_000_000
    assert current["total_room"] == 9_000
    assert current["current_room"] == 8_000
    assert current["stream_timestamp"] == "2026/07/29 10:08:00"
    assert current["received_at"] != current["stream_timestamp"]
    assert current["provider_session_date"] == "2026-07-29"
    assert current["session_date_source"] == "provider_event"
    assert payload["latest_completed_comparison"]["date"] == "2026-07-28"
    assert payload["latest_completed_comparison"]["finality"] == "completed_session_authority"
    assert payload["diagnostics"]["provisional_appended_to_history"] is False
    assert _DailyProvider.completed_rows == original_history
    assert "raw_payload" not in current
    assert not {"bq", "sq", "bv", "sv", "tr", "cr"}.intersection(current)
    assert not {"ranking", "analytics", "export"}.intersection(payload)


def test_repeated_route_polling_and_force_refresh_add_one_subscription_per_symbol(
    monkeypatch: Any,
) -> None:
    client, manager, stream_client = _route_client(monkeypatch)

    payloads = []
    for _ in range(4):
        response = client.get(
            "/api/v1/stocks/vn/foreign-flow/current/FPT"
        )
        assert response.status_code == 200
        payloads.append(response.json())
    force_response = client.get(
        "/api/v1/stocks/vn/foreign-flow/current/FPT",
        params={"force_refresh": True},
    )
    assert force_response.status_code == 200
    payloads.append(force_response.json())

    assert len(stream_client.ensure_calls) == 1
    assert stream_client.ensure_calls[0].count("R:FPT") == 1
    assert manager.status()["requested_symbols"] == ["VCB", "FPT"]
    assert {
        payload["diagnostics"]["subscription_count"] for payload in payloads
    } == {6}
    assert {
        payload["diagnostics"]["foreign_room_subscription_count"]
        for payload in payloads
    } == {2}

    assert client.get(
        "/api/v1/stocks/vn/foreign-flow/current/SSI"
    ).status_code == 200
    assert len(stream_client.ensure_calls) == 2
    assert stream_client.ensure_calls[1].count("R:SSI") == 1
    assert manager.status()["requested_symbols"] == ["VCB", "FPT", "SSI"]
    assert "R:FPT" in manager.status()["foreign_room_channels"]
    assert "R:SSI" in manager.status()["foreign_room_channels"]


def test_current_watchlist_aggregate_uses_one_shared_cohort_and_truthful_coverage(
    monkeypatch: Any,
) -> None:
    client, manager, stream_client = _route_client(monkeypatch)

    waiting = client.get(
        "/api/v1/stocks/vn/foreign-flow/current-aggregate",
        params={"scope": "watchlist", "tickers": "FPT,SSI"},
    )
    assert waiting.status_code == 200
    assert waiting.json()["data_state"] == "waiting"

    manager.handle_message({
        "topic": "room.FPT",
        "data": {
            "t": "2026/07/29 10:08:00",
            "s": "FPT",
            "bq": 10,
            "sq": 4,
            "bv": 100,
            "sv": 40,
        },
    })
    response = client.get(
        "/api/v1/stocks/vn/foreign-flow/current-aggregate",
        params={"scope": "watchlist", "tickers": "FPT,SSI"},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, no-cache, max-age=0"
    payload = response.json()
    assert payload["status"] == "partial"
    assert payload["provider_session_date"] == "2026-07-29"
    assert payload["aggregate"]["foreign_buy_volume"] == 10
    assert payload["aggregate"]["foreign_sell_volume"] == 4
    assert payload["aggregate"]["foreign_net_value"] == 60
    assert payload["coverage"]["requested_symbol_count"] == 2
    assert payload["coverage"]["observed_symbol_count"] == 1
    assert payload["coverage"]["missing_symbols"] == ["SSI"]
    assert payload["display_series"][-1]["finality"] == "current_session_provisional"
    assert len(stream_client.ensure_calls) == 1
    assert stream_client.ensure_calls[0].count("R:FPT") == 1
    assert stream_client.ensure_calls[0].count("R:SSI") == 1
