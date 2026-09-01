---
title: NosoGraph — Disease Intelligence. Connected.
description: Open-source research software for connecting disease knowledge, evidence, and provenance across biomedical sources.
---

<div class="ng-homepage">

<section class="ng-hero ng-dark" aria-labelledby="ng-hero-title">
  <div class="ng-shell ng-hero-grid">
    <div class="ng-hero-copy">
      <p class="ng-eyebrow ng-eyebrow--light">Open-source biomedical research software</p>
      <h1 id="ng-hero-title" class="ng-hero-title">Trace disease evidence from claim to&nbsp;source.</h1>
      <p class="ng-lede ng-hero-lede">NosoGraph connects disease knowledge from MONDO, HPO, literature, and clinical trials into typed claims — and keeps every claim's evidence direction and source provenance open to inspection.</p>
      <div class="ng-hero-actions" aria-label="Primary actions">
        <a class="ng-btn ng-btn--primary" href="using/evidence-explorer/">Explore Evidence Explorer</a>
        <a class="ng-btn ng-btn--secondary ng-btn--on-dark" href="getting-started/install/">Run NosoGraph locally</a>
        <a class="ng-btn ng-btn--text" href="https://github.com/AdamEddahmouni/nosograph">View source →</a>
      </div>
      <p class="ng-hero-availability">Runs locally · no hosted demo yet</p>
    </div>
    <figure class="ng-hero-trace" data-ng-evidence-trace aria-labelledby="ng-hero-trace-title">
      <div class="ng-hero-trace-head">
        <span id="ng-hero-trace-title" class="ng-hero-trace-label">Evidence trace</span>
        <span class="ng-hero-trace-chip">Illustrative structure</span>
      </div>
      <div class="ng-hero-trace-stage" data-ng-trace-stage>
        <ol class="ng-hero-trace-path" aria-label="Trace path stages">
          <li>
            <button type="button" class="ng-trace-stage is-selected" data-ng-trace-step="disease" aria-controls="ng-trace-inspector" aria-pressed="true">
              <span class="ng-trace-index">01</span><span class="ng-hero-trace-name">Disease</span><span class="ng-hero-trace-detail">MONDO:0007915</span>
            </button>
          </li>
          <li>
            <button type="button" class="ng-trace-stage" data-ng-trace-step="claim" aria-controls="ng-trace-inspector" aria-pressed="false">
              <span class="ng-trace-index">02</span><span class="ng-hero-trace-name">Typed claim</span><span class="ng-hero-trace-detail">associated_with</span>
            </button>
          </li>
          <li>
            <button type="button" class="ng-trace-stage" data-ng-trace-step="evidence" aria-controls="ng-trace-inspector" aria-pressed="false">
              <span class="ng-trace-index">03</span><span class="ng-hero-trace-name">Evidence</span><span class="ng-hero-trace-detail"><span class="ng-ev ng-ev--supports">SUPPORTS</span></span>
            </button>
          </li>
          <li>
            <button type="button" class="ng-trace-stage" data-ng-trace-step="source" aria-controls="ng-trace-inspector" aria-pressed="false">
              <span class="ng-trace-index">04</span><span class="ng-hero-trace-name">Study / source</span><span class="ng-hero-trace-detail">NOT_RECORDED</span>
            </button>
          </li>
          <li>
            <button type="button" class="ng-trace-stage" data-ng-trace-step="provenance" aria-controls="ng-trace-inspector" aria-pressed="false">
              <span class="ng-trace-index">05</span><span class="ng-hero-trace-name">Provenance</span><span class="ng-hero-trace-detail">snapshot context</span>
            </button>
          </li>
        </ol>
        <div id="ng-trace-inspector" class="ng-trace-inspector" tabindex="-1" aria-live="polite" aria-label="Selected trace stage">
          <span class="ng-trace-inspector-label">Disease context</span>
          <strong class="ng-trace-inspector-value">systemic lupus erythematosus</strong>
          <span class="ng-trace-inspector-meta">MONDO:0007915 · reference disease module</span>
        </div>
      </div>
      <p class="ng-hero-trace-meta" aria-label="Trace status"><span>Repository-backed vocabulary</span><span>Unknown stays unknown</span></p>
      <figcaption>Follow a typed claim through evidence, source context, and preserved provenance.</figcaption>
    </figure>
  </div>
  <div class="ng-shell ng-hero-rail">
    <span>Research software — <a href="project/security/">not medical advice</a></span>
    <a href="project/status/">Status: public alpha</a>
  </div>
