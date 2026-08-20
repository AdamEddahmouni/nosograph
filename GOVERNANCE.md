# Governance

## Project name

**NosoGraph** — *The Open Computational Map of Human Disease*

## Mission

Provide an open, extensible computational platform for exploring public biomedical knowledge across diseases — with honest maturity labeling and research-only framing.

## Roles

| Role | Responsibility |
|------|----------------|
| **Maintainers** | Merge gates, releases, security advisories (see `.github/CODEOWNERS`) |
| **Contributors** | PRs, issues, disease curation, documentation |
| **Users / researchers** | Self-host, cite, report bugs responsibly |

This is an early-stage OSS project without a formal steering committee. Maintainers listed in CODEOWNERS act as initial stewards.

## Decision process

1. **Routine changes:** PR review + passing CI (`make ci-local` equivalent).
2. **API/CLI breaking changes:** Require CHANGELOG entry, migration notes, semver major bump.
3. **Security fixes:** Private advisory process per [SECURITY.md](SECURITY.md).
4. **Governance changes:** PR with `[GOVERNANCE]` prefix and 7-day comment period.

## Release authority

Maintainers cut releases per [RELEASING.md](RELEASING.md). No automated PyPI publish in CI.

## Branding policy

- Public docs use **NosoGraph**
- `med-research` / `med_research` remain compatibility aliases until v3.0 (see [trademark policy](docs/legal/trademark-policy.md))

## Conflict resolution

Follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Escalate to maintainers via private email or GitHub contact if needed.

## Future steering

When contributor count grows, maintainers may establish a lightweight steering group documented in this file.
