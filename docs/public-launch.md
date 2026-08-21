# Public readiness (evergreen)

The GitHub repository **is already public** at [AdamEddahmouni/nosograph](https://github.com/AdamEddahmouni/nosograph). Current release: **v2.3.0**.

Use this page for future public-readiness reviews. The original “flip to public / rename from med-research / tag v2.2.0” list is archived at [audits/public-launch-v2.2-checklist.md](audits/public-launch-v2.2-checklist.md).

## Before each public release

```bash
make venv-sync
make ci-local
python scripts/check_public_metadata.py
```

Confirm:

- No secrets or PHI in tracked files
- README and `CITATION.cff` versions match `pyproject.toml`
- Registry vs curation-depth wording is intact
- Release notes are understandable without the full CHANGELOG
- [release-readiness-report](audits/release-readiness-report.md) reviewed when cutting a version

## GitHub settings

Maintainer-only steps: [project/github-public-settings.md](project/github-public-settings.md)

## Out of scope (still)

- Clinical decision support or PHI processing
- Billing / Stripe
- FHIR / OMOP / Phenopackets until those roadmap items ship
