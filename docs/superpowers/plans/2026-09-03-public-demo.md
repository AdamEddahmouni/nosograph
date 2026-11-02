# Public Read-Only Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe, immutable, low-cost `DEMO_MODE` and deploy the Evidence Explorer and Compare preview as the first public NosoGraph demo.

**Architecture:** Keep normal self-hosted behavior unchanged when `DEMO_MODE=false`. In demo mode, a centralized middleware policy exposes only snapshot-backed reads and a non-persisting Compare preview; the demo image contains a validated fixture-backed biomedical SQLite snapshot and runs one web process without Celery or Redis. Deployment is provider-neutral, with Heroku as the first target after the owner creates an account and confirms the GitHub Student Developer Pack offer, and Azure Container Apps as the fallback.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLite, vanilla JavaScript, Docker, Docker Compose, GitHub Actions, Heroku Container Registry, and existing pytest/Playwright tooling.

## Global Constraints

- `DEMO_MODE` defaults to `false`; existing non-demo routes and persistence behavior remain unchanged.
- Demo mutation requests return HTTP `403` with machine-readable error code `demo_read_only`.
- The persisted Compare V2 response model is not weakened; preview uses a dedicated response model with `run_id: null` and `preview: true`.
- Demo requests never call live Open Targets, PubMed, ClinicalTrials.gov, other external connectors, LLM services, or Celery.
- The demo dataset is immutable at runtime, labeled with its snapshot version/date, and validated at startup.
- `DEBUG=false` still requires a strong operator `API_KEY`; the key is never sent to public users.
- No new runtime dependency is added.
- No PHI, secrets, tokens, or user-owned data is included in the image.
- The public demo is cloud-hosted; the owner’s home machine is not a production host.
- Heroku account creation, Student Pack enrollment, app creation, billing choice, and deployment secrets are manual prerequisites and must not be assumed or automated.
- Every implementation task ends with focused tests; commits require explicit user authorization during execution.

---

## File map

Create or modify only the following files unless an existing test reveals a necessary adjacent contract:

- Create: `src/med_research/web/demo_mode.py` — centralized demo-mode configuration and route policy helpers.
- Modify: `src/med_research/web/config.py` — parse `DEMO_MODE` and demo snapshot settings.
- Modify: `src/med_research/web/middleware.py` — enforce the demo policy before handlers run.
- Modify: `src/med_research/web/main.py` — register the demo middleware and configure demo startup.
- Modify: `src/med_research/web/routers/system.py` and its response models — expose demo/snapshot metadata and demo-aware readiness.
- Modify: `src/med_research/web/routers/universal.py` — add non-persisting Compare preview and preview exports.
- Modify: `src/med_research/web/models/universal.py` — add preview request/response models.
- Modify: `src/med_research/biomed/nosograph_compare/service.py` and `models.py` — separate pure comparison calculation from persistence.
- Create: `scripts/build_demo_snapshot.py` — reproducibly build and validate the fixture-backed demo SQLite database.
- Create: `Dockerfile.demo` — one-container image with the immutable demo snapshot.
- Create: `docker-compose.demo.yml` — local production-like demo profile without Redis/Celery.
- Modify: `src/med_research/web/static/index.html` and `dashboard.js` — demo banner, tier filtering, and hidden mutation controls.
- Modify: `.env.example` — document `DEMO_MODE` and snapshot variables.
- Create: `docs/deployment-demo.md` — local, Heroku, and Azure fallback deployment runbook.
- Create: `.github/workflows/demo-deploy.yml` — manual Heroku deployment workflow gated on repository secrets.
- Create or modify: focused tests under `tests/web/`, `tests/biomed/nosograph_compare/`, `tests/integration/`, and the existing dashboard browser test files.

## Task 1: Add centralized demo configuration and deny-by-default policy

**Files:**
- Create: `src/med_research/web/demo_mode.py`
- Modify: `src/med_research/web/config.py`
- Modify: `src/med_research/web/middleware.py`
- Modify: `src/med_research/web/main.py`
- Modify: `.env.example`
- Test: `tests/web/test_demo_mode.py`

