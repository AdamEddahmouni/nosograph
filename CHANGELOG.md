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
