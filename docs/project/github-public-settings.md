# Manual GitHub settings

Code cannot apply these. Maintainer actions only.

## Canonical About values

- **Description:** Open-source research software for connecting disease knowledge, evidence, and provenance across biomedical sources.
- **Website:** https://adameddahmouni.github.io/nosograph/
- **Social preview:** `docs/assets/brand/social-preview.png` (1280×640)
- **Primary topics:** `biomedical-knowledge-graph`, `bioinformatics`, `disease-ontology`, `evidence-synthesis`, `fastapi`, `knowledge-graph`, `open-source`, `python`, `research-software`, `systems-biology`

Treat these values as the maintainer checklist whenever positioning or the social preview changes.

## Completed in this repository (2026-08-22)

- Public repo `AdamEddahmouni/nosograph`
- Issues, Discussions, Projects enabled
- Dependabot config present (`.github/dependabot.yml`)
- Current public-alpha release v0.2.1; archived releases: v0.2.0 and the v0.1.0 baseline
- Canonical About description and GitHub Pages homepage
- Custom 1280×640 social preview from `docs/assets/brand/social-preview.png`
- Private vulnerability reporting enabled. Secret scanning and push protection are **documented** as enabled; this environment could not re-verify via GitHub API (null/403). Do not treat them as proven from this file.
- `master` ruleset (`master protection`): required checks **`Tests`** and **`Documentation`**; **0** approving reviews; stale reviews are **not** dismissed on push; thread resolution required; branch must be up to date. `typecheck` is a strict CI job and is **merge-blocking** because the `Tests` aggregator lists it in `needs:` (not a separate ruleset context). Required approvals remain 0.
- Eight [good-first issues](good-first-issues.md), two research-focused categories, and five [seed Discussions](github-discussions-seed.md)
- NosoGraph pinned on the maintainer profile
- Zenodo release archival enabled; concept DOI [10.5281/zenodo.22055279](https://doi.org/10.5281/zenodo.22055279), historical version DOIs for [v0.2.0](https://doi.org/10.5281/zenodo.22062925) and [v0.1.0](https://doi.org/10.5281/zenodo.22055280) (v0.2.1 has no archive record yet)

## Applied via API (verify in GitHub UI)

- **Topics:** full 20-topic set including `biomedical-knowledge-graph`, `disease-ontology`, `drug-repurposing`, `evidence-synthesis`, `fastapi`, `python`, `research-software`, `systems-biology`.
- **Wiki:** disabled (`DISABLE_WIKI`). Canonical docs remain version-controlled in `docs/`.
- **GitHub Pages source:** GitHub Actions (`build_type=workflow`). Deploy job lives in `.github/workflows/docs.yml`.

## Operating notes

- Keep `social-preview.svg` as the canonical editable source and export the PNG after changes.
- Keep Projects maintainer-oriented; do not treat the board as the public roadmap.
- Use the repository-admin pull-request bypass only after `Tests` and `Documentation` pass.
- Preserve the v2.x tags and legacy prereleases as historical records.

## OPTIONAL

- OpenSSF Scorecard later; see [openssf-readiness.md](openssf-readiness.md).
- Custom domain when ready (`site_url` already uses github.io).