**Interfaces:**
- `med_research.web.config.DEMO_MODE: bool`
- `med_research.web.config.DEMO_SNAPSHOT_VERSION: str`
- `med_research.web.demo_mode.is_demo_mode() -> bool`
- `med_research.web.demo_mode.is_demo_allowed_path(path: str, method: str) -> bool`
- `med_research.web.demo_mode.demo_read_only_response() -> JSONResponse`
- `DemoModeMiddleware` implements the existing Starlette middleware dispatch contract.

- [ ] **Step 1: Write failing policy tests.**

Add tests that build the existing FastAPI app with `DEMO_MODE=true` and assert:

```python
def test_demo_blocks_job_submission(client):
    response = client.post("/api/jobs/run-all", params={"disease_id": "sle"})
    assert response.status_code == 403
    assert response.json()["code"] == "demo_read_only"


def test_demo_allows_health_and_condition_reads(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/v1/conditions/search", params={"q": "lupus"}).status_code == 200


def test_demo_blocks_persisted_compare_but_allows_preview(client):
    persisted = client.post(
        "/api/v1/nosograph/comparisons",
        json={"condition_curies": ["MONDO:0005290", "MONDO:0008383"]},
    )
    preview = client.post(
        "/api/v1/nosograph/comparisons/preview",
        json={"condition_curies": ["MONDO:0005290", "MONDO:0008383"]},
    )
    assert persisted.status_code == 403
    assert preview.status_code != 403
```

Cover these blocked families explicitly: `/api/jobs`, `/api/workspace`,
`/api/admin`, `/api/system/cache`, LLM extraction, evidence gathering, live
source operations, notification writes, and persisted comparison writes.

- [ ] **Step 2: Run the focused tests and verify failure.**

Run:

```bash
python -m pytest tests/web/test_demo_mode.py -n 0 -q
```

Expected: FAIL because `DEMO_MODE`, the policy helper, and the middleware do
not yet exist.

- [ ] **Step 3: Implement the configuration and policy.**

Parse booleans using the repository’s existing case-insensitive environment
convention. Define one policy response:

```python
def demo_read_only_response() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={
            "code": "demo_read_only",
            "detail": "This operation is disabled in the public read-only demo.",
        },
    )
```

Use an explicit allow-list for demo API paths. Allow health/readiness, system
metadata, supported condition/claim/evidence/provenance/snapshot reads, and
the preview endpoints. Reject every mutation method and every blocked route
family before the route handler executes. The preview path is the only
allowed `POST`.

- [ ] **Step 4: Register the middleware and document environment values.**

Register `DemoModeMiddleware` in `web/main.py` before route handling and add
these entries to `.env.example`:

```dotenv
# Public snapshot-backed demo mode. Keep false for normal self-hosting.
DEMO_MODE=false
DEMO_SNAPSHOT_VERSION=
```

Keep the existing production `API_KEY` startup check intact.

- [ ] **Step 5: Run the focused tests and the auth regression tests.**

Run:

```bash
python -m pytest tests/web/test_demo_mode.py tests/test_web_auth.py tests/test_web_auth_api.py -n 0 -q
```

Expected: all tests pass, including a test proving `DEMO_MODE=false` preserves
the existing behavior.

- [ ] **Step 6: Commit the policy slice if authorized.**

```bash
git add src/med_research/web/demo_mode.py src/med_research/web/config.py \
  src/med_research/web/middleware.py src/med_research/web/main.py \
  .env.example tests/web/test_demo_mode.py
git commit -m "feat: add public demo read-only policy"
```

## Task 2: Add a non-persisting Compare preview contract

**Files:**
- Modify: `src/med_research/biomed/nosograph_compare/models.py`
- Modify: `src/med_research/biomed/nosograph_compare/service.py`
- Modify: `src/med_research/web/models/universal.py`
- Modify: `src/med_research/web/routers/universal.py`
- Test: `tests/biomed/nosograph_compare/test_preview.py`
- Test: `tests/web/test_demo_compare_preview.py`

**Interfaces:**
- `NosoGraphCompareService.compare_many_preview(condition_curies: list[str], *, dimensions: list[str] | None = None) -> CompareV2PreviewResult`
- `NosoGraphComparePreviewRequest`
- `NosoGraphComparePreviewResultView`
- `POST /api/v1/nosograph/comparisons/preview`
- `POST /api/v1/nosograph/comparisons/preview/export?format=json|markdown`

- [ ] **Step 1: Write the pure-computation and persistence-isolation tests.**

Use the existing biomedical repository fixtures and record the research-run
count before and after:

