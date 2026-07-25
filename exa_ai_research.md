# Exa AI Research — Platform Analysis & Implementation Ideas

## Overview

**Exa AI** (formerly Metaphor) is a search engine and API platform engineered specifically for **AI agents, LLMs, and developers** — not traditional human users. While Google/Bing optimize for human click-through rates and keyword matching, Exa is designed to provide high-quality, structured, and token-efficient data directly consumable by AI models.

This document captures what Exa AI is, how it works, how it compares to alternatives, and — most importantly — what features we can replicate for our Lupus Research Platform and generalize to other diseases.

---

## Table of Contents

1. [Core Technology](#1-core-technology)
2. [Key Features](#2-key-features)
3. [Comparison to Alternatives](#3-comparison-to-alternatives)
4. [Biomedical Use Cases](#4-biomedical-use-cases)
5. [Implementation Ideas for Our Platform](#5-implementation-ideas-for-our-platform)
6. [Cross-Disease Generalization](#6-cross-disease-generalization)
7. [Implementation Roadmap](#7-implementation-roadmap)
8. [Pricing & Practical Considerations](#8-pricing--practical-considerations)

---

## 1. Core Technology

### Neural / Semantic Search

Exa represents both queries and web content as **embeddings** (high-dimensional vectors) using transformer-based models. Unlike traditional keyword engines that search for exact text matches, Exa understands the **meaning** behind a query and retrieves documents based on conceptual similarity.

| Traditional (Google/Bing/PubMed) | Exa AI |
|----------------------------------|--------|
| Keyword + metadata matching | Neural embedding similarity |
| Finds exact text matches | Finds conceptually relevant content |
| Requires precise terminology | Tolerates synonyms, paraphrasing |
| Misses results with different wording | Finds results even with zero keyword overlap |

**Example**: A query for *"drugs that reverse type I interferon signature"* can find papers about JAK inhibitors, anifrolumab, or litifilimab — even if those papers never use the exact phrase "reverse type I interferon signature."

### Embeddings-Based Indexing

Exa chunks and embeds full webpages, allowing it to perform semantic similarity searches across the web at scale. This is fundamentally different from traditional search engines that index based on inverted keyword indices.

### The "Bitter Lesson of Compute"

Exa distinguishes itself by scaling **compute per search**. While Perplexity optimizes for low-latency readable answers, Exa provides infrastructure for "hard" searches — complex, multi-step queries that can run for 12-40 seconds to find, filter, and structure data from the raw, uncurated web.

### Search Latency Tiers

| Mode | Latency | Use Case |
|------|---------|----------|
| Instant | ~250ms | Real-time agent responses |
| Standard | ~1-2s | Normal queries |
| Deep | 12-40s | Complex synthesis, multi-step research |

---

## 2. Key Features

### Highlights (AI-Optimized Content Extraction)

Exa uses a specialized model to extract the **most relevant snippets** ("highlights") from a given webpage. This is highly **token-efficient** — it provides the LLM with dense, relevant information rather than forcing it to process entire, potentially noisy webpages.

This is critical for LLM-based pipelines because:
- Full webpages can be 10,000+ tokens — most of which is noise (navigation, ads, boilerplate)
- Highlights extract only the 200-500 most relevant tokens
- Dramatically reduces API costs for downstream LLM processing

### Structured Outputs

Exa can be configured via `output_schema` to extract information directly into JSON formats, allowing agents to ingest structured data directly into their workflows:

```json
{
  "company": "Exa AI",
  "founded": 2023,
  "hq": "San Francisco",
  "employees": 50
}
```

### Category-Specific Search

Specialized indexes for specific verticals:
- Academic publications
- Companies and organizations
- People
- News articles
- Financial reports (SEC filings)

### Deep Research Modes

Multi-step agent workflows that:
1. Generate sub-queries from the main research question
2. Search for each sub-query independently
3. Synthesize results into a grounded answer with citations
4. Support iterative refinement

### Monitors (Continuous Tracking)

Users can set up monitors that:
- Periodically re-search for specific queries
- Detect new web events, updates, or specific changes
- Send notifications via webhooks
- Maintain change logs

### Extensive Filtering

Granular search by:
- Domain (`site:clinicaltrials.gov`)
- Path prefixes (`/study/`)
- Content types
- Date ranges
- Custom metadata

---

## 3. Comparison to Alternatives

| Tool | Mechanism | Scope | Best For |
|------|-----------|-------|----------|
| **Exa AI** | Neural embeddings | Entire web | Complex queries, AI agents, data collection |
| **Elicit** | Curated academic DB + LLM | Academic papers | Evidence extraction, literature reviews |
| **Consensus** | Semantic Scholar index + LLM | Peer-reviewed papers | Quick answers with paper citations |
| **Perplexity** | RAG (Retrieval-Augmented Generation) | Web | Fast synthesized answers |
| **Google Scholar** | Keyword + citation matching | Academic papers | Known-item searches, bibliographies |
| **PubMed** | Keyword + MeSH matching | Biomedical papers | Structured biomedical queries |
| **Semantic Scholar** | Embeddings + citations | Academic papers | Paper discovery, citation graphs |

### Unique Advantages of Embedding-Based Search for Drug Discovery

1. **Handling Nomenclature Chaos**: A protein might be called by 5+ names across papers (gene symbol, UniProt ID, historical name, common abbreviation). Semantic search interprets intent, not exact strings.

2. **Bridging Data Silos**: Biomedical data lives in fragmented locations — clinical trial registries, patents, preprint servers, FDA labels, patient forums. Semantic search unifies retrieval across all of them.

3. **Exploratory Queries**: Traditional databases excel at "known-item" search (find trial NCT12345). They struggle with "discovery" queries (*"what are common side effects of JAK inhibitors in lupus patients?"*). Embedding-based search handles exploratory questions naturally.

4. **Transdisciplinary Search**: Finding solutions to problems in one field that have already been documented in another (e.g., a cancer immunotherapy mechanism that could apply to lupus).

---

## 4. Biomedical Use Cases

### Real-World Examples

| Platform | How They Use Exa | Relevance to Us |
|----------|-----------------|-----------------|
| **Anara** | Powers AI workspace for scientists — agentic retrieval of technical papers, accurate citations, intelligent curation of research libraries | Direct parallel to our literature mining module |
| **FutureHouse Platform** | Superintelligent scientific agents (Falcon, Crow) use Exa for high-precision literature search and synthesis, benchmarked against frontier models | Advanced version of our cross-referencing engine |
| **Cursor** | Uses Exa to search documentation, GitHub repos, package references for context-aware code generation | Shows the general-purpose power of semantic search |
| **k-dense-ai** | Exa integrated as core tool in MCP (Model Context Protocol) servers for scientific agent skills | Architecture pattern we could adopt |

### How Researchers Use Semantic Search in Biomedicine

1. **Literature Discovery & Synthesis**: Navigating massive volumes of publications, identifying relevant studies, retrieving original sources for citation accuracy
2. **Identifying Unexplored Mechanisms**: Mapping genetic associations and research gaps across disease pathways
3. **Resolving Scientific Contradictions**: Analyzing conflicting literature to identify methodological differences
4. **Real-World Evidence Gathering**: Searching beyond academic repositories into patient forums, FDA labels, and news for safety monitoring
5. **Continuous Evidence Synthesis**: Automated monitoring for new results about specific drug-gene pairs

---

## 5. Implementation Ideas for Our Platform

### Idea A: Semantic Literature Search Engine (Phase 16)

**Current state**: Our `literature_mining/miner.py` uses rigid PubMed MeSH keyword queries. Example:

```python
'(lupus OR SLE) AND ("JAK inhibitor" OR "JAK-STAT" OR "type I interferon") AND ("therapy")'
```

This misses papers that discuss JAK inhibition conceptually without using those exact terms.

**Proposed addition**: Add an **embedding-based search layer** that:

1. **Indexes** our cached PubMed articles + bioRxiv/medRxiv preprints into a local vector store (ChromaDB — we already have `data/chroma/`)
2. **Embeds** queries using sentence-transformers (free, local) or OpenAI embeddings (cheap API)
3. **Retrieves** semantically relevant articles even when terminology differs
4. **Ranks** results by semantic similarity + traditional relevance factors (recency, citation count, journal tier)

**Implementation**:

```python
# New module: semantic_search/ engine.py

from sentence_transformers import SentenceTransformer
import chromadb

class SemanticLiteratureSearch:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')  # Free, local
        self.client = chromadb.PersistentClient(path="data/chroma/")
        self.collection = self.client.get_or_create_collection("pubmed_abstracts")

    def index_articles(self, articles: list[dict]):
        """Embed and index article abstracts into vector DB."""
        texts = [a["title"] + " " + a["abstract"] for a in articles]
        embeddings = self.model.encode(texts, show_progress_bar=True)
        # ... store in ChromaDB with metadata (pmid, year, journal, etc.)

    def semantic_search(self, query: str, top_k: int = 50) -> list:
        """Find articles by meaning, not keywords."""
        query_embedding = self.model.encode(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )
        return self._format_results(results)
```

**Integration points**:
- New API endpoint: `GET /api/semantic/search?q=drugs+that+suppress+interferon+in+lupus&top_k=20`
- New CLI: `python main.py semantic --query "BTK inhibition B cell lupus" --top 20`
- Dashboard card: "🧠 Semantic Search" (Phase 16)
- Feeds results into existing NER pipeline (`literature_mining/ner.py`)

**Why this beats our current approach**:
- Finds papers about "endosomal TLR inhibition" when searching for "hydroxychloroquine mechanism"
- Discovers papers about "type I IFN blockade" when searching for "anifrolumab alternatives"
- Surfaces preprint results before they appear in PubMed (months faster)

---

### Idea B: Web-Scale Evidence Gatherer (Phase 17)

**Current state**: Our platform only searches PubMed. ClinicalTrials.gov is separate. Drug labels, patents, patient forums, and news are completely untapped.

**Proposed addition**: A `web_evidence/` module that searches across **6+ web sources** simultaneously:

| Source | Data Retrieved | Feeds Into |
|--------|---------------|------------|
| **PubMed** | Abstracts, MeSH | Literature mining |
| **ClinicalTrials.gov** | Trial status, results | Clinical trial tracker |
| **bioRxiv / medRxiv** | Preprints | Early signal detection |
| **DailyMed / FDA Labels** | AE profiles, dosing | Adverse event profiler |
| **Google Patents** | Drug patents, new uses | Drug repurposing (novelty) |
| **PubMed Central (PMC)** | Full-text articles | Deeper evidence extraction |

**Implementation approach**:

Option 1 — **Free route** (DuckDuckGo API + BioPython Entrez):
- Use DuckDuckGo's Instant Answer API (free, no key needed) for web search
- Use BioPython Entrez for PubMed/PMC (already implemented)
- Use ClinicalTrials.gov API v2 (already partially implemented)
- Scrape bioRxiv RSS feed (free)

Option 2 — **Exa AI API** (paid, but powerful):
- Single unified API for all sources
- Built-in semantic search
- Highlights extraction saves LLM token costs
- $20 free credit to start, then pay-as-you-go

**Scoring integration**: Add a new **"Web Evidence" dimension** to the drug repurposing engine:

| Scoring Factor | Weight | Data Source |
|---------------|--------|-------------|
| Clinical Evidence | 15% | PubMed + ClinicalTrials.gov |
| **Web Evidence (NEW)** | **10%** | Preprints, patents, news, labels |
| Adverse Event Profile | 20% | FDA labels + FAERS |
| (Novelty reduced) | 5% | — |
| (Other dimensions unchanged) | 50% | — |

This would shift weight from the somewhat subjective "Novelty" dimension to a data-driven "Web Evidence" dimension.

---

### Idea C: LLM-Powered Evidence Extraction (Phase 18)

**Current state**: Our NER pipeline (`literature_mining/ner.py`) uses **dictionary-based matching** against our knowledge graph. It can only find entities we already know about.

**Proposed addition**: Add an **LLM-powered extraction layer** that:

1. **Identifies novel entities** (genes, drugs, pathways not in our KG yet)
2. **Extracts structured findings** (not just entity mentions, but what the paper found)
3. **Classifies evidence level** (preclinical, Phase 1, Phase 2, Phase 3, approved)
4. **Rates relevance** to specific repurposing candidates

**Example transformation**:

```
Input (raw abstract):
  "Fenebrutinib, a reversible BTK inhibitor, reduced anti-dsDNA 
   antibody titers by 47% in NZB/W F1 lupus-prone mice at 30 mg/kg, 
   with significant reduction in proteinuria and improved survival 
   compared to vehicle control (p < 0.01)."

Current NER output (dictionary-based):
  genes_found: ["BTK"]
  drugs_found: ["fenebrutinib"]

Proposed LLM output (structured extraction):
  {
    "genes_mentioned": ["BTK"],
    "drugs_mentioned": ["fenebrutinib"],
    "key_finding": "BTK inhibition reduced anti-dsDNA titers by 47% in lupus mouse model",
    "quantitative_result": "47% reduction in anti-dsDNA, p < 0.01",
    "evidence_level": "preclinical",
    "model_system": "NZB/W F1 mice",
    "relevance_to_repurposing": "high",
    "related_candidates": ["fenebrutinib"],
    "related_genes": ["BTK"],
    "confidence": 0.92
  }
```

**Implementation**:

```python
# New module: evidence_extraction/extractor.py

from openai import OpenAI  # or local LLM via ollama

def extract_structured_findings(abstract: str, kg_context: dict) -> dict:
    """Extract structured evidence from a scientific abstract."""
    prompt = f"""
    Extract structured findings from this biomedical abstract.
    Known entities in our knowledge graph: {kg_context}
    
    Abstract: {abstract}
    
    Return JSON with: genes_mentioned, drugs_mentioned, key_finding,
    quantitative_result, evidence_level, model_system, 
    relevance_to_repurposing (high/medium/low), related_candidates,
    related_genes, confidence (0-1).
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Cheap, fast
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)
```

**Cost analysis**: GPT-4o-mini costs ~$0.15 per 1M input tokens. Processing 500 abstracts (~200 tokens each = 100K tokens) would cost ~$0.015. Essentially free at our scale.

**Integration**:
- Run on cached PubMed articles (currently ~150 articles)
- Store structured evidence in `data/evidence_db.json`
- Feed into all scoring engines as supplemental evidence
- New API: `GET /api/evidence/extract?pmid=12345678`

---

### Idea D: Continuous Evidence Monitor (Phase 19)

**Current state**: All our modules run on-demand. No automatic monitoring for new data.

**Proposed addition**: An `evidence_monitor/` module that:

1. **Tracks new publications** for each of our 39 repurposing candidates
2. **Watches for new clinical trial results** on ClinicalTrials.gov
3. **Alerts when a new drug enters trials** for one of our 13 untargeted lupus genes
4. **Maintains a change log** — what's new since last check

**How it works**:

```python
# evidence_monitor/monitor.py

class EvidenceMonitor:
    def __init__(self):
        self.last_check = self.load_checkpoint()
        self.alerts = []
    
    def check_pubmed_updates(self):
        """Check for new PubMed articles since last checkpoint."""
        for candidate in load_candidates():
            query = f'(lupus OR SLE) AND "{candidate["drug_name"]}"'
            new_articles = search_pubmed(
                query, 
                date_from=self.last_check,
                max_results=5
            )
            if new_articles:
                self.alerts.append({
                    "type": "new_publication",
                    "candidate": candidate["drug_name"],
                    "gene": candidate["gene_id"],
                    "articles": new_articles,
                    "timestamp": datetime.now().isoformat(),
                })
    
    def check_trial_updates(self):
        """Check ClinicalTrials.gov for new/updated trials."""
        for gene_id in UNTARGETED_GENES:
            new_trials = search_clinicaltrials(
                condition="lupus",
                intervention=gene_id,
                since=self.last_check,
            )
            if new_trials:
                self.alerts.append({
                    "type": "new_trial",
                    "gene": gene_id,
                    "trials": new_trials,
                    "timestamp": datetime.now().isoformat(),
                })
    
    def run(self):
        """Run full monitoring cycle."""
        self.check_pubmed_updates()
        self.check_trial_updates()
        self.save_checkpoint()
        return self.alerts
```

**Alert example**:

```
🔔 NEW EVIDENCE ALERT — July 25, 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📄 New Publication: IRF5
  "A novel IRF5 inhibitor reduces lupus nephritis in MRL/lpr mice"
  PMID: 39987654 | Journal: J Autoimmun | Date: July 2026
  Relevance: HIGH — IRF5 is an untargeted lupus gene (#3 in our GWAS list)

🧪 New Clinical Trial: BANK1
  NCT05987654 — "Phase 1 Study of BANK1 Inhibitor in SLE"
  Status: Recruiting | Sponsor: Biogen | Start: June 2026
  Relevance: HIGH — First-ever BANK1-targeted therapy entering trials
```

**Deployment options**:
- Cron job: `0 6 * * 1 python evidence_monitor/monitor.py` (weekly Monday 6 AM)
- GitHub Actions scheduled workflow (free for public repos)
- Manual trigger: `python main.py monitor`

---

### Idea E: AI-Optimized Content Extraction Pipeline

**Current state**: We return full PubMed abstracts (~250 words each) to the NER pipeline.

**Proposed optimization**: Pre-process abstracts to extract only the most relevant sentences before NER, using either:
1. A lightweight extractive summarizer (e.g., `sumy` library — free, local)
2. Exa-style "highlights" via LLM (more accurate but has API cost)
3. Simple heuristic: extract sentences containing known KG entities

This would:
- Speed up NER processing (~60% fewer tokens to process)
- Reduce noise (irrelevant methods/details filtered out)
- Make the pipeline more token-efficient if we ever add LLM processing

---

## 6. Cross-Disease Generalization

One of Exa's most powerful properties is that **the same semantic search infrastructure works for any domain**. A query about "B cell depletion therapies" finds relevant content whether the context is lupus, rheumatoid arthritis, multiple sclerosis, or cancer.

### Our Platform's Generalization Potential

Our 15-phase architecture is designed around **gene-drug-pathway networks** — patterns that repeat across autoimmune diseases:

| Autoimmune Disease | Shared Biology with Lupus | What We Already Have | What We'd Need |
|-------------------|--------------------------|---------------------|----------------|
| **Rheumatoid Arthritis** | JAK/STAT, B cells, TNF-α, CD20 | KG structure, scoring engine, semantic search | RA-specific gene list, RA drug library |
| **Multiple Sclerosis** | B cells, CD20, BTK, sphingosine-1P | KG structure, CAR-T predictor, synergy | MS-specific genes, CNS penetration filter |
| **Sjögren's Syndrome** | IFN signature, B cells, BAFF, TLR7/9 | Gene expression module, semantic search | SS gene list, glandular cell types |
| **Systemic Sclerosis** | Fibrosis, TGF-β, endothelin, IL-6 | Network pharmacology, biomarker discovery | SSc genes, fibrosis-specific pathways |
| **Type 1 Diabetes** | T cells, PTPN22, CTLA-4, IL-2 | ML predictor, CAR-T predictor | T1D genes, beta-cell biology |
| **Inflammatory Bowel Disease** | JAK/STAT, IL-12/23, integrins | Drug repurposing, synergy | IBD genes, gut-specific cell types |

### Architecture for Multi-Disease Support

To generalize the platform, we'd need:

1. **Disease-specific data files** (analogous to `knowledge_graph/data/genes.json`):
   - `diseases/lupus/genes.json`
   - `diseases/ra/genes.json`
   - `diseases/ms/genes.json`

2. **Shared infrastructure** (all modules stay the same):
   - Knowledge graph builder (same code, different input)
   - Scoring engines (same dimensions, different weights)
   - Semantic search (same embeddings, different index)
   - API & dashboard (same endpoints, different disease filter)

3. **Cross-disease insights** (unique value add):
   - "This drug targets BTK, which is implicated in lupus, RA, and MS"
   - "JAK inhibitors show efficacy across 4 autoimmune diseases"
   - "Shared biomarkers: IRF5 is relevant in lupus AND Sjögren's"

### Implementation Path

| Phase | What | Effort |
|-------|------|--------|
| **Phase G1** | Parameterize KG builder to accept disease-specific gene/drug lists | Low (~add CLI flag) |
| **Phase G2** | Add RA gene list (25 genes) + drug list (30 drugs) | Medium (~data curation) |
| **Phase G3** | Run full pipeline for RA — all 15 modules | Low (~run scripts) |
| **Phase G4** | Add cross-disease comparison views | Medium (~new dashboard) |
| **Phase G5** | Add MS, Sjögren's, SSc, T1D, IBD gene lists | High (~data curation) |

---

## 7. Implementation Roadmap

### Priority Ranking

| Priority | Feature | Impact | Effort | Dependencies |
|----------|---------|--------|--------|-------------|
| 🔴 **P1** | Semantic Literature Search | High — finds papers we currently miss | Medium | sentence-transformers (free) |
| 🔴 **P1** | LLM Evidence Extraction | High — structured findings from abstracts | Low | OpenAI API or local LLM |
| 🟠 **P2** | Web-Scale Evidence Gatherer | High — searches beyond PubMed | Medium | Search API (free or Exa) |
| 🟠 **P2** | Continuous Evidence Monitor | Medium — alerts for new data | Low | Cron / GitHub Actions |
| 🟡 **P3** | AI Content Extraction (Highlights) | Medium — token efficiency | Low | LLM or extractive summarizer |
| 🟡 **P3** | Cross-Disease Generalization | High — platform value multiplier | High | Data curation for each disease |

### Suggested Phase 16: Semantic Literature Search

```
semantic_search/
├── __init__.py
├── engine.py          # Embedding model + ChromaDB indexing
├── indexer.py         # Batch index PubMed + preprints
├── report.py          # HTML report with semantic search results
├── data/
│   └── embeddings.json
├── requirements.txt
```

**Key dependencies** (all free):
- `sentence-transformers` — local embedding model
- `chromadb` — already in project (`data/chroma/`)

**New API endpoints**:
- `POST /api/semantic/index` — Index articles into vector DB
- `GET /api/semantic/search?q=...&top_k=20` — Semantic search

**New CLI**:
- `python main.py semantic --query "BTK inhibition B cell lupus" --top 20 --export-html`

**Tests**: ~12-15 tests (indexing, search, result ranking, API)

---

## 8. Pricing & Practical Considerations

### Exa AI Pricing (for reference)

| Service | Cost | Notes |
|---------|------|-------|
| Standard Search | ~$7 / 1,000 requests | Semantic web search |
| Deep Search | ~$12-15 / 1,000 requests | Multi-step reasoning |
| Contents (highlights) | ~$1 / 1,000 pages | Extract relevant snippets |
| Monitors | ~$15 / 1,000 requests | Continuous tracking |
| Agent Runs | $0.012 - $1.00 / request | Varies by complexity |
| Free Tier | $20 credit + $10/month grant | Good for prototyping |

### Cost-Effective Alternatives (Free/Cheap)

For our platform (open science, no budget), we should prioritize free alternatives:

| Exa Feature | Free Alternative | Quality |
|-------------|-----------------|---------|
| Semantic Search | `sentence-transformers` + ChromaDB | Good (local, free) |
| Web Search | DuckDuckGo Instant Answer API | Moderate (no key needed) |
| Academic Search | BioPython Entrez (PubMed) | Excellent (already using) |
| Content Extraction | `sumy` extractive summarizer | Moderate (local, free) |
| Structured Extraction | GPT-4o-mini ($0.15/1M tokens) | Excellent (very cheap) |
| Monitors | Cron + GitHub Actions scheduled | Good (free for public repos) |

### Recommendation

**Phase 16-17**: Build with free alternatives first. If the results justify it, upgrade to Exa AI for the web-scale search capability. The architecture should be modular enough that we can swap the search backend without changing the rest of the pipeline.

---

## Summary: What We Should Build Next

| # | Feature | Why It Matters | How Hard |
|---|---------|---------------|----------|
| 1 | **Semantic Literature Search** | Finds papers our keyword queries miss — especially important for cross-disease insights and novel mechanism discovery | Medium |
| 2 | **LLM Evidence Extraction** | Transforms raw abstracts into structured, queryable evidence — feeds ALL scoring engines | Low |
| 3 | **Continuous Evidence Monitor** | Alerts us when someone starts developing a drug for our untargeted genes — actionable intelligence | Low |
| 4 | **Web-Scale Evidence Gatherer** | Goes beyond PubMed to preprints, patents, labels — fills blind spots | Medium |
| 5 | **Cross-Disease Generalization** | Applies our 15-phase platform to RA, MS, Sjögren's — 5x value multiplier | High |

All of these are inspired by Exa AI's approach but can be built with free, open-source tools at our scale.
