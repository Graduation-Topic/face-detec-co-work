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

  window.ImageEnhancer.update(cameraSource);

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
