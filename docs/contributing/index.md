---
title: Contributing
description: Choose a NosoGraph contribution path and find the validation, governance, and security expectations.
---

# Contributing

NosoGraph accepts focused contributions to code, disease curation, source integrations, and documentation. Start by choosing the contribution type, then use the linked validation guidance. The root [CONTRIBUTING.md](https://github.com/AdamEddahmouni/nosograph/blob/master/CONTRIBUTING.md) remains the canonical repository workflow.

## Choose a contribution path

| Path | Start here | Main expectation |
|---|---|---|
| Code | [Code contributions](code.md) | Preserve contracts, add tests, and run `make ci-local`. |
| Disease curation | [Disease curation](curation.md) | Use identifiers, sourced evidence, provenance, and no PHI. |
| Data sources | [Source contributions](sources.md) | Record terms, tests, and honest `STABLE` / `BETA` / `EXPERIMENTAL` maturity. |
| Documentation | [Local development](../developers/local.md) | Keep commands and links aligned with current repository behavior. |

## Validation and project policies

Run [Testing](../developers/testing.md) for the available tiers. Read [Governance](governance.md) for decision authority, [Security](../project/security.md) for private vulnerability reporting, and [License](../project/license.md) for the distinction between NosoGraph source licensing and upstream data terms.

No contribution path should include secrets, PHI, or patient-identifiable data. Do not present fixture-backed examples as live biomedical findings.

## Continue

- [Good first issues](../project/good-first-issues.md) — existing scoped contribution ideas.
- [Current status](../project/status.md) — release and maturity context.
- [Source of truth](../project/source-of-truth.md) — which repository artifact owns each public fact.
