# Changelog

## [Phase 5] Integration & Polish — 2026-07-19

### Sprint Goal
Transform 4 standalone research modules into a **unified, reproducible, well-tested platform** with a single entry point, containerization, and complete documentation.

---

### Added

#### Unified CLI (`main.py`)
- Single entry point orchestrating all 4 modules via `argparse` subcommands
- **`run-all`** — Full pipeline: Knowledge Graph → Drug Repurposing → Bioinformatics → Literature Mining
- **`kg`** — Build & export the knowledge graph with optional analysis
- **`repurpose`** — Score drug repurposing candidates with configurable top-N
- **`bioinformatics`** — Run GWAS, enrichment, and PPI individually or combined
- **`literature`** — Mine PubMed with configurable article count and per-drug targeted queries
- **`test`** — Run the full test suite (quiet mode available)
- Consolidated bioinformatics report: `run-all --export-html` loads all three JSON result sets and generates one combined `bioinformatics_report.html`
- Cross-platform subprocess execution via `sys.executable`
- Graceful error handling with non-zero exit codes for CI integration

#### Root Dependency Files
- **`requirements.txt`** — Merged from 4 module-specific files: `networkx`, `matplotlib`, `gseapy`, `requests`, `biopython`
- **`requirements-dev.txt`** — Dev tooling: `pytest`, `pytest-cov`, `ruff`
- **`ruff.toml`** — Linter config: Python 3.10+, line-length 100, pyflakes + bugbear + simplify rules

#### Dockerization
- **`Dockerfile`** — Multi-stage build (`python:3.11-slim`), pre-builds knowledge graph at image build time, exposes port 8080, `main.py` as entrypoint
- **`docker-compose.yml`** — Two services: `pipeline` (CLI with writable output volumes) and `kg-web` (serves interactive graph on `:8080`)
- **`.dockerignore`** — Excludes `__pycache__`, venv, IDE files, databases

#### Unified Dashboard (`index.html`)
- Dark-themed root dashboard matching all existing report styles
- Hero section with animated gradient, subtitle, and tech badges
- 6 stat cards: 50 KG nodes, 22 genes, 39 candidates, 4 modules, ~150 articles, 137 tests
- 4 completed module cards with colored borders, icons, descriptions, tags, and dual-action buttons (View Report / View Data)
- 3 planned module cards (dimmed) for Virtual Screening, ML Predictor, Clinical Trial Tracker
- Quick Start section with `pip` + `main.py` and Docker commands
- Footer with links to all 4 reports

#### Literature Mining Tests (`tests/test_literature_mining.py`)
- **59 new tests** across all 4 literature_mining sub-modules
- **ner.py** (17 tests): regex gene/drug/disease extraction, deduplication, known-entity filtering, merge logic, install hints
- **crossref.py** (16 tests): synonym generation, entity matching, relevance scoring, cross-referencing integration
- **miner.py** (12 tests): candidate query generation, mocked PubMed search, error handling, print summary
- **report.py** (14 tests): HTML escape, report generation with mocked file I/O, novel entity sections
- Global spaCy mocking via autouse fixture; BioPython per-test mocking with monkeypatch

---

### Changed

#### README.md
- Roadmap updated: Phases 1–4 marked ✅ Complete, Phase 5 marked 🟡 In Progress
- Architecture tree showing all 4 modules, test files, and CI
- Usage commands for every module with correct flags
- Quick Start section with full pipeline walkthrough
- Stats table (50 nodes, 39 candidates, 196 tests)
- Installation instructions updated to use root `requirements.txt`
- Docker usage section added
- Contributing section with areas needing help

#### CI Workflow (`.github/workflows/test.yml`)
- Now installs from root `requirements.txt` + `requirements-dev.txt`
- Adds `python main.py --help` verification step
- Tests all 6 modules automatically (already ran `pytest tests/`)

---

### Summary

| Metric | Before | After |
|--------|--------|-------|
| Entry points | 6 separate scripts | 1 unified CLI + 6 separate scripts |
| `requirements.txt` files | 4 (per module) | 1 root + 1 dev |
| Tests | 137 | 196 (+59 literature mining) |
| Docker support | None | Dockerfile + compose |
| Dashboard | Per-module only | Root `index.html` hub |
| README accuracy | Phases 2-4 marked "Planned" | All phases accurate |
| CI coverage | KG + drug repurposing | All 6 modules |

**All 196 tests pass. No breaking changes to any module API.**

## [Phase 9] Drug Combination Synergy — 2026-07-24

### Sprint Goal
Add a new module that predicts synergistic drug pairs from the 26-drug knowledge graph library using a 5-dimensional weighted scoring model.

---

### Added

#### Drug Synergy Module (`drug_synergy/`)
- **`engine.py`** — Core synergy scoring engine with 5 weighted dimensions:
  - Target Complementarity (30%) — how different are the two drugs' molecular targets?
  - Pathway Diversity (25%) — how diverse are the biological pathways affected?
  - Mechanism Orthogonality (20%) — how independent are the mechanisms of action?
  - Safety Non-overlap (15%) — non-overlapping toxicity profiles
  - Combined Evidence (10%) — existing clinical evidence for the combination
