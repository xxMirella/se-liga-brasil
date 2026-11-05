/* Progressive enhancement for /pessoas. The page works without this file: the filters are a GET
   form and "Mostrar mais" is a link to the next page. Here a change in any filter (state, role,
   party, sort) refreshes the list in place, and "Mostrar mais 24" appends the next people to the
   list instead of replacing it. Plain JavaScript, no dependencies. */
(() => {
  "use strict";

  const PEOPLE_PATH = "/pessoas";
  const FORM_ID = "people-search";
  const LIST_SELECTOR = ".ds-people-list";
  const MORE_SELECTOR = "[data-people-more]";
  const PAGINATION_SELECTOR = ".ds-people-pagination";
  const COUNT_SELECTOR = ".ds-people-summary__count";
  const ITEM_SELECTOR = ".ds-people-item";
  const UPDATING_CLASS = "ds-is-updating";

  let pendingRequest = null;
  // path + query on screen: a popstate that only changes the #fragment is not a new search
  let shownKey = window.location.pathname + window.location.search;

  function mainElement() {
    return document.getElementById("main");
  }

  async function fetchPage(url, signal) {
    const response = await fetch(url.pathname + url.search, {
      headers: { Accept: "text/html" }, signal,
    });
    const isHtml = (response.headers.get("Content-Type") || "").includes("text/html");
    if (!response.ok || !isHtml) throw new Error("unexpected response");
    const page = new DOMParser().parseFromString(await response.text(), "text/html");
    if (!page.getElementById("main")) throw new Error("page without main region");
    return page;
  }

  function urlFromForm(form) {
    const url = new URL(form.action, window.location.href);
    new FormData(form).forEach((value, key) => {
      if (typeof value === "string" && value !== "") url.searchParams.append(key, value);
    });
    return url;
  }

  function isPeopleSearchUrl(url) {
    return url.origin === window.location.origin && url.pathname === PEOPLE_PATH;
  }

  function restoreFocus(name) {
    if (!name) return;
    const escaped = CSS.escape(name);
    const control = mainElement()
      .querySelector(`[name="${escaped}"]:checked, select[name="${escaped}"]`);
    if (control) control.focus({ preventScroll: true });
  }

  async function withBusyMain(task) {
    if (pendingRequest) pendingRequest.abort();
    const request = new AbortController();
    pendingRequest = request;
    const main = mainElement();
    main.classList.add(UPDATING_CLASS);
    main.setAttribute("aria-busy", "true");
    try {
      await task(request.signal);
    } finally {
      if (pendingRequest === request) {
        pendingRequest = null;
        main.classList.remove(UPDATING_CLASS);
        main.removeAttribute("aria-busy");
      }
    }
  }

  // Replaces the whole results page (filters included) so every control reflects the new URL.
  async function showSearch(url, { push = true, focusName = null } = {}) {
    try {
      await withBusyMain(async (signal) => {
        const page = await fetchPage(url, signal);
        mainElement().replaceChildren(...page.getElementById("main").childNodes);
        document.title = page.title;
        if (push) history.pushState({ people: true }, "", url.pathname + url.search);
        shownKey = url.pathname + url.search;
        restoreFocus(focusName);
      });
    } catch (error) {
      if (error.name !== "AbortError") window.location.assign(url.href);
    }
  }

  function updateCount() {
    const count = mainElement().querySelectorAll(`${LIST_SELECTOR} ${ITEM_SELECTOR}`).length;
    const status = mainElement().querySelector(COUNT_SELECTOR);
    if (status) status.textContent = `Mostrando ${count} ${count === 1 ? "pessoa" : "pessoas"}`;
  }

  function replacePagination(page) {
    const current = mainElement().querySelector(PAGINATION_SELECTOR);
    const next = page.querySelector(PAGINATION_SELECTOR);
    if (current && next) current.replaceWith(next);
    else if (current) current.remove();
  }

  // Appends the next page of people; the URL stays the same, so a reload starts from the top.
  async function showMore(link) {
    const url = new URL(link.href, window.location.href);
    try {
      await withBusyMain(async (signal) => {
        const page = await fetchPage(url, signal);
        const list = mainElement().querySelector(LIST_SELECTOR);
        const previousCount = list.querySelectorAll(ITEM_SELECTOR).length;
        list.append(...page.querySelectorAll(`${LIST_SELECTOR} ${ITEM_SELECTOR}`));
        replacePagination(page);
        updateCount();
        const firstNew = list.querySelectorAll(ITEM_SELECTOR)[previousCount];
        if (firstNew) firstNew.querySelector("a")?.focus({ preventScroll: true });
      });
    } catch (error) {
      if (error.name !== "AbortError") window.location.assign(url.href);
    }
  }

  document.addEventListener("change", (event) => {
    const form = event.target.closest(`#${FORM_ID}`);
    if (!form || !event.target.name) return;
    showSearch(urlFromForm(form), { focusName: event.target.name });
  });

  document.addEventListener("submit", (event) => {
    if (event.target.id !== FORM_ID) return;
    event.preventDefault();
    showSearch(urlFromForm(event.target));
  });

  document.addEventListener("click", (event) => {
    const isPlainLeftClick = event.button === 0 && !event.metaKey && !event.ctrlKey
      && !event.shiftKey && !event.altKey;
    const link = event.target.closest("a[href]");
    if (event.defaultPrevented || !isPlainLeftClick || !link || link.target) return;
    if (link.matches(MORE_SELECTOR)) {
      event.preventDefault();
      showMore(link);
      return;
    }
    const url = new URL(link.href, window.location.href);
    if (isPeopleSearchUrl(url) && url.hash === "" && link.closest("#main")) {
      event.preventDefault();
      showSearch(url);
    }
  });

  window.addEventListener("popstate", () => {
    const key = window.location.pathname + window.location.search;
    if (window.location.pathname === PEOPLE_PATH && key !== shownKey) {
      showSearch(new URL(window.location.href), { push: false });
    }
  });
})();
