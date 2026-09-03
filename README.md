<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand/logo-dark.svg">
    <img src="docs/assets/brand/logo-light.svg" alt="NosoGraph — Disease Intelligence. Connected." width="620">
  </picture>
</p>

<p align="center"><strong>Disease Intelligence. Connected.</strong></p>

<p align="center">
  Open-source research software for connecting disease knowledge, evidence, and provenance across biomedical sources.
</p>

<p align="center">
  <a href="https://adameddahmouni.github.io/nosograph/"><strong>Explore the documentation</strong></a>
  · <a href="#quick-start">Run locally</a>
  · <a href="CONTRIBUTING.md">Contribute</a>
</p>

<p align="center">
  <a href="https://github.com/AdamEddahmouni/nosograph/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/AdamEddahmouni/nosograph?display_name=tag"></a>
  <a href="https://doi.org/10.5281/zenodo.22055279"><img alt="DOI" src="https://zenodo.org/badge/DOI/10.5281/zenodo.22055279.svg"></a>
  <a href="https://github.com/AdamEddahmouni/nosograph/actions/workflows/test.yml"><img alt="Tests" src="https://github.com/AdamEddahmouni/nosograph/actions/workflows/test.yml/badge.svg"></a>
  <a href="https://www.python.org/downloads/"><img alt="Python 3.11 and 3.12" src="https://img.shields.io/badge/python-3.11%20%7C%203.12-2F86FF.svg"></a>
  <a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache--2.0-19D2C7.svg"></a>
</p>

<img src="docs/assets/product/evidence-explorer.webp" alt="NosoGraph Evidence Explorer showing disease context, typed claims, evidence direction, and provenance" width="100%">

> **Public alpha · research use only.** NosoGraph is not medical advice, a diagnostic system, or clinical decision support. No public hosted demo is deployed; use the local Docker evaluation or CLI.

## What you can do

| Capability | What it provides | Maturity |
|---|---|---|
| Explore evidence | Follow disease context through typed claims, evidence direction, source context, and provenance | Public Alpha |
| Compare conditions | Compare two to five conditions with explicit missingness and deterministic JSON/Markdown exports | Beta |
| Build research workflows | Use the CLI, FastAPI surface, disease modules, and 40+ analysis pipelines locally | Stable CLI · Beta API |
| Extend the graph | Add disease curation, source adapters, validation, documentation, and analysis code | Open source |

NosoGraph complements upstream resources such as MONDO, HPO, PubMed, ClinicalTrials.gov, Open Targets, and GWAS Catalog. It does not replace them or turn associations into causal conclusions.

## Choose your path

### For researchers

- [Understand NosoGraph](docs/getting-started/what-is.md)
- [Follow the five-minute SLE workflow](docs/research/sle.md)
- [Inspect claims and provenance](docs/using/evidence-explorer.md)
- [Compare conditions](docs/using/compare.md)
- [Review source coverage and limitations](docs/data/coverage.md)

### For developers and contributors

- [Install from source](docs/getting-started/install.md)
- [Understand the architecture](docs/architecture/overview.md)
- [Use the CLI](docs/using/cli.md) or [API](docs/api-reference.md)
- [Run the test suite](docs/developers/testing.md)
- [Contribute code, curation, sources, or documentation](CONTRIBUTING.md)

## Quick start

```bash
git clone https://github.com/AdamEddahmouni/nosograph.git
cd nosograph
cp .env.example .env
docker compose --profile full up --build
```

Open `http://localhost:8000`. Docker Compose v2 starts the API, worker, and Redis. For a CLI-only or contributor installation, follow the [installation guide](docs/getting-started/install.md).

The product CLI is `nosograph`. The installable distribution and import path remain `med-research` and `med_research` during the public-alpha compatibility period.

## Evidence, provenance, and limits

```text
Disease → Typed claim → Evidence relationship → Study / source → Provenance / snapshot
```

Evidence records support claims; they are not automatic proof. Supporting, contradictory, inconclusive, and unasserted evidence can coexist. Missing metadata remains `unknown` rather than silently becoming certainty. See the [evidence model](docs/architecture/evidence-model.md), [provenance model](docs/architecture/provenance.md), and [data-source matrix](docs/data/sources.md).

## Current status

**NosoGraph v0.2.1 · Public Alpha · repository snapshot 2026-08-22**

| Repository-backed measure | Value |
|---|---:|
| Registry modules | 10,407 |
| Strict L2-validated modules | 88 |
| Reference modules | 6 |
| CI-validated modules | 8 |
| Offline tests selected in the v0.2.1 suite | 2,445 |

Values come from [`docs/generated/public-status.yaml`](docs/generated/public-status.yaml). Registry breadth is not curation depth: most registry modules are scaffolds. See the [current project status](docs/project/status.md) for capability-level maturity and limitations.

## Contributing

NosoGraph welcomes focused contributions to code, documentation, source integration, and disease curation. Start with [CONTRIBUTING.md](CONTRIBUTING.md), then run the local gate:

```bash
make ci-local
```

Questions belong in [GitHub Discussions](https://github.com/AdamEddahmouni/nosograph/discussions). Report vulnerabilities privately through [SECURITY.md](SECURITY.md). Never submit secrets, PHI, or patient-identifiable data.

## Citation

Cite v0.2.1 with the all-versions concept DOI [10.5281/zenodo.22055279](https://doi.org/10.5281/zenodo.22055279) until a v0.2.1 archive record exists. The historical version DOI [10.5281/zenodo.22062925](https://doi.org/10.5281/zenodo.22062925) identifies v0.2.0 only. Canonical metadata is available through GitHub's citation UI and [`CITATION.cff`](CITATION.cff).

```bibtex
@software{nosograph2026,
  title   = {NosoGraph: Disease Intelligence. Connected.},
  author  = {Eddahmouni, Adam and NosoGraph contributors},
  year    = {2026},
  url     = {https://github.com/AdamEddahmouni/nosograph},
  version = {0.2.1},
  doi     = {10.5281/zenodo.22055279}
}
```

## License and research-use boundary

NosoGraph source code is available under [Apache-2.0](LICENSE). Upstream biomedical datasets retain their own terms; see [data licenses](docs/legal/data-licenses.md). Outputs are computational research artifacts—not diagnoses, treatment recommendations, or clinical decision support.
