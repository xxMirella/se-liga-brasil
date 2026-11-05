/* Progressive enhancement for the "Atuação no cargo" section of a person profile. Without this
   file the page already lists every record and the category counts; here the counts become
   filter buttons, a search box narrows the list and the list is shown eight items at a time.
   Plain JavaScript, no dependencies; the counts and records always come from the server. */
(() => {
  "use strict";

  const section = document.getElementById("atuacao");
  if (!section || !section.querySelector(".ds-profile-feed")) return;

  const PAGE_SIZE = Number(section.dataset.pageSize) || 8;
  const cards = Array.from(section.querySelectorAll(".ds-profile-category"));
  const articles = Array.from(section.querySelectorAll("article.monthly-proposition"));
  const groups = Array.from(section.querySelectorAll(".timeline-group"));
  const search = section.querySelector(".ds-profile-search");
  const input = search && search.querySelector("input");
  const status = section.querySelector(".ds-profile-status");
  const more = section.querySelector(".ds-profile-show-more");
  const moreButton = more && more.querySelector("button");

  const state = { category: "todos", query: "", limit: PAGE_SIZE };

  const normalize = (value) =>
    value.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const searchable = articles.map((article) => normalize(article.textContent));

  function matches(index) {
    const categories = (articles[index].dataset.category || "").split(" ");
    const inCategory = state.category === "todos" || categories.includes(state.category);
    return inCategory && (!state.query || searchable[index].includes(state.query));
  }

  function render() {
    let matched = 0;
    let shown = 0;
    articles.forEach((article, index) => {
      const visible = matches(index) && matched++ < state.limit;
      article.hidden = !visible;
      const dialog = article.nextElementSibling;
      if (dialog && dialog.tagName === "DIALOG" && !visible) dialog.close();
      if (visible) shown++;
    });
    const total = articles.filter((_, index) => matches(index)).length;
    groups.forEach((group) => {
      group.hidden = !group.querySelector("article.monthly-proposition:not([hidden])");
    });
    cards.forEach((card) => card.setAttribute("aria-pressed", String(card.dataset.category === state.category)));
    if (status) status.textContent = `Mostrando ${shown} de ${total}`;
    if (more) more.hidden = shown >= total;
  }

  function select(category) {
    state.category = category;
    state.limit = PAGE_SIZE;
    render();
  }

  cards.forEach((card) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = card.className;
    button.dataset.category = card.dataset.category;
    button.append(...card.childNodes);
    button.addEventListener("click", () => select(card.dataset.category));
    card.replaceWith(button);
    cards[cards.indexOf(card)] = button;
  });

  if (search && input) {
    search.hidden = false;
    input.addEventListener("input", () => {
      state.query = normalize(input.value.trim());
      state.limit = PAGE_SIZE;
      render();
    });
  }
  if (moreButton) {
    moreButton.addEventListener("click", () => {
      state.limit += PAGE_SIZE;
      render();
    });
  }
  render();
})();
