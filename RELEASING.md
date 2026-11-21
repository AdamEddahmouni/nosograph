# Releasing NosoGraph

This is the canonical release policy for the repository. It covers versioning,
commit conventions, release automation, the approval path, and the maintainer
runbook. The Python distribution still publishes as `med-research` during the
compatibility period.

Contributors only need the first three sections. Maintainers need all of it.

---

## 1. Versioning scheme

NosoGraph follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`)
on a pre-1.0 public-alpha line.

| Segment | Meaning in this repository |
|---|---|
| **PATCH** (`0.2.1` → `0.2.2`) | Backward-compatible fixes: bug fixes, security fixes without a compatibility change, user-visible performance fixes, dependency updates that do not change behavior. |
| **MINOR** (`0.2.1` → `0.3.0`) | Meaningful new functionality, **and** intentional compatibility-affecting changes while the project is pre-1.0. Compatibility-affecting changes must ship with migration notes. |
| **MAJOR** (`0.x` → `1.0.0`) | Reserved. `1.0.0` is the first intentionally stable release, where the supported CLI, API, package naming, and data contracts carry explicit compatibility commitments. |

The historical `v2.1.0`–`v2.4.0` tags predate this deliberate public-alpha
baseline. They remain immutable audit records but do not define the current
compatibility line.

### Pre-1.0 policy

Because the project is pre-1.0, a breaking change does **not** jump the major
version. `release-please` is configured with `bump-minor-pre-major: true`, so:

- breaking change → **MINOR** (`0.2.x` → `0.3.0`), with migration notes
- `feat` → **MINOR** (`bump-patch-for-minor-pre-major` is off)
- `fix` / `perf` → **PATCH**
- everything else → **no release**

Do not bump a version merely because commits accumulated. A version marks a
coherent, releasable state — not a commit count.

### Version source of truth

`pyproject.toml` (`[project].version`) is the canonical version. Everything else
is synchronized from it:

| File | How it is kept in sync |
|---|---|
| `src/med_research/__init__.py` (`__version__`) | `release-please` Python strategy |
| `CITATION.cff` (both `version:` keys) | `release-please` (`# x-release-please-version`) |
| `docs/generated/public-status.yaml` (`version`) | `release-please` (`# x-release-please-version`) |
| `codemeta.json` (`$.version`) | `release-please` (`jsonpath`) |
| `CHANGELOG.md` | `release-please` |
| `.release-please-manifest.json` | `release-please` (tracks the last released version) |
| `docs/`, `README.md`, `docs/project/citation.md` prose, metrics, and dates | maintainer, in the release PR (guarded by `scripts/check_public_metadata.py`) |

`scripts/check_public_metadata.py` fails the build whenever any of these drift,
so a release PR cannot merge with a half-updated version. Never hand-edit a
version that `release-please` owns.

---

## 2. Commit convention (Conventional Commits)

Commit subjects are part of the release contract: the release tooling parses them
to decide the version bump and to build the changelog.

```
<type>[(<scope>)][!]: <summary>
```

| Type | Use for | Release impact |
|---|---|---|
| `feat` | New user-visible functionality | MINOR |
| `fix` | Bug fix | PATCH |
| `perf` | User-visible performance improvement | PATCH |
| `revert` | Reverting an earlier change | match the reverted change |
| `refactor` | Restructuring with no behavior change | none |
| `build` | Build tooling, packaging | none |
| `ci` | CI/CD configuration | none |
| `chore` | Maintenance | none |
| `deps` | Dependency bumps | none (unless behavior changes) |
| `docs` | Documentation only | none |
| `style` | Formatting only | none |
| `test` | Tests only | none |

Scopes are optional and free-form; use the surface you touched
(`feat(compare): …`, `fix(web): …`, `docs(release): …`).

### Breaking changes

Mark a breaking change with `!` after the type/scope, a `BREAKING CHANGE:`
footer, or both:

```
feat(api)!: require an explicit disease_id on comparison requests

BREAKING CHANGE: POST /api/v1/nosograph/comparisons no longer defaults to SLE.
Callers must pass disease_id explicitly. See docs/using/compare.md.
```

A breaking change bumps MINOR while pre-1.0, which is exactly why the footer
must explain the migration and the affected contract (API, CLI flag, config,
env var, serialized format, or package export).

### Validation

