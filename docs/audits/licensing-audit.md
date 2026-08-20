# Licensing Audit

**Date:** 2026-08-20  
**Scope:** Source code, bundled data, third-party integrations

## Source code license (baseline → target)

| Item | Baseline | Target | Status |
|------|----------|--------|--------|
| Root LICENSE | MIT | **Apache-2.0** | Remediated |
| pyproject.toml `license` | MIT | Apache-2.0 | Remediated |
| NOTICE file | Absent | Added | Remediated |
| Contributor copyright | "Medical Research Platform contributors" | NosoGraph contributors | Remediated |

**Rationale:** Apache-2.0 provides explicit patent grant and is standard for Apache Foundation–style OSS foundations; aligns with NosoGraph public positioning.

## Bundled / compiled disease JSON

Disease KG files under `src/med_research/diseases/*/data/` are **project compilations** of public biomedical facts.

| Aspect | License treatment |
|--------|-------------------|
| JSON schema & compilation | Apache-2.0 (same as source) |
| Underlying biological facts | Governed by source provider terms (not re-licensed) |
| Open Targets–derived scaffolds | Open Targets Platform data license |
| Hand-curated overlays | Apache-2.0 contribution |

## Third-party data & APIs

See `docs/legal/data-licenses.md` and `data/sources/registry.yaml` for the authoritative table.

| Provider | Risk | Mitigation |
|----------|------|------------|
| MONDO (CC BY 4.0) | Attribution | Documented in data-licenses |
| HPO (custom license) | Attribution + restrictions | Documented; no redistribution of raw HPO dumps in repo |
| NCBI Entrez | Rate limits, email requirement | `ENTREZ_EMAIL` in `.env.example` |
| Open Targets | Data license | Bulk parquet setup documented |
| ChEMBL, UniProt, GTEx, etc. | Terms vary | Registry + third-party-notices |

## No restricted clinical data

- No PHI, EHR extracts, or patient-identifiable datasets in version control.
- Runtime SQLite databases gitignored.

## Compliance gaps (pre-remediation)

1. Single MIT license without patent grant language  
2. No separate data licensing document  
3. No trademark policy for "NosoGraph"  
4. `docs/licensing.md` referenced MIT only  

## Post-remediation artifacts

- `LICENSE` (Apache-2.0)
- `NOTICE`
- `docs/legal/licensing-model.md`
- `docs/legal/data-licenses.md`
- `docs/legal/third-party-notices.md`
- `docs/legal/trademark-policy.md`

## Blockers

**None** for private review or public alpha after Apache-2.0 migration and data license documentation.

## Deferred

- PyPI package rename (`med-research` → `nosograph`) — P2, compatibility period required
- SPDX identifiers in all file headers — P3
