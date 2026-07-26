# Medical Research Platform

A multi-disease computational drug discovery platform supporting 7 autoimmune diseases (SLE, RA, MS, SS, SSc, T1D, IBD).

Originally focused on **Systemic Lupus Erythematosus (SLE)**, now expanded to cross-disease analysis.

---

## 📋 Project Overview

Lupus is a chronic autoimmune disease affecting ~5 million people worldwide. It's notoriously complex — driven by genetic predisposition, environmental triggers, and dysregulation across multiple immune pathways. This platform takes a multi-pronged computational approach to accelerate treatment discovery.

---

## 🏗️ Architecture

```
med-research/
├── src/med_research/
│   ├── pipeline/
│   │   ├── knowledge_graph/    # Heterogeneous graph: genes, drugs, pathways, disease
│   │   ├── drug_repurposing/   # Multi-modal drug repurposing scoring engine
│   │   ├── bioinformatics/     # GWAS, pathway enrichment, PPI networks
│   │   ├── literature_mining/  # PubMed mining & biomedical NER
│   │   ├── virtual_screening/  # Property-based screening + AutoDock Vina
│   │   ├── clinical_trials/    # Clinical trial tracker & analysis
│   │   ├── ml_predictor/       # XGBoost + SHAP druggability prediction
│   │   ├── cross_disease/      # Cross-disease analysis (7 diseases)
│   │   ├── drug_synergy/       # Drug combination synergy scoring
│   │   ├── adverse_events/     # Adverse event safety profiling
│   │   ├── network_pharmacology/ # Network pharmacology analysis
│   │   ├── gene_expression/    # Gene expression correlation
│   │   ├── car_t_predictor/    # CAR-T response prediction
│   │   ├── biomarker_discovery/ # Cross-module biomarker discovery
│   │   ├── semantic_search/    # ChromaDB semantic search
│   │   └── evidence/           # Multi-source evidence gathering + LLM extraction
│   │
│   ├── web/                    # FastAPI web application (17 routers)
│   ├── diseases/               # 7 disease configs (sle, ra, ms, ss, ssc, t1d, ibd)
│   ├── logging_config.py       # Centralized logging
│   ├── exceptions.py           # Custom exception hierarchy
│   ├── cache.py                # Centralized CacheManager
│   └── rate_limiter.py         # Jittered rate limiting
│
├── tests/                      # ~718 tests, all passing
├── Dockerfile                  # Multi-stage, non-root user
├── docker-compose.yml
├── pyproject.toml
└── .github/workflows/          # CI: Python 3.10–3.12

---

## 🧰 Tool Suite

### 1. 🕸️ Lupus Knowledge Graph ✅

An interactive graph connecting **35 genes**, **26 drugs**, **10 pathways**, and the central SLE disease node through **115 curated relationships** across 6 edge types (TARGETS, TREATS, DRIVES, PARTICIPATES_IN, MODULATES, ASSOCIATED_WITH).

**Capabilities:**
- Explore known gene-disease associations mined from GWAS literature
- Trace drug mechanisms of action to molecular targets
- Identify pathway-level intervention points
- Find drug repurposing candidates via graph traversal
- Interactive visualization with search, filtering, and detail inspection

**Run it:**
```bash
python -m med_research.cli kg --analyze --export
# Open knowledge_graph/web/index.html in a browser
```

**Tech Stack:** Python, NetworkX, Cytoscape.js, vanilla HTML/CSS/JS

---

### 2. 🧪 Drug Repurposing Engine ✅

Multi-modal scoring system evaluating **39 repurposing candidates** across **13 untargeted lupus genes** using a 6-dimensional weighted model.

**Scoring Dimensions (each 0–10, weighted):**
| Dimension | Weight | Description |
|---|---|---|
| Target Similarity | 25% | How closely related is the drug's target to the gene? |
| Pathway Proximity | 15% | Network distance in the knowledge graph |
| Mechanistic Rationale | 25% | Does the mechanism make biological sense? |
| Clinical Evidence | 20% | Literature, trials, and case series support |
| Safety Profile | 10% | Known safety from approved indications |
| Novelty Bonus | 5% | How novel is this repurposing application? |

**Run it:**
```bash
python -m med_research.cli repurpose --top 15 --disease sle --export-html
```

**Tech Stack:** Python, NetworkX, custom weighted scoring model

---

### 3. 📊 Bioinformatics Analysis Platform ✅

Three integrated modules for computational genomics and systems biology:

#### 🧬 GWAS Catalog Annotation
Queries the NHGRI-EBI GWAS Catalog REST API for SLE-associated variants, resolves SNP rsIDs to genes and genomic locations, and cross-references findings against the knowledge graph. Includes Manhattan plot visualization.

```bash
python -m med_research.cli bioinformatics --skip-enrichment
```

#### 📈 Pathway Enrichment Analysis
Runs gene set enrichment via GSEApy/Enrichr across GO Biological Process, KEGG, Reactome, and WikiPathways. Cross-references enriched terms against the 7 curated lupus pathways in the knowledge graph. Generates publication-quality dot plots.

```bash
python -m med_research.cli bioinformatics --skip-gwas
```

#### 🔗 PPI Network Analysis
Builds protein-protein interaction networks from STRING, computes hub scores (degree + betweenness centrality), identifies hub proteins with repurposing candidates, and flags untargeted hubs as new opportunities. Includes interactive pyvis network visualization.

```bash
python -m med_research.cli bioinformatics --skip-gwas --skip-enrichment
```

#### 📋 Combined Bioinformatics Report
Generates a single HTML report integrating all three analyses with dot plots, Manhattan plots, hub score charts, and PPI network visualization. The report is auto-generated when you pass `--export-html` to any bioinformatics module:

```bash
python -m med_research.cli bioinformatics
# Each generates bioinformatics/bioinformatics_report.html with the sections available
```

**Tech Stack:** Python, GSEApy, STRING API, NHGRI-EBI GWAS API, NetworkX, matplotlib, pyvis

---

### 4. 📚 Literature Mining Engine ✅

Automatically searches PubMed for SLE/lupus-related articles, extracts biomedical entities, and cross-references findings against the knowledge graph and drug repurposing candidates.

**Capabilities:**
- PubMed search with 5 curated broad queries + optional 39 per-candidate targeted queries
- Dictionary-based entity matching against all KG genes, drugs, and pathways
- Hybrid NER: regex biomedical patterns (always on) + optional spaCy/scispacy for novel entity discovery
- Literature support scoring for each repurposing candidate
- Gene-level coverage tracking with visual bars

```bash
python -m med_research.cli literature --max 50 --export-html --targeted
# Open literature_mining/literature_report.html in a browser
```

**Tech Stack:** Python, BioPython (Entrez), spaCy/scispacy (optional), regex biomedical NER

---

### 5. 🔬 Virtual Drug Screening ✅

Computationally screens the 20-drug compound library against lupus protein targets using a 5-dimensional weighted scoring model.

**Scoring Dimensions (each 0–10, weighted):**
| Dimension | Weight | Description |
|---|---|---|
| Binding Affinity Estimate | 30% | MW, LogP, HBD/HBA, TPSA pseudo-binding score |
| Drug-likeness | 20% | Lipinski Rule of 5 compliance |
| Target Complementarity | 25% | Category and keyword matching against gene biology |
| Similarity to SLE Drugs | 15% | Overlap with known repurposing candidates |
| Novelty | 10% | Approved vs investigational scoring |

**Run it:**
```bash
python -m med_research.cli screening --top 15 --export-html

