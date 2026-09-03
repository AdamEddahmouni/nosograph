# NosoGraph Repository Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the NosoGraph repository and documentation presentation so researchers and contributors can evaluate the project quickly, follow equally visible paths, and trust that all public claims are current and conservative.

**Architecture:** Keep the existing NosoGraph brand system and MkDocs runtime. Make `README.md` the concise repository front door, add a compact audience router to the richer `docs/index.md` homepage, align contributor/support copy, and strengthen existing public-metadata and built-site checks so the presentation cannot drift silently.

**Tech Stack:** GitHub-flavored Markdown, MkDocs Material, HTML, CSS, Python 3.11+, pytest, GitHub Actions.

## Global Constraints

- Serve biomedical researchers and developers/open-source contributors equally.
- Preserve the current deep navy, teal, blue, violet, Sora, Inter, and JetBrains Mono identity.
- `docs/generated/public-status.yaml` remains the source of truth for current metrics and maturity facts.
- Evidence supports claims but is not automatic proof; associations are not causation.
- Missing metadata remains unknown; registry breadth is not deep curation.
- Do not imply medical advice, diagnostic use, clinical decision support, complete coverage, clinical validation, or an available public hosted service.
- Do not introduce unverified users, institutions, partnerships, publications, impact metrics, or other promotional claims.
- Preserve the `med-research` distribution and `med_research` import-path compatibility wording.
- Historical release records remain historical; change only current public copy.
- Preserve responsive behavior, dark mode, keyboard focus, and reduced-motion behavior.
- Leave the untracked `artifacts/` and `.pytest_tmp/` directories untouched.
- Use `.venv\Scripts\python.exe` for Python commands in this Windows workspace.

---

## File responsibility map

- `README.md`: concise GitHub repository front door and primary deliverable.
- `docs/index.md`: deeper product story and audience routing.
- `docs/stylesheets/home.css`: homepage-only visual layout for the new router.
- `CONTRIBUTING.md`: first-contribution path and detailed contributor expectations.
- `.github/SUPPORT.md`: help-channel routing and research-use boundary.
- `.github/pull_request_template.md`: validation expectations for public-presence changes.
- `docs/project/launch-copy.md`: reusable canonical public copy.
- `docs/project/github-public-settings.md`: exact maintainer-owned GitHub About/settings values.
- `scripts/check_public_metadata.py`: source-level public version, positioning, and required-marker contract.
- `scripts/check_public_site_consistency.py`: post-build shipped-site checks; no behavior change planned.
- `tests/test_public_metadata.py`: focused regression coverage for README, homepage, support copy, and docs gates.
- `Makefile`: local documentation build and post-build validation entry points.
- `.github/workflows/docs.yml`: strict CI build and validation before Pages deployment.

---

### Task 1: Make the README the balanced repository front door

**Files:**
- Modify: `tests/test_public_metadata.py`
- Modify: `scripts/check_public_metadata.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: canonical `TAGLINE`, `DESCRIPTOR`, current version, DOI rules, and required assets from `scripts/check_public_metadata.py`.
- Produces: stable README markers `## What you can do`, `## Choose your path`, `## Quick start`, and `docs/assets/product/evidence-explorer.webp` for future drift checks.

- [ ] **Step 1: Add a failing README hierarchy test**

Append this test to `tests/test_public_metadata.py`:

```python
def test_readme_is_a_balanced_repository_front_door() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    required = (
        "docs/assets/product/evidence-explorer.webp",
        "## What you can do",
        "## Choose your path",
        "## Quick start",
        "### For researchers",
        "### For developers and contributors",
        "Public alpha · research use only",
    )
    for marker in required:
        assert marker in readme

    assert "## At a glance" not in readme
    assert "## Researcher path" not in readme
    assert "## Developer path" not in readme
    assert readme.index("## What you can do") < readme.index("## Quick start")
    assert readme.index("## Choose your path") < readme.index("## Quick start")


def test_rejects_stale_readme_public_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    _assert_overlay_fails(
        monkeypatch,
        "README.md",
        readme.replace("10,407", "10,406"),
        "README.md registry modules",
    )
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_public_metadata.py::test_readme_is_a_balanced_repository_front_door tests/test_public_metadata.py::test_rejects_stale_readme_public_metric -n 0 -q
```

