---
title: Claims
description: Understand NosoGraph's typed subject-predicate-object claims and their relationship to evidence and provenance.
---

# Claims

A claim is a structured biomedical assertion represented with a subject, predicate, and object. The claim is the relationship NosoGraph records; it is not automatically proof that the relationship is true, causal, or clinically useful.

## Claim shape

```text
subject -> predicate -> object
```

For example, a repository-backed condition record may use a predicate such as `HAS_PHENOTYPE`, `ASSOCIATED_WITH_GENE`, `INVOLVES_PATHWAY`, or `TREATED_BY`. Exact predicates belong to the current API and data model; they should not be inferred from a display label.

| Part | Role |
|---|---|
| Subject | The entity from which the relationship starts. |
| Predicate | The typed relationship name. |
| Object | The related entity or value. |
| Evidence links | Records that NosoGraph associates with the claim, with an evidence direction where available. |
| Provenance | Source, snapshot, import, or fingerprint context for the stored record where available. |

## Claim is not proof

A claim can be supported, contradicted, inconclusive, or unasserted by attached evidence. These are stored evidence semantics, not a single truth score. Association does not establish causation. Read the [canonical Evidence page](evidence.md) before interpreting a direction label.

## Inspecting a claim

The local Evidence Explorer follows:

```text
condition -> typed claim -> evidence -> study/source -> provenance
```

Use [Evidence Explorer](../using/evidence-explorer.md) for the interaction path, and [Provenance](provenance.md) for the metadata contract. Use the [API reference](../api-reference.md) when you need structured claim responses.

> **Research use only.** Claims are computational research artifacts. NosoGraph is not a diagnostic system, clinical decision-support system, or replacement for source literature.
