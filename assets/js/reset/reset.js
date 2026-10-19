document.addEventListener("DOMContentLoaded", () => {
  const resetBtn = document.getElementById("reset-data-button");

  if (!resetBtn) {
    return;
  }

  resetBtn.addEventListener("click", async () => {
    if (resetBtn.disabled) return;

    try {
      resetBtn.disabled = true;

      const detector = window.edgeDetector;
      detector?.reset();

      const current = detector ? detector.toApiData() : {};

      if (typeof resetCharts === "function") {
        resetCharts();
      }

      if (typeof updateData === "function") {
        updateData({
          fps: 0,
          latency: null,
          faces: 0,
          ear: null,
          mar: null,
          blink_times: 0,
          yawn_times: 0,
          eye_closure_dur: null,
          yawn_dur: null,
          perclos: null,

          ear_threshold: current.ear_threshold,
          mar_threshold: current.mar_threshold,
          default_ear_threshold: current.default_ear_threshold,
          default_mar_threshold: current.default_mar_threshold,
          baseline_ear_threshold: current.baseline_ear_threshold,
          baseline_mar_threshold: current.baseline_mar_threshold,

          fatigue_level: "Normal",
          brightness: null,
          is_night_mode: false,
          fatigue_score: null,
        });
      }

      // 4. Reset backend state
      const response = await fetch("/api/state/reset", {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error("Failed to reset backend state");
      }

      // 5. Clear local brightness state and camera filter
      if (window.edgeStats) {
        window.edgeStats.brightness = null;
        window.edgeStats.isNightMode = false;
      }

      const video = document.querySelector("video");
      if (video) {
        video.style.filter = "none";
      }

      // 6. Log reset event
      if (typeof addSystemLog === "function") {
        addSystemLog("[RESET] Data Cleared", "info");
      }
    } catch (error) {
      console.error("[RESET]", error);

      if (typeof addSystemLog === "function") {
        addSystemLog(`[ERROR] ${error.message}`, "error");
      }
    } finally {
      resetBtn.disabled = false;
    }
  });
});
