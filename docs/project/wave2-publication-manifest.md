# Wave 2 publication manifest

Local, un-pushed state at the end of the Wave 2 session. Nothing in this file
describes a hosted or published artifact: no branch below has been pushed and
no pull request exists for any of them. Regenerate the SHAs with
`git rev-parse <branch>` before acting on them.

- Repository: `AdamEddahmouni/nosograph`
- Remote base verified: `master` = `4c60dd611ade008a6b0258190c8785d128c598aa`
- Open dependency PR #116 (branch `feat/demo-safety-infra`) head =
  `e67768cacaa52038e546952f8e70aac76c2a163b`
- Every branch below has `master` itself as its merge base with `master`, and
  every branch is built on `e67768cac`, not on `master`.

## Publication order

```text
master (4c60dd611)
  ├── PR 1  feat/hpoa-sync-source        independent, no PR #116 dependency
  ├── PR 2  feat/disease-validation-gate independent, no PR #116 dependency
  │
  └── (PR #116) feat/demo-safety-infra @ e67768cac
        ├── PR 3  feat/hosting-readiness      stacked
        ├── PR 4  feat/dashboard-ui-polish    stacked
        ├── PR 5  feat/parallel-wave1         stacked (integration of 1-4)
        └── PR 6  feat/parallel-wave2         stacked (integration of 1-5 + new work)
```

Publishing 1 and 2 against `master` first removes two of the four commits that
`feat/parallel-wave1` currently carries, which shrinks the stacked PRs 5 and 6.

## Branch detail

| # | Branch | HEAD | Commits since #116 | PR target | Dependency | Merge onto `master` |
|---|--------|------|--------------------|-----------|------------|---------------------|
| 1 | `feat/hpoa-sync-source` | `d34c00f953d9a422441c5cffbc3e286d8e2475eb` | 1 | `master` | none | clean |
| 2 | `feat/disease-validation-gate` | `4278b90ebd02c147cc0340787f4a99bd7d18d8b1` | 1 | `master` | none | clean |
| 3 | `feat/hosting-readiness` | `f8c3ec728d07934a1406d0595710962c23f62437` | 1 | `feat/demo-safety-infra` | PR #116 | **conflict** |
| 4 | `feat/dashboard-ui-polish` | `d7d93b588de1697ed8c62918756c880d1dd8b285` | 1 | `feat/demo-safety-infra` | PR #116 | clean, but depends on #116 content |
| 5 | `feat/parallel-wave1` | `240c3de5a244ed625c9b8ac844cb49fbc379a084` | 5 | `feat/demo-safety-infra` | PR #116 | not attempted (superset) |
| 6 | `feat/parallel-wave2` | `f68e9221000aadbd2c85ca08fce7e72f5f644c80` | 13 | `feat/demo-safety-infra` | PR #116 | not attempted (superset) |

### Why 1 and 2 are independent of PR #116

Every file each branch touches is either byte-identical between `master` and
`e67768cac`, or the changed regions do not overlap.

`feat/hpoa-sync-source` touches six files. All six are identical in both trees.
Its new module imports only `biomed.identifiers`, `biomed.imports.hpoa`,
`biomed.imports.models`, `biomed.models`, and `biomed.sync.models` — and all
five of those are also identical in both trees.

`feat/disease-validation-gate` touches four files. Only `src/med_research/cli.py`
differs, and the regions differ in different places: PR #116 edits around lines
420, 794, 1199, 1551, and 1571, while this branch edits around 345, 379, 1084,
1190, 1202, and 1214. The only non-argparse symbols it calls,
`run_strict_validation_batch` and `write_validation_report`, live in
`validation_batch.py`, which is identical in both trees.

A three-way merge with `--merge-base=e67768cac` reports no conflicts for either
branch. Neither branch has been *tested* on a `master`-based tree in this
session; that is the one remaining check before opening them.

### Why 3 and 4 are stacked

`feat/hosting-readiness` touches `Dockerfile`, `Dockerfile.demo`,
`docker-compose.demo.yml`, `src/med_research/web/config.py`,
`src/med_research/web/main.py`, and `tests/test_docker_evaluation.py` — all six
are changed by PR #116, and the three-way merge against `master` conflicts on
`Dockerfile.demo`, `docker-compose.demo.yml`, `config.py`, and `main.py`. Its
whole purpose is to build on PR #116's injected-`PORT` work, so it should target
`feat/demo-safety-infra`.

`feat/dashboard-ui-polish` merges textually, but only because its CSS additions
are appended after PR #116's. Applying it to `master` would produce a stylesheet
that is missing PR #116's 40 lines while keeping polish written against PR #116's
markup. Stack it.

## Test evidence for Wave 1 content (run on `feat/parallel-wave2`, which contains it)

| Suite | Command | Result |
|-------|---------|--------|
| Sync framework (HPOA, Open Targets, MONDO) | `pytest tests/biomed/sync/` | 54 passed |
| Validation gate | `pytest tests/test_validation_batch.py` | 13 passed |
| Docker assets and evaluation contracts | `pytest tests/test_docker_assets.py tests/test_docker_evaluation.py` | 36 passed |
| Dashboard styles | `pytest tests/test_dashboard_styles.py` | 12 passed |
| Evidence Explorer UI | `pytest tests/test_evidence_explorer_ui.py` | 11 passed |
| Dashboard a11y browser (desktop + phone) | `pytest tests/test_dashboard_a11y_browser.py` | 18 passed |

These cover the Wave 1 implementation. They do not constitute a re-run of
Wave 1's own reported numbers.

## Known limitations

- Branch 2's `master`-based behaviour is established by merge analysis, not by
  running its tests on a `master`-based tree.
- `feat/hosting-readiness` and `feat/dashboard-ui-polish` cannot be reviewed
  against `master` meaningfully until PR #116 merges.
- A fresh Docker image has not been built from the current source tree in this
  session. Container runtime behaviour was verified against
  `nosograph-smoke:8123`, created `2026-11-03T19:54:58Z`.
- Nothing here is pushed. Hosted CI, CodeQL, and Pages validation have not run
  against any of these commits.

## Regenerating this analysis

```bash
PR116=e67768cacaa52038e546952f8e70aac76c2a163b
for b in feat/hpoa-sync-source feat/disease-validation-gate feat/hosting-readiness feat/dashboard-ui-polish; do
  echo "== $b"
  git diff --name-only "$PR116" "$b" | while read -r f; do
    git diff --quiet master "$PR116" -- "$f" && echo "  same    $f" || echo "  diverges $f"
  done
  git merge-tree --write-tree --merge-base="$PR116" master "$b" >/dev/null \
    && echo "  merge onto master: clean" || echo "  merge onto master: CONFLICT"
done
```
