# NosoVolution scientific workbench — product journeys and interface specifications

The web app should be for researchers, not an intimidating all-purpose page of fifty pipelines. Use a modular experience with roles: **Explorer**, **Investigator**, **Methodologist**, **Scientific Reviewer**, and **Operator**. Each accesses the same underlying objects but different default views.

## Six core end-to-end user journeys

### 1. Challenge a biomedical statement

Search disease/mechanism → view normalized contextual assertion → inspect direct primary sources, known dependency groups, study design and uncertainty → compare counterexamples → propose a narrow hypothesis → request a human review. **Failure UX:** show missing source and "unknown", never invent a citation or convert a missing result into negative evidence.

### 2. Reproduce a published mathematical simulation

Import eligible SBML/SED-ML/OMEX model → show units and model provenance → run preflight for supported solvers → freeze protocol → execute locally → compare numerical outputs and reference trajectories → generate reproducibility crate and independent reviewer queue. **Failure UX:** show unsupported feature, missing dataset or solver discrepancy as an explainable status.

### 3. Compare conditions or biological systems

Choose curated conditions and contexts → display overlap in genes/pathways/phenotypes → annotate curation completeness, source age and contradictory evidence → export comparison with explicit missingness and lineage. **Failure UX:** scaffold-only disease not presented as equivalent to curated disease.

### 4. Design a causal epidemiology investigation

Select exposure, comparison, time zero, eligibility, outcome, causal assumptions, source and target cohorts → visualize DAG and plausible confounding → freeze analysis plan → run synthetic validation → view effects with sensitivity and applicability. **Failure UX:** if positivity absent, flag nonidentification rather than extrapolate a treatment benefit.

### 5. Investigate single-cell data

Select public dataset and release → verify donor-level replication and tissue/cell annotation → run donor-aware analyses and a cell-naive negative-comparison baseline → display influence of batch, donor and preprocessing → export controlled notebook. **Failure UX:** zero donors/unknown donor IDs should prevent inferential claims.

### 6. Audit an AI-generated hypothesis

Open hypothesis → inspect sources and prior art → challenge contradictory evidence and study independence → show competing hypotheses → select falsifiable computational tests → score output against hidden references → require reviewer acceptance. **Failure UX:** inability to establish novelty or a causal link must remain visible.

## Navigation (proposed)

Home | Investigations | Evidence | Atlas | Laboratory | Methods | Models | Reviews | Data Catalog | Operations.

Never show all 1,457 proposals in the default researcher workflow. The atlas is a planning tool, while the user-facing workbench surfaces only capabilities that passed their own readiness gate. Create excellent empty/error states, source provenance links, keyboard access, visual uncertainty distinctions, and export previews. Responsive mobile views are valuable for evidence review and project monitoring; heavy scientific modeling remains desktop/laptop-oriented initially.

## Evidence-first layouts

Use trace stacks: result → method/model → inputs → source/version → limitations → reviewer. Provide side-by-side contrasts for study findings, model runs and uncertainty. Distinguish status by text + icon, never color alone. Avoid decorative certainty gauges or opaque single-number scientific truth scores.

## Interface acceptance

- Researchers can explain why an output exists without reading source code.
- Viewers can distinguish measured null, unrecorded and unsupported conclusions.
- Exact source, model and run versions are inspectable.
- A reviewer can reject/annotate a claim without deleting history.
- A local installation works when network access is offline and cached rights allow it.
- Cross-browser accessible UI and snapshot tests cover investigation start, interruption, negative experiment and export denial.