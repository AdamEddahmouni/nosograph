# NosoGraph Repository Polish Design

**Status:** Approved
**Date:** 2026-09-01

## Goal

Complete a focused presentation and consistency pass across the NosoGraph GitHub repository and documentation site. The result should help two audiences equally well:

- biomedical researchers evaluating whether NosoGraph supports their work;
- developers and open-source contributors deciding whether to run, extend, or contribute to it.

This work refines the existing public-presence redesign. It does not create a new brand, add product functionality, or reopen the established evidence-first positioning.

## Recommended approach

Use a balanced, conversion-first public structure. The repository should explain the product quickly, demonstrate real capabilities, establish scientific and engineering trust, and route each audience toward an appropriate next action.

Two alternatives were rejected:

- A research-first editorial presentation would explain the scientific model well but slow down setup and contribution discovery.
- A developer-first open-source presentation would make installation prominent but undersell the research problem and product value.

The chosen approach keeps both paths visible without duplicating the full documentation site in the README.

## Surface responsibilities

### GitHub README

The README is the fast evaluation and action surface. A visitor should be able to understand what NosoGraph is, see what exists, recognize its limitations, and choose a next step without reading the entire page.

Its hierarchy is:

1. Brand lockup, concise value proposition, and verified badges.
2. Primary actions for documentation and local evaluation.
3. One strong product visual with a short capability summary.
4. A concise overview of evidence exploration, comparison, provenance, and extensibility.
5. Parallel researcher and developer/contributor paths.
6. A minimal quick start, with detailed alternatives delegated to documentation.
7. Evidence model, maturity, and current limitations.
8. Compact contribution, citation, security, and license information.

The README should become shorter, more scannable, and more visual. It must not become a second documentation homepage.

### Documentation homepage

The documentation homepage is the deeper product and learning surface. It explains the problem, shows authentic product interfaces, and routes users into task-oriented documentation.

Its hierarchy is:

1. Focused hero with one primary and two secondary actions.
2. Product imagery showing real interfaces and workflows.
3. Source to claim to evidence to provenance explanation.
4. Researcher and developer journeys.
5. Current capability and maturity summary.
6. Scientific and technical trust signals.
7. Documentation directory and contribution call to action.

### Supporting repository surfaces

The following files and settings reinforce trust rather than repeat the product story:

- contribution and community guidance;
- security and responsible-reporting information;
- issue and pull-request templates;
- citation and release metadata;
- package metadata and project URLs;
- GitHub About text, topics, social preview, and repository settings documentation.

## Visual direction

Preserve the existing NosoGraph identity: deep navy, teal, blue, violet, Sora display typography, Inter body typography, and JetBrains Mono for technical contexts. Refine hierarchy through spacing, type scale, content density, and image selection rather than adding decorative effects or a competing visual language.

Use product imagery only when it communicates real functionality. Decorative graph treatments must remain secondary to readable copy and actionable navigation. The README and site must remain effective on mobile, in dark mode, with keyboard navigation, and when reduced motion is requested.

## Content and trust rules

Public claims must be conservative and repository-backed.

- `docs/generated/public-status.yaml` remains the source of truth for current metrics and maturity facts.
- Evidence supports claims but is not automatic proof.
- Associations are not causation.
- Missing metadata remains unknown rather than becoming false certainty.
- Registry breadth is not equivalent to deep curation.
- NosoGraph must not be presented as medical advice, a diagnostic system, clinical decision support, or a hosted service when no public hosted service exists.
- Unverified user counts, institutions, partnerships, publications, or impact claims must not be introduced.

Version, release, DOI, package-name compatibility, canonical URLs, and hosted-demo wording must be consistent across current public surfaces. Historical release material remains historical and should not be mechanically rewritten.

## Scope

Included:

- README hierarchy, copy, links, badges, and product imagery;
- documentation homepage hierarchy and presentation;
- public-facing repository documents and templates where consistency issues are found;
- repository metadata guidance for settings that require maintainer action;
- visual and responsive refinements needed to support the approved hierarchy;
- focused automated checks that prevent public metadata drift.

Excluded:

- application feature development;
- a new logo or visual identity;
- fabricated metrics or promotional claims;
- broad refactoring outside the public repository and documentation surfaces;
- deployment of a public hosted NosoGraph application;
- changes to historical records solely to make them match current-version wording.

The untracked `artifacts/` directory is outside this work and must remain untouched.

## Validation

Completion requires evidence from:

- a strict MkDocs build;
- public metadata and site-consistency checks;
- link and reference validation available in the repository;
- focused documentation/site tests;
- formatting and `git diff --check` checks;
- visual inspection of the README and generated site at representative desktop and mobile widths;
- keyboard-focus, dark-mode, and reduced-motion inspection where applicable;
- a final copy audit for stale current-state wording and unsupported claims.

## Success criteria

The polishing pass succeeds when:

1. A new visitor can identify NosoGraph, its research boundary, and its two main audience paths from the README's opening sections.
2. Researchers can reach evidence-focused workflows without navigating through contributor material.
3. Developers can reach setup, architecture, and contribution guidance without reading the full scientific narrative.
4. The README and documentation homepage feel like complementary parts of one product rather than duplicated landing pages.
5. Current public facts are consistent across repository surfaces and guarded against drift.
6. The presentation is polished, accessible, responsive, and based on real product capabilities.
