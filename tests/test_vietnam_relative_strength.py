from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.v1.endpoints import stocks as stocks_endpoint
from server import app
from src.services.vietnam_relative_strength_service import (
    VietnamRelativeStrengthService,
    calculate_aligned_window,
    calculate_peer_window,
    clear_relative_strength_index_cache,
    normalize_close_history,
)


def sessions(count: int = 21) -> list[str]:
    return [(date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(count)]


def history(values: list[float], dates: list[str] | None = None) -> pd.DataFrame:
    selected_dates = dates or sessions(len(values))
    return pd.DataFrame({"date": selected_dates, "close": values})


class FakeMarketService:
    def __init__(self) -> None:
        dates = sessions()
        self.histories = {
            "FPT": history([100 + index for index in range(21)], dates),
            "HPG": history([50 + index * 0.5 for index in range(21)], dates),
            "SSI": history([30 for _ in range(21)], dates),
        }
        self.history_calls: list[tuple[str, bool]] = []
        self.component_calls: list[bool] = []

    def read_daily_ohlcv_history(self, symbol: str, **kwargs: Any) -> Dict[str, Any]:
        self.history_calls.append((symbol, bool(kwargs.get("force_refresh"))))
        return {
            "status": "ok",
            "cache_status": "hit",
            "dataframe": self.histories.get(symbol, pd.DataFrame()),
        }

    def build_index_components(self, index_code: str, **kwargs: Any) -> Dict[str, Any]:
        self.component_calls.append(bool(kwargs.get("force_refresh")))
        return {
            "status": "ok",
            "rows": [
                {"symbol": "FPT", "icb_code": "9537", "icb_name": "Technology"},
                {"symbol": "HPG", "icb_code": "9537", "icb_name": "Technology"},
                {"symbol": "SSI", "icb_code": "8777", "icb_name": "Financials"},
            ],
            "diagnostics": {"cache_status": "hit"},
        }


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    clear_relative_strength_index_cache()


def test_normalize_history_deduplicates_sorts_and_rejects_non_finite_or_non_positive() -> None:
    frame = pd.DataFrame({
        "date": ["2026-07-02", "2026-07-01", "2026-07-02", "bad", "2026-07-03"],
        "close": [2, 1, 3, 4, float("inf")],
    })
    assert normalize_close_history(frame) == {"2026-07-01": 1.0, "2026-07-02": 3.0}


@pytest.mark.parametrize(
    ("stock_end", "benchmark_end", "expected"),
    [(110, 105, 5.0), (90, 95, -5.0), (100, 100, 0.0)],
)
def test_relative_performance_is_percentage_point_subtraction(
    stock_end: float, benchmark_end: float, expected: float
) -> None:
    result = calculate_aligned_window(
        {"2026-01-01": 100, "2026-01-02": stock_end},
        {"2026-01-01": 100, "2026-01-02": benchmark_end},
        1,
    )
    assert result["relative_performance_pp"] == pytest.approx(expected)
    assert result["start_session"] == "2026-01-01"
    assert result["end_session"] == "2026-01-02"


def test_alignment_uses_common_provider_sessions_without_forward_fill() -> None:
    result = calculate_aligned_window(
        {"2026-01-01": 100, "2026-01-02": 101, "2026-01-03": 102},
        {"2026-01-01": 200, "2026-01-03": 204},
        1,
    )
    assert result["status"] == "ready"
    assert result["start_session"] == "2026-01-01"
    assert result["end_session"] == "2026-01-03"
    assert result["aligned_session_count"] == 2


def test_window_is_unavailable_instead_of_shortened() -> None:
    result = calculate_aligned_window({"2026-01-01": 100}, {"2026-01-01": 200}, 1)
    assert result["status"] == "unavailable"
    assert result["relative_performance_pp"] is None


def test_peer_mean_excludes_missing_peer_and_reports_partial() -> None:
    result = calculate_peer_window(
        {"2026-01-01": 100, "2026-01-02": 110},
        {
            "HPG": {"2026-01-01": 50, "2026-01-02": 55},
            "SSI": {"2026-01-01": 20},
        },
        1,
    )
    assert result["status"] == "partial"
    assert result["benchmark_return_pct"] == pytest.approx(10)
    assert result["usable_peer_count"] == 1
    assert result["missing_peers"] == ["SSI"]


def test_zero_peer_cohort_is_unavailable() -> None:
    result = calculate_peer_window(
        {"2026-01-01": 100, "2026-01-02": 110}, {}, 1
    )
    assert result["status"] == "unavailable"
    assert result["benchmark_return_pct"] is None


def test_service_builds_three_comparisons_and_excludes_selected_from_peers() -> None:
    market = FakeMarketService()
    dates = sessions()
    index_calls: list[tuple[str, str]] = []

    def index_reader(code: str, session: str) -> Dict[str, Any]:
        index_calls.append((code, session))
        offset = dates.index(session)
        base = 1000 if code == "VNINDEX" else 500
        return {"status": "ok", "rows": [{"date": session, "index_value": base + offset}]}

    payload = VietnamRelativeStrengthService(market, index_reader=index_reader).build("fpt")

    assert payload["status"] == "ready"
    assert set(payload["comparisons"]) == {"vnindex", "vn30", "industry"}
    assert payload["comparisons"]["industry"]["peer_symbols"] == ["HPG"]
    assert "FPT" not in payload["comparisons"]["industry"]["peer_symbols"]
    assert payload["comparisons"]["vnindex"]["windows"]["20d"]["complete"] is True
    assert len(index_calls) == 42
    assert market.history_calls == [("FPT", False), ("HPG", False)]
    assert payload["diagnostics"]["full_watchlist_hydration_used"] is False
    assert payload["diagnostics"]["fallback_used"] is False


def test_benchmark_points_are_cached_and_force_refresh_bypasses_cache() -> None:
    market = FakeMarketService()
    calls = 0

    def reader(code: str, session: str) -> Dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"status": "ok", "rows": [{"date": session, "index_value": 1000 + calls / 1000}]}

    service = VietnamRelativeStrengthService(market, index_reader=reader)
    first = service.build("FPT")
    second = service.build("FPT")
    assert calls == 42
    assert first["diagnostics"]["benchmark_provider_call_count"] == 42
    assert second["diagnostics"]["benchmark_provider_call_count"] == 0
    assert second["diagnostics"]["benchmark_cache_hit_count"] == 42
    service.build("FPT", force_refresh=True)
    assert calls == 84


