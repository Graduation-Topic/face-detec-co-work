// ===== Module status =====
document.addEventListener("DOMContentLoaded", () => {
  if (typeof addSystemLog === "function") {
    addSystemLog("[OK] Detection Controls module loaded", "success");
  }
});

// ===== Detection toggle =====
const SESSION_STORAGE_KEY = "fatigue-detection-session-id";

function getSessionId() {
  let sessionId = sessionStorage.getItem(SESSION_STORAGE_KEY);

  if (!sessionId) {
    sessionId = crypto.randomUUID();
    sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  }

  return sessionId;
}

async function start_detection() {
  try {
    const sessionId = getSessionId();

    await startBrowserCamera();

    const detector = window.edgeDetector;
    if (!detector) {
      stopCapture();
      throw new Error("Detector is not ready");
    }

    if (!detector.started) {
      detector.start(undefined, sessionId);
    }

    await fetch("/api/state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        started: true,
        session_id: sessionId,
      }),
    });

    const button = document.getElementById("toggle-detection-button");
    const exportBtn = document.getElementById("export-log-btn");

    const baselineRadio = document.querySelector(
      'input[name="cali-option"][value="baseline"]',
    );

    const startCalibrationBtn = document.getElementById(
      "start-calibration-btn",
    );

    button.innerText = "停止";
    button.classList.add("toggle-detection-button_active");

    if (exportBtn) {
      exportBtn.disabled = true;
    }

    if (baselineRadio) {
      baselineRadio.disabled = false;
    }

    if (startCalibrationBtn) {
      startCalibrationBtn.disabled = false;
    }

    addSystemLog("[START] 偵測開始", "start");
  } catch (error) {
    console.error("[ERROR]", error);
    addSystemLog(`[ERROR] ${error.message}`, "error");
  }
}

async function stop_detection() {
  try {
    const sessionId = getSessionId();

    window.edgeDetector?.stop();

    await fetch("/api/state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        started: false,
        session_id: sessionId,
      }),
      keepalive: true,
    }).catch((error) => {
      console.warn("[STATE] Failed to stop Python state:", error);
    });

    const button = document.getElementById("toggle-detection-button");
    const exportBtn = document.getElementById("export-log-btn");

    const baselineRadio = document.querySelector(
      'input[name="cali-option"][value="baseline"]',
    );

    const startCalibrationBtn = document.getElementById(
      "start-calibration-btn",
    );

    button.innerText = "開始";
    button.classList.remove("toggle-detection-button_active");

    if (exportBtn) {
      exportBtn.disabled = false;
    }

    // Detection 關閉後
    // Baseline disabled
    if (baselineRadio) {
      baselineRadio.disabled = true;
    }

    // Detection 關閉後
    // Start Calibration disabled
    if (startCalibrationBtn) {
      startCalibrationBtn.disabled = true;
    }

    stopCapture();

    addPauseLine();
    addSystemLog("[STOP] 偵測暫停", "stop");
  } catch (error) {
    console.error("[ERROR]", error);
    addSystemLog(`[ERROR] ${error.message}`, "error");
  }
}

async function handle_detection_toggle() {
  const button = document.getElementById("toggle-detection-button");

  if (!button) {
    return;
  }

  if (
    button.classList.contains("toggle-detection-button_active") &&
    isBrowserCameraActive()
  ) {
    await stop_detection();
  } else {
    button.classList.remove("toggle-detection-button_active");
    await start_detection();
  }
}

window.addEventListener("pagehide", () => {
  window.edgeDetector?.stop();
});

document.addEventListener("DOMContentLoaded", () => {
  const button = document.getElementById("toggle-detection-button");

  if (!button) {
    return;
  }

  button.addEventListener("click", handle_detection_toggle);
});

