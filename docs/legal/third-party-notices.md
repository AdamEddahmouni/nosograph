---
description: Notices and licenses for third-party components included or integrated by NosoGraph.
---

# Third-Party Notices

NosoGraph includes or integrates the following third-party components.

## Python dependencies

See `requirements-lock.txt` for the complete pinned dependency set with versions. Notable libraries:

| Package | License | Use |
|---------|---------|-----|
| FastAPI | MIT | Web API |
| Celery | BSD | Async jobs |
| DuckDB | MIT | Analytics |
| NetworkX | BSD | Graph algorithms |
| scikit-learn | BSD | ML modules |
| Biopython | Biopython license | Sequence/bio utilities |
| matplotlib | PSF-based | Plotting |
| rdkit (optional) | BSD | Cheminformatics |

Automated license bill-of-materials checking and SPDX 2.3 JSON SBOM generation are enforced in CI via `scripts/check_licenses.py` against `license-policy.toml`.
- Run `make license-check` locally to verify that all locked dependencies comply with the license policy.
- Run `make sbom` to generate an ISO/IEC 5962:2021 compliant SPDX 2.3 JSON document (`dist/sbom.spdx.json`) and Markdown inventory (`dist/sbom-summary.md`).

## JavaScript (dashboard)

| Library | License | Use |
|---------|---------|-----|
| 3Dmol.js | BSD | Molecular viewer |
| Cytoscape.js | MIT | Network graphs |

See `src/med_research/web/static/` for bundled assets.

## Data providers

See [data-licenses.md](data-licenses.md) for biomedical data attribution requirements.

## Apache-2.0 attribution

This product includes software developed as part of the NosoGraph project (formerly med-research).

Full license text: [LICENSE](https://github.com/AdamEddahmouni/nosograph/blob/master/LICENSE)
