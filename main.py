import os
import io
import csv
import asyncio
import hashlib
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File, Form, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from config import settings
from database import init_db, get_db
from models import FloodLog, User, Colony, CommunityReport, ColonyAlert
from schemas import (
    LogEntry, StatsSummary, SourceChangeRequest, ThresholdSettings,
    UserRegister, UserLogin, UserResponse, ColonyCreate, ColonyResponse,
    CommunityReportResponse, ColonyAlertResponse
)
from vision import vision_engine
from stream_manager import stream_manager
from report_analyzer import analyze_community_video
from colony_notifier import colony_notifier

# -------------------------------------------------------------
# 🚀 LIFESPAN MANAGEMENT
# -------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[SERVER] Initializing Database & Seed Data...")
    init_db()
    print("[SERVER] Starting StreamManager Background Worker...")
    stream_manager.start()
    yield
    print("[SERVER] Stopping StreamManager Worker...")
    stream_manager.stop()

# -------------------------------------------------------------
# 🌐 FASTAPI APP INITIALIZATION
# -------------------------------------------------------------
app = FastAPI(
    title="FloodGuard AI - Community Flood Detection & Emergency Broadcast Network",
    description="Full-stack Disaster Analytics with Colony Logins, ML Video Verification & Location-based Broadcasts",
    version="2.1.0",
    lifespan=lifespan
)

# Ensure upload directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(settings.UPLOAD_DIR, "thumbnails"), exist_ok=True)

# Static files & HTML templates
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SALT = b"floodguard_secure_salt_2026"

def hash_pw(password: str) -> str:
    # PBKDF2 HMAC SHA-256 for secure password storage
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), SALT, 100000).hex()

def verify_pw(password: str, stored_hash: str) -> bool:
    # Check PBKDF2 or fallback plain sha256 for backward compatibility
    calculated_pbkdf2 = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), SALT, 100000).hex()
    if calculated_pbkdf2 == stored_hash:
        return True
    return hashlib.sha256(password.encode("utf-8")).hexdigest() == stored_hash

# -------------------------------------------------------------
# 🎯 DASHBOARD ROUTE
# -------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "active_source": stream_manager.source_type,
        "default_video": settings.DEFAULT_VIDEO_PATH
    })

# -------------------------------------------------------------
# 👥 USER AUTHENTICATION & COLONY REGISTRATION APIS
# -------------------------------------------------------------
@app.post("/api/auth/register", response_model=UserResponse)
async def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    # 1. Password Confirmation Check
    if payload.confirm_password and payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match. Please re-enter identical passwords.")

    # 2. Check for Duplicate Email
    existing_email = db.query(User).filter(User.email == payload.email).first()
    if existing_email:
        raise HTTPException(
            status_code=400,
            detail=f"An account with email '{payload.email}' is already registered. Please login instead."
        )
    
    # 3. Check for Duplicate Phone (if provided)
    if payload.phone:
        existing_phone = db.query(User).filter(User.phone == payload.phone).first()
        if existing_phone:
            raise HTTPException(
                status_code=400,
                detail=f"The mobile number '{payload.phone}' is already associated with another account."
            )

    try:
        # 4. Ensure colony exists in colonies directory
        colony_entry = db.query(Colony).filter(Colony.name == payload.colony_name).first()
        if not colony_entry:
            colony_entry = Colony(name=payload.colony_name, city=payload.city or "General")
            db.add(colony_entry)
            db.commit()

        # 5. Create new User Record
        new_user = User(
            name=payload.name.strip(),
            email=payload.email.strip().lower(),
            phone=payload.phone,
            password_hash=hash_pw(payload.password),
            colony_name=payload.colony_name.strip(),
            city=payload.city or "General Area",
            role="resident"
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except Exception as e:
        db.rollback()
        print(f"[AUTH ERROR] Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Database registration failed. Please try again.")

@app.post("/api/auth/login")
async def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    normalized_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    
    if not user or not verify_pw(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password. Please check your credentials.")
    
    return {
        "status": "success",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "colony_name": user.colony_name,
            "city": user.city,
            "role": user.role
        }
    }

# -------------------------------------------------------------
# 🏘️ COLONY DIRECTORY APIS
# -------------------------------------------------------------
@app.get("/api/colonies")
async def get_colonies(db: Session = Depends(get_db)):
    colonies = db.query(Colony).order_by(Colony.name).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "city": c.city,
            "pincode": c.pincode,
            "alert_level": c.alert_level,
            "total_reports": db.query(CommunityReport).filter(CommunityReport.colony_name == c.name).count()
        }
        for c in colonies
    ]

