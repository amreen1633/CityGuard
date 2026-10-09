"YOLO vehicle detection for the recorded CityGuard video demo."

from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VIDEO_PATH = PROJECT_ROOT / "traffic_videos" / "video3.mp4"
VIDEO_CACHE_PATH = Path(tempfile.gettempdir()) / "cityguard" / "video3.mp4"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve(
).parent / "outputs" / "video3_annotated.mp4"
DEFAULT_MODEL = os.environ.get("CITYGUARD_YOLO_MODEL", "yolo11n.pt")
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
CONGESTION_BASIS = (
    "Demo estimate from peak simultaneously detected vehicles in this recorded clip "
    "(low: 0-3, medium: 4-8, high: 9+); not a verified real-world traffic measurement."
)

logger = logging.getLogger(__name__)
_video_download_lock = threading.Lock()


class BackgroundTaskSink(Protocol):
    def add_task(self, function: Callable[[], None]) -> None: ...


def get_video_path() -> Path:
    """Resolve the local override, remote cache, or repository sample in order."""
    configured_path = os.environ.get("CITYGUARD_VIDEO_PATH", "").strip()
    if configured_path:
        path = Path(configured_path).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()

    video_url = os.environ.get("CITYGUARD_VIDEO_URL", "").strip()
    if not video_url:
        return DEFAULT_VIDEO_PATH

    with _video_download_lock:
        if VIDEO_CACHE_PATH.is_file() and VIDEO_CACHE_PATH.stat().st_size > 0:
            return VIDEO_CACHE_PATH
        _download_video(video_url, VIDEO_CACHE_PATH)
        return VIDEO_CACHE_PATH


def _download_video(video_url: str, destination: Path) -> None:
    """Download to a temporary file, then atomically publish the completed cache."""
    try:
        parsed_url = urlsplit(video_url)
    except ValueError:
        raise RuntimeError(
            "CITYGUARD_VIDEO_URL must be a valid HTTPS download URL."
        ) from None
    if parsed_url.scheme.lower() != "https" or not parsed_url.hostname:
        raise RuntimeError("CITYGUARD_VIDEO_URL must be a valid HTTPS download URL.")

    temporary_path: Path | None = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = Request(video_url, headers={"User-Agent": "CityGuard-Video-Demo/1.0"})
        with urlopen(request, timeout=60) as response:
            content_type = response.headers.get_content_type().lower()
            if content_type in {"text/html", "application/xhtml+xml"}:
                raise RuntimeError(
                    "The configured video URL returned a web page instead of the video. "
                    "Use a Google Drive direct-download URL and ensure the file is accessible."
                )

            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{destination.name}.",
                suffix=".download",
                dir=destination.parent,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                first_chunk = response.read(64 * 1024)
                if not first_chunk:
                    raise RuntimeError("The configured video URL returned an empty file.")
                if first_chunk.lstrip().lower().startswith((b"<!doctype html", b"<html")):
                    raise RuntimeError(
                        "The configured video URL returned a web page instead of the video. "
                        "Use a Google Drive direct-download URL and ensure the file is accessible."
                    )

                temporary_file.write(first_chunk)
                while chunk := response.read(1024 * 1024):
                    temporary_file.write(chunk)

        if temporary_path.stat().st_size == 0:
            raise RuntimeError("The configured video URL returned an empty file.")
        os.replace(temporary_path, destination)
        temporary_path = None
    except HTTPError as error:
        logger.warning("Recorded-video download failed with HTTP status %s", error.code)
        raise RuntimeError(
            f"Could not download the recorded video (HTTP {error.code}). "
            "Check the URL and file-sharing permissions."
        ) from None
    except URLError:
        logger.warning("Recorded-video download failed due to a URL or network error")
        raise RuntimeError(
            "Could not download the recorded video because of a network or URL error. "
            "Check the URL and outbound network access."
        ) from None
    except TimeoutError:
        logger.warning("Recorded-video download timed out")
        raise RuntimeError(
            "The recorded-video download timed out. Check outbound network access and try again."
        ) from None
    except OSError as error:
        logger.warning(
            "Recorded-video download failed due to a local file error (%s)",
            type(error).__name__,
        )
        raise RuntimeError(
            "Could not save the downloaded video to the local cache. "
            "Check that the Render service can write to its temporary directory."
        ) from None
    except ValueError:
        logger.warning("Recorded-video download failed because its URL is invalid")
        raise RuntimeError(
            "CITYGUARD_VIDEO_URL is invalid. Provide a valid HTTPS direct-download URL."
        ) from None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def estimate_congestion(peak_simultaneous_vehicles: int) -> str:
    """Return an explicitly illustrative level from the clip's observed peak."""
    if peak_simultaneous_vehicles <= 3:
        return "low"
    if peak_simultaneous_vehicles <= 8:
        return "medium"
    return "high"


