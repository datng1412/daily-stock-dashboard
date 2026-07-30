from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from ssi_sdk.models import ForeignRoomMessage

from scripts.diagnose_vn_current_foreign_flow import (
    candidate_inventory,
    classify_numeric,
    classify_sample_changes,
    classify_delay,
    evaluate_daily_stock_price_samples,
    evaluate_room_samples,
    evaluate_semantic_gate,
    evidence_matrix,
    reconcile_evidence,
    room_sample_from_message,
    sample_from_row,
    select_latest_room_snapshot,
    V2_TO_V3_FIELD_MAP,
)


DATE = "2026-07-28"


def _row(**overrides):
    row = {
        "date": DATE,
        "foreign_buy_volume": 100,
        "foreign_sell_volume": 80,
        "foreign_buy_value": 7_000_000,
        "foreign_sell_value": 5_500_000,
        "_foreign_field_presence": {
            "foreign_buy_volume": "nonzero",
            "foreign_sell_volume": "nonzero",
            "foreign_buy_value": "nonzero",
            "foreign_sell_value": "nonzero",
        },
    }
    row.update(overrides)
    return row


def _sample(row=None, *, number=1):
    return sample_from_row(
        _row() if row is None else row,
        symbol="FPT",
        sample_number=number,
        sampled_at=f"{DATE}T10:00:0{number}+07:00",
        expected_session_date=DATE,
    )


def test_candidate_without_explicit_foreign_fields_fails():
    inventory = {item["key"]: item for item in candidate_inventory()}
    assert inventory["x"]["gate_status"] == "failed"
    assert inventory["x"]["explicit_foreign_fields"] is False


def test_r_classifies_room_capacity_and_explicit_flow_independently():
    inventory = {item["key"]: item for item in candidate_inventory()}
    assert "room capacity" in inventory["r"]["current_purpose"]
    assert "foreign counters" in inventory["r"]["current_purpose"]
    assert inventory["r"]["gate_status"] == "active_session_pending"


def test_x_trade_without_participant_identity_fails():
    inventory = {item["key"]: item for item in candidate_inventory()}
    assert "no foreign participant" in inventory["x_trade"]["rejection_reason"]


def test_current_date_daily_row_with_explicit_fields_is_candidate_but_inconclusive_once():
    result = evaluate_daily_stock_price_samples([_sample()], expected_session_date=DATE)
    assert result["volume_pair_observed"] is True
    assert result["value_pair_observed"] is True
    assert result["candidate_status"] == "inconclusive"


def test_http_success_without_current_date_row_is_inconclusive():
    sample = _sample(_row(date="2026-07-25"))
    result = evaluate_daily_stock_price_samples([sample], expected_session_date=DATE)
    assert result["current_date_sample_count"] == 0
    assert result["gate_status"] == "inconclusive"


def test_zero_only_samples_are_inconclusive():
    zero = _row(
        foreign_buy_volume=0,
        foreign_sell_volume=0,
        foreign_buy_value=0,
        foreign_sell_value=0,
    )
    result = evaluate_daily_stock_price_samples(
        [_sample(zero, number=1), _sample(zero, number=2)],
        expected_session_date=DATE,
    )
    assert result["zero_only"] is True
    assert result["candidate_status"] == "inconclusive"


def test_multiple_changing_explicit_samples_support_candidacy():
    second = _row(
        foreign_buy_volume=120,
        foreign_sell_volume=90,
        foreign_buy_value=8_000_000,
        foreign_sell_value=6_000_000,
    )
    result = evaluate_daily_stock_price_samples(
        [_sample(number=1), _sample(second, number=2)],
        expected_session_date=DATE,
    )
    assert result["candidate_status"] == "candidate_found"
    assert result["gate_status"] == "provider_contract_blocked"


def test_missing_provider_timestamp_remains_unresolved():
    result = evaluate_daily_stock_price_samples([_sample()], expected_session_date=DATE)
    assert result["provider_timestamp_known"] is False


def test_unknown_snapshot_delta_blocks_full_pass():
    result = evaluate_daily_stock_price_samples(
        [_sample(number=1), _sample(_row(foreign_buy_volume=110), number=2)],
        expected_session_date=DATE,
    )
    assert result["snapshot_delta"] == "unknown"
    assert result["gate_status"] != "passed"


def test_known_cumulative_snapshot_can_pass_semantic_subgate():
    assert evaluate_semantic_gate(
        snapshot_delta="cumulative_snapshot",
        cumulative_behavior_observed=True,
    )["status"] == "passed"


def test_delta_without_stable_sequence_fails_production_authority():
    assert evaluate_semantic_gate(
        snapshot_delta="delta_event",
        stable_event_sequence=False,
        reconnect_replay_known=True,
    )["status"] == "failed"


