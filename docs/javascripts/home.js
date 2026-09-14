/* NosoGraph docs homepage — evidence-trace instrument + scroll reveals.

   Progressive enhancement only:
   - Without JS, the trace shows its default selected stage and every section
     renders fully visible.
   - Section reveals are gated behind html.ng-motion, which is added ONLY when
     the user has not requested reduced motion. base.css additionally forces
     near-zero animation/transition durations under prefers-reduced-motion.
   First-party, no dependencies, no external origins. */
(() => {
  const trace = document.querySelector("[data-ng-evidence-trace]");
  if (trace) {
    const steps = [...trace.querySelectorAll("[data-ng-trace-step]")];
    const inspector = trace.querySelector("[data-ng-trace-detail], .ng-trace-inspector");

    const details = {
      disease: ["Disease context", "systemic lupus erythematosus", "MONDO:0007915 · reference disease module"],
      claim: ["Typed claim", "condition associated with an entity", "predicate: associated_with · association is not causation"],
      evidence: ["Evidence direction", "SUPPORTS", "direction is not a truth verdict · other directions may coexist"],
      source: ["Study / source", "NOT_RECORDED", "study identifier and upstream source are not established by this illustration"],
      provenance: ["Provenance", "snapshot context", "snapshot identifier and fingerprint: NOT_RECORDED"],
    };

    const select = (step) => {
      const key = step.dataset.ngTraceStep;
      const detail = details[key];
      if (!detail || !inspector) return;
      steps.forEach((candidate) => {
        const selected = candidate === step;
        candidate.classList.toggle("is-selected", selected);
        candidate.setAttribute("aria-pressed", String(selected));
      });
      const label = inspector.querySelector(".ng-trace-inspector-label");
      const value = inspector.querySelector(".ng-trace-inspector-value");
      const meta = inspector.querySelector(".ng-trace-inspector-meta");
      if (label) label.textContent = detail[0];
      if (value) value.textContent = detail[1];
      if (meta) meta.textContent = detail[2];
    };

    steps.forEach((step) => {
      step.addEventListener("click", () => select(step));
      step.addEventListener("focus", () => select(step));
    });
  }

  // Scroll reveals — skipped entirely under reduced motion or without IO.
  const root = document.documentElement;
  if (!root.classList.contains("ng-page-home")) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  if (!("IntersectionObserver" in window)) return;
  const sections = [...document.querySelectorAll(".ng-homepage section:not(.ng-hero)")];
  if (!sections.length) return;
  try {
    root.classList.add("ng-motion");
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        }
      },
      // Generous bottom margin: sections pre-reveal ~a quarter viewport before
      // scrolling in, so fast scroll passes can't skip a section between ticks.
      { rootMargin: "0px 0px 25% 0px", threshold: 0 }
    );
    sections.forEach((section) => observer.observe(section));
    // Safety net: never leave content hidden if observation stalls (e.g. the
    // tab was backgrounded before first paint, or a full-page capture resizes
    // the viewport faster than callbacks dispatch).
    window.setTimeout(() => {
      sections.forEach((section) => section.classList.add("is-visible"));
    }, 3500);
  } catch {
    root.classList.remove("ng-motion");
  }
})();
