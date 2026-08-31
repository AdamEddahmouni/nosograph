---
title: Style system QA
description: Local design-system fixture. Excluded from published builds via exclude_docs.
---

# Style system QA

Local fixture for design-system primitives. Not published (`exclude_docs` in `mkdocs.yml`). All values are truthful per `truth-1.3.md`.

## Type scale

<div class="ng-display" style="font-size: var(--ng-text-display); line-height: var(--ng-leading-display); font-weight: 650;">Display — Disease Intelligence. Connected.</div>

<h2 style="font-size: var(--ng-text-h2); font-weight: 620;">Section heading — evidence you can inspect</h2>

<h3 style="font-size: var(--ng-text-h3); font-weight: 600;">Small heading — curation tiers</h3>

<p class="ng-lede" style="font-size: var(--ng-text-lede); line-height: var(--ng-leading-lede); color: var(--ng-ink-soft);">Lede: NosoGraph connects disease knowledge, evidence, and provenance across biomedical sources — research use only.</p>

<p>Body 16px — registry breadth is not curation depth: 88 strict L2-validated modules, 6 reference modules, 8 CI-validated modules out of 10,407 scaffold registry entries.</p>

<p><span class="ng-eyebrow">Eyebrow · metadata floor 12px</span></p>

## Buttons

<p>
<a class="ng-btn ng-btn--primary" href="#">Primary action</a>
<a class="ng-btn ng-btn--secondary" href="#">Secondary</a>
<a class="ng-btn ng-btn--ghost" href="#">Ghost</a>
<a class="ng-btn ng-btn--text" href="#">Text action</a>
<a class="ng-btn ng-btn--primary ng-btn--sm" href="#">Small</a>
</p>

## Status chips

<p>
<span class="ng-chip ng-chip--alpha">PUBLIC_ALPHA</span>
<span class="ng-chip ng-chip--beta">BETA</span>
<span class="ng-chip ng-chip--stable">STABLE</span>
<span class="ng-chip ng-chip--experimental">EXPERIMENTAL</span>
<span class="ng-chip ng-chip--planned">PLANNED</span>
<span class="ng-chip ng-chip--deprecated">DEPRECATED</span>
<span class="ng-chip ng-chip--neutral">NOT_IMPLEMENTED</span>
</p>

## Evidence states

<p>
<span class="ng-ev ng-ev--supports">SUPPORTS</span>
<span class="ng-ev ng-ev--contradicts">CONTRADICTS</span>
<span class="ng-ev ng-ev--inconclusive">INCONCLUSIVE</span>
<span class="ng-ev ng-ev--unasserted">UNASSERTED</span>
</p>

<p>
<span class="ng-ev ng-ev--lg ng-ev--supports">SUPPORTS</span>
<span class="ng-ev ng-ev--lg ng-ev--contradicts">CONTRADICTS</span>
</p>

## Provenance trace

<div class="ng-trace">
  <div class="ng-trace__step">
    <span class="ng-trace__marker">01</span>
    <div><div class="ng-trace__title">Disease</div><div class="ng-trace__detail">Systemic lupus erythematosus — MONDO:0005151</div></div>
  </div>
  <div class="ng-trace__step">
    <span class="ng-trace__marker">02</span>
    <div><div class="ng-trace__title">Typed claim</div><div class="ng-trace__detail"><span class="ng-predicate">associated_with</span> — direction recorded, never inferred</div></div>
  </div>
  <div class="ng-trace__step">
    <span class="ng-trace__marker">03</span>
    <div><div class="ng-trace__title">Evidence</div><div class="ng-trace__detail"><span class="ng-ev ng-ev--supports">SUPPORTS</span> — conflicting evidence can coexist</div></div>
  </div>
  <div class="ng-trace__step">
    <span class="ng-trace__marker">04</span>
    <div><div class="ng-trace__title">Study</div><div class="ng-trace__detail">Human · case-control · PubMed source record</div></div>
  </div>
  <div class="ng-trace__step">
    <span class="ng-trace__marker">05</span>
    <div><div class="ng-trace__title">Source</div><div class="ng-trace__detail">PubMed — STABLE adapter, per source registry</div></div>
  </div>
  <div class="ng-trace__step">
    <span class="ng-trace__marker">06</span>
    <div><div class="ng-trace__title">Provenance</div><div class="ng-trace__detail">Snapshot · manifest fingerprint · 9-stage verified sync</div></div>
  </div>
</div>

## Metadata strip