</section>

<section class="ng-audience-routes" aria-labelledby="ng-audience-title">
  <div class="ng-shell">
    <div class="ng-audience-heading">
      <p class="ng-kicker">Choose your path</p>
      <h2 id="ng-audience-title">Inspect the evidence or extend the system.</h2>
    </div>
    <nav class="ng-audience-grid" aria-label="Audience routes">
      <a href="#researchers">
        <span>For researchers</span>
        <strong>Follow claims to evidence and source context.</strong>
        <small>Explore diseases, compare conditions, and inspect provenance →</small>
      </a>
      <a href="#developers">
        <span>For developers and contributors</span>
        <strong>Run locally, inspect the model, and add to it.</strong>
        <small>Use the CLI and API, extend sources, validate, and contribute →</small>
      </a>
    </nav>
  </div>
</section>

<section class="ng-credibility-rail" aria-labelledby="ng-credibility-title">
  <div class="ng-shell">
    <div class="ng-credibility-heading">
      <p class="ng-kicker">Project record</p>
      <h2 id="ng-credibility-title">Built to be inspected.</h2>
      <a href="project/status/">Current status →</a>
    </div>
    <dl class="ng-credibility-stats">
      <div><dt>L2-validated modules</dt><dd>{{NG_L2_STRICT_VALIDATED}}</dd></div>
      <div><dt>Selected offline tests</dt><dd>{{NG_OFFLINE_TESTS}}</dd></div>
      <div><dt>Research boundary</dt><dd>Research only</dd></div>
      <div><dt>License</dt><dd>Apache-2.0</dd></div>
      <div><dt>Concept DOI</dt><dd><a href="project/citation/">10.5281/zenodo.22055279</a></dd></div>
    </dl>
  </div>
</section>

<section class="ng-problem ng-context-section" aria-labelledby="ng-problem-title">
  <div class="ng-shell ng-problem-grid">
    <div>
      <p class="ng-kicker">Why this is hard</p>
      <h2 id="ng-problem-title">A claim rarely arrives with all of its context in one place.</h2>
      <p class="ng-lede">Biomedical resources are built for different questions. The work is not to replace them, but to reconcile identifiers, relationships, evidence direction, and provenance without flattening their differences.</p>
    </div>
    <ul class="ng-problem-list">
      <li><strong>Distributed knowledge</strong> Ontologies, literature, trials, genetics, and target resources each expose a partial view.</li>
      <li><strong>Hard-to-trace claims</strong> A relationship is easier to review when its evidence and source context travel with it.</li>
      <li><strong>Uneven metadata</strong> Species, study design, origin, and other fields may be unknown—not negative.</li>
      <li><strong>Context matters</strong> Association, evidence direction, and provenance are separate dimensions of interpretation.</li>
    </ul>
  </div>
</section>

<section class="ng-transformation ng-context-section" aria-labelledby="ng-transformation-title">
  <div class="ng-shell">
    <div class="ng-transformation-intro">
      <p class="ng-kicker">The NosoGraph layer</p>
      <h2 id="ng-transformation-title">Turn fragmented sources into inspectable relationships.</h2>
      <p class="ng-lede">NosoGraph adds a computational layer across upstream resources—not a replacement for them. Each step keeps the distinction between source data, typed relationships, evidence, and provenance visible.</p>
    </div>
    <ol class="ng-pipeline" aria-label="NosoGraph evidence pipeline">
      <li class="ng-pipeline-step"><span class="ng-pipeline-index">01</span><strong>Source sync</strong><span>Acquire a resource record and retain its snapshot context.</span></li>
      <li class="ng-pipeline-step"><span class="ng-pipeline-index">02</span><strong>Normalize</strong><span>Resolve identifiers while retaining source vocabulary.</span></li>
      <li class="ng-pipeline-step"><span class="ng-pipeline-index">03</span><strong>Typed claims</strong><span>Represent explicit subject–predicate–object relationships.</span></li>
      <li class="ng-pipeline-step"><span class="ng-pipeline-index">04</span><strong>Evidence</strong><span>Keep SUPPORTS, CONTRADICTS, and INCONCLUSIVE distinct.</span></li>
      <li class="ng-pipeline-step"><span class="ng-pipeline-index">05</span><strong>Provenance</strong><span>Carry source, snapshot, import, and fingerprint context forward.</span></li>
    </ol>
  </div>
