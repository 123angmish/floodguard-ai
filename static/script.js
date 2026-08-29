/* =========================================================
   FLOODGUARD COMMUNITY AI - JAVASCRIPT CONTROLLER
   ========================================================= */

// State
let activeColony = localStorage.getItem("floodguard_colony") || "ALL";
let currentUser = JSON.parse(localStorage.getItem("floodguard_user") || "null");
let colonyWs = null;
let cctvWs = null;
let reconnectColonyTimer = null;
let reconnectCctvTimer = null;

// Audio Alarm State
let audioAlarmEnabled = false;
let audioCtx = null;
let sirenOscillator = null;
let sirenGain = null;
let isSirenPlaying = false;

// DOM Elements
const elColonySelect = document.getElementById("colony-select");
const elColonyStatusPill = document.getElementById("colony-status-pill");
const elUserAuthSection = document.getElementById("user-auth-section");
const elEmergencyBanner = document.getElementById("colony-emergency-banner");
const elBroadcastTitle = document.getElementById("broadcast-title");
const elBroadcastMessage = document.getElementById("broadcast-message");
const elCommunityReportsContainer = document.getElementById("community-reports-container");
const elFeedColonyLabel = document.getElementById("feed-colony-label");

// Telemetry DOM
const elStatus = document.getElementById("telemetry-status");
const elStatusSubtext = document.getElementById("status-subtext");
const elConfidence = document.getElementById("telemetry-confidence");
const elConfidenceBar = document.getElementById("confidence-bar");
const elRawPred = document.getElementById("raw-pred-text");
const elVelocity = document.getElementById("telemetry-velocity");
const elVelocityBar = document.getElementById("velocity-bar");
const elVelocityIntensity = document.getElementById("velocity-intensity");
const elNavLatency = document.getElementById("nav-latency");
const elNavSource = document.getElementById("nav-source");
const elFpsBadge = document.getElementById("fps-badge");
const elConnectionBadge = document.getElementById("connection-badge");
const elVideoAlert = document.getElementById("video-overlay-alert");
const elLogsTableBody = document.getElementById("logs-table-body");

// Stats DOM
const elStatCommunityReports = document.getElementById("stat-community-reports");
const elStatCriticalAlerts = document.getElementById("stat-critical-alerts");
const elStatPeakVel = document.getElementById("stat-peak-vel");
const elStatPeakConf = document.getElementById("stat-peak-conf");

// -------------------------------------------------------------
// 📈 CHART.JS INITIALIZATION (LIVE SENSOR DUAL-AXIS)
// -------------------------------------------------------------
const ctxChart = document.getElementById("telemetryChart").getContext("2d");
const maxDataPoints = 20;

const telemetryChart = new Chart(ctxChart, {
    type: "line",
    data: {
        labels: [],
        datasets: [
            {
                label: "Flood Conf (%)",
                data: [],
                borderColor: "#38bdf8",
                backgroundColor: "rgba(56, 189, 248, 0.12)",
                borderWidth: 2,
                fill: true,
                tension: 0.3,
                yAxisID: "yConf",
                pointRadius: 2
            },
            {
                label: "Velocity (m/s)",
                data: [],
                borderColor: "#10b981",
                backgroundColor: "rgba(16, 185, 129, 0.08)",
                borderWidth: 1.8,
                borderDash: [3, 3],
                fill: false,
                tension: 0.3,
                yAxisID: "yVel",
                pointRadius: 2
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 250 },
        interaction: { mode: "index", intersect: false },
        plugins: {
            legend: {
                labels: { color: "#94a3b8", font: { family: "Inter", size: 10, weight: 600 } }
            }
        },
        scales: {
            x: {
                grid: { color: "rgba(31, 41, 61, 0.6)" },
                ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 9 } }
            },
            yConf: {
                type: "linear",
                position: "left",
                min: 0,
                max: 100,
                grid: { color: "rgba(31, 41, 61, 0.6)" },
                ticks: { color: "#38bdf8", font: { family: "JetBrains Mono", size: 9 }, callback: (v) => v + "%" }
            },
            yVel: {
                type: "linear",
                position: "right",
                min: 0,
                max: 8,
                grid: { drawOnChartArea: false },
                ticks: { color: "#10b981", font: { family: "JetBrains Mono", size: 9 }, callback: (v) => v + "m/s" }
            }
        }
    }
});

function pushChartData(timeLabel, confidence, velocity) {
    telemetryChart.data.labels.push(timeLabel);
    telemetryChart.data.datasets[0].data.push(confidence);
    telemetryChart.data.datasets[1].data.push(velocity);

    if (telemetryChart.data.labels.length > maxDataPoints) {
        telemetryChart.data.labels.shift();
        telemetryChart.data.datasets[0].data.shift();
        telemetryChart.data.datasets[1].data.shift();
    }
    telemetryChart.update("none");
}

