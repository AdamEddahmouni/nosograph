---
title: NosoGraph — Disease Intelligence. Connected.
description: Open-source research software for connecting disease knowledge, evidence, and provenance across biomedical sources.
---

<div class="ng-homepage">

<section class="ng-hero ng-dark" aria-labelledby="ng-hero-title">
  <div class="ng-shell ng-hero-grid">
    <div>
      <p class="ng-eyebrow ng-eyebrow--light">Open-source biomedical research software</p>
      <h1 id="ng-hero-title" class="ng-visually-hidden">NosoGraph — Disease Intelligence. Connected.</h1>
      <img class="ng-hero-lockup" src="assets/brand/tagline-lockup.svg" alt="" aria-hidden="true">
      <p class="ng-lede">Open-source research software for connecting disease knowledge, evidence, and provenance across biomedical sources.</p>
      <div class="ng-hero-actions" aria-label="Primary actions">
        <a class="ng-button ng-button--primary" href="getting-started/what-is/">Explore documentation</a>
        <a class="ng-button ng-button--secondary" href="getting-started/install/">Run NosoGraph locally</a>
        <a class="ng-button ng-button--secondary" href="https://github.com/AdamEddahmouni/nosograph">View on GitHub</a>
      </div>
      <p class="ng-hero-note">PUBLIC_ALPHA · RESEARCH USE ONLY · NO HOSTED DEMO YET</p>
    </div>
    <figure class="ng-hero-graph" data-ng-graph>
      <svg viewBox="0 0 720 470" role="img" aria-labelledby="ng-graph-title ng-graph-desc">
        <title id="ng-graph-title">Illustrative NosoGraph evidence path</title>
        <desc id="ng-graph-desc">A disease connects to phenotypes, genes, pathways, interventions, and claims. Claims connect to supporting or contradictory evidence, studies, and source provenance.</desc>
        <g aria-hidden="true">
          <line class="ng-graph-edge" data-from="disease" data-to="phenotype" x1="350" y1="205" x2="190" y2="90" />
          <line class="ng-graph-edge" data-from="disease" data-to="gene" x1="350" y1="205" x2="86" y2="180" />
          <line class="ng-graph-edge" data-from="disease" data-to="pathway" x1="350" y1="205" x2="190" y2="320" />
          <line class="ng-graph-edge" data-from="disease" data-to="intervention" x1="350" y1="205" x2="570" y2="100" />
          <line class="ng-graph-edge" data-from="disease" data-to="claim" x1="350" y1="205" x2="495" y2="245" />
          <line class="ng-graph-edge" data-from="gene" data-to="variant" x1="86" y1="180" x2="82" y2="385" />
          <line class="ng-graph-edge" data-from="gene" data-to="pathway" x1="86" y1="180" x2="190" y2="320" />
          <line class="ng-graph-edge" data-from="claim" data-to="evidence-supports" x1="495" y1="245" x2="560" y2="340" />
          <line class="ng-graph-edge" data-from="claim" data-to="evidence-contradicts" x1="495" y1="245" x2="665" y2="300" />
          <line class="ng-graph-edge" data-from="evidence-supports" data-to="study" x1="560" y1="340" x2="410" y2="405" />
          <line class="ng-graph-edge" data-from="evidence-contradicts" data-to="source" x1="665" y1="300" x2="635" y2="415" />
          <line class="ng-graph-edge" data-from="study" data-to="source" x1="410" y1="405" x2="635" y2="415" />
        </g>
        <g class="ng-graph-node" data-node="disease" data-label="Disease" tabindex="0" role="button" aria-label="Focus Disease relationships"><circle cx="350" cy="205" r="31" fill="#19D2C7"/><text x="350" y="210" text-anchor="middle">Disease</text></g>
        <g class="ng-graph-node" data-node="phenotype" data-label="Phenotype" tabindex="0" role="button" aria-label="Focus Phenotype relationships"><circle cx="190" cy="90" r="21" fill="#19D2C7"/><text x="190" y="58" text-anchor="middle">Phenotype</text></g>
        <g class="ng-graph-node" data-node="gene" data-label="Gene" tabindex="0" role="button" aria-label="Focus Gene relationships"><circle cx="86" cy="180" r="22" fill="#2F86FF"/><text x="86" y="224" text-anchor="middle">Gene</text></g>
        <g class="ng-graph-node" data-node="pathway" data-label="Pathway" tabindex="0" role="button" aria-label="Focus Pathway relationships"><circle cx="190" cy="320" r="22" fill="#2F86FF"/><text x="190" y="363" text-anchor="middle">Pathway</text></g>
        <g class="ng-graph-node" data-node="variant" data-label="Variant" tabindex="0" role="button" aria-label="Focus Variant relationships"><circle cx="82" cy="385" r="18" fill="#7252F4"/><text x="82" y="427" text-anchor="middle">Variant</text></g>
        <g class="ng-graph-node" data-node="intervention" data-label="Intervention" tabindex="0" role="button" aria-label="Focus Intervention relationships"><circle cx="570" cy="100" r="23" fill="#7252F4"/><text x="570" y="64" text-anchor="middle">Intervention</text></g>
        <g class="ng-graph-node" data-node="claim" data-label="Claim" tabindex="0" role="button" aria-label="Focus Claim relationships"><circle cx="495" cy="245" r="25" fill="#2F86FF"/><text x="495" y="250" text-anchor="middle">Claim</text></g>
        <g class="ng-graph-node" data-node="evidence-supports" data-label="Evidence · supports" tabindex="0" role="button" aria-label="Focus supporting Evidence relationships"><circle cx="560" cy="340" r="24" fill="#DCE4EF"/><text x="560" y="382" text-anchor="middle">Evidence</text></g>
        <g class="ng-graph-node" data-node="evidence-contradicts" data-label="Evidence · contradicts" tabindex="0" role="button" aria-label="Focus contradictory Evidence relationships"><circle cx="665" cy="300" r="20" fill="#DCE4EF"/><text x="665" y="266" text-anchor="middle">Evidence</text></g>
        <g class="ng-graph-node" data-node="study" data-label="Study" tabindex="0" role="button" aria-label="Focus Study relationships"><circle cx="410" cy="405" r="21" fill="#73819A"/><text x="410" y="445" text-anchor="middle">Study</text></g>
        <g class="ng-graph-node" data-node="source" data-label="Source / provenance" tabindex="0" role="button" aria-label="Focus Source and provenance relationships"><circle cx="635" cy="415" r="23" fill="#7252F4"/><text x="635" y="453" text-anchor="middle">Source</text></g>
      </svg>
      <p class="ng-graph-status" data-graph-status aria-live="polite">Select a labeled entity to trace relationships.</p>
      <figcaption>Illustrative model, not a live query. NosoGraph keeps the claim, evidence direction, study context, and source provenance visible for inspection.</figcaption>
    </figure>
  </div>
