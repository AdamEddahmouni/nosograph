# NosoGraph Post-v2.3 Roadmap Assessment

**Status:** COMPLETE  
**Assessment date:** 2026-08-21  
**Baseline release:** v2.3.0 (`ff1ea223b`)  
**Maturity:** PUBLIC_ALPHA  
**Starting master HEAD:** `ff1ea223b`  
**Assessment branch HEAD:** (this PR)

---

## Executive summary

NosoGraph v2.3.0 is a **technically credible public-alpha biomedical platform** with strong foundations: disease-general core, strict validation, claim/evidence/provenance APIs, NosoGraph Compare engine, and Open Targets source-sync proof. It is **not yet a research product** — the dashboard exposes infrastructure alongside partial differentiators, Evidence Explorer UX is shallow, Compare is an experimental slice, and no public demo exists.

**Recommendation:** P2 theme = **Evidence-Native Research Experience**. Build Evidence Explorer and Compare V2 as flagship surfaces first, stabilize Playwright/demo-blocking debt in parallel, then launch a read-only public demo. Defer temporal models, full computational modeling, FHIR/OMOP, Workbench collaboration, and autonomous hypothesis generation.

---

## Immediate housekeeping

### Release audit PR

| Item | Status |
|------|--------|
| Branch | `docs/v2.3.0-release-audit-final` |
| Commit | `a1c04e6e7` — finalize v2.3.0 audit record with tag and CI proof |
| Change | `docs/audits/v2.3.0-release.md` (+5/−3 lines) |
| Accuracy | Verified against tag `v2.3.0` @ `ff1ea223b`, CI run 32507860773 PASS |
| PR | Merged via this assessment PR (includes audit commit) |

### Generated local artifacts

| File | Classification | Action |
|------|----------------|--------|
| `data/reports/validation_l2_sample.json` | VERSION_CONTROLLED | Keep tracked |
| `data/reports/validation_reference.json` | VERSION_CONTROLLED | Keep tracked |
| `data/reports/validation_batch_report.json` | VERSION_CONTROLLED | Restored to HEAD (local edit reverted) |
| `data/reports/validation_l2_full.json` | CI_ARTIFACT_ONLY | Added to `.gitignore`; do not commit |
| `data/tmp_test_biomed.sqlite3` | ACCIDENTAL_LOCAL | Added to `.gitignore` |
| `test-offline-*.txt` | ACCIDENTAL_LOCAL | Added to `.gitignore` |
| Pipeline `*/data/*.json`, `report.html` | IGNORED_GENERATED | Already in `.gitignore` |
| `data/chroma/`, `data/evidence_workspace.sqlite3` | IGNORED_GENERATED | Already in `.gitignore` |

### Stash inventory (read-only; not dropped)

| Stash | Branch | Classification | Notes |
|-------|--------|----------------|-------|
| `stash@{0}` | `p1/disease-general-core` | **OBSOLETE** | Single-line change to `validation_batch_report.json`; superseded by tracked reports |
| `stash@{1}` | `master` @ `0696088` | **ALREADY_MERGED** | Pre-v2.3 migration WIP (66 files); content integrated via P1/v2.3 releases |

### Baseline record (2026-08-21)