// -------------------------------------------------------------
// 🏘️ COLONY DIRECTORY & SELECTOR
// -------------------------------------------------------------
let allColonies = [];

async function fetchColonies() {
    try {
        const resp = await fetch("/api/colonies");
        allColonies = await resp.json();

        // Populate Main Dropdown
        elColonySelect.innerHTML = `<option value="ALL">All Colonies (City Overview)</option>` + 
            allColonies.map(c => `<option value="${c.name}">${c.name} (${c.alert_level})</option>`).join("");

        // Populate Report Dropdown
        const reportColonySelect = document.getElementById("report-colony-select");
        if (reportColonySelect) {
            reportColonySelect.innerHTML = allColonies.map(c => `<option value="${c.name}">${c.name}</option>`).join("");
        }

        // Populate Register Dropdown
        const regColonySelect = document.getElementById("reg-colony-select");
        if (regColonySelect) {
            regColonySelect.innerHTML = allColonies.map(c => `<option value="${c.name}">${c.name}</option>`).join("");
        }

        // Restore active colony
        if (activeColony && Array.from(elColonySelect.options).some(o => o.value === activeColony)) {
            elColonySelect.value = activeColony;
        }

        updateColonyBadge();
    } catch (e) {
        console.error("Error fetching colonies:", e);
    }
}

function updateColonyBadge() {
    if (activeColony === "ALL") {
        elColonyStatusPill.innerText = "CITY WIDE";
        elColonyStatusPill.className = "badge badge-info";
        elFeedColonyLabel.innerText = "Showing: All Colonies";
    } else {
        const found = allColonies.find(c => c.name === activeColony);
        const level = found ? found.alert_level : "SAFE";
        elColonyStatusPill.innerText = level;
        if (level === "CRITICAL FLOOD") elColonyStatusPill.className = "badge badge-flood";
        else if (level === "WARNING") elColonyStatusPill.className = "badge badge-warning";
        else elColonyStatusPill.className = "badge badge-safe";

        elFeedColonyLabel.innerText = `Showing: ${activeColony}`;
    }
}

elColonySelect.addEventListener("change", (e) => {
    activeColony = e.target.value;
    localStorage.setItem("floodguard_colony", activeColony);
    updateColonyBadge();
    fetchCommunityReports();
    connectColonyWebSocket();
});