@app.post("/api/colonies")
async def create_colony(payload: ColonyCreate, db: Session = Depends(get_db)):
    existing = db.query(Colony).filter(Colony.name == payload.name).first()
    if existing:
        return {"status": "exists", "colony": existing.name}
    
    colony = Colony(name=payload.name, city=payload.city or "General", pincode=payload.pincode or "000000")
    db.add(colony)
    db.commit()
    return {"status": "created", "colony": colony.name}

# -------------------------------------------------------------
# 📹 CROWDSOURCED CITIZEN VIDEO REPORTING & ML VERIFICATION
# -------------------------------------------------------------
@app.post("/api/reports/upload")
async def upload_community_report(
    file: UploadFile = File(...),
    colony_name: str = Form(...),
    landmark: str = Form(...),
    user_name: str = Form("Colony Resident"),
    user_phone: str = Form(None),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    """
    Citizen Video Upload with Automated ML & Optical Flow Verification.
    
    1. Saves video in uploads folder.
    2. Runs MobileNetV2 inference & Lucas-Kanade velocity analyzer across sampled frames.
    3. Verifies flood status and generates a preview thumbnail.
    4. If verified flood, automatically updates colony threat level and broadcasts an instant alert to all residents.
    """
    safe_filename = f"{int(datetime.utcnow().timestamp())}_{file.filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Automated ML Verification
    print(f"[ML VERIFICATION] Running automated analysis on uploaded video: {file_path}")
    verification = analyze_community_video(file_path)
    print(f"[ML VERIFICATION] Result: {verification}")

    # Create Community Report in DB
    report = CommunityReport(
        user_name=user_name or "Colony Resident",
        user_phone=user_phone,
        colony_name=colony_name,
        landmark=landmark,
        video_path=f"/uploads/{safe_filename}",
        thumbnail_path=verification.get("thumbnail_path"),
        description=description,
        ml_confidence=verification.get("ml_confidence", 0.0),
        ml_velocity=verification.get("ml_velocity", 0.0),
        ml_status=verification.get("ml_status", "PENDING"),
        upvotes=1,
        status="ACTIVE",
        created_at=datetime.utcnow()
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # Check and update Colony Alert Status
    colony = db.query(Colony).filter(Colony.name == colony_name).first()
    severity = "SAFE"
    if verification["ml_status"] == "VERIFIED FLOOD":
        severity = "CRITICAL FLOOD"
        if colony:
            colony.alert_level = "CRITICAL FLOOD"
    elif verification["ml_status"] == "WARNING":
        severity = "WARNING"
        if colony and colony.alert_level != "CRITICAL FLOOD":
            colony.alert_level = "WARNING"
    
    if colony:
        db.commit()

    # If severe or warning, generate an official ColonyAlert in DB
    if severity in ["CRITICAL FLOOD", "WARNING"]:
        alert_entry = ColonyAlert(
            colony_name=colony_name,
            severity=severity,
            title=f"🚨 Inundation Reported at {landmark}",
            message=f"Resident report confirmed by AI ({verification['ml_confidence']}% Flood Confidence, Flow: {verification['ml_velocity']} m/s). Avoid {landmark}.",
            landmark=landmark,
            source_report_id=report.id,
            created_at=datetime.utcnow()
        )
        db.add(alert_entry)
        db.commit()

    # REAL-TIME BROADCAST: Send live notification to all residents in this colony
    broadcast_payload = {
        "report_id": report.id,
        "user_name": report.user_name,
        "colony_name": report.colony_name,
        "landmark": report.landmark,
        "description": report.description,
        "ml_confidence": report.ml_confidence,
        "ml_velocity": report.ml_velocity,
        "ml_status": report.ml_status,
        "thumbnail_path": report.thumbnail_path,
        "video_path": report.video_path,
        "severity": severity,
        "created_at": report.created_at.strftime("%Y-%m-%d %H:%M:%S")
    }

    # Asynchronously broadcast to connected colony room
    asyncio.create_task(
        colony_notifier.broadcast_to_colony(
            colony_name=colony_name,
            event_type="EMERGENCY_BROADCAST" if severity == "CRITICAL FLOOD" else "NEW_COMMUNITY_REPORT",
            payload=broadcast_payload
        )
    )

    return {
        "status": "success",
        "report": {
            "id": report.id,
            "colony_name": report.colony_name,
            "landmark": report.landmark,
            "ml_confidence": report.ml_confidence,
            "ml_velocity": report.ml_velocity,
            "ml_status": report.ml_status,
            "thumbnail_path": report.thumbnail_path,
            "severity": severity
        }
    }

@app.get("/api/reports")
async def get_community_reports(
    colony: str = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Retrieve community-submitted flood reports."""
    query = db.query(CommunityReport).order_by(desc(CommunityReport.created_at))
    if colony and colony != "ALL":
        query = query.filter(CommunityReport.colony_name == colony)
    
    reports = query.limit(limit).all()
    return [
        {
            "id": r.id,
            "user_name": r.user_name,
            "colony_name": r.colony_name,
            "landmark": r.landmark,
            "description": r.description or "",
            "video_path": r.video_path,
            "thumbnail_path": r.thumbnail_path,
            "ml_confidence": r.ml_confidence,
            "ml_velocity": r.ml_velocity,
            "ml_status": r.ml_status,
            "upvotes": r.upvotes,
            "status": r.status,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "--"
        }
        for r in reports
    ]

@app.post("/api/reports/{report_id}/upvote")
async def upvote_report(report_id: int, db: Session = Depends(get_db)):
    """Allow colony residents to confirm/upvote active reports."""
    report = db.query(CommunityReport).filter(CommunityReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    
    report.upvotes += 1
    db.commit()
    return {"status": "success", "id": report.id, "upvotes": report.upvotes}

@app.get("/api/alerts")
async def get_colony_alerts(colony: str = Query(None), db: Session = Depends(get_db)):
    """Retrieve emergency broadcasts for active colony."""
    query = db.query(ColonyAlert).order_by(desc(ColonyAlert.created_at))
    if colony and colony != "ALL":
        query = query.filter(ColonyAlert.colony_name == colony)
        
    alerts = query.limit(15).all()
    return [
        {
            "id": a.id,
            "colony_name": a.colony_name,
            "severity": a.severity,
            "title": a.title,
            "message": a.message,
            "landmark": a.landmark,
            "created_at": a.created_at.strftime("%H:%M:%S") if a.created_at else "--"
        }
        for a in alerts
    ]

# -------------------------------------------------------------
# 📡 COLONY-SPECIFIC WEBSOCKET ROOM (LOCATION-AWARE BROADCAST)
# -------------------------------------------------------------
@app.websocket("/ws/colony/{colony_name}")
async def websocket_colony_room(websocket: WebSocket, colony_name: str):
    await colony_notifier.connect(colony_name, websocket)
    try:
        while True:
            # Keep-alive receive ping
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await colony_notifier.disconnect(colony_name, websocket)
    except Exception as e:
        await colony_notifier.disconnect(colony_name, websocket)

# -------------------------------------------------------------
# 🎥 MJPEG VIDEO STREAM ROUTE (CCTV / DEMO STREAM)
# -------------------------------------------------------------
import time

def generate_mjpeg_frames():
    while True:
        frame_bytes = stream_manager.get_latest_frame()
        if frame_bytes is None:
            time.sleep(0.04)
            continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' +
               frame_bytes + b'\r\n')
        time.sleep(0.033)

@app.get("/api/video_feed")
def video_feed():
    return StreamingResponse(
        generate_mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# -------------------------------------------------------------
# 📡 CCTV TELEMETRY WEBSOCKET ROUTE
# -------------------------------------------------------------
@app.websocket("/ws/stream")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            telemetry = stream_manager.get_latest_telemetry()
            await websocket.send_json(telemetry)
            await asyncio.sleep(0.15)
    except Exception as e:
        pass

# -------------------------------------------------------------
# ⚙️ STREAM SOURCE CONTROL APIS
# -------------------------------------------------------------
@app.post("/api/change_source")
async def change_source(request: SourceChangeRequest):
    success = stream_manager.set_source(
        source_type=request.source_type,
        custom_path=request.file_path,
        camera_idx=request.camera_index or 0
    )
    return {
        "status": "success",
        "active_source": stream_manager.source_type,
        "source_path": stream_manager.source_path,
        "camera_index": stream_manager.camera_index
    }

@app.post("/api/upload_video")
async def upload_video(file: UploadFile = File(...)):
    file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
        
    stream_manager.set_source("upload", custom_path=file_path)
    return {
        "status": "success",
        "filename": file.filename,
        "message": "Uploaded video loaded into stream."
    }

@app.post("/api/toggle_vectors")
async def toggle_vectors():
    vision_engine.show_vectors = not vision_engine.show_vectors
    return {"status": "success", "show_vectors": vision_engine.show_vectors}

@app.post("/api/toggle_hud")
async def toggle_hud():
    vision_engine.show_hud = not vision_engine.show_hud
    return {"status": "success", "show_hud": vision_engine.show_hud}

@app.get("/api/logs")
async def get_logs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    logs = db.query(FloodLog).order_by(desc(FloodLog.timestamp)).offset(offset).limit(limit).all()
    return [
        {
            "id": log.id,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else "--",
            "status": log.status,
            "velocity": round(log.velocity, 2) if log.velocity else 0.0,
            "confidence": round(log.confidence, 1) if log.confidence else 0.0,
            "source_type": log.source_type or "video"
        }
        for log in logs
    ]

@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    total_logs = db.query(FloodLog).count()
    critical_alerts = db.query(FloodLog).filter(FloodLog.status == "CRITICAL FLOOD").count()
    warnings = db.query(FloodLog).filter(FloodLog.status == "WARNING").count()
    advisories = db.query(FloodLog).filter(FloodLog.status == "ADVISORY").count()
    
    total_community_reports = db.query(CommunityReport).count()
    total_colonies = db.query(Colony).count()

    peak_velocity = db.query(func.max(FloodLog.velocity)).scalar() or 0.0
    peak_confidence = db.query(func.max(FloodLog.confidence)).scalar() or 0.0
    
    latest_telemetry = stream_manager.get_latest_telemetry()

    return {
        "total_logs": total_logs,
        "critical_alerts": critical_alerts,
        "warnings": warnings,
        "advisories": advisories,
        "total_community_reports": total_community_reports,
        "total_colonies": total_colonies,
        "peak_velocity": round(float(peak_velocity), 2),
        "peak_confidence": round(float(peak_confidence), 1),
        "current_status": latest_telemetry.get("status", "SAFE"),
        "active_source": stream_manager.source_type,
        "fps": latest_telemetry.get("fps", 0.0),
        "latency_ms": latest_telemetry.get("latency_ms", 0.0)
    }

@app.get("/api/export")
async def export_logs_csv(db: Session = Depends(get_db)):
    logs = db.query(FloodLog).order_by(desc(FloodLog.timestamp)).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp (UTC)", "Status", "Velocity (m/s)", "Confidence (%)", "Source"])
    for l in logs:
        writer.writerow([
            l.id,
            l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "",
            l.status,
            round(l.velocity, 2) if l.velocity else 0.0,
            round(l.confidence, 1) if l.confidence else 0.0,
            l.source_type or "video"
        ])
    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=flood_incident_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )

@app.post("/api/settings")
async def update_settings(payload: ThresholdSettings):
    if payload.confidence_flood is not None:
        settings.CONFIDENCE_THRESHOLD_FLOOD = payload.confidence_flood
    if payload.confidence_warning is not None:
        settings.CONFIDENCE_THRESHOLD_WARNING = payload.confidence_warning
    if payload.velocity_warning is not None:
        settings.VELOCITY_THRESHOLD_WARNING = payload.velocity_warning
    if payload.velocity_flood is not None:
        settings.VELOCITY_THRESHOLD_FLOOD = payload.velocity_flood
        
    return {
        "status": "success",
        "thresholds": {
            "confidence_flood": settings.CONFIDENCE_THRESHOLD_FLOOD,
            "confidence_warning": settings.CONFIDENCE_THRESHOLD_WARNING,
            "velocity_warning": settings.VELOCITY_THRESHOLD_WARNING,
            "velocity_flood": settings.VELOCITY_THRESHOLD_FLOOD
        }
    }