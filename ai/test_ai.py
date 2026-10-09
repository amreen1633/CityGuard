
import os
import tempfile
import unittest
from unittest.mock import patch

from ai.ai_service import (
    analyze_emergency,
    classify_civic_issue,
    classify_civic_image,
    fallback_emergency_analysis,
    fallback_civic_analysis,
    validate_civic_result,
)


class TestCityGuardAI(unittest.TestCase):

    # --------------------------------------
    # EMERGENCY AI TESTS
    # --------------------------------------

    def test_emergency_analysis_returns_required_fields(self):
        result = analyze_emergency(
            "Accident at Main Junction. Two people are injured."
        )

        required_fields = {
            "emergency_type",
            "severity",
            "location",
            "injured_people",
            "requires_ambulance",
            "ai_status",
        }

        self.assertTrue(required_fields.issubset(result.keys()))
        self.assertIn(
            result["emergency_type"],
            {"accident", "fire", "medical", "other", "unknown"},
        )
        self.assertIn(
            result["severity"],
            {"low", "medium", "high", "critical"},
        )

    def test_empty_emergency_message(self):
        result = analyze_emergency("")

        self.assertEqual(result["ai_status"], "invalid_input")
        self.assertEqual(result["emergency_type"], "unknown")

    def test_emergency_fallback(self):
        with patch("ai.ai_service.client", None):
            result = analyze_emergency(
                "Accident at Madhapur. Two people are injured."
            )

        self.assertEqual(result["ai_status"], "fallback")
        self.assertEqual(result["emergency_type"], "accident")
        self.assertEqual(result["location"], "Madhapur")
        self.assertTrue(result["requires_ambulance"])

    # --------------------------------------
    # CIVIC TEXT CLASSIFICATION TESTS
    # --------------------------------------

    def test_civic_classification_returns_required_fields(self):
        result = classify_civic_issue(
            "A large pothole is damaging the road."
        )

        self.assertIn("category", result)
        self.assertIn("severity", result)
        self.assertIn("confidence", result)
        self.assertIn("ai_status", result)

        self.assertIn(
            result["category"],
            {
                "pothole",
                "garbage",
                "streetlight",
                "water_leakage",
                "road_damage",
                "other",
            },
        )

        self.assertIn(
            result["severity"],
            {"low", "medium", "high"},
        )

        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)

    def test_empty_civic_description(self):
        result = classify_civic_issue("")

        self.assertEqual(result["ai_status"], "invalid_input")
        self.assertEqual(result["category"], "unknown")

    def test_civic_fallback(self):
        with patch("ai.ai_service.client", None):
            result = classify_civic_issue(
                "A pothole is present on the road."
            )

        self.assertEqual(result["ai_status"], "fallback")
        self.assertEqual(result["category"], "pothole")

    # --------------------------------------
    # AI OUTPUT VALIDATION TESTS
    # --------------------------------------

    def test_invalid_civic_output_is_normalized(self):
        result = validate_civic_result({
            "category": "unknown-category",
            "severity": "extreme",
            "confidence": 5,
        })

        self.assertEqual(result["category"], "other")
        self.assertEqual(result["severity"], "medium")
        self.assertEqual(result["confidence"], 1.0)

    def test_invalid_confidence_is_handled(self):
        result = validate_civic_result({
            "category": "pothole",
            "severity": "high",
            "confidence": "not-a-number",
        })

        self.assertEqual(result["confidence"], 0.0)

    # --------------------------------------
    # IMAGE CLASSIFICATION TESTS
    # --------------------------------------

    def test_missing_image(self):
        result = classify_civic_image(
            "this_image_does_not_exist.jpg"
        )

        self.assertEqual(result["ai_status"], "invalid_input")
        self.assertEqual(result["category"], "unknown")

    def test_image_fallback_without_api_key(self):
        with tempfile.NamedTemporaryFile(
            suffix=".jpg",
            delete=False,
        ) as image_file:
            image_path = image_file.name
            image_file.write(b"test image data")

        try:
            with patch("ai.ai_service.client", None):
                result = classify_civic_image(image_path)

            self.assertEqual(result["ai_status"], "fallback")
            self.assertIn("category", result)
            self.assertIn("description", result)
        finally:
            os.remove(image_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