</section>

<section class="ng-orientation" aria-labelledby="ng-orientation-title">
  <div class="ng-shell">
    <p class="ng-kicker">Choose a way in</p>
    <h2 id="ng-orientation-title" class="ng-display">Start with the question you need to answer.</h2>
    <div class="ng-orientation-grid">
      <a class="ng-route ng-route--research" href="using/evidence-explorer/">
        <span class="ng-kicker">For researchers</span>
        <h2>Trace what the graph says—and why.</h2>
        <p>Explore disease knowledge, inspect claims, review supporting or contradictory evidence, and follow provenance to the source.</p>
        <span class="ng-button ng-button--text">Open the research path →</span>
      </a>
      <a class="ng-route ng-route--developer" href="developers/architecture/">
        <span class="ng-kicker">For developers</span>
        <h2>Inspect the model. Extend the system.</h2>
        <p>Run the platform locally, inspect the API and data model, add a source or disease, validate it, and contribute the change.</p>
        <span class="ng-button ng-button--text">Open the developer path →</span>
      </a>
    </div>
  </div>
</section>

<section class="ng-problem" aria-labelledby="ng-problem-title">
  <div class="ng-shell ng-problem-grid">
    <div>
      <p class="ng-kicker">The problem</p>
      <h2 id="ng-problem-title">Biomedical evidence is connected in the literature, but scattered in practice.</h2>
      <p class="ng-lede">Diseases, phenotypes, genes, pathways, trials, publications, and therapies live across different resources. Finding a relationship is only the beginning; researchers also need its context and lineage.</p>
    </div>
    <ul class="ng-problem-list">
      <li><strong>Distributed knowledge</strong> Ontologies, genetics resources, pathway databases, trials, and literature each expose a partial view.</li>
      <li><strong>Hard-to-trace claims</strong> A result without its underlying evidence is difficult to review or reproduce.</li>
      <li><strong>Uneven coverage</strong> A registry entry is not the same thing as a deeply curated disease module.</li>
      <li><strong>Uncertain context</strong> Species, study design, origin, and missing metadata change how evidence should be read.</li>
    </ul>
  </div>
