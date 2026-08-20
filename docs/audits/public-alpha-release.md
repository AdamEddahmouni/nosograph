# NosoGraph Public Alpha Release Record

| Field | Value |
|-------|-------|
| Release date | 2026-08-20 |
| Repository owner | AdamEddahmouni |
| Repository name | nosograph |
| Final public URL | https://github.com/AdamEddahmouni/nosograph |
| Preparation baseline SHA | `063966540ea217bab8e4ff489830433fced2e3c9` |
| Release preparation SHA | `131b72eab6a3ca2826e2dd53829495cab22f67cd` |
| Tag SHA | `131b72eab6a3ca2826e2dd53829495cab22f67cd` |
| Release tag | `v2.2.0` |
| GitHub Release | https://github.com/AdamEddahmouni/nosograph/releases/tag/v2.2.0 |
| Visibility | PUBLIC |
| Validation status | GREEN_WITH_EXPECTED_PLATFORM_VARIANCE |

## Release gates (local)

| Gate | Result |
|------|--------|
| Security | PASS (local bandit/pip-audit in prior audit; hosted bandit job has pre-existing findings) |
| Licensing | PASS (Apache-2.0 + separated data licensing) |
| Build | PASS |
| Tests | PASS (`2331 passed, 20 skipped` offline unit suite) |
| Scientific integrity | PASS (`disease validate sle/ra --strict`) |
| Documentation | PASS |
| Repository hygiene | PASS (transformation reviewed; personal paths scrubbed) |
| OSS infrastructure | PASS |
| GitHub configuration | PASS (description, topics, issues, discussions, dependabot alerts) |
| Public smoke test | PASS |

## GitHub security settings

| Setting | Status |
|---------|--------|
| Dependabot security updates | enabled |
| Dependabot alerts | enabled (via dependency graph) |
| Private vulnerability reporting | available via SECURITY.md |
| Secret scanning | disabled on free personal account tier (attempted post-public) |
| Push protection | disabled on free personal account tier |
| Branch ruleset | master: PR required, no force-push, no deletion |

## Known platform variance

Windows local lock verification reports expected drift:

- `uvloop` and `nvidia-nccl-cu12` not installed on Windows
- Minor version skew: `biopython`, `fastapi`

Classification: `EXPECTED_PLATFORM_VARIANCE` — does not block release.

## Hosted CI notes

- Initial push failed while repository was private (GitHub Actions billing limit).
- After public visibility, workflow dispatch run `32426565825` executed successfully for core jobs (`lint`, tests in progress at release cut).
- Pre-existing non-blocking failures: `typecheck` (informational), `security` bandit scan, `slow-tests` (live APIs).

## Remaining P1 work

| ID | Priority | Status |
|----|----------|--------|
| P1-A | Expand strict validation to L2 corpus | deferred |
| P1-B | Remove disease-specific CLI assumptions | deferred |
| P1-C | Canonical `nosograph` CLI/package migration | deferred |
| P1-D | Evidence UX / provenance traceability | deferred |
| P1-E | NosoGraph Compare vertical slice | deferred |
| P1-F | Curation depth over count | deferred |
| P1-G | Automated biomedical-source sync | deferred |
| P1-H | Public demo deployment | deferred |

## Release artifacts

- GitHub source archives (auto-generated)
- No PyPI publish (deferred by design)
