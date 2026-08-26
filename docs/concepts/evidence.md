---
title: Evidence
description: Canonical reference for NosoGraph evidence direction, claim attachment, source context, and interpretation limits.
---

# Evidence

Evidence records are source-linked records attached to typed claims. They provide context for inspection and can carry a directional relationship to the claim. This page is the canonical interpretation reference; product guides should link here rather than redefine the vocabulary.

> **Claim is not proof. Association is not causation.** Evidence direction describes how a stored record relates to a claim. It does not establish a universal confidence score, scientific finality, or clinical recommendation.

## Evidence directions

| Direction | Canonical meaning |
|---|---|
| `SUPPORTS` | The evidence record supports the associated claim in the stored dataset. |
| `CONTRADICTS` | The evidence record disagrees with the associated claim in the stored dataset. |
| `INCONCLUSIVE` | The available evidence is mixed or does not establish a clear direction. |
| `UNASSERTED` | No directional evidence is recorded for the associated claim. |

Supporting and contradictory records can coexist. `CONTRADICTS` is not automatic falsification, and `SUPPORTS` is not proof. Read the records, source context, and limitations together.

## What evidence attaches to

A claim has a subject, predicate, and object. Evidence records attach to that claim or to the source-backed assertion represented by it. Common record context includes source-native identifiers, species, study design, origin, human review, dates, and available source URLs. Missing fields remain missing rather than being converted into a negative finding.

The [Claims page](claims.md) defines the typed assertion. The [Evidence Explorer guide](../using/evidence-explorer.md) shows the local inspection path.

## Trace source context

Use the following sequence when reviewing a record:

```text
claim -> evidence direction -> study/source -> provenance and snapshot context
```

[Provenance](provenance.md) explains source identity, import context, version/date, and fingerprints. The [source matrix](../data/sources.md) explains NosoGraph integration maturity. Neither provenance nor source maturity is a guarantee of scientific correctness.

## Research boundary

NosoGraph presents computational research artifacts for inspection. It does not replace the source literature, establish causality, diagnose a condition, or provide clinical decision support. For a structured comparison, use [Compare](../using/compare.md) and keep its explicit missingness states distinct.
