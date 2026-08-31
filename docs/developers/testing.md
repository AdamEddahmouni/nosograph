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
| `make test-integration` | Redis | Integration behavior across async and persistence boundaries. |
| `make test-browser` | Playwright Chromium | Deterministic dashboard and Evidence Explorer workflows. |
| `make typecheck` | Mypy environment | Informational typecheck while the backlog is cleared. |

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
