/**
 * nav-auth.js
 * 在所有頁面自動偵測登入狀態，動態更新導覽列右側按鈕：
 * - 未登入 → 保持登入按鈕
 * - 已登入 → 顯示 "Dashboard"（連結到 /dashboard）
 */
(function () {
  "use strict";

  async function updateNav() {
    let me;
    try {
      const res = await fetch("/api/auth/me");
      if (!res.ok) return;
      me = await res.json();
    } catch (_) {
      return;
    }

    if (!me.logged_in) return;

    const signInBtns = document.querySelectorAll('a.nav-link-a[href="/login"]');
    signInBtns.forEach((btn) => {
      btn.textContent = "總覽";
      btn.href = "/dashboard";
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", updateNav);
  } else {
    updateNav();
  }
})();
