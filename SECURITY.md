# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 2.x     | Yes       |
| < 2.0   | No        |

Security fixes are applied to the latest 2.x release on the `master` branch.

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report security issues through one of these channels:

1. **GitHub Security Advisories** (preferred): [Report a vulnerability](https://github.com/AdamEddahmouni/med-research/security/advisories/new) for the NosoGraph repository (currently hosted at `med-research` on GitHub)
2. **Email**: Open a private security advisory via GitHub or contact the repository maintainer directly if advisories are unavailable.

Include:

- A description of the issue and potential impact
- Steps to reproduce (proof of concept if available)
- Affected version or commit hash
- Suggested remediation, if known

## Response timeline

- **Acknowledgment** within 5 business days
- **Initial assessment** within 10 business days
- **Fix or mitigation plan** within 90 days for confirmed issues, depending on severity

We will coordinate disclosure with reporters and publish a security advisory when a fix is available.

## Scope

**NosoGraph** is a **research-only** computational biomedical platform. It is designed for public biomedical knowledge, literature, and curated disease data — **not** for storing or processing protected health information (PHI) or patient-identifiable data.

Out of scope for security reports:

- Issues that require uploading PHI or clinical patient records (the platform does not accept such data by design)
- Social engineering against individual researchers
- Denial-of-service attacks against public demo instances without prior coordination

In scope:

- Authentication and authorization bypasses
- Remote code execution or unsafe deserialization
- SQL injection, path traversal, or SSRF in API endpoints
- Secret leakage in logs, responses, or repository artifacts
- Dependency vulnerabilities with a demonstrated exploit path in this codebase

## Secure deployment

When exposing the API beyond localhost:

- Set `DEBUG=false` and a strong `API_KEY`
- Set `AUTH_SESSION_SECRET` (or rely on `API_KEY` as fallback) for workspace sessions
- Restrict `CORS_ORIGINS` to trusted front-end origins
- Place the API behind a reverse proxy with TLS
- Do not commit `.env` files or API keys to version control

See [docs/deployment.md](docs/deployment.md) and [docs/api-reference.md](docs/api-reference.md) for environment variable reference.
