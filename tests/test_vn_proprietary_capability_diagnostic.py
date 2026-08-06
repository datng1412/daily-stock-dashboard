from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import pytest

from scripts import diagnose_vn_proprietary_capability as diagnostic


def row(**overrides):
    value = {
        "Ticker": "FPT",
        "TradingDate": "2026-08-05T00:00:00",
        "UpdateDate": "2026-08-05T10:00:00",
        "TotalBuyTradeVolume": 10,
        "TotalSellTradeVolume": 4,
        "TotalBuyTradeValue": 100,
        "TotalSellTradeValue": 40,
    }
    value.update(overrides)
    return value


def observation(**overrides):
    return diagnostic.normalize_observation("provider", "operation", row(**overrides))


def test_current_date_detection():
    assert observation()["trading_date"] == "2026-08-05"


def test_previous_session_only_is_historical():
    old = observation(TradingDate="2026-08-04")
    assert diagnostic.classify_capability([old], current_date="2026-08-05", market_phase="active") == "HISTORICAL_ONLY"


def test_explicit_zero_is_distinct_from_missing():
    zero = observation(TotalBuyTradeVolume=0)
    missing = observation()
    missing["field_presence"]["buy_volume"] = "FIELD_ABSENT"
    assert zero["field_presence"]["buy_volume"] == "FIELD_PRESENT_ZERO"
    assert missing["field_presence"]["buy_volume"] == "FIELD_ABSENT"


def test_gross_field_presence_is_audited():
    item = observation()
    assert item["field_presence"]["buy_volume"] == "FIELD_PRESENT_VALUE"
    assert item["aliases_used"]["buy_volume"] == "TotalBuyTradeVolume"


def test_net_derives_only_from_complete_gross_pair():
    complete = observation()
    incomplete = observation(TotalSellTradeVolume=None)
    assert complete["net_volume"] == 6
    assert incomplete["net_volume"] is None


def test_provider_timestamp_advancement_supports_polling_classification():
    first = observation(UpdateDate="2026-08-05T10:00:00")
    second = observation(UpdateDate="2026-08-05T10:01:00", TotalBuyTradeVolume=11)
    assert diagnostic.classify_capability([first, second], current_date="2026-08-05", market_phase="active") == "NEAR_REALTIME_POLLING"


def test_same_value_repeated_snapshot_does_not_prove_intraday():
    item = observation()
    assert diagnostic.classify_capability([item, dict(item)], current_date="2026-08-05", market_phase="active") == "UNAVAILABLE"


def test_changing_cumulative_snapshots_are_not_summed():
    first = observation(TotalBuyTradeVolume=10)
    second = observation(TotalBuyTradeVolume=12, UpdateDate="2026-08-05T10:01:00")
    assert second["buy_volume"] == 12
    assert second["buy_volume"] != first["buy_volume"] + 12


def test_snapshot_decrease_is_preserved_as_correction():
    corrected = observation(TotalBuyTradeVolume=8, UpdateDate="2026-08-05T10:01:00")
    assert corrected["buy_volume"] == 8


def test_delta_semantics_requires_push_proof_for_realtime():
    first = observation()
    second = observation(TotalBuyTradeVolume=11, UpdateDate="2026-08-05T10:01:00")
    assert diagnostic.classify_capability([first, second], current_date="2026-08-05", market_phase="active") != "REALTIME"


def test_push_proof_can_classify_realtime():
    first = observation()
    second = observation(TotalBuyTradeVolume=11)
    assert diagnostic.classify_capability([first, second], current_date="2026-08-05", market_phase="active", push_proven=True) == "REALTIME"


def test_bulk_and_symbol_reconciliation_uses_values_not_missing_zero():
    symbol = observation()
    bulk = observation()
    assert symbol["net_value"] == bulk["net_value"]


def test_match_deal_total_reconciliation():
    total = {"buy_volume": 10, "sell_volume": 7, "buy_value": 100, "sell_value": 70}
    parts = {
        "match_buy_volume": 6, "match_sell_volume": 4, "match_buy_value": 60, "match_sell_value": 40,
        "deal_buy_volume": 4, "deal_sell_volume": 3, "deal_buy_value": 40, "deal_sell_value": 30,
    }
    assert diagnostic.reconciliation(total, parts, parts) is True


@pytest.mark.parametrize(("message", "expected"), [
    ("HTTP 401 unauthorized", "AUTHENTICATION_FAILURE"),
    ("HTTP 403 membership required", "ENTITLEMENT_FAILURE"),
    ("HTTP 429 rate limit", "RATE_LIMITED"),
    ("connection timeout", "NETWORK_FAILURE"),
])
def test_error_classification(message, expected):
    assert diagnostic.classify_error(message) == expected


def test_bounded_retry_honors_retry_after():
    assert diagnostic.bounded_retry_delays(90) == (60.0,)


