---
title: Disease curation contributions
description: Add or improve a disease module with identifiers, sourced evidence, provenance, and validation.
---

# Disease curation contributions

Use this path when adding or improving a disease module. The detailed [disease curation playbook](../disease-curation.md) is canonical; this page is the contributor entry point.

## Minimum expectations

- Use stable disease and entity identifiers.
- Add sourced records rather than inferred biomedical conclusions.
- Preserve source and provenance context where available.
- Keep missing fields explicit; do not turn absent metadata into a negative assertion.
- Respect upstream data terms and do not include secrets, PHI, or patient-identifiable data.

## Validate the module

For a focused module check:

```bash
nosograph disease validate <disease-id> --strict
nosograph disease coverage <disease-id>
```

The full registry contains many scaffolds, so `disease validate --all --strict` is not the repository merge gate. Read [validation](../using/validation.md) for the curated checks and [data model](../architecture/data-model.md) for readiness tiers.

## Continue

- [Data source contributions](sources.md) if the module needs a new upstream integration.
- [Code contributions](code.md) for schema or loader changes.
- [Good first issues](../project/good-first-issues.md) for scoped curation work.