```python
def test_compare_preview_does_not_create_research_run(repository):
    before = repository.list_research_runs(limit=1).total
    result = NosoGraphCompareService(repository).compare_many_preview(
        ["MONDO:0005290", "MONDO:0008383"]
    )
    assert result.run_id is None
    assert result.preview is True
    assert repository.list_research_runs(limit=1).total == before
```

Add API assertions for two-to-five conditions, invalid conditions, invalid
dimensions, deterministic repeated JSON, and deterministic Markdown export.

- [ ] **Step 2: Run the new tests and verify failure.**

Run:

```bash
python -m pytest tests/biomed/nosograph_compare/test_preview.py tests/web/test_demo_compare_preview.py -n 0 -q
```

Expected: FAIL because no preview model, service method, or route exists.

- [ ] **Step 3: Extract comparison calculation from persistence.**

Refactor `compare_many()` so the shared calculation creates the normalized
conditions, cohort context, dimensions, warnings, status, and fingerprint
without writing. Keep the existing `compare_many()` method responsible for
creating and completing `ResearchRun`. Add `compare_many_preview()` that
returns the same calculated fields with:

```python
run_id = None
preview = True
```

Do not change the persisted `CompareV2Result` or its response model.

- [ ] **Step 4: Add preview models, routes, and exports.**

The preview response model must mirror the persisted fields while explicitly
declaring:

```python
run_id: UUID | None = None
preview: bool = True
```

The export route must validate the same request body, call the non-persisting
service method, and render JSON or Markdown from the returned result. It must
not accept a saved run identifier.

- [ ] **Step 5: Run comparison regression coverage.**

Run:

```bash
python -m pytest tests/biomed/nosograph_compare tests/web/test_nosograph_compare_v2_api.py \
  tests/biomed/nosograph_compare/test_preview.py tests/web/test_demo_compare_preview.py -n 0 -q
```

Expected: existing persisted Compare tests and all preview tests pass.

- [ ] **Step 6: Commit the preview slice if authorized.**

```bash
git add src/med_research/biomed/nosograph_compare \
  src/med_research/web/models/universal.py \
  src/med_research/web/routers/universal.py \
  tests/biomed/nosograph_compare/test_preview.py \
  tests/web/test_demo_compare_preview.py
git commit -m "feat: add non-persisting compare preview"
```

## Task 3: Build and validate the immutable demo snapshot

**Files:**
- Create: `scripts/build_demo_snapshot.py`
- Modify: `src/med_research/web/config.py`
- Test: `tests/test_demo_snapshot.py`

**Interfaces:**
- `build_demo_snapshot(output: Path, *, fixture_root: Path) -> Path`
- CLI: `python scripts/build_demo_snapshot.py --output <path>`
- `DEMO_SNAPSHOT_PATH` environment variable, defaulting to the image’s
  `/app/demo-data/biomedical.sqlite3` path.

- [ ] **Step 1: Write snapshot-builder tests.**

Test that the builder:

1. creates a SQLite database from the checked-in MONDO/HPO/HPOA fixtures;
2. imports the eight CI-validated/reference demo disease modules
   (`sle`, `ra`, `ibd`, `ms`, `ss`, `ssc`, `t1d`, and `ad`);
3. writes the expected schema and active snapshots;
4. is idempotent;
5. fails clearly when a required fixture is missing; and
6. does not call network APIs.

Use `monkeypatch` to make any external connector raise an assertion if
invoked.

- [ ] **Step 2: Run snapshot tests and verify failure.**

Run:

```bash
python -m pytest tests/test_demo_snapshot.py -n 0 -q
```

Expected: FAIL because the builder and demo snapshot setting do not exist.

- [ ] **Step 3: Implement the offline builder using existing import services.**

Reuse the repository’s existing biomedical initialization and fixture import
paths rather than duplicating SQL schema creation. The script must:

- accept an explicit output path;
- remove only the output file it is creating;
- initialize the canonical schema;
- import checked-in fixtures;
- validate the eight supported disease modules;
- write a manifest containing snapshot version, source fixture names,
  checksums, generated-at date, and supported disease IDs;
- return a non-zero exit code with an actionable message on failure.

- [ ] **Step 4: Add runtime snapshot validation.**