Expected: both tests FAIL: the current README uses the old `At a glance`, `Researcher path`, and `Developer path` hierarchy and the current metadata checker does not reject a stale README metric.

- [ ] **Step 3: Add source-level required markers**

In `scripts/check_public_metadata.py`, add after `REQUIRED_ASSETS`:

```python
REQUIRED_SURFACE_MARKERS = {
    "README.md": (
        "docs/assets/product/evidence-explorer.webp",
        "## What you can do",
        "## Choose your path",
        "## Quick start",
        "### For researchers",
        "### For developers and contributors",
        "Public alpha · research use only",
    ),
}
```

In `main()`, immediately after the active-positioning loop, add:

```python
    for relative, markers in REQUIRED_SURFACE_MARKERS.items():
        text = _text(relative)
        for marker in markers:
            if marker not in text:
                errors.append(f"{relative} missing required public marker: {marker}")
```

Add this helper after `_status_version()`:

```python
def _status_metric(field: str) -> str:
    return _field(
        "docs/generated/public-status.yaml",
        rf'(?m)^  {re.escape(field)}:\s*"?([^"\n]+)"?\s*$',
        f"public-status.yaml metric {field}",
    )
```

After `readme = _text("README.md")` in `main()`, add:

```python
    readme_snapshot_markers = {
        "registry_modules": (
            "registry modules",
            f"| Registry modules | {int(_status_metric('registry_modules')):,} |",
        ),
        "l2_strict_validated": (
            "L2-validated modules",
            "| Strict L2-validated modules | "
            f"{int(_status_metric('l2_strict_validated')):,} |",
        ),
        "reference_tier": (
            "reference modules",
            f"| Reference modules | {int(_status_metric('reference_tier')):,} |",
        ),
        "ci_validated": (
            "CI-validated modules",
            f"| CI-validated modules | {int(_status_metric('ci_validated')):,} |",
        ),
        "offline_tests": (
            "offline tests",
            f"| Offline tests selected in the v{version} suite | "
            f"{int(_status_metric('offline_tests')):,} |",
        ),
        "analysis_pipelines": (
            "analysis pipelines",
            f"{_status_metric('analysis_pipelines')} analysis pipelines",
        ),
    }
    for label, marker in readme_snapshot_markers.values():
        if marker not in readme:
            errors.append(f"README.md {label} do not match public-status.yaml")
```

- [ ] **Step 4: Replace the README with the approved compact hierarchy**

Replace `README.md` with this complete content, retaining the current version and DOI values:

````markdown
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand/logo-dark.svg">
    <img src="docs/assets/brand/logo-light.svg" alt="NosoGraph — Disease Intelligence. Connected." width="620">
  </picture>
</p>

<p align="center"><strong>Disease Intelligence. Connected.</strong></p>

<p align="center">
  Open-source research software for connecting disease knowledge, evidence, and provenance across biomedical sources.
</p>

<p align="center">
  <a href="https://adameddahmouni.github.io/nosograph/"><strong>Explore the documentation</strong></a>
  · <a href="#quick-start">Run locally</a>
  · <a href="CONTRIBUTING.md">Contribute</a>
</p>

<p align="center">
  <a href="https://github.com/AdamEddahmouni/nosograph/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/AdamEddahmouni/nosograph?display_name=tag"></a>
  <a href="https://doi.org/10.5281/zenodo.22055279"><img alt="DOI" src="https://zenodo.org/badge/DOI/10.5281/zenodo.22055279.svg"></a>
  <a href="https://github.com/AdamEddahmouni/nosograph/actions/workflows/test.yml"><img alt="Tests" src="https://github.com/AdamEddahmouni/nosograph/actions/workflows/test.yml/badge.svg"></a>
  <a href="https://www.python.org/downloads/"><img alt="Python 3.11 and 3.12" src="https://img.shields.io/badge/python-3.11%20%7C%203.12-2F86FF.svg"></a>
  <a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache--2.0-19D2C7.svg"></a>