# Phase 23: Real molecular docking (requires Vina binary + Meeko)
python -m med_research.cli screening --use-vina --top 15 --export-html
python virtual_screening/vina_setup.py --auto  # Install Vina binary

# Open virtual_screening/screening_report.html in a browser
```

**Tech Stack:** Python, AutoDock Vina (optional), RDKit, Meeko, BioPython

---

### 6. 🧠 ML Target Predictor ✅

Trains an XGBoost classifier on knowledge graph features to predict which currently untargeted lupus genes are most druggable, with SHAP interpretability revealing which features drive predictions.

**Capabilities:**
- Feature engineering from graph topology (degree, betweenness, pathway count, odds ratio)
- One-hot encoded gene categories across 16 biological pathways
- Stratified K-fold cross-validation with ROC-AUC scoring
- SHAP value analysis for model interpretability
- Ranked druggability scores for all untargeted genes
- Feature importance bar chart + SHAP impact visualization

**Run it:**
```bash
python -m med_research.cli ml --top 10 --export-html
# Open ml_predictor/ml_report.html in a browser
```

**Tech Stack:** Python, XGBoost, SHAP, scikit-learn, matplotlib

---

### 7. 📋 Clinical Trial Tracker ✅

Queries ClinicalTrials.gov API v2 for lupus/SLE interventional trials, categorizes by phase and mechanism of action, and cross-references trial drugs against the knowledge graph.

**Capabilities:**
- Live ClinicalTrials.gov API v2 queries with pagination
- Phase distribution analysis (Early Phase 1 through Phase 4)
- 9-category mechanism of action classification (B Cell, JAK-STAT, Complement, Cell Therapy, etc.)
- Cross-referencing against all 35 KG genes and 26 KG drugs
- Top sponsor analysis and enrollment statistics
- Matplotlib phase distribution + MoA bar charts

**Run it:**
```bash
python -m med_research.cli trials --max 50 --export-html
# Open clinical_trials/ct_report.html in a browser
```

**Tech Stack:** Python, requests, matplotlib, ClinicalTrials.gov API v2

---

---

## 🚀 Quick Start

### Installation

```bash
# Clone and set up
git clone <repo-url>
cd medical

