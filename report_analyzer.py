import os
import cv2
import numpy as np
from vision import vision_engine
from config import settings

THUMBNAIL_DIR = os.path.join(settings.UPLOAD_DIR, "thumbnails")
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

def analyze_community_video(video_path: str) -> dict:
    """
    Automated Machine Learning & Optical Flow Verification for Crowdsourced Videos.
    
    Samples key frames across the resident's uploaded video, runs MobileNetV2 CNN 
    inference and Lucas-Kanade velocity estimation, generates a preview thumbnail, 
    and classifies whether it is a real flood or false alarm.
    """
    if not os.path.exists(video_path):
        return {
            "ml_confidence": 0.0,
            "ml_velocity": 0.0,
            "ml_status": "FILE_ERROR",
            "thumbnail_path": None
        }

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    if total_frames <= 0:
        cap.release()
        return {
            "ml_confidence": 0.0,
            "ml_velocity": 0.0,
            "ml_status": "INVALID_VIDEO",
            "thumbnail_path": None
        }

    # Sample 6 representative frames across the video duration
    sample_indices = np.linspace(0, total_frames - 1, min(6, total_frames), dtype=int)
    
    confidences = []
    velocities = []
    saved_thumbnail_path = None
    best_frame = None
    max_conf = -1.0

    for idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        frame_resized = cv2.resize(frame, (640, 480))
        annotated_frame, telemetry = vision_engine.process_frame(frame_resized)
        
        conf = telemetry.get("confidence", 0.0)
        vel = telemetry.get("velocity", 0.0)
        
        confidences.append(conf)
        velocities.append(vel)

        if conf > max_conf:
            max_conf = conf
            best_frame = annotated_frame

    cap.release()

    if not confidences:
        confidences = [0.0]
        velocities = [0.0]

    avg_conf = float(np.mean(confidences))
    avg_vel = float(np.mean(velocities))

    # Save representative thumbnail
    if best_frame is not None:
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        thumb_filename = f"thumb_{base_name}.jpg"
        thumb_full_path = os.path.join(THUMBNAIL_DIR, thumb_filename)
        cv2.imwrite(thumb_full_path, best_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        saved_thumbnail_path = f"/uploads/thumbnails/{thumb_filename}"

    # Multi-Factor Verification Status
    if avg_conf >= 60.0 or max_conf >= 75.0 or (avg_conf >= 40.0 and avg_vel >= 1.5):
        ml_status = "VERIFIED FLOOD"
    elif avg_conf >= 30.0 or avg_vel >= 1.0:
        ml_status = "WARNING"
    else:
        ml_status = "SAFE / NO FLOOD"

    return {
        "ml_confidence": round(avg_conf, 1),
        "ml_velocity": round(avg_vel, 2),
        "ml_status": ml_status,
        "thumbnail_path": saved_thumbnail_path
    }
