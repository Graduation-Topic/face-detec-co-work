let loopToken = 0;
let lastVideoTime = -1;

const frameStamps = [];

// 新增：環境亮度檢測專用微型畫布
const hiddenCanvas = document.createElement("canvas");
const hiddenCtx = hiddenCanvas.getContext("2d", { willReadFrequently: true });
hiddenCanvas.width = 64;
hiddenCanvas.height = 64;

function calculateBrightness(videoEl) {
  if (!videoEl || !videoEl.videoWidth) return null;
  hiddenCtx.drawImage(videoEl, 0, 0, 64, 64);
  const data = hiddenCtx.getImageData(0, 0, 64, 64).data;
  let sum = 0;
  for (let i = 0; i < data.length; i += 4) {
    sum += (data[i] + data[i + 1] + data[i + 2]) / 3;
  }
  return Math.round((sum / (64 * 64)) * 10) / 10;
}

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

  // 更新環境亮度與夜間模式增強濾鏡
  const brightness = calculateBrightness(cameraSource);
  window.edgeStats.brightness = brightness;
  window.edgeStats.isNightMode = brightness !== null && brightness < 70;

  if (cameraSource) {
    cameraSource.style.filter = window.edgeStats.isNightMode
      ? "contrast(1.5) brightness(1.5)"
      : "none";
  }
}

function processEdgeFrame() {
  const detector = window.edgeDetector;

  if (!landmarker || !detector?.started) {
    return;
  }

  if (cameraSource.readyState < 2) {
    return;
  }

  if (cameraSource.currentTime === lastVideoTime) {
    return;
  }

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
    if (!captureRunning || token !== loopToken) {
      return;
    }

    try {
      processEdgeFrame();
    } catch (error) {
      console.error("[EDGE] Frame processing failed:", error);
    }

    scheduleFrame(tick);
  };

  scheduleFrame(tick);
}