</section>

<section class="ng-transformation ng-dark" aria-labelledby="ng-transformation-title">
  <div class="ng-shell">
    <p class="ng-eyebrow ng-eyebrow--light">The NosoGraph layer</p>
    <h2 id="ng-transformation-title">Turn fragmented sources into inspectable relationships.</h2>
    <p class="ng-lede">NosoGraph is a computational layer across upstream resources—not a replacement for them. It normalizes records, creates typed claims, attaches evidence, and preserves provenance for downstream inspection.</p>
    <div class="ng-pipeline" aria-label="NosoGraph evidence pipeline">
      <div class="ng-pipeline-step"><strong>Sources</strong><span>MONDO, HPO, PubMed, trials, genetics, pathways, and drug data.</span></div>
      <div class="ng-pipeline-step"><strong>Normalize</strong><span>Resolve identifiers and preserve source context.</span></div>
      <div class="ng-pipeline-step"><strong>Claims</strong><span>Represent deterministic biomedical assertions.</span></div>
      <div class="ng-pipeline-step"><strong>Evidence</strong><span>Separate supports, contradicts, and inconclusive signals.</span></div>
      <div class="ng-pipeline-step"><strong>Provenance</strong><span>Keep snapshot, import, fingerprint, and source lineage visible.</span></div>
    </div>
    <div class="ng-source-row" aria-label="Example upstream sources"><span class="ng-source-chip">MONDO</span><span class="ng-source-chip">HPO / HPOA</span><span class="ng-source-chip">PubMed</span><span class="ng-source-chip">ClinicalTrials.gov</span><span class="ng-source-chip">Open Targets</span><span class="ng-source-chip">GWAS Catalog</span></div>
  </div>
</section>

<section class="ng-trace ng-dark" aria-labelledby="ng-trace-title">
  <div class="ng-shell ng-trace-grid">
    <div>
      <p class="ng-eyebrow ng-eyebrow--light">Evidence-first by design</p>
      <h2 id="ng-trace-title">See why information is present—not only what was generated.</h2>
      <p class="ng-lede">Evidence records support claims; they are not automatic proof. Associations are not causation. Conflicting evidence can coexist, and unknown metadata remains unknown rather than becoming a confident score.</p>
      <a class="ng-button ng-button--primary" href="using/evidence-explorer/">Read the Evidence Explorer guide</a>
    </div>
    <div>
      <ol class="ng-trace-path" aria-label="Evidence traceability path">
        <li data-step="1">Disease context</li>
        <li data-step="2">Typed claim</li>
        <li data-step="3">Supporting / contradictory evidence</li>
        <li data-step="4">Study and source metadata</li>
        <li data-step="5">Provenance and snapshot</li>
      </ol>
      <p class="ng-trace-note">The Evidence Explorer is a read-only public-alpha surface. Quality dimensions such as species, study design, origin, and human review describe context; sparse metadata is shown as <code>unknown</code>.</p>
    </div>
  </div>