def test_bounded_probe_duration_and_interval(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(diagnostic, "inspect_vnstock", lambda **kwargs: diagnostic.ProbeResult(
        "Vnstock Data", "operation", "UNAVAILABLE", (), failure_class="PROVIDER_PACKAGE_MISSING"
    ))
    monkeypatch.setattr(diagnostic.sys, "argv", [
        "diagnostic", "--duration-seconds", "9999", "--interval-seconds", "1",
        "--output-dir", str(tmp_path), "--cleanup",
    ])
    assert diagnostic.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["duration_seconds"] == diagnostic.MAX_DURATION_SECONDS
    assert payload["interval_seconds"] == diagnostic.MIN_INTERVAL_SECONDS


def test_output_contains_no_credentials(tmp_path):
    result = diagnostic.ProbeResult(
        "FiinGroup DataFeed",
        diagnostic.FIIN_ENDPOINT,
        "POST_CLOSE_SAME_DAY",
        (observation(),),
    )
    json_path, csv_path = diagnostic._write_outputs(tmp_path, [result])
    rendered = json_path.read_text("utf-8") + csv_path.read_text("utf-8")
    assert "password" not in rendered.lower()
    assert "authorization" not in rendered.lower()
    assert "FIELD_PRESENT_VALUE" in rendered


def test_diagnostic_does_not_reference_production_cache():
    source = Path(diagnostic.__file__).read_text("utf-8")
    assert "production_cache_mutated\": False" in source
    assert "DATA_CACHE_DIR" not in source


def test_post_close_current_date_is_post_close_only():
    assert diagnostic.classify_capability([observation()], current_date="2026-08-05", market_phase="post_close") == "POST_CLOSE_SAME_DAY"


def test_eod_only_can_remain_a_documented_provider_classification():
    assert "END_OF_DAY_ONLY" in diagnostic.CAPABILITIES


def test_both_provider_unavailable_keeps_p1_gate_closed(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(diagnostic, "inspect_fiin", lambda: diagnostic.ProbeResult(
        "FiinGroup DataFeed", diagnostic.FIIN_ENDPOINT, "UNAVAILABLE", (), failure_class="CONFIGURATION_REQUIRED"
    ))
    monkeypatch.setattr(diagnostic, "inspect_vnstock", lambda **kwargs: diagnostic.ProbeResult(
        "Vnstock Data", "operation", "UNAVAILABLE", (), failure_class="PROVIDER_PACKAGE_MISSING"
    ))
    monkeypatch.setattr(diagnostic.sys, "argv", ["diagnostic", "--output-dir", str(tmp_path), "--cleanup"])
    assert diagnostic.main() == 0
    assert json.loads(capsys.readouterr().out)["p1_gate_entered"] is False


def test_fiin_contract_is_never_treated_as_configured_runtime():
    result = diagnostic.inspect_fiin()
    assert result.capability == "UNAVAILABLE"
    assert result.failure_class == "CONFIGURATION_REQUIRED"


def test_installed_fiinquant_contract_exposes_proprietary_gross_fields():
    contract = diagnostic.inspect_fiinquant_contract()
    assert contract["package_available"] is True
    assert contract["operation_available"] is True
    assert set(contract["contract_fields"]) == set(
        diagnostic.FIINQUANT_PROPRIETARY_FIELDS
    )


def test_fiinquant_proprietary_aliases_preserve_raw_field_presence():
    item = diagnostic.normalize_observation(
        "FiinQuantX",
        diagnostic.FIINQUANT_OPERATION,
        {
            "ticker": "FPT",
            "tradingDate": "2026-08-05",
            "proprietaryTotalBuyTradeVolume": 0,
            "proprietaryTotalSellTradeVolume": 20,
            "proprietaryTotalBuyTradeValue": 0,
            "proprietaryTotalSellTradeValue": 200,
        },
    )
    assert item["symbol"] == "FPT"
    assert item["field_presence"]["buy_volume"] == "FIELD_PRESENT_ZERO"
    assert item["aliases_used"]["buy_volume"] == "proprietaryTotalBuyTradeVolume"
    assert item["net_value"] == -200


def test_fiinquant_authenticated_historical_gross_rows_select_post_close_outcome():
    result = diagnostic.ProbeResult(
        provider="FiinQuantX",
        operation=diagnostic.FIINQUANT_OPERATION,
        capability="HISTORICAL_ONLY",
        observations=(observation(TradingDate="2026-08-04"),),
        authentication="AUTHENTICATED",
    )
    assert diagnostic.fiinquant_outcome(result, phase="post_close") == (
        "VN_PROPRIETARY_FIINQUANT_PROPRIETARY_CAPABILITY_FOUND_POST_CLOSE"
    )


def test_fiinquant_error_outcomes_are_typed():
    base = dict(
        provider="FiinQuantX",
        operation=diagnostic.FIINQUANT_OPERATION,
        capability="UNAVAILABLE",
        observations=(),
    )
    assert diagnostic.fiinquant_outcome(
        diagnostic.ProbeResult(**base, failure_class="AUTHENTICATION_FAILURE"),
        phase="post_close",
    ) == "VN_PROPRIETARY_FIINQUANT_AUTH_FAILED"
    assert diagnostic.fiinquant_outcome(
        diagnostic.ProbeResult(**base, failure_class="ENTITLEMENT_FAILURE"),
        phase="post_close",
    ) == "VN_PROPRIETARY_FIINQUANT_ENTITLEMENT_REQUIRED"


def test_fiinquant_login_requires_explicit_true_state():
    class Client:
        is_login = True

    class Rejected:
        is_login = False

    assert diagnostic._fiinquant_logged_in(Client()) is True
    assert diagnostic._fiinquant_logged_in(Rejected()) is False
    assert diagnostic._fiinquant_logged_in(object()) is False


def test_free_vnstock_is_not_sponsor_package(monkeypatch):
    monkeypatch.setattr(diagnostic.importlib.util, "find_spec", lambda name: None)
    result = diagnostic.inspect_vnstock(live=True, symbols=("FPT",), duration=0, interval=5)
    assert result.failure_class == "PROVIDER_PACKAGE_MISSING"


def test_market_phase_uses_vietnam_session_windows():
    assert diagnostic.market_phase(datetime(2026, 8, 5, 10, 0)) == "active"
    assert diagnostic.market_phase(datetime(2026, 8, 5, 16, 0)) == "post_close"


def test_missing_row_never_becomes_zero():
    item = diagnostic.normalize_observation("provider", "operation", None)
    assert item["buy_volume"] is None
    assert item["field_presence"]["buy_volume"] == "PROVIDER_ROW_MISSING"
