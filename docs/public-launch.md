# Public launch checklist

Use this list when flipping [med-research](https://github.com/AdamEddahmouni/med-research) to a **public** GitHub repository. The codebase is MIT-licensed and intended for open research use.

## Before you change visibility

Run locally (or on a Cloud Agent):

```bash
make venv-sync
make ci-local
```

Confirm:

- No secrets in tracked files (`.env` is gitignored; use `.env.example` only).
- No PHI or patient-identifiable data in commits.
- Runtime databases under `data/` are not version-controlled (`data/evidence_workspace.sqlite3`, `data/biomedical.sqlite3`).
- Coverage reports omit the 10k scaffold disease `config.py` / `data/` tree (see `pyproject.toml` `[tool.coverage.run]`).

## GitHub repository settings

1. **General → Change repository visibility → Public**
   - Public repos receive **free GitHub-hosted Actions** on standard runners (fair-use limits apply).
   - Private forks of a public repo still bill the fork owner's quota.

2. **Settings → Actions → General**
   - Allow all actions and reusable workflows (or restrict to verified creators if you prefer).

3. **Settings → Security → Code security and analysis**
   - Enable **Dependabot alerts** and **Dependabot security updates**.
   - Enable **Secret scanning** (available on public repos).

4. **Settings → General → Features**
   - Enable **Issues** (bug/feature templates live under `.github/ISSUE_TEMPLATE/`).
   - Optionally enable **Discussions** for Q&A.

5. **About box (repository home)**
   - Description: multi-disease computational drug discovery / biomedical research platform.
   - Website: link to README or docs.
   - Topics: `bioinformatics`, `drug-discovery`, `fastapi`, `python`, `computational-biology`, `open-science`.

6. **Default branch**
   - This repository uses `master` as the default branch. Align branch protection and docs with that name.

## Branch protection (recommended)

On `master`:

- Require pull request before merging.
- Require status checks: `lint`, `security`, `test (3.11)`, `test (3.12)`, `integration-tests`.
- Do **not** require `typecheck` until the mypy backlog in `TECHNICAL_DEBT_ISSUES.md` is cleared (job is informational only).
- Require branches to be up to date before merge.

## After going public

1. Merge the Wave 3/4 readiness PR and close superseded draft PRs (#12, Dependabot #1–#9 if already applied in-tree).
2. Confirm the README badge links to Actions and turns green on `master`.
3. Create the first GitHub Release from `v2.1.0` (or bump per [RELEASING.md](../RELEASING.md)).
4. Post a short release note: research-only disclaimer, Python 3.11–3.12, `make venv-sync` quick start.

## What stays out of scope for contributors

- Live GEO matrix download and multi-disease AutoDock Vina PDB packs (see CHANGELOG "Remaining ideas").
- Phenopacket / FHIR / OMOP interop (needs a design cycle).
- Using the platform with real PHI or for clinical decision support (see [SECURITY.md](../SECURITY.md)).

## Support channels

- **Bugs / features:** GitHub Issues (use templates).
- **Security:** [Private advisory](https://github.com/AdamEddahmouni/med-research/security/advisories/new) — never public issues.
- **Questions:** GitHub Discussions (if enabled) or Issues with the `question` label.