When `DEMO_MODE=true`, startup must check that `DEMO_SNAPSHOT_PATH` exists,
opens successfully, contains the required tables and active snapshots, and
matches the manifest. No runtime import or network fallback is allowed.

- [ ] **Step 5: Run snapshot tests and direct CLI verification.**

Run:

```bash
python -m pytest tests/test_demo_snapshot.py tests/test_kg_schema_validation.py -n 0 -q
python scripts/build_demo_snapshot.py --output .tmp-demo/biomedical.sqlite3
```

Expected: tests pass and the command creates a validated local snapshot. Do
not add `.tmp-demo/` or its database to Git.

- [ ] **Step 6: Commit the snapshot builder if authorized.**

```bash
git add scripts/build_demo_snapshot.py src/med_research/web/config.py \
  tests/test_demo_snapshot.py
git commit -m "feat: add reproducible demo snapshot builder"
```

## Task 4: Make startup, metadata, and the dashboard demo-aware

**Files:**
- Modify: `src/med_research/web/routers/system.py`
- Modify: system response models in `src/med_research/web/models/`
- Modify: `src/med_research/web/main.py`
- Modify: `src/med_research/web/static/index.html`
- Modify: `src/med_research/web/static/dashboard.js`
- Test: `tests/web/test_demo_metadata.py`
- Test: existing dashboard browser tests

**Interfaces:**
- Health/readiness metadata includes `demo_mode`, `snapshot_version`, and
  supported demo disease IDs.
- Demo startup readiness does not require Redis, Celery, or workspace DB.
- The dashboard renders a fixed snapshot banner and hides disabled actions.

- [ ] **Step 1: Write metadata and readiness tests.**

Assert that demo health/readiness:

```python
def test_demo_readiness_does_not_require_redis(client):
    response = client.get("/api/ready")
    assert response.status_code == 200
    assert response.json()["demo_mode"] is True
    assert response.json()["snapshot_version"]
```

Add a startup failure test for a missing or invalid immutable snapshot and a
non-demo regression test that retains the existing dependency checks.

- [ ] **Step 2: Implement demo metadata and readiness.**

Add the metadata to existing response models without removing current fields.
Use the validated snapshot manifest as the source of the version/date. Keep
`/api/health` as liveness and make only `/api/ready` demo-aware.

- [ ] **Step 3: Add the visible demo boundary to the UI.**

On initial dashboard load, read system metadata and render:

```text
PUBLIC DEMO · FIXED RESEARCH SNAPSHOT · DATA DATE: <date>
```

Filter the disease picker to the supported CI-validated/reference IDs, show
curation-tier labels, disable job/workspace/admin controls, and preserve the
research-only disclaimer. The UI must not merely hide controls while still
issuing their requests.

- [ ] **Step 4: Add browser assertions.**

Extend the existing deterministic browser fixture so one flow:

1. opens the dashboard;
2. sees the demo banner and snapshot date;
3. searches for a supported condition;
4. opens a claim;
5. filters evidence;
6. opens provenance;
7. runs Compare preview for two conditions; and
8. verifies no job or workspace write request is made.

- [ ] **Step 5: Run focused API and browser tests.**

Run:

```bash
python -m pytest tests/web/test_demo_metadata.py tests/test_evidence_explorer_ui.py -n 0 -q
python -m pytest tests/test_evidence_workspace_browser.py -n 0 -q
```

Expected: all focused tests pass; browser tests require Chromium installed.

- [ ] **Step 6: Commit the demo-aware product surface if authorized.**

```bash
git add src/med_research/web/routers/system.py src/med_research/web/models \
  src/med_research/web/main.py src/med_research/web/static/index.html \
  src/med_research/web/static/dashboard.js tests/web/test_demo_metadata.py \
  tests/test_evidence_explorer_ui.py tests/test_evidence_workspace_browser.py
git commit -m "feat: expose snapshot-backed public demo surface"
```

## Task 5: Package a one-container local demo

**Files:**
- Create: `Dockerfile.demo`
- Create: `docker-compose.demo.yml`
- Modify: `.gitignore`
- Test: `tests/integration/test_demo_container.py`

**Interfaces:**
- `docker build -f Dockerfile.demo -t nosograph-demo .`
- `docker compose -f docker-compose.demo.yml up --build`
- The demo container listens on the platform-provided `PORT`.

- [ ] **Step 1: Write container-contract tests.**

Add tests or shell-backed integration checks that verify:

