# NosoGraph Public Presence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an evidence-first NosoGraph GitHub Pages front door and aligned GitHub README without introducing a second web runtime.

**Architecture:** Keep MkDocs Material as the deployment and documentation system. Add a custom homepage in `docs/index.md`, shared brand tokens in `docs/stylesheets/nosograph.css`, progressive-enhancement graph behavior in `docs/javascripts/home.js`, and metadata/theme changes in `mkdocs.yml` and `docs-theme/main.html`. Generate all brand SVG variants from one Python geometry source.

**Tech Stack:** MkDocs Material, Markdown/HTML, CSS, vanilla JavaScript, Python standard library, standalone SVG.

## Global Constraints

- Canonical public positioning: **NosoGraph — Disease Intelligence. Connected.**
- Current maturity: Public Alpha; research use only; no hosted demo is deployed.
- Palette: `#08142D`, `#102246`, `#19D2C7`, `#2F86FF`, `#7252F4`, `#73819A`, `#DCE4EF`, `#F8FBFF`.
- Use Sora/Inter/JetBrains Mono family names with system fallbacks and no runtime Google Fonts dependency.
- Gradient is reserved for mark/selected Graph/important graph accents.
- Do not invent metrics, institutions, stars, contributors, studies, or partnerships.
- Preserve MkDocs search, navigation, TOC, responsive reading, code blocks, deep links, keyboard access, and reduced-motion behavior.
- The graph is NosoGraph-specific, labeled, illustrative when not live, and never the sole information channel.

---

### Task 1: Establish reproducible brand asset generation

**Files:**
- Create: `scripts/generate_brand_assets.py`
- Create/modify: `docs/assets/brand/*.svg`
- Modify: `docs/assets/brand/README.md`

- [ ] Define one canonical anchor/edge topology and helper functions for full-color, monochrome, reversed, compact, and micro variants.
- [ ] Generate standalone SVGs for the mark, wordmark, tagline lockup, favicon, avatar, hero, and social/OG treatment.
- [ ] Document that generated SVGs derive from the one geometry source and list each asset's use.
- [ ] Keep social metadata on SVG treatment until a binary PNG regeneration path is available; remove old palette references from every used SVG.

### Task 2: Add shared theme tokens and homepage behavior

**Files:**
- Create: `docs/stylesheets/nosograph.css`
- Create: `docs/javascripts/home.js`
- Modify: `mkdocs.yml`
- Modify: `docs-theme/main.html`

- [ ] Add semantic color, typography, spacing, container, graph, motion, surface, status, and focus tokens.
- [ ] Override Material chrome to share the NosoGraph identity while keeping light documentation reading surfaces.
- [ ] Add responsive homepage section styles, reduced-motion rules, accessible focus states, and mobile-safe tables/graph treatment.
- [ ] Add progressive graph focus/hover behavior using native SVG focusable groups and an aria-live status.
- [ ] Update metadata to the current positioning and current v2.4.0 social/OG treatment.

### Task 3: Build the custom Pages homepage

**Files:**
- Modify: `docs/index.md`

- [ ] Implement the approved 12-part flow: hero, audience routing, problem, transformation, graph/evidence explanation, researcher path, developer path, maturity, credibility, docs index, open-source CTA, footer.
- [ ] Link every CTA to an existing documentation or repository destination.
- [ ] Use only repository-backed current facts from `docs/generated/public-status.yaml`, dated as v2.4.0.
- [ ] Include static text alternatives for the graph and explicit research-use/maturity language.

### Task 4: Align README and public messaging

**Files:**
- Modify: `README.md`
- Modify: `docs/project/launch-copy.md`
- Modify: `docs/assets/brand/README.md`

- [ ] Make README the operational repository front door with the new positioning, lockup, short visual, verified badges, quick start, evidence model, researcher/developer paths, maturity, and contribution links.
- [ ] Remove stale top-level v2.3 current-state wording while preserving historical release language.
- [ ] Keep compatibility names (`med-research`, `med_research`) accurate and visible where relevant.

### Task 5: Correct current-version and navigation drift

**Files:**
- Modify: `mkdocs.yml`
- Modify: `docs/public-launch.md`
- Modify: `docs/data/coverage.md`
- Modify: `docs/getting-started/demo.md`
- Modify: `docs/getting-started/faq.md`
- Modify: `docs/concepts/claims.md`
- Modify: `docs/concepts/curation-tiers.md`
- Modify: `docs/project/releases.md`
- Modify: `docs/project/github-public-settings.md`
- Modify: `docs/media/README.md`
- Modify: `docs/project/package-naming.md` and other current-state pages found by audit

- [ ] Classify v2.3.0 references as historical or current; change only current-state errors to v2.4.0.
- [ ] Re-group MkDocs navigation around Overview, Research, Concepts, Data, Using NosoGraph, Developers, Contributing, and Project while preserving existing destinations.
- [ ] Remove stale current release links and update public-demo wording to v2.4.0.

### Task 6: Make metadata checks prevent public drift

**Files:**
- Modify: `scripts/check_public_metadata.py`

- [ ] Validate `CITATION.cff` preferred-citation version as well as top-level version.
- [ ] Validate a fixed set of current public surfaces contain v2.4.0/current release links where appropriate.
- [ ] Validate the homepage/README positioning and canonical repository/docs URLs.
- [ ] Keep historical audit/changelog/release-note references exempt from current-state checks.

### Task 7: Validate, inspect, and correct

**Files:**
- No new source files unless a failing check requires one.

- [ ] Run `python -m mkdocs build --strict` or project-equivalent docs build and fix warnings/errors.
- [ ] Run `python scripts/check_public_metadata.py` and link/reference checks.
- [ ] Run relevant repository tests and `git diff --check`.
- [ ] Inspect generated Pages output at mobile/tablet/desktop widths, light/dark modes, keyboard focus, and reduced motion; correct any issues found.
- [ ] Review final diff for stale current-state wording, old colors/assets, broken links, and unrelated changes.
