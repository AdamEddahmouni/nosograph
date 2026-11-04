---
description: Inspect the evidence NosoGraph disease modules record and whether it carries provenance, including presence states, sampling semantics, and measurement limits.
---

# Evidence coverage

`evidence-coverage` answers a narrow question: **what evidence does a disease
module record, and does that evidence carry provenance?**

It is not a quality score or a scientific-validity score. It does report a
provenance-density gate: whether each gene, drug, and pathway record carries at
least one resolvable identifier. A module with no recorded citation is not a
module proven to lack support, and a module with many citations is not a module
whose claims were verified. Nothing in this workflow dereferences, ranks, or
grades a source.

For registry breadth and validation subsets, see [coverage](coverage.md). For
the strict validation gate, see [validation](../using/validation.md). For the
readiness model, see [curation tiers](../concepts/curation-tiers.md).

## Presence states

Every measured field is classified into exactly one state. The distinction
between `known_absent` and `not_recorded` is the core of the report.

| State | Meaning |
|---|---|
| `present` | The field exists and has content. |
| `known_absent` | The field exists but is explicitly empty (for example `"references": []`). The curator recorded that there is nothing here. |
| `not_recorded` | The key is absent. Nothing was asserted either way. |
| `invalid` | The artifact could not be read or has the wrong shape. This is a defect, not an absence. |

`known_absent` and `not_recorded` are different statements and are never
collapsed. Neither one means "no evidence exists". An unrecorded field is not a
biological negative finding.

!!! note "Different from Compare's `KNOWN_ABSENT`"
    The Compare engine's uppercase `KNOWN_ABSENT` means *an explicit negated
    claim exists* (see [Compare](../using/compare.md)). This page's lowercase
    `known_absent` means *the module data file holds an explicitly empty value*.
    Same words, different contracts; do not substitute one for the other.

## Measured categories

Record-level categories are read from the module's `data/` JSON files:

| Category | Artifact | Provenance field |
|---|---|---|
| `genetics` | `genes.json` | `references` |
| `pharmacology` | `drugs.json` | `references` |
| `pathways` | `pathways.json` | `references` |
| `relationships` | `relationships.json` | none in schema |

Variant-level ClinVar provenance is nested in gene records. Each entry in a
gene's `variants` list carries a ClinVar variation ID, HGVS expression, and
clinical significance; the same ID is also listed in the gene's `references` as
`CLINVAR:<id>`. This keeps the evidence denominator at the gene-record level
while preserving variant-level identifiers. Curated variant records currently
cover CFTR, BRAF/NRAS/KIT, C1QA/C2, IFNGR1, SOD1, KCNJ11/PPARG, HLA-DRB1, NOD2,
PADI4, and APP. The RA PADI4 entries are explicitly `association` records, not
pathogenicity claims. SS, SSC, and T1D remain without variant entries because
no unambiguous disease-specific ClinVar record was found; modules without such
a record are left empty rather than assigned an unrelated risk allele.

Relationship edges carry no citation field in the current schema. These are
structural assertions, so their provenance is reported as
`"provenance": "not_applicable"` and the edges are **excluded from the
provenance denominator**. Counting them as gaps would inflate the defect rate.

Config-derived categories are read from the module's `config.py`:

| Category | Config key |
|---|---|
| `phenotype` | `SYMPTOMS` |
| `literature` | `PUBMED_QUERIES` |
| `trials` | `TRIAL_QUERY` |
| `gwas_terms` | `GWAS_SEARCH_TERMS` |
| `safety_risk` | `DISEASE_SPECIFIC_RISK` |

A tenth category, `safety_profiles`, reads `data/adverse_events.json`. Safety
provenance lives at the **file** level (`source` and `limitations`), not per
drug, so it is reported separately as `file_provenance` and does not contribute
to the record-level provenance counts.

