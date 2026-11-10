(function () {
  "use strict";

  const roleLabels = {
    super_admin: "總管理員",
    admin: "車隊管理員",
    driver: "駕駛員",
    employee: "員工",
  };

  async function updateNav() {
    try {
      const res = await fetch("/api/auth/me");
      if (!res.ok) return;

      const me = await res.json();
      const navRgts = document.querySelectorAll(".nav-rgt");

      navRgts.forEach((navRgt) => {
        // 若為儀表板頁面自身管理的導航欄，則不重複處理
        if (navRgt.closest(".dash-nav-inner")) return;

        if (me.logged_in) {
          const roleTag = roleLabels[me.role] ? ` (${roleLabels[me.role]})` : "";
          const identityText = (me.display_name || me.username) + roleTag;

          let extraLinkHtml = "";
          const currentPath = window.location.pathname;

          if (me.role === "admin" || me.role === "super_admin") {
            if (!currentPath.startsWith("/dashboard")) {
              extraLinkHtml = `<a class="nav-link-a user-select-none cursor-pointer" href="/dashboard/overview">管理後台</a>`;
            }
          } else {
            if (!currentPath.startsWith("/demo")) {
              extraLinkHtml = `<a class="nav-link-a user-select-none cursor-pointer" href="/demo">測試版</a>`;
            }
          }

          navRgt.innerHTML = `
            <span class="access-identity user-select-none">${identityText}</span>
            ${extraLinkHtml}
            <a id="btn-logout" class="nav-link-a cursor-pointer user-select-none btn-nav-logout" href="/logout">登出</a>
          `;

          const logoutBtn = navRgt.querySelector(".btn-nav-logout");
          if (logoutBtn) {
            logoutBtn.addEventListener("click", async (e) => {
              e.preventDefault();
              try {
                await fetch("/api/auth/logout", { method: "POST" });
              } catch (err) {
                console.error("Logout request failed: ", err);
              }
              window.location.href = "/login";
            });
          }
        } else {
          navRgt.innerHTML = `
            <a class="nav-link-a user-select-none cursor-pointer" href="/login">登入</a>
          `;
        }
      });
    } catch (error) {
      console.error("Fetch account state error: ", error);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", updateNav);
  } else {
    updateNav();
  }
})();
