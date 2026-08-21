# NosoGraph

**The Open Computational Map of Human Disease**

[![Tests](https://github.com/AdamEddahmouni/nosograph/actions/workflows/test.yml/badge.svg)](https://github.com/AdamEddahmouni/nosograph/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

NosoGraph is an open-source biomedical research platform for exploring disease knowledge graphs, gathering multi-source evidence, and generating **explainable computational hypotheses**. It combines per-disease curated data, a universal ontology store, 40+ analysis pipelines, and a FastAPI dashboard with async job support.

> **Research use only.** Outputs are computational prioritization hypotheses, not medical advice. Do not use for clinical decision-making. See [SECURITY.md](SECURITY.md).

## Compatibility note

The Python package still installs as **`med-research`** with import path **`med_research`**. Canonical CLI: **`nosograph`**. Legacy alias: **`med-research`**. Public product name: **NosoGraph**.

| Surface | Name | Policy |
|---------|------|--------|
| Product / docs | NosoGraph | Current |
| Canonical CLI | `nosograph` | Current |
| `pip install` / legacy CLI | `med-research` | Compatibility alias |
| Python imports | `med_research` | Compatibility alias |

## What is implemented today

Honest maturity labels — see [docs/architecture/overview.md](docs/architecture/overview.md).

| Capability | Maturity | Notes |
|------------|----------|-------|
| Unified CLI (`nosograph` / `med-research`) | **STABLE** | Same implementation; disease tooling, batch validation, biomed sync |
| FastAPI web API + dashboard | **BETA** | Celery async jobs, WebSocket/SSE progress |
| Evidence Workspace | **BETA** | PubMed, trials, GWAS, FDA labels, rankings |
| Universal Biomedical Store | **BETA** | MONDO, HPO, GO, Reactome, ClinVar, openFDA |
| Claim/evidence/provenance APIs | **BETA** | End-to-end traceability; polished Evidence UX incomplete |
| NosoGraph Compare | **EXPERIMENTAL** | Initial multidimensional engine + API + dashboard slice |
| Source synchronization | **EXPERIMENTAL** | Open Targets vertical slice; dry-run lifecycle proven |
| Disease registry | **BETA** | 10,407 modules — mostly scaffolds |
| Curated disease corpus | **BETA** | See tier table below |
| Live external connectors | **BETA** | Open Targets, GTEx, ChEMBL, UniProt, bioRxiv |
| Optional LLM enrichment | **EXPERIMENTAL** | Requires `OPENAI_API_KEY` |
| FHIR / OMOP / Phenopackets | **NOT_IMPLEMENTED** | See [ROADMAP.md](ROADMAP.md) |

### Disease corpus tiers

| Tier | Count | Meaning |
|------|-------|---------|
| Registry modules | 10,407 | MONDO-aligned slugs (mostly Open Targets scaffolds) |
| L2 pipeline-ready | 88 | Pass strict validation (full L2 corpus) |
| L3 expression-curated | 2 | Hand-curated GEO consensus genes (sample scan; refresh pending) |
| Reference tier | 6 | Deep reference modules (`sle`, `ra`, … subset) |
| CI-validated (original eight) | 8 | `sle`, `ra`, `ibd`, `ms`, `ss`, `ssc`, `t1d`, `ad` |

**Important:** registry size ≠ curation depth. Scaffold modules are starting points, not validated clinical models.

### Core features

- Per-disease JSON knowledge graphs with Python config overlays
- Knowledge-graph construction, multi-disease network analytics, drug repurposing
- Gene expression, screening, safety, ADMET, virtual screening, clinical trial tracking
- Provenance fingerprints and coverage contracts for research integrity
- DuckDB-accelerated biomedical graph analytics
- HPO-aware condition comparison and **NosoGraph Compare** initial slice (phenotype, gene, mechanism, treatment, evidence_coverage)
- Batch strict validation (`disease validate-batch`) and curation tier reporting
- Biomedical source-sync lifecycle (Open Targets dry-run)

## Quick start

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

make venv-sync
cp .env.example .env   # sets DEBUG=true for local dev
python -m med_research.cli --help
nosograph --help   # canonical alias
```

Run the dashboard (requires Redis for async jobs):

```bash
# Load .env first (see AGENTS.md)
python -m med_research.cli serve --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`.

## Development

```bash
make ci-local          # lint + lock verify + offline tests (pre-push gate)
make test-offline      # fast unit suite
make lint
```

Validate a curated disease:

```bash
python -m med_research.cli disease validate sle --strict
python -m med_research.cli disease validate-batch --tier reference --strict
python -m med_research.cli disease corpus-status
nosograph biomed sync open_targets --dry-run
```

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture overview](docs/architecture/overview.md) | System design |
| [Data model](docs/architecture/data-model.md) | Disease + biomed schemas |
| [Evidence model](docs/architecture/evidence-model.md) | Workspace claims & ranking |
| [Disease curation](docs/disease-curation.md) | Contributor curation playbook |
| [Deployment](docs/deployment.md) | Production hardening |
| [API reference](docs/api-reference.md) | Environment variables & endpoints |
| [Licensing model](docs/legal/licensing-model.md) | Apache-2.0 + data terms |
| [Source registry](data/sources/registry.yaml) | Upstream data providers |
| [Public launch checklist](docs/public-launch.md) | Before making repo public |
| [Release readiness](docs/audits/release-readiness-report.md) | Gate status |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and [GOVERNANCE.md](GOVERNANCE.md).

## Security

Report vulnerabilities privately — see [SECURITY.md](SECURITY.md). Do not commit secrets or patient data.

## License

Apache-2.0 for source code — see [LICENSE](LICENSE) and [NOTICE](NOTICE). Third-party biomedical data retains upstream licenses — see [docs/legal/data-licenses.md](docs/legal/data-licenses.md).

## Citation

```bibtex
@software{nosograph2026,
  title = {NosoGraph: The Open Computational Map of Human Disease},
  author = {NosoGraph contributors},
  year = {2026},
  url = {https://github.com/AdamEddahmouni/med-research},
  version = {2.2.0}
}
```

See also [CITATION.cff](CITATION.cff).
