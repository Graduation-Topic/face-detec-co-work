const cameraSource = document.getElementById("camera_source");
const landmarkOverlay = document.getElementById("landmark-overlay");
const landmarkContext = landmarkOverlay?.getContext("2d");

let EYE_LANDMARKS = new Set();
let NOSE_LANDMARKS = new Set();
let MOUTH_LANDMARKS = new Set();

function updateCameraLayout() {
  const container = cameraSource?.closest(".fd-video");

  if (!cameraSource || !container) return;

  const videoWidth = cameraSource.videoWidth;
  const videoHeight = cameraSource.videoHeight;

  if (videoWidth > 0 && videoHeight > 0) {
    container.style.aspectRatio = `${videoWidth} / ${videoHeight}`;
  }

  drawLandmarks(window.__latestFaceLandmarks || []);
}

function scheduleCameraLayoutUpdate() {
  if (!cameraSource) return;

  requestAnimationFrame(() => {
    updateCameraLayout();
  });
}

function applyLandmarkConfig(config) {
  EYE_LANDMARKS = new Set([
    ...(config.LEFT_EAR_POINTS || []),
    ...(config.RIGHT_EAR_POINTS || []),
  ]);

  NOSE_LANDMARKS = new Set(config.NOSE || []);

  MOUTH_LANDMARKS = new Set(config.MOUTH || []);
}

function drawLandmarks(faces) {
  if (!landmarkOverlay || !landmarkContext || !cameraSource) return;

  if (!cameraSource.videoWidth || !cameraSource.videoHeight) return;

  const videoRect = cameraSource.getBoundingClientRect();
  const overlayRect = landmarkOverlay.getBoundingClientRect();

  const cssWidth = Math.max(1, overlayRect.width);
  const cssHeight = Math.max(1, overlayRect.height);

  const devicePixelRatio = Math.max(1, window.devicePixelRatio || 1);

  const canvasWidth = Math.max(1, Math.round(cssWidth * devicePixelRatio));

  const canvasHeight = Math.max(1, Math.round(cssHeight * devicePixelRatio));

  if (
    landmarkOverlay.width !== canvasWidth ||
    landmarkOverlay.height !== canvasHeight
  ) {
    landmarkOverlay.width = canvasWidth;
    landmarkOverlay.height = canvasHeight;
  }

  landmarkContext.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);

  landmarkContext.clearRect(0, 0, cssWidth, cssHeight);

  const videoWidth = cameraSource.videoWidth;
  const videoHeight = cameraSource.videoHeight;

  const scale = Math.min(
    videoRect.width / videoWidth,
    videoRect.height / videoHeight,
  );

  const renderedWidth = videoWidth * scale;
  const renderedHeight = videoHeight * scale;

  const contentOffsetX = (videoRect.width - renderedWidth) / 2;

  const contentOffsetY = (videoRect.height - renderedHeight) / 2;

  const videoOffsetX = videoRect.left - overlayRect.left;

  const videoOffsetY = videoRect.top - overlayRect.top;

  for (const face of faces || []) {
    for (const [index, point] of face.entries()) {
      if (
        !EYE_LANDMARKS.has(index) &&
        !NOSE_LANDMARKS.has(index) &&
        !MOUTH_LANDMARKS.has(index)
      ) {
        continue;
      }

      const x = videoOffsetX + contentOffsetX + point.x * renderedWidth;

      const y = videoOffsetY + contentOffsetY + point.y * renderedHeight;

      landmarkContext.fillStyle = NOSE_LANDMARKS.has(index)
        ? "#00e5ff"
        : "#ffffff";

      landmarkContext.beginPath();

      landmarkContext.arc(
        x,
        y,
        NOSE_LANDMARKS.has(index) ? 3 : 2,
        0,
        Math.PI * 2,
      );

      landmarkContext.fill();
    }
  }
}

function clearLandmarks() {
  window.__latestFaceLandmarks = [];
  if (!landmarkOverlay || !landmarkContext) return;
  landmarkContext.clearRect(
    0,
    0,
    landmarkOverlay.width,
    landmarkOverlay.height,
  );
}
