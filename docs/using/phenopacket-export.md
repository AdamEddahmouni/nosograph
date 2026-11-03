---
description: The experimental NosoGraph disease-level phenotype evidence export — what it contains, what it is not, and how far it is from Phenopacket Schema conformance.
---

# Phenotype evidence export (experimental)

`med_research.biomed.phenopacket` serializes NosoGraph phenotype evidence as a
Phenopacket-**aligned** JSON bundle.

!!! warning "This is not a patient Phenopacket"
    NosoGraph records **disease-level evidence**: a source asserts that a disease
    is associated with a phenotype, for example `MONDO:0007915 HAS_PHENOTYPE
    HP:0001250`. It does not record observations of an individual person. The
    export therefore describes disease-level evidence and contains **no**
    demographics, age, sex, onset, measurements, biospecimens, variants or
    clinical findings. It is not for clinical decision-making.

Status: **EXPERIMENTAL**. See the interoperability table in
[Ontology policy](../architecture/ontology-policy.md).

## What the bundle contains

| Field | Meaning |
|---|---|
| `bundle_schema_version` | Version of this NosoGraph layout (currently `0.1.0`) |
| `phenopacket_alignment` | Which Phenopacket concepts the bundle is aligned to, and that it is *not* conformant |
| `export_scope` | Always `disease_evidence` |
| `disease.curie` / `disease.label` | The disease the evidence is scoped to |
| `phenotypicFeatures[]` | Disease-level phenotype annotations, each with evidence direction and provenance |
| `provenance_summary` | Distinct source ids and the annotated feature count |
| `missing_fields` | Every field path that carries `NOT_RECORDED` |
| `warnings` | Explicit notes about collapsed duplicates, non-MONDO disease identifiers, contradictory evidence, and empty phenotype lists |
| `disclaimer` | Research-only notice repeated inside the payload |

## Missingness is explicit

`NOT_RECORDED` is a literal string value, not `null` and not `0`.

- `NOT_RECORDED` means **no assertion exists in the supplied input**.
- It never means "known to be absent".
- Every `NOT_RECORDED` value also appears in `missing_fields`, so a consumer can
  detect incompleteness without walking the whole tree.

An export with no phenotype annotations is valid: `phenotypicFeatures` is an
empty list, `phenotypicFeatures` is listed in `missing_fields`, and a warning
states that absence was not inferred.

## Evidence direction stays verbatim

`phenotypicFeatures[].direction` is `supporting` or `contradictory`, carried
through unchanged from the biomedical claim model.

Contradictory evidence is **not** mapped onto the Phenopacket Schema `excluded`
flag. "A source argues against this disease-phenotype association" and "the
phenotype was excluded in this individual" are different statements, and the
export refuses to conflate them. A bundle containing contradictory evidence
carries a warning saying so.

## Input schema

```json
{
  "disease_curie": "MONDO:0000001",
  "disease_label": "Synthetic fixture condition",
  "phenotypes": [
    {
      "hpo_id": "HP:0000001",
      "hpo_label": "Synthetic phenotype one",
      "direction": "supporting",
      "frequency": "1/7",
      "notes": "optional free text",
      "sources": [
        {
          "source_id": "synthetic-hpoa",
          "source_record_id": "HPOA:0000001",
          "source_url": "https://example.org/record/1",
          "version": "2026-01-01",
          "checksum": "sha256:bbbb",
          "attribution": "synthetic fixture"
        }
      ]
    }
  ]
}
```

Rules enforced on every export:

- `disease_curie` must be a non-empty, well-formed CURIE. Non-MONDO identifiers
  are accepted with a warning, because NosoGraph carries EFO-linked diseases.
- `hpo_id` must be an HPO term id of the form `HP:0000000`.
- `direction` is required and must be `supporting` or `contradictory`.
- Every phenotype needs **at least one** source with a non-empty `source_id`.
- Unknown fields are rejected, so a typo cannot be silently dropped.
- All problems are reported in one `PhenopacketExportError`, not one at a time.

## Usage

From the CLI. Exit status is `0` on success, `1` for an unreadable file, invalid
JSON, or any validation problem, and every validation problem is printed rather
than only the first:

```bash
# Write the canonical bundle to a file.
med-research biomed phenopacket --input evidence.json --output out/phenotypes.json

# Or print it to stdout.
med-research biomed phenopacket --input evidence.json
```

From Python:

```python
from med_research.biomed.phenopacket import build_bundle, export_bundle

# Canonical JSON string (also validates).
text = export_bundle(payload)

# Or write straight to disk as UTF-8 with LF endings.
text = export_bundle(payload, path="out/phenotypes.json")

# Or keep the typed object and serialize separately.
bundle = build_bundle(payload)
```

The bundle carries no wall-clock timestamp on purpose: identical inputs
serialize to byte-identical text (sorted keys, compact separators, one trailing
newline). Packaging layers that need an export time should record it outside
this payload.

## Limitations

- **Not a conformant Phenopacket.** There is no `Phenopacket` envelope, no
  `subject`, no `metaData`/`resource` block, and no `OntologyClass` objects; HPO
  terms appear as plain CURIE strings.
- **Disease-level, not individual-level.** Nothing here can be interpreted as an
  observation of a person.
- **No FHIR/OMOP mapping and no PHI/EHR ingestion.** There is no persistence
  layer, no API route and no CLI verb for this export yet.
- **No frequency normalization.** A `frequency` string is passed through as
  supplied; denominators, ratios and HPO frequency terms are not validated.
- **No ontology verification.** The export does not check that an HPO term is
  current, non-obsolete, or joined to the disease in the active snapshot. It
  serializes what the caller supplies and does not invent associations.

## Next interoperability requirements

Real Phenopacket Schema conformance would additionally need:

1. A `metaData` block with a `createdBy`, an ISO-8601 `created` timestamp, and
   `resources[]` entries carrying id, name, namespacePrefix, url, version and
   iri for the MONDO and HPO releases used.
2. A decision about the envelope. A conformant patient Phenopacket would be
   dishonest here; the defensible options are a *phenotype-only* file scoped to
   the disease, or a family/cohort level exchange format that can represent
   disease-level assertions.
3. `OntologyClass` objects (`{id, label}`) instead of bare CURIE strings, which
   requires labels to be resolved from the active snapshot rather than supplied
   by the caller.
4. JSON Schema validation against a pinned Phenopacket Schema release, run in CI
   against committed fixtures.
5. A mapping review for evidence direction: whether contradictory disease-level
   evidence has any conformant representation at all.
6. Snapshot pinning in the payload, mirroring the checksum and version
   provenance already recorded by source sync.
