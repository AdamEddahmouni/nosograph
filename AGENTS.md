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
  `all 67 locked packages match`. If it doesn't, re-run the update script.

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
- Playwright browser tests (`tests/test_evidence_workspace_browser.py`, slow tier) need a
  browser: `python -m playwright install chromium` (one-off; cached in `~/.cache/ms-playwright`).
