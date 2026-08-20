# Public Launch Checklist (NosoGraph)

Use this list when flipping the repository to **public** on GitHub. NosoGraph is Apache-2.0 licensed and intended for open research use. The GitHub remote may still be named `med-research` until renamed by maintainers.

## Before you change visibility

Run locally:

```bash
make venv-sync
make ci-local
```

Confirm:

- No secrets in tracked files (`.env` is gitignored; use `.env.example` only).
- No PHI or patient-identifiable data in commits.
- Runtime databases under `data/` are not version-controlled.
- README honestly describes disease tier maturity (registry ≠ curation).
- [docs/audits/release-readiness-report.md](audits/release-readiness-report.md) gates reviewed.

## GitHub repository settings

1. **General → Change repository visibility → Public**
2. **Settings → Actions → General** — allow workflows
3. **Settings → Security** — enable Dependabot alerts, secret scanning
4. **Settings → General → Features** — enable Issues (templates under `.github/ISSUE_TEMPLATE/`)
5. **About box** — Description: *NosoGraph — The Open Computational Map of Human Disease*
6. **Topics:** `bioinformatics`, `drug-discovery`, `fastapi`, `python`, `computational-biology`, `open-science`, `knowledge-graph`, `disease-ontology`

## Branch protection (recommended)

On `master`:

- Require pull request before merging
- Require status checks: `lint`, `security`, `test (3.11)`, `test (3.12)`, `integration-tests`
- Do **not** require `typecheck` until mypy backlog cleared

## After going public

1. Create GitHub Release from `v2.2.0` per [RELEASING.md](../RELEASING.md)
2. Confirm README badge is green on `master`
3. Optionally rename repository to `nosograph` (update URLs in docs)

## What stays out of scope

- FHIR / OMOP / Phenopackets (PLANNED)
- Billing / Stripe (NOT_IMPLEMENTED)
- Clinical decision support or PHI processing

## Support channels

- **Bugs / features:** GitHub Issues
- **Security:** Private advisory — never public issues
- **Governance:** [GOVERNANCE.md](../GOVERNANCE.md)
