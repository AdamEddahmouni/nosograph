---
title: Evidence Explorer
description: Inspect a local NosoGraph claim, its evidence direction, source context, and provenance.
---

# Evidence Explorer

**Maturity:** `PUBLIC_ALPHA` · local read-only research surface

Evidence Explorer is the local NosoGraph interface for inspecting a typed claim, its evidence direction, study or source context, and available provenance. This page is procedural: it explains what to open and how to interpret the records without turning an evidence label into a scientific conclusion.

> **Research boundary.** Evidence Explorer presents computational research artifacts. `SUPPORTS` does not mean proven, `CONTRADICTS` does not by itself establish falsification, and an association is not causation. NosoGraph is not medical advice or clinical decision support.

## Open a claim

1. Start the local dashboard from the [Docker guide](../getting-started/docker.md) or the [API/server guide](../api-reference.md).
2. Open the dashboard at <http://127.0.0.1:8000/>.
3. Open a condition, choose a claim, and select **Open in Evidence Explorer**. Depending on the local dashboard build, the same surface may be reached from the **Evidence** navigation item.
4. Inspect the claim row, evidence groups, source identifiers, and provenance details.

A shareable claim URL uses the documented shape `?claim_id={uuid}#evidence-explorer`. The UUID is an application identifier, not a scientific confidence value.

## Read the claim

A claim is a structured statement with a subject, predicate, and object. The predicate names the relationship; it does not decide whether the relationship is causal or clinically useful. The [Claims concept](../concepts/claims.md) defines the model and the [Evidence model](../concepts/evidence.md) explains how records attach to it.

## Read evidence direction

The canonical evidence directions are:

| Direction | Meaning in NosoGraph |
|---|---|
| `SUPPORTS` | The evidence record is represented as supporting the claim. |
| `CONTRADICTS` | The evidence record is represented as disagreeing with the claim. |
| `INCONCLUSIVE` | The available evidence is mixed or does not establish a clear direction. |
| `UNASSERTED` | No directional evidence is recorded for the claim. |

These labels describe the stored relationship between an evidence record and a claim. They are not a universal confidence score, proof state, or clinical recommendation. Supporting and contradictory records can coexist; inspect each group separately. See the canonical [Evidence semantics](../concepts/evidence.md) page for the full interpretation reference.

## Read context and missingness

Quality dimensions such as species, study design, origin, and human review describe context. A field that is not present should remain explicitly unavailable; it should not be silently converted into a negative finding or a score.

In Compare outputs, `KNOWN_ABSENT` means an explicit current negated assertion exists, while `NOT_RECORDED` means neither a positive nor a negated assertion is present. Those are different contracts; the [Compare guide](compare.md) defines them in detail.

## Trace provenance and sources

Follow the available chain:

```text
claim -> evidence -> study or source -> snapshot/context -> provenance
```

Source identity, import context, version/date, fingerprints, and incomplete stages are shown only where the current record supports them. Provenance establishes traceability to stored inputs; it does not establish that the underlying conclusion is correct. See [Provenance](../concepts/provenance.md) and the [source matrix](../data/sources.md).

## API view

A loaded claim can expose its structured response through the local API. The evidence list is paginated:

```text
GET /api/v1/claims/{claim_id}/evidence?limit=50&offset=0
```

Use the [API reference](../api-reference.md) for the current base URL and endpoint catalog. The route is local unless you deploy the application yourself.

## Continue

- [Claims](../concepts/claims.md) — understand the subject, predicate, and object.
- [Evidence semantics](../concepts/evidence.md) — use one canonical direction vocabulary.
- [Trace evidence](../research/evidence-tracing.md) — follow the inspection sequence.
- [Provenance](../concepts/provenance.md) — interpret source and snapshot metadata.
- [Compare conditions](compare.md) — inspect recorded differences without implying diagnosis.
