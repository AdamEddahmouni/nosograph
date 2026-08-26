---
title: Disease coverage
description: Read NosoGraph registry breadth, validation subsets, and curation-depth limits.
---

# Disease coverage

This page describes repository coverage metadata, not clinical coverage or scientific completeness. The current public snapshot is v0.2.1, released 2026-08-22; authoritative values live in [public-status.yaml](../generated/public-status.yaml).

| Tier or measure | Count |
|---|---:|
| Registry modules | 10,407 |
| L2 strict-validated | 88 |
| L3 expression-curated | 2 |
| Reference | 6 |
| CI-validated | 8 |

Registry breadth describes discoverable module coverage. It is not equivalent to deep curation: most registry modules are scaffolds, while validation and reference status apply to smaller explicitly tracked subsets.

Recompute repository reports with:

```bash
nosograph disease corpus-status
nosograph disease validate-batch --tier L2 --strict
```

Do not interpret an unrecorded module field as a biological negative finding. Use [curation tiers](../concepts/curation-tiers.md) for the readiness model and [Sources](sources.md) for upstream integration context.