def test_counter_decrease_is_correction_or_reset_candidate():
    result = evaluate_daily_stock_price_samples(
        [_sample(number=1), _sample(_row(foreign_buy_volume=90), number=2)],
        expected_session_date=DATE,
    )
    assert result["counter_decrease_behavior"] == "correction_or_reset_candidate"


def test_session_reset_and_reconciliation_remain_pending():
    result = evaluate_daily_stock_price_samples([_sample()], expected_session_date=DATE)
    assert result["session_reset"] == "pending"
    assert result["reconciliation"] == "pending"


def test_explicit_zero_remains_zero():
    classified = classify_numeric(0, present=True)
    assert classified == {
        "present": True,
        "raw_type": "int",
        "semantic": "explicit_zero",
        "value": 0,
    }


def test_null_remains_null():
    classified = classify_numeric(None, present=True)
    assert classified["semantic"] == "null"
    assert classified["value"] is None


def test_missing_remains_null():
    classified = classify_numeric(None, present=False)
    assert classified["semantic"] == "missing"
    assert classified["value"] is None


@pytest.mark.parametrize("value", ["bad", True, float("nan"), -1])
def test_malformed_remains_null(value):
    classified = classify_numeric(value, present=True)
    assert classified["semantic"] == "malformed"
    assert classified["value"] is None


def test_blank_remains_null():
    classified = classify_numeric(" ", present=True)
    assert classified["semantic"] == "blank"
    assert classified["value"] is None


def test_incomplete_gross_pair_does_not_derive_net():
    row = _row()
    del row["foreign_sell_volume"]
    row["_foreign_field_presence"]["foreign_sell_volume"] = "missing"
    sample = _sample(row)
    assert sample["fields"]["foreign_net_volume"]["value"] is None
    assert sample["fields"]["foreign_net_volume"]["semantic"] == "missing"


def test_complete_zero_pair_derives_valid_zero():
    sample = _sample(_row(foreign_buy_volume=0, foreign_sell_volume=0))
    assert sample["fields"]["foreign_net_volume"]["value"] == 0
    assert sample["fields"]["foreign_net_volume"]["semantic"] == "derived_zero"


def test_change_classifier_distinguishes_increase_equal_and_decrease():
    samples = [
        _sample(number=1),
        _sample(_row(foreign_buy_volume=110), number=2),
        _sample(_row(foreign_buy_volume=90), number=3),
    ]
    changes = classify_sample_changes(samples)
    assert changes["by_field"]["foreign_buy_volume"] == ["increased", "decreased"]
    assert changes["any_increase"] is True
    assert changes["any_decrease"] is True


def test_reconciliation_rejects_date_mismatch():
    provisional = _sample()
    accepted = deepcopy(provisional)
    accepted["provider_session_date"] = "2026-07-27"
    with pytest.raises(ValueError, match="provider_session_date mismatch"):
        reconcile_evidence(provisional, accepted)


def test_reconciliation_rejects_unit_mismatch():
    provisional = _sample()
    accepted = deepcopy(provisional)
    accepted["value_unit"] = "thousand VND"
    with pytest.raises(ValueError, match="value_unit mismatch"):
        reconcile_evidence(provisional, accepted)


def test_reconciliation_zero_denominator_has_null_percentage():
    provisional = _sample(_row(foreign_buy_volume=10))
    accepted = _sample(_row(foreign_buy_volume=0))
    result = reconcile_evidence(provisional, accepted)
    comparison = result["comparisons"]["foreign_buy_volume"]
    assert comparison["absolute_difference"] == 10
    assert comparison["percentage_difference"] is None


def test_reconciliation_keeps_accepted_daily_authoritative_and_provisional_separate():
    provisional = _sample()
    accepted = deepcopy(provisional)
    result = reconcile_evidence(provisional, accepted)
    assert result["accepted_daily_authoritative"] is True
    assert result["provisional_remains_separate"] is True


def test_evidence_matrix_uses_only_allowed_cell_values():
    daily = evaluate_daily_stock_price_samples([_sample()], expected_session_date=DATE)
    allowed = {"passed", "failed", "pending", "not_applicable", "inconclusive"}
    matrix = evidence_matrix(daily)
    assert all(value in allowed for row in matrix.values() for value in row.values())


VN = ZoneInfo("Asia/Ho_Chi_Minh")
RECEIVED = datetime(2026, 7, 28, 10, 0, 10, tzinfo=VN)


def _room_message(**overrides):
    data = {
        "t": "10:00:00",
        "s": "FPT",
        "tr": 1_000,
        "cr": 800,
        "bq": 100,
        "sq": 80,
        "bv": 7_000_000,
        "sv": 5_500_000,
    }
    data.update(overrides)
    return {"topic": "room.FPT", "data": data}


