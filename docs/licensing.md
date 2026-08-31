---
title: Licensing overview
description: How Apache-2.0 applies to NosoGraph source code, how upstream data-provider terms apply to integrated biomedical data, and where the authoritative legal documents live.
---

# Licensing

> **NosoGraph** source code is Apache-2.0. This page summarizes software and data licensing; authoritative detail lives under `docs/legal/`.

## Project software

NosoGraph source code is released under the [Apache License 2.0](https://github.com/AdamEddahmouni/nosograph/blob/master/LICENSE). See also [NOTICE](https://github.com/AdamEddahmouni/nosograph/blob/master/NOTICE) and [licensing model](legal/licensing-model.md).

The Python distribution may still install as `med-research`; the license applies regardless of package name.

## Third-party data and APIs

The platform integrates public biomedical data and APIs. When using, redistributing, or citing derived work, comply with each provider's terms and attribution requirements.

See:

- [data licenses](legal/data-licenses.md) — full provider table
- [source registry](https://github.com/AdamEddahmouni/nosograph/blob/master/data/sources/registry.yaml) — machine-readable registry
- [third-party notices](legal/third-party-notices.md) — dependency notices

## Curated disease JSON

Disease-specific knowledge graph files under `src/med_research/diseases/*/data/` are project contributions compiled from the sources above and manual curation. They inherit Apache-2.0 for the **compilation and schema**, but underlying facts remain subject to source-provider terms.

## No clinical or patient data

This repository does not distribute protected health information (PHI). Do not commit patient records, clinical notes, or identifiable case data. See [SECURITY.md](https://github.com/AdamEddahmouni/nosograph/blob/master/SECURITY.md).

## Trademark

See [docs/legal/trademark-policy.md](legal/trademark-policy.md).

## Questions

For licensing questions about the software, open a GitHub issue. For data-provider terms, consult the linked source documentation.
