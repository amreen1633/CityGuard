import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class FakeQuery:
    def __init__(self, records):
        self.records = records

    def all(self):
        return list(self.records)


class FakeSession:
    def __init__(self, records):
        self.records = records
        self.added = []
        self.queried_model = None
        self.refreshed_record = None

    def query(self, model):
        self.queried_model = model
        return FakeQuery(self.records)

    def add(self, record):
        self.added.append(record)

    def commit(self):
        for index, record in enumerate(self.added, start=1):
            record.id = index
            self.records.append(record)

    def refresh(self, record):
        self.refreshed_record = record
        return None

    def close(self):
        return None


class BackendApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_directory = os.getcwd()
        cls.temporary_directory = tempfile.TemporaryDirectory()
        os.chdir(cls.temporary_directory.name)
        backend_directory = os.path.dirname(__file__)
        sys.path.insert(0, backend_directory)
        from fastapi.testclient import TestClient
        import main

        cls.main = main
        cls.TestClient = TestClient

    @classmethod
    def tearDownClass(cls):
        cls.main.app.dependency_overrides.clear()
        cls.main.engine.dispose()
        sys.path.remove(os.path.dirname(__file__))
        for module_name in ("main", "database", "models"):
            sys.modules.pop(module_name, None)
        os.chdir(cls.previous_directory)
        cls.temporary_directory.cleanup()

    def setUp(self):
        self.records = [
            SimpleNamespace(
                id=7,
                title="Pothole near school",
                description="Large pothole on the road.",
                severity="High",
                status="Pending",
                location="Madhapur",
                type="General",
            )
        ]
        self.session = FakeSession(self.records)
        self.main.app.dependency_overrides[self.main.get_db] = lambda: self.session
        self.client = self.TestClient(self.main.app)

    def tearDown(self):
        self.client.close()
        self.main.app.dependency_overrides.clear()

    def test_existing_dashboard_and_report_contracts_remain_available(self):
        assessment = {
            "category": "pothole",
            "severity": "high",
            "department": "Roads and Public Works",
            "ai_status": "fallback",
            "emergency_review": False,
        }
        with patch.object(self.main, "cached_report_assessment", return_value=assessment):
            dashboard_response = self.client.get("/dashboard")
            reports_response = self.client.get("/reports")

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(
            set(dashboard_response.json()),
            {"total_reports", "total_emergencies", "pending_reports", "resolved_reports"},
        )
        self.assertEqual(reports_response.status_code, 200)
        report = reports_response.json()[0]
        self.assertEqual(
            {key: report[key] for key in (
                "id", "title", "description", "severity", "status", "location", "type"
            )},
            {
                "id": 7,
                "title": "Pothole near school",
                "description": "Large pothole on the road.",
                "severity": "High",
                "status": "Pending",
                "location": "Madhapur",
                "type": "General",
            },
        )
        self.assertEqual(report["ai_assessment"], assessment)

    def test_submission_still_saves_original_fields_when_ai_falls_back(self):
        assessment = {
            "category": "pothole",
            "severity": "high",
            "department": "Roads and Public Works",
            "ai_status": "fallback",
            "emergency_review": False,
        }
        form = {
            "title": (None, "Pothole by school"),
            "description": (None, "Large pothole on the road."),
            "location": (None, "Madhapur"),
            "severity": (None, "High"),
        }
        with patch.object(self.main, "cached_report_assessment", return_value=assessment):
            response = self.client.post("/reports", files=form)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ai_assessment"], assessment)
        saved_report = self.session.added[0]
        self.assertEqual(saved_report.title, "Pothole by school")
        self.assertEqual(saved_report.description, "Large pothole on the road.")
        self.assertEqual(saved_report.location, "Madhapur")
        self.assertEqual(saved_report.severity, "High")
        self.assertEqual(saved_report.status, "Pending")
        self.assertEqual(saved_report.type, "General")

    def test_traffic_analysis_endpoint_keeps_simulation_inputs_explicit(self):
        recommendation = {
            "ai_status": "fallback",
            "congestion_level": "high",
            "vehicle_count": "10+",
            "directional_counts_available": False,
            "recommended_green_seconds": 50,
            "reason": "Rule-based simulated timing.",
        }
        with patch.object(
            self.main,
            "recommend_traffic_signal_timing",
            return_value=recommendation,
        ) as recommend:
            response = self.client.get(
                "/traffic-analysis?congestion_level=HIGH&vehicle_count=10%2B"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), recommendation)
        recommend.assert_called_once_with("HIGH", "10+")

    def test_traffic_analysis_endpoint_supports_explicit_rule_based_mode(self):
        recommendation = {
            "ai_status": "rule_based",
            "congestion_level": "medium",
            "vehicle_count": "6",
            "directional_counts_available": False,
            "recommended_green_seconds": 40,
            "reason": "The medium simulation level with 6 displayed vehicles maps to a 40 second green phase in the transparent demo rule.",
        }
        with patch.object(
            self.main,
            "recommend_traffic_signal_timing",
            return_value=recommendation,
        ) as recommend:
            response = self.client.get(
                "/traffic-analysis?congestion_level=MEDIUM&vehicle_count=6&rule_based=true"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), recommendation)
        recommend.assert_called_once_with("MEDIUM", "6", rule_based=True)

    def test_recorded_video_status_and_results_endpoints_expose_demo_metrics(self):
        status_response = self.client.get("/vehicle-detection/status")
        results_response = self.client.get("/vehicle-detection/results")

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(results_response.status_code, 200)
        for response in (status_response, results_response):
            result = response.json()
            self.assertEqual(result["status"], "idle")
            self.assertEqual(
                result["vehicle_counts"],
                {"car": 0, "motorcycle": 0, "bus": 0, "truck": 0},
            )
            self.assertIn("NOT LIVE CCTV", result["video_label"])
            self.assertIn("not a verified real-world", result["congestion_basis"])

    def test_vehicle_detection_status_returns_failed_job_error(self):
        failed = {
            "status": "failed",
            "message": "Recorded-video processing failed.",
            "error_message": "YOLO weights could not be loaded.",
        }
        with patch.object(self.main.video_detection_job, "snapshot", return_value=failed):
            response = self.client.get("/vehicle-detection/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "failed")
        self.assertEqual(response.json()["error_message"], "YOLO weights could not be loaded.")

    def test_vehicle_detection_status_exposes_each_workflow_state(self):
        states = {
            "idle": {"processed_frames": 0, "progress_percent": 0},
            "queued": {"processed_frames": 0, "progress_percent": 0},
            "running": {"processed_frames": 12, "progress_percent": 40},
            "processing": {"processed_frames": 18, "progress_percent": 60},
            "completed": {"processed_frames": 30, "progress_percent": 100},
            "failed": {
                "processed_frames": 8,
                "progress_percent": 26,
                "error_message": "Video decoding failed.",
            },
        }
        for status, details in states.items():
            with self.subTest(status=status), patch.object(
                self.main.video_detection_job,
                "snapshot",
                return_value={"status": status, **details},
            ):
                response = self.client.get("/vehicle-detection/status")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], status)
            for key, value in details.items():
                self.assertEqual(response.json()[key], value)

    def test_recorded_video_start_queues_without_changing_existing_routes(self):
        queued = {
            "status": "queued",
            "video_label": "RECORDED VIDEO DEMO — NOT LIVE CCTV",
        }
        with patch.object(
            self.main.video_detection_job, "start", return_value=queued
        ) as start:
            response = self.client.post("/vehicle-detection/start")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), queued)
        start.assert_called_once()

    def test_duplicate_recorded_video_job_returns_conflict(self):
        with patch.object(
            self.main.video_detection_job,
            "start",
            side_effect=RuntimeError("Recorded-video processing is already running."),
        ):
            response = self.client.post("/vehicle-detection/start")

        self.assertEqual(response.status_code, 409)
        self.assertIn("already running", response.json()["detail"])

    def test_annotated_video_is_not_served_before_processing_completes(self):
        response = self.client.get("/vehicle-detection/video")

        self.assertEqual(response.status_code, 404)
        self.assertIn("not available yet", response.json()["detail"])

    def test_saved_submission_survives_an_ai_service_exception(self):
        self.main.cached_report_assessment.cache_clear()
        form = {
            "title": (None, "Streetlight outage"),
            "description": (None, "The streetlight is not working."),
            "location": (None, "Secunderabad"),
            "severity": (None, "Medium"),
        }
        with patch.object(
            self.main,
            "analyze_civic_report",
            side_effect=RuntimeError("AI service unavailable"),
        ):
            response = self.client.post("/reports", files=form)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.session.added), 1)
        self.assertEqual(self.session.added[0].title, "Streetlight outage")
        self.assertEqual(response.json()["ai_assessment"]["ai_status"], "unavailable")
        self.assertIn("saved report remains available", response.json()["ai_assessment"]["explanation"])


if __name__ == "__main__":
    unittest.main()
