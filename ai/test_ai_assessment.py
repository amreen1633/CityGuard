import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ai import ai_service


class CivicReportAssessmentTests(unittest.TestCase):
    def test_routine_pothole_uses_title_and_recommends_roads(self):
        result = {
            "category": "pothole",
            "severity": "medium",
            "confidence": 0.92,
            "ai_status": "success",
        }
        with patch.object(ai_service, "classify_civic_issue", return_value=result) as classify:
            assessment = ai_service.analyze_civic_report(
                "Pothole by the school", "A deep hole is forming on the road."
            )

        self.assertIn("Pothole by the school", classify.call_args.args[0])
        self.assertEqual(assessment["category"], "pothole")
        self.assertEqual(assessment["department"], "Roads and Public Works")
        self.assertFalse(assessment["emergency_review"])
        self.assertEqual(assessment["ai_status"], "success")

    def test_garbage_and_water_leakage_fallback_categories(self):
        with patch.object(ai_service, "client", None):
            garbage = ai_service.analyze_civic_report(
                "Missed collection", "Garbage and waste were left at the roadside."
            )
            water = ai_service.analyze_civic_report(
                "Water leak", "Water is leaking from a pipe near the footpath."
            )

        self.assertEqual(garbage["category"], "garbage")
        self.assertEqual(garbage["department"], "Sanitation")
        self.assertEqual(water["category"], "water_leakage")
        self.assertEqual(water["department"], "Water and Drainage")
        self.assertEqual(garbage["ai_status"], "fallback")

    def test_exposed_wire_is_flagged_for_human_emergency_review(self):
        classification = {
            "category": "other",
            "severity": "high",
            "confidence": 0.8,
            "ai_status": "success",
        }
        emergency = {
            "emergency_type": "other",
            "severity": "high",
            "ai_status": "fallback",
        }
        with (
            patch.object(ai_service, "classify_civic_issue", return_value=classification),
            patch.object(ai_service, "analyze_emergency", return_value=emergency),
        ):
            assessment = ai_service.analyze_civic_report(
                "Exposed electrical wires", "Live wire hanging over a public footpath."
            )

        self.assertTrue(assessment["emergency_review"])
        self.assertEqual(assessment["emergency_ai_status"], "fallback")
        self.assertIn("human verification", assessment["recommended_next_step"])
        self.assertIn("contact local emergency services", assessment["recommended_next_step"])

    def test_ordinary_high_priority_is_not_an_emergency(self):
        classification = {
            "category": "pothole",
            "severity": "high",
            "confidence": 0.9,
            "ai_status": "success",
        }
        with (
            patch.object(ai_service, "classify_civic_issue", return_value=classification),
            patch.object(ai_service, "analyze_emergency") as emergency,
        ):
            assessment = ai_service.analyze_civic_report(
                "Large pothole", "A large pothole is disrupting traffic."
            )

        self.assertEqual(assessment["severity"], "high")
        self.assertFalse(assessment["emergency_review"])
        emergency.assert_not_called()

    def test_malformed_classifier_output_uses_explicit_fallback(self):
        invalid = {
            "category": "verified_emergency",
            "severity": "critical",
            "confidence": 2.0,
            "ai_status": "success",
        }
        for malformed in (invalid, ["unexpected", "json"]):
            with self.subTest(malformed=malformed):
                with patch.object(
                    ai_service, "classify_civic_issue", return_value=malformed
                ):
                    assessment = ai_service.analyze_civic_report(
                        "Pothole", "A pothole is visible on the road."
                    )

                self.assertEqual(assessment["category"], "pothole")
                self.assertEqual(assessment["ai_status"], "fallback")
                self.assertIn("invalid", assessment["explanation"])


class TrafficRecommendationTests(unittest.TestCase):
    def test_fallback_timing_scales_with_simulated_congestion(self):
        with patch.object(ai_service, "client", None):
            low = ai_service.recommend_traffic_signal_timing("LOW", "3")
            medium = ai_service.recommend_traffic_signal_timing("MEDIUM", "6")
            high = ai_service.recommend_traffic_signal_timing("HIGH", "10+")

        self.assertEqual(
            [low["recommended_green_seconds"], medium["recommended_green_seconds"],
             high["recommended_green_seconds"]],
            [30, 40, 50],
        )
        self.assertTrue(all(item["ai_status"] == "fallback" for item in (low, medium, high)))
        self.assertTrue(all(not item["directional_counts_available"] for item in (low, medium, high)))

    def test_invalid_ai_timing_uses_rule_based_fallback(self):
        fake_client = SimpleNamespace(
            responses=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    output_text='{"recommended_green_seconds": 999, "reason": "too long"}'
                )
            )
        )
        with patch.object(ai_service, "client", fake_client):
            result = ai_service.recommend_traffic_signal_timing("HIGH", "10+")

        self.assertEqual(result["recommended_green_seconds"], 50)
        self.assertEqual(result["ai_status"], "fallback")

    def test_explicit_rule_based_mode_uses_existing_simulation_rules(self):
        fake_client = SimpleNamespace(
            responses=SimpleNamespace(
                create=lambda **kwargs: self.fail(
                    "Rule-based simulation must not call the AI client"
                )
            )
        )
        with patch.object(ai_service, "client", fake_client):
            result = ai_service.recommend_traffic_signal_timing(
                "MEDIUM",
                "6",
                rule_based=True,
            )

        self.assertEqual(result["ai_status"], "rule_based")
        self.assertEqual(result["congestion_level"], "medium")
        self.assertEqual(result["vehicle_count"], "6")
        self.assertEqual(result["recommended_green_seconds"], 40)
        self.assertIn("medium simulation level with 6 displayed vehicles", result["reason"])


if __name__ == "__main__":
    unittest.main()
