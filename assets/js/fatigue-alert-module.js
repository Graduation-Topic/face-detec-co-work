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
      message.style.background = "rgba(108, 117, 125, 0.9)";
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

    // 等級 1：致命危險攔截 (微睡眠 / 瞬間點頭下墜 / 持續低頭)
    if (eyeClosureDur >= microsleepDur) {
      alertText = "致命危險：微睡眠發生 (Microsleep)！";
      isCritical = true;
    } else if (isSnapNodding || nodDur >= nodMinDur) {
      alertText = "致命危險：打瞌睡點頭 (Head Snap)！";
      isCritical = true;
    }
    // 等級 2：中度疲勞與分心預警 (慢速眨眼 / 打哈欠 / 左右張望)
    else if (eyeClosureDur >= config.EYE_CLOSURE_MIN_DURATION) {
      alertText = "警告：慢速眨眼 / 長時間閉眼";
    } else if (yawnDur >= config.YAWN_MIN_DURATION) {
      alertText = "警告：偵測到打哈欠";
    } else if (isLookingAway) {
      alertText = "注意：視線偏離前方 (分心)";
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

initializeAlert();
document.addEventListener("DOMContentLoaded", initializeAlert, { once: true });
