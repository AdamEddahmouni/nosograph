"""One-shot writer for public-presence markdown pages. Idempotent overwrites."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def w(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")
    print(rel)


def main() -> None:
    w(
        "docs/index.md",
        """
---
title: NosoGraph — The Open Computational Map of Human Disease
description: Open-source, evidence-native computational map connecting human diseases to phenotypes, genes, mechanisms, pathways, treatments, trials, literature, and biomedical evidence.
---

# NosoGraph

**The Open Computational Map of Human Disease**

NosoGraph is an open-source biomedical research platform that connects diseases to phenotypes, genes, mechanisms, pathways, treatments, trials, literature, and **traceable biomedical evidence**.

[Get started](getting-started/install.md){ .md-button .md-button--primary }
[GitHub](https://github.com/AdamEddahmouni/nosograph){ .md-button }

![NosoGraph hero graphic](assets/brand/hero.svg)

## What you can do

- **Explore** a disease graph and related biomedical entities.
- **Compare** conditions across selected dimensions (experimental in v2.3.0).
- **Trace** claims to evidence and provenance.
- **Analyze** via CLI, API, or research pipelines.

![Representative dashboard layout](assets/screenshots/dashboard.svg)

## Status

NosoGraph **v2.3.0** is a **public alpha**. Core research infrastructure is functional. Selected UI, comparison, and source-sync areas remain experimental. Registry size is not curation depth.

See [public-status.yaml](generated/public-status.yaml) and the [roadmap](../ROADMAP.md).

## Quick start

```bash
git clone https://github.com/AdamEddahmouni/nosograph.git
cd nosograph
cp .env.example .env
docker compose --profile full up --build
```

Then open http://localhost:8000 — or follow the [CLI path](getting-started/install.md).

## Architecture

![How NosoGraph works](assets/diagrams/how-it-works.svg)

[Architecture details](developers/architecture.md) · [Evidence model](concepts/evidence.md) · [Sources](data/sources.md)

## Citation

See [CITATION.cff](https://github.com/AdamEddahmouni/nosograph/blob/master/CITATION.cff) and [citation](project/citation.md).

## Research-use boundary

NosoGraph is research software. It is not medical advice, diagnosis, or clinical decision support.

[Security](project/security.md) · [License](project/license.md)
""",
    )

    pages = {
        "docs/getting-started/what-is.md": """
---
title: What is NosoGraph?
description: Plain-language introduction to NosoGraph, an evidence-native computational map of human disease.
---

# What is NosoGraph?

NosoGraph is software for connecting disease knowledge that is otherwise scattered across ontologies, genetics resources, pathway databases, trials, literature, and drug data—**while keeping the evidence attached**.

It is a research platform, not a clinic.

## Explore a disease

Inspect phenotypes, genes, mechanisms, pathways, treatments, trials, and literature for a selected condition.

## Compare diseases

Compare conditions on multiple dimensions. Comparison in v2.3.0 is an experimental initial slice.

## Trace claims

Open a computational claim and walk to supporting or contradictory evidence, then to provenance and the source snapshot.

## Investigate hypotheses

Rank research questions. Label outputs as computational hypotheses, not recommendations.

## Analyze programmatically

CLI (`nosograph`), HTTP API, Python import path `med_research` (compatibility), and pipelines.

Next: [installation](install.md) · [FAQ](faq.md)
""",
        "docs/getting-started/install.md": """
---
title: Installation
description: Install NosoGraph locally via Docker, pip/editable install, or contributor setup.
---

# Installation

Product name: **NosoGraph**. Canonical CLI: **`nosograph`**. Package/import: **`med-research` / `med_research`** (compatibility).

Supported Python: 3.11 and 3.12.

## Docker evaluation

See [Docker](docker.md).

## Editable install

```bash
git clone https://github.com/AdamEddahmouni/nosograph.git
cd nosograph
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -e .
cp .env.example .env
nosograph --help
```

`pip install nosograph` is **not** available yet. Do not assume a PyPI rename has happened.

## Contributor install

```bash
make venv-sync
make ci-local
```

Redis is required for async dashboard jobs and the integration test tier, not for pure CLI unit tests.

Details: [local development](../developers/local.md) and [CONTRIBUTING.md](https://github.com/AdamEddahmouni/nosograph/blob/master/CONTRIBUTING.md).
""",
        "docs/getting-started/tutorial.md": """
---
title: Five-minute tutorial
description: A short NosoGraph walkthrough using the SLE reference disease module.
---

# Five-minute tutorial

**Example · computational research · not clinical advice.**

Use the CI-validated SLE module.

```bash
nosograph disease validate sle --strict
nosograph disease coverage sle
nosograph diseases
```

If the web stack is running:

1. Open http://127.0.0.1:8000
2. Select **SLE**
3. Open Condition Explorer
4. Open Evidence Workspace
5. Optionally open Compare with RA (experimental)

Deeper: [SLE research example](../research/sle.md)
""",
        "docs/getting-started/docker.md": """
---
title: Docker
description: Run the NosoGraph dashboard with Docker Compose using the full profile.
---

# Docker

```bash
git clone https://github.com/AdamEddahmouni/nosograph.git
cd nosograph
cp .env.example .env
docker compose --profile full up --build
```

Dashboard: http://localhost:8000

The `web`, `worker`, and `beat` services are behind Compose profile **`full`**. `docker compose up` without that profile will not start the dashboard.

Local evaluation builds pass `DOCKER_SKIP_DISEASE_VALIDATE=1` so image build does not run strict validation across 10,407 modules (that gate is expected to fail on scaffolds). This does **not** disable API keys or production `DEBUG=false` rules.

Image name remains `med-research:latest` for compatibility.

Production hardening: [deployment](../developers/deployment.md)
""",
        "docs/getting-started/demo.md": """
---
title: Demo
description: How to evaluate NosoGraph locally and the status of a public hosted demo.
---

# Demo

There is **no public hosted demo** in v2.3.0.

## Local evaluation

Use [Docker](docker.md) or [installation](install.md). Fixture-backed and snapshot paths are used in CI; live connectors may call public APIs if you enable them.

Label anything fixture-backed as a snapshot. Do not imply live coverage.

## Hosted demo (planned)

Read-only, rate-limited, snapshot-backed design: [public demo architecture](../deployment/public-demo.md).

A `nosograph demo` command is deferred so it does not collide with the P2 Evidence Explorer work. Track it as a follow-up.
""",
        "docs/getting-started/faq.md": """
---
title: FAQ
description: Frequently asked questions about NosoGraph scope, data, citation, and compatibility.
---

# FAQ

**What is NosoGraph?** An open computational map of human disease: software that connects diseases to biomedical knowledge while preserving evidence.

**Who is it for?** Researchers, developers, students, curators, and institutions evaluating open research software.

**Is NosoGraph medical advice?** No.

**How many diseases does it support?** 10,407 registry modules in v2.3.0; 88 pass strict L2 validation. Counts: [public-status.yaml](../generated/public-status.yaml).

**Are all diseases equally curated?** No. Registry ≠ curation depth.

**Where does the data come from?** Upstream ontologies and databases. [Sources](../data/sources.md).

**Can I use it offline?** CLI and fixture-backed tests can run offline. Live connectors need the network.

**Does it require an LLM?** No. Optional LLM enrichment is experimental.

**Does it use OpenAI?** Only if you set `OPENAI_API_KEY` for optional workflows.

**Can I add a disease?** Yes, via the curation path.

**Can I add a data source?** Propose it with the data-source issue template; integration is a reviewed engineering change.

**Can I use it in academic research?** Yes, with citation and license/data-term compliance.

**How do I cite it?** [Citation](../project/citation.md).

**What license?** Apache-2.0 for code; upstream terms for data.

**Can I deploy it myself?** Yes. [Deployment](../developers/deployment.md).

**What is NosoGraph Compare?** An experimental multidimensional comparison slice.

**What is the Evidence Workspace?** A BETA workflow that assembles evidence into claims and ranked hypotheses.

**Why is the Python package still called med-research?** Compatibility. See [package naming](../project/package-naming.md).
""",
    }
    for rel, text in pages.items():
        w(rel, text)

    concept = {
        "docs/concepts/diseases.md": "# Diseases\n\nA disease in NosoGraph is a module keyed by a slug (for example `sle`) aligned to identifiers such as MONDO where recorded. Modules contain JSON knowledge-graph files plus Python config overlays.\n\nSee the [data model](../architecture/data-model.md) and [curation playbook](../disease-curation.md).",
        "docs/concepts/registry.md": "# Disease registry\n\nThe registry lists MONDO-aligned modules, including Open Targets scaffolds. **Listing is not validation.** Use `nosograph disease corpus-status` and [coverage](../data/coverage.md).",
        "docs/concepts/curation-tiers.md": "# Curation tiers\n\n| Tier | Meaning |\n|------|--------|\n| L0 | Scaffold gaps (missing KG JSON) |\n| L1 | KG present, config incomplete |\n| L2 | Strict validation pass (pipeline-ready) |\n| L3 | Expression-curated |\n| Reference / CI-validated | Deeper maintained sets |\n\nv2.3.0: 88 L2 strict, 6 reference, 8 CI-validated. Full playbook: [disease-curation.md](../disease-curation.md).",
        "docs/concepts/evidence.md": "# Evidence\n\nEvidence records are retrieved from source adapters (PubMed, trials, GWAS, labels, and others) and normalized. They support claims; they are not automatic proof.\n\nCanonical: [evidence-model.md](../architecture/evidence-model.md).",
        "docs/concepts/claims.md": "# Claims\n\nA claim is a deterministic assertion extracted from evidence in a disease/research context. Trace claim → evidence → provenance → source snapshot.\n\nAPIs exist in v2.3.0; polished Evidence Explorer UX is still maturing.",
        "docs/concepts/provenance.md": "# Provenance\n\nProvenance records capture source, version/date where available, import path, and fingerprints. Canonical: [provenance.md](../architecture/provenance.md).",
        "docs/concepts/sources.md": "# Biomedical sources\n\nNosoGraph does not replace upstream databases. See the public [source matrix](../data/sources.md) and machine-readable [registry.yaml](https://github.com/AdamEddahmouni/nosograph/blob/master/data/sources/registry.yaml).",
        "docs/concepts/hypotheses.md": "# Hypotheses\n\nRanked candidates and workspace outputs are **computational hypotheses** for research prioritization. They do not establish causality and must not be framed as treatment recommendations.",
        "docs/concepts/biomedical-knowledge-graph.md": """# What is a biomedical knowledge graph?

A biomedical knowledge graph stores entities (diseases, genes, phenotypes, drugs) and typed relationships, often with provenance. It is a computational structure for integration and query—not a substitute for primary literature or clinical judgment.

NosoGraph implements disease modules plus a universal store, then exposes graph analytics, evidence workflows, and APIs on top.
""",
        "docs/concepts/graph-vs-ontology.md": """# Disease knowledge graphs vs disease ontologies

Ontologies such as MONDO and HPO define controlled vocabularies and hierarchical relationships. A knowledge graph in NosoGraph **uses** those identifiers and adds cross-source associations, evidence, and research workflows.

NosoGraph is complementary to ontology projects, not a replacement.
""",
        "docs/concepts/mondo-hpo.md": """# How NosoGraph uses MONDO and HPO

MONDO provides disease identifiers and hierarchy. HPO/HPOA provide phenotype terms and annotations. NosoGraph imports these into the universal biomedical store and uses them in comparison and disease modules where curated.

Always cite and comply with MONDO and HPO licenses. See [data licenses](../legal/data-licenses.md).
""",
    }
    for rel, text in concept.items():
        w(rel, text)

    using = {
        "docs/using/web.md": "# Web interface\n\nStart `nosograph serve` or Docker `full` profile and open http://127.0.0.1:8000. The dashboard includes Condition Explorer, Evidence Workspace, corpus health, comparison, and module runners.\n\nTitle and branding: **NosoGraph**. Research-use notice appears in the footer.\n\nOpenAPI UI: `/api/docs` when enabled (follows `DEBUG` / `OPENAPI_ENABLED`).",
        "docs/using/evidence-workspace.md": "# Evidence Workspace\n\nBETA. Assembles multi-source evidence into claims and ranked hypotheses.\n\nUser guide: [evidence-workspace.md](../evidence-workspace.md). Model: [evidence-model.md](../architecture/evidence-model.md).",
        "docs/using/compare.md": "# NosoGraph Compare\n\nEXPERIMENTAL initial slice in v2.3.0. Dimensions include phenotype, gene, mechanism, treatment, and evidence_coverage. Missingness: `NOT_RECORDED` ≠ `KNOWN_ABSENT`.\n\nAPI: `POST /api/v1/nosograph/compare`. Dashboard: Condition Comparison panel.",
        "docs/using/cli.md": """# CLI

Canonical command: `nosograph` (legacy alias `med-research`).

```text
nosograph --help
```

Task-oriented groups:

| Task | Examples |
|------|----------|
| Explore / list | `diseases`, `modules` |
| Validate | `disease validate`, `disease validate-batch`, `disease coverage`, `disease corpus-status` |
| Sources | `biomed sync`, `biomed init` |
| Analyze | pipeline subcommands (`kg`, `repurpose`, …) |
| Web | `serve` |

Use `nosograph <command> --help` for flags. Compatibility notes stay below the primary flow: Python import remains `med_research`.
""",
        "docs/using/api.md": "# API\n\nFastAPI app title: **NosoGraph API**.\n\n- Swagger UI: `/api/docs`\n- OpenAPI JSON: `/openapi.json` (path may be versioned under `/api`)\n- Health: `/api/health`\n\nLocal development often uses `DEBUG=true`. Production requires `API_KEY` when `DEBUG=false`.\n\nEnvironment and endpoint catalog: [api-reference.md](../api-reference.md).",
        "docs/using/source-sync.md": "# Source sync\n\nEXPERIMENTAL. Nine-stage lifecycle with an Open Targets vertical slice.\n\n```bash\nnosograph biomed sync open_targets --dry-run\n```\n\nLifecycle: [source-sync-lifecycle.md](../architecture/source-sync-lifecycle.md).",
        "docs/using/validation.md": "# Validation\n\n```bash\nnosograph disease validate sle --strict\nnosograph disease validate-batch --tier L2 --strict\nnosograph disease corpus-status\n```\n\n`disease validate --all --strict` is **not** a merge gate for the full 10k scaffold registry. Hosted CI validates the original curated eight plus reference-tier checks as documented in release audits.",
    }
    for rel, text in using.items():
        w(rel, text)

    research_note = "\n\n> Example · computational hypothesis / research prioritization · **not clinical advice**.\n"
    w(
        "docs/research/sle.md",
        "# Investigating SLE\n"
        + research_note
        + """
Systemic lupus erythematosus (`sle`) is a CI-validated / reference disease.

1. `nosograph disease validate sle --strict`
2. Inspect phenotypes and genes in the module JSON / Condition Explorer.
3. Review expression and pathway fields where curated.
4. Compare with `ra` (experimental Compare).
5. Open Evidence Workspace; inspect a claim.
6. Trace evidence → provenance → source.
7. Export via dashboard export routes or JSON CLI output.

Do not interpret ranked drugs or genes as treatment recommendations.
""",
    )
    w(
        "docs/research/ra.md",
        "# Rheumatoid arthritis\n"
        + research_note
        + "RA (`ra`) is a CI-validated disease suitable for comparison against SLE. Same commands as the [SLE walkthrough](sle.md) with `--disease ra` / slug `ra`.",
    )
    w(
        "docs/research/ad.md",
        "# Alzheimer disease\n"
        + research_note
        + "Alzheimer disease (`ad`) is one of the original eight CI-validated diseases. Validate with `nosograph disease validate ad --strict`. Curation depth still varies by evidence type; check coverage before treating outputs as complete.",
    )
    w(
        "docs/research/comparison.md",
        "# Cross-disease comparison\n"
        + research_note
        + "Use the experimental Compare API and dashboard panel. Interpret missing values using explicit missingness semantics. Not a finished standalone Compare product in v2.3.0.",
    )
    w(
        "docs/research/evidence-tracing.md",
        "# How to trace biomedical evidence in NosoGraph\n"
        + research_note
        + "Golden path: condition → claim → evidence → provenance → source snapshot. Implemented in claim/evidence/provenance APIs. UX polish is incomplete. See [evidence flow](../assets/diagrams/evidence-flow.svg).",
    )
    w(
        "docs/research/repurposing.md",
        "# Drug repurposing (research)\n"
        + research_note
        + "Repurposing pipelines surface **candidates with evidence context**. Phrase results as “NosoGraph surfaces evidence linking X to Y for further investigation,” never “NosoGraph recommends treatment X.”",
    )

    w(
        "docs/data/coverage.md",
        """# Disease coverage

Generated from NosoGraph **v2.3.0**. Data snapshot: release date 2026-08-21. Source: [public-status.yaml](../generated/public-status.yaml).

| Tier | Count |
|------|------:|
| Registry modules | 10,407 |
| L2 strict-validated | 88 |
| L3 (sampled report) | 2 |
| Reference | 6 |
| CI-validated | 8 |

NosoGraph separates **breadth of registry coverage** from **depth of evidence curation**. Scaffolds are starting points.

Recompute: `nosograph disease corpus-status` and `nosograph disease validate-batch --tier L2 --strict`.
""",
    )
    w(
        "docs/data/sources.md",
        """# Data sources

Machine-readable registry: [`data/sources/registry.yaml`](https://github.com/AdamEddahmouni/nosograph/blob/master/data/sources/registry.yaml) (updated 2026-08-20).

| Source | Domain | Used for | Integration state | License/terms |
|--------|--------|----------|-------------------|---------------|
| MONDO | Disease ontology | IDs, hierarchy | STABLE import | CC-BY-4.0 |
| HPO | Phenotypes | Comparison, annotations | STABLE import | HPO-custom |
| HPOA | Phenotype associations | Symptom harvest | STABLE import | HPO-custom |
| GO | Function/process | Pathways | STABLE import | CC-BY-4.0 |
| Reactome | Pathways | Pathways | STABLE import | CC-BY-4.0 |
| Uberon | Anatomy | Anatomy | STABLE import | CC-BY-4.0 |
| Open Targets | Target-disease | KG scaffold, live connector, sync slice | BETA / EXPERIMENTAL sync | Open Targets data license |
| PubMed | Literature | Evidence workspace | STABLE adapter | NCBI terms |
| ClinicalTrials.gov | Trials | Trials, workspace | STABLE adapter | CT.gov terms |
| GWAS Catalog | Genetics | Workspace | BETA | EBI terms |
| openFDA | Labels | Workspace | BETA | US public domain / FDA |
| ClinVar | Variants | Biomed import | BETA | NCBI ClinVar |
| ChEMBL | Bioactivity | Live connector | BETA | EBI ChEMBL |
| PubChem | Compounds | Live connector | BETA | NCBI PubChem |
| GTEx | Expression | Expression / live | BETA | GTEx policy |
| UniProt | Proteins | Live connector | BETA | UniProt terms |
| bioRxiv/medRxiv | Preprints | Workspace | EXPERIMENTAL | Per-preprint |

LIVE vs fixture-backed vs experimental depends on the code path (CI often fixture-backed). Do not assume every source is a continuously updated live feed.

Licenses: [data-licenses.md](../legal/data-licenses.md).
""",
    )
    w("docs/data/licensing.md", "# Data licensing\n\nCanonical page: [legal/data-licenses.md](../legal/data-licenses.md).\n\nApache-2.0 covers NosoGraph source code. Upstream biomedical datasets retain their own terms.")
    w("docs/data/provenance.md", "# Data provenance\n\nCanonical: [architecture/provenance.md](../architecture/provenance.md). Researchers should be able to ask: what source, which version/date, when imported, what transformation, what evidence supports this.")
    w("docs/data/update-cadence.md", "# Update cadence\n\nOntology imports and live connectors refresh when you run import/sync jobs—not on a guaranteed public SLA. Hosted source-sync is currently an Open Targets dry-run vertical slice. Record snapshot dates in analyses. Public-status metrics are tied to the named software version.")

    w("docs/developers/architecture.md", "# Architecture\n\nCanonical overview: [architecture/overview.md](../architecture/overview.md).\n\n![System architecture](../assets/diagrams/architecture.svg)\n\nThree views: [system](../assets/diagrams/architecture.svg), [evidence flow](../assets/diagrams/evidence-flow.svg), [user workflow](../assets/diagrams/workflow-sle.svg).")
    w("docs/developers/data-model.md", "# Data model\n\nCanonical: [architecture/data-model.md](../architecture/data-model.md).")
    w("docs/developers/local.md", "# Local development\n\nPython 3.11–3.12, `make venv-sync`, `.env` from `.env.example`, Redis for dashboard jobs, `make ci-local` before PRs. Browser tests need Playwright Chromium. See CONTRIBUTING.md and AGENTS.md in the repository root.")
    w("docs/developers/testing.md", "# Testing\n\n- `make test-offline` — fast unit tier\n- `make test-integration` — needs Redis\n- `make test-browser` — Playwright\n- `make ci-local` — pre-push gate\n\n`typecheck` is informational until the mypy backlog clears.")
    w("docs/developers/deployment.md", "# Deployment\n\nCanonical: [deployment.md](../deployment.md). Public demo (not deployed here): [public-demo.md](../deployment/public-demo.md).")

    w("docs/contributing/index.md", "# Contributing\n\nThree paths: [code](code.md), [disease curation](curation.md), documentation (this site: MkDocs Material; `pip install -r requirements-docs.txt && mkdocs serve`).\n\nRoot guide: [CONTRIBUTING.md](https://github.com/AdamEddahmouni/nosograph/blob/master/CONTRIBUTING.md).")
    w("docs/contributing/curation.md", "# Disease curation contributions\n\nFollow [disease-curation.md](../disease-curation.md) and the GitHub **Disease curation** issue template. Minimum bar: identifiers, sourced evidence, provenance, no PHI, licenses respected. Tiers L0–L3 are defined there.")
    w("docs/contributing/sources.md", "# Data source contributions\n\nAdd or update entries in `data/sources/registry.yaml` with license/terms and maturity. New live connectors need tests and honest LIVE/FIXTURE/EXPERIMENTAL labels.")
    w("docs/contributing/code.md", "# Code contributions\n\nBranch from `master`, run `make ci-local`, fill the PR template. Do not weaken tests to get a green build.")
    w("docs/contributing/governance.md", "# Governance\n\nCanonical: [GOVERNANCE.md](https://github.com/AdamEddahmouni/nosograph/blob/master/GOVERNANCE.md).")

    w("docs/project/roadmap.md", "# Public roadmap\n\nCanonical: [ROADMAP.md](https://github.com/AdamEddahmouni/nosograph/blob/master/ROADMAP.md).\n\nEngineering detail: `docs/roadmaps/` (not the visitor-facing plan).")
    w("docs/project/releases.md", "# Releases\n\nLatest: [v2.3.0](https://github.com/AdamEddahmouni/nosograph/releases/tag/v2.3.0). Audit: [audits/v2.3.0-release.md](../audits/v2.3.0-release.md). Changelog: repository `CHANGELOG.md`.")
    w("docs/project/citation.md", "# Citation\n\nCanonical metadata: repository `CITATION.cff` (version **2.3.0**, URL `https://github.com/AdamEddahmouni/nosograph`). README BibTeX must match. No DOI yet — [Zenodo setup](zenodo-setup.md).")
    w("docs/project/security.md", "# Security\n\nCanonical: [SECURITY.md](https://github.com/AdamEddahmouni/nosograph/blob/master/SECURITY.md). Report privately. No PHI.")
    w("docs/project/license.md", "# License\n\nApache-2.0 source. Data: [data-licenses.md](../legal/data-licenses.md).")
    w(
        "docs/project/source-of-truth.md",
        """# Documentation source of truth

| Artifact | Owns |
|----------|------|
| README.md | Public overview |
| docs/ | User and technical documentation |
| ROADMAP.md | Public roadmap |
| docs/roadmaps/ | Engineering plans |
| docs/audits/ | Validation / release evidence |
| CHANGELOG.md | Version history |
| CITATION.cff | Canonical citation |
| docs/generated/public-status.yaml | Public metric numbers |
| CONTRIBUTING.md | Contribution workflow |
| GOVERNANCE.md | Governance |
| SECURITY.md | Vulnerability reporting |
""",
    )
    w(
        "docs/project/package-naming.md",
        """# Package naming strategy

| Era | Brand | CLI | Install | Import |
|-----|-------|-----|---------|--------|
| v2.x (now) | NosoGraph | `nosograph` | `med-research` | `med_research` |
| Future major | NosoGraph | `nosograph` | planned `nosograph` | planned `nosograph` + shim |

Do not publish a package merely for branding. Confirm PyPI name availability before promising `pip install nosograph`.
""",
    )
    w(
        "docs/project/zenodo-setup.md",
        """# Zenodo / DOI setup (maintainer)

No DOI exists yet. Do not display a DOI badge until Zenodo mints one.

1. Log in to [Zenodo](https://zenodo.org) with the GitHub account that can admin `AdamEddahmouni/nosograph`.
2. GitHub → Settings → Integrations (or Zenodo GitHub page) → enable the `nosograph` repository.
3. Create a GitHub Release (already true for v2.3.0) or cut the next release after enabling.
4. Verify the deposit: title NosoGraph, version, license Apache-2.0, metadata from CITATION.cff / codemeta.json.
5. Copy the **concept DOI** (all versions) and **version DOI** into CITATION.cff `identifiers:` and the README badge.
6. Re-run `python scripts/check_public_metadata.py`.

This archival is for research software discovery, not a claim of clinical validation.
""",
    )
    w(
        "docs/project/github-public-settings.md",
        """# Manual GitHub settings

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
""",
    )
    w(
        "docs/project/github-discussions-seed.md",
        """# Seeded Discussions (copy/paste)

Create after categories exist.

## Welcome to NosoGraph — what are you researching?

NosoGraph is an open computational map of human disease. Introduce yourself: disease area, methods, or what you hope to trace in the evidence model. Research use only.

## Which disease should receive deeper curation next?

Registry size ≠ curation depth. Which condition should move toward L2/L3 next, and what public sources support that work?

## Which biomedical source should NosoGraph integrate next?

Propose a source with license/terms, identifier scheme, and research value. See `data/sources/registry.yaml`.

## Share what you're building with NosoGraph

Show and tell for tools, notebooks, and analyses. No PHI. Label hypotheses as research prioritization.

## NosoGraph v2.3.0 public-alpha discussion

Thread for the v2.3.0 release: disease-general core, 88/88 L2 strict, Compare slice, provenance APIs. Known gaps: hosted demo, package rename, UX polish.
""",
    )
    w(
        "docs/project/openssf-readiness.md",
        """# OpenSSF / supply-chain readiness (assessment)

Not chasing a badge in this sprint.

| Check | State |
|-------|--------|
| Security policy | Present (`SECURITY.md`) |
| Releases | v2.3.0 tagged |
| Workflow permissions | `contents: read` on Tests |
| Dependabot | Configured |
| Pinned Actions | Uses major tags (`@v7`); pin-to-SHA is a future hardening |
| Branch protection | Maintainer setting |
| Signed tags | v2.3.0 has SSH signature |
| CodeQL | Not enabled here; evaluate cost vs signal |
| Scorecard | Optional later |

Do not enable noisy workflows solely for a badge.
""",
    )
    w(
        "docs/project/adoption-metrics.md",
        """# Public metrics (privacy-respecting)

Track GitHub Insights: stars, forks, clones, visitors, issues, discussions, contributors. Docs: GitHub Pages traffic after enablement. Later: citations, Zenodo downloads, Docker pulls if published.

Do not add invasive analytics pixels to the research UI. Prefer GitHub/Pages native stats.
""",
    )
    w(
        "docs/project/launch-copy.md",
        """# Launch copy

**Core story:** Biomedical knowledge is fragmented across disease ontologies, genetics resources, pathway databases, clinical trials, publications, and drug data. NosoGraph is building an open computational layer across those sources while preserving evidence and provenance.

**50 words:** NosoGraph is an open-source computational map of human disease. It connects conditions to phenotypes, genes, mechanisms, pathways, treatments, trials, literature, and traceable evidence. Public alpha — research use only, not medical advice. Registry coverage is not the same as curation depth.

**150 words:** (use README + 50-word blurb; keep limitations: public alpha, no hosted demo, package name `med-research`, experimental Compare.)

Do not ask communities to “please star.” Channels only if the story fits: GitHub, Show HN, r/bioinformatics, r/computationalbiology, r/openscience, LinkedIn, Bluesky, university lists, awesome-bioinformatics — without spam.
""",
    )
    w(
        "docs/media/README.md",
        """# Media kit

- Short: Open computational map of human disease (evidence-native, open source, research use only).
- 50 / 150 words: [launch-copy.md](../project/launch-copy.md)
- Logo usage: [assets/brand](../assets/brand/README.md) — node/edge language, no clinical clipart
- Social preview: `../assets/brand/social-preview.png`
- Screenshots: representative layouts in `../assets/screenshots/` (not live PHI-bearing captures)
- Links: https://github.com/AdamEddahmouni/nosograph · docs GitHub Pages URL · [CITATION.cff](https://github.com/AdamEddahmouni/nosograph/blob/master/CITATION.cff)
- Release: v2.3.0 public alpha (2026-08-21)
""",
    )
    w(
        "docs/deployment/public-demo.md",
        """# Public hosted demo (design)

**Status:** NOT deployed. v2.3.0 identified the missing public demo.

## Goals

`demo.nosograph.*` or GitHub Pages cannot host the FastAPI app; use a cheap VM/container later with explicit authorization.

## Architecture (snapshot-first)

- Read-only API + dashboard
- `DEMO_MODE=true`: disable mutating jobs, disable live paid APIs, disable LLM
- Fixture/snapshot dataset (ci_validated diseases), labeled snapshot date
- Rate limits + no unrestricted source fetch
- No secrets in the image; no PHI
- Abuse: reject pipeline fan-out; cap concurrency
- Shutdown: destroy VM / scale to zero

## Cost (order of magnitude)

Single small VM or one container: typically low tens of USD/month if always-on; near-zero if on-demand. Snapshot mode avoids Open Targets/PubMed flood.

## Preload

Showcase `sle`, `ra`, `ad` because they are CI-validated with richer fixtures—not because of popularity alone.

## Next action

Implement `DEMO_MODE` in a dedicated P2-aligned issue; do not ship an unsafe open proxy.
""",
    )

    examples = {
        "examples/README.md": """# Examples

Deterministic research examples. **Not clinical advice.** No secrets, no PHI.

Run from the repo root with the package installed (`pip install -e .`).

| Script | Topic |
|--------|--------|
| `01_explore_a_disease.py` | Load SLE module metadata |
| `02_compare_two_diseases.py` | Compare CLI help / engine import |
| `03_trace_evidence.py` | Provenance types exist |
| `04_generate_a_research_hypothesis.py` | Framing for hypotheses |
| `05_query_nosograph_api.py` | Documents local OpenAPI URLs |
""",
        "examples/01_explore_a_disease.py": '''"""Explore a CI-validated disease module. Example · not clinical advice."""

from med_research.diseases.base import Disease


def main() -> None:
    disease = Disease("sle")
    print("disease_id:", disease.disease_id)
    print("name:", getattr(disease, "name", "sle"))
    cfg = disease.config
    print("config_keys:", sorted(list(cfg.keys())[:12]), "...")
    print("Research use only. Registry/module presence is not a clinical finding.")


if __name__ == "__main__":
    main()
''',
        "examples/02_compare_two_diseases.py": '''"""Point to NosoGraph Compare. Example · experimental · not clinical advice."""

from med_research.biomed.nosograph_compare.service import NosoGraphCompareService
from med_research.biomed.store import get_default_repository


def main() -> None:
    print("NosoGraph Compare is an experimental initial slice.")
    print("Typical pair: sle vs ra — missingness is explicit.")
    repo = get_default_repository()
    service = NosoGraphCompareService(repo)
    print("service:", type(service).__name__)
    print("Use POST /api/v1/nosograph/compare when the API is running.")
    print("Not medical advice.")


if __name__ == "__main__":
    main()
''',
        "examples/03_trace_evidence.py": '''"""Evidence tracing reminder. Example · not clinical advice."""

from med_research.pipeline.evidence_workspace import schemas


def main() -> None:
    print("Trace: condition → claim → evidence → provenance → source snapshot")
    print("schema_module:", schemas.__name__)
    print("Computational hypothesis only. Not a causal or clinical conclusion.")


if __name__ == "__main__":
    main()
''',
        "examples/04_generate_a_research_hypothesis.py": '''"""How to phrase NosoGraph outputs. Example · not clinical advice."""


def main() -> None:
    print(
        "Preferred: NosoGraph surfaces evidence linking entity X to disease Y "
        "for further investigation."
    )
    print("Avoid: NosoGraph recommends treatment X.")
    print("Label: Example · Computational hypothesis · Research prioritization.")


if __name__ == "__main__":
    main()
''',
        "examples/05_query_nosograph_api.py": '''"""Document local API entry points. Example · not clinical advice."""


def main() -> None:
    print("Start: nosograph serve --host 127.0.0.1 --port 8000")
    print("OpenAPI UI:  http://127.0.0.1:8000/api/docs")
    print("Health:      http://127.0.0.1:8000/api/health")
    print("Compare:     POST /api/v1/nosograph/compare")
    print("Auth: local DEBUG=true typically; production requires API_KEY.")


if __name__ == "__main__":
    main()
''',
    }
    for rel, text in examples.items():
        w(rel, text)


if __name__ == "__main__":
    main()
