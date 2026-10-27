// ===== Environment & Lighting Analysis Module =====
// 負責：中心測光、壓高光檢測、影像環境分析

const hiddenCanvas = document.createElement("canvas");
const hiddenCtx = hiddenCanvas.getContext("2d", { willReadFrequently: true });
hiddenCanvas.width = 64;
hiddenCanvas.height = 64;

function analyzeEnvironment(videoEl) {
  if (!videoEl || !videoEl.videoWidth) return { brightness: null, highlightRatio: 0 };
  
  hiddenCtx.drawImage(videoEl, 0, 0, 64, 64);
  const data = hiddenCtx.getImageData(0, 0, 64, 64).data;

  // 動態讀取後端設定，若未讀取到則使用預設值防呆
  const lumaHighlightThresh = window.edgeConfig?.ENV_LUMA_HIGHLIGHT ?? 220;

  let weightedSum = 0;
  let totalWeight = 0;
  let highlightCount = 0;

  for (let y = 0; y < 64; y++) {
    for (let x = 0; x < 64; x++) {
      const i = (y * 64 + x) * 4;
      // 1. 人眼視覺真實亮度 (Luminance)
      const luma = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];

      // 2. 中心測光權重 (Center-Weighted)
      const dx = x - 32;
      const dy = y - 32;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const weight = Math.max(0.2, 1 - dist / 40);

      weightedSum += luma * weight;
      totalWeight += weight;

      // 3. 高光像素偵測
      if (luma > lumaHighlightThresh) {
        highlightCount++;
      }
    }
  }

  const brightness = Math.round((weightedSum / totalWeight) * 10) / 10;
  const highlightRatio = highlightCount / (64 * 64);

  return { brightness, highlightRatio };
}

// 將函式掛載到 window，讓其他模組可以呼叫
window.analyzeEnvironment = analyzeEnvironment;

document.addEventListener("DOMContentLoaded", () => {
  if (typeof addSystemLog === "function") {
    addSystemLog("[OK] Environment module loaded", "success");
  }
});