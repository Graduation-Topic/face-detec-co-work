let loopToken = 0;
let lastVideoTime = -1;

const frameStamps = [];

// =========================================================
// Edge：逐幀偵測迴圈
// =========================================================

function scheduleFrame(callback) {
  if (typeof cameraSource.requestVideoFrameCallback === "function") {
    cameraSource.requestVideoFrameCallback(() => callback());
  } else {
    requestAnimationFrame(() => callback());
  }
}

function updateEdgeStats(frameStart, elapsedMs) {
  frameStamps.push(frameStart);

  if (frameStamps.length > 30) {
    frameStamps.shift();
  }

  if (frameStamps.length > 1) {
    const span = frameStart - frameStamps[0];

    if (span > 0) {
      window.edgeStats.fps =
        Math.round((10000 * (frameStamps.length - 1)) / span) / 10;
    }
  }

  window.edgeStats.latency = Math.round(elapsedMs);

  // ====== 呼叫外部的環境檢測模組 (Environment Module) ======
  if (typeof window.analyzeEnvironment === "function") {
    const env = window.analyzeEnvironment(cameraSource);
    window.edgeStats.brightness = env.brightness;
    window.edgeStats.highlightRatio = env.highlightRatio;

    let isNightMode = false;
    let filterStyle = "none";
    let envStatus = "";

    if (env.brightness !== null) {
      const cfg = window.edgeConfig || {};
      const nightBrightThresh = cfg.ENV_NIGHT_BRIGHTNESS ;
      const nightHighRatio = cfg.ENV_NIGHT_HIGHLIGHT_RATIO ;
      const dayBrightThresh = cfg.ENV_DAY_BRIGHTNESS ;
      const dayHighRatio = cfg.ENV_DAY_HIGHLIGHT_RATIO ;
      if (env.brightness < nightBrightThresh) {
        isNightMode = true;
        if (env.highlightRatio > nightHighRatio) {
          filterStyle = "contrast(1.1) brightness(1.2)";
          envStatus = "(🌙 夜間 + 壓高光)";
        } else {
          filterStyle = "contrast(1.5) brightness(1.5)";
          envStatus = "(🌙 夜間增強)";
        }
      } else if (env.brightness > dayBrightThresh || env.highlightRatio > dayHighRatio) {
        filterStyle = "brightness(0.85) contrast(1.1)";
        envStatus = "(☀️ 強光壓制)";
      }
    }

    window.edgeStats.isNightMode = isNightMode;
    window.edgeStats.envStatus = envStatus;

    if (cameraSource) {
      cameraSource.style.filter = filterStyle;
    }
  }
}

function processEdgeFrame() {
  const detector = window.edgeDetector;

  if (!landmarker || !detector?.started) return;
  if (cameraSource.readyState < 2) return;
  if (cameraSource.currentTime === lastVideoTime) return;

  lastVideoTime = cameraSource.currentTime;
  const t0 = performance.now();
  detector.aspect = cameraSource.videoWidth / cameraSource.videoHeight;
  const result = landmarker.detectForVideo(cameraSource, t0);
  const face = result.faceLandmarks?.[0] ?? null;

  detector.update(face, t0 / 1000);
  window.__latestFaceLandmarks = face ? [face] : [];

  drawLandmarks(window.__latestFaceLandmarks);
  updateEdgeStats(t0, performance.now() - t0);
}

function runEdgeLoop(token) {
  const tick = () => {
    if (!captureRunning || token !== loopToken) return;
    try {
      processEdgeFrame();
    } catch (error) {
      console.error("[EDGE] Frame processing failed:", error);
    }
    scheduleFrame(tick);
  };
  scheduleFrame(tick);
}
