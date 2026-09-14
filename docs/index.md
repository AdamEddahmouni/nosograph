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
        <a class="ng-btn ng-btn--primary" href="getting-started/what-is/">Start with the docs</a>
        <a class="ng-btn ng-btn--secondary ng-btn--on-dark" href="getting-started/install/">Run NosoGraph locally</a>
        <a class="ng-btn ng-btn--text" href="https://github.com/AdamEddahmouni/nosograph">View source →</a>
      </div>
      <p class="ng-hero-availability">This site is the documentation · the software runs locally · no hosted demo</p>
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
    <a href="project/status/">Status: public alpha · v{{NG_VERSION}}</a>
  </div>
</section>

<section class="ng-metrics" aria-labelledby="ng-metrics-title">
  <div class="ng-shell">
    <div class="ng-metrics-heading">
      <div>
        <p class="ng-eyebrow">Current scope</p>
        <h2 id="ng-metrics-title">A broad registry, honestly labeled.</h2>
      </div>
      <a class="ng-metrics-more" href="project/status/">Full project status →</a>
    </div>
    <dl class="ng-metrics-grid">
      <div class="ng-metric"><dt>Discoverable disease modules</dt><dd>{{NG_REGISTRY_MODULES}}</dd><span class="ng-metric-kind">full-corpus</span></div>
      <div class="ng-metric"><dt>CI-validated modules</dt><dd>{{NG_CI_VALIDATED}}</dd><span class="ng-metric-kind">full-corpus gate</span></div>
      <div class="ng-metric"><dt>Reference modules</dt><dd>{{NG_REFERENCE_TIER}}</dd><span class="ng-metric-kind">full-corpus</span></div>
      <div class="ng-metric"><dt>Strict L2-validated</dt><dd>{{NG_L2_STRICT_VALIDATED}}</dd><span class="ng-metric-kind">n=500 sample</span></div>
      <div class="ng-metric"><dt>Registered pipeline adapters</dt><dd>{{NG_ADAPTERS}}</dd><span class="ng-metric-kind">full-corpus</span></div>
      <div class="ng-metric"><dt>Offline tests</dt><dd>{{NG_OFFLINE_TESTS}}</dd><span class="ng-metric-kind">v{{NG_VERSION}} snapshot</span></div>
    </dl>
    <p class="ng-metrics-note">Registry breadth is not curation depth. Validation figures marked <em>sample</em> describe an n=500 alphabetical slice of the registry, not the full corpus. <a href="concepts/registry/">How the registry counts work →</a></p>
  </div>
</section>

<section class="ng-boundary" aria-labelledby="ng-boundary-title">
  <div class="ng-shell">
    <div class="ng-boundary-heading">
      <p class="ng-eyebrow">Positioning</p>
      <h2 id="ng-boundary-title">Research software, with the boundary on the page.</h2>
    </div>
    <div class="ng-boundary-grid">
      <div class="ng-boundary-col ng-boundary-col--is">
        <h3>NosoGraph is</h3>
        <ul>
          <li>Open-source (Apache-2.0) software for biomedical research workflows.</li>
          <li>A typed-claims layer across ontologies, literature, trials, genetics, and target resources.</li>
          <li>Local software you run and inspect — a CLI, an API, and a dashboard.</li>
          <li>Provenance-preserving: source, snapshot, and import context travel with each claim.</li>
        </ul>
      </div>
      <div class="ng-boundary-col ng-boundary-col--not">
        <h3>NosoGraph is not</h3>
        <ul>
          <li>Not medical advice, diagnosis, or clinical decision support.</li>
          <li>Not a hosted service — this site is documentation; the app runs on your machine.</li>
          <li>Not a replacement for the upstream sources it reconciles.</li>
          <li>Not a truth engine — computational rankings are hypotheses for review, never clinical certainty.</li>
        </ul>
      </div>
    </div>
  </div>
</section>

<section class="ng-audience-routes" aria-labelledby="ng-audience-title">
  <div class="ng-shell">
    <div class="ng-audience-heading">
      <p class="ng-eyebrow">Choose your path</p>
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

