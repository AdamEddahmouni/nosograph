---
description: Validating disease modules with nosograph validate commands, and what the strict validation gate does and does not cover.
---

# Validation

```bash
nosograph disease validate sle --strict
nosograph disease validate-batch --tier L2 --strict
nosograph disease corpus-status
```

`disease validate --all --strict` is **not** a merge gate for the full 10k scaffold registry. Hosted CI validates the original curated eight plus reference-tier checks as documented in release audits.
