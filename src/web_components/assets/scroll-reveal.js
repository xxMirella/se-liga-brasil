/* Content eases in, in a short stagger, as it scrolls into view. Shared by /panorama and the
   person profile. The page is complete without this file: nothing is hidden until it runs.
   Pages that replace their content in place announce it with a `ds:content-replaced` event.
   Plain JavaScript, no dependencies. */
(() => {
  "use strict";

  const MAIN_ID = "main";
  const REVEAL_CLASS = "ds-reveal";
  const REVEAL_READY_CLASS = "ds-reveal-ready";
  const REVEAL_VISIBLE_CLASS = "ds-is-visible";
  const CONTENT_REPLACED_EVENT = "ds:content-replaced";
  const MAX_STAGGER_STEP = 5;
  const STAGGER_CLEANUP_MS = 1500;
  // Keep targets from nesting, and keep the data-mark rules in motion.css in step with them.
  const REVEAL_SELECTOR = [
    // /panorama
    ".ds-opening__intro", ".ds-rule-card", ".ds-timeline__header", ".ds-timeline__controls",
    ".ds-timeline-row", ".ds-timeline__callout", ".ds-period__heading", ".ds-period__verdict",
    ".ds-period-card", ".ds-seats-card", ".ds-reading", ".ds-disclosure",
    // person profile
    ".ds-profile-identity", ".ds-profile-summary__card", ".ds-profile-heading",
    ".ds-profile-career__list", ".ds-profile-attendance__summary", ".ds-profile-chart",
    ".ds-profile-category", ".ds-profile-search", ".ds-profile-card",
    // civic guide
    ".ds-civic-principle", ".ds-civic-step__title", ".ds-civic-step__lead", ".ds-civic-toolbar",
    ".ds-civic-realms__title", ".ds-civic-power", ".ds-civic-office", ".ds-civic-quiz",
    ".ds-civic-law__sphere", ".ds-civic-law__tag",
  ].join(",");

  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const canReveal = "IntersectionObserver" in window && !prefersReducedMotion.matches;

  let revealObserver = null;

  function isInView(element) {
    return element.getBoundingClientRect().top < window.innerHeight;
  }

  // Two frames: the hidden state must be painted once, or the browser has nothing to transition from.
  function afterFirstPaint(callback) {
    window.requestAnimationFrame(() => window.requestAnimationFrame(callback));
  }

  function showWithStagger(element, step) {
    const stepClass = `ds-reveal-step-${Math.min(step, MAX_STAGGER_STEP)}`;
    element.classList.add(stepClass, REVEAL_VISIBLE_CLASS);
    window.setTimeout(() => element.classList.remove(stepClass), STAGGER_CLEANUP_MS);
  }

  function onReveal(entries) {
    entries.filter((entry) => entry.isIntersecting).forEach((entry, index) => {
      showWithStagger(entry.target, index);
      revealObserver.unobserve(entry.target);
    });
  }

  // `animate` is true on the first load, so the opening content also eases in; after an in-place
  // update the new content is already in place and must not blink.
  function setUpReveal({ animate }) {
    const main = document.getElementById(MAIN_ID);
    if (!canReveal || !main) return;
    revealObserver = revealObserver || new IntersectionObserver(onReveal, {
      threshold: 0.12, rootMargin: "0px 0px -6% 0px",
    });
    const targets = [...main.querySelectorAll(REVEAL_SELECTOR)];
    targets.forEach((element) => element.classList.add(REVEAL_CLASS));
    document.documentElement.classList.add(REVEAL_READY_CLASS);
    const inView = targets.filter(isInView);
    inView.forEach((element, index) => {
      if (animate) afterFirstPaint(() => showWithStagger(element, index));
      else element.classList.add(REVEAL_VISIBLE_CLASS);
    });
    targets.filter((element) => !inView.includes(element))
      .forEach((element) => revealObserver.observe(element));
  }

  document.addEventListener(CONTENT_REPLACED_EVENT, () => setUpReveal({ animate: false }));
  setUpReveal({ animate: true });
})();
