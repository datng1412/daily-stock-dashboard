import json

import pytest

from src.services.vietnam_proprietary_flow_eod_service import (
    ProprietaryFlowValidationError,
    VietnamProprietaryFlowEodService,
)
from src.services.vietnam_proprietary_flow_eod_store import VietnamProprietaryFlowEodStore


def _service(tmp_path):
    return VietnamProprietaryFlowEodService(VietnamProprietaryFlowEodStore(tmp_path / "store.json"))


def _args(**overrides):
    values = {
        "trading_date": "2026-08-06",
        "exchange": "HOSE",
        "buy_value": 200,
        "sell_value": 150,
        "source_url": "https://example.test/official.pdf",
        "verified_by_user": True,
        "source_file_unavailable": True,
    }
    values.update(overrides)
    return values


def test_value_only_preview_derives_net_and_keeps_volume_null(tmp_path):
    result = _service(tmp_path).preview_candidate(**_args())
    assert result["accepted"] is True
    assert result["would_persist"] is False
    assert result["net_value"] == 50
    assert result["buy_volume"] is None
    assert result["net_volume"] is None
    assert result["data_quality"] == "accepted_value_only"


def test_value_and_volume_preview_reconciles_explicit_zero(tmp_path):
    result = _service(tmp_path).preview_candidate(**_args(
        buy_value=0,
        sell_value=0,
        net_value=0,
        buy_volume=0,
        sell_volume=0,
        net_volume=0,
    ))
    assert result["net_value"] == 0
    assert result["net_volume"] == 0
    assert result["complete_volume"] is True
    assert result["data_quality"] == "accepted"


@pytest.mark.parametrize("field", ["buy_value", "sell_value"])
def test_negative_gross_value_rejected(tmp_path, field):
    with pytest.raises(ProprietaryFlowValidationError, match="nonnegative"):
        _service(tmp_path).preview_candidate(**_args(**{field: -1}))


def test_bool_and_non_integer_value_rejected(tmp_path):
    with pytest.raises(ProprietaryFlowValidationError, match="integer"):
        _service(tmp_path).preview_candidate(**_args(buy_value=True))
    with pytest.raises(ProprietaryFlowValidationError, match="integer"):
        _service(tmp_path).preview_candidate(**_args(buy_value="200"))


def test_supplied_net_value_mismatch_rejected(tmp_path):
    with pytest.raises(ProprietaryFlowValidationError, match="net_value"):
        _service(tmp_path).preview_candidate(**_args(net_value=49))


def test_volume_pair_and_net_reconciliation(tmp_path):
    with pytest.raises(ProprietaryFlowValidationError, match="supplied together"):
        _service(tmp_path).preview_candidate(**_args(buy_volume=10))
    with pytest.raises(ProprietaryFlowValidationError, match="net_volume"):
        _service(tmp_path).preview_candidate(**_args(buy_volume=10, sell_volume=4, net_volume=5))


def test_persist_requires_verified_url_and_source_acknowledgment(tmp_path):
    service = _service(tmp_path)
    with pytest.raises(ProprietaryFlowValidationError, match="verified"):
        service.persist_candidate(**_args(verified_by_user=False))
    with pytest.raises(ProprietaryFlowValidationError, match="HTTP"):
        service.persist_candidate(**_args(source_url=""))
    with pytest.raises(ProprietaryFlowValidationError, match="source-file-unavailable"):
        service.persist_candidate(**_args(source_file_unavailable=False))


def test_pdf_is_hashed_without_persisting_full_path_or_content(tmp_path):
    pdf = tmp_path / "official report.pdf"
    pdf.write_bytes(b"%PDF-1.7\nsynthetic test bytes")
    service = _service(tmp_path)
    result = service.persist_candidate(**_args(source_file=pdf, source_file_unavailable=False))
    stored = json.loads(service.store.path.read_text(encoding="utf-8"))["rows"][0]

    assert result["persisted"] is True
    assert stored["source_file_name"] == "official report.pdf"
    assert len(stored["source_file_hash"]) == 64
    assert str(tmp_path) not in service.store.path.read_text(encoding="utf-8")
    assert "synthetic test bytes" not in service.store.path.read_text(encoding="utf-8")


@pytest.mark.parametrize("kind", ["missing", "extension", "signature"])
def test_invalid_source_file_rejected(tmp_path, kind):
    path = tmp_path / ("missing.pdf" if kind == "missing" else "file.txt" if kind == "extension" else "file.pdf")
    if kind != "missing":
        path.write_bytes(b"not a pdf")
    with pytest.raises(ProprietaryFlowValidationError):
        _service(tmp_path).preview_candidate(**_args(source_file=path, source_file_unavailable=False))


def test_latest_history_order_limit_and_state(tmp_path):
    service = _service(tmp_path)
    assert service.get_latest()["data_state"] == "no_data"
    for day in ("2026-08-04", "2026-08-06", "2026-08-05"):
        service.persist_candidate(**_args(trading_date=day))
    latest = service.get_latest("hose")
    history = service.get_history("HOSE", 2)
    assert latest["latest"]["trading_date"] == "2026-08-06"
    assert history["count"] == 2
    assert [row["trading_date"] for row in history["series"]] == ["2026-08-05", "2026-08-06"]
    assert history["series"][0]["buy_volume"] is None


def test_invalid_exchange_and_history_limit_rejected(tmp_path):
    service = _service(tmp_path)
    with pytest.raises(ProprietaryFlowValidationError, match="HOSE"):
        service.get_latest("HNX")
    with pytest.raises(ProprietaryFlowValidationError, match="between"):
        service.get_history("HOSE", 251)


def test_storage_failure_maps_to_storage_error(tmp_path):
    path = tmp_path / "store.json"
    path.write_text("broken", encoding="utf-8")
    service = VietnamProprietaryFlowEodService(VietnamProprietaryFlowEodStore(path))
    assert service.get_latest()["data_state"] == "storage_error"
    assert service.get_history()["status"] == "error"
