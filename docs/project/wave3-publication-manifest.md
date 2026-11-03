# Wave 3 publication manifest

Local, un-pushed state at the end of the Wave 3 session. Nothing in this file
describes a hosted or published artifact: no branch below has been pushed, no
pull request exists for any of them, and no remote check has run against any
commit here. Regenerate every SHA with `git rev-parse <branch>` before acting on
it.

## Verified bases

| Ref | SHA | How it was verified |
|-----|-----|---------------------|
| `origin/master` | `2b9a5bae316ce8c73d5e76d414ab2ea371241b4a` | `git fetch origin --prune`, then `git rev-parse origin/master` |
| PR #116 head | `e67768cacaa52038e546952f8e70aac76c2a163b` | `git ls-remote origin refs/pull/116/head` |
| Wave 2 integration | `0386f1c5009a54995ec96b718e0c107ce2e095e3` | `feat/parallel-wave2` |
| Wave 3 integration | `a507162a26ebca2591eda6768c5e72e21b320f92` | `feat/parallel-wave3` |

**Correction to the Wave 2 manifest.** Wave 2 analysed against
`4c60dd611ade008a6b0258190c8785d128c598aa`. Current remote master is
`2b9a5bae3`, one commit ahead: the completed mypy ratchet (#115). Every
candidate below was rebuilt from `2b9a5bae3` and every result was re-measured on
that tree.

## Publication candidates

All five were created fresh from current `origin/master`; none carries PR #116
ancestry. `git merge-base origin/master <branch>` equals `2b9a5bae3` for all of
them.

| # | Branch | HEAD | Commits | Source commits (cherry-picked with `-x`) | Proposed base | Tested on master-based tree |
|---|--------|------|---------|------------------------------------------|---------------|------------------------------|
| 1 | `pub/hpoa-sync-source` | `3aa7dcb580bc27f7591755c894ea0756aa1b37ad` | 1 | `6167ce20c` | `master` | yes |
| 2 | `pub/mondo-sync-source` | `99aadeb4ea31d6da4381a54f45bec02dac333012` | 2 | `6167ce20c`, `afd64a73c` | **branch 1** | yes |
| 3 | `pub/disease-validation-gate` | `1d11627c7fab1e569497ee22bfbaeaead2a5767d` | 1 | `fada676cf` | `master` | yes |
| 4 | `pub/evidence-coverage` | `38dd6a1d46d251e6f29981e055f70a199e524d9d` | 3 | `aa4dd32d9`, `a507162a2`, `d302bee5c` | `master` | yes |
| 5 | `pub/atlas-evidence` | `130a1b32b7a8de009ee0c51b873749b90ce5718f` | 7 | `c0e3ec172`, `560535444`, `f890fa839`, `aa4dd32d9`, `a507162a2`, `d302bee5c`, `3e37209a3` | `master` after 4 and 6 merge | yes |

## Test evidence per candidate

These are commands actually executed in this session, on the branch named, with
`PYTHONPATH` pointed at that branch's tree so the import could not silently
resolve to the main checkout.

| Candidate | Command | Result |
|-----------|---------|--------|
| 1 | `pytest tests/biomed/sync/ -n 0` | 30 passed |
| 1 | `ruff check` / `ruff format --check` / `mypy hpoa.py` | clean |
| 2 | `pytest tests/biomed/sync/ -n 0` | 60 passed |
| 3 | `pytest tests/test_validation_batch.py -n 0` | 13 passed |
| 3 | `disease validate --all --tier reference --json` | exit 0, 6/6 |
| 3 | `disease validate --all --tier ci_validated --strict` | exit 0, 8/8 |
| 3 | two seeded `--sample 5 --seed 3` runs | identical selection and summary; only `generated_at` differs |
| 3 | typecheck ratchet | 294 files, `Success` |
| 4 | `pytest tests/test_evidence_coverage.py tests/test_corpus_status.py` | 24 passed |
| 4 | typecheck ratchet | 296 files, `Success` |
| 5 | `pytest tests/test_evidence_coverage.py tests/test_corpus_status.py tests/test_dashboard_styles.py` | 36 passed |
| 5 | `pytest tests/test_dashboard_a11y_browser.py -m "slow and browser"` | 21 passed |

What these results do **not** establish: hosted CI, CodeQL, GitHub Pages, or the
Docker image. Nothing here has run in GitHub Actions.

## Publication order

```text
origin/master (2b9a5bae3)
  ├── 1  pub/hpoa-sync-source            -> master
  │     └── 2  pub/mondo-sync-source     -> branch 1  (target master only after 1 merges)
  ├── 3  pub/disease-validation-gate     -> master
  └── 4  pub/evidence-coverage           -> master

       PR #116 (feat/demo-safety-infra @ e67768cac)
         └── hosting readiness 2a7263653 -> #116
               └── docker harness 2c29e9446, f68e92210 -> hosting-readiness branch

master + 6 (dashboard stack: c0e3ec172, 560535444, f890fa839)
         └── 5  pub/atlas-evidence       -> single commit 3e37209a3 after 4 and 6 merge
```

### Why the dashboard stack is a prerequisite for the Atlas

`pub/atlas-evidence` contains seven commits only because it has to prove the
combination works. Its publishable delta is the single Atlas commit
`3e37209a3`; the other six belong to branches 4 and 6. Once those merge, the
Atlas branch should be recreated from `master` and carry only that commit, so
the Atlas PR does not restate dashboard or coverage content.

`f890fa839` is not optional decoration. It defines the `_open_dashboard` test
helper that the accessibility suite needs; without it seven browser tests fail
with "element(s) not found" on a master-based tree. It was found by running the
stack, not by reading it.

### Why branches 1 and 3 are independent of PR #116

Branch 1 touches six files, none of which differ between `master` and
`e67768cac`. Branch 3 touches four files; only `src/med_research/cli.py`
differs, and the edits sit in different regions. Both were cherry-picked onto
`2b9a5bae3` with no conflict and tested there.

### Why branch 2 is stacked on branch 1

`afd64a73c` updates the expected sync-source list in
`tests/biomed/sync/test_hpoa_sync.py` and extends the registry that branch 1
introduces. Applied directly to `master` it conflicts; applied on top of
branch 1 it is clean and its tests pass (60 passed).

### Why the Docker harness is stacked on PR #116

`scripts/docker_smoke.py` does not exist on `master`.
`2a7263653` (hosting readiness) conflicts on `master` on `Dockerfile`,
`Dockerfile.demo`, `docker-compose.demo.yml`, `config.py`, and `main.py`, and
applies cleanly to `e67768cac`. The harness commits build on that file, so the
whole group stays behind PR #116.

### Commits that are not independent candidates

| Commit | Why it is not its own PR |
|--------|--------------------------|
| `158eaa611` (widen ratchet, docs nav) | Touches `Makefile` and `mkdocs.yml`, which the integration branches already modify; it registers pages that only exist there. |
| `0386f1c50` (CLI phenotype export) | Conflicts on `master` because it extends `cli.py` alongside the Wave 2 evidence export it depends on. |
| `240c3de5a` (docker-smoke target, ratchet) | `Makefile`-only, and the target it adds drives a script that does not exist on `master`. |
| `4183b39e1` (Wave 1 manifest) | Documentation of local state; superseded by this file. |

## Duplicate-content warning

`feat/parallel-wave3` is the integration branch and is **not** a PR candidate.
It contains PR #116 ancestry plus every Wave 1 and Wave 2 commit. Publishing it
alongside branches 1-5 would duplicate all of their content.

## Known limitations

- No candidate has been pushed, so no hosted check, review, or merge simulation
  has run against any of them.
- Branch 5's browser tests run against a static file server, not the FastAPI
  app. They exercise the real render functions and the real DOM, but not the
  network path.
- Branch 4's report was measured on the checked-in corpus sample. It has not
  been run over the full 10,404-module registry, which would take roughly 40
  minutes at the observed ~24 ms per module.
- The fresh Docker image build did not complete in this session (see the
  Wave 3 engineering report). Branch 3's Docker-adjacent behaviour is therefore
  established by tests and by a cached image, not by a current-source build.

## Regenerating this analysis

```bash
git fetch origin --prune
BASE=$(git rev-parse origin/master)
for b in pub/hpoa-sync-source pub/mondo-sync-source pub/disease-validation-gate \
         pub/evidence-coverage pub/atlas-evidence; do
  printf '%-32s head=%s base=%s\n' "$b" "$(git rev-parse "$b")" \
    "$(git merge-base "$BASE" "$b")"
done
```

Every `base=` value must equal `$BASE`. If one does not, that branch has been
rebased onto another candidate and the order above no longer holds.
