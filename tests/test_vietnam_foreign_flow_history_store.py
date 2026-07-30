from __future__ import annotations

import json

import pytest

from src.services.vietnam_foreign_flow_history_store import (
    SCHEMA_VERSION,
    VietnamForeignFlowHistoryStore,
)
from src.services.vietnam_foreign_flow_service import (
    VietnamForeignFlowService,
    accepted_vietnam_foreign_flow_history,
    reset_vietnam_foreign_flow_state,
)


def _row(day: int, **overrides):
    row = {
        "date": f"2026-07-{day:02d}",
        "foreign_buy_volume": day * 100,
        "foreign_sell_volume": day * 40,
        "foreign_net_volume": day * 60,
        "foreign_buy_value": day * 1_000,
        "foreign_sell_value": day * 400,
        "foreign_net_value": day * 600,
    }
    row.update(overrides)
    return row


class _Fetcher:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def get_daily_stock_price(self, ticker, **kwargs):
        item = self.results[min(self.calls, len(self.results) - 1)]
        self.calls += 1
        return item


@pytest.fixture(autouse=True)
def _reset_state():
    reset_vietnam_foreign_flow_state()
    yield
    reset_vietnam_foreign_flow_state()


def _service(path, results):
    return VietnamForeignFlowService(
        _Fetcher(results),
        accepted_history_path=str(path),
    )


def test_completed_history_survives_service_restart(tmp_path):
    path = tmp_path / "accepted.json"
    first = _service(
        path,
        [{"status": "ok", "rows": [_row(27), _row(28)]}],
    )
    assert first.get_symbol_history("FPT", limit=2)["coverage"]["end_date"] == "2026-07-28"

    reset_vietnam_foreign_flow_state()
    restarted = _service(
        path,
        [{"status": "unavailable", "failure_class": "network_error", "rows": []}],
    )
    result = restarted.get_symbol_history("FPT", limit=2)

    assert result["data_state"] == "stale"
    assert [row["trading_date"] for row in result["rows"]] == [
        "2026-07-27",
        "2026-07-28",
    ]


def test_regressive_empty_and_failure_refreshes_preserve_durable_latest(tmp_path):
    path = tmp_path / "accepted.json"
    service = _service(
        path,
        [
            {"status": "ok", "rows": [_row(27), _row(28)]},
            {"status": "ok", "rows": [_row(27, foreign_buy_value=27_777)]},
        ],
    )
    service.get_symbol_history("FPT", limit=2)
    assert service.get_symbol_history("FPT", limit=2, force_refresh=True)["latest_row"]["trading_date"] == "2026-07-28"
    assert _service(
        path,
        [{"status": "ok", "rows": []}],
    ).get_symbol_history("FPT", limit=2, force_refresh=True)["latest_row"]["trading_date"] == "2026-07-28"
    assert _service(
        path,
        [{"status": "unavailable", "failure_class": "network_error", "rows": []}],
    ).get_symbol_history("FPT", limit=2, force_refresh=True)["latest_row"]["trading_date"] == "2026-07-28"

    reset_vietnam_foreign_flow_state()
    restored = _service(
        path,
        [{"status": "unavailable", "failure_class": "timeout", "rows": []}],
    ).get_symbol_history("FPT", limit=2)
    assert restored["latest_row"]["trading_date"] == "2026-07-28"
    assert restored["rows"][0]["foreign_buy_value"] == 27_777


def test_same_date_completed_correction_replaces_durable_row(tmp_path):
    path = tmp_path / "accepted.json"
    service = _service(
        path,
        [
            {"status": "ok", "rows": [_row(28)]},
            {"status": "ok", "rows": [_row(28, foreign_buy_value=999_000)]},
        ],
    )
    service.get_symbol_history("FPT", limit=1)
    corrected = service.get_symbol_history("FPT", limit=1, force_refresh=True)
    assert corrected["latest_row"]["foreign_buy_value"] == 999_000

    reset_vietnam_foreign_flow_state()
    restored = _service(
        path,
        [{"status": "unavailable", "failure_class": "timeout", "rows": []}],
    ).get_symbol_history("FPT", limit=1)
    assert restored["latest_row"]["foreign_buy_value"] == 999_000


