// ===== Module status =====
document.addEventListener("DOMContentLoaded", () => {
  if (typeof addSystemLog === "function") {
    addSystemLog("[OK] Detection Controls module loaded", "success");
  }
});

// ===== Session ID 管理 =====
const SESSION_STORAGE_KEY = "fatigue-detection-session-id";

function getSessionId() {
  let sessionId = sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  }
  return sessionId;
}

// 狀態管理：
// stage 0: 尚未校正 (按鈕: "開始校正")
// stage 1: 正在校正 (按鈕: "校準中 (點擊取消)")
// stage 2: 已校正完成，待命 (按鈕: "開始檢測")
// stage 3: 正式檢測中 (按鈕: "停止檢測")
let currentStage = 0;
let caliPollTimer = null;

function stopCaliPolling() {
  if (caliPollTimer) {
    clearInterval(caliPollTimer);
    caliPollTimer = null;
  }
}

/**
 * 步驟一：開始校準流程（開鏡頭、收集100幀個人基準）
 */
async function start_calibration_flow() {
  const button = document.getElementById("toggle-detection-button");
  const exportBtn = document.getElementById("export-log-btn");
  const baselineRadio = document.querySelector('input[name="cali-option"][value="baseline"]');
  const startCalibrationBtn = document.getElementById("start-calibration-btn");
  const statusText = document.getElementById("baseline-status-text");

  try {
    currentStage = 1;
    const sessionId = getSessionId();

    if (button) {
      button.innerText = "相機啟動中...";
      button.classList.add("toggle-detection-button_active");
    }

    // 1. 開啟相機與載入模型
    await startBrowserCamera();

    const detector = window.edgeDetector;
    if (!detector) {
      stopCapture();
      throw new Error("偵測模組尚未就緒，請稍候重試");
    }

    if (!detector.started) {
      detector.start(undefined, sessionId);
    }

    // 同步後端狀態
    fetch("/api/state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ started: true, session_id: sessionId }),
    }).catch(() => {});

    if (exportBtn) exportBtn.disabled = true;
    if (baselineRadio) baselineRadio.disabled = true;

    addSystemLog("[CALIBRATION] 請直視鏡頭並保持正常坐姿，開始個人基準校正...", "info");

    if (button) {
      button.innerText = "校準中 0% (點擊取消)";
    }
    if (statusText) {
      statusText.textContent = `校準中... 0/${detector.calibrationProgress.target}`;
    }
    if (startCalibrationBtn) {
      startCalibrationBtn.disabled = true;
      startCalibrationBtn.textContent = "校準中...";
    }

    // 2. 啟動 detector 校準收集
    detector.startCalibration();

    // 3. 輪詢檢查校準進度
    stopCaliPolling();
    caliPollTimer = setInterval(() => {
      try {
        if (!detector.started || currentStage !== 1) {
          stopCaliPolling();
          return;
        }

        const { current, target } = detector.calibrationProgress;

        if (detector.isCalibrating) {
          const pct = Math.min(100, Math.round((current / target) * 100));
          if (statusText) {
            statusText.textContent = `校準中... ${current}/${target} (${pct}%)`;
          }
          if (button) {
            button.innerText = `校準中 ${pct}% (點擊取消)`;
          }
          return;
        }

        if (detector.isCalibrated) {
          stopCaliPolling();

          // 校準成功，自動套用 baseline
          detector.selectCalibration("baseline");

          if (baselineRadio) {
            baselineRadio.disabled = false;
            baselineRadio.checked = true;
            baselineRadio.dataset.wasCalibrated = "true";
          }
          if (statusText) {
            statusText.textContent = "已校準";
          }
          if (startCalibrationBtn) {
            startCalibrationBtn.disabled = false;
            startCalibrationBtn.textContent = "重新校準";
          }

          // 進入已校準階段，按鈕切換為「開始檢測」
          currentStage = 2;
          if (button) {
            button.innerText = "開始檢測";
            button.disabled = false;
            button.classList.remove("toggle-detection-button_active");
          }

          addSystemLog("[CALIBRATION] 校正完成！已確立個人基準門檻", "success");
          addSystemLog("[READY] 請點擊「開始檢測」開始疲勞監控與記錄報告", "info");
        }
      } catch (err) {
        console.warn("[CALIBRATION] poll error:", err);
      }
    }, 200);

  } catch (error) {
    stopCaliPolling();
    currentStage = 0;
    console.error("[ERROR]", error);
    addSystemLog(`[ERROR] ${error.message}`, "error");

    if (button) {
      button.innerText = "開始校正";
      button.disabled = false;
      button.classList.remove("toggle-detection-button_active");
    }
    if (startCalibrationBtn) {
      startCalibrationBtn.disabled = false;
      startCalibrationBtn.textContent = "開始校準";
    }
  }
}

/**
 * 步驟二：正式開始疲勞檢測與記錄報告
 */
