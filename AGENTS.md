# AGENTS.md

## Cursor Cloud specific instructions

This is `med-research`, a Python 3.11+ FastAPI + Celery biomedical research platform with a
unified CLI (`med_research.cli`), a vanilla-JS web dashboard, and a pytest suite. Standard
commands live in `README.md`, `CONTRIBUTING.md`, and the `Makefile` — reference those rather
than duplicating them. The notes below capture only non-obvious, environment-specific gotchas.

### Environment layout
- Dependencies are installed into a project virtualenv at `.venv` (the startup update script
  refreshes it from the lock files). Activate it (`source .venv/bin/activate`) or use
  `.venv/bin/python` for every command; there is no globally-installed `med_research`.
- Repository-managed Cloud config lives in [`.cursor/environment.json`](.cursor/environment.json):
  Dockerfile base image (Python 3.12 + build tools + Redis), `install` syncs the venv from lock
  files, `start` runs [`scripts/cloud-agent-start.sh`](scripts/cloud-agent-start.sh) to start Redis.
- The pinned toolchain is exact: `python scripts/lock_verify.py` should report
  `all 68 locked packages match`. If it doesn't, re-run the update script.

### Running the web app (dashboard + API)
- Load env first: `set -a && . ./.env && set +a` (a copy of `.env.example`), then
  `python -m med_research.cli serve --host 127.0.0.1 --port 8000`. The dashboard is at `/`.
- Startup **fails** with `API_KEY must be set when DEBUG=false` if `.env` is not loaded — the
  process reads config from environment variables, and `serve` does NOT auto-load `.env`.
  Always source `.env` (which sets `DEBUG=true`) before serving or running the Celery worker.
- `.env.example` starts with a UTF-8 BOM, so sourcing it prints a harmless
  `./.env: line 1: #: command not found` warning. Ignore it.

### Async jobs (Celery + Redis)
- On Cloud Agent builds, Redis is started by `start` / [`scripts/cloud-agent-start.sh`](scripts/cloud-agent-start.sh).
  On a plain VM without that script, start Redis manually and idempotently with
  `redis-server --daemonize yes` (verify with `redis-cli ping` → `PONG`).
  Redis is only needed for async dashboard jobs and the integration test tier; pure CLI and
  the offline unit suite do not require it.
- Start the worker with `.env` sourced:
  `celery -A med_research.web.tasks.analysis_tasks worker --loglevel=info --concurrency=2`.

### Testing
- Use the `Makefile` targets: `make test-offline` (fast unit tier), `make test-integration`
  (needs Redis). Tests run under `pytest-xdist` (`-n auto` in `pyproject.toml` addopts); to run
  a single test serially, pass `-n 0` (NOT `-p no:xdist`, which breaks the `-n` addopt).
- `-n auto` is capped to what free RAM can hold (see `pytest_xdist_auto_num_workers` in
  `tests/conftest.py`): every worker is a separate interpreter holding ~600 MB of imported
  scientific stack, so on a high-core/low-memory machine the CPU count can oversubscribe
  memory and get a worker killed mid-test. The cap only ever lowers the count and falls back
  to xdist's default when memory can't be read; override it with
  `PYTEST_XDIST_AUTO_NUM_WORKERS=<n>`, and note an explicit `-n <n>` is never adjusted.
- Playwright browser tests (`tests/test_evidence_workspace_browser.py`, slow tier) need a
  browser: `python -m playwright install chromium` (one-off; cached in `~/.cache/ms-playwright`).

### GitHub Actions
- **Public OSS:** hosted Actions are free on public repositories (standard runners).
  The `Tests` workflow runs on push/PR to `master`/`main`; slow/live tests run weekly
  or via `workflow_dispatch`.
- **Private forks** of a public repo still consume the fork owner's Actions quota.
- Local pre-push gate: `make ci-local` (matches hosted lint + offline pytest; serial,
  skips Playwright browser tests).
- `make typecheck` is informational only in CI until the mypy backlog in
  `TECHNICAL_DEBT_ISSUES.md` is cleared.
- `disease validate --all --strict` is **not** a merge gate: the 10k scaffold registry is
  expected to exit non-zero. Hosted CI validates the original curated eight (`sle` … `ad`) only.

### Releases and versioning
- Releases are automated with Release Please from Conventional Commits on `master`.
  Read [RELEASING.md](RELEASING.md) before touching anything release-related; the
  contributor-facing summary is [docs/contributing/releasing.md](docs/contributing/releasing.md).
- Write Conventional Commit subjects (`feat(scope): …`, `fix: …`, `docs: …`). The next
  version is derived from the subject line: `feat` → MINOR, `fix`/`perf` → PATCH, a
  `BREAKING CHANGE:` footer or `!` → MINOR while pre-1.0, everything else → no release.
  Verify with `make commitlint`; preview classification and version with `make release-plan`.
- Never hand-edit a version. `pyproject.toml` is the source of truth; the release PR
  synchronizes `src/med_research/__init__.py`, `CITATION.cff`, `codemeta.json`, and
  `docs/generated/public-status.yaml`. `scripts/check_public_metadata.py` fails on drift,
  and the remaining prose surfaces are updated inside the release PR by a maintainer.
- Do not create a release, push a tag, publish a package, or rewrite published tags,
  release history, or released changelog sections unless a maintainer explicitly asks.
- Treat the versioned public surface as a compatibility contract: `/api/v1` routes, the
  CLI, environment variables, and serialized data formats.
- Release automation lives in `release-please-config.json`, `.release-please-manifest.json`,
  and `.github/workflows/release-please.yml`.
