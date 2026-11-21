## Summary

<!-- What changed and why? -->

## Why

<!-- User or research impact. Skip for tiny typo PRs. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation / public presence
- [ ] Refactor / tooling
- [ ] Disease data / curation
- [ ] Data source / provenance

## Evidence / sources

<!-- Required for curation and data PRs. Public identifiers only. -->

## Validation

- [ ] `make commitlint` (Conventional Commit subjects)
- [ ] `make lint` (or N/A for docs-only)
- [ ] `make test-offline` (or N/A for docs-only)
- [ ] `python scripts/check_public_metadata.py` if README, citation, release, or public copy changed
- [ ] `make docs-build` if documentation, theme, or public-site files changed
- [ ] Additional:

## Screenshots

<!-- UI PRs only. No secrets, PHI, or local paths. -->

## Data / provenance impact

- [ ] No new restricted data
- [ ] Provenance/source metadata updated if associations changed

## Release impact

<!-- Conventional Commits drive the next version. See RELEASING.md and docs/contributing/releasing.md. -->

- [ ] No release — docs / tests / CI / refactor / internal tooling only
- [ ] PATCH — bug fix, security fix, or user-visible performance fix
- [ ] MINOR — new functionality, or an intentional pre-1.0 compatibility change
- [ ] Not sure — let release automation classify it (`make release-plan`)

## Breaking changes

<!-- None / describe. Mark the commit with `!` or a BREAKING CHANGE: footer and include migration notes. -->

## Research safety

- [ ] Outputs remain framed as computational hypotheses, not clinical advice

## Security

- [ ] No secrets, API keys, credentials, or PHI committed
