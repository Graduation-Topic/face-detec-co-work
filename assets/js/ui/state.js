// =========================================================
// info-card 卡片收合（不顯示 header 摘要）
// =========================================================

function initCollapsibleCards() {
  document.querySelectorAll(".info-card--collapse").forEach((card) => {
    const header = card.querySelector(".info-card-header");
    if (!header) return;

    header.addEventListener("click", () => {
      const open = card.classList.toggle("is-open");
      header.setAttribute("aria-expanded", open);
    });
  });
}

initCollapsibleCards();

function formatSeconds(value, digits = 1) {
  if (
    value === null ||
    value === undefined ||
    !Number.isFinite(Number(value))
  ) {
    return "--";
  }

  return Number(value).toFixed(digits) + "s";
}

// =========================================================
// Data Fetching and Updating
// =========================================================

function updateData(data) {
  document.getElementById("fps-info").textContent = data.fps ?? "--";

  document.getElementById("resolution-info").textContent =
    data.resolution ?? window.edgeStats?.resolution ?? "--";

  document.getElementById("latency-info").textContent =
    data.latency != null ? data.latency + "ms" : "--";

  document.getElementById("faces-info").textContent = data.faces ?? "--";

  // =======================================================
  // Eye
  // =======================================================

  document.getElementById("ear-info").textContent =
    data.ear != null ? Number(data.ear).toFixed(2) : "--";

  document.getElementById("blink-times-info").textContent =
    data.blink_times ?? "--";

  document.getElementById("eye-closure-dur-info").textContent = formatSeconds(
    data.eye_closure_dur,
  );

  document.getElementById("perclos-info").textContent =
    data.perclos != null ? (Number(data.perclos) * 100).toFixed(1) + "%" : "--";

  document.getElementById("baseline-ear-threshold-info").textContent =
    data.baseline_ear_threshold != null
      ? Number(data.baseline_ear_threshold).toFixed(2)
      : "--";

  // =======================================================
  // Mouth
  // =======================================================

  document.getElementById("mar-info").textContent =
    data.mar != null ? Number(data.mar).toFixed(2) : "--";

  document.getElementById("yawn-times-info").textContent =
    data.yawn_times ?? "--";

  document.getElementById("yawn-dur-info").textContent = formatSeconds(
    data.yawn_dur,
  );

  document.getElementById("baseline-mar-threshold-info").textContent =
    data.baseline_mar_threshold != null
      ? Number(data.baseline_mar_threshold).toFixed(2)
      : "--";

  // =======================================================
  // Head 
  // =======================================================

  const pitchEl = document.getElementById("pitch-info");
  if (pitchEl) {
    pitchEl.textContent =
      data.nod_ratio != null
        ? `${Number(data.nod_ratio).toFixed(2)} (v:${Number(data.nod_velocity ?? 0).toFixed(2)})`
        : "--";
  }

  const yawEl = document.getElementById("yaw-info");
  if (yawEl) {
    yawEl.textContent =
      data.turn_ratio != null ? Number(data.turn_ratio).toFixed(2) : "--";
  }

  // =======================================================
  // Brightness
  // =======================================================

  const brightEl = document.getElementById("brightness-info");
  if (brightEl) {
    const bVal = data.brightness ?? window.edgeStats?.brightness;
    const envStatus = window.edgeStats?.envStatus || "";
    brightEl.textContent =
      bVal != null ? `${bVal} ${envStatus}` : "--";
  }

  // =======================================================
  // Threshold
  // =======================================================

  document.getElementById("default-ear-threshold").textContent =
    data.default_ear_threshold != null
      ? Number(data.default_ear_threshold).toFixed(2)
      : "--";

  document.getElementById("default-mar-threshold").textContent =
    data.default_mar_threshold != null
      ? Number(data.default_mar_threshold).toFixed(2)
      : "--";

  // =======================================================
  // Fatigue Status
  // =======================================================

  updateFatigueStatus(data.fatigue_level, data.fatigue_score);

  updateFatigueAlert(data);
}

function updateFatigueStatus(level, score) {
  const statusEl = document.getElementById("fatigue-status");
  const scoreEl = document.getElementById("fatigue-score");

  const levelMap = {
    Normal: {
      text: "正常",
      cls: "fatigue-status-safe",
    },

    Mild: {
      text: "輕度疲勞",
      cls: "fatigue-status-warning",
    },

    Severe: {
      text: "重度疲勞",
      cls: "fatigue-status-danger",
    },
  };

  const info = levelMap[level] || levelMap.Normal;

  statusEl.textContent = info.text;
  statusEl.className = info.cls;

  scoreEl.textContent = score != null ? `${score}%` : "N/A";
}

function fetchData() {
  const detector = window.edgeDetector;

  if (!detector) return;

  if (!detector.started) {
    window.hideFatigueAlert?.();
    return;
  }

  try {
    const data = detector.toApiData(window.edgeStats);

    updateRealtimeCharts(data.ear, data.mar);

    fetch("/api/state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
      keepalive: true,
    }).catch((error) => {
      console.warn("[STATE] Failed to sync Python state:", error);
    });

    updateData(data);
  } catch (error) {
    console.error("[FETCH]", error);
  }
}

fetchData();

setInterval(fetchData, 1000);
