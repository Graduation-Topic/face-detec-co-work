/**
 * manage-users.js — 後台「員工管理」模組 (RBAC 角色管理)
 * 支援：開發者 (可檢視/建立所有人員與管理員) 與 一般管理員 (僅檢視/建立自己名下的駕駛)
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
    if (role === "developer") {
      return '<span class="role-badge role-badge-developer">開發者</span>';
    }
    if (role === "admin") {
      return '<span class="role-badge role-badge-admin">管理員</span>';
    }
    return '<span class="role-badge role-badge-driver">駕駛</span>';
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

  // ===== 載入管理員清單 (供開發者指派所屬主管) =====
  async function loadManagers() {
    if (currentRole !== "developer") return;
    try {
      const res = await fetch("/api/admin/managers");
      if (!res.ok) return;
      const data = await res.json();
      allManagers = data.managers || [];

      const selectMgr = $("select-new-manager");
      if (selectMgr) {
        selectMgr.innerHTML = '<option value="">無</option>';
        allManagers.forEach((m) => {
          const opt = document.createElement("option");
          opt.value = m.id;
          opt.textContent = `${m.display_name || m.username} (${m.role === "developer" ? "開發者" : "管理員"})`;
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

    if (currentRole === "developer") {
      if (groupRole) groupRole.classList.remove("hidden");
      if (groupManager) groupManager.classList.remove("hidden");
      loadManagers();
    } else {
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
          currentRole === "developer"
            ? !isSelf
            : u.role === "driver" && u.manager_id === currentUserId;

        const actionBtn = canDelete
          ? `<button type="button" class="btn-user-delete cursor-pointer" data-id="${u.id}" data-name="${u.display_name || u.username}" aria-label="刪除 ${u.display_name || u.username}" title="刪除">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path fill-rule="evenodd" clip-rule="evenodd" d="M21 5h-5v-.25A2.755 2.755 0 0 0 13.25 2h-2.5A2.755 2.755 0 0 0 8 4.75V5H3v1.5h1v12.75A2.755 2.755 0 0 0 6.75 22h10.5A2.755 2.755 0 0 0 20 19.25V6.5h1V5ZM9.5 4.75c0-.69.56-1.25 1.25-1.25h2.5c.69 0 1.25.56 1.25 1.25V5h-5v-.25Zm9 14.5c0 .69-.56 1.25-1.25 1.25H6.75c-.69 0-1.25-.56-1.25-1.25V6.5h13v12.75Zm-8-9.75H9v8h1.5v-8Zm3 0H15v8h-1.5v-8Z" fill="#ff453a"/>
              </svg>
            </button>`
          : '<span style="color:var(--color-text-muted);font-size:12px;">—</span>';

        return `
          <tr>
            <td class="manage-user-id">${u.id}</td>
            <td class="manage-username"><strong>${u.username}</strong></td>
            <td class="manage-display-name">${u.display_name || "—"}</td>
            <td class="manage-role">${getRoleBadge(u.role)}</td>
            <td class="manage-manager">${u.manager_name || "—"}</td>
            <td class="manage-created-at">${formatTime(u.created_at)}</td>
            <td class="manage-actions">${actionBtn}</td>
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
    if (!confirm(`確定刪除帳號「${name}」(ID: ${id})？`)) {
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

  const manageLink = document.querySelector(
    '.dash-bookmark [dash-page="manage"]',
  );
  if (manageLink) {
    manageLink.addEventListener("click", () => {
      setTimeout(loadUsers, 50);
    });
  }

  // 初始載入
  loadUsers();
})();