- Scores all 325 unique drug pairs from the 26-drug library
- Ranked output with 4-tier priority classification
- **`report.py`** — Standalone HTML report with highlights grid, ranked table, and methodology

#### Web API Integration
- **`GET /api/synergy/pairs`** — Returns ranked synergistic drug pairs with score breakdowns
- **`POST /api/jobs/synergy`** — Celery async job with WebSocket progress streaming
- Pydantic models in `web_api/models/synergy.py`
- Service layer in `web_api/services/synergy_service.py`
- Dedicated router in `web_api/routers/synergy.py`
- "Synergy" OpenAPI tag in config

#### Dashboard & CLI
- Synergy module card in the web dashboard with live execution
- CLI subcommand: `python main.py synergy --top 20 --export-html`
- Integration into `run-all` pipeline (now 8 steps)
- WebSocket job streaming and HTTP polling fallback support

#### Tests
- **23 tests** in `tests/test_drug_synergy.py`:
  - 13 unit tests covering all 5 scoring dimensions
  - 7 integration tests for batch scoring and full pipeline
  - 2 CLI integration tests
  - Marked with `@pytest.mark.slow` for integration tests

### Upcoming Features (Documented)
- Adverse Event Profiling (FAERS/SIDER integration)
- Network Pharmacology Hub (centrality, community detection)
- Gene Expression Correlation (GEO datasets, Connectivity Map)
- Interactive Radar Charts (Chart.js score visualizations)

**All 23 synergy tests pass alongside the existing 297.**

---

## [Phase 10] Adverse Event Profiling — 2026-07-25

### Sprint Goal
Add lupus-specific adverse event safety profiling across all 26 KG drugs and integrate as a new scoring dimension in the drug repurposing engine.

---

### Added

#### Adverse Events Module (`adverse_events/`)
- **`profiler.py`** — Core profiling engine with curated FDA-label safety data for all 26 drugs
- 4-dimensional weighted scoring:
  - Lupus Symptom Overlap (35%) — do AEs mimic lupus symptoms?
  - Severity Burden (30%) — how severe are common AEs?
  - Chronic Use Safety (25%) — is the drug safe long-term?
  - Drug-Induced Lupus Risk (10%) — risk of triggering DIL
- Black box warning tracking and monitoring requirements
- **`report.py`** — HTML report with safety rankings, highlights, and per-drug profiles

#### Drug Repurposing Engine Update
- Replaced `safety_score` (10%) with `adverse_event_score` (20%)
- Updated weights: Target 20%, Pathway 15%, Mechanistic 20%, Clinical 15%, AE 20%, Novelty 10%
- Drug name matching against KG drug IDs for reliable profile lookup
- Graceful fallback to legacy `safety_score` for non-KG repurposing candidates
- Updated report display for adverse event scores

#### Web API Integration
- **`GET /api/safety/profiles`** — All 26 drug safety profiles with summary stats
- **`GET /api/safety/profiles?drug_id=X`** — Single drug detailed safety profile
- **`POST /api/jobs/safety`** — Celery async job with progress streaming
- Pydantic models in `web_api/models/adverse_events.py`
- Service layer in `web_api/services/adverse_events_service.py`
- "Safety" OpenAPI tag in config

#### Dashboard & CLI
- Safety Profiling module card in the web dashboard (Phase 10)
- CLI: `python main.py safety --drug belimumab --export-html`
- WebSocket streaming support for async profiling

#### Tests
- **26 tests** in `tests/test_adverse_events.py`:
  - 17 unit tests covering all scoring dimensions
  - 9 integration tests (marked `@pytest.mark.slow`)

**All 26 adverse event tests pass. All existing engine tests pass with updated weights.**

---

## [Phase 11] Network Pharmacology Hub — 2026-07-25

### Sprint Goal
Deep network analysis on the full 72-node/115-edge lupus knowledge graph with centrality metrics, community detection, and bridge node identification.

---

### Added

#### Network Pharmacology Module (`network_pharmacology/`)
- **`analyzer.py`** — Comprehensive network analysis engine:
  - **Centrality**: degree, betweenness, eigenvector, closeness, PageRank for all 72 nodes
  - **Community Detection**: Louvain algorithm (with greedy modularity fallback), 9 communities found (modularity 0.524)
  - **Bridge Nodes**: Top 20 nodes by betweenness centrality connecting communities
  - **Graph Metrics**: density (0.045), diameter, avg shortest path, clustering coefficient, assortativity
  - Graceful eigenvector centrality fallback on disconnected graphs (uses largest component)
  - Results saved to `network_analysis.json` for API consumption
- **`report.py`** — HTML report with metrics cards, centrality rankings, community breakdown, and methodology

#### Web API Integration
- **`GET /api/kg/centrality?metric=betweenness&top_n=20`** — Per-node centrality scores
- **`GET /api/kg/communities`** — Community detection results with node membership
- Service functions in `web_api/services/kg_service.py`: `run_centrality_analysis()`, `run_community_detection()`
- Pydantic models in `web_api/models/kg.py`: `CentralityResponse`, `CommunityDetectionResponse`

