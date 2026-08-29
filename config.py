import os

try:
    from pydantic_settings import BaseSettings
    class Settings(BaseSettings):
        DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./flood_guard.db")
        CAMERA_INDEX: int = int(os.getenv("CAMERA_INDEX", "0"))
        DEFAULT_VIDEO_PATH: str = os.getenv("DEFAULT_VIDEO_PATH", "t4.mp4")
        UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
        
        # Physics Calibration
        SCALE_FACTOR: float = float(os.getenv("SCALE_FACTOR", "0.05"))
        FPS_ESTIMATE: float = 30.0
        
        # ML & Risk Thresholds
        CONFIDENCE_THRESHOLD_FLOOD: float = float(os.getenv("CONFIDENCE_THRESHOLD_FLOOD", "0.65"))
        CONFIDENCE_THRESHOLD_WARNING: float = float(os.getenv("CONFIDENCE_THRESHOLD_WARNING", "0.35"))
        VELOCITY_THRESHOLD_WARNING: float = float(os.getenv("VELOCITY_THRESHOLD_WARNING", "1.5"))
        VELOCITY_THRESHOLD_FLOOD: float = float(os.getenv("VELOCITY_THRESHOLD_FLOOD", "3.5"))
        
        # Database Logging Threshold
        LOG_ALERT_COOLDOWN_SECONDS: float = 3.0

        class Config:
            env_file = ".env"
            extra = "allow"
except ImportError:
    try:
        from pydantic import BaseSettings
        class Settings(BaseSettings):
            DATABASE_URL: str = "sqlite:///./flood_guard.db"
            CAMERA_INDEX: int = 0
            DEFAULT_VIDEO_PATH: str = "t4.mp4"
            UPLOAD_DIR: str = "uploads"
            SCALE_FACTOR: float = 0.05
            FPS_ESTIMATE: float = 30.0
            CONFIDENCE_THRESHOLD_FLOOD: float = 0.65
            CONFIDENCE_THRESHOLD_WARNING: float = 0.35
            VELOCITY_THRESHOLD_WARNING: float = 1.5
            VELOCITY_THRESHOLD_FLOOD: float = 3.5
            LOG_ALERT_COOLDOWN_SECONDS: float = 3.0
            class Config:
                env_file = ".env"
    except ImportError:
        class Settings:
            def __init__(self):
                self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./flood_guard.db")
                self.CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
                self.DEFAULT_VIDEO_PATH = os.getenv("DEFAULT_VIDEO_PATH", "t4.mp4")
                self.UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
                self.SCALE_FACTOR = float(os.getenv("SCALE_FACTOR", "0.05"))
                self.FPS_ESTIMATE = 30.0
                self.CONFIDENCE_THRESHOLD_FLOOD = float(os.getenv("CONFIDENCE_THRESHOLD_FLOOD", "0.65"))
                self.CONFIDENCE_THRESHOLD_WARNING = float(os.getenv("CONFIDENCE_THRESHOLD_WARNING", "0.35"))
                self.VELOCITY_THRESHOLD_WARNING = float(os.getenv("VELOCITY_THRESHOLD_WARNING", "1.5"))
                self.VELOCITY_THRESHOLD_FLOOD = float(os.getenv("VELOCITY_THRESHOLD_FLOOD", "3.5"))
                self.LOG_ALERT_COOLDOWN_SECONDS = 3.0

settings = Settings()

# Ensure uploads directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
