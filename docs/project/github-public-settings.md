# Manual GitHub settings

Code cannot apply these. Maintainer actions only.

## DONE in this repository (as of audit)

- Public repo `AdamEddahmouni/nosograph`
- Issues, Discussions, Projects enabled
- Dependabot config present (`.github/dependabot.yml`)
- Latest release v2.3.0

## MANUAL_ACTION_REQUIRED

1. **Social preview:** Settings → General → Social preview → upload `docs/assets/brand/social-preview.png`.
2. **About homepage:** set to `https://adameddahmouni.github.io/nosograph/` after Pages is live (keep description as-is if still accurate).
3. **Topics:** add `biomedical-knowledge-graph`, `disease-ontology`, `drug-repurposing`, `evidence-synthesis`, `fastapi`, `python`, `research-software`, `systems-biology` to the existing set if missing.
4. **GitHub Pages:** Settings → Pages → Source **GitHub Actions** (workflow `.github/workflows/docs.yml`).
5. **Discussions categories:** Announcements, Q&A, Ideas, Research, Data & Curation, Show and Tell, General. Seed posts: [github-discussions-seed.md](github-discussions-seed.md).
6. **Private vulnerability reporting:** Settings → Code security → enable private reporting if not on.
7. **Wiki:** disable (canonical docs are version-controlled). Recommendation: `DISABLE_WIKI`.
8. **Projects:** keep maintainer-oriented; do not treat the board as the public roadmap.
9. **Zenodo:** [zenodo-setup.md](zenodo-setup.md).
10. **Profile pin:** pin NosoGraph with one-line description (do not edit unrelated profile content).

## OPTIONAL

- OpenSSF Scorecard later; see [openssf-readiness.md](openssf-readiness.md).
- Custom domain when ready (`site_url` already uses github.io).
