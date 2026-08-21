# NosoGraph Roadmap

Status key: **STABLE** | **BETA** | **EXPERIMENTAL** | **PROTOTYPE** | **PLANNED** | **NOT_IMPLEMENTED**

## Current release (v2.3.0 — Public Alpha)

Shipped in v2.3.0 (2026-08-21):

- [x] Disease-general core (explicit disease selection, identifier resolution)
- [x] Canonical `nosograph` CLI alias (legacy `med-research` retained)
- [x] Batch strict validation and curation tiers
- [x] NosoGraph Compare initial vertical slice (engine + API + dashboard panel)
- [x] Claim/evidence/provenance API traceability (golden trace)
- [x] Source-sync framework + Open Targets dry-run (hosted workflow proven)
- [x] P1-0 hosted CI baseline

## Near term (post-v2.3.0)

| Item | Status |
|------|--------|
| Evidence Workspace UX / polished provenance explorer | PLANNED |
| NosoGraph Compare productization (standalone workflow) | PLANNED |
| Public hosted demo deployment (P1-H) | PLANNED |
| Full registry status refresh (10k scaffold scan) | PLANNED |
| Package/distribution rename (`med-research` → `nosograph` on PyPI) | PLANNED v3.0 |
| Official NosoGraph logo & website | PLANNED |
| GitHub Discussions Q&A | PLANNED |

## Medium term (P2)

| Item | Status |
|------|--------|
| Clear mypy backlog (`TECHNICAL_DEBT_ISSUES.md`) | PLANNED |
| Source-sync expansion beyond Open Targets slice | PLANNED |
| Phenopacket export prototype | PLANNED |
| Automated SPDX license report in CI | PLANNED |
| PyPI publish workflow | PLANNED |

## Long term (P3)

| Item | Status |
|------|--------|
| FHIR Evidence resource export | NOT_IMPLEMENTED |
| OMOP concept mapping | NOT_IMPLEMENTED |
| Hosted SaaS / enterprise SSO | NOT_IMPLEMENTED (see [commercialization boundaries](docs/architecture/commercialization-boundaries.md)) |
| Stripe billing | NOT_IMPLEMENTED |

## Disease curation expansion

Contributor-driven — not pre-complete. See [docs/disease-curation.md](docs/disease-curation.md).

Target: grow L2/L3 corpus via validated PRs, not bulk auto-promotion of scaffolds.

**v2.3.0 baseline:** 88/88 L2 modules pass strict validation; registry size (10,407) ≠ curation depth.

## Completed (v2.2.x)

- [x] Public-readiness documentation and Apache-2.0 licensing
- [x] Honest disease tier messaging
- [x] Architecture and legal doc set
- [x] GitHub repository at `AdamEddahmouni/nosograph`

## Out of scope

- Clinical decision support products
- PHI / EHR ingestion
- Full 10k scaffold manual curation
