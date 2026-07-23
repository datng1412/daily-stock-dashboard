"""Deterministic SSI V3 foreign unit and operational-finality policy tests."""

from __future__ import annotations

from datetime import date

import pytest

from data_provider.ssi_v3_foreign_policy import (
    SSI_V3_FOREIGN_FINALITY_POLICY,
    evaluate_implied_price_scales,
    foreign_row_finality,
    foreign_value_policy_for_board,
    normalize_foreign_value_rows,
    proven_implied_price_scale,
)


@pytest.mark.parametrize(
    ("board", "scale", "domain"),
    [
        ("HOSE", 1, "HOSE_EQUITY_VALUE"),
        ("HNX", 1_000, "HNX_EQUITY_VALUE"),
        ("UPCOM", 1_000, "UPCOM_EQUITY_VALUE"),
    ],
)
def test_foreign_value_policy_is_exchange_isolated_and_explicit(
    board: str, scale: int, domain: str
) -> None:
    policy = foreign_value_policy_for_board(board)
    assert policy == {
        "board": board,
        "domain": domain,
        "scale": scale,
        "volume_unit": "shares",
        "value_unit": "VND",
        "confidence": "PROVEN",
    }


def test_unproven_exchange_is_rejected_instead_of_using_a_global_scale() -> None:
    with pytest.raises(ValueError, match="HOSE, HNX, or UPCOM"):
        foreign_value_policy_for_board("OTHER")


@pytest.mark.parametrize(
    ("board", "raw_value", "expected_value"),
    [
        ("HOSE", 72_300_000, 72_300_000.0),
        ("HNX", 18_450, 18_450_000.0),
        ("UPCOM", 44_000, 44_000_000.0),
    ],
)
def test_normalization_applies_the_proven_scale_once(
    board: str, raw_value: int, expected_value: float
) -> None:
    rows, diagnostics = normalize_foreign_value_rows(
        [
            {
                "date": "2026-07-21",
                "foreign_buy_value": raw_value,
                "foreign_sell_value": raw_value // 2,
            }
        ],
        board=board,
        as_of=date(2026, 7, 23),
    )
    row = rows[0]
    assert row["foreign_buy_value"] == expected_value
    assert row["foreign_net_value"] == (
        row["foreign_buy_value"] - row["foreign_sell_value"]
    )
    assert row["foreign_value_unit"] == "VND"
    assert row["foreign_volume_unit"] == "shares"
    assert row["foreign_value_domain"] == f"{board}_EQUITY_VALUE"
    assert row["foreign_value_scale_confidence"] == "PROVEN"
    assert diagnostics["foreign_value_scale"] == (
        1 if board == "HOSE" else 1_000
    )


def test_normalization_preserves_nulls_and_never_uses_partial_gross_pairs() -> None:
    rows, _diagnostics = normalize_foreign_value_rows(
        [
            {
                "date": "2026-07-21",
                "foreign_buy_value": 12,
                "foreign_sell_value": None,
                "foreign_net_value": 999,
            }
        ],
        board="HNX",
        as_of=date(2026, 7, 23),
    )
    assert rows[0]["foreign_buy_value"] == 12_000.0
    assert rows[0]["foreign_sell_value"] is None
    assert rows[0]["foreign_net_value"] is None
    assert rows[0]["_foreign_net_value_source"] is None


def test_duplicate_dates_are_rejected_before_product_analytics() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        normalize_foreign_value_rows(
            [{"date": "2026-07-21"}, {"date": "2026-07-21"}],
            board="HOSE",
            as_of=date(2026, 7, 23),
        )


def test_current_and_t1_are_provisional_while_t2_is_completed_candidate() -> None:
    as_of = date(2026, 7, 23)
    current = foreign_row_finality("2026-07-23", as_of=as_of)
    t1 = foreign_row_finality(
        "2026-07-22",
        as_of=as_of,
        completed_session_rank=1,
    )
    t2 = foreign_row_finality(
        "2026-07-21",
        as_of=as_of,
        completed_session_rank=2,
    )
    assert current["state"] == "current_session_provisional"
    assert t1["state"] == "t_minus_1_provisional"
    assert t2["state"] == "t_minus_2_or_older_completed_candidate"
    assert current["is_provisional"] is True
    assert t1["is_provisional"] is True
    assert t2["is_provisional"] is False
    assert t2["policy"] == SSI_V3_FOREIGN_FINALITY_POLICY
    assert t2["provider_guaranteed"] is False


def test_session_rank_does_not_treat_weekends_or_holidays_as_sessions() -> None:
    rows, _diagnostics = normalize_foreign_value_rows(
        [
            {"date": "2026-04-29"},
            {"date": "2026-05-04"},
        ],
        board="HOSE",
        as_of=date(2026, 5, 5),
    )
    by_date = {row["date"]: row for row in rows}
    assert by_date["2026-05-04"]["foreign_finality"] == "t_minus_1_provisional"
    assert by_date["2026-04-29"]["foreign_finality"] == (
        "t_minus_2_or_older_completed_candidate"
    )
    assert by_date["2026-05-04"]["foreign_is_provisional"] is True
    assert by_date["2026-04-29"]["foreign_is_provisional"] is False


def test_historical_row_without_session_context_is_rejected() -> None:
    with pytest.raises(ValueError, match="completed-session rank"):
        foreign_row_finality("2026-07-22", as_of=date(2026, 7, 23))


def test_completed_analytics_filter_provisional_rows_but_raw_rows_can_retain_them() -> None:
    source = [
        {"date": "2026-07-21", "foreign_buy_value": 3, "foreign_sell_value": 1},
        {"date": "2026-07-22", "foreign_buy_value": 5, "foreign_sell_value": 2},
        {"date": "2026-07-23", "foreign_buy_value": 8, "foreign_sell_value": 3},
    ]
    completed, diagnostics = normalize_foreign_value_rows(
        source,
        board="HOSE",
        as_of=date(2026, 7, 23),
        include_provisional=False,
    )
    raw, _ = normalize_foreign_value_rows(
        source,
        board="HOSE",
        as_of=date(2026, 7, 23),
        include_provisional=True,
    )
    assert [row["date"] for row in completed] == ["2026-07-21"]
    assert len(raw) == 3
    assert diagnostics["provisional_row_count"] == 2
    assert diagnostics["foreign_provider_finality_guaranteed"] is False


def test_implied_price_invariant_accepts_only_unique_full_match_scale() -> None:
    results = evaluate_implied_price_scales(
        volumes=[1_000, 2_000],
        values=[72_300_000, 144_600_000],
        lows=[70_000, 70_000],
        highs=[74_000, 74_000],
    )
    assert results[1] == {
        "eligible_rows": 2,
        "plausible_rows": 2,
        "outliers": 0,
    }
    assert results[1_000]["plausible_rows"] == 0
    assert results[1_000_000]["plausible_rows"] == 0
    assert proven_implied_price_scale(results) == 1


def test_implied_price_invariant_rejects_outliers_and_ambiguous_empty_samples() -> None:
    outlier = evaluate_implied_price_scales(
        volumes=[1_000, 1_000],
        values=[72_300_000, 1],
        lows=[70_000, 70_000],
        highs=[74_000, 74_000],
    )
    empty = evaluate_implied_price_scales(
        volumes=[0],
        values=[0],
        lows=[70_000],
        highs=[74_000],
    )
    assert outlier[1]["outliers"] == 1
    assert proven_implied_price_scale(outlier) is None
    assert proven_implied_price_scale(empty) is None
