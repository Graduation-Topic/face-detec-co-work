/**
 * manage-users.js — 後台「員工管理」模組 (RBAC 角色管理)
 * 支援：總管理員 (可檢視/建立/修改所有人員與管理員資料) 與 一般管理員 (僅檢視/建立/修改自己名下的駕駛員)
 */

(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  let allUsers = [];
  let allManagers = [];
  let currentRole = "admin";
  let currentUserId = null;

  function showActionMsg(text, type = "info") {
    const el = $("action-msg");
    if (!el) return;
    el.textContent = text;
    el.className = `dash-msg dash-msg-${type}`;
    clearTimeout(el._t);
    el._t = setTimeout(() => {
      el.className = "hidden";
    }, 4500);
  }

  function formatTime(isoStr) {
    if (!isoStr) return "—";
    const date = new Date(isoStr);
    if (Number.isNaN(date.getTime())) return "—";
    return date.toLocaleString("zh-TW", { hour12: false });
  }

  function getRoleBadge(role) {
    if (role === "super_admin") {
      return '<span class="role-badge role-badge-super">總管理員</span>';
    }
    if (role === "admin") {
      return '<span class="role-badge role-badge-admin">車隊管理員</span>';
    }
    return '<span class="role-badge role-badge-driver">駕駛員</span>';
  }

  // ===== 載入使用者清單 =====
  async function loadUsers() {
    const tbody = $("manage-user-tbody");
    if (!tbody) return;

    try {
      const res = await fetch("/api/admin/users");
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || "讀取員工清單失敗");
      }

      allUsers = data.users || [];
      currentRole = data.current_role || "admin";
      currentUserId = data.current_user_id;

      // 更新統計數字
      const totalCount = allUsers.length;
      if ($("manage-total")) $("manage-total").textContent = totalCount;
      if ($("manage-on-detec")) $("manage-on-detec").textContent = 0;
      if ($("manage-not-detec")) $("manage-not-detec").textContent = totalCount;

      // 依目前角色設定建立彈窗的選項
      setupModalRoleOptions();

      // 渲染表格
      renderUserTable(allUsers);
    } catch (err) {
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="8" class="table-empty" style="color:var(--color-danger)!important">載入失敗: ${err.message}</td></tr>`;
      }
    }
  }

  // ===== 載入管理員清單 (供總管理員指派所屬主管) =====
  async function loadManagers() {
    try {
      const res = await fetch("/api/admin/managers");
      if (!res.ok) return;
      const data = await res.json();
      allManagers = data.managers || [];

      // 填充新增 Modal 的主管下拉選單
      const selectMgr = $("select-new-manager");
      if (selectMgr) {
        selectMgr.innerHTML = '<option value="">(無 / 直屬總管理員)</option>';
        allManagers.forEach((m) => {
          const opt = document.createElement("option");
          opt.value = m.id;
          opt.textContent = `${m.display_name || m.username} (${m.role === "super_admin" ? "總管理員" : "管理員"})`;
          selectMgr.appendChild(opt);
        });
      }

      // 填充編輯 Modal 的主管下拉選單
      const selectEditMgr = $("select-edit-manager");
      if (selectEditMgr) {
        selectEditMgr.innerHTML = '<option value="">(無 / 直屬總管理員)</option>';
        allManagers.forEach((m) => {
          const opt = document.createElement("option");
          opt.value = m.id;
          opt.textContent = `${m.display_name || m.username} (${m.role === "super_admin" ? "總管理員" : "管理員"})`;
          selectEditMgr.appendChild(opt);
        });
      }
    } catch (_) {}
  }

  // ===== 依登入者權限調整 Modal 表單選項 =====
  function setupModalRoleOptions() {
    const groupRole = $("group-new-role");
    const groupManager = $("group-new-manager");
    const selectRole = $("select-new-role");

    if (currentRole === "super_admin") {
      if (groupRole) groupRole.classList.remove("hidden");
      if (groupManager) groupManager.classList.remove("hidden");
      loadManagers();
    } else {
      // 一般管理員只能建 driver，隱藏選擇角色與主管
      if (groupRole) groupRole.classList.add("hidden");
      if (groupManager) groupManager.classList.add("hidden");
      if (selectRole) selectRole.value = "driver";
    }
  }

  // ===== 渲染員工表格 =====
  function renderUserTable(users) {
    const tbody = $("manage-user-tbody");
    if (!tbody) return;

    if (!users || users.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="8" class="table-empty">目前無符合條件的員工紀錄</td></tr>';
      return;
    }

    tbody.innerHTML = users
      .map((u) => {
        const isSelf = u.id === currentUserId;
        const canEdit =
          currentRole === "super_admin"
            ? true
            : u.role === "driver" && u.manager_id === currentUserId;

        const canDelete =
          currentRole === "super_admin"
            ? !isSelf
            : u.role === "driver" && u.manager_id === currentUserId;

        const editBtn = canEdit
          ? `<button class="btn-user-edit cursor-pointer" data-id="${u.id}">編輯</button>`
          : "";

        const deleteBtn = canDelete
          ? `<button class="btn-user-delete cursor-pointer" data-id="${u.id}" data-name="${u.display_name || u.username}">刪除</button>`
          : "";

        const actionBtns =
          editBtn || deleteBtn
            ? `${editBtn}${deleteBtn}`
            : '<span style="color:var(--color-text-muted);font-size:12px;">—</span>';

        const lineBadge = u.has_line
          ? '<span class="line-badge bound" title="已綁定 LINE 推播">● 已綁定</span>'
          : '<span class="line-badge unbound" title="未綁定 LINE">○ 未綁定</span>';

        return `
          <tr>
            <td>${u.id}</td>
            <td><strong>${u.username}</strong></td>
            <td>${u.display_name || "—"}</td>
            <td>${getRoleBadge(u.role)}</td>
            <td>${u.manager_name || "—"}</td>
            <td>${lineBadge}</td>
            <td>${formatTime(u.created_at)}</td>
            <td>${actionBtns}</td>
          </tr>
        `;
      })
      .join("");

    // 綁定編輯事件
    tbody.querySelectorAll(".btn-user-edit").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        const target = allUsers.find((u) => String(u.id) === String(id));
        if (target) {
          openEditModal(target);
        }
      });
    });

    // 綁定刪除事件
    tbody.querySelectorAll(".btn-user-delete").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        const name = btn.getAttribute("data-name");
        deleteUser(id, name);
      });
    });
  }

  // ===== 刪除員工 =====
  async function deleteUser(id, name) {
    if (!confirm(`確定要刪除員工帳號「${name}」(ID: ${id}) 嗎？此操作無法復原。`)) {
      return;
    }

    try {
      const res = await fetch(`/api/admin/users/${id}`, {
        method: "DELETE",
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.message || "刪除失敗");
      }
      showActionMsg(data.message || "刪除成功", "success");
      loadUsers();
    } catch (err) {
      showActionMsg(err.message, "error");
    }
  }

  // ===== 搜尋過濾 =====
  const searchInput = $("search-user");
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      const q = searchInput.value.trim().toLowerCase();
      if (!q) {
        renderUserTable(allUsers);
        return;
      }
      const filtered = allUsers.filter((u) => {
        const idStr = String(u.id);
        const nameStr = (u.display_name || "").toLowerCase();
        const userStr = (u.username || "").toLowerCase();
        const roleStr = (u.role || "").toLowerCase();
        const mgrStr = (u.manager_name || "").toLowerCase();
        return (
          idStr.includes(q) ||
          nameStr.includes(q) ||
          userStr.includes(q) ||
          roleStr.includes(q) ||
          mgrStr.includes(q)
        );
      });
      renderUserTable(filtered);
    });
  }

  // ===== 新增員工 Modal 開關邏輯 =====
  const modal = $("add-user-modal");
  const addBtn = $("manage-add-employee");
  const closeBtn = $("btn-close-modal");
  const cancelBtn = $("btn-cancel-modal");
  const backdrop = $("modal-backdrop");
  const form = $("add-user-form");
  const errBox = $("add-user-error");

  function openModal() {
    if (!modal) return;
    if (form) form.reset();
    if (errBox) {
      errBox.classList.add("hidden");
      errBox.textContent = "";
    }
    setupModalRoleOptions();
    modal.classList.remove("hidden");
  }

  function closeModal() {
    if (!modal) return;
    modal.classList.add("hidden");
  }

  if (addBtn) addBtn.addEventListener("click", openModal);
  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
  if (backdrop) backdrop.addEventListener("click", closeModal);

  // 角色選單切換時，若選 admin 則隱藏指派主管
  const selectRole = $("select-new-role");
  if (selectRole) {
    selectRole.addEventListener("change", () => {
      const groupMgr = $("group-new-manager");
      if (groupMgr) {
        if (selectRole.value === "admin") {
          groupMgr.classList.add("hidden");
        } else {
          groupMgr.classList.remove("hidden");
        }
      }
    });
  }

  // ===== 表單提交 (新增員工) =====
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (errBox) {
        errBox.classList.add("hidden");
        errBox.textContent = "";
      }

      const submitBtn = $("btn-submit-modal");
      if (submitBtn) submitBtn.disabled = true;

      const username = $("inp-new-username").value.trim();
      const displayName = $("inp-new-name").value.trim();
      const password = $("inp-new-password").value;
      const role = selectRole ? selectRole.value : "driver";
      const managerId =
        $("select-new-manager") && $("select-new-manager").value
          ? $("select-new-manager").value
          : null;

      try {
        const res = await fetch("/api/admin/users", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username,
            display_name: displayName,
            password,
            role,
            manager_id: managerId,
          }),
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.message || "建立帳號失敗");
        }

        showActionMsg(data.message || "成功建立員工帳號", "success");
        closeModal();
        loadUsers();
      } catch (err) {
        if (errBox) {
          errBox.textContent = err.message;
          errBox.classList.remove("hidden");
        }
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  }

  // ===== 編輯員工 Modal 邏輯 =====
  const editModal = $("edit-user-modal");
  const editCloseBtn = $("btn-close-edit-modal");
  const editCancelBtn = $("btn-cancel-edit-modal");
  const editBackdrop = $("edit-modal-backdrop");
  const editForm = $("edit-user-form");
  const editErrBox = $("edit-user-error");

  function closeEditModal() {
    if (!editModal) return;
    editModal.classList.add("hidden");
  }

  if (editCloseBtn) editCloseBtn.addEventListener("click", closeEditModal);
  if (editCancelBtn) editCancelBtn.addEventListener("click", closeEditModal);
  if (editBackdrop) editBackdrop.addEventListener("click", closeEditModal);

  function openEditModal(user) {
    if (!editModal) return;
    if (editForm) editForm.reset();
    if (editErrBox) {
      editErrBox.classList.add("hidden");
      editErrBox.textContent = "";
    }

    $("inp-edit-user-id").value = user.id;
    $("inp-edit-username").value = user.username || "";
    $("inp-edit-name").value = user.display_name || user.username || "";
    $("inp-edit-password").value = "";

    // 帳號狀態
    const selActive = $("select-edit-active");
    if (selActive) {
      selActive.value = user.is_active === false ? "false" : "true";
    }

    // 角色設定 (僅總管理員可變更角色與指派主管)
    const groupRole = $("group-edit-role");
    const selectRole = $("select-edit-role");
    const groupMgr = $("group-edit-manager");
    const selectMgr = $("select-edit-manager");
    const groupLineAll = $("group-edit-line-all");
    const groupLineToken = $("group-edit-line-token");

    if (currentRole === "super_admin") {
      if (groupRole) groupRole.classList.remove("hidden");
      if (selectRole) {
        selectRole.value = user.role || "driver";
        selectRole.disabled = user.id === currentUserId; // 總管理員無法降級自己
      }

      if (selectMgr) {
        selectMgr.innerHTML = '<option value="">(無 / 直屬總管理員)</option>';
        allManagers.forEach((m) => {
          const opt = document.createElement("option");
          opt.value = m.id;
          opt.textContent = `${m.display_name || m.username} (${m.role === "super_admin" ? "總管理員" : "管理員"})`;
          selectMgr.appendChild(opt);
        });
        selectMgr.value = user.manager_id || "";
      }

      if (groupMgr) {
        if (user.role === "driver") {
          groupMgr.classList.remove("hidden");
        } else {
          groupMgr.classList.add("hidden");
        }
      }

      if (groupLineAll) groupLineAll.classList.remove("hidden");
      if (groupLineToken) groupLineToken.classList.remove("hidden");
    } else {
      // 一般管理員不可改角色、主管與全域推播
      if (groupRole) groupRole.classList.add("hidden");
      if (groupMgr) groupMgr.classList.add("hidden");
      if (groupLineAll) groupLineAll.classList.add("hidden");
      if (groupLineToken) groupLineToken.classList.add("hidden");
    }

    // LINE 設定
    $("inp-edit-line-id").value = user.line_user_id || "";
    $("inp-edit-line-token").value = "";
    const hintEl = $("edit-token-hint");
    if (hintEl) {
      hintEl.textContent = user.line_token
        ? "目前已設定專屬 Token (留空表示不更動)"
        : "目前未設定專屬 Token (使用系統預設)";
    }

    const chkEnabled = $("chk-edit-line-enabled");
    if (chkEnabled) {
      chkEnabled.checked = user.line_notify_enabled !== false;
    }

    const chkAll = $("chk-edit-line-all");
    if (chkAll) {
      chkAll.checked = user.line_notify_all !== false;
    }

    editModal.classList.remove("hidden");
  }

  // 編輯彈窗中的角色變更
  const editSelectRole = $("select-edit-role");
  if (editSelectRole) {
    editSelectRole.addEventListener("change", () => {
      const groupMgr = $("group-edit-manager");
      if (groupMgr) {
        if (editSelectRole.value === "driver") {
          groupMgr.classList.remove("hidden");
        } else {
          groupMgr.classList.add("hidden");
        }
      }
    });
  }

  // ===== 表單提交 (修改員工資料) =====
  if (editForm) {
    editForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (editErrBox) {
        editErrBox.classList.add("hidden");
        editErrBox.textContent = "";
      }

      const submitBtn = $("btn-submit-edit-modal");
      if (submitBtn) submitBtn.disabled = true;

      const userId = $("inp-edit-user-id").value;
      const displayName = $("inp-edit-name").value.trim();
      const password = $("inp-edit-password").value;
      const isActive = $("select-edit-active").value === "true";
      const lineUserId = $("inp-edit-line-id").value.trim();
      const lineTokenInput = $("inp-edit-line-token").value;
      const lineNotifyEnabled = $("chk-edit-line-enabled").checked;
      const lineNotifyAll = $("chk-edit-line-all") ? $("chk-edit-line-all").checked : true;

      const payload = {
        display_name: displayName,
        is_active: isActive,
        line_user_id: lineUserId || "",
        line_notify_enabled: lineNotifyEnabled,
      };

      if (password) {
        payload.password = password;
      }

      if (currentRole === "super_admin") {
        if ($("select-edit-role") && !$("select-edit-role").disabled) {
          payload.role = $("select-edit-role").value;
        }
        if (payload.role === "driver" || !payload.role) {
          payload.manager_id = $("select-edit-manager") ? $("select-edit-manager").value : null;
        } else {
          payload.manager_id = null;
        }
        payload.line_notify_all = lineNotifyAll;

        // 若輸入框留空，代表不更動 token；若輸入空格則表示清空
        if (lineTokenInput === "") {
          payload.line_token = "__UNCHANGED__";
        } else {
          payload.line_token = lineTokenInput.trim();
        }
      }

      try {
        const res = await fetch(`/api/admin/users/${userId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.message || "更新使用者資料失敗");
        }

        showActionMsg(data.message || "成功更新使用者資料", "success");
        closeEditModal();
        loadUsers();
      } catch (err) {
        if (editErrBox) {
          editErrBox.textContent = err.message;
          editErrBox.classList.remove("hidden");
        }
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  }

  // 切換到 manage 分頁時自動重新載入
  window.addEventListener("popstate", () => {
    if (location.pathname.includes("/dashboard/manage")) {
      loadUsers();
    }
  });

  const manageLink = document.querySelector('.dash-bookmark [dash-page="manage"]');
  if (manageLink) {
    manageLink.addEventListener("click", () => {
      setTimeout(loadUsers, 50);
    });
  }

  // 初始載入
  loadUsers();
})();
