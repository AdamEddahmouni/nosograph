# Governance

## Project name

**NosoGraph** — *Disease Intelligence. Connected.*

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
2. **API/CLI breaking changes:** Require migration notes and an explicit breaking-change marker (`!` or a `BREAKING CHANGE:` footer) in the commit. Pre-1.0 this bumps the MINOR version; MAJOR is reserved for compatibility commitments made at or after 1.0. See [RELEASING.md](RELEASING.md).
3. **Security fixes:** Private advisory process per [SECURITY.md](SECURITY.md).
4. **Governance changes:** PR with `[GOVERNANCE]` prefix and 7-day comment period.

## Release authority

Maintainers approve releases by merging the automated release pull request described in [RELEASING.md](RELEASING.md); Release Please then produces the version bump, changelog entry, git tag, and GitHub Release. No automated PyPI publish in CI.

## Branding policy

- Public docs use **NosoGraph**
- `med-research` / `med_research` remain compatibility aliases until v3.0 (see [trademark policy](docs/legal/trademark-policy.md))

## Conflict resolution

Follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Escalate to maintainers via private email or GitHub contact if needed.

## Future steering

When contributor count grows, maintainers may establish a lightweight steering group documented in this file.
