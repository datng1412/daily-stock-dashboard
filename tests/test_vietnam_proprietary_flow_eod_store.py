import json
from pathlib import Path

import pytest

from src.services.vietnam_proprietary_flow_eod_store import (
    ProprietaryFlowConflictError,
    ProprietaryFlowStoreError,
    VietnamProprietaryFlowEodStore,
)


def _row(**overrides):
    row = {
        "trading_date": "2026-08-06",
        "exchange": "HOSE",
        "buy_volume": None,
        "sell_volume": None,
        "net_volume": None,
        "buy_value": 200,
        "sell_value": 150,
        "net_value": 50,
        "source_type": "official_exchange_pdf_manual_entry",
        "source_url": "https://example.test/hose.pdf",
        "source_title": "Official publication",
        "source_file_name": None,
        "source_file_hash": None,
        "source_file_size": None,
        "source_evidence_strength": "OFFICIAL_URL_USER_VERIFIED",
        "verified_by_user": True,
        "imported_at": "2026-08-06T12:00:00+00:00",
        "finality": "completed_daily",
        "complete_value": True,
        "complete_volume": False,
        "complete": True,
        "data_quality": "accepted_value_only",
        "warnings": ["source_pdf_unavailable_hash_not_recorded"],
    }
    row.update(overrides)
    return row


def test_first_persist_restart_restoration_and_deterministic_document(tmp_path):
    path = tmp_path / "store.json"
    result = VietnamProprietaryFlowEodStore(path).persist(_row())
    restored = VietnamProprietaryFlowEodStore(path).load()

    assert result == {**result, "persisted": True, "idempotent": False, "replaced": False}
    assert restored[0]["net_value"] == 50
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    assert document["rows"][0]["trading_date"] == "2026-08-06"
    assert not list(tmp_path.glob("*.tmp"))


def test_same_canonical_row_is_idempotent_and_does_not_rewrite(tmp_path):
    store = VietnamProprietaryFlowEodStore(tmp_path / "store.json")
    store.persist(_row())
    before = store.path.read_bytes()
    result = store.persist(_row(imported_at="2026-08-06T13:00:00+00:00"))

    assert result["idempotent"] is True
    assert result["persisted"] is False
    assert store.path.read_bytes() == before


def test_same_date_different_values_rejected_by_default(tmp_path):
    store = VietnamProprietaryFlowEodStore(tmp_path / "store.json")
    store.persist(_row())
    with pytest.raises(ProprietaryFlowConflictError, match="different row"):
        store.persist(_row(buy_value=201, net_value=51))


def test_replace_requires_reason_and_records_audit(tmp_path):
    store = VietnamProprietaryFlowEodStore(tmp_path / "store.json")
    store.persist(_row())
    replacement = _row(
        buy_value=210,
        net_value=60,
        source_file_name="official.pdf",
        source_file_hash="a" * 64,
        source_file_size=8,
        source_evidence_strength="OFFICIAL_PDF_HASHED",
        imported_at="2026-08-06T14:00:00+00:00",
        warnings=[],
    )
    with pytest.raises(ProprietaryFlowConflictError, match="replacement_reason"):
        store.persist(replacement, replace=True)
    result = store.persist(replacement, replace=True, replacement_reason="Corrected manual transcription")
    row = VietnamProprietaryFlowEodStore(store.path).load()[0]

    assert result["replaced"] is True
    assert row["data_quality"] == "replacement"
    assert row["replacement_reason"] == "Corrected manual transcription"
    assert row["previous_imported_at"] == "2026-08-06T12:00:00+00:00"
    assert row["replaced_at"]


def test_strong_evidence_cannot_be_replaced_by_weak_evidence(tmp_path):
    store = VietnamProprietaryFlowEodStore(tmp_path / "store.json")
    store.persist(_row(source_evidence_strength="OFFICIAL_PDF_HASHED", source_file_hash="a" * 64))
    with pytest.raises(ProprietaryFlowConflictError, match="weaker"):
        store.persist(_row(buy_value=210, net_value=60), replace=True, replacement_reason="wrong")


def test_value_only_row_can_be_strengthened_with_volume(tmp_path):
    store = VietnamProprietaryFlowEodStore(tmp_path / "store.json")
    store.persist(_row())
    result = store.persist(
        _row(
            buy_volume=10,
            sell_volume=4,
            net_volume=6,
            complete_volume=True,
            data_quality="accepted",
        ),
        replace=True,
        replacement_reason="Added verified gross volume",
    )
    assert result["replaced"] is True
    assert store.load()[0]["net_volume"] == 6


def test_corrupt_store_is_reported_truthfully(tmp_path):
    path = tmp_path / "store.json"
    path.write_text("not-json", encoding="utf-8")
    store = VietnamProprietaryFlowEodStore(path)
    with pytest.raises(ProprietaryFlowStoreError):
        store.load()
    assert store.diagnostics()["status"] == "invalid"


def test_store_is_separate_from_foreign_flow_history(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_CACHE_DIR", str(tmp_path))
    store = VietnamProprietaryFlowEodStore()
    store.persist(_row())
    assert store.path.name == "vietnam_proprietary_flow_eod.v1.json"
    assert not (tmp_path / "vietnam_foreign_flow_accepted.v1.json").exists()
