import time
import threading
import cv2
import numpy as np
from tensorflow.keras.models import load_model
from config import settings

class FloodVisionEngine:
    """
    Hybrid Machine Learning & Computer Vision Analytics Engine.
    
    Combines:
    1. MobileNetV2 Deep CNN for spatial Flood scene classification.
    2. Lucas-Kanade Optical Flow for temporal surface water motion vector tracking & velocity estimation.
    3. Multi-Factor Decision Fusion for robust, false-positive-resistant disaster severity assessment.
    """
    def __init__(self, model_path: str = "flood_model.h5"):
        self.lock = threading.Lock()
        
        # Load Pre-trained Deep Learning Model
        print(f"[VISION] Loading Neural Network from {model_path}...")
        self.model = load_model(model_path)
        print("[VISION] MobileNetV2 Model loaded successfully.")
        
        # Lucas-Kanade Optical Flow Parameters
        self.lk_params = dict(
            winSize=(21, 21),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01)
        )
        
        # Feature Detection (Good Features To Track)
        self.feature_params = dict(
            maxCorners=150,
            qualityLevel=0.15,
            minDistance=10,
            blockSize=7
        )
        
        # State variables for Optical Flow & Smoothing
        self.prev_gray = None
        self.p0 = None
        self.last_feature_refresh = 0.0
        self.prev_velocity = 0.0
        self.prev_confidence = 0.0
        self.last_frame_time = time.time()
        
        # Configurable visual toggles
        self.show_vectors = True
        self.show_hud = True

    def _detect_features(self, gray_frame):
        """Detect trackable interest points (corners/textures) for optical flow."""
        self.p0 = cv2.goodFeaturesToTrack(gray_frame, mask=None, **self.feature_params)
        self.prev_gray = gray_frame.copy()
        self.last_feature_refresh = time.time()

    def process_frame(self, frame: np.ndarray) -> tuple[np.ndarray, dict]:
        """
        Process a single video frame through the hybrid ML + CV pipeline.
        
        Returns:
            annotated_frame (np.ndarray): Video frame rendered with vectors & HUD.
            telemetry (dict): Metrics dictionary containing velocity, confidence, status, etc.
        """
        if frame is None or frame.size == 0:
            return frame, {
                "status": "NO_FEED",
                "confidence": 0.0,
                "velocity": 0.0,
                "raw_pred": 1.0,
                "fps": 0.0,
                "latency_ms": 0.0
            }

        start_time = time.time()
        h, w = frame.shape[:2]
        display_frame = frame.copy()
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # -------------------------------------------------------------
        # 1. DEEP LEARNING INFERENCE (MobileNetV2 CNN)
        # -------------------------------------------------------------
        # Preprocessing: Resize to 224x224, RGB color space, [0, 1] normalized
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img_rgb, (224, 224)).astype(np.float32) / 255.0
        img_batch = np.expand_dims(img_resized, axis=0)

        with self.lock:
            raw_pred_val = self.model.predict(img_batch, verbose=0)

        # Calibrated Output Mapping:
        # The binary classifier outputs 0.0 for FLOOD and 1.0 for SAFE.
        # Therefore, P(Flood) = 1.0 - raw_prediction.
        if len(raw_pred_val.shape) > 1 and raw_pred_val.shape[1] == 1:
            raw_pred = float(raw_pred_val[0][0])
        else:
            raw_pred = float(raw_pred_val[0])
            
        flood_prob = float(np.clip(1.0 - raw_pred, 0.0, 1.0))
        raw_confidence = flood_prob * 100.0

        # Exponential moving average smoothing for confidence
        confidence = float(0.70 * self.prev_confidence + 0.30 * raw_confidence)
        self.prev_confidence = confidence

        # -------------------------------------------------------------
        # 2. COMPUTER VISION: LUCAS-KANADE OPTICAL FLOW VELOCITY
        # -------------------------------------------------------------
        raw_velocity = 0.0
        now = time.time()
        time_elapsed = max(now - self.last_frame_time, 0.001)
        self.last_frame_time = now
        fps = 1.0 / time_elapsed

        # Re-detect trackable features every 1.5 seconds or if tracking points are depleted
        if self.prev_gray is None or (now - self.last_feature_refresh > 1.5) or (self.p0 is None or len(self.p0) < 15):
            self._detect_features(frame_gray)
        else:
            p1, st, err = cv2.calcOpticalFlowPyrLK(
                self.prev_gray, frame_gray, self.p0, None, **self.lk_params
            )

            if p1 is not None and st is not None:
                good_new = p1[st == 1]
                good_old = self.p0[st == 1]

                displacements = []
                for (new_pt, old_pt) in zip(good_new, good_old):
                    x1, y1 = old_pt.ravel()
                    x2, y2 = new_pt.ravel()
                    dist = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                    displacements.append(dist)

                    # Draw flow vector arrows if enabled
                    if self.show_vectors and dist > 1.5:
                        # Vector length amplification for visual clarity
                        dx = (x2 - x1) * 1.5
                        dy = (y2 - y1) * 1.5
                        end_x = int(np.clip(x1 + dx, 0, w - 1))
                        end_y = int(np.clip(y1 + dy, 0, h - 1))
                        cv2.arrowedLine(
                            display_frame,
                            (int(x1), int(y1)),
                            (end_x, end_y),
                            (0, 255, 255),  # Yellow/Cyan flow vector
                            1,
                            tipLength=0.3
                        )

                if len(displacements) > 0:
                    # Physical velocity calculation in m/s:
                    # v = mean_pixel_displacement * scale_factor * fps
                    effective_fps = min(fps, 30.0)
                    raw_velocity = float(np.mean(displacements) * settings.SCALE_FACTOR * (effective_fps / 15.0))

                self.prev_gray = frame_gray.copy()
                self.p0 = good_new.reshape(-1, 1, 2)
            else:
                self._detect_features(frame_gray)

        # Exponential smoothing for velocity
        velocity = float(0.75 * self.prev_velocity + 0.25 * raw_velocity)
        velocity = round(float(np.clip(velocity, 0.0, 25.0)), 2)
        self.prev_velocity = velocity

        # -------------------------------------------------------------
        # 3. MULTI-FACTOR DECISION FUSION & RISK LEVEL
        # -------------------------------------------------------------
        if confidence >= 65.0 or (confidence >= 45.0 and velocity >= settings.VELOCITY_THRESHOLD_WARNING) or velocity >= settings.VELOCITY_THRESHOLD_FLOOD:
            status = "CRITICAL FLOOD"
            color = (0, 0, 235)  # Crimson Red (BGR)
        elif confidence >= 35.0 or velocity >= settings.VELOCITY_THRESHOLD_WARNING:
            status = "WARNING"
            color = (0, 165, 255)  # Orange (BGR)
        elif confidence >= 20.0 or velocity >= 0.8:
            status = "ADVISORY"
            color = (0, 215, 255)  # Yellow (BGR)
        else:
            status = "SAFE"
            color = (50, 205, 50)  # Emerald Green (BGR)

        latency_ms = round((time.time() - start_time) * 1000.0, 1)

        # -------------------------------------------------------------
        # 4. RENDER TELEMETRY HUD OVERLAY
        # -------------------------------------------------------------
        if self.show_hud:
            # Top Status Pill Banner
            cv2.rectangle(display_frame, (15, 15), (280, 55), (20, 20, 25), -1)
            cv2.rectangle(display_frame, (15, 15), (280, 55), color, 2)
            cv2.putText(
                display_frame,
                f"STATUS: {status}",
                (25, 42),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                color,
                2
            )

            # Telemetry Sub-panel (bottom-left)
            cv2.rectangle(display_frame, (15, h - 85), (320, h - 15), (15, 23, 42), -1)
            cv2.rectangle(display_frame, (15, h - 85), (320, h - 15), (51, 65, 85), 1)

            cv2.putText(
                display_frame,
                f"Flood Conf: {confidence:.1f}% | Flow: {velocity:.2f} m/s",
                (25, h - 55),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (255, 255, 255),
                1
            )
            cv2.putText(
                display_frame,
                f"Latency: {latency_ms:.1f}ms | FPS: {fps:.1f} | Model: MobileNetV2",
                (25, h - 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (148, 163, 184),
                1
            )

        telemetry = {
            "status": status,
            "confidence": round(confidence, 1),
            "velocity": velocity,
            "raw_pred": round(raw_pred, 4),
            "fps": round(fps, 1),
            "latency_ms": latency_ms
        }

        return display_frame, telemetry

# Singleton Vision Engine instance
vision_engine = FloodVisionEngine()