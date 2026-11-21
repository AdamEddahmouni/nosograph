# NosoVolution — The Scientific Research Operating System

## Executive thesis

NosoVolution should become a **research-science operating environment** that turns justified evidence into inspectable explanations, computational models, falsifiable research questions, controlled experiments and reproducible findings, while helping scientists discover gaps and criticize their own conclusions. The program encompasses medical specialties, molecular biology, quantitative physiology, causal/statistical inference, scientific software and education. It is **not** a universal physician, a giant automated truth machine, a default EHR, or an unvalidated treatment design system.

A large number of software modules is not scientific progress. Scientific progress means more relevant hypotheses tested under controlled conditions, better-calibrated uncertainty, higher reproducibility, fewer wrong assumptions accepted as true, and demonstrable research value to independent users.

## Strategic goal and differentiators

**Research challenge:** biomedical evidence is fragmented by disease, population, tissue, time, assay, instrument, study and publication. Software reproductions often omit exact environments; biomedical inference frequently mistakes associations for causal mechanisms; medical AI can misinterpret poor-quality evidence as high confidence. NosoVolution will make those distinctions structural rather than hoping prompts will handle them.

**Distinctive candidate mechanisms (not asserted inventions):**

1. Source-to-claim lineage through nested study families, including dependent cohorts and duplicated evidence.
2. Typed measurement and effect estimands with unit, sample, population, design and time context.
3. Model verification/validation/uncertainty quantification (VVUQ) with independent solver triangulation and explicit model applicability boundaries.
4. Experiment-as-object with pre-run acceptance conditions, negative and positive controls, blocked datasets and independent replication.
5. Competing causal mechanism hypotheses, disconfirming tests and expected information gain, subject to prior-art evaluation.
6. A research workbench unifying literature, annotations, code, protocols, notebook runs and review decisions.
7. A mixed developer/researcher ecosystem where mature third-party libraries and standards are wrapped as versioned adapters, not replaced.
8. Protected-data enforcement that propagates source rights into derived artifacts, agent tools, prompts, logs and exports.
9. Human/agent governance in which the authoring agent may not certify its own scientific claims.
10. Value demonstration using controlled research tasks, reproducibility, reviewer burden and cost, rather than vanity feature counts.

## Shared domain model

A `ScientificProject` contains one or more `Investigation` objects; each investigation holds `Question` → `Hypothesis` → `Protocol` → `DatasetSnapshot` + `ModelVersion` → `ExperimentRun` → `Observation`/`Estimate` → `EvidenceLink` → `ReviewDecision` → `ResultPublication`. A hypothesis can be rejected, superseded or unresolved, but never silently promoted into a confirmed fact by a model-generated response. Each source record has an immutable artifact hash, rights metadata, retrieval time, method and reference version; permissions are checked at every transfer edge.

**Evidence type must be explicit:** `OBSERVATION`, `ASSOCIATION`, `EXPERIMENTAL_EFFECT`, `MECHANISTIC_MODEL`, `CAUSAL_ESTIMATE`, `MODEL_PREDICTION`, `EXPERT_OPINION`, `REVIEW_CONCLUSION`, `UNRESOLVED`. Different types cannot be averaged into a single universal certainty score without a justified and tested model.

**Missingness and uncertainty:** `NOT_RECORDED`, `NOT_MEASURED`, `MEASURED_NULL`, `BELOW_DETECTION`, `KNOWN_ABSENT`, `CONFLICTING`, `UNAVAILABLE_RIGHTS`, `UNASSESSED`, and `NOT_APPLICABLE` are not interchangeable. Keep the underlying raw measurement and its limitations.

**Maturity is multi-axis**: engineering reliability, methodological validity, external scientific replication, and permissible intended use. A unit-tested algorithm may remain `scientifically unvalidated`; an externally validated analysis does not become a regulated medical product merely by existing.

## System composition and reuse

```text
Researcher / reviewer / contributor / agent
           ↓
  Local web workbench ─ CLI ─ Python SDK ─ Jupyter ─ scoped MCP
           ↓
  Study control (investigation, frozen protocol, run manifests)
           ↓
  Epistemic kernel (entities, assertions, measures, evidence, contexts, decisions)
           ↓
  Data plane (source rights, versioned snapshots, ontology maps, hashes, access rules)
           ↓
  Methods plane (stats, causal, simulation, omics, molecules, imaging, time series)
           ↓
  Sandboxed execution, output review, reproducible crates, immutable archive
```

Preserve the working NosoGraph legacy `med_research` package, disease registry, evidence store, Evidence Workspace, pipeline adapters and FastAPI until actual local implementation is reconciled. Build compatibility adapters first. Do not replace SQLite with a new graph database without a measured reason. Adopt DuckDB/Parquet for larger analytic tables, content-addressed filesystem for large reproducibility artifacts, and a migration-tested metadata store. Choose distributed queues only after a single-machine benchmark demands them.

## Scientific platform families

- **NosoEvidence:** source lineage, study design, contradiction interpretation, retractions, evidence quality, review and citations.
- **NosoAtlas:** contextual disease, phenotype, gene, organ, cell, pathway, exposure and outcome graph exploration.
- **NosoDiscovery:** falsifiable hypotheses, competing mechanisms, source gaps, target prioritization under explicit scope.
- **NosoMethods:** quantitative statistics, meta-analysis, causal inference, transportability, bias studies and metrology.
- **NosoSim:** curated mathematical models, solver adapters, nonlinear/stochastic/spatial simulation, calibration and VVUQ.
- **NosoLab:** reproducible workflows, notebooks, experiment registries, artifact bundles and controlled reruns.
- **NosoOmics, NosoMolecules, NosoImaging, NosoPhysiology, NosoPopulation, NosoTrials:** specialist adapters, benchmarks and domain-specific methods built over shared contracts.
- **NosoValidation:** external cohort/site testing, leakage prevention, model failure modes and review gates.
- **NosoResearchOps:** collaborative investigation queues, review workflows, agent cost governance and scientific audit.

