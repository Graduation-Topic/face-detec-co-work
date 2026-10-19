// ===== Settings modal =====
document.addEventListener("DOMContentLoaded", () => {
  const settingsBtn = document.getElementById("settings-btn");
  const settingModal = document.getElementById("settings-modal");
  const fdOverlay = document.querySelector(".fd-overlay");

  if (!settingsBtn || !settingModal || !fdOverlay) {
    console.warn("settings modal: element not found", {
      settingsBtn,
      settingModal,
      fdOverlay,
    });
    return;
  }

  const openSettings = () => {
    settingModal.classList.add("active");
    fdOverlay.classList.add("is-active");
  };

  const closeSettings = () => {
    settingModal.classList.remove("active");
    fdOverlay.classList.remove("is-active");
  };

  settingsBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    settingModal.classList.contains("active")
      ? closeSettings()
      : openSettings();
  });

  settingModal.addEventListener("click", (event) => {
    if (event.target.closest("[data-overlay-off]")) {
      closeSettings();
    }
  });

  document.addEventListener("click", (event) => {
    if (!settingModal.contains(event.target)) {
      closeSettings();
    }
  });

  fdOverlay.addEventListener("mouseleave", () => {
    if (!settingModal.classList.contains("active")) {
      fdOverlay.classList.remove("is-active");
    }
  });
});