// -------------------------------------------------------------
// 📡 LOCATION-SCOPED COLONY WEBSOCKET (REAL-TIME BROADCASTS)
// -------------------------------------------------------------
function connectColonyWebSocket() {
    if (colonyWs) {
        try { colonyWs.close(); } catch (e) {}
    }

    const roomName = activeColony === "ALL" ? "General" : activeColony;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/colony/${encodeURIComponent(roomName)}`;

    console.log(`[COLONY WS] Connecting to room: ${roomName}`);
    colonyWs = new WebSocket(wsUrl);

    colonyWs.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleColonyBroadcast(msg);
        } catch (e) {
            console.error("[COLONY WS] Message parse error:", e);
        }
    };

    colonyWs.onclose = () => {
        clearTimeout(reconnectColonyTimer);
        reconnectColonyTimer = setTimeout(connectColonyWebSocket, 3000);
    };
}

function handleColonyBroadcast(msg) {
    console.log("[COLONY WS] Broadcast received:", msg);
    const data = msg.data || {};

    // 1. Show Top Alert Banner
    elEmergencyBanner.classList.remove("hidden");
    elBroadcastTitle.innerText = `🚨 EMERGENCY ALERT: ${msg.colony || "Your Colony"}`;
    elBroadcastMessage.innerText = `Confirmed Flood at ${data.landmark || "Local Area"} (${data.ml_confidence}% Flood Confidence, Flow: ${data.ml_velocity} m/s). Avoid the area!`;

    // 2. Trigger Siren Sound if enabled
    if (audioAlarmEnabled) {
        triggerSiren(true);
        setTimeout(() => triggerSiren(false), 5000);
    }

    // 3. Refresh Community Feed
    fetchCommunityReports();
    fetchStats();
    fetchColonies();
}

document.getElementById("btn-dismiss-broadcast").addEventListener("click", () => {
    elEmergencyBanner.classList.add("hidden");
});

// -------------------------------------------------------------
// 🏘️ COMMUNITY FLOOD FEED, UPVOTES & VIDEO DETAIL MODAL
// -------------------------------------------------------------
let currentReportsList = [];
const videoViewModal = document.getElementById("video-view-modal");
const modalVideoPlayer = document.getElementById("modal-video-player");
const modalVideoSource = document.getElementById("modal-video-source");

async function fetchCommunityReports() {
    try {
        let url = "/api/reports?limit=25";
        if (activeColony && activeColony !== "ALL") {
            url += `&colony=${encodeURIComponent(activeColony)}`;
        }

        const resp = await fetch(url);
        currentReportsList = await resp.json();

        if (!currentReportsList || currentReportsList.length === 0) {
            elCommunityReportsContainer.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-camera fa-2x"></i>
                    <p>No flood reports submitted for <strong>${activeColony === "ALL" ? "any colony" : activeColony}</strong> yet.<br>Click <strong>"Report Flood in Colony"</strong> to upload a video.</p>
                </div>
            `;
            return;
        }

        elCommunityReportsContainer.innerHTML = currentReportsList.map(r => {
            let badgeClass = "badge-verified-safe";
            let badgeText = "✓ VERIFIED SAFE";
            if (r.ml_status === "VERIFIED FLOOD") {
                badgeClass = "badge-verified-flood";
                badgeText = "🚨 VERIFIED FLOOD";
            } else if (r.ml_status === "WARNING") {
                badgeClass = "badge-verified-warn";
                badgeText = "⚠️ WARNING";
            }

            const thumb = r.thumbnail_path || "/static/placeholder_flood.jpg";

            return `
                <div class="report-card">
                    <div class="report-thumb-wrapper" onclick="openVideoModal(${r.id})">
                        <img src="${thumb}" alt="Report Video Preview" class="report-thumb" onerror="this.src='/static/placeholder_flood.jpg'">
                        <div class="report-play-btn-overlay" title="Click to watch full video">
                            <i class="fa-solid fa-play"></i>
                        </div>
                        <span class="report-badge ${badgeClass}">${badgeText}</span>
                    </div>
                    <div class="report-body">
                        <div class="report-landmark" onclick="openVideoModal(${r.id})" style="cursor: pointer;" title="Click to watch full video">
                            <i class="fa-solid fa-location-dot"></i> ${r.landmark}
                        </div>
                        <div class="report-meta">
                            <span>📍 ${r.colony_name}</span> • <span>👤 ${r.user_name}</span>
                        </div>
                        <div class="report-metrics">
                            <span>Conf: <strong class="conf">${r.ml_confidence.toFixed(1)}%</strong></span>
                            <span>Flow: <strong class="vel">${r.ml_velocity.toFixed(2)} m/s</strong></span>
                        </div>
                        ${r.description ? `<p class="report-desc">${r.description}</p>` : ""}
                        <div class="report-footer">
                            <button class="btn-watch-video" onclick="openVideoModal(${r.id})">
                                <i class="fa-solid fa-play"></i> Watch Video
                            </button>
                            <button class="btn-upvote" onclick="upvoteReport(${r.id}, this)">
                                <i class="fa-solid fa-thumbs-up"></i> <span>${r.upvotes}</span>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join("");
    } catch (e) {
        console.error("Error fetching community reports:", e);
    }
}

let activeModalReport = null;

function openVideoModal(reportId) {
    const report = currentReportsList.find(r => r.id === reportId);
    if (!report) return;

    activeModalReport = report;

    document.getElementById("modal-video-landmark").innerText = `📍 ${report.landmark} - Video`;
    document.getElementById("modal-video-colony").innerText = report.colony_name;
    document.getElementById("modal-video-user").innerText = report.user_name;
    document.getElementById("modal-video-time").innerText = report.created_at;
    document.getElementById("modal-video-desc").innerText = report.description || "No additional notes provided.";

    document.getElementById("modal-video-conf").innerText = `${report.ml_confidence.toFixed(1)}%`;
    document.getElementById("modal-video-vel").innerText = `${report.ml_velocity.toFixed(2)} m/s`;

    const badgeEl = document.getElementById("modal-video-badge");
    if (report.ml_status === "VERIFIED FLOOD") {
        badgeEl.innerText = "🚨 VERIFIED FLOOD";
        badgeEl.className = "badge badge-flood";
    } else if (report.ml_status === "WARNING") {
        badgeEl.innerText = "⚠️ WARNING";
        badgeEl.className = "badge badge-warning";
    } else {
        badgeEl.innerText = "✓ VERIFIED SAFE";
        badgeEl.className = "badge badge-safe";
    }

    if (modalVideoPlayer && report.video_path) {
        modalVideoPlayer.src = report.video_path;
        modalVideoPlayer.load();
        modalVideoPlayer.play().catch(() => {});
    }

    openModal("video-view-modal");
}

document.querySelectorAll("[data-close='video-view-modal']").forEach(btn => {
    btn.addEventListener("click", () => {
        if (modalVideoPlayer) modalVideoPlayer.pause();
    });
});

const btnLoadToStream = document.getElementById("btn-load-to-stream");
if (btnLoadToStream) {
    btnLoadToStream.addEventListener("click", async () => {
        if (!activeModalReport || !activeModalReport.video_path) return;
        const filename = activeModalReport.video_path.replace("/uploads/", "");
        try {
            await fetch("/api/change_source", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ source_type: "upload", file_path: `uploads/${filename}` })
            });
            if (modalVideoPlayer) modalVideoPlayer.pause();
            closeModal("video-view-modal");
            refreshStreamFeed();
            alert("Video successfully loaded into main Live Stream Analyzer!");
            window.scrollTo({ top: 0, behavior: "smooth" });
        } catch (e) {
            alert("Failed to load video into stream analyzer.");
        }
    });
}

async function upvoteReport(id, btnElement) {
    try {
        const resp = await fetch(`/api/reports/${id}/upvote`, { method: "POST" });
        const data = await resp.json();
        btnElement.querySelector("span").innerText = data.upvotes;
    } catch (e) {
        console.error("Error upvoting:", e);
    }
}

// -------------------------------------------------------------
// 🚨 CROWDSOURCED CITIZEN VIDEO REPORT MODAL & SUBMISSION
// -------------------------------------------------------------
const reportModal = document.getElementById("report-modal");
const formUploadReport = document.getElementById("form-upload-report");
const reportVideoFile = document.getElementById("report-video-file");
const uploadFileLabel = document.getElementById("upload-file-label");
const mlVerifyProgress = document.getElementById("ml-verify-progress");
const btnSubmitReport = document.getElementById("btn-submit-report");

document.getElementById("btn-open-report").addEventListener("click", () => {
    // If logged in, pre-fill user name and colony
    if (currentUser) {
        document.getElementById("report-user-name").value = currentUser.name;
        if (currentUser.colony_name) {
            document.getElementById("report-colony-select").value = currentUser.colony_name;
        }
    }
    openModal("report-modal");
});

reportVideoFile.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
        uploadFileLabel.innerHTML = `<strong>Selected:</strong> ${file.name} (${(file.size / (1024*1024)).toFixed(1)} MB)`;
    }
});

formUploadReport.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (!reportVideoFile.files.length) {
        alert("Please select a video file first.");
        return;
    }

    const formData = new FormData(formUploadReport);

    // Show AI progress indicator
    mlVerifyProgress.classList.remove("hidden");
    btnSubmitReport.disabled = true;
    btnSubmitReport.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing Neural Network...`;

    try {
        const resp = await fetch("/api/reports/upload", {
            method: "POST",
            body: formData
        });
        const result = await resp.json();

        mlVerifyProgress.classList.add("hidden");
        btnSubmitReport.disabled = false;
        btnSubmitReport.innerHTML = `<i class="fa-solid fa-bolt"></i> Verify with AI & Broadcast Alert`;
        closeModal("report-modal");
        formUploadReport.reset();
        uploadFileLabel.innerText = "Click or drag & drop video file (.mp4, .mov, .avi)";

        if (result.status === "success") {
            const rep = result.report;
            alert(`✅ Report Successfully Verified & Logged!\n\nAI Flood Confidence: ${rep.ml_confidence}%\nFlow Velocity: ${rep.ml_velocity} m/s\nStatus: ${rep.ml_status}\n\nBroadcast alert sent to all residents in ${rep.colony_name}.`);
            fetchCommunityReports();
            fetchColonies();
            fetchStats();
        } else {
            alert("Report upload failed.");
        }
    } catch (err) {
        console.error("Upload error:", err);
        alert("Error analyzing and uploading report.");
        mlVerifyProgress.classList.add("hidden");
        btnSubmitReport.disabled = false;
        btnSubmitReport.innerHTML = `<i class="fa-solid fa-bolt"></i> Verify with AI & Broadcast Alert`;
    }
});

