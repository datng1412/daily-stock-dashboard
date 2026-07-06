# -*- coding: utf-8 -*-

import importlib.util
from pathlib import Path

from data_provider.ssi_fastconnect_fetcher import SsiFastConnectFetcher


def _load_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "diagnose_ssi_daily_ohlc.py"
    spec = importlib.util.spec_from_file_location("diagnose_ssi_daily_ohlc", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_daily_ohlc_diagnostic_sanitizer_redacts_secret_like_keys():
    script = _load_script()

    sanitized = script.sanitize_mapping(
        {
            "Authorization": "Bearer should-not-print",
            "accessToken": "token-value",
            "consumerSecret": "secret-value",
            "accountId": "account-value",
            "symbol": "FPT",
            "params": {"api_key": "key-value", "pageSize": 260},
        }
    )

    assert sanitized["Authorization"] == "<redacted>"
    assert sanitized["accessToken"] == "<redacted>"
    assert sanitized["consumerSecret"] == "<redacted>"
    assert sanitized["accountId"] == "<redacted>"
    assert sanitized["params"]["api_key"] == "<redacted>"
    assert sanitized["params"]["pageSize"] == 260
    assert "should-not-print" not in str(sanitized)
    assert "secret-value" not in str(sanitized)


def test_daily_ohlc_diagnostic_classifies_exception_and_429():
    script = _load_script()

    assert (
        script.classify_provider_payload(
            {
                "status": "unavailable",
                "error_type": "ssi_error",
                "http_status": 200,
                "code": "Exception",
            }
        )
        == "provider_unavailable"
    )
    assert (
        script.classify_provider_payload(
            {
                "status": "unavailable",
                "error_type": "ssi_error",
                "http_status": 200,
                "code": "429",
            }
        )
        == "rate_limited"
    )


def test_daily_ohlc_diagnostic_does_not_count_unavailable_envelope_as_raw_row():
    script = _load_script()
    fetcher = SsiFastConnectFetcher(enabled=False)

    raw_rows, normalized_rows = script.normalize_rows(
        fetcher,
        {
            "status": "unavailable",
            "reason": "SSI FastConnect request failed",
            "error_type": "ssi_error",
            "code": "Exception",
        },
    )

    assert raw_rows == []
    assert normalized_rows == []


def test_daily_ohlc_diagnostic_output_contains_no_secret_like_values(tmp_path):
    script = _load_script()
    payload = {
        "attempts": [
            {
                "endpoint": "DailyOhlc",
                "params": script.sanitize_mapping({"Authorization": "Bearer raw", "symbol": "FPT"}),
            }
        ]
    }
    output = tmp_path / "daily_ohlc.json"

    output.write_text(script.json.dumps(script.sanitize_value(payload), ensure_ascii=False), encoding="utf-8")
    text = output.read_text(encoding="utf-8")

    assert "Bearer raw" not in text
    assert "DailyOhlc" in text
    assert "FPT" in text
