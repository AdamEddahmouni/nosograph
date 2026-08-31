---
title: Tracing evidence
description: Follow a local NosoGraph condition from typed claim through evidence, source context, and provenance.
---

# Tracing evidence

This walkthrough connects the NosoGraph data model to the local inspection path. It is about how to review a stored relationship, not how to derive a medical conclusion. The practical sequence is:

```text
condition -> typed claim -> evidence -> study or source -> provenance
```

## Start with a condition

Use a repository-backed condition in the local dashboard or the API. The [SLE walkthrough](sle.md) provides a compact software example; it does not assert a clinical finding.

## Open the typed claim

From a condition view, select a claim and note its subject, predicate, and object. The predicate is the relationship type. Read [Claims](../concepts/claims.md) if the structure is unfamiliar.

## Inspect evidence direction

Open the claim in [Evidence Explorer](../using/evidence-explorer.md). Review the evidence groups using the canonical labels:

- `SUPPORTS` — the record is represented as supporting the claim.
- `CONTRADICTS` — the record is represented as disagreeing with the claim.
- `INCONCLUSIVE` — the available records do not establish a clear direction.
- `UNASSERTED` — no directional evidence is recorded.

These labels describe stored evidence semantics. They are not proof, a universal confidence score, or causality.

## Follow study and source context

Inspect source-native identifiers, study metadata, dates, and URLs where present. A missing field remains missing; do not infer a negative finding from an unavailable study or source field.

## Read provenance

Follow the available provenance details for source identity, snapshot/version, import context, and fingerprint. [Provenance](../concepts/provenance.md) explains what those fields support: traceability and reproducibility checks, not scientific certification.

## Continue to comparison

When the research question is cross-condition, open [Compare](../using/compare.md). Keep `KNOWN_ABSENT` distinct from `NOT_RECORDED`: explicit negation is not the same as no recorded assertion.

> **Research use only.** NosoGraph records computational research artifacts. Associations are not causation, and the walkthrough is not medical advice or clinical decision support.
