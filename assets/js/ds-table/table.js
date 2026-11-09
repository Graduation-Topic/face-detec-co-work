const $ = (id) => document.getElementById(id);

function showMsg(text, type) {
  const el = $("action-msg");
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
  return date.toLocaleString("zh-TW", {
    hour12: false,
  });
}

function shortId(sid) {
  if (!sid) return "—";
  return sid.length > 14 ? sid.slice(0, 14) + "…" : sid;
}

  async function loadData() {
  const limit = $("limit-select").value;
  try {
    const res = await fetch(`/api/admin/alerts?limit=${limit}`);
    if (res.status === 401) {
      window.location.href = "/login";
      return;
    }
    if (!res.ok) {
      throw new Error("警告事件查詢失敗");
    }
    const data = await res.json();

    const st = data.status || {};
    $("stat-window-count").textContent = st.window_count ?? "—";
    $("stat-window-threshold").textContent =
      `門檻：${st.trigger_count ?? "—"} 次 / ${Math.round((st.window_sec ?? 300) / 60)} 分鐘`;

    const isEsc = !!st.is_escalated;
    $("stat-escalated").textContent = isEsc ? "已升級" : "正常";
    $("escalation-card").classList.toggle("stat-card-escalated", isEsc);
    $("stat-escalated-sub").textContent = isEsc
      ? "已超過門檻，請關注"
      : "目前無異常升級";

    try {
      const cfg = await fetch("/api/config").then((r) => r.json());
      $("stat-retention").textContent = `${cfg.ALERT_RETENTION_DAYS} 天`;
      $("stat-max-records").textContent = cfg.ALERT_MAX_DB_RECORDS;
    } catch (_) {}

    const alerts = data.recent_alerts || [];
    $("stat-total-db").textContent = alerts.length;
    const tbody = $("alert-tbody");

    if (!alerts.length) {
      tbody.innerHTML =
        '<tr><td colspan="7" class="table-empty">目前沒有警告事件紀錄</td></tr>';
      return;
    }

    tbody.innerHTML = alerts
      .map(
        (a) => `
        <tr class="${a.is_new_escalation ? "row-escalated" : ""}">
          <td>${a.id}</td>
          <td>${formatTime(a.created_at)}</td>
          <td title="${a.session_id || ""}">${shortId(a.session_id)}</td>
          <td>${a.reason || "—"}</td>
          <td>${a.score != null ? a.score.toFixed(1) : "—"}</td>
          <td>${a.window_count ?? "—"}</td>
          <td class="${a.is_escalated ? "cell-danger" : "cell-ok"}">
            ${a.is_escalated ? "是" : "正常"}
          </td>
        </tr>
      `,
      )
      .join("");
  } catch (err) {
    showMsg("載入失敗：" + err.message, "error");
  }
}

$("btn-refresh").addEventListener("click", loadData);
$("limit-select").addEventListener("change", loadData);

$("btn-reset").addEventListener("click", async () => {
  if (!confirm("確定要重置警報視窗計數？\n（資料庫紀錄不會刪除）")) return;
  const res = await fetch("/api/admin/alerts/reset", { method: "POST" });
  if (res.status === 401) {
    window.location.href = "/login";
    return;
  }
  const d = await res.json();
  showMsg(d.message || "已重置", "info");
  loadData();
});

$("btn-purge").addEventListener("click", async () => {
  if (
    !confirm(
      "確定要清理過期警告資料？\n超過保留天數的記錄將被永久刪除，此操作無法還原。",
    )
  )
    return;
  const res = await fetch("/api/admin/alerts/purge", { method: "POST" });
  if (res.status === 401) {
    window.location.href = "/login";
    return;
  }
  const d = await res.json();
  showMsg(
    d.message || "清理完成",
    d.status === "success" ? "success" : "error",
  );
  loadData();
});

$("btn-logout").addEventListener("click", async (event) => {
  event.preventDefault();
  await fetch("/api/auth/logout", { method: "POST" });
  window.location.href = "/login";
});

(async () => {
  try {
    const res = await fetch("/api/auth/me");
    const me = await res.json();

    if (!res.ok || !me.logged_in || !["admin", "super_admin"].includes(me.role)) {
      window.location.href = "/login";
      return;
    }

    const roleTag = me.role === "super_admin" ? " (總管理員)" : " (管理員)";
    $("access-identity").textContent = (me.display_name || me.username) + roleTag;
    await loadData();
    document.body.classList.remove("dashboard-loading");
    setInterval(loadData, 30000);
  } catch (err) {
    showMsg("載入失敗：" + err.message, "error");
    document.body.classList.remove("dashboard-loading");
  }
})();