</section>

<section class="ng-sources ng-context-section" aria-labelledby="ng-sources-title">
  <div class="ng-shell">
    <div class="ng-sources-heading">
      <div><p class="ng-kicker">Source ecosystem</p><h2 id="ng-sources-title">Source context stays visible.</h2></div>
      <p class="ng-sources-count"><strong>Source matrix</strong><br><span>Representative resources shown below.</span></p>
    </div>
    <div class="ng-source-table-wrap">
      <table class="ng-source-table">
        <caption class="ng-visually-hidden">Representative NosoGraph source integrations and their integration maturity</caption>
        <thead><tr><th scope="col">Source</th><th scope="col">Role in NosoGraph</th><th scope="col">Integration maturity</th></tr></thead>
        <tbody>
          <tr><th scope="row"><a href="data/sources/">MONDO</a></th><td>Disease ontology and identifiers</td><td><span class="ng-chip ng-chip--stable">STABLE</span></td></tr>
          <tr><th scope="row"><a href="data/sources/">HPO / HPOA</a></th><td>Phenotypes and annotations</td><td><span class="ng-chip ng-chip--stable">STABLE</span></td></tr>
          <tr><th scope="row"><a href="data/sources/">PubMed</a></th><td>Literature and evidence workspace</td><td><span class="ng-chip ng-chip--stable">STABLE</span></td></tr>
          <tr><th scope="row"><a href="data/sources/">ClinicalTrials.gov</a></th><td>Clinical study records</td><td><span class="ng-chip ng-chip--stable">STABLE</span></td></tr>
          <tr><th scope="row"><a href="data/sources/">Open Targets</a></th><td>Target–disease data and connector</td><td><span class="ng-chip ng-chip--beta">BETA</span></td></tr>
          <tr><th scope="row"><a href="data/sources/">GWAS Catalog</a></th><td>Genetic associations</td><td><span class="ng-chip ng-chip--beta">BETA</span></td></tr>
          <tr><th scope="row"><a href="data/sources/">bioRxiv / medRxiv</a></th><td>Preprint evidence workspace</td><td><span class="ng-chip ng-chip--experimental">EXPERIMENTAL</span></td></tr>
        </tbody>
      </table>
    </div>
    <p class="ng-source-note">Integration maturity describes NosoGraph's implementation state, not the scientific quality or clinical validity of an upstream resource. <a href="data/sources/">View the complete source matrix →</a></p>
  </div>
</section>

