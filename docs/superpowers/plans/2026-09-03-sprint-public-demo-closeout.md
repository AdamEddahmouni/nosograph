# Sprint Plan — Public Demo Hardening (v0.2.1 → v0.3.0 transition)

**Branch:** `fix/security-remediation`
**Start date:** 2026-09-03
**Sprint length:** full sprint (smallest meaningful multi-week tranche; ~3 weeks of agentic work split into review gates)
**Theme:** make the repository leave the security-remediation branch in a state where the public demo is an allowed, auditable, self-contained product story rather than a scattered collection of security patches.

## Context

We are on `fix/security-remediation`. The recent history already includes a strong security-remediation run (cookie hardening, exception-detail suppression, XSS/CDE fixes, dependency pinning, SRI/CORS cleanup, Compare V2 readiness, and a side quest into demo scaffolding).

That side quest is now real work in the tree:

- `DEMO_MODE` policy slice: `src/med_research/web/demo_mode.py`, `config.py`, `middleware.py`, `main.py`, `.env.example`
- non-persisting Compare preview slice: `biomed/nosograph_compare/models.py`, `service.py`, web models/routers/services, and focused tests
- reproducible snapshot builder: `scripts/build_demo_snapshot.py` with `tests/test_demo_snapshot.py`
- new focused tests: `tests/web/test_demo_mode.py`, `tests/web/test_demo_compare_preview.py`

The working tree is currently **ahead of** `origin/fix/security-remediation` with staged-and-committed demo work plus unstaged edits on a few files (`.env.example`, `jobs.py`, `universal.py` services, etc.). The artifacts tree is huge and must stay out of the sprint.

## Goals

1. Close the public-demo implementation loop that is already partially built.
2. Ship a **single coherent demo story**: read-only policy, immutable snapshot, Compare preview, demo-aware metadata/UI, one-container demo profile, and deployment docs without committing secrets.
3. Make the demo usable without Redis/Celery for the flagship read-only surfaces.
4. Keep the existing security-remediation work intact and green.
5. Leave the repo on a merge-ready or clearly-labeled-napkin state, with the demo described honestly in public docs.

## Non-goals for this sprint

- Live external hosting setup (Heroku account, Azure setup, billing choices). Those are manual prerequisites.
- Shipping the full dashboard or full analysis module set to anonymous users.
- Persisted workspace/admin/job mutation on the public demo image.
- New runtime dependencies.
- PHI, secrets, tokens, or mutable user data in the image.
- Rewriting the existing Compare V2 persisted contract.

## Existing concrete plan we inherit

`docs/superpowers/plans/2026-09-03-public-demo.md` already decomposes the demo into 7 tasks. This sprint adopts that plan as the backbone and then adds the closure work around it.

The inherited tasks:

- Task 1: centralized demo configuration and deny-by-default policy
- Task 2: non-persisting Compare preview contract
- Task 3: immutable demo snapshot builder + startup validation
- Task 4: startup/metadata/dashboard demo-awareness
- Task 5: one-container local demo profile
- Task 6: deployment documentation without assuming a Heroku account
- Task 7: verification gate

## Sprint phases

### Phase 0: snapshot state and objective ratification

- Read the actual current diffs on the key demo files, not just the plan.
- Confirm what is already committed, what is staged, and what is locally edited.
- Decide whether the “public demo” story should close as one merged sprint or as a staged rollout with a napkin intermediate.
- Ratify the demo boundary in the sprint plan so later steps do not drift.

### Phase 1: verify the existing demo slices actually pass as written

- Run the focused demo tests that already exist.
- Run the same snapshot builder locally and inspect the manifest it produces.
- Run the existing Compare V2 coverage to ensure the preview work did not weaken it.
- Record any failures as sprint blockers, not side notes.

### Phase 2: complete the missing demo surface

**What we validated before touching code**

- The existing demo slices already pass as written in the venv:
  `tests/web/test_demo_mode.py` (17/17), `tests/web/test_demo_compare_preview.py` (9/9),
  `tests/test_demo_snapshot.py` (12/12), `tests/biomed/nosograph_compare/test_preview.py` (16/16).
- The snapshot builder runs offline and deterministic: `scripts/build_demo_snapshot.py` produced
  `.tmp-demo/biomedical.sqlite3` + `.tmp-demo/biomedical.manifest.json` with:
  - `snapshot_version: demo-c261bb954d784035`
  - `generated_at: 2026-09-03`
  - `supported_disease_ids: ['sle', 'ra', 'ibd', 'ms', 'ss', 'ssc', 't1d', 'ad']`
  - tables include `active_snapshots`, `resource_snapshots`, `entities`, `claims`, `claim_evidence`

**Decision made**

- This sprint completes **Task 4 metadata/readiness** first, because the missing surface is the
  demo-aware metadata/readiness path rather than the policy or preview contract.
- The dashboard banner and browser smoke (Task 4 UI sub-parts) stay explicitly deferred unless the
  repo already contains the static dashboard entry points we are allowed to edit.
