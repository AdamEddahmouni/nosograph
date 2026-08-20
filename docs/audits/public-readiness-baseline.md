# NosoGraph Public-Readiness Baseline

**Audit date:** 2026-08-20  
**Starting HEAD:** `063966540ea217bab8e4ff489830433fced2e3c9`  
**Branch:** `master` (clean working tree, tracking `origin/master`)  
**Remote:** `https://github.com/AdamEddahmouni/med-research.git`  
**Transformation target:** **NosoGraph** — *The Open Computational Map of Human Disease*

---

## Repository state at baseline

| Item | Value |
|------|-------|
| Package name (PyPI/CLI) | `med-research` |
| Python import path | `med_research` |
| Version | `2.1.0` |
| License (baseline) | MIT |
| Python | 3.11–3.12 |
| Disease module directories | 10,407 |
| Default branch | `master` |
| CI workflow | `.github/workflows/test.yml` (lint, security, test 3.11/3.12, integration) |

## Technology stack

- **Runtime:** Python 3.11+, FastAPI, Uvicorn, Celery, Redis
- **Data:** SQLite (evidence workspace, universal biomedical store), DuckDB analytics, JSON disease KGs
- **Frontend:** Vanilla JavaScript dashboard (`src/med_research/web/static/`)
- **Testing:** pytest, pytest-xdist, Playwright (slow tier), ruff, mypy (informational)
- **Lock files:** `requirements-lock.txt`, `requirements-dev-lock.txt` (68 packages verified by `scripts/lock_verify.py`)
- **Containers:** Dockerfile, docker-compose.yml

## Repository layout (high level)

```text
src/med_research/          # Application source (CLI, diseases, pipeline, biomed, web)
tests/                     # Unit, integration, browser tests
docs/                      # Usage docs + superpowers design archives
scripts/                   # Lock verify, disease batch, biomed imports
data/                      # Runtime DBs (gitignored); reports under data/reports/
.github/                   # CI, issue/PR templates, CODEOWNERS
```

## Disease corpus maturity (honest baseline)

| Tier | Count (approx.) | Meaning |
|------|-----------------|--------|
| **L0** | Majority of 10k+ | Open Targets scaffold; incomplete KG/config |
| **L1** | Subset | Partial KG or config gaps |
| **L2** | ~45 promoted + 18 legacy curated | Strict validation pass (symptoms, queries, CAR-T, safety) |
| **L3** | 23 (`CURATED_CONSENSUS_DISEASES`) | L2 + hand-curated GEO expression consensus |
| **CI gate** | 8 only | `sle`, `ra`, `ibd`, `ms`, `ss`, `ssc`, `t1d`, `ad` |

**Important:** README baseline overclaimed “10,403+ disease modules” as research-ready. Scaffold count ≠ curated count.

## Biomedical model (baseline)

- Per-disease JSON KGs: `profile`, `genes`, `drugs`, `pathways`, `relationships`
- Disease configs in `config.py` (symptoms, PubMed/trial/GWAS queries, CAR-T, safety, screening)
- Universal Biomedical Schema v1 (`med_research.biomed`): MONDO, HPO, HPOA, GO, Reactome, Uberon, ClinVar, openFDA imports
- Evidence Workspace: multi-source adapters, deterministic claims, optional LLM enrichment
- Provenance: `pipeline/provenance.py` (schema v1.0, SHA-256 fingerprints)

## Evidence & provenance (baseline)

- **STABLE:** Provenance metadata, coverage contracts, evidence deduplication
- **BETA:** Evidence Workspace dossier ranking, LLM extraction (optional, requires API key)
- **EXPERIMENTAL:** Some pipeline modules default to `sle` disease context in CLI defaults

## Security baseline

- `.env` gitignored; `.env.example` documents secrets (`API_KEY`, `AUTH_SESSION_SECRET`, optional `OPENAI_API_KEY`)
- Secret pattern grep: no hardcoded API keys or AWS tokens found in tracked files
- Bandit + pip-audit in CI
- Research-only framing in SECURITY.md; no PHI by design

## Licensing baseline

- Source: MIT (to migrate to Apache-2.0)
- Third-party data: documented in `docs/licensing.md` (MONDO CC BY 4.0, HPO custom, Open Targets, NCBI, etc.)
- Disease JSON compilations: project license for schema/compilation; underlying facts subject to source terms

## Documentation baseline

| Present | Missing (pre-transformation) |
|---------|---------------------------|
| README, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, CHANGELOG | GOVERNANCE, ROADMAP, CITATION.cff |
| docs/licensing.md, deployment.md, api-reference.md | docs/audits/*, docs/architecture/*, docs/legal/* |
| docs/public-launch.md, disease-curation.md | data/sources/registry |
| RELEASING.md | NOTICE (Apache attribution) |

## CI & quality baseline

- `make ci-local`: ruff check/format, lock verify, import audit, serial offline pytest (80% coverage gate in CI)
- `make test-offline`: unit tests, no network
- Disease validate `--all --strict`: expected non-zero on 10k scaffold registry (documented in AGENTS.md)
- mypy: informational only (`TECHNICAL_DEBT_ISSUES.md` backlog)

## Branding baseline

| Surface | Current name | Target |
|---------|--------------|--------|
| Public docs / README | Medical Research Platform / med-research | **NosoGraph** |
| Python package | `med_research` | **KEEP_FOR_COMPATIBILITY** (document alias) |
| CLI entry point | `med-research` | **KEEP_FOR_COMPATIBILITY** |
| GitHub remote | `med-research` | Rename deferred (not in scope) |

## Secrets & data governance scan (baseline)

- No `.env` tracked
- Runtime DB paths gitignored (`data/*.sqlite3`)
- No PHI patterns audited in repo content
- OpenAI key placeholders commented in `.env.example` only

## Validation commands to run post-transformation

```bash
make venv-sync          # or pip install -r requirements-lock.txt && pip install -e .
make ci-local
python -m med_research.cli disease validate sle --strict
python -m med_research.cli disease validate ra --strict
# ... remaining curated eight
```

---

*This document is the Wave 0 snapshot. See companion audits under `docs/audits/` for gap analysis and remediation tracking.*
