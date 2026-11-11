// ===== Fatigue alerts =====
function initializeAlert() {
  if (window.__alertInitialized) return;

  const overlay = document.querySelector(".fd-alert-overlay");
  const message = document.querySelector(".fd-alert-message");
  const messageText = message?.querySelector("span");
  const alertToggle = document.getElementById("alert-message-toggle");

  if (!overlay || !message || !messageText) {
    console.error("[ALERT] Alert elements not found");
    return;
  }

  window.__alertInitialized = true;

  function hideAlert() {
    message.classList.add("hidden");
    overlay.classList.remove("active");
  }

  window.hideFatigueAlert = hideAlert;

  window.updateFatigueAlert = function updateFatigueAlert(data) {
    const detector = window.edgeDetector;

    if (!detector?.started) {
      hideAlert();
      return;
    }

    if (alertToggle && !alertToggle.checked) {
      hideAlert();
      return;
    }

    if (!data) {
      hideAlert();
      return;
    }

    if (Number(data.faces ?? 0) === 0) {
      messageText.textContent = "未偵測到臉";
      message.style.background = "rgba(108, 117, 125, 0.4)";
      message.classList.remove("hidden");
      overlay.classList.add("active");
      return;
    }

    const eyeClosureDur = Number(data.eye_closure_dur ?? 0);
    const yawnDur = Number(data.yawn_dur ?? 0);
    const nodDur = Number(data.nod_dur ?? 0);
    const isSnapNodding = Boolean(data.is_snap_nodding);
    const isLookingAway = Boolean(data.is_looking_away);

    const config = detector.cfg;

    if (!config) {
      console.warn("[ALERT] Detector config not found");
      hideAlert();
      return;
    }

    const microsleepDur = config.MICROSLEEP_MIN_DURATION ?? 1.5;
    const nodMinDur = config.NOD_MIN_DURATION ?? 1.5;

    let alertText = "";
    let isCritical = false;

    // *需修改警告訊息
    //
    // 等級 1：輕度疲勞 (微睡眠 / 瞬間點頭下墜 / 持續低頭)
    if (eyeClosureDur >= microsleepDur) {
      alertText = "微睡眠發生 (Microsleep)！";
      isCritical = true;
    } else if (isSnapNodding) {
      alertText = "打瞌睡點頭 (Head Snap)！";
      isCritical = true;
    } else if (nodDur >= nodMinDur) {
      alertText = "持續低頭打瞌睡！";
      isCritical = true;
    }

    // *需修改警告訊息
    //
    // 等級 2：中度疲勞與分心預警 (慢速眨眼 / 打哈欠 / 左右張望)
    else if (eyeClosureDur >= config.EYE_CLOSURE_MIN_DURATION) {
      alertText = "長時間閉眼";
    } else if (yawnDur >= config.YAWN_MIN_DURATION) {
      alertText = "偵測到打哈欠";
    } else if (isLookingAway) {
      alertText = "視線偏離前方 (分心)";
    }

    if (alertText) {
      messageText.textContent = alertText;
      message.style.background = isCritical
        ? "rgba(180, 0, 0, 0.95)"
        : "rgba(212, 136, 6, 0.95)";
      message.classList.remove("hidden");
      overlay.classList.add("active");
    } else {
      hideAlert();
    }
  };

  if (alertToggle) {
    alertToggle.addEventListener("change", () => {
      if (!alertToggle.checked) {
        hideAlert();
      }
    });
  }

  hideAlert();
}

// ===== Alert Event Dispatcher to Backend =====
const alertQueue = [];
let isSendingAlert = false;

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function sendAlert(alertInfo) {
  try {
    const sessionId =
      window.edgeDetector?.sessionId ||
      sessionStorage.getItem("fatigue-detection-session-id");

    if (typeof addSystemLog === "function") {
      addSystemLog(
        `[ALERT] ${alertInfo.reason} x${alertInfo.count}`,
        "warning",
      );
    }

    for (let attempt = 1; attempt <= 3; attempt += 1) {
      try {
        const response = await fetch("/api/alert", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            score: alertInfo.score,
            level: alertInfo.level,
            reason: alertInfo.reason,
            count: alertInfo.count,
            timestamp: Date.now() / 1000,
          }),
        });

        if (response.ok) {
          const result = await response.json();
          if (result.is_new_escalation) {
            const windowMin = Math.round((result.window_sec || 300) / 60);
            if (typeof addSystemLog === "function") {
              addSystemLog(
                `[後台通報] 警告已在 ${windowMin} 分鐘內累積達 ${result.window_count} 次，已通報後台管理者！`,
                "error",
              );
            }
          }
          return;
        }

        const body = await response.text();
        if (response.status < 500 || attempt === 3) {
          console.error(
            "[ALERT API] Server returned status",
            response.status,
            body,
          );
          return;
        }
      } catch (error) {
        if (attempt === 3) throw error;
      }

      await wait(250 * 2 ** (attempt - 1));
    }
  } catch (error) {
    console.error("[ALERT] Failed to post alert event:", error);
  }
}

async function processAlertQueue() {
  if (isSendingAlert) return;
  isSendingAlert = true;
  try {
    while (alertQueue.length) {
      await sendAlert(alertQueue.shift());
    }
  } finally {
    isSendingAlert = false;
  }
}

window.handleAlertEvent = function handleAlertEvent(alertInfo) {
  alertQueue.push({ ...alertInfo });
  void processAlertQueue();
};

initializeAlert();
document.addEventListener("DOMContentLoaded", initializeAlert, { once: true });
