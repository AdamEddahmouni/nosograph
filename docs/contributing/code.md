---
title: Code contributions
description: Add or change NosoGraph code while preserving contracts, tests, and research-use boundaries.
---

# Code contributions

Use this path for runtime, API, CLI, dashboard, pipeline, or test changes. Read [local development](../developers/local.md) first, then run the repository's local validation gate before opening a pull request.

## Workflow

1. Create a focused branch from `master`.
2. Make the smallest change that preserves the current API, CLI, and provenance contracts.
3. Add or update focused tests for changed behavior.
4. Run:

   ```bash
   make ci-local
   ```

5. Use the project pull-request template and describe data/provenance impact, validation, and any research-safety boundary.

Do not weaken tests to obtain a green build. Do not add clinical claims, fake evidence, or unverified endpoint examples to user-facing surfaces.

## Useful references

- [Architecture overview](../architecture/overview.md)
- [API reference](../api-reference.md)
- [Testing](../developers/testing.md)
- [Good first issues](../project/good-first-issues.md)