def _room_sample(message=None, *, number=1, received_at=RECEIVED):
    return room_sample_from_message(
        _room_message() if message is None else message,
        received_at=received_at,
        sample_number=number,
    )


def test_room_capacity_only_does_not_create_flow():
    sample = _room_sample(
        _room_message(bq=None, sq=None, bv=None, sv=None)
    )
    assert sample["room_capacity"]["total_foreign_room"]["value"] == 1_000
    assert sample["fields"]["foreign_buy_volume"]["value"] is None
    result = evaluate_room_samples([sample], expected_session_date=DATE)
    assert result["candidate_status"] == "inconclusive"


def test_explicit_room_buy_sell_fields_are_flow_candidate():
    result = evaluate_room_samples([_room_sample()], expected_session_date=DATE)
    assert result["candidate_status"] == "candidate_found"
    assert result["snapshot_delta"] == "cumulative_snapshot_candidate"


def test_room_capacity_and_flow_coexist_independently():
    sample = _room_sample()
    assert sample["sdk_typed_decoded"] is True
    assert sample["room_capacity"]["current_foreign_room"]["value"] == 800
    assert sample["fields"]["foreign_buy_volume"]["value"] == 100


def test_v2_to_v3_mapping_preserves_room_and_flow_categories():
    assert V2_TO_V3_FIELD_MAP["room_capacity"]["CurrentRoom"] == "current_room"
    assert (
        V2_TO_V3_FIELD_MAP["current_foreign_flow"]["FBuyVol"]
        == "buy_quantity"
    )
    assert "FBuyVol" not in V2_TO_V3_FIELD_MAP["room_capacity"]


def test_installed_sdk_foreign_room_model_exposes_both_capability_groups():
    annotations = ForeignRoomMessage.__annotations__
    assert {"total_room", "current_room"} <= annotations.keys()
    assert {
        "buy_quantity",
        "sell_quantity",
        "buy_value",
        "sell_value",
    } <= annotations.keys()


def test_installed_sdk_foreign_room_decoder_uses_verified_raw_aliases():
    decoded = ForeignRoomMessage.from_dict(
        {
            "t": "10:00:00",
            "s": "FPT",
            "tr": 1_000,
            "cr": 800,
            "bq": 100,
            "sq": 80,
            "bv": 7_000_000,
            "sv": 5_500_000,
        }
    )
    assert decoded.total_room == 1_000
    assert decoded.current_room == 800
    assert decoded.buy_quantity == 100
    assert decoded.sell_quantity == 80
    assert decoded.buy_value == 7_000_000
    assert decoded.sell_value == 5_500_000


@pytest.mark.parametrize("capacity_field", ["tr", "cr"])
def test_room_capacity_change_is_never_converted_to_flow(capacity_field):
    first = _room_sample(number=1)
    second = _room_sample(
        _room_message(**{capacity_field: 700}),
        number=2,
    )
    assert _numeric_room_values(first) == _numeric_room_values(second)
    result = evaluate_room_samples([first, second], expected_session_date=DATE)
    assert result["counter_movement"] == "equal"


def _numeric_room_values(sample):
    return tuple(
        sample["fields"][field]["value"]
        for field in (
            "foreign_buy_volume",
            "foreign_sell_volume",
            "foreign_buy_value",
            "foreign_sell_value",
        )
    )


@pytest.mark.parametrize(
    ("alias", "normalized", "value"),
    [
        ("bq", "foreign_buy_volume", 100),
        ("sq", "foreign_sell_volume", 80),
        ("bv", "foreign_buy_value", 7_000_000),
        ("sv", "foreign_sell_value", 5_500_000),
    ],
)
def test_verified_room_alias_mapping(alias, normalized, value):
    sample = _room_sample()
    assert sample["fields"][normalized]["value"] == value


def test_room_complete_pairs_derive_nets():
    sample = _room_sample()
    assert sample["fields"]["foreign_net_volume"]["value"] == 20
    assert sample["fields"]["foreign_net_value"]["value"] == 1_500_000


@pytest.mark.parametrize(
    ("missing_alias", "net_field"),
    [("sq", "foreign_net_volume"), ("sv", "foreign_net_value")],
)
def test_room_incomplete_pair_keeps_net_null(missing_alias, net_field):
    message = _room_message()
    del message["data"][missing_alias]
    sample = _room_sample(message)
    assert sample["fields"][net_field]["value"] is None


def test_room_explicit_zero_remains_zero_and_derives_zero_net():
    sample = _room_sample(_room_message(bq=0, sq=0, bv=0, sv=0))
    assert sample["fields"]["foreign_buy_volume"]["semantic"] == "explicit_zero"
    assert sample["fields"]["foreign_net_volume"]["value"] == 0


