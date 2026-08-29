from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Text
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    phone = Column(String(20), nullable=True)
    password_hash = Column(String(255), nullable=False)
    colony_name = Column(String(100), index=True, nullable=False)
    city = Column(String(100), default="General Area")
    role = Column(String(30), default="resident")  # "resident", "admin", "authority"
    created_at = Column(DateTime, default=datetime.utcnow)

class Colony(Base):
    __tablename__ = "colonies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    city = Column(String(100), default="General")
    pincode = Column(String(20), default="000000")
    alert_level = Column(String(32), default="SAFE")  # SAFE, ADVISORY, WARNING, CRITICAL FLOOD
    total_reports = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class CommunityReport(Base):
    __tablename__ = "community_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String(100), default="Colony Resident")
    user_phone = Column(String(20), nullable=True)
    colony_name = Column(String(100), index=True, nullable=False)
    landmark = Column(String(200), nullable=False)  # e.g., "Main Gate 2", "Market Road"
    video_path = Column(String(300), nullable=False)
    thumbnail_path = Column(String(300), nullable=True)
    description = Column(Text, nullable=True)
    
    # Automated ML Verification Metrics
    ml_confidence = Column(Float, default=0.0)      # % Flood Probability
    ml_velocity = Column(Float, default=0.0)        # Flow speed (m/s)
    ml_status = Column(String(32), default="PENDING") # VERIFIED FLOOD, WARNING, SAFE / FALSE ALARM
    
    upvotes = Column(Integer, default=1)
    status = Column(String(32), default="ACTIVE")    # ACTIVE, RESOLVED
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class ColonyAlert(Base):
    __tablename__ = "colony_alerts"

    id = Column(Integer, primary_key=True, index=True)
    colony_name = Column(String(100), index=True, nullable=False)
    severity = Column(String(32), nullable=False)   # ADVISORY, WARNING, CRITICAL FLOOD
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    landmark = Column(String(200), nullable=True)
    source_report_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class FloodLog(Base):
    __tablename__ = "flood_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String(32), index=True)           # SAFE, ADVISORY, WARNING, CRITICAL FLOOD
    velocity = Column(Float)                          # Estimated surface velocity (m/s)
    confidence = Column(Float)                        # ML Flood Confidence (0.0 to 100.0 %)
    raw_pred = Column(Float)                          # Model raw sigmoid output
    source_type = Column(String(32), default="video") # webcam, video, upload