</section>

<section class="ng-audience-section" aria-labelledby="ng-researcher-title">
  <div class="ng-shell">
    <p class="ng-kicker">Real paths, not dead-end cards</p>
    <div class="ng-audience-grid">
      <article class="ng-audience ng-audience--research">
        <span class="ng-kicker">Researcher path</span>
        <h2 id="ng-researcher-title">From disease question to inspectable evidence.</h2>
        <ul>
          <li>Explore a disease and its connected entities</li>
          <li>Inspect claims and evidence directions</li>
          <li>Trace provenance to source snapshots</li>
          <li>Compare relationships with explicit missingness</li>
        </ul>
        <a class="ng-button ng-button--text" href="research/sle/">See a research example →</a>
      </article>
      <article class="ng-audience ng-audience--developer">
        <span class="ng-kicker">Developer path</span>
        <h2>From architecture to contribution.</h2>
        <ul>
          <li>Understand the disease and biomedical store model</li>
          <li>Run the CLI, API, dashboard, and tests locally</li>
          <li>Extend a source adapter or disease module</li>
          <li>Validate the change and open a contribution</li>
        </ul>
        <a class="ng-button ng-button--text" href="contributing/">Read the contribution path →</a>
      </article>
    </div>
  </div>
</section>

<section class="ng-maturity" aria-labelledby="ng-maturity-title">
  <div class="ng-shell">
    <div class="ng-status-line"><span class="ng-status-badge">PUBLIC_ALPHA</span><span>Research software under active development. Snapshot: v0.2.1 · 2026-08-22.</span></div>
    <h2 id="ng-maturity-title">What exists today—and what does not.</h2>
    <p class="ng-lede">Maturity labels are part of the product. They tell you how to interpret a surface before you use it.</p>
    <div class="ng-maturity-table-wrap">
      <table class="ng-maturity-table">
        <thead><tr><th scope="col">Capability</th><th scope="col">Current state</th><th scope="col">What that means</th></tr></thead>
        <tbody>
          <tr><td>Unified <code>nosograph</code> CLI</td><td>Stable</td><td>Task-oriented commands for exploration, validation, sources, analysis, and serving.</td></tr>
          <tr><td>FastAPI API + dashboard</td><td>Beta</td><td>Working local research interface with async jobs and documented API surfaces.</td></tr>
          <tr><td>Evidence Explorer</td><td>Public alpha · included in v0.1.0</td><td>Read-only claim → evidence → provenance → source workflow.</td></tr>
          <tr><td>Evidence Workspace</td><td>Beta</td><td>Multi-source evidence assembled into claims and ranked hypotheses.</td></tr>
          <tr><td>NosoGraph Compare</td><td>Beta · released in v0.2.0</td><td>2–5-condition comparison with explicit missingness, claim drill-down, and deterministic exports.</td></tr>
          <tr><td>Public hosted demo</td><td>Planned</td><td>Not deployed; local Docker evaluation is the current route.</td></tr>
          <tr><td>Optional LLM enrichment</td><td>Experimental</td><td>Not required for core deterministic extraction and evidence workflows.</td></tr>
          <tr><td>FHIR / OMOP / Phenopackets</td><td>Not implemented</td><td>Future interoperability work, not current capability.</td></tr>
        </tbody>
      </table>
    </div>
    <div class="ng-snapshot" aria-label="Repository snapshot metrics">
      <div class="ng-stat"><strong>10,407</strong><span>registry modules</span></div>
      <div class="ng-stat"><strong>88</strong><span>strict L2-validated</span></div>
      <div class="ng-stat"><strong>6</strong><span>reference modules</span></div>
      <div class="ng-stat"><strong>8</strong><span>CI-validated modules</span></div>
      <div class="ng-stat"><strong>40+</strong><span>analysis pipelines</span></div>
      <div class="ng-stat"><strong>2,445</strong><span>offline tests selected in v0.2.1 suite</span></div>
    </div>
    <p class="ng-footnote">Snapshot source: <a href="generated/public-status.yaml">public-status.yaml</a>. Registry breadth is not curation depth; most registry modules are scaffolds.</p>
  </div>