</p>

<img src="docs/assets/product/evidence-explorer.webp" alt="NosoGraph Evidence Explorer showing disease context, typed claims, evidence direction, and provenance" width="100%">

> **Public alpha · research use only.** NosoGraph is not medical advice, a diagnostic system, or clinical decision support. No public hosted demo is deployed; use the local Docker evaluation or CLI.

## What you can do

| Capability | What it provides | Maturity |
|---|---|---|
| Explore evidence | Follow disease context through typed claims, evidence direction, source context, and provenance | Public Alpha |
| Compare conditions | Compare two to five conditions with explicit missingness and deterministic JSON/Markdown exports | Beta |
| Build research workflows | Use the CLI, FastAPI surface, disease modules, and 40+ analysis pipelines locally | Stable CLI · Beta API |
| Extend the graph | Add disease curation, source adapters, validation, documentation, and analysis code | Open source |

NosoGraph complements upstream resources such as MONDO, HPO, PubMed, ClinicalTrials.gov, Open Targets, and GWAS Catalog. It does not replace them or turn associations into causal conclusions.

## Choose your path

### For researchers

- [Understand NosoGraph](docs/getting-started/what-is.md)
- [Follow the five-minute SLE workflow](docs/research/sle.md)
- [Inspect claims and provenance](docs/using/evidence-explorer.md)
- [Compare conditions](docs/using/compare.md)
- [Review source coverage and limitations](docs/data/coverage.md)

### For developers and contributors

- [Install from source](docs/getting-started/install.md)
- [Understand the architecture](docs/architecture/overview.md)
- [Use the CLI](docs/using/cli.md) or [API](docs/api-reference.md)
- [Run the test suite](docs/developers/testing.md)
- [Contribute code, curation, sources, or documentation](CONTRIBUTING.md)

## Quick start

```bash
git clone https://github.com/AdamEddahmouni/nosograph.git
cd nosograph
cp .env.example .env
docker compose --profile full up --build
```

Open `http://localhost:8000`. Docker Compose v2 starts the API, worker, and Redis. For a CLI-only or contributor installation, follow the [installation guide](docs/getting-started/install.md).

The product CLI is `nosograph`. The installable distribution and import path remain `med-research` and `med_research` during the public-alpha compatibility period.

## Evidence, provenance, and limits

```text
Disease → Typed claim → Evidence relationship → Study / source → Provenance / snapshot
```

Evidence records support claims; they are not automatic proof. Supporting, contradictory, inconclusive, and unasserted evidence can coexist. Missing metadata remains `unknown` rather than silently becoming certainty. See the [evidence model](docs/architecture/evidence-model.md), [provenance model](docs/architecture/provenance.md), and [data-source matrix](docs/data/sources.md).

## Current status

**NosoGraph v0.2.1 · Public Alpha · repository snapshot 2026-08-22**

| Repository-backed measure | Value |
|---|---:|
| Registry modules | 10,407 |
| Strict L2-validated modules | 88 |
| Reference modules | 6 |
| CI-validated modules | 8 |
| Offline tests selected in the v0.2.1 suite | 2,445 |

Values come from [`docs/generated/public-status.yaml`](docs/generated/public-status.yaml). Registry breadth is not curation depth: most registry modules are scaffolds. See the [current project status](docs/project/status.md) for capability-level maturity and limitations.

## Contributing

NosoGraph welcomes focused contributions to code, documentation, source integration, and disease curation. Start with [CONTRIBUTING.md](CONTRIBUTING.md), then run the local gate:

```bash
make ci-local
```

