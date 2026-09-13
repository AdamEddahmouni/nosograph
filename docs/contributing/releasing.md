---
title: Releases and versioning
description: How NosoGraph versions, what Conventional Commit types trigger a release, and how the automated release pull request works.
---

# Releases and versioning

NosoGraph releases are automated with
[Release Please](https://github.com/googleapis/release-please) from
[Conventional Commits](https://www.conventionalcommits.org/) on `master`. Contributors
never bump versions, edit the changelog, or create tags. The complete policy — including
the maintainer runbook, prerelease setup, and hotfix process — is
[RELEASING.md](https://github.com/AdamEddahmouni/nosograph/blob/master/RELEASING.md)
in the repository root.

## The only thing a contributor has to do

Write a well-formed commit subject:

```
<type>[(<scope>)][!]: <summary>
```

```text
feat(compare): add N-way comparison engine
fix(web): stop leaking filesystem paths in /api/ready
docs(cli): document the --disease flag
feat(api)!: require an explicit disease_id on comparison requests
```

The release tooling parses that subject to decide the next version and to write the
changelog entry, so the prefix is functional.

## Which commits trigger a release

| Commit | Version impact |
|---|---|
| `feat` | MINOR — new functionality |
| `fix` | PATCH — bug fix |
| `perf` | PATCH — user-visible performance fix |
| `feat!` / `fix!` / `BREAKING CHANGE:` footer | MINOR while pre-1.0, with migration notes |
| `docs`, `test`, `style`, `refactor`, `chore`, `ci`, `build`, `deps` | none on their own |

A release represents a coherent improvement, not a commit count. Several commits that
implement one capability — feature, tests, follow-up fixes, documentation — land as one
MINOR release. A bug found after that release becomes a PATCH release.

Pre-1.0, a breaking change bumps MINOR rather than MAJOR. `1.0.0` is reserved for the
first release where the CLI, API, package naming, and data contracts carry explicit
compatibility commitments.

## Breaking changes

Mark them explicitly and explain the migration:

```text
feat(api)!: require an explicit disease_id on comparison requests

BREAKING CHANGE: POST /api/v1/nosograph/comparisons no longer defaults to SLE.
Callers must pass disease_id explicitly. See docs/using/compare.md.
```

The affected contract might be an `/api/v1` route, a CLI flag, a configuration file, an
environment variable, or a serialized data format. All of these are compatibility
contracts — see [Source of truth](../project/source-of-truth.md) for which artifact owns
each public fact.

## Check your work locally

```bash
make commitlint     # validate every commit since the last release tag
make release-plan   # preview the classification and next version (read-only)
```

Both commands work offline. `make release-plan` mirrors the release configuration, so it
answers "is this none, patch, minor, or major?" without a token or a network call.

The same commit check runs on pull requests as an **advisory** CI job: it annotates
violations but does not block your PR.

## What happens after your PR merges

```text
your PR merges to master
      ↓
Release Please opens or updates a release pull request
      ↓
a maintainer reviews the proposed version and changelog
      ↓
merging that PR creates the version bump, CHANGELOG entry, git tag, and GitHub Release
```

The release pull request is the human approval step. Pushing to `master` never publishes
a release by itself.

## Version numbers

Versions follow [Semantic Versioning](https://semver.org/) as
`MAJOR.MINOR.PATCH`, tagged `vMAJOR.MINOR.PATCH` (`v0.2.1`). Prereleases use the standard
identifiers — `0.3.0-alpha.1`, `0.3.0-beta.1`, `0.3.0-rc.1` — and are published as GitHub
pre-releases.

`pyproject.toml` is the source of truth for the version. Every other metadata file is
synchronized from it automatically, and `scripts/check_public_metadata.py` fails the
build if any of them drift.

## Next

- [Releases](../project/releases.md) — current and historical releases.
- [Current status](../project/status.md) — maturity and release context.
- [Testing](../developers/testing.md) — the validation tiers to run before a PR.