</section>

<section class="ng-credibility" aria-labelledby="ng-credibility-title">
  <div class="ng-shell">
    <p class="ng-kicker">Scientific and technical practice</p>
    <h2 id="ng-credibility-title">Trust comes from inspectability.</h2>
    <div class="ng-credibility-grid">
      <article class="ng-credibility-item"><h3>Source transparency</h3><p>Upstream resources, integration state, and data terms are documented in a source matrix.</p></article>
      <article class="ng-credibility-item"><h3>Provenance</h3><p>Source snapshots, import paths, filters, fingerprints, and retrieval context can travel with an output.</p></article>
      <article class="ng-credibility-item"><h3>Conservative quality</h3><p>Species, study design, origin, and human review are contextual dimensions; missing values stay unknown.</p></article>
      <article class="ng-credibility-item"><h3>Reproducibility</h3><p>CLI validation, fixture-backed workflows, tests, and explicit maturity make limits visible.</p></article>
    </div>
  </div>
</section>

<section class="ng-docs" aria-labelledby="ng-docs-title">
  <div class="ng-shell">
    <p class="ng-kicker">Go deeper</p>
    <h2 id="ng-docs-title">Documentation organized around how you work.</h2>
    <div class="ng-doc-grid">
      <a class="ng-doc-link" href="getting-started/what-is/"><h3>Get started</h3><p>Understand the model, install locally, and run a first workflow.</p></a>
      <a class="ng-doc-link" href="concepts/evidence/"><h3>Learn the concepts</h3><p>Evidence, claims, provenance, knowledge graphs, and curation tiers.</p></a>
      <a class="ng-doc-link" href="using/cli/"><h3>Use NosoGraph</h3><p>Web interface, Evidence Explorer, CLI, API, validation, and source sync.</p></a>
      <a class="ng-doc-link" href="data/sources/"><h3>Inspect the data</h3><p>Sources, coverage, licensing, provenance, and update cadence.</p></a>
      <a class="ng-doc-link" href="developers/architecture/"><h3>Build with it</h3><p>Architecture, data model, local development, testing, and deployment.</p></a>
      <a class="ng-doc-link" href="project/roadmap/"><h3>See what is next</h3><p>Read the public roadmap and current release record without inflated promises.</p></a>
    </div>
  </div>
</section>

<section class="ng-open-source ng-dark" aria-labelledby="ng-open-source-title">
  <div class="ng-shell">
    <p class="ng-eyebrow ng-eyebrow--light">Open implementation · open questions</p>
    <h2 id="ng-open-source-title">Read the code. Improve the model.</h2>
    <p class="ng-lede">Add a source, deepen a disease module, improve the evidence workflow, or ask a research question. NosoGraph is built in public and labeled honestly.</p>
    <div class="ng-hero-actions"><a class="ng-button ng-button--primary" href="https://github.com/AdamEddahmouni/nosograph">View on GitHub</a><a class="ng-button ng-button--secondary" href="contributing/">Contribute</a><a class="ng-button ng-button--secondary" href="https://github.com/AdamEddahmouni/nosograph/discussions">Join Discussions</a></div>
  </div>
</section>

<footer class="ng-footer">
  <div class="ng-shell ng-footer-inner"><span>NosoGraph · Disease Intelligence. Connected.</span><span><a href="project/security/">Research-use boundary</a> · <a href="project/license/">Apache-2.0</a> · <a href="project/citation/">Citation</a> · <a href="https://github.com/AdamEddahmouni/nosograph">GitHub</a></span></div>
</footer>

</div>
