# 🌊 FloodGuard AI: Hydrodynamic Flood Detection & Community Emergency Broadcast Network

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.20%2B-FF6F00.svg)](https://www.tensorflow.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.13%2B-5C3EE8.svg)](https://opencv.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)]()

> **Final Year Major Project in Computer Science & Engineering / AI & ML**  
> An autonomous disaster monitoring and crowdsourced emergency response network combining Deep Convolutional Neural Networks (`MobileNetV2`), Lucas-Kanade Optical Flow velocity estimation, colony-scoped citizen reporting, and location-based real-time WebSocket emergency broadcasts.

---

## 📌 Key Architectural Highlights

- **🧠 Deep Learning Classifier**: MobileNetV2 CNN achieving sub-30ms spatial scene inference with calibrated confidence metrics ($P(\text{Flood}) = 1.0 - \sigma(\mathbf{w}^T \mathbf{x} + b)$).
- **🌊 Lucas-Kanade Optical Flow**: Calculates pixel displacement vectors across consecutive video frames to quantify real physical water surface velocity ($m/s$).
- **🏘️ Colony/Location-Based Citizen Network**: Colony-based resident registration and login with encrypted PBKDF2-HMAC-SHA256 authentication.
- **📹 Automated ML Verification for Citizen Videos**: Residents upload waterlogging videos + landmarks; AI automatically samples frames, calculates flood confidence and flow velocity, generates preview thumbnails, and verifies authenticity.
- **📡 Real-Time Location-Scoped WebSocket Broadcasts**: When a verified flood is reported, an emergency broadcast banner and audio siren alert are instantly pushed to all residents currently connected to that specific colony/area.
- **🧵 Thread-Safe Stream Architecture**: Decoupled `StreamManager` single-worker ingestion model eliminating OpenCV race conditions, supporting live Webcams, uploaded videos, and demo test files.
- **📊 Interactive Modern UI**: Responsive dashboard with Chart.js dual-axis telemetry, community video modal player, upvoting system, and CSV incident export.

---

## 🏗️ System Architecture

```mermaid
graph TD
    A[CCTV / Webcam / Citizen Upload] --> B[Stream Ingestion & Sampler]
    B --> C[Preprocessing: 224x224 RGB Normalization]
    B --> D[Grayscale Temporal Processing]
    
    C --> E[MobileNetV2 CNN: Flood Probability]
    D --> F[Lucas-Kanade Optical Flow: Velocity m/s]
    
    E --> G[Multi-Factor Decision Fusion Engine]
    F --> G
    
    G --> H[Render HUD & Flow Vector Overlay]
    G --> I[SQLite DBMS: Users, Colonies, Reports, Alerts]
    
    H --> J[MJPEG Video Stream: /api/video_feed]
    G --> K[CCTV Telemetry WebSocket: /ws/stream]
    G --> L[Colony Room Broadcaster: /ws/colony/{colony_name}]
    
    J --> M[Interactive Dashboard UI]
    K --> M
    L --> M
    I --> M
```

---

## 📐 Mathematical Formulations

### 1. Lucas-Kanade Optical Flow Differential Constraint
Under the brightness constancy assumption $I(x, y, t) = I(x + \delta x, y + \delta y, t + \delta t)$:
$$\nabla I \cdot \mathbf{v} + \frac{\partial I}{\partial t} = 0 \quad \iff \quad I_x u + I_y v + I_t = 0$$

For a local neighborhood window $\Omega$:
$$\begin{bmatrix} I_x(p_1) & I_y(p_1) \\ \vdots & \vdots \\ I_x(p_n) & I_y(p_n) \end{bmatrix} \begin{bmatrix} u \\ v \end{bmatrix} = - \begin{bmatrix} I_t(p_1) \\ \vdots \\ I_t(p_n) \end{bmatrix} \implies \mathbf{A}\mathbf{v} = \mathbf{b}$$

Solved via least-squares:
$$\mathbf{v} = (\mathbf{A}^T \mathbf{A})^{-1} \mathbf{A}^T \mathbf{b}$$

### 2. Surface Flow Velocity Conversion ($m/s$)
$$v_{\text{surface}} = \left( \frac{1}{N} \sum_{i=1}^N \sqrt{(x_{i, t} - x_{i, t-1})^2 + (y_{i, t} - y_{i, t-1})^2} \right) \times S \times \text{FPS}$$
Where $S = 0.05 \, \text{m/pixel}$ (spatial scale factor) and $\text{FPS}$ is real-time frame rate.

---

## 🚀 Quick Start & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/flood-guard-ai.git
cd flood-guard-ai
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Application Server
```bash
python run.py
# or
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Access the Web Dashboard
Open your browser and navigate to:
```
http://127.0.0.1:8000
```

---

## 📡 Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Responsive Cyber-Slate Dashboard UI |
| `GET` | `/api/video_feed` | High-performance MJPEG video stream with telemetry HUD |
| `WS` | `/ws/stream` | Real-time WebSocket broadcasting velocity, confidence & risk level |
| `WS` | `/ws/colony/{colony_name}` | Location-scoped WebSocket room for emergency alerts & community updates |
| `POST` | `/api/auth/register` | Register colony resident account with email, phone & PBKDF2 password |
| `POST` | `/api/auth/login` | Resident authentication and colony association |
| `GET` | `/api/colonies` | Retrieve list of all colonies and active threat levels |
| `POST` | `/api/reports/upload` | Citizen video upload with automated ML verification & broadcast |
| `GET` | `/api/reports` | Get crowdsourced community incident reports filtered by colony |
| `POST` | `/api/reports/{id}/upvote`| Community validation / upvote for active incident reports |
| `GET` | `/api/alerts` | Get emergency broadcast history for active colony |
| `POST` | `/api/change_source` | Switch live stream input between `demo`, `webcam`, and `upload` |
| `GET` | `/api/stats` | Retrieve aggregate metrics (peak velocity, critical alerts, uptime) |
| `GET` | `/api/export` | Download full incident report as a CSV file |

---

## 👥 Contributors & Academic Acknowledgments
Developed as a Major Final Year Engineering Project for automated flood hazard identification, hydrodynamic flow measurement, and community disaster response.
