# OpenSSF / supply-chain readiness (assessment)

Not chasing a badge in this sprint.

| Check | State |
|-------|--------|
| Security policy | Present (`SECURITY.md`) |
| Releases | v0.1.0 published and archived; v2.x retained as legacy prereleases |
| Workflow permissions | `contents: read` on Tests |
| Dependabot | Configured |
| Pinned Actions | Uses major tags (`@v7`); pin-to-SHA is a future hardening |
| Branch protection | Ruleset requires `Tests` + `Documentation`, **0** approvals, thread resolution, current branch |
| Signed tags | v0.1.0 has a verified ED25519 SSH signature |
| Vulnerability reporting | Private reporting enabled |
| Secret protection | Documented as enabled; **not re-verified** via this environment's GitHub API |
| CodeQL | No workflow in repo. Dynamic/default setup has been observed to run; **not** a ruleset required check. Admin API 403 here — do not claim merge-blocking. |
| Scorecard | Optional later |

Do not enable noisy workflows solely for a badge.
