const dashLinks = document.querySelectorAll(".dash-bookmark [dash-page]");
const dashPages = document.querySelectorAll("[dash-page].dash-main");

const getPage = () => {
  const path = location.pathname;
  const page = path.split("/").filter(Boolean).pop() || "overview";
  return page === "setting" ? "settings" : page;
};

function switchDashboardPage(page) {
  dashPages.forEach((section) => {
    const isActive = section.getAttribute("dash-page") === page;
    section.hidden = !isActive;
    section.classList.toggle("active", isActive);
  });

  dashLinks.forEach((link) => {
    link.classList.toggle("active", link.getAttribute("dash-page") === page);
  });
}

dashLinks.forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();

    const page = link.getAttribute("dash-page");
    const newUrl = link.getAttribute("href");

    if (location.pathname === newUrl) return;

    history.pushState(null, "", newUrl);
    switchDashboardPage(page);
  });
});

window.addEventListener("popstate", () => {
  switchDashboardPage(getPage());
});

switchDashboardPage(getPage());
