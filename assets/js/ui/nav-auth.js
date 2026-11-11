(function () {
  "use strict";

  const roleLabels = {
    developer: "開發者",
    admin: "管理員",
    driver: "駕駛",
    employee: "員工",
  };

  async function updateNav() {
    try {
      const res = await fetch("/api/auth/me");
      if (!res.ok) return;

      const me = await res.json();
      const navRgts = document.querySelectorAll(".nav-rgt");

      navRgts.forEach((navRgt) => {
        if (navRgt.closest(".dash-nav-inner")) return;

        if (me.logged_in) {
          const identityText = roleLabels[me.role] || me.role || "";

          let extraLinkHtml = "";
          const currentPath = window.location.pathname;

          if (me.role === "admin" || me.role === "developer") {
            if (!currentPath.startsWith("/dashboard")) {
              extraLinkHtml = `<a class="nav-link-a user-select-none cursor-pointer" href="/dashboard/overview">後台管理</a>`;
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
                window.faceDetectionAuth.clearToken();
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