| Item | Value |
|------|-------|
| Release tag | `v2.3.0` @ `ff1ea223b` |
| Master HEAD | `ff1ea223b` |
| Open PRs | Dependabot mypy bump only (#14) |
| Worktrees | Single worktree on assessment branch |
| Latest master CI | Run 32507860773 — PASS (lint, security, test, integration) |
| L2 strict validation | 88/88 pass |
| Registry size | ~10,407 scaffolds |
| mypy | 61 errors (informational ceiling) |
| Playwright slow suite | 12 pass / 10 fail (structure-modal intercept + timing) |

---

## Current product assessment

### What an outside researcher can do today

**Via dashboard (requires Redis/Celery for async):**

- Run Evidence-to-Hypothesis Workspace dossiers (BETA) — strongest end-to-end workflow
- Browse 10k disease corpus by curation tier (Corpus Health)
- Explore disease-local KG (search, paths, centrality)
- Run 15+ analysis module jobs (repurposing, bioinformatics, trials, etc.)
- Search universal conditions and view claim chips (Condition Explorer)
- Compare two MONDO conditions across 5 dimensions (experimental panel)
- Graph analytics (DuckDB paths, target ranking, topology)
- Export module JSON/HTML; workspace review bundles (ZIP)

**Via CLI/API (often easier or only path):**

- Sync workspace dossiers without Celery (`nosograph workspace`)
- Batch strict validation, corpus status, coverage reports
- Biomed init/import/sync (`biomed sync open_targets --dry-run`)
- Full claim provenance drill-down (`GET /api/v1/claims/{id}/provenance`)
- Live external lookups, cache admin, disease admin prune/restore
- All 8 workspace source adapters (UI exposes 4)

**Cannot do convincingly today:**

- Answer "why does NosoGraph claim X?" in a polished, filterable Evidence Explorer
- Run a standalone Compare research workflow with exports and evidence drill-down
- Use a public hosted instance without self-hosting Docker + Redis
- Trust scaffold-tier diseases for deep research (10k registry ≠ curation)
- Rely on Playwright CI for UI regression confidence

### Strengths

1. **Evidence-native architecture** — claim → evidence → provenance → source chain exists and is tested
2. **Honest curation tiers** — L0–L3 + ci_validated semantics are formal and validated
3. **Disease-general platform** — no inappropriate SLE default; identifier resolution centralized
4. **Source-sync framework** — nine-stage lifecycle proven with Open Targets hosted dry-run
5. **Compare semantics** — explicit missingness (`NOT_RECORDED` ≠ `KNOWN_ABSENT`); no fake similarity score
6. **Rich pipeline modular** — 15+ analysis modules with registry, CLI, API, tests
7. **Apache-2.0 OSS core** — commercialization boundaries documented; core remains forkable

### Weaknesses

1. **Split evidence stacks** — universal biomed claims vs Evidence Workspace claims are not unified
2. **Monolithic dashboard IA** — researcher, operator, and universal-map flows mixed in one scroll
3. **Shallow provenance UX** — API complete; UI is `<details>` panels, not a product surface
4. **Compare incomplete** — engine exists; no workflow, exports, multi-disease (2–5), or entity drill-down
5. **Scaffold honesty gap** — disease picker exposes all 10,407 IDs without tier gating
6. **No public demo** — P1-H designed only; self-host requires API_KEY when DEBUG=false
7. **Heuristic downstream modules** — repurposing, biomarkers, ML predictor are scoring layers, not research-grade
8. **Interoperability deferred** — no Phenopacket/FHIR/OMOP exports despite ontology richness internally

---

## Workstream findings (consolidated)

### A — Product UX

Top gaps: IA fragmentation, tier-unaware disease picker, infrastructure feel vs research product. Top 3 capabilities to improve usefulness: (1) Evidence Explorer, (2) Compare product workflow, (3) tier-gated Atlas navigation.

### B — Evidence Explorer

Backend **BETA-complete** (`/api/v1/claims/*`, golden trace). UI **PARTIAL** (Condition Explorer chips). Workspace dossier graph is separate BETA track. Missing: unified Explorer, evidence-quality model, filters (species, study design, date), cross-stack bridge, export.

### C — Compare

Engine **BETA-complete** (5 dimensions, missingness, API, dashboard panel). Missing: 2–5 disease support, pathways/cells/biomarkers where data supports, evidence linkage per overlap, exports, standalone workflow, curation-asymmetry warnings in UX.

### D — Disease object maturity

| Domain | Schema | Data | Evidence | API | UI | Validation | Overall |
|--------|--------|------|----------|-----|-----|------------|---------|
| Identity | MATURE | USABLE | PARTIAL | USABLE | PARTIAL | MATURE | USABLE |
| Phenotypes | MATURE | USABLE | USABLE | USABLE | PARTIAL | MATURE | USABLE |
| Genes | MATURE | USABLE | USABLE | USABLE | USABLE | MATURE | MATURE |
| Mechanisms/pathways | MATURE | USABLE | PARTIAL | USABLE | USABLE | MATURE | USABLE |
| Treatments/drugs | MATURE | USABLE | PARTIAL | USABLE | USABLE | MATURE | USABLE |
| Variants | PARTIAL | PARTIAL | SCAFFOLD | SCAFFOLD | MISSING | PARTIAL | PARTIAL |
| Biomarkers | PARTIAL | SCAFFOLD | MISSING | SCAFFOLD | SCAFFOLD | PARTIAL | SCAFFOLD |
| Cells/anatomy | PARTIAL | PARTIAL | SCAFFOLD | PARTIAL | MISSING | PARTIAL | PARTIAL |
| Trials | PARTIAL | USABLE | PARTIAL | USABLE | USABLE | PARTIAL | PARTIAL |
| Epidemiology | SCAFFOLD | SCAFFOLD | MISSING | MISSING | MISSING | SCAFFOLD | SCAFFOLD |
| Progression/staging | SCAFFOLD | SCAFFOLD | MISSING | MISSING | MISSING | SCAFFOLD | SCAFFOLD |
| Literature | PARTIAL | PARTIAL | PARTIAL | USABLE | USABLE | PARTIAL | PARTIAL |
| Models | SCAFFOLD | SCAFFOLD | MISSING | PARTIAL | PARTIAL | MISSING | SCAFFOLD |

### E — Source expansion

**Implemented adapters:** MONDO, HPO, HPOA, GO, Reactome, Uberon, ClinVar, openFDA, Open Targets, ChEMBL, PubChem, legacy disease KG.

**Full sync lifecycle:** Open Targets only.

**Recommended next sources (ranked):**

1. **HPOA automated sync** — strengthens phenotype claims + Compare phenotype dimension (effort S, value 5)
2. **MONDO release sync** — identity backbone for 10k registry (effort M, value 5)
3. **ClinicalTrials.gov structured sync** — trials intelligence (effort M, value 4)
4. **ClinVar sync** — variants dimension (effort M, value 4, licensing low)
5. **Reactome/GO refresh sync** — mechanism/pathway depth (effort S, value 3)
6. **GWAS Catalog** — genetics evidence (effort M, value 3)
7. **PubMed corpus (controlled)** — literature intelligence foundation (effort L, value 4, risk medium)

Defer: ORPHA standalone (cover via MONDO), NCBI Taxonomy (low near-term leverage), UniProt bulk (partial via OT).

### F — Curation depth

**Recommended tier definitions (refined):**

| Tier | Definition | Validation | Evidence density |
|------|------------|------------|------------------|
| scaffold | Auto-generated KG skeleton | None required | None expected |
| L1 | Partial KG; strict fails | Optional | Minimal |
| L2 | Strict pass; pipeline-ready | Required strict | Config + KG complete |
| L3 | Research-ready | Strict + expression consensus OR deep manual review | Multi-source claims preferred |
| ci_validated | L2/L3 ∩ 8 core PR gate | Every PR | Reference quality |

**Reference disease strategy:** Deepen existing reference set (`sle`, `cystic_fibrosis`, `tuberculosis`, `melanoma`, `als`, `t2d`) plus add **one** deep L3 module per major class only where an existing module qualifies — do not add diseases to fill categories.

**Automation vs manual:** Automate scaffold refresh + strict validation; manual review only for L3 promotion and evidence disputes.

### G — Mechanism graph

Dual representation: disease-local 6-type KG + universal 13-predicate claim graph. **Gap:** no causal edge ontology (`CAUSES`, `CONTRIBUTES_TO`, `PRECEDES`, etc.) — only association predicates. **P2 action:** ADR for mechanism edge semantics; extend predicates incrementally with evidence requirements. Do not overclaim causality.

### H — Temporal disease model

Snapshot-centric versioning exists (`resource_snapshots`, `supersedes_claim_id`). No temporal query API or disease trajectory model. **Decision: DEFER to P3** — prerequisites: Evidence Explorer, versioned knowledge UX, richer staging data.

### I — Contradiction engine

Tri-state at claim API level (SUPPORTS/CONTRADICTS/INCONCLUSIVE). Workspace has heuristic conflict groups. **Not product-ready.** Build after Evidence Quality Model + Explorer (P2 P1).

### J — Knowledge gaps

Only `config_gaps` and compare missingness exist. **No gap engine.** Build after Compare V2 + contradiction context (P2 P2).

### K — Hypothesis architecture

Workspace rankings and Target Hypothesis Agent exist but ununified. **Prerequisite:** formal `COMPUTATIONAL_HYPOTHESIS` contract before public discovery features. Defer public hypothesis product to Wave 5.

### L — Computational models

No model registry. ML predictor, docking, multi-omics are heuristics. **Defer execution platform to P3.**

### M — Literature intelligence

Retrieval solid (Entrez + Europe PMC). No persistent corpus, citation graph, or validated claim extraction pipeline. **P2 P1 foundation** after Evidence Explorer.

### N — Clinical trials

CT.gov v2 tracker works. Shallow on results, eligibility NLP, publication linkage. **P2 P2** enrichment after trials sync adapter.

### O — Biomarkers

Gene-ranking composite only; no diagnostic biomarker schema. **P2 P2** after shared `Biomarker` contract.

### P — Drug/target/repurposing

Heuristic scoring over curated SLE-centric candidates; Open Targets not in repurposing loop. **P2 P2** — link OT associations + hypothesis labeling.

### Q — Research Workbench

Evidence Workspace is partial workbench (saved runs, compare, reviews). Full Workbench (notes, hypotheses, multi-object investigations) = **P3**.

### R — API/SDK/MCP

REST + OpenAPI BETA-complete. No Python SDK, GraphQL, or MCP server. **P2 P1:** thin OpenAPI-generated Python client. MCP after SDK.

### S — Interoperability

MONDO/HPO internal interoperability strong. **P2 P1:** Phenopacket export prototype. **P3:** FHIR/OMOP. Reject KGX/Biolink unless user demand emerges.

### T — Public demo

Self-host Docker exists. No hosted demo, no `DEMO_MODE`. Launch **during early P2 Wave 3** after Evidence + Compare polish.

### U — UX/IA

Recommended top-level: **Research Hub → Disease Studio → Universal Map → Operator (gated) → Platform**. Progressive disclosure on disease pages (Clinical / Biology / Interventions / Research).

### V — Performance

SQLite + DuckDB + Parquet architecture sound for alpha scale. Real bottlenecks: full-corpus validation scans, unbounded dashboard polling, compare without caching. No K8s/graph-cluster rewrite needed.

### W — Technical debt

| Item | Class | P2 action |
|------|-------|-----------|
| mypy 61 errors | HIGH_LEVERAGE | Ratchet: 61 → 45 → 25 |
| Playwright 10/22 fail | HIGH_LEVERAGE | Fix intercept mocks before heavy UI |
| Package rename | NORMAL | Defer to pre-beta/PyPI |
| 6543 scaffold TODOs | COSMETIC | Ignore |
| Windows make/venv | HIGH_LEVERAGE | Document PowerShell equivalents |

### X — Open-source adoption

README/CONTRIBUTING strong. Gaps: no PyPI, no public demo, dual naming confusion, no good-first-issue labels. Minimum: tier-aware contributor guide, `good first issue` templates, Windows quickstart.

### Y — Commercialization

Architecture compatible with future Cloud (read API OSS, premium compute private). No billing. Preserve open core in all P2 contracts.

---

## External ecosystem comparison

| System | Does well | NosoGraph should reuse | Should not duplicate | Underserved workflow |
|--------|-----------|------------------------|--------------------|-----------------------|
| **Monarch KG** | Cross-species phenotype, monthly updates, 30+ sources | MONDO/HPO alignment, phenolog concepts | Full cross-species phenolog engine | Evidence ledger + claim disputes |
| **Open Targets** | Target–disease evidence scores, genetics | OT sync adapter (exists) | OT platform UI | Cross-source normalized compare |
| **PrimeKG/PrimeKG-Plus** | Unified ML-ready graph, drug repurposing topology | MONDO-UMLS bijective mapping discipline | Static CSV graph dumps | Traceable per-claim provenance |
| **DisGeNET/Hetionet** | Association breadth | — | Bulk association graphs without provenance | — |
| **PubMed/OpenAlex** | Literature corpus | Europe PMC/Entrez connectors | Full literature platform | Claim-level evidence mapping |
| **ClinicalTrials.gov** | Trial registry | CT.gov tracker (exists) | Trial search UI alone | Trial ↔ mechanism ↔ evidence linkage |
| **Reactome/HPO** | Ontology depth | Import adapters (exist) | Ontology browsers | Versioned snapshot diff in product |

**NosoGraph differentiation (defensible):**

1. Every relationship traceable to evidence and source version
2. Explicit missingness and curation asymmetry in Compare
3. Cross-source normalized disease comparison without a single opaque score
4. Evidence ledger + future contradiction/gap analysis on same claim graph
5. Research workbench trajectory (Workspace → Explorer → Compare → export)

**Not differentiated today:** raw graph size, ML repurposing heuristics, literature search alone.

---

## Product North Star

> **A researcher should be able to start from a disease, mechanism, phenotype, gene, treatment, or hypothesis and navigate through every relevant relationship to its evidence, compare it against other diseases, identify uncertainty and contradictions, and produce a reproducible research artifact without manually stitching together multiple biomedical databases.**

---

## P2 theme

**Evidence-Native Research Experience**

Coherent story: make NosoGraph's evidence traceability and disease comparison **visible, usable, and exportable** — the capabilities that specialist databases cannot jointly provide.

---

## Priority matrix

Scores: Priority (P0–P3), Value/Effort/Risk (1–5).

| Capability | Priority | Value | Effort | Risk | Dependency |
|------------|----------|------:|-------:|-----:|------------|
| Evidence Explorer | P0 | 5 | M | M | Evidence Quality ADR |
| Compare V2 | P0 | 5 | M | M | Explorer entity drill-down |
| Playwright stabilization | P0 | 4 | S | L | — |
| Evidence Quality Model | P0 | 5 | S | L | ADR |
| Public Demo | P1 | 4 | M | M | Explorer + Compare + DEMO_MODE |
| Literature Intelligence | P1 | 4 | L | H | Corpus ADR |
| Source Expansion | P1 | 4 | M | M | Sync framework |
| Mechanism Graph | P2 | 3 | L | M | Edge semantics ADR |
| Contradictions | P2 | 4 | M | H | Quality model + Explorer |
| Knowledge Gaps | P2 | 4 | M | M | Compare V2 + contradictions |
| Workbench | P3 | 4 | XL | M | Explorer + Compare stable |
| Temporal Model | P3 | 3 | XL | H | Versioned knowledge |
| Computational Models | P3 | 2 | XL | H | Model registry ADR |
| Interoperability (Phenopackets) | P1 | 3 | S | L | Stable claim schema |
| Interoperability (FHIR/OMOP) | P3 | 2 | XL | M | — |
| Developer SDK | P1 | 3 | S | L | OpenAPI stable |
| Reference disease depth | P1 | 4 | M | L | Curation playbook |

---

## Rejected for now

- FHIR / OMOP as near-term priority
- Billing / Stripe
- Full `med_research` → `nosograph` package rename (pre-PyPI)
- Autonomous public hypothesis generation without review contract
- Bulk promotion of 10k scaffolds to L2
- Distributed graph database / Kubernetes rewrite
- KGX / Biolink export (no user demand evidenced)
- MCP server before Python SDK
- Clinical decision support features

---

## Beta criteria (PUBLIC_ALPHA → PUBLIC_BETA)

| Criterion | Measurable gate |
|-----------|-----------------|
| Public read-only demo | Hosted URL, 99% uptime week, DEMO_MODE enabled |
| Evidence Explorer usable | 90% of ci_validated claim types open with evidence + provenance + source link in UI |
| Compare usable | 2–5 diseases, ≥6 dimensions, export JSON/MD, missingness labeled |
| CI health | Required jobs green; Playwright slow suite ≥90% pass |
| API stability | `/api/v1` breaking changes documented; OpenAPI published |
| Source sync | ≥2 sources with hosted dry-run proof |
| Curation semantics | Tier badges on all product surfaces; scaffold warning on L1 |
| Data integrity | Zero P0 provenance defects in ci_validated modules |
| Onboarding | New contributor completes `make ci-local` (or documented Windows equivalent) in <30 min |
| Test stability | Offline suite <15 min on Linux CI |

---

## Release roadmap (recommended)

| Version | Theme | Contents |
|---------|-------|----------|
| v2.4.0 | Evidence Explorer | Explorer UI, quality model, Playwright fix, shared contracts |
| v2.5.0 | Compare product | Compare V2, exports, drill-down, 2–5 diseases |
| v2.6.0 | Public demo + sources | DEMO_MODE deployment, MONDO/HPOA sync, Phenopacket prototype |
| v3.0.0 | Discovery platform | Contradictions, knowledge gaps, Workbench foundation, optional package rename |

---

## Risk register (top items)

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Evidence stacks remain split | M | H | Shared ClaimView contract + bridge layer |
| UI scope creep | H | M | Wave gates; DEMO_MODE scope cap |
| AI extraction unreliable | M | H | Deterministic-first; review status required |
| Scaffold misuse in demos | M | H | Tier gating + warnings |
| Playwright flakes block releases | M | M | Fix mocks in Wave 1 |
| Source license drift | L | H | SPDX CI + registry.yaml |
| Compare misinterpreted as diagnosis | L | H | Research-only disclaimers; no scores implying efficacy |

---

## ADRs recommended before implementation

1. Evidence Quality Model
2. Evidence Explorer resource model (unified claim view)
3. Compare V2 semantics (multi-disease, dimensions, exports)
4. Hypothesis isolation contract
5. Public demo architecture (DEMO_MODE, read-only)
6. Literature claim ingestion (when Wave 4 starts)

---

## Files created by this assessment

- `docs/audits/post-v2.3-roadmap-assessment.md` (this document)
- `docs/roadmaps/p2-master-plan.md`
- `ROADMAP.md` (updated public layer)
- `.gitignore` (validation_l2_full.json, tmp artifacts)