<section class="ng-product-proof ng-dark" id="product" aria-labelledby="ng-product-title">
  <div class="ng-shell">
    <div class="ng-product-intro">
      <p class="ng-eyebrow ng-eyebrow--light">From model to working software</p>
      <h2 id="ng-product-title">Inspect the structure directly.</h2>
      <p class="ng-lede">The evidence model is not only a diagram. NosoGraph exposes local research interfaces for exploring conditions, claims, evidence, and provenance.</p>
    </div>
    <figure class="ng-product-figure ng-product-figure--primary">
      <div class="ng-product-media"><img src="assets/product/evidence-explorer.webp" width="1440" height="900" loading="lazy" decoding="async" alt="NosoGraph dashboard showing condition and evidence exploration panels." /></div>
      <figcaption><strong>Evidence Explorer</strong> — a local dashboard surface for inspecting condition context, claims, evidence direction, and source-linked research data. <span class="ng-product-meta">LOCAL RUN · PUBLIC ALPHA</span></figcaption>
    </figure>
    <div class="ng-product-secondary">
      <figure class="ng-product-figure">
        <div class="ng-product-media"><img src="assets/product/evidence-workspace.webp" width="1440" height="900" loading="lazy" decoding="async" alt="NosoGraph local dashboard showing a disease exploration interface." /></div>
        <figcaption><strong>Evidence Workspace</strong> — the documented async workspace turns selected evidence sources into a provenance-backed dossier. <a href="evidence-workspace/">Run it locally →</a><span class="ng-product-meta">DOCUMENTED SURFACE · BETA</span></figcaption>
      </figure>
      <figure class="ng-product-figure">
        <div class="ng-product-media"><img src="assets/product/compare.svg" width="900" height="520" loading="lazy" decoding="async" alt="Conceptual diagram representing NosoGraph Compare condition comparison." /></div>
        <figcaption><strong>NosoGraph Compare</strong> — the implemented workflow compares two to five conditions with explicit missingness and deterministic structured output. <a href="using/compare/">Read the workflow →</a><span class="ng-product-meta">DOCUMENTED SURFACE · BETA · CONCEPTUAL ARTWORK</span></figcaption>
      </figure>
    </div>
    <p class="ng-product-note">These are local research interfaces, not a hosted demo. Captures and concepts are presented with their actual status; no screenshot is a clinical result or proof of causation.</p>
  </div>
</section>

<section class="ng-philosophy ng-context-section" aria-labelledby="ng-philosophy-title">
  <div class="ng-shell ng-philosophy-grid">
    <div class="ng-philosophy-intro">
      <p class="ng-kicker">Evidence-first by design</p>
      <h2 id="ng-philosophy-title">Evidence is direction, context, and provenance—not a single score.</h2>
      <p class="ng-lede">NosoGraph structures evidence for inspection. It does not automatically turn a claim into scientific proof or a clinical conclusion.</p>
      <p class="ng-philosophy-boundary"><strong>ASSOCIATED_WITH</strong> is a relationship type. It is not automatically <strong>CAUSES</strong>.</p>
    </div>
    <div class="ng-evidence-specimen" aria-labelledby="ng-evidence-specimen-title">
      <div class="ng-specimen-head"><span id="ng-evidence-specimen-title">Evidence semantics</span><span>Structural example</span></div>
      <div class="ng-specimen-claim"><span class="ng-specimen-label">Typed claim</span><strong>subject <span>→</span> predicate <span>→</span> object</strong><code>associated_with</code></div>
      <dl class="ng-evidence-semantics">
        <div><dt><span class="ng-ev ng-ev--supports">SUPPORTS</span></dt><dd>Evidence supports the claim; it is not a proven fact.</dd></div>
        <div><dt><span class="ng-ev ng-ev--contradicts">CONTRADICTS</span></dt><dd>Evidence disagrees with the claim; it is not automatic falsification.</dd></div>
        <div><dt><span class="ng-ev ng-ev--inconclusive">INCONCLUSIVE</span></dt><dd>Evidence does not establish a clear direction.</dd></div>
        <div><dt><span class="ng-ev ng-ev--unasserted">UNASSERTED</span></dt><dd>No directional evidence is recorded.</dd></div>
      </dl>
      <div class="ng-specimen-footer"><span>Missing field</span><code>NOT_RECORDED</code><span>Provenance stays attached where available.</span></div>
    </div>
  </div>
</section>

<section class="ng-research-workflow ng-context-section" id="researchers" aria-labelledby="ng-research-workflow-title">
  <div class="ng-shell">
    <div class="ng-workflow-heading">
      <div><p class="ng-kicker">Researcher workflow</p><h2 id="ng-research-workflow-title">Start with a question. Follow the evidence.</h2></div>
      <p class="ng-lede">A practical path from disease context to the next inspectable research surface.</p>
    </div>
    <ol class="ng-research-flow">
      <li><span class="ng-flow-index">01</span><div><strong>Choose context</strong><p>Start with a disease module or research question, then check its curation and coverage context.</p><a href="research/sle/">SLE walkthrough →</a></div></li>
      <li><span class="ng-flow-index">02</span><div><strong>Inspect claims</strong><p>Open the condition view and identify the exact relationship type instead of reading an unlabeled edge.</p><a href="using/evidence-explorer/">Evidence Explorer guide →</a></div></li>
      <li><span class="ng-flow-index">03</span><div><strong>Review direction</strong><p>Read SUPPORTS, CONTRADICTS, INCONCLUSIVE, or UNASSERTED as categorical evidence semantics.</p><a href="concepts/evidence/">Evidence concepts →</a></div></li>
      <li><span class="ng-flow-index">04</span><div><strong>Trace context</strong><p>Follow study/source metadata and the provenance chain; keep unavailable fields explicitly unknown.</p><a href="research/evidence-tracing/">Evidence tracing →</a></div></li>
      <li><span class="ng-flow-index">05</span><div><strong>Compare if useful</strong><p>Compare two to five conditions with explicit missingness when a cross-condition question is appropriate.</p><a href="using/compare/">Compare workflow →</a></div></li>
    </ol>
    <p class="ng-research-boundary">Research software for investigation—not medical advice or clinical decision support. <a href="project/security/">Research-use boundary →</a></p>
  </div>
