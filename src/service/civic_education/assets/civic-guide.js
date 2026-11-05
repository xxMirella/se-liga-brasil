/* Progress index of the civic guide. The four-step index is a set of links that work without this
   file; here each step's bar fills as the reader moves through that step, and the step being read
   is marked as current. Plain JavaScript, no dependencies. */
(() => {
  "use strict";

  const STEP_COUNT = 4;
  const READING_LINE_RATIO = 0.4;
  const END_TOLERANCE_PX = 4;
  const BAR_SELECTOR = ".ds-civic-stepper__bar";
  const LINK_SELECTOR = ".ds-civic-stepper__link";
  const PROGRESS_PROPERTY = "--step-progress";

  const steps = Array.from({ length: STEP_COUNT }, (_, index) => ({
    section: document.getElementById(`passo-${index + 1}`),
    link: document.querySelector(`${LINK_SELECTOR}[href="#passo-${index + 1}"]`),
  })).filter((step) => step.section && step.link);

  let isUpdateScheduled = false;

  function clamp(value) {
    return Math.min(1, Math.max(0, value));
  }

  // Fraction of the step already read: how far the reading line has travelled through the section.
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

  function update() {
    isUpdateScheduled = false;
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

  function scheduleUpdate() {
    if (isUpdateScheduled) return;
    isUpdateScheduled = true;
    window.requestAnimationFrame(update);
  }

  if (steps.length === STEP_COUNT) {
    window.addEventListener("scroll", scheduleUpdate, { passive: true });
    window.addEventListener("resize", scheduleUpdate);
    update();
  }
})();