These are **logical product capabilities**. Creating 14 independent repositories or brands immediately would multiply overhead. Start with a modular monolith plus isolated adapter packages. Split only when API stability, ownership or compute requirements justify it.

## What scientific work could actually change

**Biomedicine:** detect literature claims with weak statistical support; highlight reused cohorts; compare known biological pathways while retaining indirectness and tissue context; expose neglected study populations and unresolved findings.

**Molecular:** reproduce validated research-level docking/simulation experiments and give uncertainty and method applicability, not automatic proof of therapeutic value.

**Physiology:** couple well-specified submodels, verify conservation laws, study parameter identifiability and demonstrate how a model fails outside its validated region.

**Omics:** compare donor-aware and cell-naive analyses, batch and site confounding, feature-alignment uncertainty and replication across public cohorts.

**Epidemiology:** make target trial assumptions explicit; test immortal-time and selection bias; distinguish transportable and nontransportable estimates.

**Imaging:** perform patient/site separated cross-modality benchmarks and signal quality assessment; never conflate retrospective test scores with clinical diagnostic authorization.

**Drug/clinical evidence:** trace trials, endpoints, publications, contradictory outcomes, adverse-event reporting artifacts and their dependence.

**Operations and global health:** compare research models of access, resource allocation and surveillance under sensitivity to missing denominators and sampling intensity.

**Meta-research:** benchmark whether NosoVolution itself makes an independent scientist more successful on a reproducible task. Report failures and increased costs, not only positives.

## Four initial scientific lighthouses

1. **Scientific Evidence Calibration:** build a 200-case adjudicated synthetic-and-public benchmark of evidence quality, source entailment and study design. Correct observed heuristic overconfidence in `evidence_quality.py`; compare to conservative unknown-preserving baseline.
2. **Published Model Reproduction:** choose a small set of eligible public SBML/SED-ML BioModels; verify equations, units, simulation instructions, solver versions, tolerances, invariant checks and two-solver numerical agreement where technically supported. Reference study: https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1013239.
3. **Evidence Independence:** use public study/trial/DOI metadata and synthetic duplicates to test whether a study-lineage graph reduces double counting. Report ambiguous linkage rather than guessing actual patient overlap.
4. **Causal Transportability:** use synthetic source and target populations with known ground-truth effects to test positivity diagnostics and transport estimators versus naive extrapolation, including a deliberately broken assumption.

Each has independent test data, a fixed unit of analysis, a simple baseline, an explicit negative control, a preregistered analysis plan and an independent reviewer.

## Governance and open-source research quality

- Keep research-only language and refuse promotion from hypothetical outputs to patient advice.
- Restricted clinical datasets stay in their authorized environment. Avoid sending PHI or credentialed data to online agent prompts, tools or logs. This is a technical enforcement requirement, not a disclaimer.
- Use declared intended-use tiers with capability-specific reviews; do not infer device regulation from a generic project name.
- Record rights, attribution, redistribution, training and external-compute permissions per source. Default to denied if unknown.
- Track CodeMeta/CITATION, license, data version, method reference, model/solver version, reproducibility crate, DOI if published, and correction/withdrawal lineage.
- Subject scientific claims to independent review. Academic collaboration is valuable but not automatically evidence of accuracy.

## Practical execution priority

**Gate A: reality and evidence** — reconcile local divergent work, identify all installed dependencies and scientific data rights, trace existing code and tests, run source-level audit and reproducible baseline.

**Gate B: correctness** — fix evidence appraisal overconfidence, normalize claims and context, test unknown outcomes, add source and cohort identity mechanisms; do not destroy previous data semantics.

**Gate C: run engine** — freeze experiment specifications; implement versioned run and artifact manifests; demonstrate deterministic reexecution and proper failure status.

**Gate D: numerical science** — independently reproduce one public model and show both successful and deliberately invalid runs, explaining difference between numerical and biological validity.

**Gate E: scientific method** — add the contradiction/gap/hypothesis engine only when upstream evidence semantics are trustworthy; benchmark against naive baselines and hidden holdouts.

**Gate F: specialty pilots** — require one actual question, eligible public data, appropriate methodology, independent review and an external test set. Do not present the 124-domain horizon as 124 functioning laboratories.

**Gate G: researcher usefulness** — assess outside users, training time, reproducibility, task accuracy, cost and maintenance burden; preserve negative feedback.

## First director-facing decisions still open

- Repository rebrand and compatibility migration after local state audit: **UNAPPROVED**.
- Which four lighthouse programs to run in parallel after read-only audit: recommended all four with bounded resource limits; implementation authorization not inferred.
- Governance model for formal external scientific advisors and data stewards: proposed; no people assigned.
- Research source refresh policy and optional paid compute providers: proposed; cost ceilings default to free.
- Public demo, dataset redistribution and cloud hosting: do not launch before permissions and evaluation are verified.

## Key limitations of this plan

A planning document does not demonstrate that any method is novel, beneficial or medically safe. All counts refer to catalog entries. Some older experiment records are lightweight descriptions; their lack of details remains visible. Some domain categories overlap: partitioning the portfolio does not prove scientific novelty. Neither a small synthetic benchmark nor two solvers agreeing establishes biological correctness.