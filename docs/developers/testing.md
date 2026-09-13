---
title: Testing
description: Run NosoGraph's offline, integration, browser, typecheck, and local CI validation tiers.
---

# Testing

NosoGraph separates fast offline checks from infrastructure-dependent and browser checks. Test counts describe software validation coverage; they are not evidence of scientific validity.

## Local gates

Use the repository's local gate before a contribution:

```bash
make ci-local
```

The release metadata records 2,445 offline tests selected in the v0.2.1 release suite. That number is a gate selection, not a claim about total test coverage or biomedical correctness.

## Test tiers

| Command | Requirement | Purpose |
|---|---|---|
| `make test-offline` | Python environment | Fast unit tier without Redis. |
| `make test-integration` | Redis | Offline integration (fixture-backed). The target sets `CELERY_TASK_ALWAYS_EAGER=true` like hosted CI, so job-lifecycle tests do not need a Celery worker. A live worker is still required for production-shaped async jobs. |
| `make test-browser` | Playwright Chromium | Deterministic dashboard and Evidence Explorer workflows. |
| `make typecheck` | Mypy environment | Explicit Makefile file-list ratchet. After PR #102, CI has a strict standalone `typecheck` job (no `continue-on-error`). The Tests aggregator requires `lint`, `security`, `test`, `integration-tests`, and `typecheck`, so typecheck is **merge-blocking** via the required `Tests` check. License-check/SBOM runs in the `security` job. `make ci-local` runs lint, locks, license policy, import/metadata/font/harvest checks, and serial offline pytest; it does not run typecheck or Playwright. |
| `python scripts/check_registry_harvest.py` | Python environment | Harvest catalog vs on-disk disease-module drift (also part of `make ci-local` and the lint job). |

For a single pytest test, pass `-n 0` because the project config enables xdist by default. Browser tests that exercise the dashboard are separate from the offline CLI path.

## Documentation checks

```bash
.venv/Scripts/python.exe -m mkdocs build --strict
.venv/Scripts/python.exe scripts/check_public_fonts.py
.venv/Scripts/python.exe scripts/check_public_metadata.py
```

Use `.venv/bin/python` on macOS/Linux.

## Continue

- [Local development](local.md) for environment and service setup.
- [Contributing code](../contributing/code.md) for the expected validation before a pull request.