function start_detecting_flow() {
  const detector = window.edgeDetector;
  if (!detector) return;

  currentStage = 3;
  if (typeof detector.startDetecting === "function") {
    detector.startDetecting();
  }

  const button = document.getElementById("toggle-detection-button");
  const exportBtn = document.getElementById("export-log-btn");

  if (button) {
    button.innerText = "停止檢測";
    button.classList.add("toggle-detection-button_active");
  }

  if (exportBtn) exportBtn.disabled = true;

  addSystemLog("[START] 正式開始疲勞檢測與記錄報告", "start");
}

/**
 * 步驟三：停止檢測（保留相機與基準，隨時可重新開始檢測或匯出報告）
 */
function stop_detecting_flow() {
  const detector = window.edgeDetector;
  if (!detector) return;

  currentStage = 2;
  if (typeof detector.stopDetecting === "function") {
    detector.stopDetecting();
  }

  const button = document.getElementById("toggle-detection-button");
  const exportBtn = document.getElementById("export-log-btn");

  if (button) {
    button.innerText = "開始檢測";
    button.classList.remove("toggle-detection-button_active");
  }

  if (exportBtn) exportBtn.disabled = false;

  addPauseLine();
  addSystemLog("[PAUSE] 疲勞檢測已暫停（可點擊「匯出資料」下載報告）", "stop");
}

/**
 * 完全關閉相機並重置狀態
 */
async function stop_all() {
  stopCaliPolling();
  currentStage = 0;

  const detector = window.edgeDetector;
  detector?.stop();

  try {
    const sessionId = getSessionId();
    await fetch("/api/state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ started: false, session_id: sessionId }),
      keepalive: true,
    }).catch(() => {});
  } catch (_) {}

  stopCapture();

  const button = document.getElementById("toggle-detection-button");
  const exportBtn = document.getElementById("export-log-btn");
  const startCalibrationBtn = document.getElementById("start-calibration-btn");
  const baselineRadio = document.querySelector('input[name="cali-option"][value="baseline"]');

  if (button) {
    button.innerText = "開始校正";
    button.disabled = false;
    button.classList.remove("toggle-detection-button_active");
  }

  if (exportBtn) exportBtn.disabled = false;
  if (startCalibrationBtn) {
    startCalibrationBtn.disabled = false;
    startCalibrationBtn.textContent = detector?.isCalibrated ? "重新校準" : "開始校準";
  }
  if (baselineRadio && !detector?.isCalibrated) {
    baselineRadio.disabled = true;
  }

  addPauseLine();
  addSystemLog("[STOP] 偵測已停止", "stop");
}

/**
 * 主按鈕點擊事件分發
 */
async function handle_detection_toggle() {
  if (currentStage === 0) {
    // 尚未校正 -> 點擊開始校正
    await start_calibration_flow();
  } else if (currentStage === 1) {
    // 校正中 -> 點擊取消校正並關閉相機
    await stop_all();
  } else if (currentStage === 2) {
    // 已校正完成 -> 點擊開始正式檢測
    start_detecting_flow();
  } else if (currentStage === 3) {
    // 檢測進行中 -> 點擊停止檢測
    stop_detecting_flow();
  }
}

window.addEventListener("pagehide", () => {
  window.edgeDetector?.stop();
});

document.addEventListener("DOMContentLoaded", () => {
  const button = document.getElementById("toggle-detection-button");
  if (button) {
    button.addEventListener("click", handle_detection_toggle);
  }
});

// ===== Calibration controls (右側卡片) =====
document.addEventListener("DOMContentLoaded", () => {
  const startBtn = document.getElementById("start-calibration-btn");
  const statusText = document.getElementById("baseline-status-text");
  const radios = document.querySelectorAll('input[name="cali-option"]');
  const baselineRadio = document.querySelector('input[name="cali-option"][value="baseline"]');

  if (!startBtn || !statusText) return;

  // 初始即允許點擊
  startBtn.disabled = false;

  startBtn.addEventListener("click", async () => {
    // 如果檢測中點擊重新校準，先暫停檢測
    if (currentStage === 3) {
      stop_detecting_flow();
    }
    await start_calibration_flow();
  });

  radios.forEach((radio) => {
    radio.addEventListener("change", () => {
      if (radio.value === "default") {
        try {
          window.edgeDetector?.selectCalibration("default");
          if (typeof addSystemLog === "function") {
            addSystemLog("[CALIBRATION] 切換為系統預設模式", "info");
          }
        } catch (error) {
          console.error("[CALIBRATION]", error);
        }
        return;
      }

      if (radio.value === "baseline") {
        if (!radio.dataset.wasCalibrated) {
          statusText.textContent = "尚未校準";
          return;
        }
        try {
          window.edgeDetector?.selectCalibration("baseline");
          if (typeof addSystemLog === "function") {
            addSystemLog("[CALIBRATION] 切換為個人校準基準 (Baseline)", "info");
          }
        } catch (error) {
          console.error("[CALIBRATION]", error);
        }
      }
    });
  });
});
