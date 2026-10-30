document.addEventListener("click", (e) => {
  const btn = e.target.closest(".copy-text-button");
  if (!btn) return;

  const text = btn
    .closest(".copy-code-0")
    ?.querySelector("code")
    ?.innerText.trim();
  navigator.clipboard.writeText(text).then(() => {
    btn.classList.add("copied");
    setTimeout(() => btn.classList.remove("copied"), 2000);
  });
});