// -------------------------------------------------------------
// 👤 RESIDENT LOGIN & REGISTRATION
// -------------------------------------------------------------
const loginModal = document.getElementById("login-modal");
const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");
const formLogin = document.getElementById("form-login");
const formRegister = document.getElementById("form-register");
const authModalTitle = document.getElementById("auth-modal-title");
const authAlertBox = document.getElementById("auth-alert-box");

// Live Registration Inputs & Hints
const regNameInput = document.getElementById("reg-name");
const regEmailInput = document.getElementById("reg-email");
const regEmailHint = document.getElementById("reg-email-hint");
const regPhoneInput = document.getElementById("reg-phone");
const regPhoneHint = document.getElementById("reg-phone-hint");
const regPasswordInput = document.getElementById("reg-password");
const regConfirmPasswordInput = document.getElementById("reg-confirm-password");
const regPwMatchHint = document.getElementById("reg-pw-match-hint");

function showAuthAlert(type, message) {
    if (!authAlertBox) return;
    authAlertBox.className = `auth-alert-box ${type}`;
    authAlertBox.innerText = message;
    authAlertBox.classList.remove("hidden");
}

function clearAuthAlert() {
    if (!authAlertBox) return;
    authAlertBox.className = "auth-alert-box hidden";
    authAlertBox.innerText = "";
}

