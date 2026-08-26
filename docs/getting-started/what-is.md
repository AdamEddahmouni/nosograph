---
title: What is NosoGraph?
description: A concise introduction to NosoGraph's research scope, evidence model, local interfaces, and current maturity.
---

# What is NosoGraph?

NosoGraph is open-source biomedical research software for connecting disease knowledge, typed claims, evidence, and source provenance across local data and upstream resources. This page is conceptual: it explains the objects and boundaries before you install anything.

> **Research use only.** NosoGraph is not a diagnostic system, clinical decision-support system, or replacement for source literature. An association is not automatically causation, and a claim is not proof.

## The core objects

A normal inspection path is:

```text
condition or disease
        -> typed claim
        -> evidence direction
        -> study or source
        -> provenance and snapshot context
```

- A **condition** is a disease or biomedical entity identified in the repository or an imported ontology snapshot.
- A **typed claim** records a subject, predicate, and object, such as a condition `HAS_PHENOTYPE` relationship.
- **Evidence** describes the records attached to a claim and preserves directional semantics: `SUPPORTS`, `CONTRADICTS`, `INCONCLUSIVE`, or `UNASSERTED`.
- **Provenance** records the source, import context, snapshot information, and stable identifiers where available. It supports traceability; it does not establish that a scientific conclusion is correct.

## What you can do locally

- Use the `nosograph` CLI to inspect and validate disease modules.
- Run the FastAPI dashboard and open the read-only Evidence Explorer.
- Compare two through five conditions with explicit `KNOWN_ABSENT` and `NOT_RECORDED` states.
- Use the API and structured biomedical store for programmatic research workflows.

NosoGraph complements upstream resources such as MONDO, HPO/HPOA, PubMed, ClinicalTrials.gov, Open Targets, and GWAS Catalog. Source integration maturity is tracked separately from scientific quality; see [Data sources](../data/sources.md).

## Current scope

NosoGraph is **Public Alpha**. The CLI is the most stable task-oriented surface; the API and dashboard are Beta, Evidence Explorer is Public Alpha, Compare and Evidence Workspace are Beta, and Open Targets synchronization plus optional LLM enrichment are Experimental. A public hosted demo is planned but not deployed. FHIR, OMOP, and Phenopackets are not implemented.

The registry contains 10,407 modules, but registry breadth is not curation depth. Smaller explicitly tracked subsets carry validation or reference status; see [Current status](../project/status.md) and [coverage](../data/coverage.md).

## Continue

- [Install locally](install.md) to run the CLI or Docker stack.
- [Follow the short tutorial](tutorial.md) to validate the SLE reference module.
- Researchers: [open Evidence Explorer](../using/evidence-explorer.md) and [trace a claim](../research/evidence-tracing.md).
- Developers: [read the architecture overview](../architecture/overview.md) and [use the API reference](../api-reference.md).
