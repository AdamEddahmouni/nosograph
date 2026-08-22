# Manual GitHub settings

Code cannot apply these. Maintainer actions only.

## DONE in this repository (as of audit)

- Public repo `AdamEddahmouni/nosograph`
- Issues, Discussions, Projects enabled
- Dependabot config present (`.github/dependabot.yml`)
- Latest release v2.4.0

## Applied via API (verify in GitHub UI)

- **Topics:** full 20-topic set including `biomedical-knowledge-graph`, `disease-ontology`, `drug-repurposing`, `evidence-synthesis`, `fastapi`, `python`, `research-software`, `systems-biology`.
- **Wiki:** disabled (`DISABLE_WIKI`). Canonical docs remain version-controlled in `docs/`.
- **GitHub Pages source:** GitHub Actions (`build_type=workflow`). Deploy job lives in `.github/workflows/docs.yml`.

## MANUAL_ACTION_REQUIRED

1. **Social preview:** Settings → General → Social preview → Edit → Export the canonical `docs/assets/brand/social-preview.svg` to a 1280×640 PNG, then upload that PNG; keep the SVG as the version-controlled source.
2. **About homepage:** set to `https://adameddahmouni.github.io/nosograph/` after the live site returns HTTP 200.
3. **Discussions categories:** add **Research** and **Data & Curation** if desired (defaults already include Announcements, Q&A, Ideas, Show and tell, General). Seed posts: [github-discussions-seed.md](github-discussions-seed.md).
4. **Private vulnerability reporting:** Settings → Code security → enable private reporting if not on.
5. **Issue labels:** create `disease-curation`, `data-source`, and `research` if templates do not apply them automatically.
6. **Projects:** keep maintainer-oriented; do not treat the board as the public roadmap.
7. **Zenodo:** [zenodo-setup.md](zenodo-setup.md).
8. **Profile pin:** pin NosoGraph with one-line description (do not edit unrelated profile content).

## OPTIONAL

- OpenSSF Scorecard later; see [openssf-readiness.md](openssf-readiness.md).
- Custom domain when ready (`site_url` already uses github.io).