// Live Validation: Email
if (regEmailInput) {
    regEmailInput.addEventListener("input", () => {
        const val = regEmailInput.value.trim();
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!val) {
            regEmailHint.className = "input-validation-hint";
        } else if (!emailRegex.test(val)) {
            regEmailHint.className = "input-validation-hint error";
            regEmailHint.innerText = "❌ Please enter a valid email address (e.g. name@gmail.com)";
        } else {
            regEmailHint.className = "input-validation-hint success";
            regEmailHint.innerText = "✓ Valid email format";
        }
    });
}

// Live Validation: Phone (10 Digits)
if (regPhoneInput) {
    regPhoneInput.addEventListener("input", () => {
        const val = regPhoneInput.value.replace(/\D/g, "");
        regPhoneInput.value = val; // Force numbers only
        if (!val) {
            regPhoneHint.className = "input-validation-hint";
        } else if (val.length !== 10 || !/^[6-9]/.test(val)) {
            regPhoneHint.className = "input-validation-hint error";
            regPhoneHint.innerText = "❌ Enter a valid 10-digit Indian mobile number (starts with 6-9)";
        } else {
            regPhoneHint.className = "input-validation-hint success";
            regPhoneHint.innerText = "✓ Valid 10-digit mobile number";
        }
    });
}

// Live Validation: Password Match
function checkPasswordMatch() {
    const pw = regPasswordInput.value;
    const cpw = regConfirmPasswordInput.value;

    if (!cpw) {
        regPwMatchHint.className = "input-validation-hint";
        return;
    }

    if (pw !== cpw) {
        regPwMatchHint.className = "input-validation-hint error";
        regPwMatchHint.innerText = "❌ Passwords do not match!";
    } else if (pw.length < 6) {
        regPwMatchHint.className = "input-validation-hint error";
        regPwMatchHint.innerText = "❌ Password must be at least 6 characters";
    } else {
        regPwMatchHint.className = "input-validation-hint success";
        regPwMatchHint.innerText = "✓ Passwords match successfully";
    }
}

if (regPasswordInput && regConfirmPasswordInput) {
    regPasswordInput.addEventListener("input", checkPasswordMatch);
    regConfirmPasswordInput.addEventListener("input", checkPasswordMatch);
}

function renderAuthUI() {
    if (currentUser) {
        elUserAuthSection.innerHTML = `
            <div class="metric-pill">
                <i class="fa-solid fa-user-check text-accent"></i>
                <span class="val">${currentUser.name}</span>
                <button id="btn-logout" class="btn btn-sm btn-secondary" title="Logout" style="padding: 2px 6px; margin-left: 4px;">
                    <i class="fa-solid fa-right-from-bracket"></i>
                </button>
            </div>
        `;
        document.getElementById("btn-logout").addEventListener("click", () => {
            currentUser = null;
            localStorage.removeItem("floodguard_user");
            renderAuthUI();
        });
    } else {
        elUserAuthSection.innerHTML = `
            <button id="btn-open-login" class="btn btn-secondary">
                <i class="fa-solid fa-user-circle"></i> Resident Login
            </button>
        `;
        document.getElementById("btn-open-login").addEventListener("click", () => {
            clearAuthAlert();
            openModal("login-modal");
        });
    }
}

tabLogin.addEventListener("click", () => {
    clearAuthAlert();
    tabLogin.classList.add("active");
    tabRegister.classList.remove("active");
    formLogin.classList.remove("hidden");
    formRegister.classList.add("hidden");
    authModalTitle.innerText = "Colony Resident Login";
});

tabRegister.addEventListener("click", () => {
    clearAuthAlert();
    tabRegister.classList.add("active");
    tabLogin.classList.remove("active");
    formRegister.classList.remove("hidden");
    formLogin.classList.add("hidden");
    authModalTitle.innerText = "Register as Colony Resident";
});

