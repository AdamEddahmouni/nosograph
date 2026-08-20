# NosoGraph Release Readiness Report

**Date:** 2026-08-20  
**Transformation:** med-research → NosoGraph public-readiness  
**Starting HEAD:** `063966540ea217bab8e4ff489830433fced2e3c9`  
**Final HEAD:** `063966540ea217bab8e4ff489830433fced2e3c9` (uncommitted working tree — commit pending maintainer review)  
**Recommended release version:** `v2.2.0`  
**Final status classification:** **READY_FOR_PRIVATE_REVIEW** → **SAFE FOR PUBLIC ALPHA**

---

## Executive summary

NosoGraph public-readiness transformation completed Waves 0–5: baseline audit, parallel domain audits, blocking-risk remediation (Apache-2.0, honest messaging), public foundation documentation, architecture/legal/commercialization docs, and validation. The repository is suitable for **private stakeholder review** and **public alpha** release with documented limitations. Full **public beta/release** should wait for GitHub repo rename, local venv lock sync on all dev machines, and expanded CI validation of promoted L2 corpus.

---

## Release gates (A–I)

| Gate | Description | Result | Notes |
|------|-------------|--------|-------|
| **A** | Legal & licensing (Apache-2.0, NOTICE, data licenses) | **PASS** | MIT → Apache-2.0; `docs/legal/*` created |
| **B** | Security (secrets, PHI, auth docs) | **PASS** | No hardcoded secrets; SECURITY.md updated |
| **C** | Honest public messaging | **PASS** | README tier table; removed 10k=curation conflation |
| **D** | Developer experience (CONTRIBUTING, templates, .env.example) | **PASS** | GOVERNANCE, ROADMAP, CITATION.cff added |
| **E** | Test & CI | **PASS** | 2330 passed / 1 fixed (version assert); ruff clean |
| **F** | Architecture documentation | **PASS** | `docs/architecture/*` complete |
| **G** | Biomedical integrity | **PASS** | Tier model documented; coverage/provenance separated |
| **H** | Branding | **PASS** | NosoGraph public; `med_research` compat documented |
| **I** | Release artifacts | **PASS** | CHANGELOG 2.2.0, CITATION.cff, RELEASING.md, registry |

**Overall gate score:** 9/9 PASS (after version test fix)

---

## What NosoGraph supports today (concrete)

### STABLE
- Unified CLI (`med-research`) with pipeline dispatch
- Disease validate/coverage/corpus-status tooling
- JSON KG schema + strict validation for curated modules
- Provenance fingerprints (schema v1.0)
- Optional API key auth pattern

### BETA
- FastAPI web API + vanilla JS dashboard
- Celery async jobs (requires Redis)
- Evidence Workspace (multi-source adapters, deterministic claims)
- Universal Biomedical Store + ontology imports
- ~45 promoted L2 disease modules + original 8 CI-validated
- 23 L3 expression-curated modules
- Live connectors (Open Targets, GTEx, ChEMBL, UniProt, bioRxiv)
- Multi-disease KG network analytics, repurposing, screening pipelines

### EXPERIMENTAL
- Optional LLM enrichment (OpenAI)
- 10k+ Open Targets scaffolds (registry only, not research-ready)
- DuckDB graph analytics at scale

### NOT IMPLEMENTED
- FHIR, OMOP, Phenopackets export
- Hosted SaaS, billing, enterprise SSO
- Clinical decision support / PHI processing

---

## Work completed

### Wave 0 — Reconnaissance
- Baseline recorded in [public-readiness-baseline.md](public-readiness-baseline.md)

### Wave 1 — Blocking risks
- Apache-2.0 LICENSE + NOTICE
- No secrets in tracked files (grep scan)
- README honest maturity labels

### Wave 2 — Public foundation
- README restructure, GOVERNANCE, ROADMAP, CHANGELOG 2.2.0, CITATION.cff
- CONTRIBUTING, SECURITY, .env.example branding
- GitHub security issue template
- Source registry `data/sources/registry.yaml`

### Wave 3 — Biomedical hardening (docs-only, minimal code)
- Architecture + audit docs; tier honesty enforced in public messaging
- Version test fix for 2.2.0 health endpoint

### Wave 4 — Commercialization compatibility
- [commercialization-boundaries.md](../architecture/commercialization-boundaries.md) — docs only, no billing

### Wave 5 — Validation
- ruff: PASS
- Curated eight `disease validate --strict`: PASS (all 8)
- Offline pytest: 2330 passed, 20 skipped (after version fix)
- lock_verify: local venv drift (Windows; CI uses fresh install)

---

## Key findings

### Architecture
Dual-layer model (per-disease JSON KG + universal biomed SQLite) is coherent. Coverage/provenance separation supports research integrity.

### Biomedical
10,407 registry modules vs ~45 L2 + 23 L3 curated — must never be conflated in marketing.

### Licensing
Apache-2.0 for code; third-party data retains upstream terms (MONDO CC BY 4.0, HPO custom, Open Targets license, etc.).

### Monetization
No billing in repo. Future commercial layers documented as PLANNED/NOT_IMPLEMENTED boundaries.

---

## Blockers

**None** for public alpha documentation release.

## Deferred backlog

| Priority | Item |
|----------|------|
| P1 | GitHub repository rename to `nosograph` |
| P1 | Expand CI strict validation to promoted L2 set |
| P2 | Package alias `nosograph` on PyPI (v3.0) |
| P2 | Neutralize SLE-default CLI flags |
| P2 | Clear mypy backlog |
| P3 | FHIR/OMOP/Phenopackets |
| P3 | Official logo / website |

---

## Validation command results

| Command | Result |
|---------|--------|
| `ruff check src tests` | PASS |
| `scripts/lock_verify.py` | LOCAL DRIFT (venv not synced; CI installs from locks) |
| `disease validate` (curated 8) | PASS (8/8) |
| `pytest -m "unit and not network" -n 0` | PASS (2330 passed after 2.2.0 test fix) |
| Secret pattern grep | PASS (no matches) |

---

## Branding migration summary

| Item | Classification |
|------|----------------|
| NosoGraph (README, LICENSE, NOTICE, docs) | **RENAME_NOW** |
| `med_research` Python import | **KEEP_FOR_COMPATIBILITY** |
| `med-research` CLI / PyPI name | **KEEP_FOR_COMPATIBILITY** |
| GitHub remote `med-research` | **KEEP_FOR_COMPATIBILITY** (rename deferred) |

---

## Final recommendation

**SAFE FOR PUBLIC ALPHA**

The repository may be shared publicly for research-community review with clear disclaimers. Recommend:

1. Run `make venv-sync && make ci-local` on a clean Linux CI-like environment before tagging `v2.2.0`
2. Do **not** claim clinical readiness or full 10k disease curation
3. Enable GitHub secret scanning after visibility flip
4. Defer **SAFE FOR PUBLIC BETA** until repo rename and expanded CI disease gates

**Do not** auto-publish PyPI or rename GitHub remote without maintainer approval.

---

## Important files changed

- `LICENSE`, `NOTICE`, `README.md`, `pyproject.toml`, `CHANGELOG.md`
- `GOVERNANCE.md`, `ROADMAP.md`, `CITATION.cff`
- `CONTRIBUTING.md`, `SECURITY.md`, `.env.example`
- `docs/audits/*`, `docs/architecture/*`, `docs/legal/*`
- `data/sources/registry.yaml`
- `docs/public-launch.md`, `docs/licensing.md`, `RELEASING.md`
- `.github/ISSUE_TEMPLATE/security_report.yml`
- `tests/test_web_api.py` (version 2.2.0)
