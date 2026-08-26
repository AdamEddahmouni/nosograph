---
title: Provenance
description: Understand how NosoGraph records source, snapshot, import, and fingerprint context for traceability.
---

# Provenance

Provenance records how a NosoGraph result or claim reached the local store. It answers a traceability question: which source and inputs produced this record, under what import or retrieval context? It does not prove that the underlying scientific conclusion is correct.

## Traceability chain

```text
record or claim
    -> source identity
    -> version/date or snapshot context
    -> import or transformation
    -> stable identifier or fingerprint
```

The exact fields depend on the surface. Evidence Explorer may expose source-native identifiers and URLs. Source synchronization records a nine-stage lifecycle from version discovery through publish and provenance update. Pipeline results can include a provenance schema, source list, retrieval mode, filters, package version, and a stable SHA-256 fingerprint.

## What the fields mean

| Field or concept | Meaning |
|---|---|
| Source identity | The upstream resource or adapter associated with the record. |
| Snapshot | A versioned or dated local view of an imported resource where supported. |
| Import context | The retrieval, normalization, validation, or transformation path used locally. |
| Fingerprint | A stable identifier over selected inputs; it supports reproducibility checks. |
| Missing field | A value not recorded by the current path. It is not evidence that the underlying fact is absent. |

See the detailed [provenance model](../architecture/provenance.md) and [source sync lifecycle](../architecture/source-sync-lifecycle.md) for implementation fields and stages.

## What provenance does not mean

Provenance does not certify a source, turn an association into causation, or make a claim a proven fact. Review the attached evidence, source terms, coverage, and limitations. A run can have complete provenance while reporting limited coverage.

## Continue

- [Evidence Explorer](../using/evidence-explorer.md) — inspect a claim in the local interface.
- [Data sources](../data/sources.md) — read integration maturity and source-specific terms.
- [Evidence semantics](evidence.md) — interpret `SUPPORTS`, `CONTRADICTS`, `INCONCLUSIVE`, and `UNASSERTED`.