def _to_list(value: object) -> list:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    # type: ignore[arg-type]
    return value if isinstance(value, list) else list(value)


def _empty_summary() -> dict[str, object]:
    return {
        "video_label": "RECORDED VIDEO DEMO — NOT LIVE CCTV",
        "status": "idle",
        "vehicle_counts": {name: 0 for name in VEHICLE_CLASSES.values()},
        "total_unique_vehicles": 0,
        "total_detections": 0,
        "untracked_detections": 0,
        "processed_frames": 0,
        "total_frames": 0,
        "progress_percent": 0,
        "peak_simultaneous_vehicles": 0,
        "congestion_estimate": None,
        "congestion_basis": CONGESTION_BASIS,
        "model": DEFAULT_MODEL,
        "message": "Recorded-video processing has not started.",
        "error_message": None,
    }


def process_video(
    video_path: Path | str | None = None,
    output_path: Path | str = DEFAULT_OUTPUT_PATH,
    model_name: str = DEFAULT_MODEL,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, object]:
    """Track supported COCO vehicles in a clip and save an annotated MP4."""
    source = Path(video_path).expanduser().resolve(
    ) if video_path is not None else get_video_path()
    destination = Path(output_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Recorded video was not found: {source}")

    try:
        import cv2
    except ImportError as error:
        raise RuntimeError(
            "OpenCV is not installed. From the project root run: "
            "backend\\venv\\Scripts\\python.exe -m pip install -r "
            "traffic\\vehicle_detection\\requirements.txt"
        ) from error
    try:
        from ultralytics import YOLO
    except ImportError as error:
        raise RuntimeError(
            "Ultralytics is not installed. From the project root run: "
            "backend\\venv\\Scripts\\python.exe -m pip install -r "
            "traffic\\vehicle_detection\\requirements.txt"
        ) from error

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(
            f"OpenCV could not open the recorded video: {source}. "
            "Check that the MP4 is readable and its video codec is supported."
        )

    writer = None
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        if fps <= 0:
            fps = 25.0
        total_frames = max(0, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError(
                f"The video opened but no frames could be read: {source}. "
                "The file may be empty, truncated, or use an unsupported codec."
            )

        height, width = frame.shape[:2]
        destination.parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(
            str(destination), fourcc, fps, (width, height))
        if not writer.isOpened():
            raise RuntimeError(
                f"OpenCV could not create the annotated MP4: {destination}. "
                "Check write permissions and MP4 codec support."
            )

        try:
            model = YOLO(model_name)
        except Exception as error:
            raise RuntimeError(
                f"Could not load YOLO model '{model_name}'. Check the model name, "
                "network access for its first download, and available disk space."
            ) from error

        tracked_ids: dict[str, set[int]] = {
            name: set() for name in VEHICLE_CLASSES.values()
        }
        total_detections = 0
        untracked_detections = 0
        processed_frames = 0
        peak_simultaneous_vehicles = 0

        while ok and frame is not None:
            try:
                results = model.track(
                    frame,
                    persist=True,
                    tracker="bytetrack.yaml",
                    classes=list(VEHICLE_CLASSES),
                    verbose=False,
                )
            except Exception as error:
                raise RuntimeError(
                    "YOLO could not process a video frame. The model may have failed "
                    "to download or initialize; check network access and try again."
                ) from error

            result = results[0] if results else None
            boxes = getattr(result, "boxes", None)
            class_ids = _to_list(
                boxes.cls) if boxes is not None and boxes.cls is not None else []
            track_ids = (
                _to_list(boxes.id)
                if boxes is not None and boxes.id is not None
                else []
            )
            observed_this_frame = 0
            for index, class_value in enumerate(class_ids):
                class_id = int(class_value)
                class_name = VEHICLE_CLASSES.get(class_id)
                if class_name is None:
                    continue

                total_detections += 1
                observed_this_frame += 1
                track_id = int(track_ids[index]) if index < len(
                    track_ids) else None
                if track_id is None:
                    untracked_detections += 1
                else:
                    tracked_ids[class_name].add(track_id)

            peak_simultaneous_vehicles = max(
                peak_simultaneous_vehicles, observed_this_frame
            )
            annotated = result.plot() if result is not None else frame.copy()
            counts = {
                name: len(ids) for name, ids in tracked_ids.items()
            }
            overlay = [
                "RECORDED VIDEO DEMO - NOT LIVE CCTV",
                f"Vehicles in current frame: {observed_this_frame}",
                *(f"{name.title()} tracks: {counts[name]}" for name in VEHICLE_CLASSES.values()),
                f"Unique tracked vehicles: {sum(counts.values())}",
            ]
            for line_number, text in enumerate(overlay):
                cv2.putText(
                    annotated,
                    text,
                    (16, 28 + line_number * 27),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )
            writer.write(annotated)
            processed_frames += 1

            current_summary = {
                "vehicle_counts": counts,
                "total_unique_vehicles": sum(counts.values()),
                "total_detections": total_detections,
                "untracked_detections": untracked_detections,
                "processed_frames": processed_frames,
                "total_frames": total_frames,
                "progress_percent": (
                    min(100, round(processed_frames * 100 / total_frames))
                    if total_frames
                    else 0
                ),
                "peak_simultaneous_vehicles": peak_simultaneous_vehicles,
                "congestion_estimate": estimate_congestion(peak_simultaneous_vehicles),
                "congestion_basis": CONGESTION_BASIS,
                "model": model_name,
            }
            if progress_callback is not None:
                progress_callback(current_summary)

            ok, frame = capture.read()

        if processed_frames == 0:
            raise RuntimeError(
                f"No video frames were processed from {source}.")
        if total_frames and processed_frames + max(2, round(total_frames * 0.01)) < total_frames:
            raise RuntimeError(
                f"Video reading stopped after {processed_frames} of {total_frames} "
                "reported frames. The file may be truncated or contain an unsupported codec."
            )

        return {
            **current_summary,
            "progress_percent": 100,
            "video_label": "RECORDED VIDEO DEMO — NOT LIVE CCTV",
            "status": "completed",
            "output_file": str(destination),
            "message": "Annotated video processing completed.",
        }
    finally:
        capture.release()
        if writer is not None:
            writer.release()


class VideoDetectionJob:
    """Single in-process background job for the optional FastAPI demo."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = _empty_summary()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {**self._state, "vehicle_counts": dict(self._state["vehicle_counts"])}

    def start(self, background_tasks: BackgroundTaskSink) -> dict[str, object]:
        with self._lock:
            if self._state["status"] in {"queued", "running"}:
                raise RuntimeError(
                    "Recorded-video processing is already running.")
            self._state = {
                **_empty_summary(),
                "status": "queued",
                "message": "Recorded-video processing is queued.",
            }
        try:
            background_tasks.add_task(self.run)
        except Exception as error:
            logger.exception(
                "Could not queue recorded-video vehicle detection")
            with self._lock:
                self._state.update(
                    status="failed",
                    message="Recorded-video processing could not be queued.",
                    error_message=str(error),
                )
        return self.snapshot()

    def _update_progress(self, progress: dict[str, object]) -> None:
        with self._lock:
            self._state.update(progress)

    def run(self) -> None:
        with self._lock:
            self._state["status"] = "running"
            self._state["message"] = "Processing recorded video with YOLO and ByteTrack."
        try:
            summary = process_video(progress_callback=self._update_progress)
        except Exception as error:
            logger.exception("Recorded-video vehicle detection failed")
            with self._lock:
                self._state.update(
                    status="failed",
                    message="Recorded-video processing failed.",
                    error_message=str(error),
                )
            return

        with self._lock:
            self._state.update(
                {key: value for key, value in summary.items() if key !=
                 "output_file"}
            )
            self._state["error_message"] = None
            self._state["output_video_url"] = "/vehicle-detection/video"


video_detection_job = VideoDetectionJob()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Process the CityGuard recorded-video vehicle detection demo."
    )
    parser.add_argument("--video", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    try:
        result = process_video(args.video, args.output, args.model)
    except (FileNotFoundError, RuntimeError) as error:
        parser.exit(1, f"Vehicle detection failed: {error}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
