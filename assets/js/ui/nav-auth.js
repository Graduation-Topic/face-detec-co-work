/**
 * nav-auth.js
 * 在所有頁面自動偵測登入狀態，動態更新導覽列右側按鈕：
 * - 未登入 → 顯示 "Sign in"（原樣）
 * - 已登入 admin → 顯示 "Dashboard"（連結到 /dashboard）
 */
(function () {
  'use strict';

  async function updateNav() {
    let me;
    try {
      const res = await fetch('/api/auth/me');
      if (!res.ok) return;
      me = await res.json();
    } catch (_) {
      return; // 網路失敗，保持原樣
    }

    if (!me.logged_in) return; // 未登入，不需修改

    // 找到所有導覽列右側「Sign in」按鈕（href="/login"）
    const signInBtns = document.querySelectorAll('a.app-nav-link-button-s-1[href="/login"]');
    signInBtns.forEach(btn => {
      if (me.role === 'admin') {
        btn.textContent = 'Dashboard';
        btn.href = '/dashboard';
      } else {
        // 一般使用者：改為指向 demo 或隱藏
        btn.textContent = 'Demo';
        btn.href = '/demo';
      }
    });
  }

  // DOM 解析完成後執行（defer 情境下 DOMContentLoaded 通常已觸發，直接執行亦可）
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', updateNav);
  } else {
    updateNav();
  }
})();

