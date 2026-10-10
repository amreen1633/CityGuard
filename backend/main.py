from functools import lru_cache
from pathlib import Path
import sys

from fastapi import BackgroundTasks, FastAPI, Depends, Form, UploadFile, File, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import engine, Base, get_db
from models import Report

# The backend is normally launched from its own directory, so add the project
# root to imports for the sibling AI package without changing the launch command.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.ai_service import analyze_civic_report, recommend_traffic_signal_timing
from traffic.vehicle_detection.detect_vehicles import (
    DEFAULT_OUTPUT_PATH,
    video_detection_job,
)

# Create database tables
Base.metadata.create_all(bind=engine)


app = FastAPI(title="CityGuard API")


# Allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=512)
def cached_report_assessment(title: str, description: str):
    """Cache transient AI results without changing the existing database schema."""
    try:
        return analyze_civic_report(title, description)
    except Exception as error:
        print("Report AI assessment unavailable:", error)
        return {
            "category": None,
            "severity": None,
            "confidence": 0.0,
            "department": None,
            "ai_status": "unavailable",
            "explanation": "AI assessment failed; the saved report remains available for human review.",
            "emergency_review": None,
            "emergency_reason": None,
            "recommended_next_step": "Review the original citizen-submitted report manually.",
            "emergency_ai_status": "unavailable",
        }


@app.get("/")
def home():
    return {
        "message": "CityGuard Backend is Running"
    }


# Dashboard statistics
@app.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):

    reports = db.query(Report).all()

    total_reports = len(reports)

    total_emergencies = len([
        r for r in reports
        if r.type.lower() == "emergency"
    ])

    pending_reports = len([
        r for r in reports
        if r.status.lower() == "pending"
    ])

    resolved_reports = len([
        r for r in reports
        if r.status.lower() == "resolved"
    ])

    return {
        "total_reports": total_reports,
        "total_emergencies": total_emergencies,
        "pending_reports": pending_reports,
        "resolved_reports": resolved_reports
    }


# Get all reports
@app.get("/reports")
def get_reports(db: Session = Depends(get_db)):

    reports = db.query(Report).all()

    return [
        {
            "id": r.id,
            "title": r.title,
            "description": r.description,
            "severity": r.severity,
            "status": r.status,
            "location": r.location,
            "type": r.type,
            "ai_assessment": cached_report_assessment(r.title, r.description)
        }
        for r in reports
    ]


# Add a new report
@app.post("/reports")
def create_report(
    title: str = Form(...),
    description: str = Form(...),
    location: str = Form(...),
    severity: str = Form("Medium"),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):

    new_report = Report(
        title=title,
        description=description,
        severity=severity,
        status="Pending",
        location=location,
        type="General"
    )

    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    assessment = cached_report_assessment(new_report.title, new_report.description)

    return {
        "message": "Report created successfully",
        "id": new_report.id,
        "image": image.filename if image else None,
        "ai_assessment": assessment
    }


@app.get("/traffic-analysis")
def traffic_analysis(
    congestion_level: str = Query(...),
    vehicle_count: str = Query(...),
    rule_based: bool = Query(False),
):
    """Return a simulation-only timing recommendation; it never applies a signal."""
    if rule_based:
        return recommend_traffic_signal_timing(
            congestion_level,
            vehicle_count,
            rule_based=True,
        )
    return recommend_traffic_signal_timing(congestion_level, vehicle_count)


@app.post("/vehicle-detection/start")
def start_vehicle_detection(background_tasks: BackgroundTasks):
    """Queue recorded-video processing without blocking the API request."""
    try:
        return video_detection_job.start(background_tasks)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/vehicle-detection/status")
def vehicle_detection_status():
    """Return status and the latest available progress/counts."""
    return video_detection_job.snapshot()


@app.get("/vehicle-detection/results")
def vehicle_detection_results():
    """Return final or in-progress recorded-video counts."""
    return video_detection_job.snapshot()


@app.get("/vehicle-detection/video")
def vehicle_detection_video():
    """Serve the annotated output after a successful recorded-video run."""
    state = video_detection_job.snapshot()
    if state["status"] != "completed" or not DEFAULT_OUTPUT_PATH.is_file():
        raise HTTPException(
            status_code=404,
            detail="Annotated video is not available yet. Complete the recorded-video demo first.",
        )
    return FileResponse(
        DEFAULT_OUTPUT_PATH,
        media_type="video/mp4",
        filename=DEFAULT_OUTPUT_PATH.name,
    )