<section class="ng-capabilities" aria-labelledby="ng-capabilities-title">
  <div class="ng-shell">
    <div class="ng-section-heading">
      <p class="ng-eyebrow">Major capabilities</p>
      <h2 id="ng-capabilities-title">What you can inspect today.</h2>
      <p class="ng-lede">Each surface is documented with its actual maturity. Nothing here is a clinical result.</p>
    </div>
    <div class="ng-cap-grid">
      <a class="ng-cap-card" href="using/evidence-explorer/">
        <span class="ng-chip ng-chip--alpha">Public alpha</span>
        <h3>Evidence Explorer</h3>
        <p>Inspect condition context, typed claims, and evidence direction in the local dashboard.</p>
        <span class="ng-cap-link">Read the guide →</span>
      </a>
      <a class="ng-cap-card" href="evidence-workspace/">
        <span class="ng-chip ng-chip--beta">Beta</span>
        <h3>Evidence Workspace</h3>
        <p>Turn selected evidence sources into a provenance-backed dossier, asynchronously.</p>
        <span class="ng-cap-link">Run it locally →</span>
      </a>
      <a class="ng-cap-card" href="using/compare/">
        <span class="ng-chip ng-chip--beta">Beta</span>
        <h3>Compare conditions</h3>
        <p>Two to five conditions, explicit missingness, deterministic structured output.</p>
        <span class="ng-cap-link">Read the workflow →</span>
      </a>
      <a class="ng-cap-card" href="concepts/registry/">
        <span class="ng-chip ng-chip--stable">Stable</span>
        <h3>Disease registry</h3>
        <p>{{NG_REGISTRY_MODULES}} discoverable modules — breadth labeled separately from curation depth.</p>
        <span class="ng-cap-link">Understand the registry →</span>
      </a>
      <a class="ng-cap-card" href="using/cli/">
        <span class="ng-chip ng-chip--stable">Stable</span>
        <h3>CLI</h3>
        <p>Validate disease modules, sync sources, and run task-oriented analysis commands.</p>
        <span class="ng-cap-link">CLI guide →</span>
      </a>
      <a class="ng-cap-card" href="api-reference/">
        <span class="ng-chip ng-chip--beta">Beta</span>
        <h3>API</h3>
        <p>Local FastAPI surface for diseases, evidence, provenance, and comparison.</p>
        <span class="ng-cap-link">API reference →</span>
      </a>
    </div>
  </div>
</section>

<section class="ng-model" aria-labelledby="ng-model-title">
  <div class="ng-shell">
    <div class="ng-section-heading">
      <p class="ng-eyebrow">The NosoGraph layer</p>
      <h2 id="ng-model-title">From fragmented sources to inspectable relationships.</h2>
      <p class="ng-lede">Biomedical resources are built for different questions. NosoGraph adds a computational layer across them — not a replacement — and keeps the distinction between source data, typed relationships, evidence, and provenance visible at every step.</p>
    </div>
    <ol class="ng-pipeline" aria-label="NosoGraph evidence pipeline">
      <li class="ng-pipeline-step"><span class="ng-pipeline-index">01</span><strong>Source sync</strong><span>Acquire a resource record and retain its snapshot context.</span></li>
      <li class="ng-pipeline-step"><span class="ng-pipeline-index">02</span><strong>Normalize</strong><span>Resolve identifiers while retaining source vocabulary.</span></li>
      <li class="ng-pipeline-step"><span class="ng-pipeline-index">03</span><strong>Typed claims</strong><span>Represent explicit subject–predicate–object relationships.</span></li>
      <li class="ng-pipeline-step"><span class="ng-pipeline-index">04</span><strong>Evidence</strong><span>Keep SUPPORTS, CONTRADICTS, and INCONCLUSIVE distinct.</span></li>
      <li class="ng-pipeline-step"><span class="ng-pipeline-index">05</span><strong>Provenance</strong><span>Carry source, snapshot, import, and fingerprint context forward.</span></li>
    </ol>
    <div class="ng-model-evidence">
      <div class="ng-model-evidence-intro">
        <h3>Evidence is direction, context, and provenance — not a single score.</h3>
        <p>NosoGraph structures evidence for inspection. It does not automatically turn a claim into scientific proof or a clinical conclusion.</p>
        <p class="ng-model-boundary"><strong>ASSOCIATED_WITH</strong> is a relationship type. It is not automatically <strong>CAUSES</strong>.</p>
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
  </div>
</section>

<section class="ng-sources" aria-labelledby="ng-sources-title">
  <div class="ng-shell">
    <div class="ng-sources-heading">
      <div>
        <p class="ng-eyebrow">Source ecosystem</p>
        <h2 id="ng-sources-title">Source context stays visible.</h2>
      </div>
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

<section class="ng-surfaces ng-dark" aria-labelledby="ng-surfaces-title">
  <div class="ng-shell ng-surfaces-grid">
    <div class="ng-surfaces-copy">
      <p class="ng-eyebrow ng-eyebrow--light">Two surfaces, one project</p>
      <h2 id="ng-surfaces-title">This site is the documentation. The dashboard is local software.</h2>
      <p class="ng-lede">GitHub Pages hosts only these docs. The NosoGraph dashboard, CLI, and API run on your machine — every capture shown here comes from a local run, and there is no hosted demo to log into.</p>
      <nav class="ng-inline-links" aria-label="Software surfaces">
        <a href="using/web/">Web interface guide →</a>
        <a href="getting-started/docker/">Run with Docker →</a>
        <a href="deployment/">Self-hosted deployment →</a>
      </nav>
    </div>
    <figure class="ng-surfaces-figure">
      <div class="ng-surfaces-media"><img src="assets/product/evidence-explorer.webp" width="1440" height="900" loading="lazy" decoding="async" alt="NosoGraph dashboard showing condition and evidence exploration panels." /></div>
      <figcaption><strong>Evidence Explorer</strong> — a local dashboard surface for inspecting condition context, claims, evidence direction, and source-linked research data. <span class="ng-figure-meta">LOCAL RUN · PUBLIC ALPHA</span></figcaption>
    </figure>
  </div>
