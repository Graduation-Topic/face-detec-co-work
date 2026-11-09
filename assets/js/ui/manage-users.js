/**
 * manage-users.js — 後台「員工管理」模組 (RBAC 角色管理)
 * 支援：總管理員 (可檢視/建立所有人員與一般管理員) 與 一般管理員 (僅檢視/建立自己名下的駕駛員)
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
      return '<span class="role-badge role-badge-admin">管理員</span>';
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
        tbody.innerHTML = `<tr><td colspan="7" class="table-empty" style="color:var(--color-danger)!important">載入失敗: ${err.message}</td></tr>`;
      }
    }
  }

  // ===== 載入管理員清單 (供總管理員指派所屬主管) =====
  async function loadManagers() {
    if (currentRole !== "super_admin") return;
    try {
      const res = await fetch("/api/admin/managers");
      if (!res.ok) return;
      const data = await res.json();
      allManagers = data.managers || [];

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
        '<tr><td colspan="7" class="table-empty">目前無符合條件的員工紀錄</td></tr>';
      return;
    }

    tbody.innerHTML = users
      .map((u) => {
        const isSelf = u.id === currentUserId;
        const canDelete =
          currentRole === "super_admin"
            ? !isSelf
            : u.role === "driver" && u.manager_id === currentUserId;

        const actionBtn = canDelete
          ? `<button class="btn-user-delete cursor-pointer" data-id="${u.id}" data-name="${u.display_name || u.username}">刪除</button>`
          : '<span style="color:var(--color-text-muted);font-size:12px;">—</span>';

        return `
          <tr>
            <td>${u.id}</td>
            <td><strong>${u.username}</strong></td>
            <td>${u.display_name || "—"}</td>
            <td>${getRoleBadge(u.role)}</td>
            <td>${u.manager_name || "—"}</td>
            <td>${formatTime(u.created_at)}</td>
            <td>${actionBtn}</td>
          </tr>
        `;
      })
      .join("");

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

  // ===== Modal 開關邏輯 =====
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