</section>

<section class="ng-research-exits ng-context-section" aria-labelledby="ng-research-exits-title">
  <div class="ng-shell">
    <div class="ng-exits-heading"><p class="ng-kicker">Continue the research</p><h2 id="ng-research-exits-title">Choose the next question, not an automatic answer.</h2></div>
    <nav aria-label="Research workflows"><ul class="ng-exit-list">
      <li><a href="research/evidence-tracing/"><strong>Evidence tracing</strong><span>Follow a claim to source provenance →</span></a></li>
      <li><a href="research/comparison/"><strong>Cross-disease comparison</strong><span>Inspect structured differences across conditions →</span></a></li>
      <li><a href="research/repurposing/"><strong>Drug repurposing research</strong><span>Surface evidence context for further investigation →</span></a></li>
      <li><a href="research/ra/"><strong>Rheumatoid arthritis</strong><span>Use a second CI-validated disease context →</span></a></li>
    </ul></nav>
  </div>
</section>

<section class="ng-developer ng-context-section" id="developers" aria-labelledby="ng-developer-title">
  <div class="ng-shell ng-developer-grid">
    <div class="ng-developer-copy">
      <p class="ng-kicker">Developer path</p>
      <h2 id="ng-developer-title">Run it locally. Inspect the model. Extend the system.</h2>
      <p class="ng-lede">NosoGraph is source-install software: use the CLI, local FastAPI surface, structured disease modules, and documented interfaces to inspect or extend research workflows.</p>
      <nav class="ng-inline-links" aria-label="Developer resources">
        <a href="getting-started/install/">Installation guide →</a>
        <a href="api-reference/">API reference →</a>
        <a href="architecture/overview/">Architecture →</a>
      </nav>
    </div>
    <div class="ng-quickstart">
      <div class="ng-code-head"><span>Run locally</span><span>source install</span></div>
      <pre><code>git clone https://github.com/AdamEddahmouni/nosograph.git
cd nosograph
cp .env.example .env
docker compose --profile full up --build</code></pre>
      <p>Then open the local dashboard at <code>http://localhost:8000</code>.</p>
    </div>
  </div>
  <div class="ng-shell ng-developer-surface">
    <div class="ng-capability-list" aria-label="Developer capabilities">
      <div><strong>CLI</strong><span>Validate disease modules and run task-oriented analysis commands.</span><a href="using/cli/">CLI guide →</a></div>
      <div><strong>API</strong><span>Query structured disease, evidence, provenance, and comparison surfaces.</span><a href="api-reference/">API reference →</a></div>
      <div><strong>Validation</strong><span>Run the local project gate before contributing.</span><code>make ci-local</code></div>
      <div><strong>Sources</strong><span>Extend source integrations with licensing, provenance, maturity, and tests.</span><a href="contributing/sources/">Source contributions →</a></div>
    </div>
    <div class="ng-architecture-map" aria-label="Software architecture">
      <div><span>DATA</span><strong>Disease modules</strong><small>structured domain objects</small></div>
      <div><span>MODEL</span><strong>Claims · evidence</strong><small>typed relationships + context</small></div>
      <div><span>INTERFACES</span><strong>CLI · API · web</strong><small>inspect, validate, compare</small></div>
      <div><span>EXTEND</span><strong>Modules · adapters · tests</strong><small>documented contribution surfaces</small></div>
    </div>
  </div>
