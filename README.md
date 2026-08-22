<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand/logo-dark.svg">
  <img src="docs/assets/brand/logo-light.svg" alt="NosoGraph — Disease Intelligence. Connected." width="620">
</picture>

# NosoGraph

**Disease Intelligence. Connected.**

Open-source research software for connecting disease knowledge, evidence, and provenance across biomedical sources. NosoGraph helps researchers inspect relationships across diseases, phenotypes, genes, pathways, interventions, studies, and sources—without treating an association as causation or a registry entry as deep curation.

[Explore GitHub Pages](https://adameddahmouni.github.io/nosograph/)
· [Quick start](#quick-start)
· [Evidence model](#evidence-and-provenance)
· [Contribute](#contributing)
· [Cite](#citation)

[![Release](https://img.shields.io/github/v/release/AdamEddahmouni/nosograph?display_name=tag)](https://github.com/AdamEddahmouni/nosograph/releases/latest)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22055279.svg)](https://doi.org/10.5281/zenodo.22055279)
[![Tests](https://github.com/AdamEddahmouni/nosograph/actions/workflows/test.yml/badge.svg)](https://github.com/AdamEddahmouni/nosograph/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12-2F86FF.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-19D2C7.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-7252F4.svg)](https://adameddahmouni.github.io/nosograph/)

<img src="docs/assets/brand/hero.svg" alt="NosoGraph connects disease entities, claims, evidence, and provenance" width="100%">

> **Public alpha · research use only.** NosoGraph is not medical advice, a diagnostic system, or clinical decision support. A public hosted demo is not deployed yet; run the local Docker evaluation or CLI instead.

## At a glance

**NosoGraph v0.2.0 · Public Alpha · snapshot 2026-08-22**

| Repository-backed snapshot | Value |
|---|---:|
| Registry modules | 10,407 |
| Strict L2-validated modules | 88 |
| Reference modules | 6 |
| CI-validated modules | 8 |
| Analysis pipelines | 40+ |
| Offline tests selected in the v0.2.0 suite | 2,425 |

These values come from [`docs/generated/public-status.yaml`](docs/generated/public-status.yaml). **Registry breadth is not curation depth**: most registry modules are scaffolds.

## What NosoGraph is

NosoGraph is a computational layer across upstream biomedical resources. It normalizes identifiers and records, represents typed relationships as claims, attaches supporting or contradictory evidence, and preserves source/provenance context for inspection.

```text
fragmented biomedical evidence
        ↓
structured claims + relationships
        ↓
evidence + provenance
        ↓
connected disease intelligence
        ↓
researcher inspection / developer extension
```

It complements—not replaces—resources such as MONDO, HPO, PubMed, ClinicalTrials.gov, Open Targets, GWAS Catalog, and other upstream databases.

## Evidence and provenance

The primary research path is:

```text
Disease → Claim → Evidence relationship → Study / source → Provenance / snapshot
```

Evidence records support claims; they are not automatic proof. Supporting and contradictory evidence can coexist. Missing metadata remains `unknown` rather than silently becoming certainty. See the [Evidence Explorer guide](docs/using/evidence-explorer.md), [evidence model](docs/architecture/evidence-model.md), and [provenance model](docs/architecture/provenance.md).

## What exists today

| Surface | Maturity | Use it for |
|---|---|---|
| `nosograph` CLI | **Stable** | Explore, validate, sync, analyze, and serve locally |
| FastAPI API + dashboard | **Beta** | Local research interface and documented API routes |
| Evidence Explorer | **Public Alpha** | Claim → evidence → provenance → source inspection; included in v0.1.0 |
| Evidence Workspace | **Beta** | Multi-source evidence, claims, and ranked research hypotheses |
| NosoGraph Compare | **Beta** | Released in v0.2.0: deterministic 2–5-condition workflow with explicit missingness, claim drill-down, and JSON/Markdown exports |
| Source synchronization | **Experimental** | Open Targets vertical slice and sync lifecycle |
| Public hosted demo | **Planned** | Not deployed |
| Optional LLM enrichment | **Experimental** | Not required for deterministic core workflows |
| FHIR / OMOP / Phenopackets | **Not implemented** | Future interoperability work |

## Quick start

### Docker evaluation

```bash
git clone https://github.com/AdamEddahmouni/nosograph.git
cd nosograph
cp .env.example .env
docker compose --profile full up --build
```

Open http://localhost:8000. Requires Docker Compose v2. The `full` profile starts the API, worker, and Redis. See the [Docker guide](docs/getting-started/docker.md).

### CLI / contributor setup

The product CLI is `nosograph`. The installable Python distribution and import path remain `med-research` / `med_research` throughout the public-alpha compatibility period.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e .
cp .env.example .env
nosograph --help
nosograph disease validate sle --strict
```

For contributor setup, use `make venv-sync` and run `make ci-local`. Redis is needed for async dashboard jobs and integration tests, not pure offline CLI tests.

## Researcher path

- [What is NosoGraph?](docs/getting-started/what-is.md)
- [Five-minute SLE workflow](docs/research/sle.md)
- [Evidence Explorer](docs/using/evidence-explorer.md)
- [Evidence Workspace](docs/evidence-workspace.md)
- [Research examples](docs/research/)
- [Data sources and coverage](docs/data/sources.md)
- [Validation and curation tiers](docs/using/validation.md)

Typical journey: explore a disease → inspect claims → inspect evidence → trace provenance → compare relationships.

## Developer path

- [Architecture](docs/architecture/overview.md)
- [Data model](docs/architecture/data-model.md)
- [CLI](docs/using/cli.md)
- [API](docs/using/api.md)
- [Local development](docs/developers/local.md)
- [Testing](docs/developers/testing.md)
- [Source adapter contributions](docs/contributing/sources.md)
- [Disease curation](docs/contributing/curation.md)
- [Code contributions](docs/contributing/code.md)

Typical journey: understand architecture → run locally → inspect APIs/data model → extend a source or disease → validate → contribute.

## Data and scientific practice

NosoGraph documents upstream source terms and integration state in the [source matrix](docs/data/sources.md). It uses deterministic extraction for core workflows; optional LLM enrichment is experimental and disabled by default in secure deployments. Provenance fingerprints, validation tiers, coverage warnings, and conservative `unknown` values help keep outputs inspectable.

All outputs are computational research artifacts. Review source context and limitations before drawing conclusions; ranked candidates are research prioritization hypotheses, not treatment recommendations.

## Architecture

<img src="docs/assets/diagrams/architecture.svg" alt="NosoGraph architecture from biomedical sources through the universal store to CLI, API, and dashboard" width="100%">

The platform combines disease modules, a universal biomedical store, evidence gathering and extraction, analysis pipelines, a FastAPI API/dashboard, and Celery/Redis jobs. See the [architecture overview](docs/architecture/overview.md).

## Documentation

The [GitHub Pages site](https://adameddahmouni.github.io/nosograph/) is the long-form public surface, with search and task-oriented navigation:

- [Getting started](https://adameddahmouni.github.io/nosograph/getting-started/what-is/)
- [Research](https://adameddahmouni.github.io/nosograph/using/evidence-explorer/)
- [Concepts](https://adameddahmouni.github.io/nosograph/concepts/evidence/)
- [Data](https://adameddahmouni.github.io/nosograph/data/sources/)
- [Developers](https://adameddahmouni.github.io/nosograph/developers/architecture/)
- [Project roadmap](ROADMAP.md)

## Contributing

NosoGraph needs code, documentation, data-source integration, and disease curation contributions. Start with [CONTRIBUTING.md](CONTRIBUTING.md), then run the local gate:

```bash
make ci-local
```

Do not submit secrets, PHI, or patient-identifiable data. Questions belong in [GitHub Discussions](https://github.com/AdamEddahmouni/nosograph/discussions); security reports belong through [SECURITY.md](SECURITY.md).

## Citation

Cite v0.2.0 through the all-versions concept DOI [10.5281/zenodo.22055279](https://doi.org/10.5281/zenodo.22055279) until Zenodo mints its version-specific archive. The historical v0.1.0 version DOI is [10.5281/zenodo.22055280](https://doi.org/10.5281/zenodo.22055280). Canonical metadata is also available through GitHub’s citation UI and [`CITATION.cff`](CITATION.cff). The software is Apache-2.0; upstream biomedical datasets retain their own terms.

```bibtex
@software{nosograph2026,
  title   = {NosoGraph: Disease Intelligence. Connected.},
  author  = {Eddahmouni, Adam and NosoGraph contributors},
  year    = {2026},
  url     = {https://github.com/AdamEddahmouni/nosograph},
  version = {0.2.0},
  doi     = {10.5281/zenodo.22055279}
}
```

## Research-use boundary

NosoGraph is research software. It must not be used as a diagnostic device, treatment recommender, or clinical decision-support system. Report security issues privately. Do not submit secrets, PHI, or patient-identifiable data. See [SECURITY.md](SECURITY.md).

## License

Apache-2.0 for NosoGraph source code — [LICENSE](LICENSE), [NOTICE](NOTICE). Third-party biomedical datasets retain upstream licenses and terms — [data licenses](docs/legal/data-licenses.md).
