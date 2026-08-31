(() => {
  const trace = document.querySelector("[data-ng-evidence-trace]");
  if (!trace) return;

  const steps = [...trace.querySelectorAll("[data-ng-trace-step]")];
  const inspector = trace.querySelector("[data-ng-trace-detail], .ng-trace-inspector");
  if (!inspector || !steps.length) return;

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
    if (!detail) return;
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
})();