formLogin.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAuthAlert();

    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    const btnSubmit = document.getElementById("btn-submit-login");

    btnSubmit.disabled = true;
    btnSubmit.innerText = "Verifying...";

    try {
        const resp = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });
        const data = await resp.json();
        btnSubmit.disabled = false;
        btnSubmit.innerText = "Login to Account";

        if (resp.ok && data.status === "success") {
            currentUser = data.user;
            localStorage.setItem("floodguard_user", JSON.stringify(currentUser));
            if (currentUser.colony_name) {
                activeColony = currentUser.colony_name;
                localStorage.setItem("floodguard_colony", activeColony);
                elColonySelect.value = activeColony;
                updateColonyBadge();
                connectColonyWebSocket();
                fetchCommunityReports();
            }
            showAuthAlert("success", `✓ Login successful! Welcome back, ${currentUser.name}.`);
            setTimeout(() => {
                closeModal("login-modal");
                renderAuthUI();
            }, 800);
        } else {
            showAuthAlert("error", data.detail || "Invalid email or password. Please check your credentials.");
        }
    } catch (err) {
        btnSubmit.disabled = false;
        btnSubmit.innerText = "Login to Account";
        showAuthAlert("error", "Network error. Please try again.");
    }
});

formRegister.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAuthAlert();

    const name = regNameInput.value.trim();
    const email = regEmailInput.value.trim();
    const phone = regPhoneInput ? regPhoneInput.value.trim() : "";
    const customColony = document.getElementById("reg-custom-colony").value.trim();
    const colony_name = customColony ? customColony : document.getElementById("reg-colony-select").value;
    const password = regPasswordInput.value;
    const confirm_password = regConfirmPasswordInput.value;
    const btnSubmit = document.getElementById("btn-submit-register");

    // Client-side Validation Checks
    if (name.length < 2) {
        showAuthAlert("error", "Please enter your full name (at least 2 characters).");
        return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        showAuthAlert("error", "Please provide a valid email address (e.g. name@gmail.com).");
        return;
    }

    if (phone && (phone.length !== 10 || !/^[6-9]/.test(phone))) {
        showAuthAlert("error", "Please enter a valid 10-digit Indian mobile number.");
        return;
    }

    if (password.length < 6) {
        showAuthAlert("error", "Password must be at least 6 characters long.");
        return;
    }

    if (password !== confirm_password) {
        showAuthAlert("error", "Passwords do not match. Please re-enter identical passwords.");
        return;
    }

    btnSubmit.disabled = true;
    btnSubmit.innerText = "Registering Account...";

    try {
        const resp = await fetch("/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, phone, colony_name, password, confirm_password })
        });
        const data = await resp.json();
        btnSubmit.disabled = false;
        btnSubmit.innerText = "Create Resident Account";

        if (resp.ok) {
            currentUser = data;
            localStorage.setItem("floodguard_user", JSON.stringify(currentUser));
            activeColony = currentUser.colony_name;
            localStorage.setItem("floodguard_colony", activeColony);
            await fetchColonies();
            elColonySelect.value = activeColony;
            updateColonyBadge();
            connectColonyWebSocket();
            fetchCommunityReports();
            showAuthAlert("success", `✓ Account successfully created for ${currentUser.name} in ${currentUser.colony_name}!`);
            setTimeout(() => {
                closeModal("login-modal");
                renderAuthUI();
                formRegister.reset();
            }, 1000);
        } else {
            showAuthAlert("error", data.detail || (data.message ? data.message : "Registration failed."));
        }
    } catch (err) {
        btnSubmit.disabled = false;
        btnSubmit.innerText = "Create Resident Account";
        showAuthAlert("error", "Failed to communicate with server. Please try again.");
    }
});

