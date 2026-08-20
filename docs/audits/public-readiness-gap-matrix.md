# NosoGraph Public-Readiness Gap Matrix

**Date:** 2026-08-20  
**Baseline HEAD:** `063966540ea217bab8e4ff489830433fced2e3c9`

Legend: **PASS** = acceptable for public alpha; **GAP** = addressed in transformation; **DEFER** = documented P1/P2/P3 backlog.

| ID | Area | Finding | Severity | Status | Wave |
|----|------|---------|----------|--------|------|
| G-01 | Branding | README overclaims 10k+ modules as curated | P0 | GAP → fix | 2 |
| G-02 | Licensing | MIT license; Apache-2.0 required for OSS foundation | P0 | GAP → fix | 1 |
| G-03 | Legal | No NOTICE, trademark policy, separate data license docs | P1 | GAP → fix | 2 |
| G-04 | Governance | No GOVERNANCE.md, ROADMAP.md, CITATION.cff | P1 | GAP → fix | 2 |
| G-05 | Architecture | No public architecture docs | P1 | GAP → fix | 2 |
| G-06 | Source registry | No `data/sources/registry` | P1 | GAP → fix | 2 |
| G-07 | Messaging | “Medical Research Platform” not aligned with NosoGraph | P1 | GAP → fix | 2 |
| G-08 | Secrets | No hardcoded secrets found | — | PASS | 0 |
| G-09 | PHI | No patient data in repo | — | PASS | 0 |
| G-10 | CI | Lint + test + security jobs present | — | PASS | 0 |
| G-11 | Disease claims | 45+ L2 promoted vs 10k scaffold distinction unclear publicly | P1 | GAP → fix | 2 |
| G-12 | Package rename | `med_research` import path | P2 | DEFER | — |
| G-13 | CLI rename | `med-research` entry point | P2 | DEFER | — |
| G-14 | GitHub repo rename | Remote still `med-research` | P2 | DEFER | — |
| G-15 | mypy debt | Typecheck non-blocking | P2 | DEFER | — |
| G-16 | FHIR/OMOP | Not implemented | P3 | DEFER | — |
| G-17 | PyPI publish | Not automated | P3 | DEFER | — |
| G-18 | Billing/Stripe | Out of scope | — | N/A | 4 |
| G-19 | SLE defaults | Pipeline CLI defaults still `sle` | P2 | DEFER | 3 |
| G-20 | Evidence WS docstring | “SLE-first” in module docstring | P3 | DEFER | 3 |

## Release gate preview

| Gate | Pre-transform | Post-transform target |
|------|---------------|----------------------|
| A — Legal & licensing | FAIL | PASS (Apache-2.0 + data docs) |
| B — Security | PASS | PASS |
| C — Honest messaging | FAIL | PASS |
| D — Developer experience | PARTIAL | PASS |
| E — Test & CI | PASS | PASS |
| F — Architecture docs | FAIL | PASS |
| G — Biomedical integrity | PARTIAL | PASS |
| H — Branding | FAIL | PASS |
| I — Release artifacts | PARTIAL | PASS |

## Remediation ownership

All P0/P1 gaps in this matrix are addressed in the NosoGraph public-readiness transformation branch. P2/P3 items are recorded in `docs/audits/release-readiness-report.md` deferred backlog.
