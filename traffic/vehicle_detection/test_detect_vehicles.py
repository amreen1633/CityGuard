import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock, patch

from traffic.vehicle_detection.detect_vehicles import (
    VideoDetectionJob,
    estimate_congestion,
    get_video_path,
    process_video,
)


class FakeFrame:
    shape = (360, 640, 3)

    def copy(self):
        return self


class FakeCapture:
    def __init__(self, frames):
        self.frames = list(frames)
        self.position = 0

    def isOpened(self):
        return True

    def get(self, property_id):
        if property_id == 1:
            return 30.0
        if property_id == 2:
            return len(self.frames)
        return 640 if property_id == 3 else 360

    def read(self):
        if self.position >= len(self.frames):
            return False, None
        frame = self.frames[self.position]
        self.position += 1
        return True, frame

    def release(self):
        return None


class FakeWriter:
    def __init__(self):
        self.frames = []

    def isOpened(self):
        return True

    def write(self, frame):
        self.frames.append(frame)

    def release(self):
        return None


class FakeBackgroundTasks:
    def __init__(self):
        self.tasks = []

    def add_task(self, function):
        self.tasks.append(function)


class VehicleDetectionTests(unittest.TestCase):
    def test_video_path_defaults_to_repository_sample(self):
        with patch.dict(os.environ, {"CITYGUARD_VIDEO_PATH": ""}):
            self.assertEqual(
                get_video_path(),
                Path(__file__).resolve().parents[2] / "traffic_videos" / "video3.mp4",
            )

    def test_video_path_uses_configured_absolute_path(self):
        configured_path = Path("C:/cityguard-media/video3.mp4")
        with patch.dict(os.environ, {"CITYGUARD_VIDEO_PATH": str(configured_path)}):
            self.assertEqual(get_video_path(), configured_path.resolve())

    def test_explicit_local_path_takes_precedence_over_remote_url(self):
        configured_path = Path("C:/cityguard-media/video3.mp4")
        with patch.dict(
            os.environ,
            {
                "CITYGUARD_VIDEO_PATH": str(configured_path),
                "CITYGUARD_VIDEO_URL": "https://example.invalid/video3.mp4",
            },
        ), patch("traffic.vehicle_detection.detect_vehicles._download_video") as download:
            self.assertEqual(get_video_path(), configured_path.resolve())
        download.assert_not_called()

    def test_video_path_resolves_relative_configuration_from_project_root(self):
        configured_path = "media/video3.mp4"
        expected = Path(__file__).resolve().parents[2] / configured_path
        with patch.dict(os.environ, {"CITYGUARD_VIDEO_PATH": configured_path}):
            self.assertEqual(get_video_path(), expected.resolve())

    def test_processing_uses_configured_video_path_at_runtime(self):
        configured_path = Path("C:/render-media/missing-video.mp4")
        with patch.dict(os.environ, {"CITYGUARD_VIDEO_PATH": str(configured_path)}):
            with self.assertRaises(FileNotFoundError) as error:
                process_video(output_path=configured_path.with_name("output.mp4"))
        self.assertIn(str(configured_path), str(error.exception))

    def test_video_url_downloads_once_and_reuses_nonempty_cache(self):
        response = MagicMock()
        response.headers.get_content_type.return_value = "video/mp4"
        response.read.side_effect = [b"video-content", b""]
        urlopen = MagicMock()
        urlopen.return_value.__enter__.return_value = response

        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_path = Path(temporary_directory) / "cityguard" / "video3.mp4"
            with patch.dict(
                os.environ,
                {
                    "CITYGUARD_VIDEO_PATH": "",
                    "CITYGUARD_VIDEO_URL": "https://drive.google.com/uc?export=download&id=demo",
                },
            ), patch(
                "traffic.vehicle_detection.detect_vehicles.VIDEO_CACHE_PATH",
                cache_path,
            ), patch(
                "traffic.vehicle_detection.detect_vehicles.urlopen",
                urlopen,
            ):
                first_path = get_video_path()
                second_path = get_video_path()

            self.assertEqual(first_path, cache_path)
            self.assertEqual(second_path, cache_path)
            self.assertEqual(cache_path.read_bytes(), b"video-content")
            urlopen.assert_called_once()

    def test_empty_video_cache_is_downloaded_again(self):
        response = MagicMock()
        response.headers.get_content_type.return_value = "video/mp4"
        response.read.side_effect = [b"recovered-video", b""]
        urlopen = MagicMock()
        urlopen.return_value.__enter__.return_value = response

        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_path = Path(temporary_directory) / "video3.mp4"
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.touch()
            with patch.dict(
                os.environ,
                {
                    "CITYGUARD_VIDEO_PATH": "",
                    "CITYGUARD_VIDEO_URL": "https://drive.google.com/uc?export=download&id=demo",
                },
            ), patch(
                "traffic.vehicle_detection.detect_vehicles.VIDEO_CACHE_PATH",
                cache_path,
            ), patch(
                "traffic.vehicle_detection.detect_vehicles.urlopen",
                urlopen,
            ):
                get_video_path()

            self.assertEqual(cache_path.read_bytes(), b"recovered-video")
            urlopen.assert_called_once()

    def test_download_failure_does_not_expose_url_or_leave_partial_cache(self):
        secret_url = "https://drive.google.com/download?token=secret-value"
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_path = Path(temporary_directory) / "video3.mp4"
            with patch.dict(
                os.environ,
                {"CITYGUARD_VIDEO_PATH": "", "CITYGUARD_VIDEO_URL": secret_url},
            ), patch(
                "traffic.vehicle_detection.detect_vehicles.VIDEO_CACHE_PATH",
                cache_path,
            ), patch(
                "traffic.vehicle_detection.detect_vehicles.urlopen",
                side_effect=URLError("private network detail"),
            ):
                with self.assertLogs(
                    "traffic.vehicle_detection.detect_vehicles",
                    level="WARNING",
                ) as captured_logs:
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "network or URL error",
                    ) as raised_error:
                        get_video_path()

            self.assertNotIn(secret_url, str(raised_error.exception))
            self.assertNotIn(secret_url, "\n".join(captured_logs.output))
            self.assertFalse(cache_path.exists())
            self.assertEqual(list(cache_path.parent.glob("*.download")), [])

    def test_http_download_error_reports_status_without_url(self):
        secret_url = "https://drive.google.com/download?token=secret-value"
        http_error = HTTPError(secret_url, 403, "Forbidden", None, None)
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_path = Path(temporary_directory) / "video3.mp4"
            with patch.dict(
                os.environ,
                {"CITYGUARD_VIDEO_PATH": "", "CITYGUARD_VIDEO_URL": secret_url},
            ), patch(
                "traffic.vehicle_detection.detect_vehicles.VIDEO_CACHE_PATH",
                cache_path,
            ), patch(
                "traffic.vehicle_detection.detect_vehicles.urlopen",
                side_effect=http_error,
            ):
                with self.assertLogs(
                    "traffic.vehicle_detection.detect_vehicles",
                    level="WARNING",
                ) as captured_logs:
                    with self.assertRaisesRegex(RuntimeError, "HTTP 403") as error:
                        get_video_path()

            self.assertNotIn(secret_url, str(error.exception))
            self.assertNotIn(secret_url, "\n".join(captured_logs.output))
            self.assertFalse(cache_path.exists())

    def test_download_timeout_has_network_error_message(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_path = Path(temporary_directory) / "video3.mp4"
            with patch.dict(
                os.environ,
                {
                    "CITYGUARD_VIDEO_PATH": "",
                    "CITYGUARD_VIDEO_URL": "https://drive.google.com/uc?export=download&id=demo",
                },
            ), patch(
                "traffic.vehicle_detection.detect_vehicles.VIDEO_CACHE_PATH",
                cache_path,
            ), patch(
                "traffic.vehicle_detection.detect_vehicles.urlopen",
                side_effect=TimeoutError("request timed out"),
            ):
                with self.assertRaisesRegex(RuntimeError, "download timed out"):
                    get_video_path()
            self.assertFalse(cache_path.exists())

    def test_html_download_response_is_rejected_without_caching(self):
        response = MagicMock()
        response.headers.get_content_type.return_value = "text/html"
        urlopen = MagicMock()
        urlopen.return_value.__enter__.return_value = response

        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_path = Path(temporary_directory) / "video3.mp4"
            with patch.dict(
                os.environ,
                {
                    "CITYGUARD_VIDEO_PATH": "",
                    "CITYGUARD_VIDEO_URL": "https://drive.google.com/uc?export=download&id=demo",
                },
            ), patch(
                "traffic.vehicle_detection.detect_vehicles.VIDEO_CACHE_PATH",
                cache_path,
            ), patch(
                "traffic.vehicle_detection.detect_vehicles.urlopen",
                urlopen,
            ):
                with self.assertRaisesRegex(RuntimeError, "returned a web page"):
                    get_video_path()

            self.assertFalse(cache_path.exists())

    def test_congestion_thresholds_are_explicit(self):
        self.assertEqual(estimate_congestion(0), "low")
        self.assertEqual(estimate_congestion(3), "low")
        self.assertEqual(estimate_congestion(4), "medium")
        self.assertEqual(estimate_congestion(8), "medium")
        self.assertEqual(estimate_congestion(9), "high")

    def test_missing_video_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing = Path(temporary_directory) / "missing.mp4"
            with self.assertRaisesRegex(FileNotFoundError, "Recorded video was not found"):
                process_video(missing, missing.with_name("output.mp4"))

    def test_missing_opencv_has_install_instructions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            video = Path(temporary_directory) / "input.mp4"
            video.touch()
            with patch.dict(sys.modules, {"cv2": None}):
                with self.assertRaisesRegex(RuntimeError, "OpenCV is not installed"):
                    process_video(video, video.with_name("output.mp4"))

    def test_missing_ultralytics_has_install_instructions(self):
        fake_cv2 = ModuleType("cv2")
        with tempfile.TemporaryDirectory() as temporary_directory:
            video = Path(temporary_directory) / "input.mp4"
            video.touch()
            with patch.dict(sys.modules, {"cv2": fake_cv2, "ultralytics": None}):
                with self.assertRaisesRegex(RuntimeError, "Ultralytics is not installed"):
                    process_video(video, video.with_name("output.mp4"))

    def test_open_video_with_no_readable_frames_has_useful_error(self):
        capture = FakeCapture([])
        fake_cv2 = ModuleType("cv2")
        fake_cv2.CAP_PROP_FPS = 1
        fake_cv2.CAP_PROP_FRAME_COUNT = 2
        fake_cv2.VideoCapture = lambda path: capture

        with tempfile.TemporaryDirectory() as temporary_directory:
            video = Path(temporary_directory) / "input.mp4"
            video.touch()
            fake_ultralytics = ModuleType("ultralytics")
            fake_ultralytics.YOLO = object
            with patch.dict(
                sys.modules,
                {"cv2": fake_cv2, "ultralytics": fake_ultralytics},
            ):
                with self.assertRaisesRegex(RuntimeError, "no frames could be read"):
                    process_video(video, video.with_name("output.mp4"))

    def test_process_counts_unique_track_ids_and_writes_annotated_frames(self):
        frames = [FakeFrame() for _ in range(3)]
        capture = FakeCapture(frames)
        writer = FakeWriter()
        fake_cv2 = ModuleType("cv2")
        fake_cv2.CAP_PROP_FPS = 1
        fake_cv2.CAP_PROP_FRAME_COUNT = 2
        fake_cv2.CAP_PROP_FRAME_WIDTH = 3
        fake_cv2.CAP_PROP_FRAME_HEIGHT = 4
        fake_cv2.FONT_HERSHEY_SIMPLEX = 0
        fake_cv2.LINE_AA = 0
        fake_cv2.VideoCapture = lambda path: capture
        fake_cv2.VideoWriter_fourcc = lambda *args: 0
        fake_cv2.VideoWriter = lambda *args: writer
        fake_cv2.putText = lambda *args: None

        observations = [
            ([2, 3], [11, 8]),
            ([2, 5], [11, 22]),
            ([7, 3], [33, 8]),
        ]

        class FakeYOLO:
            def __init__(self, model_name):
                self.frame_number = 0

            def track(self, frame, **kwargs):
                classes, ids = observations[self.frame_number]
                self.frame_number += 1
                boxes = SimpleNamespace(cls=classes, id=ids)
                return [SimpleNamespace(boxes=boxes, plot=frame.copy)]

        fake_ultralytics = ModuleType("ultralytics")
        fake_ultralytics.YOLO = FakeYOLO
        progress_updates = []

        with tempfile.TemporaryDirectory() as temporary_directory:
            video = Path(temporary_directory) / "input.mp4"
            video.touch()
            output = Path(temporary_directory) / "annotated.mp4"
            with patch.dict(
                sys.modules,
                {"cv2": fake_cv2, "ultralytics": fake_ultralytics},
            ):
                summary = process_video(
                    video,
                    output,
                    progress_callback=progress_updates.append,
                )

        self.assertEqual(
            summary["vehicle_counts"],
            {"car": 1, "motorcycle": 1, "bus": 1, "truck": 1},
        )
        self.assertEqual(summary["total_unique_vehicles"], 4)
        self.assertEqual(summary["total_detections"], 6)
        self.assertEqual(summary["processed_frames"], 3)
        self.assertEqual(summary["peak_simultaneous_vehicles"], 2)
        self.assertEqual(summary["congestion_estimate"], "low")
        self.assertEqual(len(writer.frames), 3)
        self.assertEqual(len(progress_updates), 3)
        self.assertIn("NOT LIVE CCTV", summary["video_label"])

    def test_model_load_failure_reports_download_troubleshooting(self):
        capture = FakeCapture([FakeFrame()])
        writer = FakeWriter()
        fake_cv2 = ModuleType("cv2")
        fake_cv2.CAP_PROP_FPS = 1
        fake_cv2.CAP_PROP_FRAME_COUNT = 2
        fake_cv2.VideoCapture = lambda path: capture
        fake_cv2.VideoWriter_fourcc = lambda *args: 0
        fake_cv2.VideoWriter = lambda *args: writer
        fake_ultralytics = ModuleType("ultralytics")

        class BrokenYOLO:
            def __init__(self, model_name):
                raise OSError("model download failed")

        fake_ultralytics.YOLO = BrokenYOLO
        with tempfile.TemporaryDirectory() as temporary_directory:
            video = Path(temporary_directory) / "input.mp4"
            video.touch()
            with patch.dict(
                sys.modules,
                {"cv2": fake_cv2, "ultralytics": fake_ultralytics},
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "network access for its first download",
                ):
                    process_video(video, video.with_name("output.mp4"))

    def test_background_job_reports_progress_and_final_video_url(self):
        job = VideoDetectionJob()
        background = FakeBackgroundTasks()
        queued = job.start(background)
        self.assertEqual(queued["status"], "queued")
        self.assertEqual(len(background.tasks), 1)

        result = {
            "status": "completed",
            "vehicle_counts": {"car": 2, "motorcycle": 0, "bus": 0, "truck": 0},
            "total_unique_vehicles": 2,
            "total_detections": 4,
            "processed_frames": 4,
            "output_file": "private/path/is/not/exposed.mp4",
        }
        with patch(
            "traffic.vehicle_detection.detect_vehicles.process_video",
            return_value=result,
        ):
            background.tasks[0]()

        completed = job.snapshot()
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["vehicle_counts"]["car"], 2)
        self.assertEqual(completed["output_video_url"], "/vehicle-detection/video")
        self.assertNotIn("output_file", completed)

    def test_background_job_exposes_processing_exception_as_failed(self):
        job = VideoDetectionJob()
        background = FakeBackgroundTasks()
        job.start(background)
        with patch(
            "traffic.vehicle_detection.detect_vehicles.process_video",
            side_effect=RuntimeError("YOLO model could not be loaded"),
        ):
            background.tasks[0]()

        failed = job.snapshot()
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["message"], "Recorded-video processing failed.")
        self.assertEqual(failed["error_message"], "YOLO model could not be loaded")

    def test_background_queue_failure_does_not_leave_job_queued(self):
        class BrokenBackgroundTasks:
            def add_task(self, function):
                raise RuntimeError("Background worker could not be scheduled")

        job = VideoDetectionJob()
        failed = job.start(BrokenBackgroundTasks())

        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error_message"], "Background worker could not be scheduled")


if __name__ == "__main__":
    unittest.main()
