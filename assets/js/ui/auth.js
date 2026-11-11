const form = document.getElementById("login-form");
const errEl = document.getElementById("login-error");
const btnLbl = document.getElementById("btn-label");
const btnSpin = document.getElementById("btn-spinner");
const btn = document.getElementById("btn-login");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errEl.classList.add("hidden");
  btn.disabled = true;
  btnLbl.classList.add("hidden");
  btnSpin.classList.remove("hidden");

  const username = document.getElementById("inp-username").value.trim();
  const password = document.getElementById("inp-password").value;

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();

    if (res.ok && data.status === "ok") {
      if (data.role === "admin" || data.role === "developer") {
        window.location.href = "/dashboard/overview";
      } else {
        window.location.href = "/demo";
      }
    } else {
      errEl.textContent = data.message || "帳號或密碼錯誤";
      errEl.classList.remove("hidden");
      btn.disabled = false;
      btnLbl.classList.remove("hidden");
      btnSpin.classList.add("hidden");
    }
  } catch (err) {
    errEl.textContent = "網路錯誤，請稍後再試";
    errEl.classList.remove("hidden");
    btn.disabled = false;
    btnLbl.classList.remove("hidden");
    btnSpin.classList.add("hidden");
  }
});