# Install all dependencies at once
pip install -r requirements.txt

# Optional: install dev tooling (pytest, ruff, pytest-cov)
pip install -r requirements-dev.txt
```

### Quick Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install everything
pip install -r requirements.txt -r requirements-dev.txt

# Lint
ruff check .
ruff format --check .

# Run tests with coverage
pytest tests/ -v --cov=. --cov-report=term-missing
```

### Run the Full Pipeline

```bash
# Option 1: Unified CLI (one command)
python -m med_research.cli run-all --export-html

# Option 2: Step-by-step
# Step 1: Build the knowledge graph (required by all other modules)
python -m med_research.cli kg --analyze --export

# Step 2: Run drug repurposing analysis
python -m med_research.cli repurpose --top 15 --export-html

# Step 3: Run bioinformatics analyses
python -m med_research.cli bioinformatics

# Step 4: Mine the literature
python -m med_research.cli literature --export-html

# Step 5: Run virtual screening
python -m med_research.cli screening --top 15 --export-html

# Step 6: Track clinical trials
python -m med_research.cli trials --export-html

# Step 7: Run ML target prediction
python -m med_research.cli ml --top 10 --export-html

# Step 8: View results
# Open in browser:
#   knowledge_graph/web/index.html              — Interactive knowledge graph
#   drug_repurposing/report.html                 — Drug repurposing candidates
#   bioinformatics/bioinformatics_report.html     — Combined bioinformatics
#   literature_mining/literature_report.html      — Literature mining
#   virtual_screening/screening_report.html       — Virtual drug screening
#   clinical_trials/ct_report.html               — Clinical trial tracker
#   ml_predictor/ml_report.html                  — ML target predictor
```

### Docker (Alternative)

```bash
# Build the image
docker compose build

# Run the full pipeline
docker compose run --rm pipeline run-all --export-html

# Serve the knowledge graph web app (visit http://localhost:8080)
docker compose up kg-web

# Run tests
docker compose run --rm pipeline test
```

### Run Tests

```bash
python -m pytest tests/ -v
# ~718 tests, all passing
```

---

