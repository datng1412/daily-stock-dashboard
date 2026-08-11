from __future__ import annotations

import unittest
from unittest.mock import patch

from src.services.vietnam_watchlist_alerts import (
    VietnamWatchlistAlert,
    evaluate_vietnam_alert,
    normalize_vietnam_alert_parameters,
    normalize_vietnam_alert_target,
)


def _rule(alert_type: str, target: str, parameters: dict) -> VietnamWatchlistAlert:
    return VietnamWatchlistAlert(
        target_scope="vn_market", target=target, alert_type=alert_type,
        parameters=parameters, metadata={"persisted_rule_id": 7},
    )


class VietnamWatchlistAlertTestCase(unittest.TestCase):
    def test_validation_rejects_invalid_family_fields_before_provider_work(self) -> None:
        with self.assertRaisesRegex(ValueError, "metric"):
            normalize_vietnam_alert_parameters("vn_breadth", {"metric": "invented", "operator": "gt", "threshold": 1})
        with self.assertRaisesRegex(ValueError, "window"):
            normalize_vietnam_alert_parameters("vn_foreign_flow", {"metric": "net_value", "window": 3, "operator": "gt", "threshold": 1})
        with self.assertRaisesRegex(ValueError, "benchmark"):
            normalize_vietnam_alert_parameters("vn_relative_strength", {"metric": "relative_performance_pp", "window": 5, "benchmark": "fake", "operator": "gt", "threshold": 1})
        with self.assertRaisesRegex(ValueError, "sector"):
            normalize_vietnam_alert_target("vn_sector", "bad sector!")
        with self.assertRaisesRegex(ValueError, "ticker"):
            normalize_vietnam_alert_target("vn_relative_strength", "!")
        with self.assertRaisesRegex(ValueError, "operator"):
            normalize_vietnam_alert_parameters("vn_breadth", {"metric": "advances", "operator": "crosses", "threshold": 1})
        with self.assertRaisesRegex(ValueError, "finite"):
            normalize_vietnam_alert_parameters("vn_breadth", {"metric": "advances", "operator": "gt", "threshold": "not-a-number"})

    def test_foreign_flow_only_fires_on_complete_completed_window(self) -> None:
        parameters = normalize_vietnam_alert_parameters(
            "vn_foreign_flow", {"metric": "net_value", "window": 5, "operator": "gt", "threshold": 100},
        )
        ready = {
            "source": "ssi_fastconnect", "source_endpoint": "daily_stock_price", "finality": "daily_available",
            "data_state": "ready", "coverage": {"covered_sessions": 60},
            "analytics": {"value": {"windows": {"5": {"complete": True, "net_sum": 125, "end_date": "2026-08-10"}}}},
        }
        incomplete = {**ready, "analytics": {"value": {"windows": {"5": {"complete": False, "net_sum": 125, "end_date": "2026-08-10"}}}}}
        with patch("src.services.vietnam_foreign_flow_service.VietnamForeignFlowService.get_symbol_history", return_value=ready):
            fired = evaluate_vietnam_alert(_rule("vn_foreign_flow", "FPT", parameters), cache={})
        with patch("src.services.vietnam_foreign_flow_service.VietnamForeignFlowService.get_symbol_history", return_value=incomplete):
            skipped = evaluate_vietnam_alert(_rule("vn_foreign_flow", "FPT", parameters), cache={})
        self.assertTrue(fired["triggered"])
        self.assertEqual(fired["data_timestamp"].date().isoformat(), "2026-08-10")
        self.assertFalse(skipped["triggered"])
        self.assertEqual(skipped["record_status"], "skipped")

    def test_breadth_sector_and_relative_strength_representative_rules(self) -> None:
        breadth = {
            "source": "SSI", "source_endpoint": "securitiesSummary", "usable": True,
            "finality": "completed_daily", "provider_session_date": "2026-08-10",
            "direction": {"advances": 20, "declines": 8}, "ma20": {"percent_above": 60}, "ma50": {"percent_above": 50},
            "coverage": {"direction_usable_count": 30, "ma20_usable_count": 30, "ma50_usable_count": 30},
        }
        sector = {
            "source": "SSI", "price_session_date": "2026-08-10", "price_finality": "completed_daily",
            "groups": [{"icb_code": "8300", "member_count": 3, "return_1d": {"value": .02, "usable_count": 3},
                        "ma20": {"percent_above": 66.7, "usable_count": 3}, "ma50": {"percent_above": 33.3, "usable_count": 3},
                        "foreign_flow": {"finality": "completed_accepted", "windows": {"5": {"complete": True, "net_value": 500, "end_date": "2026-08-10"}}}}],
        }
        rs = {"source": "SSI", "comparisons": {"vnindex": {"windows": {"5d": {
            "status": "ready", "complete": True, "end_session": "2026-08-10", "relative_performance_pp": 3.2,
            "stock_return_pct": 5.0, "benchmark_return_pct": 1.8,
        }}}}}
        cases = [
            ("vn_breadth", "VN30", {"metric": "advance_decline_spread", "operator": "gt", "threshold": 10},
             "src.services.vietnam_market_breadth_service.VietnamMarketBreadthService.build", breadth),
            ("vn_sector", "8300", {"metric": "foreign_net_value", "window": 5, "operator": "gt", "threshold": 100},
             "src.services.vietnam_sector_strength_service.VietnamSectorStrengthService.build", sector),
            ("vn_relative_strength", "FPT", {"metric": "relative_performance_pp", "window": 5, "benchmark": "vnindex", "operator": "gt", "threshold": 2},
             "src.services.vietnam_relative_strength_service.VietnamRelativeStrengthService.build", rs),
        ]
        for alert_type, target, raw, patch_target, payload in cases:
            with self.subTest(alert_type=alert_type), patch(patch_target, return_value=payload):
                result = evaluate_vietnam_alert(_rule(alert_type, target, normalize_vietnam_alert_parameters(alert_type, raw)), cache={})
                self.assertTrue(result["triggered"])
                self.assertIn('"finality"', result["diagnostics"])

    def test_cycle_cache_reuses_identical_scope(self) -> None:
        params = normalize_vietnam_alert_parameters("vn_breadth", {"metric": "advances", "operator": "gt", "threshold": 1})
        payload = {"source": "SSI", "usable": True, "finality": "completed_daily", "provider_session_date": "2026-08-10",
                   "direction": {"advances": 20, "declines": 10}, "ma20": {}, "ma50": {},
                   "coverage": {"direction_usable_count": 30}}
        cache = {}
        with patch("src.services.vietnam_market_breadth_service.VietnamMarketBreadthService.build", return_value=payload) as build:
            evaluate_vietnam_alert(_rule("vn_breadth", "VN30", params), cache=cache)
            evaluate_vietnam_alert(_rule("vn_breadth", "VN30", params), cache=cache)
        build.assert_called_once()

    def test_provisional_missing_partial_and_explicit_zero_never_become_fake_values(self) -> None:
        flow_params = normalize_vietnam_alert_parameters(
            "vn_foreign_flow", {"metric": "net_value", "window": 1, "operator": "lte", "threshold": 0},
        )
        provisional = {
            "finality": "provisional", "data_state": "ready", "coverage": {},
            "analytics": {"value": {"windows": {"1": {"complete": True, "net_sum": 0, "end_date": "2026-08-11"}}}},
        }
        with patch("src.services.vietnam_foreign_flow_service.VietnamForeignFlowService.get_symbol_history", return_value=provisional):
            result = evaluate_vietnam_alert(_rule("vn_foreign_flow", "FPT", flow_params), cache={})
        self.assertFalse(result["triggered"])
        self.assertIsNone(result["observed_value"])
        self.assertEqual(result["record_status"], "skipped")

        breadth_params = normalize_vietnam_alert_parameters(
            "vn_breadth", {"metric": "advance_decline_spread", "operator": "gte", "threshold": 0},
        )
        partial = {"usable": True, "finality": "completed_daily", "provider_session_date": "2026-08-10",
                   "direction": {"advances": 0, "declines": 0}, "ma20": {}, "ma50": {},
                   "coverage": {"direction_usable_count": 29}}
        with patch("src.services.vietnam_market_breadth_service.VietnamMarketBreadthService.build", return_value=partial):
            result = evaluate_vietnam_alert(_rule("vn_breadth", "VN30", breadth_params), cache={})
        self.assertFalse(result["triggered"])
        self.assertIsNone(result["observed_value"])

    def test_foreign_state_and_all_rs_benchmarks_windows_are_existing_contracts(self) -> None:
        state_params = normalize_vietnam_alert_parameters(
            "vn_foreign_flow", {"metric": "direction_state", "window": 20, "expected_state": "accumulating"},
        )
        flow = {"source": "SSI", "finality": "daily_available", "data_state": "ready", "coverage": {},
                "analytics": {"signals": {"direction_20d": {"complete": True, "state": "accumulating", "end_date": "2026-08-10"}}, "value": {"windows": {}}}}
        with patch("src.services.vietnam_foreign_flow_service.VietnamForeignFlowService.get_symbol_history", return_value=flow):
            self.assertTrue(evaluate_vietnam_alert(_rule("vn_foreign_flow", "FPT", state_params), cache={})["triggered"])

        for benchmark in ("vnindex", "vn30", "industry"):
            for window in (1, 5, 20):
                params = normalize_vietnam_alert_parameters("vn_relative_strength", {
                    "metric": "relative_performance_pp", "window": window, "benchmark": benchmark,
                    "operator": "lte", "threshold": 0,
                })
                payload = {"comparisons": {benchmark: {"windows": {f"{window}d": {
                    "status": "ready", "complete": True, "end_session": "2026-08-10",
                    "relative_performance_pp": 0, "stock_return_pct": 0, "benchmark_return_pct": 0,
                }}}}}
                with patch("src.services.vietnam_relative_strength_service.VietnamRelativeStrengthService.build", return_value=payload):
                    result = evaluate_vietnam_alert(_rule("vn_relative_strength", "FPT", params), cache={})
                self.assertTrue(result["triggered"], (benchmark, window))


if __name__ == "__main__":
    unittest.main()
