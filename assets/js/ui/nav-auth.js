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
      btn.href = "/dashboard/overview";
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", updateNav);
  } else {
    updateNav();
  }
})();
