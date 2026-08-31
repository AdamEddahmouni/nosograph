---
title: Investigating SLE
description: A repository-backed SLE module walkthrough for validating local data and following the evidence inspection path.
---

# Investigating SLE

This walkthrough uses the repository-backed `sle` module as a reproducible software example. It demonstrates validation and navigation; it does not make a clinical claim about systemic lupus erythematosus or recommend a treatment.

> **Research use only.** Outputs are computational research artifacts, not medical advice, diagnosis, or clinical decision support.

## Verify the module

From the repository root:

```bash
nosograph disease validate sle --strict
nosograph disease coverage sle
```

The strict command checks the module's repository contract. Coverage output identifies recorded fields and gaps; it does not establish that an unrecorded relationship is absent.

## Follow the inspection path

1. Open the local dashboard after following [Installation](../getting-started/install.md) or [Docker](../getting-started/docker.md).
2. Select the SLE condition or inspect the module data locally.
3. Open a recorded claim in [Evidence Explorer](../using/evidence-explorer.md).
4. Read the exact predicate and evidence direction using the [Claims](../concepts/claims.md) and [Evidence](../concepts/evidence.md) references.
5. Follow source identifiers and available snapshot or fingerprint context through [Provenance](../concepts/provenance.md).
6. Use [Compare](../using/compare.md) only when a cross-condition question is appropriate, and interpret `KNOWN_ABSENT` and `NOT_RECORDED` separately.

The module can contain sparse or source-dependent fields. Do not fill missing study, source, or provenance values with an assumed conclusion.

## Next paths

- [Trace evidence](evidence-tracing.md) for the full claim-to-source sequence.
- [Data sources](../data/sources.md) for integration maturity and source terms.
- [Architecture overview](../architecture/overview.md) for the developer view of the same data flow.
