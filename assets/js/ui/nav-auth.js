(function () {
  "use strict";

  const signInBtns = document.querySelectorAll('a.nav-link-a[href="/login"]');

  signInBtns.forEach((btn) => {
    btn.style.visibility = "hidden";
  });

  async function updateNav() {
    try {
      const res = await fetch("/api/auth/me");

      if (!res.ok) return;

      const me = await res.json();

      if (me.logged_in) {
        signInBtns.forEach((btn) => {
          if (me.role === "admin" || me.role === "super_admin") {
            btn.textContent = "總覽";
            btn.href = "/dashboard/overview";
          } else {
            btn.textContent = "測試版";
            btn.href = "/demo";
          }
        });
      }
    } catch (error) {
      console.error("Fetch account state error: ", error);
    } finally {
      signInBtns.forEach((btn) => {
        btn.style.visibility = "visible";
      });
    }
  }

  updateNav();
})();
