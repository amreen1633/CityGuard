from fastapi import FastAPI, Depends, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, Base, get_db
from models import Report
from ai.ai_service import classify_civic_issue
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
            "type": r.type
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
    # AI classification
    ai_result = classify_civic_issue(description)

    new_report = Report(
        title=title,
        description=description,
        severity=ai_result["severity"],
        status="Pending",
        location=location,
        type=ai_result["category"]
    )

    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    return {
        "message": "Report created successfully",
        "id": new_report.id,
        "image": image.filename if image else None
    }
