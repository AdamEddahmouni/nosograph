# Four proof-of-value research charters (DRAFT; not executed)

These charters are prioritized because they validate the platform's own foundational claims before attempting ungrounded therapeutic discovery. Thresholds below are **candidate planning gates**, to be selected/frozen by the scientific lead before any holdout test is viewed. No result is claimed.

## Campaign L1: Evidence-quality overconfidence

**Observed target:** NosoGraph's existing evidence-quality heuristic can infer `statistical_quality='high'` when a text mentions certain p-values or confidence intervals. Those markers do not establish methodological quality. Verify exact local code state before patching.

**Hypothesis:** explicit extraction of statistical reporting features with conservative unknown quality and reviewable evidence spans reduces false confidence compared to the current heuristic while retaining useful metadata.

**Design:** construct 200 synthetic/adjudicated cases across 12 controlled strata: reported p with missing methods, underpowered significant study, precise biased estimate, selected endpoint, duplicate publications, null well-designed study, retraction, cross-species mismatch, nonrandomized confounding, reviewer status uncertainty, negative outcomes, unknown assay unit. Ensure independent reviewer adjudication and a held-out 30% group split *after* grouping by study family. Freeze exact criteria before holdout.

**Baseline:** current heuristic + simpler always-unknown quality classifier. **Intervention:** structured extraction plus methods review states, not a new opaque score. **Primary metric:** false-HIGH quality classification per strata; separately report false negatives of recorded design metadata. **Negative control:** artificially insert `p < 0.0001` in a low-quality study while preserving known bias. **Positive control:** source with independently adjudicated design and quality metadata. **Falsifier:** method cannot reduce false confidence without unacceptable information loss, invents assessment, or cannot trace source. **Outcome:** testable plan and code/gold records, not clinical conclusions.

## Campaign L2: Published biological model reproduction

**Hypothesis:** a source-pinned verification pipeline identifies numerical/metadata errors in published model runs more reliably than a manual `run with defaults` process.

**Input criteria:** 3–5 open, legally usable models with accessible SBML and SED-ML/COMBINE artifacts, plus documentation of supported simulation engines. Begin with a minimal two-species conserved reaction network and one more difficult model after code-readiness check. Cite each selected model accession and license in the frozen protocol.

**Method:** capture model/file hashes, solver/algorithm identifiers, SED-ML instructions, units, parameters, initial conditions, random seeds and model scope. Execute a supported reference solver, then independent engine or analytic solution where feasible. Compare time-grid-aligned trajectories and conservation residuals using prespecified `atol`/`rtol` and scale. Test solver tolerance sensitivity and parameter perturbation. **Baseline:** manual default run. **Negative control:** insert a broken initial condition or unit mismatch. **Primary metric:** exact reproduction of specified reference output (not merely software run success), plus correctly diagnosed mismatch frequency. **Falsifier:** unreliable cross-engine comparison, untraceable data, false mismatch due to incompatible algorithms, or no improvement over reference process. **Review:** numerical analyst and domain scientist separately sign outcomes.

## Campaign L3: Study lineage and dependence-aware evidence

**Hypothesis:** grouping dependent publications by study family reduces evidence double-counting without incorrectly merging independent replication.

**Data:** synthetic graph with known study-family labels and allowed public registry/DOI records for realistic ambiguity. Do not use actual patient identifiers. **Baselines:** publication-count scoring, DOI-only deduplication. **Method:** infer study family links with citation/source metadata, recruitment, trial identifiers and manual review of ambiguous matches. **Primary:** precision, recall and abstention of dependency classification; support estimate sensitivity to grouping. **Negative:** two unrelated studies sharing disease, institution and date must not be forced into same cohort; duplicate follow-up publications from one cohort must not be independent. **Falsifier:** excessive false merges, unverifiable linkage, no improvement or substantial reviewer burden. **Output:** independent study-family graph, uncertainty report and reviewed case library.

## Campaign L4: Causal transportability failure detection

**Hypothesis:** assumption-aware transfer analysis gives more accurate target-population effect estimates or appropriately declines unsupported extrapolation compared with naive source-only results.

**Data:** openly reproducible synthetic source/target populations with known effect modifiers and known true target mean effect. **Design:** source randomized assignment in simulation; vary selection into source cohort, overlap, outcome model misspecification and unmeasured effect modifiers. Freeze target estimand, interval method and seed batch. **Baseline:** naive source average effect and standard reweighting where assumptions hold. **Primary:** bias/coverage of target effect and correct refusal under positivity failure. **Negative:** deliberately remove a target covariate stratum and omit true modifier; fail the estimator if it asserts point identification. **Falsifier:** worse interval coverage, failure to abstain or improper causal claim outside generated assumptions. **Bound:** synthetic validity, not treatment advice.

## Cross-campaign required evidence package

`protocol.json`, source/use policy report, model/algorithm versions, independent group split record, baseline and control outputs, raw computation results, uncertainties, reviewer disagreement, `ro-crate-metadata.json`, error report and release decision. An autonomous agent cannot sign the final scientific validity gate.