// ===== Calibration controls =====
document.addEventListener("DOMContentLoaded", () => {
  const startBtn = document.getElementById("start-calibration-btn");
  const statusText = document.getElementById("baseline-status-text");
  const radios = document.querySelectorAll('input[name="cali-option"]');

  const baselineRadio = document.querySelector(
    'input[name="cali-option"][value="baseline"]',
  );

  const defaultRadio = document.querySelector(
    'input[name="cali-option"][value="default"]',
  );

  if (!startBtn || !statusText) {
    console.error(
      "[CALIBRATION] Required DOM elements not found: check site ids",
    );
    return;
  }

  if (baselineRadio) {
    baselineRadio.disabled = true;
  }

  startBtn.disabled = true;

  let pollTimer = null;

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function setCalibrationButtonLabel(isCalibrated) {
    startBtn.textContent = isCalibrated ? "重新校準" : "開始校準";
  }

  function pollStatus() {
    stopPolling();

    pollTimer = setInterval(() => {
      try {
        const detector = window.edgeDetector;
        if (!detector?.started) {
          throw new Error("Detection not started");
        }

        const { current, target } = detector.calibrationProgress;

        if (detector.isCalibrating) {
          statusText.textContent = `校準中... ${current}/${target}`;

          startBtn.textContent = "校準中...";
          startBtn.disabled = true;

          return;
        }

        if (detector.isCalibrated) {
          statusText.textContent = "已校準";

          setCalibrationButtonLabel(true);
          startBtn.disabled = false;

          if (baselineRadio) {
            baselineRadio.disabled = false;
            baselineRadio.dataset.wasCalibrated = "true";
          }

          stopPolling();

          return;
        }

        statusText.textContent = "尚未校準";
        setCalibrationButtonLabel(false);
        startBtn.disabled = false;

        stopPolling();
      } catch (error) {
        console.error("[CALIBRATION]", error);

        startBtn.disabled = false;

        stopPolling();
      }
    }, 300);
  }

  startBtn.addEventListener("click", () => {
    try {
      const detector = window.edgeDetector;
      if (!detector?.started) {
        throw new Error("Detection not started");
      }

      startBtn.disabled = true;
      startBtn.textContent = "校準中...";
      detector.startCalibration();
      statusText.textContent = `校準中... 0/${detector.calibrationProgress.target}`;

      pollStatus();
    } catch (error) {
      console.error("[CALIBRATION]", error);

      if (typeof addSystemLog === "function") {
        addSystemLog(`[ERROR] ${error.message}`, "error");
      }

      setCalibrationButtonLabel(false);
      startBtn.disabled = false;
    }
  });

  radios.forEach((radio) => {
    radio.addEventListener("change", () => {
      if (radio.value === "default") {
        try {
          window.edgeDetector?.selectCalibration("default");

          if (typeof addSystemLog === "function") {
            addSystemLog("[CALIBRATION] Default", "info");
          }
        } catch (error) {
          console.error("[CALIBRATION]", error);

          if (typeof addSystemLog === "function") {
            addSystemLog(`[ERROR] ${error.message}`, "error");
          }
        }

        return;
      }

      if (radio.value === "baseline") {
        if (!radio.dataset.wasCalibrated) {
          statusText.textContent = "尚未校準";

          if (typeof addSystemLog === "function") {
            addSystemLog("[CALIBRATION] Baseline", "info");
          }

          return;
        }

        try {
          window.edgeDetector?.selectCalibration("baseline");

          if (typeof addSystemLog === "function") {
            addSystemLog("[CALIBRATION] Switched to baseline", "info");
          }
        } catch (error) {
          console.error("[CALIBRATION]", error);

          if (typeof addSystemLog === "function") {
            addSystemLog(`[ERROR] ${error.message}`, "error");
          }
        }

        return;
      }
    });
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const resetBtns = [document.getElementById("reset-data-button")].filter(
    Boolean,
  );

  resetBtns.forEach((resetBtn) => {
    resetBtn.addEventListener("click", async () => {
      if (resetBtn.disabled) return;

      try {
        resetBtn.disabled = true;

        const detector = window.edgeDetector;
        detector?.reset();

        const current = detector ? detector.toApiData() : {};

        resetCharts();

        updateData({
          fps: 0,
          latency: null,
          faces: 0,
          ear: null,
          mar: null,
          blink_times: 0,
          yawn_times: 0,
          eye_closure_dur: null,
          yawn_dur: null,
          perclos: null,
          ear_threshold: current.ear_threshold,
          mar_threshold: current.mar_threshold,
          default_ear_threshold: current.default_ear_threshold,
          default_mar_threshold: current.default_mar_threshold,
          baseline_ear_threshold: current.baseline_ear_threshold,
          baseline_mar_threshold: current.baseline_mar_threshold,
          fatigue_level: "Normal",
          fatigue_score: null,
        });

        addSystemLog("[RESET] Data Cleared", "info");
      } catch (error) {
        console.error("[ERROR]", error);
        addSystemLog(`[ERROR] ${error.message}`, "error");
      } finally {
        resetBtn.disabled = false;
      }
    });
  });
});
