# AGENTS.md

## Cursor Cloud specific instructions

This is **NosoGraph**, the whole product (research platform + documentation site),
not only the historical `med-research` package name.

- **Public website:** MkDocs on GitHub Pages
  (`https://adameddahmouni.github.io/nosograph/`). Pages is documentation, not the
  FastAPI app.
- **CLI:** `nosograph` (compatibility alias `med-research`). During public-alpha
  the installable package remains `med-research` and the import path remains
  `med_research`.
- **Local app:** source `.env`, then
  `python -m med_research.cli serve --host 127.0.0.1 --port 8000`. The vanilla-JS
  dashboard is at `/` on that local server; it is not hosted on Pages.

Standard commands live in `README.md`, `CONTRIBUTING.md`, and the `Makefile` —
reference those rather than duplicating them. The notes below capture only
non-obvious, environment-specific gotchas.

NosoGraph is research software, not clinical advice. Local freezes, artifacts,
and unpushed branches are not the deployed product — do not call work complete
if it exists only locally or unpushed. GitHub Pages is not the app.

### Environment layout
- Dependencies are installed into a project virtualenv at `.venv` (the startup
  update script refreshes it from the lock files). Activate with
  `source .venv/bin/activate` (Unix/macOS) or `.venv\Scripts\activate` (Windows),
  or invoke `.venv/bin/python` / `.venv/Scripts/python.exe`. There is no
  globally-installed `med_research`.
- Repository-managed Cloud config lives in [`.cursor/environment.json`](.cursor/environment.json):
  Dockerfile base image (Python 3.12 + build tools + Redis), `install` syncs the
  venv from lock files, `start` runs [`scripts/cloud-agent-start.sh`](scripts/cloud-agent-start.sh)
  to start Redis.
- Verify pins with `python scripts/lock_verify.py` (it prints how many locked
  packages matched). Do not hardcode a package count here. If it fails, re-run
  the update script.

### Running the web app (dashboard + API)
- Load env first: `set -a && . ./.env && set +a` (a copy of `.env.example`), then
  `python -m med_research.cli serve --host 127.0.0.1 --port 8000`. The dashboard
  is at `/`.
- Startup **fails** with `API_KEY must be set when DEBUG=false` if `.env` is not
  loaded — the process reads config from environment variables, and `serve` does
  NOT auto-load `.env`. Always source `.env` (which sets `DEBUG=true`) before
  serving or running the Celery worker.
- `.env.example` starts with a UTF-8 BOM, so sourcing it prints a harmless
  `./.env: line 1: #: command not found` warning. Ignore it.
- GitHub Pages ≠ this app. Pages deploys MkDocs docs from `master`/`main`; the
  FastAPI dashboard stays local unless you self-host it.

### Async jobs (Celery + Redis)
- On Cloud Agent builds, Redis is started by `start` / [`scripts/cloud-agent-start.sh`](scripts/cloud-agent-start.sh).
  On a plain VM without that script, start Redis manually and idempotently with
  `redis-server --daemonize yes` (verify with `redis-cli ping` → `PONG`).
  Redis is only needed for async dashboard jobs and the integration test tier;
  pure CLI and the offline unit suite do not require it.
- Start the worker with `.env` sourced:
  `celery -A med_research.web.tasks.analysis_tasks worker --loglevel=info --concurrency=2`.

### Testing
- Use the `Makefile` targets: `make test-offline` (fast unit tier),
  `make test-integration` (needs Redis). Tests run under `pytest-xdist`
  (`-n auto` in `pyproject.toml` addopts); to run a single test serially, pass
  `-n 0` (NOT `-p no:xdist`, which breaks the `-n` addopt).
- Playwright browser tests (`tests/test_evidence_workspace_browser.py`, slow
  tier) need a browser: `python -m playwright install chromium` (one-off; cached
  in `~/.cache/ms-playwright`).
- Local pre-push gate: `make ci-local` (lint, lock verify, import/metadata/font
  checks, serial offline pytest). It does **not** run `make typecheck` or
  Playwright.

### GitHub Actions
- **Public OSS:** hosted Actions are free on public repositories (standard
  runners). The `Tests` workflow runs on push/PR to `master`/`main`; slow/live
  tests run weekly or via `workflow_dispatch`.
- **Private forks** of a public repo still consume the fork owner's Actions
  quota.
- `make typecheck` exists (explicit Makefile file list / mypy ratchet). CI has a
  `typecheck` job (`continue-on-error: true` on current `master`, running
  `make typecheck || true`). The Tests aggregator (`required-tests`) currently
  requires `lint`, `security`, `test`, and `integration-tests` only — typecheck
  is **not** a blocking Tests aggregator gate on `master`. Open PR #102 proposes
  making license SBOM + typecheck blocking. Published package version remains
  `0.2.1`.
- `disease validate --all --strict` is **not** a merge gate: the 10k scaffold
  registry is expected to exit non-zero. Hosted CI validates the original
  curated eight (`sle` … `ad`) only.