Questions belong in [GitHub Discussions](https://github.com/AdamEddahmouni/nosograph/discussions). Report vulnerabilities privately through [SECURITY.md](SECURITY.md). Never submit secrets, PHI, or patient-identifiable data.

## Citation

Cite v0.2.1 with the all-versions concept DOI [10.5281/zenodo.22055279](https://doi.org/10.5281/zenodo.22055279) until a v0.2.1 archive record exists. The historical version DOI [10.5281/zenodo.22062925](https://doi.org/10.5281/zenodo.22062925) identifies v0.2.0 only. Canonical metadata is available through GitHub's citation UI and [`CITATION.cff`](CITATION.cff).

```bibtex
@software{nosograph2026,
  title   = {NosoGraph: Disease Intelligence. Connected.},
  author  = {Eddahmouni, Adam and NosoGraph contributors},
  year    = {2026},
  url     = {https://github.com/AdamEddahmouni/nosograph},
  version = {0.2.1},
  doi     = {10.5281/zenodo.22055279}
}
```

## License and research-use boundary

NosoGraph source code is available under [Apache-2.0](LICENSE). Upstream biomedical datasets retain their own terms; see [data licenses](docs/legal/data-licenses.md). Outputs are computational research artifacts—not diagnoses, treatment recommendations, or clinical decision support.
````

- [ ] **Step 5: Run the focused contract and metadata checks**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_public_metadata.py::test_readme_is_a_balanced_repository_front_door tests/test_public_metadata.py::test_rejects_stale_readme_public_metric tests/test_public_metadata.py::test_public_metadata -n 0 -q
```

Expected: `3 passed` and `public metadata ok (version 0.2.1; ... current surfaces checked)`.

- [ ] **Step 6: Commit the README front door**

```powershell
git add README.md scripts/check_public_metadata.py tests/test_public_metadata.py
git commit -m "docs: sharpen repository front door"
```

---

### Task 2: Add immediate researcher and contributor routing to the docs homepage

**Files:**
- Modify: `tests/test_public_metadata.py`
- Modify: `scripts/check_public_metadata.py`
- Modify: `docs/index.md`
- Modify: `docs/stylesheets/home.css`

**Interfaces:**
- Consumes: existing homepage anchors `#product`, `#developers`, and `#contribute` and shared `.ng-shell`, `.ng-kicker`, and color tokens.
- Produces: stable `#researchers` anchor and `.ng-audience-routes` landmark immediately after the hero.

- [ ] **Step 1: Add a failing homepage routing test**

Append:

```python
def test_documentation_homepage_routes_both_audiences() -> None:
    homepage = (ROOT / "docs/index.md").read_text(encoding="utf-8")
    stylesheet = (ROOT / "docs/stylesheets/home.css").read_text(encoding="utf-8")

    for marker in (
        'class="ng-audience-routes"',
        'href="#researchers"',
        'href="#developers"',
        'id="researchers"',
        'id="developers"',
        'id="contribute"',
    ):
        assert marker in homepage
    assert ".ng-audience-routes" in stylesheet
    assert "Registered integrations" not in homepage
    assert "<strong>17</strong> registered integrations" not in homepage
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_public_metadata.py::test_documentation_homepage_routes_both_audiences -n 0 -q
```

Expected: FAIL because `.ng-audience-routes`, `#researchers`, and its hero-adjacent links do not exist.

- [ ] **Step 3: Add homepage markers to the metadata contract**

Extend `REQUIRED_SURFACE_MARKERS` in `scripts/check_public_metadata.py`:

```python
    "docs/index.md": (
        'class="ng-audience-routes"',
        'href="#researchers"',
        'href="#developers"',
        'id="researchers"',
        'id="developers"',
        'id="contribute"',
    ),
```

Add this adjacent forbidden-marker contract:

```python
FORBIDDEN_SURFACE_MARKERS = {
    "docs/index.md": (
        "Registered integrations",
        "<strong>17</strong> registered integrations",
    ),
}
```

After the required-marker loop in `main()`, add:

```python
    for relative, markers in FORBIDDEN_SURFACE_MARKERS.items():
        text = _text(relative)
        for marker in markers:
            if marker in text:
                errors.append(f"{relative} contains forbidden public marker: {marker}")
```

- [ ] **Step 4: Add the compact audience router after the hero**

In `docs/index.md`, insert this section between the closing hero `</section>` and `.ng-credibility-rail`:

```html
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
```

Change the researcher workflow opening tag to:

```html
<section class="ng-research-workflow ng-context-section" id="researchers" aria-labelledby="ng-research-workflow-title">
```

In the credibility rail, replace the unsupported integration count:

```html
<div><dt>Research boundary</dt><dd>Research only</dd></div>
```

In the source-section heading, replace the hard-coded count with:

```html
<p class="ng-sources-count"><strong>Source matrix</strong><br><span>Representative resources shown below.</span></p>
```

These two replacements remove the only homepage metric that is not owned by `docs/generated/public-status.yaml`.

- [ ] **Step 5: Style the router with the existing design tokens**

Add to `docs/stylesheets/home.css` immediately after the `.ng-homepage .ng-hero-rail` rules:

```css
.ng-audience-routes {
  padding: 28px 0;
  background: var(--ng-surface);
  border-bottom: 1px solid var(--ng-border);
}

.ng-audience-routes .ng-shell {
  display: grid;
  grid-template-columns: minmax(180px, 0.65fr) minmax(0, 1.65fr);
  gap: clamp(24px, 5vw, 72px);
  align-items: center;
}

.ng-audience-heading h2 {
  margin: 6px 0 0;
  color: var(--ng-ink);
  font: 620 clamp(24px, 3vw, 34px) / 1.08 var(--ng-font-display);
  letter-spacing: -0.03em;
}

.ng-audience-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.ng-audience-grid > a {
  display: grid;
  gap: 8px;
  min-height: 132px;
  padding: 20px;
  color: var(--ng-ink);
  background: var(--ng-elevated);
  border: 1px solid var(--ng-border);
  border-radius: var(--ng-radius-md);
  text-decoration: none;
  transition: border-color var(--ng-fast) var(--ng-ease), transform var(--ng-fast) var(--ng-ease), box-shadow var(--ng-fast) var(--ng-ease);
}

.ng-audience-grid > a:hover,
.ng-audience-grid > a:focus-visible {
  border-color: var(--ng-link);
  box-shadow: var(--ng-shadow-plate);
  transform: translateY(-2px);
}

.ng-audience-grid span {
  color: var(--ng-ink-muted);
  font: 500 11px / 1.45 var(--ng-font-mono);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.ng-audience-grid small {
  color: var(--ng-ink-muted);
  font: 500 12px / 1.5 var(--ng-font-text);
}

.ng-audience-grid strong {
  font: 600 17px / 1.3 var(--ng-font-display);
}

@media (max-width: 760px) {
  .ng-audience-routes .ng-shell,
  .ng-audience-grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ng-audience-grid > a {
    transition: none;
  }

  .ng-audience-grid > a:hover,
  .ng-audience-grid > a:focus-visible {
    transform: none;
  }
}
```

- [ ] **Step 6: Run homepage and metadata checks**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_public_metadata.py::test_documentation_homepage_routes_both_audiences tests/test_public_metadata.py::test_public_metadata -n 0 -q
```

Expected: `2 passed`.

- [ ] **Step 7: Commit the homepage routing**

```powershell
git add docs/index.md docs/stylesheets/home.css scripts/check_public_metadata.py tests/test_public_metadata.py
git commit -m "docs: balance homepage audience routes"
```

---

### Task 3: Align contributor, support, launch, and GitHub-settings copy

**Files:**
- Modify: `tests/test_public_metadata.py`
- Modify: `scripts/check_public_metadata.py`
- Modify: `CONTRIBUTING.md`
- Modify: `.github/SUPPORT.md`
- Modify: `.github/pull_request_template.md`
- Modify: `docs/project/launch-copy.md`
- Modify: `docs/project/github-public-settings.md`

**Interfaces:**
- Consumes: `CURRENT_VERSION` in tests and the canonical repository/docs URLs.
- Produces: current launch copy, a four-step first-contribution path, current support routes, and exact maintainer-owned GitHub About values.

- [ ] **Step 1: Add failing consistency tests for supporting surfaces**

Append:

```python
def test_supporting_public_surfaces_route_new_contributors() -> None:
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    support = (ROOT / ".github" / "SUPPORT.md").read_text(encoding="utf-8")
    pull_request = (ROOT / ".github" / "pull_request_template.md").read_text(
        encoding="utf-8"
    )
    settings = (ROOT / "docs" / "project" / "github-public-settings.md").read_text(
        encoding="utf-8"
    )

    assert "## Your first contribution" in contributing
    assert "project/good-first-issues.md" in support
    assert "project/status.md" in support
    assert "make docs-build" in pull_request
    assert "Open-source research software for connecting disease knowledge" in settings
    assert "https://adameddahmouni.github.io/nosograph/" in settings


def test_launch_copy_uses_current_public_release() -> None:
    launch_copy = (ROOT / "docs" / "project" / "launch-copy.md").read_text(
        encoding="utf-8"
    )

    assert f"NosoGraph v{CURRENT_VERSION} is a public alpha" in launch_copy
    assert f"NosoGraph v{CURRENT_VERSION} is Public Alpha" in launch_copy
    assert "NosoGraph v0.2.0 is a public alpha" not in launch_copy
    assert "NosoGraph v0.2.0 is Public Alpha" not in launch_copy
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_public_metadata.py::test_supporting_public_surfaces_route_new_contributors tests/test_public_metadata.py::test_launch_copy_uses_current_public_release -n 0 -q
```

Expected: both tests FAIL because the first-contribution section and exact About values are absent, the PR template lacks the docs gate, and launch copy still identifies v0.2.0 as current.

- [ ] **Step 3: Make launch copy a checked current surface**

Add `"docs/project/launch-copy.md"` to `CURRENT_SURFACES` in `scripts/check_public_metadata.py`.

In `docs/project/launch-copy.md`, replace both current-state occurrences of `v0.2.0` with `v0.2.1`. Do not change historical DOI text because this file contains no historical release discussion.

- [ ] **Step 4: Add the first-contribution path**

Insert this section in `CONTRIBUTING.md` after the contribution-path table:

```markdown
## Your first contribution

1. Choose a scoped [`good first issue`](docs/project/good-first-issues.md) or open a [Discussion](https://github.com/AdamEddahmouni/nosograph/discussions) before proposing a large change.
2. Follow the setup below and run the smallest relevant test while you work.
3. Run `make ci-local` before opening a pull request; documentation changes should also run `make docs-build`.
4. Explain the user or research impact, validation performed, and any data/provenance implications in the pull request template.

Documentation-only, source-integration, and disease-curation contributions are welcome; you do not need to modify the application runtime to contribute.
```

- [ ] **Step 5: Replace the support routing with current destinations**

Replace the `## Maintainer settings` section of `.github/SUPPORT.md` with:

```markdown
## Start contributing

- Browse [good first issues](../docs/project/good-first-issues.md).
- Read the [contribution guide](../CONTRIBUTING.md).
- Check the [current project status](../docs/project/status.md) and [public roadmap](../docs/project/roadmap.md) before proposing a large change.

Repository settings maintained outside git are documented in [GitHub public settings](../docs/project/github-public-settings.md).
```

- [ ] **Step 6: Strengthen the pull-request validation checklist**

Replace the documentation-related validation lines in `.github/pull_request_template.md` with:

```markdown
- [ ] `make lint` (or N/A for docs-only)
- [ ] `make test-offline` (or N/A for docs-only)
- [ ] `python scripts/check_public_metadata.py` if README, citation, release, or public copy changed
- [ ] `make docs-build` if documentation, theme, or public-site files changed
- [ ] Additional:
```

- [ ] **Step 7: Record exact GitHub About values**

Add after the opening sentence in `docs/project/github-public-settings.md`:

```markdown
## Canonical About values

- **Description:** Open-source research software for connecting disease knowledge, evidence, and provenance across biomedical sources.
- **Website:** https://adameddahmouni.github.io/nosograph/
- **Social preview:** `docs/assets/brand/social-preview.png` (1280×640)
- **Primary topics:** `biomedical-knowledge-graph`, `bioinformatics`, `disease-ontology`, `evidence-synthesis`, `fastapi`, `knowledge-graph`, `open-source`, `python`, `research-software`, `systems-biology`

Treat these values as the maintainer checklist whenever positioning or the social preview changes.
```

- [ ] **Step 8: Run the supporting-surface tests and metadata checker**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_public_metadata.py::test_supporting_public_surfaces_route_new_contributors tests/test_public_metadata.py::test_launch_copy_uses_current_public_release tests/test_public_metadata.py::test_public_metadata -n 0 -q
```

Expected: `3 passed`.

- [ ] **Step 9: Commit the aligned repository copy**

```powershell
git add CONTRIBUTING.md .github/SUPPORT.md .github/pull_request_template.md docs/project/launch-copy.md docs/project/github-public-settings.md scripts/check_public_metadata.py tests/test_public_metadata.py
git commit -m "docs: align contributor and repository copy"
```

---

### Task 4: Make the documentation gate strict locally and in GitHub Actions

**Files:**
- Modify: `tests/test_public_metadata.py`
- Modify: `Makefile`
- Modify: `.github/workflows/docs.yml`

**Interfaces:**
- Consumes: `scripts/check_public_metadata.py`, `scripts/check_public_fonts.py`, and `scripts/check_public_site_consistency.py` command-line exit codes.
- Produces: `make docs-build` as the complete local docs gate and a matching `Documentation` CI job before Pages deployment.

- [ ] **Step 1: Add a failing docs-gate contract test**

Append:

```python
def test_documentation_gate_is_strict_and_checks_shipped_site() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "docs.yml").read_text(
        encoding="utf-8"
    )

    assert "python -m mkdocs build --strict" in makefile
    assert "python scripts/check_public_site_consistency.py" in makefile
    assert "python scripts/check_public_metadata.py" in workflow
    assert "python scripts/check_public_fonts.py" in workflow
    assert "python -m mkdocs build --strict" in workflow
    assert "python scripts/check_public_site_consistency.py" in workflow
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_public_metadata.py::test_documentation_gate_is_strict_and_checks_shipped_site -n 0 -q
```

Expected: FAIL because both local and CI builds currently use non-strict `mkdocs build`, and the CI job does not run the metadata, font, or shipped-site checks.

- [ ] **Step 3: Complete the local documentation gate**

Add `check-public-site` to the `.PHONY` declaration in `Makefile`.

Add this target after `check-public-fonts`:

```make
check-public-site:  ## Verify built Pages metadata, sitemap, robots, and canonical URLs
	python scripts/check_public_site_consistency.py
```

Replace `docs-build` with:

```make
docs-build:  ## Build and verify the MkDocs documentation site
	python -m pip install -r requirements-docs.txt
	python scripts/check_public_metadata.py
	python scripts/check_public_fonts.py
	python -m mkdocs build --strict
	python scripts/check_public_site_consistency.py
```

- [ ] **Step 4: Make the GitHub Pages build match the local gate**

In `.github/workflows/docs.yml`, add these push-path filters:

```yaml
      - "scripts/check_public_*.py"
      - "tests/test_public_metadata.py"
      - "pyproject.toml"
      - "CITATION.cff"
      - "codemeta.json"
```

Replace the single build step with:

```yaml
      - name: Validate public metadata
        run: python scripts/check_public_metadata.py
      - name: Validate bundled fonts
        run: python scripts/check_public_fonts.py
      - name: Build documentation strictly
        run: python -m mkdocs build --strict
      - name: Validate shipped site
        run: python scripts/check_public_site_consistency.py
```

- [ ] **Step 5: Run the docs-gate contract and complete metadata tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_public_metadata.py -n 0 -q
```

Expected: all tests in `tests/test_public_metadata.py` PASS.

- [ ] **Step 6: Run the complete local documentation gate**

Run the equivalent direct commands so the workspace venv is explicit:

```powershell
.venv\Scripts\python.exe scripts/check_public_metadata.py
.venv\Scripts\python.exe scripts/check_public_fonts.py
.venv\Scripts\python.exe -m mkdocs build --strict
.venv\Scripts\python.exe scripts/check_public_site_consistency.py
```

Expected: metadata and font checks print `ok`; MkDocs exits 0 with no warnings promoted to errors; the site checker prints `public site consistency ok`.

- [ ] **Step 7: Commit the strict documentation gate**

```powershell
git add Makefile .github/workflows/docs.yml tests/test_public_metadata.py
git commit -m "ci: enforce strict public documentation checks"
```

---

### Task 5: Perform final public-surface and visual verification

**Files:**
- Verify: `README.md`
- Verify: `docs/index.md`
- Verify: generated `site/`
- Verify: all files changed in Tasks 1–4

**Interfaces:**
- Consumes: the complete local documentation gate from Task 4.
- Produces: a verified branch with no unsupported claims, broken audience routes, responsive regressions, or accidental changes to `artifacts/`.

- [ ] **Step 1: Run the focused public test suite serially**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_public_metadata.py -n 0 -q
```

Expected: all tests PASS.

- [ ] **Step 2: Rebuild and validate the shipped site**

```powershell
.venv\Scripts\python.exe scripts/check_public_metadata.py
.venv\Scripts\python.exe scripts/check_public_fonts.py
.venv\Scripts\python.exe -m mkdocs build --strict
.venv\Scripts\python.exe scripts/check_public_site_consistency.py
```

Expected: every command exits 0; no `{{NG_*}}` placeholder leaks into `site/`; sitemap and canonical URLs use `https://adameddahmouni.github.io/nosograph/`.

- [ ] **Step 3: Inspect the generated homepage at representative widths**

Start the local site:

```powershell
.venv\Scripts\python.exe -m mkdocs serve --dev-addr 127.0.0.1:8001
```

Inspect `/nosograph/` or the served root at 375×812, 768×1024, and 1440×900. Verify all of the following before stopping the server:

- the hero has one dominant action and no clipped evidence-trace content;
- the researcher and developer route cards appear immediately after the hero;
- route-card links land at `#researchers` and `#developers`;
- cards collapse to one column without horizontal scrolling at 375px;
- the Evidence Explorer screenshot remains legible and does not distort;
- keyboard focus is visible on both route cards and hero actions;
- light and dark palettes preserve text contrast and borders;
- reduced-motion mode removes the route-card lift and existing animated transitions;
- the footer and all capability tables remain within the viewport.

If any item fails, return to Task 2, correct the owning HTML/CSS rule, rerun Task 2 tests, and repeat this inspection before continuing.

- [ ] **Step 4: Audit current-state wording and repository links**

Run:

```powershell
rg -n "NosoGraph v0\.2\.0 is|public hosted demo is available|clinically validated|complete disease coverage|medical advice|AdamEddahmouni/med-research" README.md CONTRIBUTING.md .github docs/project docs/index.md
```

Expected: no stale current-state v0.2.0 sentence, no claim that a hosted demo is available, no clinical-validation or complete-coverage claim, no stale public repository URL; research-boundary uses of “medical advice” are expected and must remain.

- [ ] **Step 5: Check the final diff and workspace boundaries**

```powershell
git diff --check
git status --short
git diff --stat origin/master...HEAD
```

Expected: `git diff --check` prints nothing; only intentional repository-polish files are modified or committed; `artifacts/` and `.pytest_tmp/` remain untracked and unchanged.

- [ ] **Step 6: Commit only if visual verification required corrections**

If Step 3 required a correction, stage only its owning public files and commit:

```powershell
git add README.md docs/index.md docs/stylesheets/home.css scripts/check_public_metadata.py tests/test_public_metadata.py
git commit -m "fix: finish public surface visual QA"
```

If Step 3 required no correction, do not create an empty commit.