- We do **not** invent a new demo image from scratch today. If `Dockerfile.demo` and `docker-compose.demo.yml`
  are absent, that becomes an explicit sprint gap rather than an implicit assumption.

**Concrete work done in this phase**

- Add `GET /api/demo_mode` and demo-aware `/api/ready` fields via `src/med_research/web/routers/system.py`.
- Add `DemoModeMetadata` and `ReadyResponse.demo` to `src/med_research/web/models/__init__.py`.
- Keep `/api/health` unchanged as a plain liveness check.
- Document in `docs/superpowers/plans/2026-09-03-public-demo.md` that browser smoke is deferred.

**Concrete work deferred**

- Static dashboard banner/disease-picker filtering (`index.html`/`dashboard.js`) — only if the
  repository already includes the files we are allowed to edit.
- Browser smoke assertions in `test_evidence_workspace_browser.py` / `test_evidence_explorer_ui.py`.

### Phase 3: one-container local demo profile

**Actual state**

- `Dockerfile.demo`, `docker-compose.demo.yml`, `tests/integration/test_demo_container.py`,
  and `docs/deployment-demo.md` are **not present** in the current tree.

**Decision made**

- Phase 3 is recorded as an **open sprint item**, not silently skipped and not faked via placeholder
  files. If the repo should have a demo container profile, it is a distinct follow-up task.
- The sprint can still close if the governance story says "demo middleware + preview + snapshot builder
  + metadata ready; container profile and deployment docs remain owner-facing setup or a later PR."

**Concrete work done in this phase**

- None emitted to the repository. Only the sprint record was updated to mark the missing pieces explicitly.

**Concrete work deferred**

- `Dockerfile.demo`
- `docker-compose.demo.yml`
- container contract tests
- packaged immutable snapshot copy into the image build step

### Phase 4: deployment documentation and public-facing honesty

**Actual state**

- `docs/deployment-demo.md`, `.github/workflows/demo-deploy.yml` are **not present**.
- Public surface still says the hosted demo is planned/not deployed in the current source tree we inspected.

**Decision made**

- We do not invent a deployment workflow or secrets setup path. That would overstate the sprint.
- We do adjust the sprint record so the public-facing honesty task names the exact doc updates that
  remain, rather than assuming they are done.

**Concrete work done in this phase**

- None emitted to the repository. The sprint record now explicitly lists the doc updates that still need
  a human decision (README demo status line, `docs/getting-started/demo.md`, deployment runbook).

**Concrete work deferred**

- `docs/deployment-demo.md`
- `.github/workflows/demo-deploy.yml` (manual `workflow_dispatch` only, secrets never committed)
- README and demo doc status wording, gated on whether we truly want to say “implementation available; hosting
  requires owner setup”

### Phase 5: cleanup and boundaries

- Remove or ignore demo-local artifacts that should not enter Git (`.tmp-demo/`, generated snapshots, browser artifacts, QA reports).
- Ensure the artifacts tree and the site-overhaul artifacts stay out of the committed story.
- Verify `Makefile`, lock files, and public metadata checks still agree.
- Make sure the branch narrative matches the commit narrative: security remediation first, then demo gating and demo product surface.

### Phase 6: final verification gate

**What we ran before finalizing**

- Focused demo tests: `tests/web/test_demo_mode.py`, `tests/web/test_demo_compare_preview.py`,
  `tests/test_demo_snapshot.py`, `tests/biomed/nosograph_compare/test_preview.py` — all passed.
- Local snapshot builder: `scripts/build_demo_snapshot.py --output .tmp-demo/biomedical.sqlite3` —
  created a validated snapshot + manifest.

**Still remaining before this sprint can be called fully closed**

- `make ci-local` against the full offline gate.
- Relevant Compare regression coverage.
- Browser smoke if Chromium is available.
- Final diff review for:
  - no leaked secrets
  - no committed mutable local databases
  - no deployed-provider assumptions baked into the repo
  - demo status described honestly in public docs

## Acceptance criteria

- A reviewer can read the branch and understand the demo boundary in one pass.
- The focused demo tests and existing regression tests pass together.
- The local demo container starts and serves the flagship read-only surfaces without Redis/Celery.
- Compare preview returns canonical result semantics without persisting a run.
- Public docs do not claim a live hosted demo unless that is actually true.
- The repo does not commit secrets, PHI, or mutable user data.
- The security-remediation branch still reads as a security-remediation branch, not a demo branch that accidentally absorbed security fixes.

## Risks and watch-outs

- The artifacts tree is large and actively growing; keep it out of the sprint narrative and out of the eventual PR/merge set.
- Do not let demo mode weaken the existing production behavior for `DEMO_MODE=false`.
- Do not let Compare preview become a weaker contract than the persisted Compare V2 result model.
- Do not automate the manual prerequisites (Heroku/Azure account creation) as if they were code.
- Do not claim a deployed public URL unless a real deployment smoke test passes.

## Suggested next steps

1. Read the current diffs on the demo slice and ratify the sprint boundary before executing anything else.
2. Run the already-written demo-focused tests and the snapshot builder locally.
3. Decide whether this sprint closes as a single merged trunk story or as a staged napkin first.
