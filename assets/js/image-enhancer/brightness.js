window.ImageEnhancer = (() => {
  // 環境亮度檢測專用微型畫布
  const hiddenCanvas = document.createElement("canvas");
  const hiddenCtx = hiddenCanvas.getContext("2d", {
    willReadFrequently: true,
  });

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

  function update(videoEl) {
    const brightness = calculateBrightness(videoEl);
    const isNightMode = brightness !== null && brightness < 70;

    window.edgeStats.brightness = brightness;
    window.edgeStats.isNightMode = isNightMode;

    if (videoEl) {
      videoEl.style.filter = isNightMode
        ? "contrast(1.5) brightness(1.5)"
        : "none";
    }
  }

  return { update };
})();
