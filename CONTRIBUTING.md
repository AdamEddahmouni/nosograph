# Contributing

Thank you for helping improve **NosoGraph — Disease Intelligence. Connected.** NosoGraph is open-source research software for connecting disease knowledge, evidence, and provenance across biomedical sources. The Python package still installs as `med-research` with import path `med_research` during the compatibility transition. This document covers local development and pull requests.

## Contribution paths

| Path | Start |
|------|--------|
| Code | This file + [docs/contributing/code.md](docs/contributing/code.md) |
| Disease / data curation | [docs/disease-curation.md](docs/disease-curation.md) + the Disease curation issue template |
| Documentation | `pip install -r requirements-docs.txt` then `mkdocs serve`; see [docs/contributing/index.md](docs/contributing/index.md) |

Newcomers: look for `good first issue` and `help wanted`. Do not open public issues with secrets or PHI.

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

- Branch from `master` using prefixes: `feature/`, `fix/`, or `docs/`
- Keep PRs focused; link related issues when applicable
- Before opening a PR, run:

  ```bash
  make ci-local
  ```

  (`make lint` + `make test-offline` cover most of the same checks.)
- Fill out the pull request template checklist
- Ensure GitHub Actions `Tests` passes on your PR (public repos receive free hosted runners)

## Security

Do **not** open public issues for security vulnerabilities. See [SECURITY.md](SECURITY.md) for the private reporting process.

## Running tests

Fast offline suite (excludes `slow` and `network` tests):

```bash
make test-offline
```

Equivalent:

```bash
python -m pytest tests/ -m "unit and not network" -q
```

Fast unit tests (excluding `slow` and `integration`):

```bash
make test-fast
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

## License

By contributing code, documentation, or other materials to this repository, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE), the same license that covers the project. See [docs/legal/licensing-model.md](docs/legal/licensing-model.md) for how software licensing relates to third-party biomedical data.
