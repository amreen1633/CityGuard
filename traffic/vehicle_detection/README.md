# Recorded-video vehicle detection demo

This optional feature analyzes `traffic_videos/video3.mp4` with Ultralytics YOLO
and ByteTrack. It is a **RECORDED VIDEO DEMO — NOT LIVE CCTV**. It does not
connect to cameras or operate traffic signals.

## Windows PowerShell setup

Run commands from the repository root. Install the optional dependencies into
the project's existing backend virtual environment:

```powershell
.\backend\venv\Scripts\python.exe -m pip install -r .\traffic\vehicle_detection\requirements.txt
```

The first run downloads the default `yolo11n.pt` model from Ultralytics. Ensure
network access and enough disk space. Set `CITYGUARD_YOLO_MODEL` only if you
want the API job to use another locally available or supported model name; no
camera credentials or API keys are needed.

## Run the video processor directly

```powershell
.\backend\venv\Scripts\python.exe .\traffic\vehicle_detection\detect_vehicles.py
```

The annotated video is written to
`traffic\vehicle_detection\outputs\video3_annotated.mp4`; the output directory
is ignored by Git. Optional inputs can be provided with `--video`, `--output`,
and `--model`.

## Run through the dashboard

Start the existing FastAPI app from the repository root:

```powershell
.\backend\venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --reload
```

Open `frontend\admin.html`, go to **Video Demo**, then select **Process recorded
video**. The API queues a background task; use **Refresh status** to inspect it.
The dashboard polls while processing and provides a link to the annotated video
when complete.

The optional API routes are:

- `POST /vehicle-detection/start` — queue the fixed sample-video job.
- `GET /vehicle-detection/status` — processing status and latest progress/counts.
- `GET /vehicle-detection/results` — latest result and counts.
- `GET /vehicle-detection/video` — annotated MP4 after a successful run.

Counts by vehicle class are unique ByteTrack IDs observed across the clip.
`total_detections` counts frame-level detections (so the same vehicle may
contribute more than once); untracked detections are reported separately.
Congestion is only a demo estimate based on the peak number detected in one
frame: low (0-3), medium (4-8), or high (9+). It is not a calibrated or
verified real-world traffic measurement. The single-process in-memory job
status resets when the API restarts.

Missing dependencies, unreadable video, model download/inference failures, and
output writer errors are surfaced in the CLI or job status with an actionable
message. Detection is performed only when this optional feature is started;
the existing reports and traffic-simulation endpoints do not load YOLO.