def test_provisional_rows_are_never_persisted(tmp_path):
    path = tmp_path / "accepted.json"
    result = _service(
        path,
        [{
            "status": "ok",
            "rows": [
                _row(28),
                _row(29, foreign_finality="current_session_provisional"),
            ],
        }],
    ).get_symbol_history("FPT", limit=2)

    assert [row["trading_date"] for row in result["rows"]] == ["2026-07-28"]
    document = json.loads(path.read_text(encoding="utf-8"))
    assert list(document["symbols"]["FPT"]) == ["2026-07-28"]
    persisted = document["symbols"]["FPT"]["2026-07-28"]
    assert persisted["accepted_source"] == "ssi_fastconnect"
    assert persisted["accepted_finality"] == "daily_available"
    assert persisted["persisted_at"].endswith("+00:00")
    assert persisted["coverage_metadata"]["suspicious_zero_session"] is False
    assert "current_session_provisional" not in path.read_text(encoding="utf-8")


def test_symbol_scoping_and_bounds_are_preserved(tmp_path):
    path = tmp_path / "accepted.json"
    store = VietnamForeignFlowHistoryStore(path, max_symbols=2, max_rows_per_symbol=2)
    row = {
        "trading_date": "2026-07-28",
        "foreign_buy_volume": 10,
        "foreign_sell_volume": 2,
        "foreign_net_volume": 8,
        "foreign_buy_value": 100,
        "foreign_sell_value": 20,
        "foreign_net_value": 80,
        "field_presence": {},
        "suspicious_zero_session": False,
        "anomaly_code": None,
    }
    assert store.write({
        "SSI": {"2026-07-26": {**row, "trading_date": "2026-07-26"}, "2026-07-27": {**row, "trading_date": "2026-07-27"}, "2026-07-28": row},
        "FPT": {"2026-07-28": row},
        "HPG": {"2026-07-28": row},
    })

    loaded = store.load()
    assert list(loaded) == ["FPT", "HPG"]
    assert loaded["FPT"]["2026-07-28"]["foreign_net_value"] == 80


def test_corrupt_and_schema_mismatched_files_fail_closed(tmp_path):
    path = tmp_path / "accepted.json"
    path.write_text("{bad-json", encoding="utf-8")
    store = VietnamForeignFlowHistoryStore(path)
    assert store.load() == {}
    assert store.diagnostics()["status"] == "invalid"

    path.write_text(
        json.dumps({
            "schema_version": SCHEMA_VERSION + 1,
            "provider": "SSI",
            "source_endpoint": "daily_stock_price",
            "scope": "symbol",
            "symbols": {},
        }),
        encoding="utf-8",
    )
    assert store.load() == {}
    assert store.diagnostics()["last_error"] == "schema_mismatch"
    assert accepted_vietnam_foreign_flow_history(["FPT"]) == {"FPT": []}


def test_atomic_write_failure_preserves_previous_valid_file(tmp_path, monkeypatch):
    path = tmp_path / "accepted.json"
    store = VietnamForeignFlowHistoryStore(path)
    original = {
        "FPT": {
            "2026-07-28": {
                "trading_date": "2026-07-28",
                "foreign_buy_volume": 10,
                "foreign_sell_volume": 2,
                "foreign_net_volume": 8,
                "foreign_buy_value": 100,
                "foreign_sell_value": 20,
                "foreign_net_value": 80,
                "field_presence": {},
                "suspicious_zero_session": False,
                "anomaly_code": None,
            }
        }
    }
    assert store.write(original)
    previous_bytes = path.read_bytes()

    def _fail_replace(source, destination):
        raise OSError("simulated atomic replace failure")

    monkeypatch.setattr(
        "src.services.vietnam_foreign_flow_history_store.os.replace",
        _fail_replace,
    )
    assert store.write({}) is False
    assert path.read_bytes() == previous_bytes
    assert list(tmp_path.glob("*.tmp")) == []
