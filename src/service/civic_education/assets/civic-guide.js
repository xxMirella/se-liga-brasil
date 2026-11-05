/* Behaviour of the civic guide on top of plain links. Everything works without this file; here
   (1) the sphere buttons update the guide in place instead of reloading and jumping to an anchor,
   (2) links that only reveal something (definitions, answers via :target) keep the scroll
   position instead of scrolling to the revealed element, and (3) the four-step index fills as
   the reader moves through the steps. Plain JavaScript, no dependencies. */
(() => {
  "use strict";

  const GUIDE_PATH = "/como-funciona";
  const MAIN_ID = "main";
  const STEP_COUNT = 4;
  const READING_LINE_RATIO = 0.4;
  const END_TOLERANCE_PX = 4;
  const BAR_SELECTOR = ".ds-civic-stepper__bar";
  const LINK_SELECTOR = ".ds-civic-stepper__link";
  const PROGRESS_PROPERTY = "--step-progress";
  const UPDATING_CLASS = "ds-is-updating";
  const CONTENT_REPLACED_EVENT = "ds:content-replaced";
  // Panels opened by an in-page link; without this script the same links open them via :target.
  const REVEAL_PANEL_SELECTOR = ".ds-civic-law__term-panel, .ds-civic-law__feedback";
  const OPEN_CLASS = "is-open";

  let isUpdateScheduled = false;
  let pendingRequest = null;
  let scrollToRestore = null;
  // path + query of the guide on screen: a popstate that only changes the #fragment is not a new page
  let shownKey = window.location.pathname + window.location.search;

  function mainElement() {
    return document.getElementById(MAIN_ID);
  }

  function clamp(value) {
    return Math.min(1, Math.max(0, value));
  }

  // Resolved on every update: the guide's content is replaced when the sphere changes.
  function findSteps() {
    return Array.from({ length: STEP_COUNT }, (_, index) => ({
      section: document.getElementById(`passo-${index + 1}`),
      link: document.querySelector(`${LINK_SELECTOR}[href="#passo-${index + 1}"]`),
    })).filter((step) => step.section && step.link);
  }

  // Fraction of the step already read: how far the reading line has travelled through it.
  function readProgress(section) {
    const { top, height } = section.getBoundingClientRect();
    const readingLine = window.innerHeight * READING_LINE_RATIO;
    return height > 0 ? clamp((readingLine - top) / height) : 0;
  }

  function currentStepIndex(progressByStep) {
    const reading = progressByStep.findIndex((progress) => progress > 0 && progress < 1);
    if (reading !== -1) return reading;
    const finished = progressByStep.filter((progress) => progress === 1).length;
    return finished > 0 ? finished - 1 : -1;
  }

  // At the very bottom the reading line cannot go further, so the last step counts as finished.
  function hasReachedPageEnd() {
    const scrolled = window.scrollY + window.innerHeight;
    return scrolled >= document.documentElement.scrollHeight - END_TOLERANCE_PX;
  }

  function updateProgress() {
    isUpdateScheduled = false;
    const steps = findSteps();
    if (steps.length !== STEP_COUNT) return;
    const progressByStep = steps.map((step) => readProgress(step.section));
    if (hasReachedPageEnd()) progressByStep[progressByStep.length - 1] = 1;
    const current = currentStepIndex(progressByStep);
    steps.forEach((step, index) => {
      step.link.querySelector(BAR_SELECTOR)
        .style.setProperty(PROGRESS_PROPERTY, progressByStep[index].toFixed(3));
      if (index === current) step.link.setAttribute("aria-current", "step");
      else step.link.removeAttribute("aria-current");
    });
  }

  function scheduleProgressUpdate() {
    if (isUpdateScheduled) return;
    isUpdateScheduled = true;
    window.requestAnimationFrame(updateProgress);
  }

  function isPlainLeftClick(event) {
    return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey
      && !event.altKey;
  }

  // Only links that choose another sphere; in-page anchors resolve to the current URL and must not.
  function guideUrlOf(link) {
    const href = link.getAttribute("href");
    if (href.startsWith("#")) return null;
    const url = new URL(href, window.location.href);
    const isGuide = url.origin === window.location.origin && url.pathname === GUIDE_PATH;
    return isGuide && url.search !== "" ? url : null;
  }

  async function fetchGuide(url, signal) {
    const response = await fetch(url.pathname + url.search, {
      headers: { Accept: "text/html" }, signal,
    });
    const isHtml = (response.headers.get("Content-Type") || "").includes("text/html");
    if (!response.ok || !isHtml) throw new Error("unexpected response");
    const page = new DOMParser().parseFromString(await response.text(), "text/html");
    if (!page.getElementById(MAIN_ID)) throw new Error("page without main region");
    return page;
  }

  function restoreFocus(href) {
    const replacement = mainElement().querySelector(`a[href="${CSS.escape(href)}"]`);
    if (replacement) replacement.focus({ preventScroll: true });
  }

  // Replaces the guide for another sphere without moving the reader: no fragment scroll.
  async function showSphere(url, { link = null, push = true } = {}) {
    if (pendingRequest) pendingRequest.abort();
    const request = new AbortController();
    pendingRequest = request;
    const main = mainElement();
    main.classList.add(UPDATING_CLASS);
    main.setAttribute("aria-busy", "true");
    try {
      const page = await fetchGuide(url, request.signal);
      main.replaceChildren(...page.getElementById(MAIN_ID).childNodes);
      document.title = page.title;
      if (push) history.pushState({ civic: true }, "", url.pathname + url.search + url.hash);
      shownKey = url.pathname + url.search;
      if (link) restoreFocus(link.getAttribute("href"));
      document.dispatchEvent(new CustomEvent(CONTENT_REPLACED_EVENT));
      scheduleProgressUpdate();
    } catch (error) {
      if (error.name !== "AbortError") window.location.assign(url.href);
    } finally {
      if (pendingRequest === request) {
        pendingRequest = null;
        main.classList.remove(UPDATING_CLASS);
        main.removeAttribute("aria-busy");
      }
    }
  }

  // Opens the panel a link points to, closing the others of its kind, without navigating: a
  // fragment navigation would scroll the page, which is the jump this avoids.
  function openRevealPanel(link) {
    const id = (link.getAttribute("href") || "").slice(1);
    const panel = id ? document.getElementById(id) : null;
    if (!panel || !panel.matches(REVEAL_PANEL_SELECTOR)) return false;
    const kind = `.${panel.classList[0]}.${OPEN_CLASS}`;
    document.querySelectorAll(kind).forEach((open) => open.classList.remove(OPEN_CLASS));
    panel.classList.add(OPEN_CLASS);
    const check = link.closest(".ds-civic-law__check");
    if (check) check.dataset.chosen = id;
    history.replaceState(window.history.state, "", `#${id}`);
    return true;
  }

  // Other anchors would scroll to their target; remember where the reader is.
  function isRevealOnlyAnchor(link) {
    const href = link.getAttribute("href") || "";
    const isAnchor = href.startsWith("#") && href.length > 1;
    return isAnchor && !link.closest(".ds-civic-stepper") && !link.classList.contains("ds-skip-link");
  }

  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || !isPlainLeftClick(event)) return;
    const link = event.target.closest("a[href]");
    if (!link || link.target) return;
    const sphereUrl = guideUrlOf(link);
    if (sphereUrl) {
      event.preventDefault();
      showSphere(sphereUrl, { link });
    } else if (openRevealPanel(link)) {
      event.preventDefault();
    } else if (isRevealOnlyAnchor(link)) {
      scrollToRestore = window.scrollY;
    }
  });

  // The browser may apply the fragment scroll right away or on its next rendering update, so the
  // position is restored now and again after two frames.
  window.addEventListener("hashchange", () => {
    if (scrollToRestore === null) return;
    const top = scrollToRestore;
    scrollToRestore = null;
    const restore = () => window.scrollTo({ top, behavior: "instant" });
    restore();
    window.requestAnimationFrame(() => window.requestAnimationFrame(restore));
  });

  window.addEventListener("popstate", () => {
    const key = window.location.pathname + window.location.search;
    if (window.location.pathname === GUIDE_PATH && key !== shownKey) {
      showSphere(new URL(window.location.href), { push: false });
    }
  });

  window.addEventListener("scroll", scheduleProgressUpdate, { passive: true });
  window.addEventListener("resize", scheduleProgressUpdate);
  updateProgress();
})();