#### Dashboard & CLI
- Network Pharmacology module card in the web dashboard (Phase 11)
- CLI: `python main.py network --centrality`, `--communities`, `--export-html`

#### Tests
- **16 tests** in `tests/test_network_pharmacology.py`:
  - 11 unit tests: graph metrics, centrality, bridge nodes, communities
  - 5 integration tests (marked `@pytest.mark.slow`)

**All 16 network pharmacology tests pass. 72 nodes, 115 edges, 9 communities, modularity 0.524.**

---

## [Phase 12] Gene Expression Correlation — 2026-07-25

### Sprint Goal
Connectivity Map-inspired module that correlates drug mechanisms against curated SLE gene expression signatures to score each drug's potential to reverse disease-associated transcriptomic dysregulation.

---

### Added

#### Gene Expression Module (`gene_expression/`)
- **`correlator.py`** — Core correlation engine with curated SLE signatures:
  - **SLE Upregulated Genes** (38 genes with fold-changes): IFN signature, cytokines, B/T cell markers
  - **SLE Downregulated Genes** (26 genes with fold-changes): complement, Treg, DNase, clearance
  - **Drug Target Gene Mapping**: 26 drugs → therapeutic target genes
  - **Pathway-Level Reversal**: 11 drugs with known pathway-level expression effects
  - **Cell Type Relevance**: 11 SLE-relevant immune cell types with disease relevance scores
- 5-dimensional weighted scoring:
  - Signature Reversal (35%) — counteracts up/down-regulated disease genes?
  - Target-Disease Overlap (25%) — drug targets in dysregulated lupus pathways?
  - Cell Type Specificity (20%) — active in B cells, pDCs, Tfh?
  - Expression Evidence (15%) — well-studied in SLE transcriptomics?
  - Directionality (5%) — drug's effect directionally correct?
- **`report.py`** — HTML report with highlights grid, ranked table, and methodology

#### Web API Integration
- **`GET /api/expression/correlate?top_n=10`** — Ranked drug expression correlation scores
- Pydantic models in `web_api/models/expression.py`
- Service layer in `web_api/services/expression_service.py`
- Dedicated router in `web_api/routers/expression.py`
- "Expression" OpenAPI tag in config

#### Dashboard & CLI
- Gene Expression module card in the web dashboard (Phase 12)
- CLI: `python main.py expression --top 15 --export-html`
- Direct API mode (no Celery job) for fast synchronous results

#### Tests
- **17 tests** in `tests/test_gene_expression.py`:
  - 4 data integrity tests (SLE signatures, target mappings, cell types)
  - 7 unit tests covering all 5 scoring dimensions
  - 3 integration tests for full analysis and JSON persistence
  - 3 slow tests (report generation, API service, CLI help)

**Top result: Anifrolumab (9.16) — strongest IFN signature reversal. Litifilimab (8.81), Baricitinib (7.90).**

---

## [Phase 13] Interactive Radar Charts — 2026-07-25

### Sprint Goal
Add interactive Chart.js radar (spider) charts to the three core scoring reports for visual score dimension comparison.

---

### Added

#### Drug Repurposing Report (`drug_repurposing/report.py`)
- Radar chart of top 5 candidates across 6 dimensions (Target Similarity, Pathway Proximity, Mechanistic Rationale, Clinical Evidence, Adverse Event Profile, Novelty)
- Chart.js v4.4.7 CDN integration
- Dark-themed chart styling matching platform design
- Novelty score scaled 0-5 to 0-10 for visual consistency

#### Virtual Screening Report (`virtual_screening/report.py`)
- **Overall radar chart**: Top 5 hits across 5 dimensions (Binding, Drug-Like, Target, Similarity, Novelty)
- **Per-target radar charts**: Individual radar charts for each screened gene target
- JSON data generated via `json.dumps()` for proper escaping

#### Drug Synergy Report (`drug_synergy/report.py`)
- Radar chart of top 5 synergistic pairs across 5 dimensions (Target Complementarity, Pathway Diversity, Mechanism Orthogonality, Safety Non-overlap, Combined Evidence)
- Pair names truncated for legend readability

**All 3 reports regenerated with interactive charts. No external dependencies beyond Chart.js CDN.**

---

## [Future] Planned Features — Roadmap
The following features are documented for future implementation:

### Adverse Event Profiling
- New scoring dimension in drug repurposing engine using FAERS/SIDER adverse event data
- Scores each candidate on known adverse events vs lupus symptom overlap
- Updates `drug_repurposing/engine.py` with a `safety_profile_score` dimension
- Adds `GET /api/repurpose/safety` endpoint with per-drug adverse event profiles

### Interactive Radar Charts for Scoring
- Enhances drug repurposing and virtual screening reports with interactive radar/spider charts
- Uses Chart.js for per-candidate score breakdown visualization
- Updates `report.py` in both modules + adds Chart.js CDN dependency
