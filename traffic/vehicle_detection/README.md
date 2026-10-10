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

If `yolo11n.pt` (or the model selected by `CITYGUARD_YOLO_MODEL`) is already
available in the working directory, backend directory, or project root, the
processor reuses that local file. Otherwise, Ultralytics downloads the model on
first use, so ensure network access and enough disk space. No camera
credentials or API keys are needed.

## Render video file

The default video is the repository-local `traffic_videos/video3.mp4`. An
explicit `CITYGUARD_VIDEO_PATH` always takes precedence and points to a local
file (relative paths resolve from the repository root; absolute paths are
recommended on Render).

The sample video is intentionally excluded by the repository's `.gitignore`,
so it is not present in a normal GitHub deployment. Do not commit it or make a
private incident video world-readable to work around this. Alternatively, set
`CITYGUARD_VIDEO_URL` to an HTTPS direct-download URL for the demo video. With
this option the backend downloads to a cache at
`<system-temp>\cityguard\video3.mp4` (on Render, normally
`/tmp/cityguard/video3.mp4`) only when that file is missing or empty. A
non-empty cache is reused rather than downloaded on each processing request.
For Google Drive, use its direct-download URL form, such as
`https://drive.google.com/uc?export=download&id=FILE_ID`, and ensure the file's
sharing settings allow the Render service to download it. Google Drive may
return a confirmation or sign-in HTML page instead; the backend rejects that
response rather than caching it as a video.

For a private clip, a persistent disk (if available for the Render service
plan) or private object storage with a short-lived, read-only signed URL is
safer than a public share link. Store the URL only in Render's environment
settings/secrets, never in source code; errors and logs do not include its
value. Render's ordinary instance filesystem and `/tmp` cache can be ephemeral,
so the video may need to download again after restart or redeploy. Configure
`CITYGUARD_VIDEO_PATH` instead if the file is already present on a mounted disk;
when both variables are set, the explicit local path wins.

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
Frames are processed one at a time. Frames larger than 640 pixels on their
longest side are resized for inference, while the annotated output retains the
source video dimensions.
Congestion is only a demo estimate based on the peak number detected in one
frame: low (0-3), medium (4-8), or high (9+). It is not a calibrated or
verified real-world traffic measurement. The single-process in-memory job
status resets when the API restarts.

Missing dependencies, unreadable video, model download/inference failures, and
output writer errors are surfaced in the CLI or job status with an actionable
message. Detection is performed only when this optional feature is started;
the existing reports and traffic-simulation endpoints do not load YOLO.
