const docLinks = document.querySelectorAll(".doc-bookmark [data-doc]");
const docPages = document.querySelectorAll("[data-doc-page]");

const getPage = () =>
  new URLSearchParams(location.search).get("doc") || "intro";

function switchDoc(page) {
  docPages.forEach((section) => {
    const isActive = section.dataset.docPage === page;
    section.hidden = !isActive;
    section.classList.toggle("active", isActive);
  });

  docLinks.forEach((link) => {
    link.classList.toggle("active", link.dataset.doc === page);
  });
}

docLinks.forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    const page = link.dataset.doc;
    if (page === getPage()) return;
    history.pushState(null, "", `?doc=${page}`);
    switchDoc(page);
  });
});

window.addEventListener("popstate", () => switchDoc(getPage()));
switchDoc(getPage());
