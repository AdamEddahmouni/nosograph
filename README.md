# 🧬 Lupus Research & Drug Discovery Platform

An open computational platform to accelerate the discovery of treatments and, ultimately, a cure for **Systemic Lupus Erythematosus (SLE)**.

---

## 📋 Project Overview

Lupus is a chronic autoimmune disease affecting ~5 million people worldwide. It's notoriously complex — driven by genetic predisposition, environmental triggers, and dysregulation across multiple immune pathways. This platform takes a multi-pronged computational approach to accelerate treatment discovery.

---

## 🏗️ Architecture

```
lupus-platform/
├── knowledge_graph/      # Phase 1 ✅ — Heterogeneous graph: genes, drugs, pathways, disease
│   ├── build_graph.py    #   NetworkX graph builder & analyzer
│   ├── data/             #   Curated JSON: 22 genes, 20 drugs, 7 pathways, 63+ relationships
│   └── web/              #   Interactive Cytoscape.js visualization
│
├── drug_repurposing/     # Phase 3 ✅ — Multi-modal drug repurposing scoring engine
│   ├── engine.py         #   6-dimensional weighted scoring across 13 untargeted genes
│   └── data/             #   39 scored candidates with mechanistic evidence
│
├── bioinformatics/       # Phase 2 ✅ — GWAS, pathway enrichment, PPI networks
│   ├── gwas.py           #   NHGRI-EBI GWAS Catalog annotation & SNP resolution
│   ├── enrichment.py     #   GSEApy/Enrichr pathway enrichment (GO, KEGG, Reactome, WikiPathways)
│   ├── ppi.py            #   STRING API protein-protein interaction networks
│   └── report.py         #   Combined HTML report with dot plots, Manhattan plots, hub charts
│
├── literature_mining/    # Phase 4 ✅ — PubMed mining & biomedical NER
│   ├── miner.py          #   BioPython Entrez PubMed search with targeted queries
│   ├── crossref.py       #   Dictionary + regex + spaCy entity extraction
│   ├── ner.py            #   Hybrid NER (regex patterns + optional scispacy)
│   └── report.py         #   HTML report with coverage bars & candidate support
│
├── virtual_screening/    # Phase 6 ✅ — Property-based virtual drug screening
│   ├── screening.py       #   5-dimensional scoring (binding, drug-likeness, etc.)
│   ├── docking.py         #   Phase 23 ✅ — AutoDock Vina integration
│   ├── vina_setup.py      #   Vina binary download helper
│   ├── report.py          #   HTML report with per-target compound tables
│   ├── targets/           #   PDB target configs (10 validated + 3 validation)
│   └── data/              #   Screening results JSON
│
├── clinical_trials/      # Phase 8 ✅ — Clinical trial tracker & analysis
│   ├── tracker.py        #   ClinicalTrials.gov API v2 queries & KG cross-ref
│   ├── report.py         #   HTML report with phase/MoA charts
│   └── data/             #   Cached trial data
│
├── ml_predictor/         # Phase 7 ✅ — ML-driven target druggability prediction
│   ├── predictor.py      #   XGBoost classifier with KG features & SHAP interpretability
│   ├── report.py         #   HTML report with SHAP plots & feature importance
│   └── data/             #   ML predictions JSON
│
├── cross_disease/        # Phase 22 ✅ — Cross-disease analyzer across 7 autoimmune diseases
│   ├── analyzer.py        #   Shared genes/drugs/pathways, disease similarity, multi-disease scoring
│   └── report.py          #   HTML report with radar chart, similarity matrix, drug rankings
│
├── tests/                # 328 tests, all passing
│   ├── test_engine.py              # Drug repurposing scoring & tiering
│   ├── test_knowledge_graph.py     # Graph construction & web export
│   ├── test_report.py              # Report generation & escaping
│   ├── test_bioinformatics_enrichment.py
│   ├── test_bioinformatics_gwas.py
│   ├── test_bioinformatics_ppi.py
│   ├── test_literature_mining.py
│   ├── test_virtual_screening.py
│   ├── test_clinical_trials.py
│   ├── test_ml_predictor.py
│   ├── test_cross_disease.py       # Cross-disease analysis
│   ├── test_docking.py             # Molecular docking engine
│   └── test_web_api.py
│
└── .github/workflows/    # CI: Python 3.10–3.12, pytest across all modules
```

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
python knowledge_graph/build_graph.py --analyze --export
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
python drug_repurposing/engine.py --top 15 --export-html
# Open drug_repurposing/report.html in a browser
```

**Tech Stack:** Python, NetworkX, custom weighted scoring model

---

### 3. 📊 Bioinformatics Analysis Platform ✅

Three integrated modules for computational genomics and systems biology:

#### 🧬 GWAS Catalog Annotation
Queries the NHGRI-EBI GWAS Catalog REST API for SLE-associated variants, resolves SNP rsIDs to genes and genomic locations, and cross-references findings against the knowledge graph. Includes Manhattan plot visualization.

```bash
python bioinformatics/gwas.py --max-studies 50 --export-html
```

#### 📈 Pathway Enrichment Analysis
Runs gene set enrichment via GSEApy/Enrichr across GO Biological Process, KEGG, Reactome, and WikiPathways. Cross-references enriched terms against the 7 curated lupus pathways in the knowledge graph. Generates publication-quality dot plots.

```bash
python bioinformatics/enrichment.py --export-html
```

#### 🔗 PPI Network Analysis
Builds protein-protein interaction networks from STRING, computes hub scores (degree + betweenness centrality), identifies hub proteins with repurposing candidates, and flags untargeted hubs as new opportunities. Includes interactive pyvis network visualization.

```bash
python bioinformatics/ppi.py --confidence 0.4 --export-html
```

#### 📋 Combined Bioinformatics Report
Generates a single HTML report integrating all three analyses with dot plots, Manhattan plots, hub score charts, and PPI network visualization. The report is auto-generated when you pass `--export-html` to any bioinformatics module:

```bash
python bioinformatics/gwas.py --export-html
python bioinformatics/enrichment.py --export-html
python bioinformatics/ppi.py --export-html
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
python literature_mining/miner.py --max 50 --export-html --targeted
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
python virtual_screening/screening.py --top 15 --export-html

# Phase 23: Real molecular docking (requires Vina binary + Meeko)
python virtual_screening/screening.py --use-vina --top 15 --export-html
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
python ml_predictor/predictor.py --top 10 --export-html
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
python clinical_trials/tracker.py --max 50 --export-html
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
python main.py run-all --export-html

# Option 2: Step-by-step
# Step 1: Build the knowledge graph (required by all other modules)
python knowledge_graph/build_graph.py --analyze --export

# Step 2: Run drug repurposing analysis
python drug_repurposing/engine.py --top 15 --export-html

# Step 3: Run bioinformatics analyses
python bioinformatics/gwas.py --export-html
python bioinformatics/enrichment.py --export-html
python bioinformatics/ppi.py --export-html

# Step 4: Mine the literature
python literature_mining/miner.py --export-html

# Step 5: Run virtual screening
python virtual_screening/screening.py --top 15 --export-html

# Step 6: Track clinical trials
python clinical_trials/tracker.py --export-html

# Step 7: Run ML target prediction
python ml_predictor/predictor.py --top 10 --export-html

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
# 297 tests, all passing
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
python main.py kg --disease ra --analyze
python main.py run-all --disease ra --export-html
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
- Real molecular docking with AutoDock Vina and PDB structures
- Additional data curation for genes, drugs, and pathways
- scispacy integration for advanced biomedical NER
- Multi-omics data integration (GEO expression datasets)
- Web application / REST API layer
