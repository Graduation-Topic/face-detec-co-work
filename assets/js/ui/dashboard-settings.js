/**
 * dashboard-settings.js — 後台「設定」頁面模組
 * 負責個人基本資料展示、LINE Messaging API 帳號綁定、測試推播與通知開關
 */

(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  let currentSettings = null;

  const roleLabels = {
    super_admin: "總管理員",
    admin: "車隊管理員",
    driver: "駕駛員",
    employee: "員工",
  };

  // ===== 載入個人與 LINE 設定 =====
  async function loadSettings() {
    try {
      const res = await fetch("/api/user/line-settings");
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (!res.ok) return;

      const data = await res.json();
      currentSettings = data.settings || {};

      renderSettingsView(currentSettings);
    } catch (err) {
      console.error("[SETTINGS] 載入設定失敗:", err);
    }
  }

  // ===== 渲染設定介面 =====
  function renderSettingsView(st) {
    // 1. 基本資料
    const userInfoEl = $("settings-user-info");
    if (userInfoEl) {
      const rLabel = roleLabels[st.role] || st.role || "使用者";
      userInfoEl.textContent = `${st.display_name || st.username} (@${st.username}) · ${rLabel}`;
    }

    // 2. LINE API 連線狀態
    const lineBadge = $("line-api-status-badge");
    if (lineBadge) {
      if (st.has_line) {
        lineBadge.textContent = "已連線";
        lineBadge.className = "status-badge active cursor-pointer";
        lineBadge.title = `已綁定 ID: ${st.line_user_id}`;
      } else {
        lineBadge.textContent = "未連接";
        lineBadge.className = "status-badge inactive cursor-pointer";
        lineBadge.title = "點擊開啟設定彈窗";
      }
    }

    // 3. 網頁端 LINE 通知開關
    const lineToggle = $("line-notify-toggle");
    if (lineToggle) {
      lineToggle.checked = !!(st.has_line && st.line_notify_enabled);
    }
  }

  // ===== 快速切換 LINE 通知開關 =====
  const lineToggle = $("line-notify-toggle");
  if (lineToggle) {
    lineToggle.addEventListener("change", async () => {
      if (!currentSettings || !currentSettings.has_line) {
        alert("請先綁定 LINE User ID 後再開啟推播通知！");
        lineToggle.checked = false;
        openLineModal();
        return;
      }

      const enabled = lineToggle.checked;
      try {
        const res = await fetch("/api/user/line-settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ line_notify_enabled: enabled }),
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.message || "更新失敗");
        }
        currentSettings.line_notify_enabled = enabled;
      } catch (err) {
        alert("更新通知設定失敗: " + err.message);
        lineToggle.checked = !enabled;
      }
    });
  }

  // ===== LINE 設定彈窗邏輯 =====
  const lineModal = $("line-settings-modal");
  const openLineBtn = $("btn-open-line-modal");
  const badgeBtn = $("line-api-status-badge");
  const closeLineBtn = $("btn-close-line-modal");
  const cancelLineBtn = $("btn-cancel-line-modal");
  const lineBackdrop = $("line-modal-backdrop");
  const lineForm = $("line-settings-form");
  const lineErrBox = $("line-settings-error");
  const lineSuccessBox = $("line-settings-success");
  const testPushBtn = $("btn-test-line-push");
  const testFeedback = $("line-test-feedback");

  function openLineModal() {
    if (!lineModal) return;
    if (lineErrBox) {
      lineErrBox.classList.add("hidden");
      lineErrBox.textContent = "";
    }
    if (lineSuccessBox) {
      lineSuccessBox.classList.add("hidden");
      lineSuccessBox.textContent = "";
    }
    if (testFeedback) {
      testFeedback.textContent = "";
    }

    const st = currentSettings || {};

    $("inp-my-line-id").value = st.line_user_id || "";
    $("inp-my-line-token").value = "";

    const tokenHint = $("token-status-hint");
    if (tokenHint) {
      if (st.has_custom_token) {
        tokenHint.textContent = "目前已設定專屬 Token (留空表示不更動，若需變更請直接輸入)";
      } else if (st.has_system_token) {
        tokenHint.textContent = "目前使用系統預設全域 Token (選填，如需自訂專屬 Bot 請在此填入)";
      } else {
        tokenHint.textContent = "目前系統未設定預設 Token，請填寫您的 LINE Channel Access Token";
      }
    }

    $("chk-my-line-enabled").checked = st.line_notify_enabled !== false;

    // 若為總管理員，顯示「接收所有車隊通報」選項
    const groupAll = $("group-my-line-all");
    const chkAll = $("chk-my-line-all");
    if (st.role === "super_admin") {
      if (groupAll) groupAll.classList.remove("hidden");
      if (chkAll) chkAll.checked = st.line_notify_all !== false;
    } else {
      if (groupAll) groupAll.classList.add("hidden");
    }

    lineModal.classList.remove("hidden");
  }

  function closeLineModal() {
    if (!lineModal) return;
    lineModal.classList.add("hidden");
  }

  if (openLineBtn) openLineBtn.addEventListener("click", openLineModal);
  if (badgeBtn) badgeBtn.addEventListener("click", openLineModal);
  if (closeLineBtn) closeLineBtn.addEventListener("click", closeLineModal);
  if (cancelLineBtn) cancelLineBtn.addEventListener("click", closeLineModal);
  if (lineBackdrop) lineBackdrop.addEventListener("click", closeLineModal);

  // ===== 發送測試推播訊息 =====
  if (testPushBtn) {
    testPushBtn.addEventListener("click", async () => {
      const targetId = $("inp-my-line-id").value.trim();
      const tokenInput = $("inp-my-line-token").value;

      if (!targetId) {
        if (testFeedback) {
          testFeedback.style.color = "var(--color-danger)";
          testFeedback.textContent = "請先填寫 LINE User ID";
        }
        return;
      }

      if (testFeedback) {
        testFeedback.style.color = "var(--color-text-secondary)";
        testFeedback.textContent = "發送測試推播中…";
      }
      testPushBtn.disabled = true;

      try {
        const payload = {
          line_user_id: targetId,
          line_token: tokenInput === "" ? "__UNCHANGED__" : tokenInput.trim(),
        };

        const res = await fetch("/api/user/line-settings/test", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.message || "發送失敗");
        }

        if (testFeedback) {
          testFeedback.style.color = "var(--color-success)";
          testFeedback.textContent = "✔ 測試訊息已成功送達！";
        }
      } catch (err) {
        if (testFeedback) {
          testFeedback.style.color = "var(--color-danger)";
          testFeedback.textContent = "✖ " + err.message;
        }
      } finally {
        testPushBtn.disabled = false;
      }
    });
  }

  // ===== 儲存 LINE 設定表單 =====
  if (lineForm) {
    lineForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (lineErrBox) lineErrBox.classList.add("hidden");
      if (lineSuccessBox) lineSuccessBox.classList.add("hidden");

      const submitBtn = $("btn-submit-line-modal");
      if (submitBtn) submitBtn.disabled = true;

      const targetId = $("inp-my-line-id").value.trim();
      const tokenInput = $("inp-my-line-token").value;
      const notifyEnabled = $("chk-my-line-enabled").checked;
      const notifyAll = $("chk-my-line-all") ? $("chk-my-line-all").checked : true;

      const payload = {
        line_user_id: targetId || null,
        line_notify_enabled: notifyEnabled,
        line_notify_all: notifyAll,
      };

      if (tokenInput === "") {
        payload.line_token = "__UNCHANGED__";
      } else {
        payload.line_token = tokenInput.trim() || null;
      }

      try {
        const res = await fetch("/api/user/line-settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.message || "儲存失敗");
        }

        currentSettings = Object.assign({}, currentSettings, data.settings);
        renderSettingsView(currentSettings);

        if (lineSuccessBox) {
          lineSuccessBox.textContent = data.message || "設定已成功儲存";
          lineSuccessBox.classList.remove("hidden");
        }

        setTimeout(() => {
          closeLineModal();
        }, 800);
      } catch (err) {
        if (lineErrBox) {
          lineErrBox.textContent = err.message;
          lineErrBox.classList.remove("hidden");
        }
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  }

  // 切換到 settings 分頁時自動重新載入
  window.addEventListener("popstate", () => {
    if (location.pathname.includes("/dashboard/settings")) {
      loadSettings();
    }
  });

  const settingsLink = document.querySelector('.dash-bookmark [dash-page="settings"]');
  if (settingsLink) {
    settingsLink.addEventListener("click", () => {
      setTimeout(loadSettings, 50);
    });
  }

  // 初始載入
  loadSettings();
})();