```bash
make commitlint                       # every commit since the last release tag
python scripts/check_commit_messages.py            # just the current commit
python scripts/check_commit_messages.py --range v0.2.1..HEAD
```

Merge commits, `Revert "…"`, fixup/squash commits, and bot authors are exempted.
In CI the same check runs on pull requests as an **advisory** job
(`Commit messages (advisory)` in `.github/workflows/test.yml`) so that public
contributors are never blocked by it. To promote it to a hard gate, remove
`continue-on-error` and `--advisory`, then add the job to the `required-tests`
aggregate.

---

## 3. Release decision policy

Release when the repository has a coherent improvement that users, contributors,
package consumers, or deployments would benefit from receiving.

Several commits that together implement one capability — feature, tests, fixes
found during implementation, documentation, UI polish — belong to **one** MINOR
release. A bug found after that release justifies a PATCH release.

### Decision table

| Change | Release impact |
|---|---|
| Bug fix | PATCH |
| Security fix without a compatibility change | PATCH |
| Performance fix | PATCH |
| New backward-compatible feature | MINOR |
| New optional API or CLI capability | MINOR |
| Breaking API / CLI / config / data-contract change | MINOR (pre-1.0) |
| Removed supported feature | MINOR (pre-1.0) |
| Documentation only | none |
| Tests only | none |
| CI only | none |
| Refactor with no behavior change | none |
| Internal tooling only | usually none |
| Dependency bump that changes runtime behavior | classify as the change it causes |

Preview the classification offline, without a token or a network call:

```bash
make release-plan
# Current version : 0.2.1 (manifest)
# Classification  : MINOR
# Next version    : 0.3.0   tag: v0.3.0
```

`scripts/next_release.py` is read-only and mirrors the `release-please`
configuration. It is a preview, not the authority: `release-please` computes the
version for the actual release PR.

### Prerelease policy

Prereleases are for distributing a not-yet-stable candidate — not for ordinary
development. Use the standard SemVer identifiers:

| Version | Meaning |
|---|---|
| `X.Y.Z-alpha.N` | Experimental/incomplete. APIs and behavior may change substantially. |
| `X.Y.Z-beta.N` | Feature set is mostly established; broader testing is required. |
| `X.Y.Z-rc.N` | Release candidate intended to become the stable release if nothing blocking is found. |

Prereleases use the same tag shape (`v0.3.0-beta.1`) and are published as GitHub
**pre-releases**, so they are never mistaken for the stable release.

To cut prereleases, run a release channel from a dedicated branch. Add a second
entry to `release-please-config.json` and run the workflow against that branch:

```json
"release/0.3": {
  "release-type": "python",
  "prerelease": true,
  "versioning": "prerelease",
  "prerelease-type": "beta",
  "include-component-in-tag": false
}
```

Promote to stable by merging the release branch back to `master` (a prerelease
never becomes stable by being relabelled — the final `X.Y.Z` release PR does).

---

## 4. Release automation

