"""Deterministic tests for bounded SSI streaming last-known snapshots."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from data_provider.ssi_streaming_realtime import SsiStreamingRealtimeManager
from data_provider.ssi_streaming_snapshot_store import SsiStreamingSnapshotStore


def _now_factory(now: datetime):
    return lambda: now


def _contexts():
    return {
        "realtime": {"FPT": {"ticker": "FPT", "price": 100.0, "stream_timestamp": "2026-07-10T08:00:00+00:00", "forbidden_private_value": "never-save"}},
        "order_book": {"FPT": {"ticker": "FPT", "bids": [{"level": 1, "price": 99.0, "volume": 100}], "asks": [{"level": 1, "price": 101.0, "volume": 100}]}},
        "trades": {"FPT": [{"ticker": "FPT", "price": 100.0, "volume": 10, "timestamp": "2026-07-10T08:00:00+00:00", "id": "a"}, {"ticker": "FPT", "price": 100.0, "volume": 10, "timestamp": "2026-07-10T08:00:00+00:00", "id": "a"}]},
        "foreign_room": {"FPT": {"ticker": "FPT", "current_room": 20.0}},
        "market_index": {"VNINDEX": {"index_code": "VNINDEX", "index_value": 1234.5}},
        "session": {"FPT": {"ticker": "FPT", "trading_session": "ATO"}},
    }


def test_snapshot_round_trip_is_allowlisted_bounded_and_atomic(tmp_path):
    now = datetime(2026, 7, 10, 8, 5, tzinfo=timezone.utc)
    path = tmp_path / "ssi_streaming_last_known.v1.json"
    store = SsiStreamingSnapshotStore(enabled=True, path=str(path), trade_limit=50, now_func=_now_factory(now))
    store.mark_dirty()

    assert store.flush_now(_contexts) is True
    assert path.exists()
    loaded = SsiStreamingSnapshotStore(enabled=True, path=str(path), now_func=_now_factory(now)).load()

    assert loaded["provider"] == "SSI"
    assert loaded["contexts"]["trades"]["FPT"] == [{"ticker": "FPT", "symbol": "FPT", "price": 100.0, "volume": 10, "timestamp": "2026-07-10T08:00:00+00:00", "id": "a"}]
    assert "forbidden_private_value" not in str(loaded)
    assert not list(tmp_path.glob("*.tmp"))


def test_snapshot_load_rejects_invalid_and_expired_files_without_raising(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text("{not json", encoding="utf-8")
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    store = SsiStreamingSnapshotStore(enabled=True, path=str(path), now_func=_now_factory(now))
    assert store.load()["contexts"]["realtime"] == {}
    assert store.diagnostics()["snapshot_status"] == "invalid"

    path.write_text('{"schema_version":1,"provider":"SSI","captured_at":"2026-06-01T00:00:00+00:00","trading_date":"2026-06-01","contexts":{}}', encoding="utf-8")
    assert store.load()["contexts"]["realtime"] == {}
    assert store.diagnostics()["snapshot_status"] == "expired"


def test_dirty_writes_are_debounced_and_close_flushes_once(tmp_path):
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    store = SsiStreamingSnapshotStore(enabled=True, path=str(tmp_path / "snapshot.json"), write_interval_seconds=5, now_func=_now_factory(now))
    store.mark_dirty()
    assert store.flush_if_due(_contexts) is True
    store.mark_dirty()
    assert store.flush_if_due(_contexts) is False
    assert store.close(_contexts) is True
    assert store.diagnostics()["snapshot_write_count"] == 2


def test_manager_restore_is_persisted_stale_and_live_row_replaces_it(tmp_path):
    now = datetime(2026, 7, 10, 8, tzinfo=timezone.utc)
    store = SsiStreamingSnapshotStore(enabled=True, path=str(tmp_path / "snapshot.json"), now_func=_now_factory(now))
    store.mark_dirty()
    assert store.flush_now(_contexts)
    snapshot = store.load()
    manager = SsiStreamingRealtimeManager(enabled=True, time_func=lambda: now.timestamp())

    restored = manager.restore_persisted_snapshot(snapshot)
    quote, status, _ = manager.cache.get("FPT")
    assert restored["realtime"] == 1
    assert status == "persisted_stale"
    assert quote and quote["snapshot_source"] == "persisted" and quote["is_stale"] is True
    assert manager.cache.put_rows([{"ticker": "FPT", "price": 101.0}]) == 1
    live_quote, live_status, _ = manager.cache.get("FPT")
    assert live_status == "hit"
    assert live_quote and live_quote.get("snapshot_source") is None


def test_running_manager_exposes_persisted_contexts_without_marking_them_live(tmp_path):
    now = datetime(2026, 7, 10, 8, tzinfo=timezone.utc)
    store = SsiStreamingSnapshotStore(enabled=True, path=str(tmp_path / "snapshot.json"), now_func=_now_factory(now))
    store.mark_dirty()
    assert store.flush_now(_contexts)
    manager = SsiStreamingRealtimeManager(
        enabled=True,
        time_func=lambda: now.timestamp(),
        client_factory=lambda: _NoopClient(),
    )
    manager.restore_persisted_snapshot(store.load())
    assert manager.start(["FPT"])["manager_state"] == "running"

    realtime = manager.snapshot(["FPT"])
    order_book = manager.order_book("FPT")
    trades = manager.trade_tape("FPT")
    foreign_room = manager.foreign_room("FPT")
    session = manager.session_status("FPT")

    assert realtime["cache_status"] == "persisted_stale"
    assert realtime["quotes"][0]["snapshot_source"] == "persisted"
    assert order_book["order_book"]["snapshot_source"] == "persisted"
    assert trades["trades"][0]["snapshot_source"] == "persisted"
    assert foreign_room["foreign_room"]["snapshot_source"] == "persisted"
    assert session["session_status"]["snapshot_source"] == "persisted"


class _NoopClient:
    def start(self, on_message, on_error, channels):
        self.on_message = on_message

    def stop(self):
        return None


def test_snapshot_rejects_future_timestamp(tmp_path):
    now = datetime(2026, 7, 10, tzinfo=timezone.utc)
    path = tmp_path / "snapshot.json"
    future = now + timedelta(minutes=6)
    path.write_text(f'{{"schema_version":1,"provider":"SSI","captured_at":"{future.isoformat()}","trading_date":"2026-07-10","contexts":{{}}}}', encoding="utf-8")
    store = SsiStreamingSnapshotStore(enabled=True, path=str(path), now_func=_now_factory(now))
    assert store.load()["contexts"]["realtime"] == {}
    assert store.diagnostics()["snapshot_status"] == "expired"