@pytest.mark.parametrize(
    ("raw", "semantic"),
    [(None, "null"), ("", "blank"), ("bad", "malformed")],
)
def test_room_null_blank_and_malformed_remain_null(raw, semantic):
    sample = _room_sample(_room_message(bq=raw))
    assert sample["fields"]["foreign_buy_volume"]["semantic"] == semantic
    assert sample["fields"]["foreign_buy_volume"]["value"] is None


def test_room_missing_field_remains_missing_null():
    message = _room_message()
    del message["data"]["bq"]
    sample = _room_sample(message)
    assert sample["fields"]["foreign_buy_volume"]["semantic"] == "missing"
    assert sample["fields"]["foreign_buy_volume"]["value"] is None


def test_time_only_active_message_is_safely_attributed_to_receipt_date():
    sample = _room_sample()
    assert sample["provider_date_supplied"] is False
    assert sample["receipt_date_attributed"] is True
    assert sample["provider_session_date"] == DATE


def test_previous_session_message_does_not_become_current():
    sample = _room_sample(
        _room_message(td="2026-07-27", t="2026-07-27T10:00:00+07:00")
    )
    result = evaluate_room_samples([sample], expected_session_date=DATE)
    assert result["current_date_sample_count"] == 0
    assert result["candidate_status"] == "active_session_pending"


def test_static_zero_only_room_sample_is_inconclusive():
    sample = _room_sample(_room_message(bq=0, sq=0, bv=0, sv=0))
    result = evaluate_room_samples([sample], expected_session_date=DATE)
    assert result["zero_only"] is True
    assert result["gate_status"] == "inconclusive"


def test_changing_room_counters_support_observed_cumulative_behavior():
    second = _room_sample(
        _room_message(bq=110, bv=7_500_000),
        number=2,
        received_at=datetime(2026, 7, 28, 10, 0, 20, tzinfo=VN),
    )
    result = evaluate_room_samples(
        [_room_sample(number=1), second], expected_session_date=DATE
    )
    assert result["snapshot_delta"] == "cumulative_snapshot_observed"
    assert result["counter_movement"] == "increased"


def test_room_counter_decrease_is_correction_or_reset_candidate():
    second = _room_sample(_room_message(bq=90), number=2)
    result = evaluate_room_samples(
        [_room_sample(number=1), second], expected_session_date=DATE
    )
    assert result["snapshot_delta"] == "correction_or_reset_candidate"
    assert result["counter_decrease_behavior"] == "correction_or_reset_candidate"


def test_provider_event_and_receipt_time_remain_distinct():
    sample = _room_sample()
    assert sample["provider_event_time"] == "10:00:00"
    assert sample["received_at"].startswith("2026-07-28T10:00:10")


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "near_realtime"),
        (15, "near_realtime"),
        (16, "delayed"),
        (300, "delayed"),
        (301, "materially_delayed"),
        (None, "unknown"),
        (-1, "unknown"),
    ],
)
def test_delay_classification(seconds, expected):
    assert classify_delay(seconds) == expected


def test_missing_provider_time_has_unknown_delay():
    sample = _room_sample(_room_message(t=None))
    assert sample["delay_ms"] is None
    assert sample["delay_classification"] == "unknown"


def test_repeated_room_snapshots_are_not_accumulated_or_double_counted():
    samples = [_room_sample(number=1), _room_sample(number=2)]
    result = evaluate_room_samples(samples, expected_session_date=DATE)
    assert result["local_accumulation"] is False
    assert result["replay_count"] == 1
    assert result["latest_snapshot"]["fields"]["foreign_buy_volume"]["value"] == 100


def test_later_room_snapshot_replaces_earlier_snapshot():
    later = _room_sample(_room_message(bq=140), number=2)
    selected = select_latest_room_snapshot([_room_sample(number=1), later])
    assert selected["fields"]["foreign_buy_volume"]["value"] == 140


def test_volume_only_room_candidate_can_pass_minimum_gate():
    sample = _room_sample(_room_message(bv=None, sv=None))
    result = evaluate_room_samples([sample], expected_session_date=DATE)
    assert result["volume_pair_observed"] is True
    assert result["value_pair_observed"] is False
    assert result["gate_status"] == "passed"


def test_room_candidate_keeps_deferred_gates_and_daily_authority():
    result = evaluate_room_samples([_room_sample()], expected_session_date=DATE)
    assert result["reconciliation"] == "reconciliation_pending"
    assert result["session_reset"] == "next_session_reset_pending"
    assert result["accepted_daily_authority"] == "DailyStockPrice"
