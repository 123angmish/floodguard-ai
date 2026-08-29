import os
import time
import threading
import cv2
import numpy as np
from datetime import datetime
from config import settings
from vision import vision_engine
from database import SessionLocal
from models import FloodLog

class StreamManager:
    """
    Unified Thread-Safe Video Stream & Ingestion Manager.
    
    Eliminates OpenCV concurrency race conditions by running a single dedicated 
    ingestion and inference worker thread that services both the MJPEG video feed 
    and the real-time WebSocket telemetry channel.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        
        # Stream Source State
        self.source_type = "demo"  # "demo", "webcam", "upload"
        self.source_path = settings.DEFAULT_VIDEO_PATH
        self.camera_index = settings.CAMERA_INDEX
        self.cap = None
        
        # Latest frame buffer and telemetry
        self.latest_jpeg = None
        self.latest_telemetry = {
            "status": "INITIALIZING",
            "confidence": 0.0,
            "velocity": 0.0,
            "fps": 0.0,
            "latency_ms": 0.0,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "source_type": self.source_type
        }
        
        # Database Logging Cooldown
        self.last_db_log_time = 0.0

    def start(self):
        """Start the background streaming worker."""
        if self.running:
            return
        self.running = True
        self._open_capture()
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
        print("[STREAM] StreamManager background worker started.")

    def stop(self):
        """Stop the streaming worker and release camera/video capture."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self._release_capture()
        print("[STREAM] StreamManager stopped.")

    def _open_capture(self):
        """Open video capture according to current source configuration."""
        self._release_capture()
        
        if self.source_type == "webcam":
            print(f"[STREAM] Probing webcam index {self.camera_index}...")
            # Try specified camera index with DirectShow on Windows
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                print(f"[STREAM] Index {self.camera_index} failed, trying index 0...")
                self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                print("[STREAM] Warning: Could not open any webcam. Falling back to demo video.")
                self.source_type = "demo"
                self.source_path = settings.DEFAULT_VIDEO_PATH
                self.cap = cv2.VideoCapture(self.source_path)
        else:
            # Video File mode (Demo or Upload)
            target_path = self.source_path if os.path.exists(self.source_path) else settings.DEFAULT_VIDEO_PATH
            print(f"[STREAM] Opening video source: {target_path}")
            self.cap = cv2.VideoCapture(target_path)

    def _release_capture(self):
        """Safely release the active VideoCapture."""
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception as e:
                print(f"[STREAM] Error releasing capture: {e}")
            self.cap = None

    def set_source(self, source_type: str, custom_path: str = None, camera_idx: int = 0) -> bool:
        """Switch video input source dynamically without restarting the server."""
        with self.lock:
            self.source_type = source_type
            if source_type == "webcam":
                self.camera_index = camera_idx
            elif source_type in ["demo", "upload"]:
                if custom_path and os.path.exists(custom_path):
                    self.source_path = custom_path
                else:
                    self.source_path = settings.DEFAULT_VIDEO_PATH
            self._open_capture()
            return True

    def _worker_loop(self):
        """Core frame ingestion, ML inference, and telemetry dispatch loop."""
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                self._open_capture()
                time.sleep(0.5)
                continue

            success, frame = self.cap.read()

            if not success or frame is None:
                # If reading video file, loop back to beginning
                if self.source_type in ["demo", "upload"]:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    time.sleep(0.03)
                    continue
                else:
                    # Webcam disconnected or frame read failure
                    time.sleep(0.1)
                    continue

            # Resize frame to standard 640x480 for uniform inference and streaming bandwidth
            frame = cv2.resize(frame, (640, 480))

            # Run through Hybrid ML + CV Analytics Pipeline
            annotated_frame, telemetry = vision_engine.process_frame(frame)
            telemetry["timestamp"] = datetime.now().strftime("%H:%M:%S")
            telemetry["source_type"] = self.source_type

            # Encode annotated frame as JPEG for MJPEG stream
            _, buffer = cv2.imencode('.jpg', annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            jpeg_bytes = buffer.tobytes()

            with self.lock:
                self.latest_jpeg = jpeg_bytes
                self.latest_telemetry = telemetry

            # Database Incident Logging with Cooldown
            now = time.time()
            if telemetry["status"] in ["WARNING", "CRITICAL FLOOD", "ADVISORY"] and (now - self.last_db_log_time > settings.LOG_ALERT_COOLDOWN_SECONDS):
                self._log_incident_to_db(telemetry)
                self.last_db_log_time = now

            # Throttle loop to achieve target ~25-30 FPS streaming
            time.sleep(0.02)

    def _log_incident_to_db(self, telemetry: dict):
        """Asynchronously record elevated risk incidents into SQLite."""
        try:
            db = SessionLocal()
            log_entry = FloodLog(
                status=telemetry.get("status", "SAFE"),
                velocity=telemetry.get("velocity", 0.0),
                confidence=telemetry.get("confidence", 0.0),
                raw_pred=telemetry.get("raw_pred", 1.0),
                source_type=self.source_type,
                timestamp=datetime.utcnow()
            )
            db.add(log_entry)
            db.commit()
            db.close()
        except Exception as e:
            print(f"[DATABASE] Error logging incident: {e}")

    def get_latest_frame(self) -> bytes:
        """Retrieve the most recently processed JPEG frame."""
        with self.lock:
            return self.latest_jpeg

    def get_latest_telemetry(self) -> dict:
        """Retrieve the most recent telemetry metrics."""
        with self.lock:
            return self.latest_telemetry.copy()

# Singleton instance
stream_manager = StreamManager()
