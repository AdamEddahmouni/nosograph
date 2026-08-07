# Evidence-to-Hypothesis Workspace Design

**Date:** 2026-08-06
**Status:** Implemented (historical design record)
**Scope:** Disease-aware backend workflow with PubMed, ClinicalTrials.gov, optional expanded sources, provenance, and exports

## Goal

Build a reproducible backend workflow that accepts a natural-language biomedical question with optional filters, gathers evidence, extracts provenance-backed claims using deterministic rules with optional LLM enrichment, ranks drugs and targets, explains valid knowledge-graph paths, and exports a cited JSON/HTML evidence dossier.

The implementation started with an SLE-first vertical slice and now preserves `disease_id` through request validation, search-term generation, source execution, ranking context, graph explanation, reporting, and the web job contract. Seven discovered disease modules are currently validated by `disease validate --all --strict`.

The MVP is a research-support tool. It must not present computational rankings as established efficacy or medical advice.

## Scope and non-goals

### Implemented

- Disease-aware request and dossier contracts with SLE-compatible defaults.
- Free-text research question plus optional date range, source selection, candidate type, result limit, and LLM toggle.
- PubMed and ClinicalTrials.gov source adapters, with GWAS and FDA-label adapters also available through the source boundary.
- Deterministic extraction that works without credentials or network access when given fixtures/cached data.
- Optional LLM enrichment that is validated, provenance-labeled, and non-blocking.
- Normalized evidence records and structured claims.
- Supporting and contradicting evidence handling.
- Explainable drug and target rankings.
- Knowledge-graph path explanations when a real path exists, plus explicit no-path explanations.
- Reproducible run metadata and source provenance fingerprints.
- JSON and self-contained HTML dossier export.
- Unit, mocked-source, fixture end-to-end, API, dashboard contract, and Playwright browser tests.

### Deferred or outside this package

- User authentication and multi-user ownership policy for saved runs.
- PDF generation as a required runtime capability. HTML output is print-friendly.
- Full cross-disease parity for every scientific scoring table; disease validation blocks incomplete configuration for Workspace execution.
- Replacement of the existing source adapters or frontend with a new framework.

## Public package boundary

```text
src/med_research/pipeline/evidence_workspace/
├── __init__.py
├── schemas.py       # Typed request, evidence, claim, ranking, graph, and dossier models
├── sources.py       # Common adapter protocol and source adapters
├── extraction.py    # Deterministic extraction and optional LLM enrichment
├── ranking.py       # Explainable drug and target scoring
├── graph.py         # Valid knowledge-graph path discovery and explanations
├── workspace.py     # End-to-end orchestration and failure isolation
└── report.py        # JSON serialization and self-contained HTML rendering
```

The package is an orchestration and normalization boundary. It reuses existing disease and evidence helpers where public behavior is compatible rather than duplicating source HTTP logic.

## Input contract

```python
ResearchRequest(
    disease_id="sle",
    question="Find promising JAK/STAT interventions for SLE",
    sources=("pubmed", "clinical_trials"),
    date_from=None,
    date_to=None,
    candidate_type="both",
    max_evidence=50,
    enable_llm=True,
)
```

Requirements:

- `disease_id` is normalized and validated against discovered disease modules.
- `question` is non-empty after trimming and retained in the manifest.
- Sources are a non-empty subset of supported source names.
- Dates, when supplied, are valid and ordered.
- `candidate_type` supports `drugs`, `targets`, or `both`; default is `both`.
- `max_evidence` is bounded from 1 through 200.
- Search expansion is deterministic: disease configuration plus recognized terms from the question and profile.

## Normalized evidence model

Every adapter returns a common evidence record containing:

- Stable internal evidence ID.
- Source kind (`pubmed`, `clinical_trials`, `gwas`, or `fda_labels`).
- Source-native identifier such as PMID, NCT, GWAS accession, or SPL set ID.
- DOI and canonical source URL when available.
- Title, abstract/description snippet, and source metadata.
- Publication, study, or update date when available.
- Evidence/study type and quality tier/score.
- Retrieval timestamp.
- Query/search context that produced the record.

Records are deduplicated by strongest available source-native identifier, DOI, or canonical URL while preserving complementary metadata and source IDs.

## Claim model and provenance

A claim is never standalone. It references one or more normalized evidence IDs and includes claim ID, subject entity/type, relationship, human-readable text, evidence type, supporting snippet, citation references, confidence with component breakdown, extraction method, optional model name, timestamps, and limitations.

Deterministic claims are emitted when their patterns/entities are present. LLM claims are accepted only after schema validation and evidence-reference validation. Invalid, malformed, or unsupported LLM output becomes a warning and is not silently included as evidence.

Conflicting claims remain visible as separate claims. Conflict detection links claims sharing a subject/context but differing in polarity or conclusion; confidence is reduced for affected ranking inputs.

## Source adapters

The `EvidenceSource` protocol accepts a normalized request and search-term list and returns a `SourceResult` containing records and a `SourceStatus`. Adapters isolate ordinary source failures, preserve native identifiers and URLs, and support fixture injection.

Source results execute independently. PubMed or ClinicalTrials.gov can fail without erasing the other source's evidence. A missing adapter is reported as `skipped`; a failed adapter is reported as `error` with a warning.

## Extraction and ranking

The pipeline normalizes the request, builds search terms, gathers sources, deduplicates records, extracts deterministic claims, optionally validates LLM claims, detects conflicts, ranks drugs and targets, generates graph explanations, and assembles the dossier.

Ranking components expose support, contradiction, recency, quality, clinical-trial signal, confidence, and evidence-count signals where available. Scores are prioritization heuristics, not probabilities of efficacy.

## Knowledge-graph explanations

For ranked candidates, the graph layer attempts real paths such as:

```text
drug → target gene → pathway → disease
```

If a node is absent or no path exists, the dossier contains a structured `no_path_found` explanation with a reason. Textual evidence never fabricates a graph edge.

## Dossier contract and exports

The `EvidenceDossier` contains schema/version and run ID, request and search plan, timestamps, source statuses, normalized evidence, claims, rankings, graph explanations, warnings, limitations, a provenance manifest/fingerprint, and a research-only disclaimer.

JSON export serializes the complete dossier without dropping provenance. HTML export is self-contained, escaped, print-friendly, and includes research question, run metadata, source/retrieval summary, rankings, evidence/citations, graph explanations, limitations, and the disclaimer.

The report renderer consumes the dossier rather than recomputing scores or fetching data.

## Testing and acceptance

The authoritative current commands are:

```bash
python -m pytest tests/test_evidence_workspace*.py -q
python -m pytest tests/test_evidence_workspace_browser.py -q
```

The fixture-backed suite does not require live network, Redis, Celery workers, or LLM credentials. Browser coverage includes submission, duplicate prevention, progress fallback, source/status rendering, exports, and terminal `FAILURE`, `ERROR`, and `TIMEOUT` recovery with escaped messages.