- the demo image contains the snapshot and manifest;
- `DEMO_MODE=true` and `DEBUG=false` are set;
- the app starts without Redis/Celery;
- `/api/health`, `/api/ready`, `/`, and Compare preview respond;
- a blocked job request returns the `demo_read_only` contract; and
- the runtime user cannot modify the packaged snapshot.

- [ ] **Step 2: Create the demo image.**

Base it on the existing locked dependency image, run
`build_demo_snapshot.py` during image construction, set
`DEMO_SNAPSHOT_PATH` to the packaged file, retain the non-root user, and use
the existing CLI server entrypoint. Do not change the default `Dockerfile`
behavior used by normal local Compose.

- [ ] **Step 3: Create the no-Redis Compose profile.**

Define one `web` service in `docker-compose.demo.yml`, map a configurable host
port, pass `DEMO_MODE=true`, and do not declare Redis, worker, Beat, or a
writable `./data` mount. Add a healthcheck using `/api/health`.

- [ ] **Step 4: Run the local demo smoke test.**

Run:

```bash
docker build -f Dockerfile.demo -t nosograph-demo .
docker compose -f docker-compose.demo.yml up --build -d
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/ready
docker compose -f docker-compose.demo.yml down
```

Expected: the health and readiness responses are successful, the app serves
the dashboard, and no Redis or Celery container is started.

- [ ] **Step 5: Commit the local container profile if authorized.**

```bash
git add Dockerfile.demo docker-compose.demo.yml .gitignore \
  tests/integration/test_demo_container.py
git commit -m "feat: add single-container demo profile"
```

## Task 6: Document and prepare deployment without assuming a Heroku account

**Files:**
- Create: `docs/deployment-demo.md`
- Create: `.github/workflows/demo-deploy.yml`
- Modify: `README.md`
- Modify: `docs/getting-started/demo.md`
- Test: documentation/link checks and workflow syntax validation

**Interfaces:**
- Manual prerequisite checklist for Heroku account and GitHub Student Pack.
- Manual Heroku deployment path using the already-built demo image.
- Manual Azure Container Apps fallback path.
- No deployment secret values committed to the repository.

- [ ] **Step 1: Write the deployment documentation.**

Document this exact prerequisite gate before any deployment command:

1. Create or sign in to a Heroku account.
2. Confirm the GitHub Student Developer Pack Heroku offer is active.
3. Create the Heroku app and choose whether to use the student credit.
4. Configure `API_KEY`, `CORS_ORIGINS`, `DEMO_MODE=true`,
   `DEMO_SNAPSHOT_VERSION`, and the platform `PORT` behavior.
5. Add `HEROKU_API_KEY` and `HEROKU_APP_NAME` only as repository secrets.

Document the cost boundary: one Eco web dyno for the read-only app, no Redis,
no Postgres, no worker, no paid API keys, and a shutdown/deletion procedure.
Also document Azure Container Apps as the fallback, including scale-to-zero,
one replica, free-grant caveats, credit monitoring, and explicit shutdown.

- [ ] **Step 2: Add a manual-only deployment workflow.**

Create a `workflow_dispatch` workflow that:

- has `contents: read` permissions;
- builds `Dockerfile.demo`;
- logs into Heroku using secrets;
- pushes the image to the Heroku Container Registry;
- releases the `web` process; and
- runs health/readiness smoke checks.

The workflow must fail clearly when either secret is absent and must not run on
ordinary pushes or pull requests.

- [ ] **Step 3: Update public entry-point documentation.**

Change the demo status from “planned” to “implementation available; hosting
requires owner setup” only after the local demo profile passes. Keep the
public hosted URL marked unavailable until a real deployment smoke test passes.

- [ ] **Step 4: Run docs and workflow checks.**

Run:

```bash
python scripts/check_public_metadata.py
python -m mkdocs build --strict
git diff --check
```

Expected: all checks pass and no secret or local deployment artifact appears in
the diff.

- [ ] **Step 5: Commit deployment preparation if authorized.**

```bash
git add docs/deployment-demo.md .github/workflows/demo-deploy.yml \
  README.md docs/getting-started/demo.md
git commit -m "docs: prepare public demo deployment"
```

## Task 7: Run the complete verification gate

**Files:**
- No source changes expected; update release/status documentation only if
  verification changes a documented fact.