def test_missing_benchmark_dates_leave_each_window_independent() -> None:
    market = FakeMarketService()
    dates = sessions()

    def reader(code: str, session: str) -> Dict[str, Any]:
        if code == "VN30" and session not in dates[-6:]:
            return {"status": "ok", "rows": []}
        return {"status": "ok", "rows": [{"date": session, "index_value": 1000}]}

    payload = VietnamRelativeStrengthService(market, index_reader=reader).build("FPT")
    windows = payload["comparisons"]["vn30"]["windows"]
    assert windows["1d"]["status"] == "ready"
    assert windows["5d"]["status"] == "ready"
    assert windows["20d"]["status"] == "unavailable"


def test_non_vn30_selected_ticker_keeps_index_comparisons_and_truthful_industry_unavailable() -> None:
    market = FakeMarketService()
    market.histories["VNM"] = market.histories["FPT"]

    def reader(code: str, session: str) -> Dict[str, Any]:
        return {"status": "ok", "rows": [{"date": session, "index_value": 1000}]}

    payload = VietnamRelativeStrengthService(market, index_reader=reader).build("VNM")
    assert payload["comparisons"]["vnindex"]["usable"] is True
    assert payload["comparisons"]["vn30"]["usable"] is True
    assert payload["comparisons"]["industry"]["status"] == "unavailable"
    assert payload["status"] == "partial"


def test_api_route_serializes_service_result_and_rejects_invalid_ticker(monkeypatch: pytest.MonkeyPatch) -> None:
    market = FakeMarketService()

    def reader(code: str, session: str) -> Dict[str, Any]:
        return {"status": "ok", "rows": [{"date": session, "index_value": 1000}]}

    monkeypatch.setattr(
        stocks_endpoint,
        "VietnamRelativeStrengthService",
        lambda: VietnamRelativeStrengthService(market, index_reader=reader),
    )
    client = TestClient(app)
    response = client.get("/api/v1/stocks/vn/relative-strength/FPT")
    assert response.status_code == 200
    assert response.json()["ticker"] == "FPT"
    assert response.json()["comparisons"]["vnindex"]["windows"]["1d"]["relative_performance_pp"] is not None
    invalid = client.get("/api/v1/stocks/vn/relative-strength/%21")
    assert invalid.status_code == 422
