/* Progressive enhancement for /panorama. The page works without this file: every control is a
   link whose URL carries the state. Here those links update the page in place (no reload, no
   jump to the top). Plain JavaScript, no dependencies. */
(() => {
  "use strict";

  const PANORAMA_PATH = "/panorama";
  const MAIN_ID = "main";
  const UPDATING_CLASS = "ds-is-updating";
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  let pendingRequest = null;
  // path + query on screen: a popstate that only changes the #fragment is not a new page
  let shownKey = window.location.pathname + window.location.search;

  function mainElement() {
    return document.getElementById(MAIN_ID);
  }

  function isPlainLeftClick(event) {
    return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey
      && !event.altKey;
  }

  function panoramaLinkFor(event) {
    if (event.defaultPrevented || !isPlainLeftClick(event)) return null;
    const link = event.target.closest("a[href]");
    if (!link || link.target || link.hasAttribute("download")) return null;
    const url = new URL(link.href, window.location.href);
    const isPanorama = url.origin === window.location.origin && url.pathname === PANORAMA_PATH;
    const isSamePageAnchor = url.search === window.location.search && url.hash !== "";
    return isPanorama && !isSamePageAnchor ? { link, url } : null;
  }

  async function fetchMain(url, signal) {
    const response = await fetch(url.pathname + url.search, {
      headers: { Accept: "text/html" }, signal,
    });
    const isHtml = (response.headers.get("Content-Type") || "").includes("text/html");
    if (!response.ok || !isHtml) throw new Error("unexpected response");
    const next = new DOMParser().parseFromString(await response.text(), "text/html");
    if (!next.getElementById(MAIN_ID)) throw new Error("page without main region");
    return next;
  }

  // The clicked link is replaced by the swap, so decide before it whether the click came from
  // inside the section its fragment names (stay where we are) or from outside it (scroll there).
  function fragmentIdToScrollTo(link, hash) {
    if (!hash) return null;
    const id = decodeURIComponent(hash.slice(1));
    const target = document.getElementById(id);
    return target && !target.contains(link) ? id : null;
  }

  function restoreFocus(link) {
    const href = link.getAttribute("href");
    const replacement = mainElement().querySelector(`a[href="${CSS.escape(href)}"]`);
    if (replacement) replacement.focus({ preventScroll: true });
  }

  function swapContent(next) {
    mainElement().replaceChildren(...next.getElementById(MAIN_ID).childNodes);
    document.title = next.title;
    document.dispatchEvent(new CustomEvent("ds:content-replaced"));
  }

  async function navigate(url, { link = null, push = true } = {}) {
    if (pendingRequest) pendingRequest.abort();
    const request = new AbortController();
    pendingRequest = request;
    const main = mainElement();
    main.classList.add(UPDATING_CLASS);
    main.setAttribute("aria-busy", "true");
    try {
      const next = await fetchMain(url, request.signal);
      const scrollTargetId = link ? fragmentIdToScrollTo(link, url.hash) : null;
      swapContent(next);
      if (push) history.pushState({ panorama: true }, "", url.pathname + url.search + url.hash);
      shownKey = url.pathname + url.search;
      if (link) restoreFocus(link);
      const target = scrollTargetId && document.getElementById(scrollTargetId);
      if (target) {
        target.scrollIntoView({ behavior: prefersReducedMotion.matches ? "auto" : "smooth" });
      }
    } catch (error) {
      if (error.name === "AbortError") return;
      window.location.assign(url.href);
    } finally {
      if (pendingRequest === request) {
        pendingRequest = null;
        main.classList.remove(UPDATING_CLASS);
        main.removeAttribute("aria-busy");
      }
    }
  }

  document.addEventListener("click", (event) => {
    const match = panoramaLinkFor(event);
    if (!match) return;
    event.preventDefault();
    navigate(match.url, { link: match.link });
  });

  window.addEventListener("popstate", () => {
    const key = window.location.pathname + window.location.search;
    if (window.location.pathname === PANORAMA_PATH && key !== shownKey) {
      navigate(new URL(window.location.href), { push: false });
    }
  });

})();
