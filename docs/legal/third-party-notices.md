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

Run `pip-licenses` locally for a full SPDX report (not automated in CI).

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

Full license text: [LICENSE](../../LICENSE)