</section>

<section class="ng-research-workflow" id="researchers" aria-labelledby="ng-research-workflow-title">
  <div class="ng-shell">
    <div class="ng-workflow-heading">
      <div>
        <p class="ng-eyebrow">Researcher workflow</p>
        <h2 id="ng-research-workflow-title">Start with a question. Follow the evidence.</h2>
      </div>
      <p class="ng-lede">A practical path from disease context to the next inspectable research surface.</p>
    </div>
    <ol class="ng-research-flow">
      <li><span class="ng-flow-index">01</span><div><strong>Choose context</strong><p>Start with a disease module or research question, then check its curation and coverage context.</p><a href="research/sle/">SLE walkthrough →</a></div></li>
      <li><span class="ng-flow-index">02</span><div><strong>Inspect claims</strong><p>Open the condition view and identify the exact relationship type instead of reading an unlabeled edge.</p><a href="using/evidence-explorer/">Evidence Explorer guide →</a></div></li>
      <li><span class="ng-flow-index">03</span><div><strong>Review direction</strong><p>Read SUPPORTS, CONTRADICTS, INCONCLUSIVE, or UNASSERTED as categorical evidence semantics.</p><a href="concepts/evidence/">Evidence concepts →</a></div></li>
      <li><span class="ng-flow-index">04</span><div><strong>Trace context</strong><p>Follow study/source metadata and the provenance chain; keep unavailable fields explicitly unknown.</p><a href="research/evidence-tracing/">Evidence tracing →</a></div></li>
      <li><span class="ng-flow-index">05</span><div><strong>Compare if useful</strong><p>Compare two to five conditions with explicit missingness when a cross-condition question is appropriate.</p><a href="using/compare/">Compare workflow →</a></div></li>
    </ol>
    <p class="ng-research-boundary">Research software for investigation — not medical advice or clinical decision support. <a href="project/security/">Research-use boundary →</a></p>
  </div>
</section>

<section class="ng-developer ng-dark" id="developers" aria-labelledby="ng-developer-title">
  <div class="ng-shell ng-developer-grid">
    <div class="ng-developer-copy">
      <p class="ng-eyebrow ng-eyebrow--light">Developer path</p>
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

<section class="ng-contribution" id="contribute" aria-labelledby="ng-contribution-title">
  <div class="ng-shell">
    <div class="ng-contribution-heading">
      <p class="ng-eyebrow">Open source</p>
      <h2 id="ng-contribution-title">Contribute to the parts you can inspect.</h2>
      <p class="ng-lede">The project accepts focused improvements to code, curation, source context, documentation, and validation.</p>
    </div>
    <div class="ng-contribution-list">
      <div><strong>Build</strong><span>Improve software and interfaces without weakening the tests.</span><a href="contributing/code/">Code contribution guide →</a></div>
      <div><strong>Curate</strong><span>Improve disease modules with sourced evidence, provenance, and licensing discipline.</span><a href="contributing/curation/">Disease curation guide →</a></div>
      <div><strong>Integrate</strong><span>Add or maintain source entries with terms, maturity, and connector tests.</span><a href="contributing/sources/">Source contribution guide →</a></div>
      <div><strong>Document</strong><span>Strengthen research examples and accessible project documentation.</span><a href="contributing/">Contributing overview →</a></div>
    </div>
    <p class="ng-contribution-note"><a href="project/good-first-issues/">Good first issues →</a> are listed with their intended area; governance and decision-making are documented publicly.</p>
  </div>
</section>

<section class="ng-closing ng-dark" aria-labelledby="ng-closing-title">
  <div class="ng-shell">
    <h2 id="ng-closing-title" class="ng-gradient-text">Disease Intelligence. Connected.</h2>
    <p class="ng-closing-sub">The research model is open to review — read the source, check the current status, or cite the project.</p>
    <nav class="ng-closing-links" aria-label="Project resources">
      <a href="https://github.com/AdamEddahmouni/nosograph">View source →</a>
      <a href="project/status/">Status →</a>
      <a href="project/roadmap/">Roadmap →</a>
      <a href="project/citation/">Concept DOI / citation →</a>
      <a href="project/security/">Security policy →</a>
      <a href="project/license/">Apache-2.0 license →</a>
    </nav>
    <p class="ng-closing-baseline">Apache-2.0 source · upstream data terms vary by source · v{{NG_VERSION}} · Concept DOI <a href="project/citation/">10.5281/zenodo.22055279</a></p>
  </div>
</section>

</div>