- [ ] **Step 1: Run focused demo tests.**

```bash
.venv/Scripts/python.exe -m pytest tests/web/test_demo_mode.py \
  tests/web/test_demo_compare_preview.py \
  tests/web/test_demo_metadata.py \
  tests/test_demo_snapshot.py \
  tests/biomed/nosograph_compare \
  -n 0 -q --tb=short
```

Expected: all focused tests pass.

- [ ] **Step 2: Run the repository gate.**

```bash
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/python.exe -m ruff format --check src tests
.venv/Scripts/python.exe scripts/lock_verify.py
make lock-check
.venv/Scripts/python.exe scripts/check_imports.py
.venv/Scripts/python.exe scripts/check_public_metadata.py
.venv/Scripts/python.exe scripts/check_public_fonts.py
.venv/Scripts/python.exe -m pytest tests/ -m "unit and not network and not slow" -q --tb=short -n 0 --ignore=tests/test_evidence_workspace_browser.py
```

Expected: lint, formatting, lock verification, import audit, public metadata,
public font checks, and the serial offline suite pass.

- [ ] **Step 3: Run the browser gate.**

```bash
.venv/Scripts/python.exe -m pytest tests/test_evidence_workspace_browser.py \
  tests/test_evidence_explorer_ui.py -n 0 -q --tb=short
```

Expected: the demo browser flow and existing UI flows pass with no retry-based
workaround.

- [ ] **Step 4: Review the final diff and deployment boundary.**

Confirm that:
- this branch ends with a deployed, immutable, read-only public demo and a
  documented deployment runbook rather than open security checkboxes;
- the `fix/security-remediation` history references this sprint as the first
  time the public surfaces combine a demo policy, snapshot-backed dataset,
  and a non-persisting Compare preview;
- the release note ships the demo as **implementation available; hosting
  requires owner setup**, not as deployed live on a specific provider;
- no provider secrets, account names, or local deployment artifacts appear in
  the committed diff.
**Files:**
- No source changes expected; update release/status documentation only if
  verification changes a documented fact.

- [ ] **Step 1: Run focused demo tests.**

```bash
python -m pytest tests/web/test_demo_mode.py \
  tests/web/test_demo_compare_preview.py \
  tests/web/test_demo_metadata.py \
  tests/test_demo_snapshot.py \
  tests/biomed/nosograph_compare \
  -n 0 -q --tb=short
```

Expected: all focused tests pass.

- [ ] **Step 2: Run the repository gate.**

```bash
make ci-local
```

Expected: lint, formatting, lock verification, import audit, public metadata,
public font checks, and the serial offline suite pass.

- [ ] **Step 3: Run the browser gate.**

```bash
python -m pytest tests/test_evidence_workspace_browser.py \
  tests/test_evidence_explorer_ui.py -n 0 -q --tb=short
```

Expected: the demo browser flow and existing UI flows pass with no retry-based
workaround.

- [ ] **Step 4: Review the final diff and deployment boundary.**

Confirm that:
- this branch ends with a deployed, immutable, read-only public demo and a
  documented deployment runbook rather than open security checkboxes;
- the `fix/security-remediation` history references this sprint as the first
  time the public surfaces combine a demo policy, snapshot-backed dataset,
  and a non-persisting Compare preview;
- the release note ships the demo as **implementation available; hosting
  requires owner setup**, not as deployed live on a specific provider;
- no provider secrets, account names, or local deployment artifacts appear in
  the committed diff.
- only intended files changed;
- the untracked `artifacts/` directory was not added;
- no snapshot database, credentials, or generated reports are tracked;
- demo mode cannot reach jobs, workspace writes, admin writes, live APIs, or
  LLM extraction;
- normal self-hosted mode remains unchanged; and
- Heroku account setup remains a documented manual prerequisite.

- [ ] **Step 5: Record the release readiness result.**

Update `docs/project/status.md`, `docs/getting-started/demo.md`, and the
changelog only with verified facts. Do not claim a public URL until a hosted
smoke test has succeeded.

## Execution prerequisite

Implementation can begin without a Heroku account by completing Tasks 1–5 and
the local verification portions of Tasks 6–7. The Heroku account and Student
Pack offer are needed only for the final hosted deployment step. Once the
account exists, deployment requires the owner to supply the app name and
repository secrets; the implementation plan does not assume or create them.