## 🎯 Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 1** | Knowledge Graph + Web Visualization | ✅ Complete |
| **Phase 2** | Bioinformatics Pipeline (GWAS, Enrichment, PPI) | ✅ Complete |
| **Phase 3** | Drug Repurposing Engine (39 candidates scored) | ✅ Complete |
| **Phase 4** | Literature Mining (PubMed + Biomedical NER) | ✅ Complete |
| **Phase 5** | Integration & Polish (CLI, Docker, Dashboard) | ✅ Complete |
| **Phase 6** | Virtual Drug Screening (Molecular Docking) | ✅ Complete |
| **Phase 7** | ML Target Predictor | ✅ Complete |
| **Phase 8** | Clinical Trial Tracker | ✅ Complete |
| **Phase 9** | Drug Combination Synergy (325 pairs) | ✅ Complete |
| **Phase 10** | Adverse Event Profiling (26 drugs) | ✅ Complete |
| **Phase 11** | Network Pharmacology Hub | ✅ Complete |
| **Phase 12** | Gene Expression Correlation | ✅ Complete |
| **Phase 13** | Interactive Radar Charts | ✅ Complete |
| **Phase 14** | CAR-T Response Predictor | ✅ Complete |
| **Phase 15** | Biomarker Discovery (cross-module) | ✅ Complete |
| **Phase 16** | Semantic Literature Search | ✅ Complete |
| **Phase 17** | Web-Scale Evidence Gatherer | ✅ Complete |
| **Phase 18** | LLM-Powered Evidence Extraction | ✅ Complete |
| **Phase 19** | Continuous Evidence Monitor | ✅ Complete |
| **Phase 20** | Cross-Disease Generalization (RA data curated) | ✅ Complete |
| **Phase 21** | Cross-Disease Expansion (MS, SS, SSc, T1D, IBD) | ✅ Complete |
| **Phase 22** | Cross-Disease Drug Repurposing Analyzer | ✅ Complete |
| **Phase 23** | Real Molecular Docking (AutoDock Vina) | ✅ Complete |
| **Phase 24** | Data Curation — Expanded KG for SS, T1D, SSc, MS, IBD + MODULATES edges | ✅ Complete |
| **Phase 25** | Advanced NER — Variant/mutation, clinical trial, statistical extraction + scispacy validation | ✅ Complete |
| **Phase 26** | GEO Multi-omics — GEO data fetcher, dynamic expression signatures | ✅ Complete |
| **Phase 27** | Web Dashboard — Cross-disease API, static mounts, dashboard enhancements | ✅ Complete |

---

## 🌐 Cross-Disease Support

The platform supports multiple autoimmune diseases through per-disease data directories:

```
knowledge_graph/data/
├── sle/                       # Systemic Lupus Erythematosus
├── ra/                        # Rheumatoid Arthritis (Phase 20)
├── ms/                        # Multiple Sclerosis (Phase 21)
├── ss/                        # Sjögren's Syndrome (Phase 21)
├── ssc/                       # Systemic Sclerosis (Phase 21)
├── t1d/                       # Type 1 Diabetes (Phase 21)
└── ibd/                       # Inflammatory Bowel Disease (Phase 21)
```

**CLI Usage:**
```bash
python -m med_research.cli kg --disease ra --analyze
python -m med_research.cli run-all --disease ra --export-html
python main.py kg --list-diseases
```

---

## 📊 Current Stats

| Metric | Value |
|---|---|
| Knowledge Graph Nodes (SLE) | 72 (35 genes, 26 drugs, 10 pathways, 1 disease) |
| Knowledge Graph Edges (SLE) | 115 curated relationships |
| Cross-Disease Support | 7 diseases: SLE, RA, MS, SS, SSc, T1D, IBD |
| Repurposing Candidates | 39 across 13 untargeted genes |
| GWAS Studies Analyzed | ~30 SLE/lupus studies |
| Enrichment Libraries | 4 (GO BP, KEGG, Reactome, WikiPathways) |
| Literature Articles | ~150 PubMed abstracts |
| Virtual Drug Screening | 20 compounds screened against 13 untargeted genes |
| Clinical Trials Tracked | 50 interventional lupus trials from ClinicalTrials.gov |
| ML Predicted Targets | 35 genes analyzed, XGBoost + SHAP druggability scoring |
| Tests | ~465 passing, 0 failures |
| Python Support | 3.10, 3.11, 3.12 |

---

## ⚠️ Disclaimer

This platform is a **research tool** intended to assist in computational drug discovery. It does not provide medical advice. Any findings are hypotheses that require rigorous experimental and clinical validation before therapeutic use.

---

## 🤝 Contributing

This is an open science project. Contributions in computational biology, immunology, rheumatology, data science, and software engineering are welcome.

**Areas where help is especially needed:**
- Jinja2 template-based HTML report generation
- Additional data curation for genes, drugs, and pathways (6 non-SLE diseases)
- Disease config population (CAR-T scores, drug safety risk tiers for RA, MS, IBD, etc.)
- Integration test suite organization
- Type annotation improvements