Releases are automated with [Release Please](https://github.com/googleapis/release-please)
in manifest mode.

```
Conventional Commits
      ↓
push to master
      ↓
.github/workflows/release-please.yml  (Release Please)
      ↓
release pull request  ← proposed version + generated CHANGELOG section
      ↓
maintainer review  (human approval; nothing publishes before this)
      ↓
merge the release PR
      ↓
version bump + CHANGELOG.md + git tag vX.Y.Z + GitHub Release
      ↓
documentation deploy (existing Documentation workflow)
```

Key properties:

- **Nothing is released from an arbitrary push.** A push to `master` only opens or
  updates the release PR. The release is published when a maintainer merges it.
- **Merge commits and bot PRs are ignored** by the conventional-commit parser; only
  release-relevant types bump the version.
- **The changelog is generated.** New release sections are inserted directly under
  `# Changelog`, numbered `[X.Y.Z]` with a compare link, and grouped as
  `### Added` / `### Fixed` / `### Performance` / `### Changed` / `### Reverted`.
  `docs`, `test`, `style`, `chore`, `ci`, `build`, and `deps` commits do not get a
  section.
- **Breaking changes are called out** in a `### ⚠ BREAKING CHANGES` section.
- **Historical entries are preserved.** Release Please only prepends; it never
  rewrites earlier sections.
- **`## [Unreleased]` is not the release mechanism.** It is a transitional
  staging block left over from the pre-automation changelog. Do not add entries
  to `CHANGELOG.md` by hand; the generated section is authoritative. Delete any
  stale `## [Unreleased]` content when the release PR that supersedes it merges.

### Configuration

| File | Purpose |
|---|---|
| `release-please-config.json` | Release type, bump policy (`bump-minor-pre-major`), changelog sections, tag format, and extra version files |
| `.release-please-manifest.json` | Last released version (`{".": "0.2.1"}`); updated by Release Please |
| `.github/workflows/release-please.yml` | Runs Release Please on pushes to `master` |

`bootstrap-sha` in the config is a one-time seed so the first release PR
collects commits after `v0.2.1` instead of the entire history. Once the first
release PR has merged it is ignored and can be removed.

### One-time repository setup

These are GitHub settings, not code, so they must be applied by a maintainer:

- **Actions permissions:** Settings → Actions → General → Workflow permissions must allow
  read and write access, otherwise the job-level `contents: write` and
  `pull-requests: write` permissions are capped and Release Please cannot open its PR.
- **Token:** the workflow falls back to `GITHUB_TOKEN`, which is enough to open and update
  the release PR. GitHub does not start workflow runs for events raised by `GITHUB_TOKEN`,
  so that release PR will not run the required `Tests` and `Documentation` checks. Add a
  `RELEASE_PLEASE_TOKEN` repository secret — a fine-grained PAT or GitHub App installation
  token with `contents: write` and `pull-requests: write` — to make the release PR run the
  normal checks. Without it, a maintainer must trigger the checks by hand before merging.
- **Branch protection:** keep `Tests` (the aggregated check) and `Documentation` required on
  `master`. That is what stops an unvalidated release from shipping: the release PR cannot
  merge until both are green.

### Tags

Release tags are `vMAJOR.MINOR.PATCH` — `v0.2.1`, `v0.3.0`, `v1.0.0` — and
prereleases are `v0.3.0-beta.1`. The `v` prefix matches the existing tag
convention and is produced by `include-v-in-tag: true`.

**Never reuse, move, or rewrite a published tag.** Published versions are
immutable. If a release is wrong, cut a new patch release; do not re-point the
tag.

---

## 5. Release checklist

### Before the release

- [ ] `master` is green: the aggregated `Tests` check passes (lint, security,
      offline test matrix, integration tests).
- [ ] Every PR since the last release follows Conventional Commits
      (`make commitlint`).
- [ ] Breaking changes are explicitly marked with `!` or a `BREAKING CHANGE:`
      footer and have migration notes ready.
- [ ] No known release-blocking defect is open against the milestone.
- [ ] `make release-check` passes locally (the full `ci-local` gate plus the
      commit convention).
- [ ] `python scripts/check_public_metadata.py` passes.
- [ ] `make docs-build` passes if documentation, theme, or public-site files changed.

### Reviewing the release PR

The generated release PR is a starting point. Before merging it:

- [ ] The proposed version matches the decision table (`make release-plan` should
      agree with it). Override an intentional choice with a `Release-As: X.Y.Z`
      commit footer; never hand-edit the version in the release PR.
- [ ] The generated changelog section reads as user-facing impact, not a commit
      dump. Reword by amending the commit subjects and letting Release Please
      regenerate, or accept the generated text and refine it in the GitHub Release.
- [ ] Update the prose surfaces the generator cannot touch:
      `README.md`, `docs/project/releases.md`, `docs/project/status.md`,
      `docs/project/citation.md`, `docs/index.md`, `docs/data/coverage.md`,
      `docs/getting-started/*`, `docs/public-launch.md`, `docs/project/launch-copy.md`,
      `docs/media/README.md`, and `docs/project/github-public-settings.md`.
- [ ] Refresh `docs/generated/public-status.yaml` metrics (`registry_modules`,
      `l2_strict_validated`, `reference_tier`, `ci_validated`, `tests`, …) and
      `release_date`, and update the matching README snapshot table.
- [ ] Add `docs/release-notes/vX.Y.Z.md` from
      [`docs/project/release-notes-template.md`](docs/project/release-notes-template.md).
- [ ] `python scripts/check_public_metadata.py` passes on the release PR — this is
      what forces the two bullets above to be complete.
- [ ] Delete any stale `## [Unreleased]` content that the generated section
      supersedes.
- [ ] Zenodo: if this is the first release of a new version line, follow
      [`docs/project/zenodo-setup.md`](docs/project/zenodo-setup.md) and add the
      version DOI to `CITATION.cff`, `codemeta.json`, and `README.md`.

### Merging the release PR

- [ ] Merge the release PR through the normal review path. Branch protection
      requires the `Tests` check, so an unvalidated release cannot ship.
- [ ] Release Please then bumps the version, updates `CHANGELOG.md`, creates the
      `vX.Y.Z` tag, and creates the GitHub Release.

### After the release

- [ ] Verify the GitHub Release body: major features, fixes, breaking changes,
      migrations, security-relevant changes, deprecations, and upgrade steps.
- [ ] Verify the tag (and that `vX.Y.Z` is not a prerelease, unless intended).
- [ ] Verify the public documentation deployed and points at the new version.
- [ ] If Docker images are published, rebuild and tag them (below).
- [ ] Confirm `.release-please-manifest.json` records the released version.
- [ ] Start accumulating changes for the next release.

---

## 6. Branch strategy

Trunk-based, with the primary branch always releasable:

- `master` is the release branch and the target of every PR.
- Work happens on short-lived branches: `feature/…`, `fix/…`, `docs/…` (see
  [CONTRIBUTING.md](CONTRIBUTING.md)).
- Release tooling only ever runs from `master`.
- Prerelease channels use `release/X.Y` branches (see the prerelease policy above).

No Git-flow model, no long-lived `develop` branch.

---

## 7. Publishing

### PyPI (not automated)

PyPI publishing is **not** configured in CI, and nothing in the release workflow
publishes a package. When distribution via PyPI is ready, prefer
[trusted publishing](https://docs.pypi.org/trusted-publishers/) (OIDC) over a
long-lived API token, and gate the publish job on `make release-check` plus the
`Tests` check. Prereleases must be uploaded with a PEP 440 prerelease identifier
(`0.3.0b1`) so they never become the default install.

### Docker / OCI images (manual)

There is no image registry workflow yet. After a stable tag:

```bash
docker build -t med-research:X.Y.Z .
docker tag med-research:X.Y.Z med-research:latest
```

Tag convention when a registry is added: the exact version (`1.4.2`), plus
`1.4` and `1` aliases where useful. Point `latest` only at stable releases —
never at an alpha, beta, or rc.

### Public demo

The public demo deploy (`.github/workflows/demo-deploy.yml`) is **manual-only**
and is not tied to the release train. See
[docs/deployment-demo.md](docs/deployment-demo.md).

---

## 8. Security releases

Follow [SECURITY.md](SECURITY.md): coordinate privately, land the fix on
`master`, cut a PATCH release, and publish a GitHub Security Advisory.

Never publish an embargoed vulnerability in `CHANGELOG.md` or the GitHub Release
before coordinated disclosure. When the fix is already public, describe the
impact without publishing exploit instructions, and keep the release notes
focused on what users must upgrade.

---

## 9. Hotfix process

A hotfix is an ordinary PATCH release, not a separate flow:

1. Branch `fix/…` from the released tag (`git switch -c fix/… v0.2.1`).
2. Land the minimal fix with a `fix:` commit (add `!` only if it is truly
   breaking — in which case it is a MINOR per the pre-1.0 policy).
3. Merge to `master`, let the standard checks pass.
4. Merge the resulting release PR; Release Please cuts the next patch with a
   changelog entry that references the fix.

Do not re-tag or amend an existing release for a hotfix.

---

## 10. Notes for coding agents

- Use Conventional Commits for every commit you create. The release version is
  derived from your subject line.
- Classify your change as none / patch / minor / major and record breaking
  changes explicitly (`!` or a `BREAKING CHANGE:` footer with a migration note).
- Never invent or hand-edit a version number. `release-please` owns
  `pyproject.toml`, `CITATION.cff`, `codemeta.json`,
  `docs/generated/public-status.yaml`, `src/med_research/__init__.py`, and
  `.release-please-manifest.json`.
- Never create a release, push a tag, or publish anything unless explicitly
  instructed by a maintainer.
- Never rewrite published tags, release history, or released changelog sections.
- Treat the versioned public API (`/api/v1`), the CLI surface, configuration and
  environment variables, and serialized data contracts as compatibility
  contracts.
- When a change alters one of those contracts, say so in the commit and in the
  release notes.
