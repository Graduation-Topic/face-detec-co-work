let cameraStream = null;
let captureRunning = false;
let previewPromise = null;

window.edgeStats = {
  fps: 0,
  latency: 0,
  resolution: "--",
};

function isBrowserCameraActive() {
  return Boolean(
    cameraStream?.getVideoTracks().some((track) => track.readyState === "live"),
  );
}
function describeCameraError(error) {
  const messages = {
    NotAllowedError: "Camera permission was denied.",
    NotFoundError: "No camera was found.",
    NotReadableError:
      "The camera is already being used by another application.",
    OverconstrainedError: "The requested camera constraints are not available.",
    SecurityError: "Camera access is blocked by the browser security policy.",
  };

  return messages[error.name] || error.message || "Unknown camera error.";
}

async function waitForVideoMetadata() {
  if (cameraSource.videoWidth && cameraSource.videoHeight) {
    return;
  }

  await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      cleanup();
      reject(new Error("The camera did not provide video metadata."));
    }, 5000);

    const onLoadedMetadata = () => {
      cleanup();
      resolve();
    };

    const onError = () => {
      cleanup();
      reject(new Error("The camera video metadata could not be loaded."));
    };

    const cleanup = () => {
      clearTimeout(timeout);

      cameraSource.removeEventListener("loadedmetadata", onLoadedMetadata);

      cameraSource.removeEventListener("error", onError);
    };

    cameraSource.addEventListener("loadedmetadata", onLoadedMetadata, {
      once: true,
    });

    cameraSource.addEventListener("error", onError, {
      once: true,
    });
  });
}

async function openCameraStream() {
  cameraStream = await navigator.mediaDevices.getUserMedia({
    video: true,
    audio: false,
  });

  cameraSource.srcObject = cameraStream;

  await waitForVideoMetadata();
  await cameraSource.play();

  const videoTrack = cameraStream.getVideoTracks()[0];

  const settings = videoTrack?.getSettings?.() || {};

  const width = settings.width || cameraSource.videoWidth;
  const height = settings.height || cameraSource.videoHeight;

  window.edgeStats.resolution = width && height ? `${width} × ${height}` : "--";

  const resolutionInfo = document.getElementById("resolution-info");

  if (resolutionInfo) {
    resolutionInfo.textContent = window.edgeStats.resolution;
  }

  updateCameraLayout();
}
// =========================================================
// Camera Preview
// =========================================================

function startBrowserPreview() {
  if (previewPromise) {
    return previewPromise;
  }

  previewPromise = (async () => {
    if (!cameraSource) {
      throw new Error("Camera video element is missing.");
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error(
        window.isSecureContext
          ? "Browser camera access is unavailable."
          : "Camera needs HTTPS or localhost. Open http://localhost:4000 or use an https:// URL.",
      );
    }

    if (isBrowserCameraActive()) {
      return;
    }

    try {
      await openCameraStream();

      const videoTrack = cameraStream.getVideoTracks()[0];
      const cameraName = videoTrack?.label || "Unknown camera";

      if (typeof addSystemLog === "function") {
        addSystemLog(`[OK] 鏡頭: ${cameraName}`, "success");
      }
    } catch (error) {
      stopBrowserCamera();

      throw new Error(`無法開啟鏡頭: ${describeCameraError(error)}`, {
        cause: error,
      });
    }
  })();

  const clearPreviewPromise = () => {
    previewPromise = null;
  };

  previewPromise.then(clearPreviewPromise, clearPreviewPromise);

  return previewPromise;
}

// =========================================================
// 開鏡頭預覽 + 載入本機模型 + 開始逐幀偵測
// =========================================================

async function startBrowserCamera() {
  await startBrowserPreview();
  await ensureEdge();

  if (captureRunning) {
    return;
  }

  clearLandmarks();

  captureRunning = true;
  lastVideoTime = -1;
  frameStamps.length = 0;

  runEdgeLoop(++loopToken);
}

function stopCapture() {
  captureRunning = false;
  loopToken += 1;

  frameStamps.length = 0;

  window.edgeStats.fps = 0;
  window.edgeStats.latency = 0;

  clearLandmarks();
}

function stopBrowserCamera() {
  captureRunning = false;
  loopToken += 1;

  cameraStream?.getTracks().forEach((track) => track.stop());

  cameraStream = null;

  if (cameraSource) {
    cameraSource.pause();
    cameraSource.srcObject = null;
  }
}
window.isBrowserCameraActive = isBrowserCameraActive;

window.startBrowserPreview = startBrowserPreview;

window.startBrowserCamera = startBrowserCamera;

window.stopBrowserCamera = stopBrowserCamera;

window.stopCapture = stopCapture;

window.clearLandmarks = clearLandmarks;

window.addEventListener("pagehide", stopBrowserCamera);

window.addEventListener("resize", scheduleCameraLayoutUpdate);

window.addEventListener("orientationchange", scheduleCameraLayoutUpdate);

window.visualViewport?.addEventListener("resize", scheduleCameraLayoutUpdate);

const cameraResizeObserver = cameraSource
  ? new ResizeObserver(() => {
      scheduleCameraLayoutUpdate();
    })
  : null;

if (cameraResizeObserver) {
  const cameraContainer = cameraSource.closest(".fd-video");

  if (cameraContainer) {
    cameraResizeObserver.observe(cameraContainer);
  }

  cameraResizeObserver.observe(cameraSource);
}

document.addEventListener("DOMContentLoaded", () => {
  updateCameraLayout();

  if (typeof addSystemLog === "function") {
    addSystemLog("[OK] 鏡頭模組載入", "success");
  }

  ensureEdge().catch((error) => {
    console.error("[EDGE] Background preload failed:", error);

    if (typeof addSystemLog === "function") {
      addSystemLog(`[ERROR] Edge preload failed: ${error.message}`, "error");
    }
  });

  startBrowserPreview()
    .then(() => {
      if (typeof addSystemLog === "function") {
        addSystemLog("[OK] 鏡頭預覽", "success");
      }
    })
    .catch((error) => {
      console.error("[CAMERA]", error);

      if (typeof addSystemLog === "function") {
        addSystemLog(`[ERROR] ${error.message}`, "error");
      }
    });
});
