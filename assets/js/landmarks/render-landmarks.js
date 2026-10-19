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

  // 使用 clientWidth / clientHeight 避免受到 CSS transform: scaleX(-1) 干擾
  const cssWidth = Math.max(1, landmarkOverlay.clientWidth);
  const cssHeight = Math.max(1, landmarkOverlay.clientHeight);

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

  // 如果設定裡有把特徵點關閉，則清空後直接返回
  if (window.showLandmarks === false) return;

  const videoWidth = cameraSource.videoWidth;
  const videoHeight = cameraSource.videoHeight;

  // 計算 object-fit: contain 的留黑邊比例
  const scale = Math.min(
    cssWidth / videoWidth,
    cssHeight / videoHeight,
  );

  const renderedWidth = videoWidth * scale;
  const renderedHeight = videoHeight * scale;

  const contentOffsetX = (cssWidth - renderedWidth) / 2;
  const contentOffsetY = (cssHeight - renderedHeight) / 2;

  for (const face of faces || []) {
    for (const [index, point] of face.entries()) {
      if (
        !EYE_LANDMARKS.has(index) &&
        !NOSE_LANDMARKS.has(index) &&
        !MOUTH_LANDMARKS.has(index)
      ) {
        continue;
      }

      const x = contentOffsetX + point.x * renderedWidth;
      const y = contentOffsetY + point.y * renderedHeight;

      // 鼻尖、額頭、下巴、臉頰等關鍵姿態點畫成亮青色，其餘眼嘴點畫成白色
      const isPosePoint = NOSE_LANDMARKS.has(index);
      landmarkContext.fillStyle = isPosePoint ? "#00e5ff" : "#ffffff";

      landmarkContext.beginPath();
      landmarkContext.arc(
        x,
        y,
        isPosePoint ? 3 : 2, 
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
