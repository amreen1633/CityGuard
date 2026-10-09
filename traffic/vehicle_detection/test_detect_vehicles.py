import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from traffic.vehicle_detection.detect_vehicles import (
    VideoDetectionJob,
    estimate_congestion,
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
