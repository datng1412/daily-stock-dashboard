from pathlib import Path

from scripts.record_vn_proprietary_eod import run
from src.services.vietnam_proprietary_flow_eod_service import VietnamProprietaryFlowEodService
from src.services.vietnam_proprietary_flow_eod_store import VietnamProprietaryFlowEodStore


def _service(tmp_path):
    return VietnamProprietaryFlowEodService(VietnamProprietaryFlowEodStore(tmp_path / "store.json"))


def _argv(operation="--dry-run"):
    return [
        "--date", "2026-08-06", "--exchange", "HOSE",
        "--buy-value", "200", "--sell-value", "150",
        "--source-url", "https://example.test/official.pdf",
        "--source-file-unavailable", "--verified-by-user", operation,
    ]


def test_cli_value_only_dry_run_does_not_write(tmp_path):
    service = _service(tmp_path)
    code, result = run(_argv(), service=service)
    assert code == 0
    assert result["operation"] == "dry_run"
    assert result["net_value"] == 50
    assert not service.store.path.exists()


def test_cli_value_and_volume_dry_run(tmp_path):
    code, result = run(_argv()[:-1] + ["--buy-volume", "10", "--sell-volume", "4", "--dry-run"], service=_service(tmp_path))
    assert code == 0
    assert result["net_volume"] == 6
    assert result["complete_volume"] is True


def test_cli_persist_and_idempotent_repeat(tmp_path):
    service = _service(tmp_path)
    code, first = run(_argv("--persist"), service=service)
    code_again, second = run(_argv("--persist"), service=service)
    assert code == code_again == 0
    assert first["persisted"] is True
    assert second["idempotent"] is True
    assert second["store_path"] == str(service.store.path)


def test_cli_persist_failure_is_sanitized(tmp_path):
    argv = _argv("--persist")
    argv.remove("--verified-by-user")
    code, result = run(argv, service=_service(tmp_path))
    assert code == 2
    assert result["accepted"] is False
    assert "verified" in result["error"]
    assert str(tmp_path) not in result["error"]


def test_cli_pdf_hash_output_does_not_expose_full_path(tmp_path):
    pdf = tmp_path / "official.pdf"
    pdf.write_bytes(b"%PDF-1.7\nfixture")
    argv = [item for item in _argv() if item != "--source-file-unavailable"]
    argv[-1:-1] = ["--source-file", str(pdf)]
    code, result = run(argv, service=_service(tmp_path))
    assert code == 0
    assert len(result["source_file_hash"]) == 64
    assert "source_file" not in result
    assert str(tmp_path) not in str(result)
