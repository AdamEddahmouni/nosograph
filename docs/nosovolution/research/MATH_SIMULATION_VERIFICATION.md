# ADR-R5-03 — Mathematical science and simulation assurance

## Why numerical verification must precede biological conclusions

For a mechanistic model, a numerically stable-looking output can still be based on wrong units, a stiff solver artifact, unidentifiable parameters, incorrect boundary conditions, or a mechanism that does not represent measured biology. Separate:

- **Verification:** are the equations discretized/implemented and solved as claimed?
- **Validation:** is the model appropriate to represent the biological question in its declared domain?
- **Uncertainty quantification:** what uncertainty arises from parameters, measurement, structure, initial conditions and numerical error?
- **Applicability:** when does the model extrapolate beyond its supported population, species, tissue, time or assay conditions?

## Model families and checks

| Model family | Verification | Domain validation | First integration |
|---|---|---|---|
| ODE reaction kinetics | reference solution, timestep convergence, mass balance, units | published experimental curve when available | libRoadRunner / BioSimulators |
| Stochastic reactions | distributional tests, seeds, ensemble convergence | event distribution and observability | Gillespie-style adapters |
| PDE tissue transport | grid refinement, boundary condition tests, conservation | literature boundary/regime comparison | SciPy/FEniCSx only if justified |
| Pharmacokinetic models | compartments, mass balance, unit conversion, calibration | externally measured concentration curves | open PBPK methods and SciPy |
| Agent-based cell models | conservation/transition bounds, deterministic fixtures | independent aggregate cell behavior | Mesa/PhysiCell adapters |
| Molecular models | force-field/version constraints, energy stability and replicate variance | known benchmarks; no efficacy inference | RDKit/OpenMM where licensed |
| Causal models | estimand clarity, DAG consistency, positivity and sensitivity | synthetic ground truth / external cohorts | statsmodels/DoWhy |
| Neural dynamics | integration stability, synaptic parameter identifiability | signal features where licensed | MNE and specialist solvers |

## Required model registry contract

An engine must declare mathematics, version, allowed parameter types, unit system, solver algorithm, exact solver version, supported model format (SBML/SED-ML etc), license, model validation region, expected outputs, stochastic state and known limitations. Do not mark model "biologically valid" because a repository has curated it or because two engines agree.

## Cross-solver experiment

1. Select 3–5 clearly licensed public SBML/SED-ML examples, including a stiff system if supported and a conserved reaction network.
2. Freeze model source checksum, SED-ML tasks, simulation horizon, initial conditions, symbols and KISAO algorithms.
3. Verify unit semantics and any events/discontinuities; document unsupported solver/model combinations as `NOT_APPLICABLE` rather than FAIL.
4. Run at least two supported independent engines where feasible (or baseline plus analytic/manufactured solution where not), using prespecified absolute/relative tolerances.
5. Compare against published reference outputs if available; where not, distinguish `simulation executed` from `published result reproduced`.
6. Deliberately introduce a unit mismatch, a wrong initial condition, and a solver tolerance error; ensure diagnostic signals identify them.
7. Produce quantitative time-grid-aligned error metrics, conservation residuals, sensitivity to tolerance, environment logs and explainable mismatch classification.
8. Independent reviewer validates the run and records remaining biological unknowns.

## Mathematics roadmap

- Measurement science: unit registry, affine conversions, detection limits, uncertainty intervals.
- ODE/simulation: conservation, stiffness, sensitivity, bifurcation, parameter inference, event detection.
- Probability: stochastic processes, hierarchical Bayes, model discrepancy, posterior predictive checks.
- Spatial models: PDE discretization, finite elements, tissue transport, agent-based couplings.
- Causality: target trial emulation, exchangeability/positivity, transportability and sensitivity.
- Inverse methods: identifiability, regularization and ill-posed inference.
- Model selection: expected information gain, cost constraints, predeclared outcome utility.
- Multi-scale: coupling interface and uncertainty boundaries across cell, organ and population scales.

Reference: official BioSimulators documentation https://docs.biosimulations.org/users/faqs/ and PLOS Computational Biology study https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1013239.