</section>

<section class="ng-contribution ng-context-section" id="contribute" aria-labelledby="ng-contribution-title">
  <div class="ng-shell">
    <div class="ng-contribution-heading"><p class="ng-kicker">Open source</p><h2 id="ng-contribution-title">Contribute to the parts you can inspect.</h2><p class="ng-lede">The project accepts focused improvements to code, curation, source context, documentation, and validation.</p></div>
    <div class="ng-contribution-list">
      <div><strong>Build</strong><span>Improve software and interfaces without weakening the tests.</span><a href="contributing/code/">Code contribution guide →</a></div>
      <div><strong>Curate</strong><span>Improve disease modules with sourced evidence, provenance, and licensing discipline.</span><a href="contributing/curation/">Disease curation guide →</a></div>
      <div><strong>Integrate</strong><span>Add or maintain source entries with terms, maturity, and connector tests.</span><a href="contributing/sources/">Source contribution guide →</a></div>
      <div><strong>Document</strong><span>Strengthen research examples and accessible project documentation.</span><a href="contributing/">Contributing overview →</a></div>
    </div>
    <p class="ng-contribution-note"><a href="project/good-first-issues/">Good first issues →</a> are listed with their intended area; governance and decision-making are documented publicly.</p>
  </div>
</section>

<section class="ng-legacy-open-source ng-dark" aria-labelledby="ng-open-source-title">
  <div class="ng-shell ng-open-source-grid">
    <div><p class="ng-eyebrow ng-eyebrow--light">Inspectable evidence · inspectable software</p><h2 id="ng-open-source-title">The research model is open to review.</h2></div>
    <div><p class="ng-lede">Read the source, check the current status, cite the project, or review its security and roadmap records. Apache-2.0 covers the source code; upstream data terms remain source-specific.</p><nav class="ng-open-links" aria-label="Project resources"><a href="https://github.com/AdamEddahmouni/nosograph">View source →</a><a href="project/status/">Status →</a><a href="project/roadmap/">Roadmap →</a><a href="project/citation/">Concept DOI / citation →</a><a href="project/security/">Security policy →</a><a href="project/license/">Apache-2.0 license →</a></nav></div>
  </div>
</section>

<footer class="ng-footer" aria-label="Site footer">
  <div class="ng-shell ng-footer-grid">
    <div class="ng-footer-brand"><strong>NosoGraph</strong><span>Disease intelligence, connected.</span><small>Research software · not medical advice</small></div>
    <nav aria-labelledby="ng-footer-product"><h2 id="ng-footer-product">Product</h2><a href="using/evidence-explorer/">Evidence Explorer</a><a href="evidence-workspace/">Evidence Workspace</a><a href="using/compare/">Compare</a><a href="project/status/">Status</a></nav>
    <nav aria-labelledby="ng-footer-start"><h2 id="ng-footer-start">Start</h2><a href="getting-started/what-is/">What is NosoGraph?</a><a href="getting-started/install/">Installation</a><a href="getting-started/tutorial/">Five-minute tutorial</a><a href="research/sle/">Research examples</a></nav>
    <nav aria-labelledby="ng-footer-understand"><h2 id="ng-footer-understand">Understand</h2><a href="concepts/claims/">Claims</a><a href="concepts/evidence/">Evidence</a><a href="concepts/provenance/">Provenance</a><a href="data/sources/">Sources</a></nav>
    <nav aria-labelledby="ng-footer-project"><h2 id="ng-footer-project">Project</h2><a href="https://github.com/AdamEddahmouni/nosograph">GitHub</a><a href="contributing/">Contributing</a><a href="project/roadmap/">Roadmap</a><a href="project/citation/">Citation</a><a href="project/security/">Security</a><a href="project/license/">License</a></nav>
  </div>
  <div class="ng-shell ng-footer-baseline"><span>Apache-2.0 source · upstream data terms vary by source · v{{NG_VERSION}}</span><span>Concept DOI <a href="project/citation/">10.5281/zenodo.22055279</a></span></div>
</footer>

</div>
