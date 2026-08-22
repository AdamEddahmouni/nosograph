# Public readiness (evergreen)

The GitHub repository is public at [AdamEddahmouni/nosograph](https://github.com/AdamEddahmouni/nosograph). Current release: **v2.4.0**. Current maturity: **Public Alpha**.

Use this page for future public-readiness reviews. Historical launch checklists remain in [audits/public-launch-v2.2-checklist.md](audits/public-launch-v2.2-checklist.md).

## Before each public release

```bash
make venv-sync
make ci-local
python scripts/check_public_metadata.py
python -m mkdocs build --strict
```

Confirm:

- No secrets or PHI in tracked files
- README, `CITATION.cff`, `pyproject.toml`, and `public-status.yaml` versions match
- README and Pages use the current positioning: **Disease Intelligence. Connected.**
- Registry vs curation-depth wording is intact
- Release notes are understandable without the full CHANGELOG
- Current screenshots and diagrams are labeled accurately
- `scripts/generate_brand_assets.py --check` passes

## GitHub settings

Maintainer-only steps: [project/github-public-settings.md](project/github-public-settings.md)

## Out of scope (still)

- Clinical decision support or PHI processing
- Billing / Stripe
- FHIR / OMOP / Phenopackets until those roadmap items ship
- A public hosted demo until the snapshot-first design is implemented safely