// -------------------------------------------------------------
// 🎥 CCTV SENSOR TELEMETRY & WEBSOCKET
// -------------------------------------------------------------
function connectCctvWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/stream`;

    cctvWs = new WebSocket(wsUrl);

    cctvWs.onopen = () => {
        elConnectionBadge.innerText = "CONNECTED";
        elConnectionBadge.className = "badge badge-online";
    };

    cctvWs.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleCctvTelemetry(data);
        } catch (e) {}
    };

    cctvWs.onclose = () => {
        elConnectionBadge.innerText = "RECONNECTING";
        elConnectionBadge.className = "badge badge-fps";
        clearTimeout(reconnectCctvTimer);
        reconnectCctvTimer = setTimeout(connectCctvWebSocket, 2000);
    };
}

function handleCctvTelemetry(data) {
    const status = data.status || "SAFE";
    const confidence = parseFloat(data.confidence) || 0.0;
    const velocity = parseFloat(data.velocity) || 0.0;
    const fps = data.fps || 0.0;
    const latency = data.latency_ms || 0.0;
    const timestamp = data.timestamp || new Date().toLocaleTimeString();

    elStatus.innerText = status;
    elStatus.className = "";
    if (status === "CRITICAL FLOOD") {
        elStatus.classList.add("status-flood");
        elStatusSubtext.innerText = "Torrential flood detected on primary camera!";
        elVideoAlert.style.display = "flex";
    } else if (status === "WARNING") {
        elStatus.classList.add("status-warning");
        elStatusSubtext.innerText = "Elevated water presence or surging flow.";
        elVideoAlert.style.display = "none";
    } else if (status === "ADVISORY") {
        elStatus.classList.add("status-advisory");
        elStatusSubtext.innerText = "Water movement within standard limits.";
        elVideoAlert.style.display = "none";
    } else {
        elStatus.classList.add("status-safe");
        elStatusSubtext.innerText = "Normal conditions. No hazardous flood detected.";
        elVideoAlert.style.display = "none";
    }

    elConfidence.innerText = confidence.toFixed(1);
    elConfidenceBar.style.width = `${Math.min(confidence, 100)}%`;
    if (data.raw_pred !== undefined) elRawPred.innerText = `Raw Sigmoid: ${data.raw_pred.toFixed(4)}`;

    elVelocity.innerText = velocity.toFixed(2);
    const velPercent = Math.min((velocity / 8.0) * 100, 100);
    elVelocityBar.style.width = `${velPercent}%`;
    elVelocityIntensity.innerText = velocity > 3.0 ? "Motion: Torrential Surge" : velocity > 1.5 ? "Motion: Elevated Flow" : "Motion: Normal";

    elNavLatency.innerText = `${latency.toFixed(0)} ms`;
    elFpsBadge.innerText = `FPS: ${fps.toFixed(1)}`;
    if (data.source_type) elNavSource.innerText = data.source_type.toUpperCase();

    pushChartData(timestamp, confidence, velocity);
}

// -------------------------------------------------------------
// 🔊 WEB AUDIO SYNTHESIZER EMERGENCY SIREN
// -------------------------------------------------------------
function triggerSiren(play) {
    if (!audioAlarmEnabled) {
        stopSiren();
        return;
    }

    if (play && !isSirenPlaying) {
        try {
            if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            if (audioCtx.state === "suspended") audioCtx.resume();

            sirenOscillator = audioCtx.createOscillator();
            sirenGain = audioCtx.createGain();

            sirenOscillator.type = "sawtooth";
            sirenGain.gain.setValueAtTime(0.15, audioCtx.currentTime);
            sirenOscillator.frequency.setValueAtTime(700, audioCtx.currentTime);

            const lfo = audioCtx.createOscillator();
            const lfoGain = audioCtx.createGain();
            lfo.frequency.value = 2;
            lfoGain.gain.value = 300;
            lfo.connect(sirenOscillator.frequency);
            lfo.start();

            sirenOscillator.connect(sirenGain);
            sirenGain.connect(audioCtx.destination);
            sirenOscillator.start();

            isSirenPlaying = true;
        } catch (e) {}
    } else if (!play && isSirenPlaying) {
        stopSiren();
    }
}

function stopSiren() {
    if (sirenOscillator) {
        try {
            sirenOscillator.stop();
            sirenOscillator.disconnect();
        } catch (e) {}
        sirenOscillator = null;
    }
    isSirenPlaying = false;
}

document.getElementById("btn-audio-alarm").addEventListener("click", function() {
    audioAlarmEnabled = !audioAlarmEnabled;
    this.classList.toggle("danger-active", audioAlarmEnabled);
    this.innerHTML = audioAlarmEnabled 
        ? '<i class="fa-solid fa-volume-high"></i>' 
        : '<i class="fa-solid fa-volume-xmark"></i>';
    if (!audioAlarmEnabled) stopSiren();
});

// -------------------------------------------------------------
// 📹 CCTV STREAM CONTROLS & TOGGLES
// -------------------------------------------------------------
const sourceTabs = document.querySelectorAll(".btn-tab");
const videoFileInput = document.getElementById("video-file-input");
const btnTriggerUpload = document.getElementById("btn-trigger-upload");

sourceTabs.forEach((tab) => {
    tab.addEventListener("click", async () => {
        const source = tab.getAttribute("data-source");

        if (source === "upload") {
            if (videoFileInput) videoFileInput.click();
            return;
        }

        sourceTabs.forEach(t => t.classList.remove("active"));
        tab.classList.add("active");

        try {
            await fetch("/api/change_source", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ source_type: source, camera_index: 0 })
            });
            refreshStreamFeed();
        } catch (err) {}
    });
});

if (videoFileInput) {
    videoFileInput.addEventListener("change", async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append("file", file);

        if (btnTriggerUpload) {
            btnTriggerUpload.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Uploading...';
        }

        try {
            const resp = await fetch("/api/upload_video", {
                method: "POST",
                body: formData
            });
            const res = await resp.json();
            sourceTabs.forEach(t => t.classList.remove("active"));
            if (btnTriggerUpload) {
                btnTriggerUpload.classList.add("active");
                btnTriggerUpload.innerHTML = `<i class="fa-solid fa-file-video"></i> ${file.name.substring(0, 10)}...`;
            }
            refreshStreamFeed();
        } catch (err) {
            alert("Video upload to stream failed.");
            if (btnTriggerUpload) {
                btnTriggerUpload.innerHTML = '<i class="fa-solid fa-upload"></i> Upload Video';
            }
        }
    });
}

function refreshStreamFeed() {
    const img = document.getElementById("stream-img");
    img.src = "/api/video_feed?t=" + new Date().getTime();
}

function handleStreamError() {
    setTimeout(refreshStreamFeed, 1000);
}

document.getElementById("btn-toggle-vectors").addEventListener("click", async function() {
    const resp = await fetch("/api/toggle_vectors", { method: "POST" });
    const data = await resp.json();
    this.classList.toggle("active", data.show_vectors);
});

document.getElementById("btn-toggle-hud").addEventListener("click", async function() {
    const resp = await fetch("/api/toggle_hud", { method: "POST" });
    const data = await resp.json();
    this.classList.toggle("active", data.show_hud);
});

document.getElementById("btn-snapshot").addEventListener("click", () => {
    const img = document.getElementById("stream-img");
    const canvas = document.createElement("canvas");
    canvas.width = img.naturalWidth || 640;
    canvas.height = img.naturalHeight || 480;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0);

    const a = document.createElement("a");
    a.download = `floodguard_snapshot_${new Date().toISOString().replace(/[:.]/g, "-")}.jpg`;
    a.href = canvas.toDataURL("image/jpeg", 0.95);
    a.click();
});

// -------------------------------------------------------------
// 📊 STATS & CCTV LOGS
// -------------------------------------------------------------
async function fetchStats() {
    try {
        const statsResp = await fetch("/api/stats");
        const stats = await statsResp.json();
        elStatCommunityReports.innerText = stats.total_community_reports || 0;
        elStatCriticalAlerts.innerText = stats.critical_alerts || 0;
        elStatPeakVel.innerText = `${(stats.peak_velocity || 0).toFixed(1)} m/s`;
        elStatPeakConf.innerText = `${(stats.peak_confidence || 0).toFixed(1)}%`;

        const logsResp = await fetch("/api/logs?limit=10");
        const logs = await logsResp.json();

        if (logs.length === 0) {
            elLogsTableBody.innerHTML = `<tr><td colspan="4" class="empty-state">No alerts recorded yet.</td></tr>`;
            return;
        }

        elLogsTableBody.innerHTML = logs.map(l => `
            <tr>
                <td>${l.timestamp.split(" ")[1] || l.timestamp}</td>
                <td><span class="badge ${l.status === 'CRITICAL FLOOD' ? 'badge-flood' : l.status === 'WARNING' ? 'badge-warning' : 'badge-safe'}">${l.status}</span></td>
                <td>${l.confidence.toFixed(1)}%</td>
                <td>${l.velocity.toFixed(2)} m/s</td>
            </tr>
        `).join("");
    } catch (e) {}
}

// -------------------------------------------------------------
// ⚙️ MODAL CONTROLLER
// -------------------------------------------------------------
function openModal(id) {
    document.getElementById(id).classList.remove("hidden");
}

function closeModal(id) {
    document.getElementById(id).classList.add("hidden");
}

document.querySelectorAll("[data-close]").forEach(btn => {
    btn.addEventListener("click", () => {
        closeModal(btn.getAttribute("data-close"));
    });
});

// -------------------------------------------------------------
// 🚀 BOOTSTRAP ON LOAD
// -------------------------------------------------------------
window.addEventListener("DOMContentLoaded", async () => {
    renderAuthUI();
    await fetchColonies();
    connectColonyWebSocket();
    connectCctvWebSocket();
    fetchCommunityReports();
    fetchStats();
    setInterval(fetchStats, 10000);
});