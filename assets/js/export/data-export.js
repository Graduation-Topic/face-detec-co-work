// ===== CSV export =====
document.addEventListener("DOMContentLoaded", () => {
  const exportBtn = document.getElementById("export-log-btn");

  if (!exportBtn) return;

  exportBtn.addEventListener("click", () => {
    if (exportBtn.disabled) return;

    if (typeof addSystemLog === "function") {
      addSystemLog("[EXPORT] 下載資料", "start");
    }

    const detector = window.edgeDetector;

    if (!detector) {
      console.error("[EXPORT] edgeDetector not found");

      if (typeof addSystemLog === "function") {
        addSystemLog("[EXPORT] Detector not found", "error");
      }

      return;
    }

    const logCount = detector.logHistory?.length ?? 0;

    if (logCount === 0) {
      console.warn("[EXPORT] No frontend log data");

      if (typeof addSystemLog === "function") {
        addSystemLog("[EXPORT] No log data", "error");
      }

      return;
    }

    try {
      detector.downloadCSV();

      if (typeof addSystemLog === "function") {
        addSystemLog(
          `[EXPORT] Download completed (${logCount} rows)`,
          "success",
        );
      }
    } catch (error) {
      console.error("[EXPORT] CSV download error:", error);

      if (typeof addSystemLog === "function") {
        addSystemLog("[EXPORT] Download failed", "error");
      }
    }
  });
});
