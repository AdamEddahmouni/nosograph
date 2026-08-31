---
title: Data source contributions
description: Propose a NosoGraph source integration with terms, tests, provenance, and honest maturity labels.
---

# Data source contributions

Use this path to add or update an upstream source integration. Start with the [source matrix](../data/sources.md) and the [source sync lifecycle](../architecture/source-sync-lifecycle.md) so the proposed role and maturity are explicit.

## Contribution requirements

1. Record the source role, identifiers, license, and terms in `data/sources/registry.yaml`.
2. Define whether the path is local, fixture-backed, live, or experimental.
3. Preserve source identity, snapshot/version, import context, and fingerprints where supported.
4. Add deterministic fixtures or focused tests for normalization and validation.
5. Keep `STABLE`, `BETA`, and `EXPERIMENTAL` labels tied to NosoGraph implementation maturity, not upstream scientific quality.

## Validate the change

Run the focused tests for the adapter, then the repository gate:

```bash
make ci-local
```

Do not describe a connector as continuously updated or production-grade unless the implementation and current status support that claim. Upstream data terms remain separate from the Apache-2.0 license for NosoGraph source code.

## Continue

- [Sources](../data/sources.md) — current integration matrix.
- [Provenance](../concepts/provenance.md) — traceability semantics.
- [Good first issues](../project/good-first-issues.md) — a scoped source task.
