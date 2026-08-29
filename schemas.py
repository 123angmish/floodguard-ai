import re
from pydantic import BaseModel, field_validator, ConfigDict
from datetime import datetime
from typing import Optional, List

EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
PHONE_REGEX = r"^(\+91[\-\s]?)?[6-9]\d{9}$"

# ----------------- USER & AUTH SCHEMAS -----------------
class UserRegister(BaseModel):
    name: str
    email: str
    password: str
    confirm_password: Optional[str] = None
    phone: Optional[str] = None
    colony_name: str
    city: Optional[str] = "General Area"

    @field_validator("email")
    def validate_email(cls, v):
        v = v.strip().lower()
        if not re.match(EMAIL_REGEX, v):
            raise ValueError("Invalid email format. Please provide a valid email (e.g. name@gmail.com).")
        return v

    @field_validator("phone")
    def validate_phone(cls, v):
        if v:
            v_clean = re.sub(r"[\s\-\(\)]", "", v)
            if v_clean.startswith("+91"):
                v_clean = v_clean[3:]
            elif v_clean.startswith("0"):
                v_clean = v_clean[1:]
            if not re.match(r"^[6-9]\d{9}$", v_clean):
                raise ValueError("Invalid mobile number. Please enter a valid 10-digit phone number.")
            return v_clean
        return None

    @field_validator("password")
    def validate_pw(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters long.")
        return v

    @field_validator("name")
    def validate_name(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full Name must be at least 2 characters.")
        return v

class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator("email")
    def validate_email(cls, v):
        return v.strip().lower()

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: Optional[str] = None
    colony_name: str
    city: Optional[str] = None
    role: str

# ----------------- COLONY SCHEMAS -----------------
class ColonyCreate(BaseModel):
    name: str
    city: Optional[str] = "General"
    pincode: Optional[str] = "000000"

class ColonyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    city: str
    pincode: str
    alert_level: str
    total_reports: int

# ----------------- COMMUNITY REPORT SCHEMAS -----------------
class CommunityReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_name: str
    colony_name: str
    landmark: str
    video_path: str
    thumbnail_path: Optional[str] = None
    description: Optional[str] = None
    ml_confidence: float
    ml_velocity: float
    ml_status: str
    upvotes: int
    status: str
    created_at: datetime

# ----------------- COLONY ALERT SCHEMAS -----------------
class ColonyAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    colony_name: str
    severity: str
    title: str
    message: str
    landmark: Optional[str] = None
    created_at: datetime

# ----------------- LEGACY / CCTV LOG SCHEMAS -----------------
class LogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    status: str
    velocity: float
    confidence: float
    source_type: Optional[str] = "video"

class StatsSummary(BaseModel):
    total_logs: int
    critical_alerts: int
    warnings: int
    advisories: int
    peak_velocity: float
    peak_confidence: float
    current_status: str
    active_source: str

class SourceChangeRequest(BaseModel):
    source_type: str
    camera_index: Optional[int] = 0
    file_path: Optional[str] = None

class ThresholdSettings(BaseModel):
    confidence_warning: Optional[float] = None
    confidence_flood: Optional[float] = None
    velocity_warning: Optional[float] = None
    velocity_flood: Optional[float] = None