<p class="ng-meta-strip">
<span class="ng-meta">v0.2.1</span>
<span class="ng-meta ng-meta--caps">PUBLIC_ALPHA</span>
<span class="ng-meta">2026-08-22</span>
<span class="ng-meta">source: public-status.yaml</span>
</p>

<p class="ng-meta">MONDO:0005151 · snapshot 2026-08-20 · fingerprint 9f2a…c41d (truncates safely, full value in title attr)</p>

## Figure plate

<figure class="ng-figure">
  <div class="ng-figure__media">
    <img src="../assets/screenshots/dashboard.png" alt="NosoGraph dashboard, local run" loading="lazy">
  </div>
  <figcaption>NosoGraph web dashboard — Evidence Workspace and pipeline modules on a local run.</figcaption>
  <div class="ng-figure__meta ng-meta">LOCAL RUN · v0.2.1 · 2026-08-22</div>
</figure>

<p class="ng-note">Annotation primitive: hairline leader note for figure callouts, max three per figure.</p>

## Data table

<div class="ng-table-wrap">
<table class="ng-table">
  <thead>
    <tr><th>Surface</th><th>State</th><th class="ng-num">Since</th></tr>
  </thead>
  <tbody>
    <tr><td>CLI</td><td><span class="ng-chip ng-chip--stable">STABLE</span></td><td class="ng-num">v0.1.0</td></tr>
    <tr><td>FastAPI API + dashboard</td><td><span class="ng-chip ng-chip--beta">BETA</span></td><td class="ng-num">v0.1.0</td></tr>
    <tr><td>Evidence Explorer</td><td><span class="ng-chip ng-chip--alpha">PUBLIC_ALPHA</span></td><td class="ng-num">v0.1.0</td></tr>
    <tr><td>Evidence Workspace</td><td><span class="ng-chip ng-chip--beta">BETA</span></td><td class="ng-num">v0.2.0</td></tr>
    <tr><td>Open Targets sync</td><td><span class="ng-chip ng-chip--experimental">EXPERIMENTAL</span></td><td class="ng-num">v0.2.0</td></tr>
    <tr><td>FHIR / OMOP / Phenopackets</td><td><span class="ng-chip ng-chip--neutral">NOT_IMPLEMENTED</span></td><td class="ng-num">—</td></tr>
  </tbody>
</table>
</div>

## Stat rail

<div class="ng-statrail">
  <div class="ng-stat"><span class="ng-stat__value">10,407</span><span class="ng-stat__label">Registry modules (breadth ≠ depth)</span></div>
  <div class="ng-stat"><span class="ng-stat__value">88</span><span class="ng-stat__label">Strict L2-validated modules</span></div>
  <div class="ng-stat"><span class="ng-stat__value">8</span><span class="ng-stat__label">CI-validated (curated eight)</span></div>
  <div class="ng-stat"><span class="ng-stat__value">2,445</span><span class="ng-stat__label">Offline tests in v0.2.1 gate</span></div>
</div>

## Code surfaces

Inline code: `nosograph disease validate sle --strict` inside a sentence.

    $ nosograph disease validate sle --strict
    [ok] sle: 14 claims validated against registry snapshot 2026-08-20

## Surfaces & brand

<p style="display: flex; flex-wrap: wrap; gap: 8px;">
<span style="padding: 12px 16px; border: 1px solid var(--ng-border); border-radius: var(--ng-radius-md); background: var(--ng-bg); color: var(--ng-ink); font-size: var(--ng-text-sm);">page</span>
<span style="padding: 12px 16px; border: 1px solid var(--ng-border); border-radius: var(--ng-radius-md); background: var(--ng-surface); color: var(--ng-ink); font-size: var(--ng-text-sm);">surface</span>
<span style="padding: 12px 16px; border: 1px solid var(--ng-border); border-radius: var(--ng-radius-md); background: var(--ng-surface-alt); color: var(--ng-ink); font-size: var(--ng-text-sm);">surface-alt</span>
<span style="padding: 12px 16px; border-radius: var(--ng-radius-md); background: var(--ng-deep-navy); color: var(--ng-white); font-size: var(--ng-text-sm);">deep-navy</span>
<span style="padding: 12px 16px; border-radius: var(--ng-radius-md); background: var(--ng-navy-layer); color: var(--ng-white); font-size: var(--ng-text-sm);">navy-layer</span>
</p>

<p style="font-family: var(--ng-font-display); font-weight: 650; font-size: var(--ng-text-h2);"><span class="ng-gradient-text">Disease Intelligence. Connected.</span></p>

<hr class="ng-hairline">
