from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, Base, get_db
from models import Report


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
    report: dict,
    db: Session = Depends(get_db)
):

    new_report = Report(
        title=report.get("title", "Unknown"),
        description=report.get("description", ""),
        severity=report.get("severity", "Medium"),
        status=report.get("status", "Pending"),
        location=report.get("location", "Unknown"),
        type=report.get("type", "General")
    )

    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    return {
        "message": "Report created successfully",
        "id": new_report.id
    }
