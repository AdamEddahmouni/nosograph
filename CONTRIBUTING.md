# Contributing

Thank you for helping improve the med-research platform. This document covers the essentials for local development and pull requests.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating, you agree to uphold a respectful, inclusive community.

## Development setup

1. Clone the repository and create a virtual environment.
2. Sync dependencies to the locked environment:

   ```bash
   make venv-sync
   ```

3. Install the package in editable mode if you are not using the Makefile target above:

   ```bash
   python -m pip install -e .
   ```

4. Install pre-commit hooks (recommended):

   ```bash
   pip install pre-commit
   pre-commit install
   ```

See [README.md](README.md) for alternative install paths and CLI usage.

## Branch and pull request workflow

- Branch from `main` using prefixes: `feature/`, `fix/`, or `docs/`
- Keep PRs focused; link related issues when applicable
- Before opening a PR, run:

  ```bash
  make lint
  make test-offline
  ```

- Fill out the pull request template checklist
- Ensure CI passes (lint, tests, lock-check, 80% coverage gate)

## Security

Do **not** open public issues for security vulnerabilities. See [SECURITY.md](SECURITY.md) for the private reporting process.

## Running tests

Fast offline suite (excludes `slow` and `integration` markers):

```bash
make test-offline
```

Equivalent:

```bash
python -m pytest tests/ -m "not slow" -q
```

Report-related changes should pass the neutral-terminology tests so non-SLE diseases do not leak unrelated lupus/SLE copy:

```bash
python -m pytest tests/test_report_neutral_terminology.py -q
```

Add deterministic unit tests for new behavior. Prefer fixtures and mocks over live external API calls in the default test job.

## Disease context

New analysis modules, HTML reports, and user-facing exports must respect the active disease via `disease_context(disease_id)` from `med_research.pipeline.reporting`. Use `ctx_disease` for the full display name, `ctx_report_name` for short report titles, and pass `disease_id` through CLI, API, and report generators. Do not hardcode SLE/lupus labels in shared code paths.

## User-facing output

- Computational results are hypotheses for research, not clinical recommendations.
- Do not present outputs as medical advice, diagnosis, or treatment guidance.
- Keep provenance and limitations visible where results depend on heuristics, caches, or incomplete data.

## Known follow-ups

See [TECHNICAL_DEBT_ISSUES.md](TECHNICAL_DEBT_ISSUES.md) for the historical audit, resolved items, and remaining open work. Re-verify issues against the current tree before implementing large changes.

For disease-module curation (validate, coverage, expression consensus, screening profiles), see [docs/disease-curation.md](docs/disease-curation.md).

For self-hosted deployment, see [docs/deployment.md](docs/deployment.md).
