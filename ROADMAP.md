# NosoGraph Roadmap

Status key: **STABLE** | **BETA** | **EXPERIMENTAL** | **PROTOTYPE** | **PLANNED** | **NOT_IMPLEMENTED**

## Current release focus (v2.2.x)

- [x] Public-readiness documentation and Apache-2.0 licensing
- [x] Honest disease tier messaging
- [x] Architecture and legal doc set
- [ ] GitHub repository rename (`med-research` → `nosograph`) — **PLANNED**, maintainer action
- [ ] Package alias `nosograph` on PyPI — **PLANNED** v3.0

## Near term (P1)

| Item | Status |
|------|--------|
| Expand CI strict validation to promoted L2 corpus | PLANNED |
| Neutralize SLE-default CLI flags | PLANNED |
| Official NosoGraph logo & website | PLANNED |
| GitHub Discussions Q&A | PLANNED |

## Medium term (P2)

| Item | Status |
|------|--------|
| Clear mypy backlog (`TECHNICAL_DEBT_ISSUES.md`) | PLANNED |
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

## Out of scope

- Clinical decision support products
- PHI / EHR ingestion
- Full 10k scaffold manual curation
