(function () {
  "use strict";

  const TOKEN_KEY = "face-detection-auth-token";
  const nativeFetch = window.fetch.bind(window);

  window.faceDetectionAuth = {
    getToken() {
      return window.sessionStorage.getItem(TOKEN_KEY);
    },
    setToken(token) {
      window.sessionStorage.setItem(TOKEN_KEY, token);
    },
    clearToken() {
      window.sessionStorage.removeItem(TOKEN_KEY);
    },
  };

  window.fetch = function (input, init) {
    const url = typeof input === "string" ? input : input.url;
    const token = window.faceDetectionAuth.getToken();
    const headers = new Headers(
      init && init.headers ? init.headers : input instanceof Request ? input.headers : undefined
    );

    const requestUrl = new URL(url, window.location.origin);
    if (
      token &&
      requestUrl.origin === window.location.origin &&
      requestUrl.pathname.startsWith("/api/")
    ) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    return nativeFetch(input, {
      ...(init || {}),
      headers,
    });
  };

  if (window.location.pathname.startsWith("/dashboard")) {
    window.addEventListener("DOMContentLoaded", async () => {
      try {
        const response = await window.fetch("/api/auth/me", { cache: "no-store" });
        const me = await response.json();
        if (!me.logged_in || !["admin", "developer"].includes(me.role)) {
          window.location.replace(me.logged_in ? "/demo" : "/login");
        }
      } catch (error) {
        console.error("Verify account state failed:", error);
        window.location.replace("/login");
      }
    });
  }
})();
