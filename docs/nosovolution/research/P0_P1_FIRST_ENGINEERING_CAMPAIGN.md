# The first NosoVolution campaign: exact order and acceptance evidence

**Planning-only work order.** This is not authorization to touch private repos or protected data; a local agent should begin with read-only reconnaissance, then submit a director-ready implementation plan. The only executable outputs bundled in Revision 5 are standalone synthetic test examples detached from the NosoGraph repository.

## Campaign 0 — Recover reality, preserve work (P0, no source edits)

1. **Discover every user-authorized clone** of `nosograph` and earlier `med-research`, on all mounted drives, using a read-only scoped path inventory. Include Git remotes, branches, default branch, worktrees, stashes, untracked/modified files, local releases, notebook collections, model checkpoints and data snapshots. Do not recursively search protected folders or unrelated personal files.
2. **Snapshot repository state**, per root: `git status --porcelain=v1 -uall`, `git worktree list`, `git branch -a -vv`, `git remote -v`, `git stash list`, `git log --all --decorate --graph --oneline -n 100`, all as read-only queries. Avoid printing secrets, private data or patient records into shared logs. An agent needs actual permission to access local drives, not an assumption about presence.
3. **Classify divergence:** public master, local-only commits, detached worktrees, stale feature branches, local uncommitted content, ignored research artifacts, versioned datasets and changes in dependencies. Do not equate last GitHub commit with local project state.
4. **Validate existing gates only in safe isolated environment** after dependencies/source rights are evaluated: `make ci-local`, fast pytest tier, mypy, relevant browser tests, and a source-specific scientific benchmark. Report `NOT_RUN` where tools or permissions are unavailable. Avoid unexpected network or writing into tracked directories.
5. **Create capability matrix** mapping each proposed contract to actual functions, tests, data and documentation. Label `OBSERVED_IN_CODE`, `TESTED_LOCALLY`, `VALIDATED_BY_EXTERNAL_DATA`, `DOC_ONLY`, `NOT_FOUND`, or `UNKNOWN` with evidence location.
6. **Produce acceptance report:** all relevant code/data found; no destructive actions; no new scientific claims; exact proposed integration branch and reversible patch plan.

## Campaign 1 — Evidence-quality correctness (P1)

**Observed public-file target:** `src/med_research/biomed/evidence_quality.py`, where a p-value regex or interval phrase can map to HIGH statistical quality. Audit current local file before change. Required behavior: `p` and confidence-interval presence captured as reported attributes, while risk of bias and scientific quality remain unknown unless supported by evaluable design and explicit reviewer criteria.

**Proposed work:** pin representative historical API behavior; author red/green tests for p-values, strong-but-confounded study, unknown design, population ambiguity, LLM-extracted claim, curator metadata misuse and null evidence; implement typed evidence-quality assessment; add fields without destructive historical migration; verify UI and exported provenance; compare false-confidence on a held-out adjudicated set.

**Deliverables:** source patch proposal, schema compatibility report, controlled tests, statistical evaluator and independent reviewer sign-off. **Exit gate:** false-HIGH from reporting-only text eliminated in fixtures; no quiet promotion from unknown to high; no regression in source trace.

## Campaign 2 — Source rights and experiment reproducibility (P1/P2)

Implement `DataPolicyDecision` validator (deny unknown), immutable `ExperimentProtocol`, `RunManifest`, scientific reason codes and content-addressed output storage. Connect to legacy claims as adapters. Reproduce a synthetic run offline first; then import one rights-checked public model. A run must be independently replayed from source hashes and a pinned environment. Restricted data cannot enter export or external AI prompts.

**Exit gate:** tool attempts restricted external transfer -> denied; exact synthetic run -> deterministic output hash or documented numeric-tolerance comparison; interrupted run -> not incorrectly COMPLETE; missing source license -> REVIEW_REQUIRED.

## Campaign 3 — One published simulation reproduction (P2)

Choose one public BioModels model with valid SED-ML, supported solver and license. Declare test version and expected trajectory before running; independently verify mathematical invariants and numerical differences. Produce a public-only RO-Crate-style bundle with source references, hashes, software version and results. **Exit:** independently rerunnable computation and clearly limited biological interpretation.

## Campaign 4 — Two parallel bounded validation pilots (P2/P3)

- Study-family linkage with public metadata and synthetic planted duplicate study families.
- Causal transportability with generated source/target populations and an intentional positivity violation.

Both use signed-off statistical plans and run on local CPU initially. Report negative outcomes.

## Parallelism rules

At most 4 independent active implementation branches at a time, each with distinct files and a sole primary owner; a separate reviewer never edits the same branch concurrently. Shared schema contracts freeze before parallel changes. Test failures are triaged; no agent silently fixes another agent's unrelated files. A user may change concurrency after observing token/CPU costs.

## Director acceptance summary format

`work package | base SHA | repository path | new evidence | tests attempted/passed | scientific result level | source rights | risks | reversible diff | recommendation | approval needed`.