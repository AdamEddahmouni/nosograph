# Security & Privacy Audit

**Date:** 2026-08-20  
**Scope:** Secrets, auth, API surface, PHI, dependencies

## Summary

**Classification: BETA — suitable for research deployment with documented hardening steps.** No critical secret leakage found. Platform explicitly excludes PHI.

## Secret scan results

| Pattern | Result |
|---------|--------|
| OpenAI `sk-...` keys | Not found in tracked files |
| AWS `AKIA...` keys | Not found |
| GitHub `ghp_...` tokens | Not found |
| Hardcoded passwords | Not found (placeholders in `.env.example` only) |

`.env` is gitignored. Commented optional keys in `.env.example` are acceptable.

## Authentication & authorization

| Feature | Maturity | Notes |
|---------|----------|-------|
| Optional `API_KEY` gate | STABLE | Required when `DEBUG=false` |
| Evidence Workspace sessions | BETA | `AUTH_MODE=local` or `proxy` |
| Rate limiting (Redis) | BETA | Configurable fail-open/closed |
| CORS restrictions | STABLE | `CORS_ORIGINS` env |
| CSP for dashboard | BETA | Off by default |

## API security controls

- Max request body size configurable
- Bandit scan in CI (`-ll`, excludes disease data tree)
- pip-audit on locked requirements
- SQL parameterized via repository patterns (biomed, workspace)

## Privacy / PHI

| Control | Status |
|---------|--------|
| No PHI in repo | PASS |
| Research-only disclaimers | PASS (SECURITY.md, matching API) |
| Patient matching API | Does not persist submitted vectors (per CHANGELOG) |
| Issue/PR templates | PHI exclusion checkbox |

## Dependency security

- Locked toolchain with `lock_verify.py`
- Dependabot configured (`.github/dependabot.yml`)
- pip-audit in CI security job

## Deployment recommendations (documented)

1. `DEBUG=false`, strong `API_KEY`
2. TLS via reverse proxy
3. Restrict `CORS_ORIGINS`
4. Set `AUTH_SESSION_SECRET` for workspace sessions
5. Enable GitHub secret scanning after repo goes public

## Findings & remediation

| ID | Finding | Severity | Action |
|----|---------|----------|--------|
| S-01 | No SECURITY.md NosoGraph branding | P3 | Updated branding |
| S-02 | CSP off by default | P2 | Documented in deployment.md |
| S-03 | Plaintext `LOCAL_AUTH_USERS` for dev | P3 | Documented as dev-only |

## Blockers

**None** for public alpha with SECURITY.md and deployment guidance.
