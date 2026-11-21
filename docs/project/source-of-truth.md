---
description: Which repository artifact owns each class of public fact — versions, metrics, citation data, capability status, and documentation.
---

# Documentation source of truth

| Artifact | Owns |
|----------|------|
| README.md | Public overview |
| docs/ | User and technical documentation |
| ROADMAP.md | Public roadmap |
| docs/roadmaps/ | Engineering plans |
| docs/audits/ | Validation / release evidence |
| CHANGELOG.md | Version history |
| pyproject.toml | Canonical version (`[project].version`) |
| .release-please-manifest.json | Last released version tracked by Release Please |
| release-please-config.json | Release automation configuration (bump policy, changelog sections, tag format) |
| RELEASING.md | Versioning and release policy |
| CITATION.cff | Canonical citation |
| docs/generated/public-status.yaml | Current public metric numbers and release snapshot |
| CONTRIBUTING.md | Contribution workflow |
| GOVERNANCE.md | Governance |
| SECURITY.md | Vulnerability reporting |
