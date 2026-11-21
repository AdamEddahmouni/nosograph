# Revision 5 — 20 new bounded experiment protocols

Every protocol is **DRAFT ONLY** until source selection and preregistration; no real biomedical results are represented. Replace all `MUST SPECIFY` fields before launch.

## E125 — Evidence lineage and study independence: detection and negative-control stress test
**Research question.** When does apparent replication actually reuse the same sample or study?
**Testable prediction.** The specified method (dataset genealogy, bibliographic linkage, graph clustering, dependency-aware uncertainty) detects and quantifies scientifically relevant failure modes more reliably than naive publication counting.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Public literature/registry metadata with rights-checked study manifests
**Baseline.** naive publication counting
**Proposed method.** dataset genealogy, bibliographic linkage, graph clustering, dependency-aware uncertainty
**Negative control.** deliberately create duplicate papers from the same cohort
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** precision/recall of cohort-dependence edges and calibrated support intervals
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** synthetic data with a known injected violation and held-out seeds; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (deliberately create duplicate papers from the same cohort), is worse than naive publication counting, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1358, NGX-1359, NGX-1360, NGX-1361, NGX-1362
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E126 — Evidence lineage and study independence: external-context and sensitivity evaluation
**Research question.** When does apparent replication actually reuse the same sample or study?
**Testable prediction.** The specified method (dataset genealogy, bibliographic linkage, graph clustering, dependency-aware uncertainty) detects and quantifies scientifically relevant failure modes more reliably than naive publication counting.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Public literature/registry metadata with rights-checked study manifests
**Baseline.** naive publication counting
**Proposed method.** dataset genealogy, bibliographic linkage, graph clustering, dependency-aware uncertainty
**Negative control.** deliberately create duplicate papers from the same cohort
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** precision/recall of cohort-dependence edges and calibrated support intervals
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** a separate source/assay/site/time slice where rights allow, otherwise a marked synthetic proxy; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (deliberately create duplicate papers from the same cohort), is worse than naive publication counting, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1363, NGX-1364, NGX-1365, NGX-1366, NGX-1367
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E127 — Causal transportability and external validity: detection and negative-control stress test
**Research question.** Can an estimate from one population be transferred to another without hidden assumptions?
**Testable prediction.** The specified method (selection diagrams, covariate shift diagnostics, transport estimators, sensitivity bounds) detects and quantifies scientifically relevant failure modes more reliably than unadjusted source-population estimate.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Synthetic trials and public population benchmark data
**Baseline.** unadjusted source-population estimate
**Proposed method.** selection diagrams, covariate shift diagnostics, transport estimators, sensitivity bounds
**Negative control.** break positivity and hide a target-population effect modifier
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** target-population effect error and interval coverage
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** synthetic data with a known injected violation and held-out seeds; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (break positivity and hide a target-population effect modifier), is worse than unadjusted source-population estimate, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1368, NGX-1369, NGX-1370, NGX-1371, NGX-1372
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E128 — Causal transportability and external validity: external-context and sensitivity evaluation
**Research question.** Can an estimate from one population be transferred to another without hidden assumptions?
**Testable prediction.** The specified method (selection diagrams, covariate shift diagnostics, transport estimators, sensitivity bounds) detects and quantifies scientifically relevant failure modes more reliably than unadjusted source-population estimate.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Synthetic trials and public population benchmark data
**Baseline.** unadjusted source-population estimate
**Proposed method.** selection diagrams, covariate shift diagnostics, transport estimators, sensitivity bounds
**Negative control.** break positivity and hide a target-population effect modifier
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** target-population effect error and interval coverage
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** a separate source/assay/site/time slice where rights allow, otherwise a marked synthetic proxy; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (break positivity and hide a target-population effect modifier), is worse than unadjusted source-population estimate, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1373, NGX-1374, NGX-1375, NGX-1376, NGX-1377
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E129 — Measurement ontology and metrological traceability: detection and negative-control stress test
**Research question.** Do measurements really mean the same quantity across assays and modalities?
**Testable prediction.** The specified method (quantity calculus, unit invariants, measurement error models, instrument provenance) detects and quantifies scientifically relevant failure modes more reliably than unit-string equality with no method context.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Public assay specifications, synthetic standards, permitted reference materials
**Baseline.** unit-string equality with no method context
**Proposed method.** quantity calculus, unit invariants, measurement error models, instrument provenance
**Negative control.** inject unit conversion errors and assay-specific offsets
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** unsafe merge detection rate and numeric conversion error
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** synthetic data with a known injected violation and held-out seeds; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (inject unit conversion errors and assay-specific offsets), is worse than unit-string equality with no method context, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1378, NGX-1379, NGX-1380, NGX-1381, NGX-1382
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E130 — Measurement ontology and metrological traceability: external-context and sensitivity evaluation
**Research question.** Do measurements really mean the same quantity across assays and modalities?
**Testable prediction.** The specified method (quantity calculus, unit invariants, measurement error models, instrument provenance) detects and quantifies scientifically relevant failure modes more reliably than unit-string equality with no method context.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Public assay specifications, synthetic standards, permitted reference materials
**Baseline.** unit-string equality with no method context
**Proposed method.** quantity calculus, unit invariants, measurement error models, instrument provenance
**Negative control.** inject unit conversion errors and assay-specific offsets
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** unsafe merge detection rate and numeric conversion error
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** a separate source/assay/site/time slice where rights allow, otherwise a marked synthetic proxy; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (inject unit conversion errors and assay-specific offsets), is worse than unit-string equality with no method context, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1383, NGX-1384, NGX-1385, NGX-1386, NGX-1387
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E131 — Computational figure and methods reproduction: detection and negative-control stress test
**Research question.** Can an independent researcher recreate a published computational figure from preserved artifacts?
**Testable prediction.** The specified method (paper-to-protocol mapping, executable environments, numeric image comparison, blinded replication) detects and quantifies scientifically relevant failure modes more reliably than paper-only instructions without machine-verifiable manifest.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Public code, figures, simulation packages and openly licensed supplementary data
**Baseline.** paper-only instructions without machine-verifiable manifest
**Proposed method.** paper-to-protocol mapping, executable environments, numeric image comparison, blinded replication
**Negative control.** perturb random seeds, solver tolerances or source-file versions
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** independent reproduction success under prespecified tolerances
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** synthetic data with a known injected violation and held-out seeds; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (perturb random seeds, solver tolerances or source-file versions), is worse than paper-only instructions without machine-verifiable manifest, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1388, NGX-1389, NGX-1390, NGX-1391, NGX-1392
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E132 — Computational figure and methods reproduction: external-context and sensitivity evaluation
**Research question.** Can an independent researcher recreate a published computational figure from preserved artifacts?
**Testable prediction.** The specified method (paper-to-protocol mapping, executable environments, numeric image comparison, blinded replication) detects and quantifies scientifically relevant failure modes more reliably than paper-only instructions without machine-verifiable manifest.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Public code, figures, simulation packages and openly licensed supplementary data
**Baseline.** paper-only instructions without machine-verifiable manifest
**Proposed method.** paper-to-protocol mapping, executable environments, numeric image comparison, blinded replication
**Negative control.** perturb random seeds, solver tolerances or source-file versions
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** independent reproduction success under prespecified tolerances
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** a separate source/assay/site/time slice where rights allow, otherwise a marked synthetic proxy; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (perturb random seeds, solver tolerances or source-file versions), is worse than paper-only instructions without machine-verifiable manifest, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1393, NGX-1394, NGX-1395, NGX-1396, NGX-1397
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E133 — Patient-important outcomes and measurement validity: detection and negative-control stress test
**Research question.** Are scientific endpoints connected to outcomes that matter to people?
**Testable prediction.** The specified method (outcome measurement, psychometrics, content validity, missing-data sensitivity) detects and quantifies scientifically relevant failure modes more reliably than proxy-only endpoint interpretation.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Public outcome-instrument descriptions, survey methods, synthetic cohorts
**Baseline.** proxy-only endpoint interpretation
**Proposed method.** outcome measurement, psychometrics, content validity, missing-data sensitivity
**Negative control.** introduce language and response-shift bias
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** construct-validity and subgroup measurement-invariance performance
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** synthetic data with a known injected violation and held-out seeds; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (introduce language and response-shift bias), is worse than proxy-only endpoint interpretation, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1398, NGX-1399, NGX-1400, NGX-1401, NGX-1402
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E134 — Patient-important outcomes and measurement validity: external-context and sensitivity evaluation
**Research question.** Are scientific endpoints connected to outcomes that matter to people?
**Testable prediction.** The specified method (outcome measurement, psychometrics, content validity, missing-data sensitivity) detects and quantifies scientifically relevant failure modes more reliably than proxy-only endpoint interpretation.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Public outcome-instrument descriptions, survey methods, synthetic cohorts
**Baseline.** proxy-only endpoint interpretation
**Proposed method.** outcome measurement, psychometrics, content validity, missing-data sensitivity
**Negative control.** introduce language and response-shift bias
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** construct-validity and subgroup measurement-invariance performance
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** a separate source/assay/site/time slice where rights allow, otherwise a marked synthetic proxy; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (introduce language and response-shift bias), is worse than proxy-only endpoint interpretation, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1403, NGX-1404, NGX-1405, NGX-1406, NGX-1407
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E135 — Neonatal and early-life systems physiology: detection and negative-control stress test
**Research question.** How do rapidly changing neonatal physiology and measurement context affect model assumptions?
**Testable prediction.** The specified method (age-dependent physiology, dynamical models, maturation curves, uncertainty intervals) detects and quantifies scientifically relevant failure modes more reliably than adult-parameter extrapolation.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Open developmental physiology references and synthetic model trajectories
**Baseline.** adult-parameter extrapolation
**Proposed method.** age-dependent physiology, dynamical models, maturation curves, uncertainty intervals
**Negative control.** swap gestational versus postnatal age or units
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** prediction consistency on published reference curves with uncertainty
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** synthetic data with a known injected violation and held-out seeds; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (swap gestational versus postnatal age or units), is worse than adult-parameter extrapolation, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1408, NGX-1409, NGX-1410, NGX-1411, NGX-1412
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E136 — Neonatal and early-life systems physiology: external-context and sensitivity evaluation
**Research question.** How do rapidly changing neonatal physiology and measurement context affect model assumptions?
**Testable prediction.** The specified method (age-dependent physiology, dynamical models, maturation curves, uncertainty intervals) detects and quantifies scientifically relevant failure modes more reliably than adult-parameter extrapolation.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Open developmental physiology references and synthetic model trajectories
**Baseline.** adult-parameter extrapolation
**Proposed method.** age-dependent physiology, dynamical models, maturation curves, uncertainty intervals
**Negative control.** swap gestational versus postnatal age or units
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** prediction consistency on published reference curves with uncertainty
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** a separate source/assay/site/time slice where rights allow, otherwise a marked synthetic proxy; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (swap gestational versus postnatal age or units), is worse than adult-parameter extrapolation, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1413, NGX-1414, NGX-1415, NGX-1416, NGX-1417
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E137 — Biophysical solver assurance and uncertainty: detection and negative-control stress test
**Research question.** Does numerical model agreement survive conservation and uncertainty challenges?
**Testable prediction.** The specified method (stability theory, solver differential testing, identifiability, interval methods, VVUQ) detects and quantifies scientifically relevant failure modes more reliably than single default solver with default tolerance.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Open ODE/PDE benchmark problems, curated BioModels, synthetic conserved systems
**Baseline.** single default solver with default tolerance
**Proposed method.** stability theory, solver differential testing, identifiability, interval methods, VVUQ
**Negative control.** break mass conservation and perturb stiff parameters
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** reference trajectory error, invariant violations and false-convergence rate
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** synthetic data with a known injected violation and held-out seeds; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (break mass conservation and perturb stiff parameters), is worse than single default solver with default tolerance, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1418, NGX-1419, NGX-1420, NGX-1421, NGX-1422
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E138 — Biophysical solver assurance and uncertainty: external-context and sensitivity evaluation
**Research question.** Does numerical model agreement survive conservation and uncertainty challenges?
**Testable prediction.** The specified method (stability theory, solver differential testing, identifiability, interval methods, VVUQ) detects and quantifies scientifically relevant failure modes more reliably than single default solver with default tolerance.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Open ODE/PDE benchmark problems, curated BioModels, synthetic conserved systems
**Baseline.** single default solver with default tolerance
**Proposed method.** stability theory, solver differential testing, identifiability, interval methods, VVUQ
**Negative control.** break mass conservation and perturb stiff parameters
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** reference trajectory error, invariant violations and false-convergence rate
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** a separate source/assay/site/time slice where rights allow, otherwise a marked synthetic proxy; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (break mass conservation and perturb stiff parameters), is worse than single default solver with default tolerance, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1423, NGX-1424, NGX-1425, NGX-1426, NGX-1427
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E139 — Multimodal biomedical model robustness: detection and negative-control stress test
**Research question.** Do biomedical AI models survive shifts in assay, site, acquisition and missing modalities?
**Testable prediction.** The specified method (OOD evaluation, subgroup calibration, leakage audit, selective prediction, uncertainty) detects and quantifies scientifically relevant failure modes more reliably than random split accuracy without group separation.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Publicly licensed imaging/omics/biosignal benchmark subsets
**Baseline.** random split accuracy without group separation
**Proposed method.** OOD evaluation, subgroup calibration, leakage audit, selective prediction, uncertainty
**Negative control.** duplicate patients across train and test or remove an input modality
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** external-site AUROC/PR-AUC, calibration, subgroup gap and abstention utility
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** synthetic data with a known injected violation and held-out seeds; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (duplicate patients across train and test or remove an input modality), is worse than random split accuracy without group separation, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1428, NGX-1429, NGX-1430, NGX-1431, NGX-1432
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E140 — Multimodal biomedical model robustness: external-context and sensitivity evaluation
**Research question.** Do biomedical AI models survive shifts in assay, site, acquisition and missing modalities?
**Testable prediction.** The specified method (OOD evaluation, subgroup calibration, leakage audit, selective prediction, uncertainty) detects and quantifies scientifically relevant failure modes more reliably than random split accuracy without group separation.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Publicly licensed imaging/omics/biosignal benchmark subsets
**Baseline.** random split accuracy without group separation
**Proposed method.** OOD evaluation, subgroup calibration, leakage audit, selective prediction, uncertainty
**Negative control.** duplicate patients across train and test or remove an input modality
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** external-site AUROC/PR-AUC, calibration, subgroup gap and abstention utility
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** a separate source/assay/site/time slice where rights allow, otherwise a marked synthetic proxy; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (duplicate patients across train and test or remove an input modality), is worse than random split accuracy without group separation, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1433, NGX-1434, NGX-1435, NGX-1436, NGX-1437
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E141 — One Health resistance and antimicrobial stewardship: detection and negative-control stress test
**Research question.** Can cross-reservoir antimicrobial resistance models distinguish surveillance effects from ecological change?
**Testable prediction.** The specified method (time-series surveillance, phylogenetic uncertainty, network ecology, spatial statistics) detects and quantifies scientifically relevant failure modes more reliably than single-source annual resistance trend.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Public surveillance aggregates and appropriately permitted microbial genomic datasets
**Baseline.** single-source annual resistance trend
**Proposed method.** time-series surveillance, phylogenetic uncertainty, network ecology, spatial statistics
**Negative control.** inject surveillance sampling intensity changes
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** calibration and external-period predictive error with source-shift sensitivity
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** synthetic data with a known injected violation and held-out seeds; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (inject surveillance sampling intensity changes), is worse than single-source annual resistance trend, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1438, NGX-1439, NGX-1440, NGX-1441, NGX-1442
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E142 — One Health resistance and antimicrobial stewardship: external-context and sensitivity evaluation
**Research question.** Can cross-reservoir antimicrobial resistance models distinguish surveillance effects from ecological change?
**Testable prediction.** The specified method (time-series surveillance, phylogenetic uncertainty, network ecology, spatial statistics) detects and quantifies scientifically relevant failure modes more reliably than single-source annual resistance trend.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Public surveillance aggregates and appropriately permitted microbial genomic datasets
**Baseline.** single-source annual resistance trend
**Proposed method.** time-series surveillance, phylogenetic uncertainty, network ecology, spatial statistics
**Negative control.** inject surveillance sampling intensity changes
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** calibration and external-period predictive error with source-shift sensitivity
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** a separate source/assay/site/time slice where rights allow, otherwise a marked synthetic proxy; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (inject surveillance sampling intensity changes), is worse than single-source annual resistance trend, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1443, NGX-1444, NGX-1445, NGX-1446, NGX-1447
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E143 — Research workflows and human-agent collaboration: detection and negative-control stress test
**Research question.** Can agents improve research quality when review burden, cost and errors are counted?
**Testable prediction.** The specified method (human-computer interaction, controlled agent experiments, reproducibility review, operations research) detects and quantifies scientifically relevant failure modes more reliably than single researcher or agent without review infrastructure.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Synthetic workflows, open research code and expert-scored nonclinical study tasks
**Baseline.** single researcher or agent without review infrastructure
**Proposed method.** human-computer interaction, controlled agent experiments, reproducibility review, operations research
**Negative control.** introduce false citations, conflicting objectives and replay disruptions
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** verified scientific task success per dollar/hour and reviewer-corrected error rate
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** synthetic data with a known injected violation and held-out seeds; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (introduce false citations, conflicting objectives and replay disruptions), is worse than single researcher or agent without review infrastructure, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1448, NGX-1449, NGX-1450, NGX-1451, NGX-1452
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN

## E144 — Research workflows and human-agent collaboration: external-context and sensitivity evaluation
**Research question.** Can agents improve research quality when review burden, cost and errors are counted?
**Testable prediction.** The specified method (human-computer interaction, controlled agent experiments, reproducibility review, operations research) detects and quantifies scientifically relevant failure modes more reliably than single researcher or agent without review infrastructure.
**Unit of analysis.** MUST BE FIXED BEFORE EXECUTION; do not confuse subject, specimen, study, cell, visit or source record
**Eligible source scope.** Synthetic workflows, open research code and expert-scored nonclinical study tasks
**Baseline.** single researcher or agent without review infrastructure
**Proposed method.** human-computer interaction, controlled agent experiments, reproducibility review, operations research
**Negative control.** introduce false citations, conflicting objectives and replay disruptions
**Positive control.** Known reference, synthetic planted truth, or documented unavailable
**Primary metric.** verified scientific task success per dollar/hour and reviewer-corrected error rate
**Secondary metrics.** calibration or uncertainty coverage, control sensitivity, abstention rate where applicable, wall-clock and memory cost, independent replay success
**Design.** a separate source/assay/site/time slice where rights allow, otherwise a marked synthetic proxy; Before reading held-out data: pin inclusion, exclusion, source version, exact metric, controls, seeds, and acceptance threshold
**Statistical plan.** Set explicit unit, train/test split, effect size, uncertainty interval, multiplicity handling, and preregistered inference before execution
**Leakage prevention.** Split at highest shared entity level; freeze inputs and preprocessing before holdout
**Replicability.** At least independent seeds for stochastic cases and external data/site if permitted; exact count preregistered
**Falsification.** Fails control (introduce false citations, conflicting objectives and replay disruptions), is worse than single researcher or agent without review infrastructure, or cannot be independently reproduced
**Acceptance.** Requires external or held-out pass, negative control pass, and independent review; never automatically promoted to scientific validation
**Required outputs.** versioned eligible source manifest, frozen protocol, raw and processed input hashes, baseline/comparison output, positive/negative control outcomes, null and adverse results, independent reviewer decision, reproduction crate
**Linked initiatives.** NGX-1453, NGX-1454, NGX-1455, NGX-1456, NGX-1457
**Status.** PROTOCOL_DRAFT_NOT_PREREGISTERED_OR_RUN