Config categories can only be `present` or `known_absent` in practice — see
[Measurement limitations](#measurement-limitations).

## Provenance vocabulary

A record's provenance is the list of reference identifiers it declares. Each
identifier is grouped by scheme:

`PMID`, `PMC`, `DOI`, `NCT`, `REACTOME`, `KEGG`, `OMIM`, `MONDO`, `EFO`, `HP`,
`ORPHA`, `CHEMBL`, `DRUGBANK`, `UNIPROT`, `CLINVAR`, `GO`.

Anything else is reported as `OTHER` (an unrecognised leading prefix) or
`UNCLASSIFIED` (free text with no recognisable identifier) rather than being
silently dropped. Embedded identifiers count: a free-text citation such as
`"ACR 2024 Abstract; REGENCY Trial (NCT04252599)"` contributes an `NCT` scheme.

**The coverage report never dereferences or scores identifiers.** A recorded
citation is not a verified citation. Resolution is a separate, explicit check:
`python scripts/check_reference_identifiers.py --tier both` verifies PMIDs,
DOIs, and ClinVar IDs against NCBI and the DOI Handle API and fails CI on a
dead identifier.

## Evidence-density gate

The report includes an `evidence` block per module and in the aggregate. A
record is evidenced only when its `references` list contains a recognised
identifier scheme; the record's own `id` is not evidence. Free-text notes are
reported as `UNCLASSIFIED` and do not count.

A module passes when at least **80%** (`EVIDENCE_DENSITY_TARGET`) of its gene,
drug, and pathway records are evidenced. Zero records cannot pass. Aggregate
`gate_passes` requires every measured module to pass.

`--require-evidence` turns a failed gate into exit status 1. It is separate from
`--strict`: a structurally valid module can fail the evidence gate, and a
structurally broken module can still be evidenced. Use both when both contracts
are required.

## Sampling versus full population

The checked-out registry holds more than ten thousand modules, most of them
generated scaffolds. A bounded run therefore measures a *slice*, and the report
says so explicitly.

| Field | Meaning |
|---|---|
| `scope.population_modules` | Size of the discoverable registry (`Disease.list_all()`) |
| `scope.measured` | Modules actually measured in this run |
| `scope.selection` | `explicit`, `tier`, or `reference` |
| `scope.coverage_basis` | `full_population`, `sample`, or `bounded_unsampled_slice` |
| `scope.covers_full_population` | Boolean; `true` only when the measured count equals the population and no sampling was applied |
| `scope.excluded_blocked` | Non-disease slugs removed before measurement |
| `scope.errors` | Modules that failed to load, kept as evidence rather than swallowed |

A `sample` or `bounded_unsampled_slice` result must never be read as a
platform-wide rate. The cached corpus report
`data/reports/disease_batch_status.json` is an **n=500 sample** of the 10k+
registry, and its L2/L3 figures are sample figures for the same reason — see
[coverage](coverage.md).

Sampling is deterministic: candidates are ordered by
`sha256("{seed}:{disease_id}")` and the first `N` are taken, so the same slice,
seed, and `N` always select the same modules across processes and platforms. It
is a fixed pseudo-random sample, not a fresh draw per run.

## Determinism and fingerprints

`fingerprint` is a SHA-256 over the canonical report body with `generated_at`
excluded. Two runs over identical inputs produce an identical fingerprint;
`generated_at` still changes between runs, so whole-file bytes are not stable
while the fingerprint is.

The report schema identifier is `nosograph.evidence_coverage/1`.

## Usage

### CLI

```bash
# Default slice: the reference diseases
nosograph disease evidence-coverage

# One module, written to JSON
nosograph disease evidence-coverage --disease sle --json data/reports/sle_coverage.json

# A tier slice, deterministically sampled
nosograph disease evidence-coverage --tier L2 --sample 200 --seed 0 \
  --output data/reports/evidence_coverage_l2_sample.json

# Bound the run explicitly
nosograph disease evidence-coverage --tier reference --limit 6
```

| Flag | Meaning |
|---|---|
| `--tier` | Corpus slice (`L2`, `L3`, `ci_validated`, `reference`, `all`) |
| `--disease` | Measure specific module ids instead of a tier slice |
| `--sample N` | Deterministically sample `N` modules from the selected slice |
| `--seed` | Sampling seed (default `0`; deterministic) |
| `--limit` | Cap modules measured after sampling |
| `--json` / `--output` | Write the machine-readable report to a path |
| `--require-evidence` | Exit non-zero if any measured module misses the 80% density target |

Without `--tier`, `--disease`, or `--sample`, the run measures the reference
diseases and reports `coverage_basis` accordingly.

### Python API

```python
from med_research.diseases.evidence_coverage import (
    build_evidence_coverage_report,
    inspect_disease,
    render_summary,
    write_evidence_coverage_report,
)

report = build_evidence_coverage_report(
    tier_filter="ci_validated",
    sample_size=8,
    sample_seed=0,
)
print(render_summary(report))                      # researcher-facing text
path = write_evidence_coverage_report(report)      # default: data/reports/evidence_coverage_report.json

one = inspect_disease("sle")                       # single module; raises on an unregistered id
print(one["provenance"]["without_provenance"])
```

`inspect_disease` raises `ValueError` for an unregistered id.
`build_evidence_coverage_report` records that failure per module in
`scope.errors` instead of aborting the run.

## Reading a report

The aggregate block carries the headline counts:

| Field | Meaning |
|---|---|
| `aggregate.diseases` | Modules measured |
| `aggregate.scaffolds` | Modules whose profile self-identifies as generated |
| `aggregate.tier_counts` | Per-readiness-tier counts over the measured slice |
| `aggregate.category_states` | Per-category `present` / `known_absent` / `not_recorded` / `invalid` counts |
| `aggregate.provenance.evidence_records` | Denominator: evidence-bearing records in gene, drug, and pathway collections |
| `aggregate.provenance.present` | Records with at least one recorded reference |
| `aggregate.provenance.known_absent` | Records with an explicitly empty `references` value |
| `aggregate.provenance.not_recorded` | Records with no `references` key at all |
| `aggregate.provenance.by_scheme` | Reference identifiers grouped by scheme |
| `aggregate.provenance.without_provenance` | `known_absent` + `not_recorded` |
| `aggregate.validation` | Strict-validation pass count and grouped failure classes |
| `aggregate.evidence` | Gate block: `records`, `evidenced`, `density`, `target`, `passes`, `modules_passing`, `modules_failing`, `gate_passes` |

`without_provenance` is a count of records with no recorded citation **split**
by `known_absent` versus `not_recorded`. Read the two separately: one is a
curatorial statement, the other is silence. Since `evidence_records` excludes
relationship edges, the ratio `present / evidence_records` describes only the
gene, drug, and pathway collections.

`per_disease` repeats this detail per module, including a capped
`unprovenanced` list (`UNPROVENANCED_LIST_LIMIT` = 25);
`unprovenanced_truncated` flags that the list is capped, so consult it before
reading the list as exhaustive. Aggregate counts are never capped. Each
`per_disease` row also carries an `evidence` block with the same fields plus
`structurally_valid`.

## Measurement limitations

These limits are stored in every report under `limitations`:

- Provenance counts recorded references only; absence means NosoGraph holds no
  recorded citation for that record, not that no evidence exists.
- A reference identifier is never dereferenced, so a recorded citation is not a
  verified citation and support is not assessed here.
- Reference presence is not evidence quality: a single PMID and a systematic
  review are counted identically.
- Relationship edges carry no citation field in the current schema, so their
  provenance is reported as not-applicable instead of as a gap.
- Config-derived categories can only be present or known-absent: the scaffold
  template defines every config key, so "never recorded" is indistinguishable
  from "recorded empty" for those fields.
- A bounded run measures a sample of the registry. Compare it only against runs
  that used the same selection.

Additionally, a module that does not pass strict validation carries an extra
leading limitation stating that its coverage describes recorded inputs only and
that the module is not pipeline-ready.

Do not turn any of these counts into a claim that a disease is under-studied, or
that a drug is safe or unsafe. Use [Sources](sources.md) for upstream
integration context and [validation](../using/validation.md) for what the strict
gate actually checks.
