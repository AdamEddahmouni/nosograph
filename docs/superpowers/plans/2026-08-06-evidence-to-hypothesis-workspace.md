# Evidence-to-Hypothesis Workspace Implementation Plan

> **Status: Implemented (historical plan).** This plan records the original backend build. The implementation is now disease-aware beyond the initial SLE-first scope; use `docs/evidence-workspace.md` for the live contract and operational guidance.
>
> **For agentic workers:** Implement this plan task-by-task with tests first and review checkpoints.

**Original goal:** Build an SLE-first backend workflow that gathers PubMed and ClinicalTrials.gov evidence, extracts provenance-backed deterministic claims with optional non-blocking LLM enrichment, ranks drugs and targets, explains knowledge-graph paths, and exports reproducible JSON/HTML dossiers.

**Architecture:** Add a focused `evidence_workspace` package that owns normalization and orchestration while reusing existing evidence gatherer, clinical-trial tracker, disease, and knowledge-graph helpers where practical. Keep computation, provenance, and rendering separate; source failures are isolated and every result remains usable without an LLM key.

**Tech Stack:** Python 3.10+, Pydantic v2, existing project pipeline helpers, NetworkX, pytest, standard-library HTML/JSON rendering.

## Global Constraints

- SLE is the only executable MVP disease, but public APIs retain `disease_id`.
- MVP live sources are PubMed and ClinicalTrials.gov; GWAS and FDA are deferred.
- Deterministic extraction always runs; LLM enrichment is optional and never required.
- No live network or LLM credentials in the default test suite.
- Every claim must reference normalized evidence and retain source provenance.
- Ranking scores are computational prioritization heuristics, never efficacy probabilities.
- HTML must be escaped, self-contained, print-friendly, and include a research-only disclaimer.
- Do not alter unrelated pre-existing working-tree changes.

---

### Task 1: Define workspace schemas and request normalization

**Files:**
- Create: `src/med_research/pipeline/evidence_workspace/__init__.py`
- Create: `src/med_research/pipeline/evidence_workspace/schemas.py`
- Create: `tests/test_evidence_workspace_schemas.py`

**Interfaces:**
- Produce `ResearchRequest`, `EvidenceRecord`, `Citation`, `Claim`, `RankedCandidate`, `GraphExplanation`, `SourceStatus`, and `EvidenceDossier` Pydantic models.
- Produce `normalize_request(request: ResearchRequest) -> ResearchRequest` and `deduplicate_evidence(records: list[EvidenceRecord]) -> list[EvidenceRecord]`.
- Use literal source names `pubmed` and `clinical_trials`, candidate types `drugs`, `targets`, and `both`, and `disease_id` default `sle`.

- [ ] Write tests for valid default input, whitespace rejection, invalid dates, unsupported sources/candidate types, bounded `max_evidence`, and JSON round-trip.
- [ ] Run `pytest tests/test_evidence_workspace_schemas.py -v` and confirm the new tests fail because the package is absent.
- [ ] Implement the Pydantic models with strict enough validation for the documented contract, default factories for collections, UTC-aware timestamps, and explicit `schema_version`.
- [ ] Implement identifier-based deduplication in priority order PMID/NCT, DOI, canonical URL; merge missing metadata without dropping provenance/source IDs.
- [ ] Run the focused schema tests and confirm they pass.

### Task 2: Add source adapter boundary and PubMed/trials adapters

**Files:**
- Create: `src/med_research/pipeline/evidence_workspace/sources.py`
- Create: `tests/test_evidence_workspace_sources.py`
- Read/reuse: `src/med_research/pipeline/evidence/gatherer.py`
- Read/reuse: `src/med_research/pipeline/clinical_trials/tracker.py`

**Interfaces:**
- Produce `EvidenceSource(Protocol)` with `name` and `search(request: ResearchRequest, terms: list[str]) -> SourceResult`.
- Produce `SourceResult(records: list[EvidenceRecord], status: SourceStatus)`.
- Produce `PubMedSource` and `ClinicalTrialsSource` adapters with injectable callables for deterministic fixtures.
- Default adapters wrap existing project functions rather than duplicating HTTP implementation.

- [ ] Write tests with fixture callables returning PubMed/trial-shaped records and assert normalized IDs, URLs, dates, source kinds, and query context.
- [ ] Write source-isolation tests where one adapter raises and the other still returns records; assert warnings/status are preserved.
- [ ] Run the focused source tests and confirm they fail before implementation.
- [ ] Implement normalization helpers for common dict shapes, native identifiers, snippets, study type, citation metadata, and retrieval timestamps.
- [ ] Catch ordinary source exceptions at the adapter boundary, return an error `SourceStatus`, and do not catch process-control exceptions.
- [ ] Run the focused source tests and confirm they pass.

### Task 3: Implement deterministic extraction and optional LLM enrichment

**Files:**
- Create: `src/med_research/pipeline/evidence_workspace/extraction.py`
- Create: `tests/test_evidence_workspace_extraction.py`
- Read/reuse: `src/med_research/pipeline/literature_mining/crossref.py`
- Read/reuse: `src/med_research/pipeline/evidence/extractor.py`

**Interfaces:**
- Produce `ExtractionResult(claims: list[Claim], warnings: list[str], llm_status: str)`.
- Produce `extract_deterministic(records: list[EvidenceRecord], disease_id: str) -> ExtractionResult`.
- Produce `enrich_with_llm(records, existing_claims, llm_client=None, model=None) -> ExtractionResult`.
- Produce `extract_claims(records, disease_id, enable_llm=True, llm_client=None, model=None) -> ExtractionResult`.

- [ ] Write tests that extract known SLE genes, drugs, pathways, support/contradiction polarity, snippets, evidence references, and citations from fixture text.
- [ ] Write tests for no-client fallback and malformed/unknown-evidence LLM output; assert deterministic claims survive and warnings are recorded.
- [ ] Write conflict tests for opposite claims about the same subject/context.
- [ ] Run focused extraction tests and confirm expected red failures.
- [ ] Implement deterministic matching using existing disease/config entities and existing entity extraction utilities where possible; create claims only with evidence IDs.
- [ ] Implement validation for LLM claim dictionaries, filtering unsupported entities/relationships/evidence IDs and recording safe warnings.
- [ ] Compute claim confidence from source/study quality, recency, extraction method, and conflict state; keep component details in the claim.
- [ ] Run focused extraction tests and confirm green.

### Task 4: Implement explainable drug and target ranking

**Files:**
- Create: `src/med_research/pipeline/evidence_workspace/ranking.py`
- Create: `tests/test_evidence_workspace_ranking.py`

**Interfaces:**
- Produce `rank_candidates(records: list[EvidenceRecord], claims: list[Claim], candidate_type: str) -> list[RankedCandidate]`.
- Produce separate `rank_drugs(...)` and `rank_targets(...)` wrappers.

- [ ] Write tests proving supporting claims increase a candidate score, contradictory claims reduce it, recent/clinical evidence contributes to components, and ties sort deterministically.
- [ ] Run focused ranking tests and verify red failures.
- [ ] Implement transparent bounded components for support, contradiction, recency, clinical-trial signal, confidence, and evidence count; include claim/citation IDs and explanation text.
- [ ] Return no candidates for a type with no claims and never create candidates from unreferenced text.
- [ ] Run focused ranking tests and confirm green.

### Task 5: Add knowledge-graph path explanations

**Files:**
- Create: `src/med_research/pipeline/evidence_workspace/graph.py`
- Create: `tests/test_evidence_workspace_graph.py`
- Reuse: `src/med_research/web/dependencies.py`
- Reuse: `src/med_research/web/services/kg_service.py`

**Interfaces:**
- Produce `build_graph_explanations(candidates: list[RankedCandidate], disease_id: str = "sle", graph=None) -> list[GraphExplanation]`.
- Explanations must contain candidate ID, path node IDs, edge/relationship labels, status `found` or `no_path_found`, and a reason when absent.

- [ ] Write tests with a small NetworkX fixture covering a valid drug→gene→pathway→disease path, missing node, and no-path cases.
- [ ] Run focused graph tests and verify red failures.
- [ ] Implement graph injection for tests and default loading through existing disease-aware KG helpers; use real shortest paths only.
- [ ] Ensure missing paths are explicit and no textual claim is converted into a fabricated graph edge.
- [ ] Run focused graph tests and confirm green.

### Task 6: Orchestrate the workspace and assemble reproducibility metadata

**Files:**
- Create: `src/med_research/pipeline/evidence_workspace/workspace.py`
- Create: `tests/test_evidence_workspace.py`
- Modify: `src/med_research/pipeline/evidence_workspace/__init__.py`

**Interfaces:**
- Produce `run_workspace(request: ResearchRequest, sources=None, graph=None, llm_client=None, model=None) -> EvidenceDossier`.
- Produce `build_search_terms(request) -> list[str]`.
- Produce source status, warnings, LLM status, run timestamps, normalized request/search plan, evidence, claims, rankings, graph explanations, limitations, and manifest.

- [ ] Write a fixture-backed end-to-end test with two source adapters, one graph fixture, deterministic extraction, rankings for both types, and reproducibility metadata.
- [ ] Write failure tests for PubMed-only success, trials-only success, both-source failure, and LLM-unavailable execution.
- [ ] Run focused orchestration tests and verify red failures.
- [ ] Implement independent source execution, deduplication, extraction, ranking, graph explanation, and dossier assembly in the documented order.
- [ ] Ensure `run_workspace` is deterministic apart from run IDs/timestamps when fixture inputs are supplied.
- [ ] Export public symbols from `__init__.py`.
- [ ] Run focused orchestration tests and confirm green.

### Task 7: Render reproducible JSON and HTML dossiers

**Files:**
- Create: `src/med_research/pipeline/evidence_workspace/report.py`
- Create: `tests/test_evidence_workspace_report.py`

**Interfaces:**
- Produce `dossier_to_json(dossier: EvidenceDossier, *, indent: int = 2) -> str`.
- Produce `render_html(dossier: EvidenceDossier) -> str`.
- Produce `write_json(dossier, path)` and `write_html(dossier, path)`.

- [ ] Write tests for JSON provenance preservation, HTML escaping, supporting/contradicting sections, citations, confidence display, graph notices, and disclaimer.
- [ ] Run focused report tests and verify red failures.
- [ ] Implement pure renderers that never recompute rankings or perform network access; HTML must be self-contained and print-friendly.
- [ ] Include the exact safety copy: `For research purposes only. This computational prioritization is not medical advice and requires experimental and clinical validation.`
- [ ] Run focused report tests and confirm green.

### Task 8: Run review, lint, and regression verification

**Files:**
- Modify only if needed after review: workspace package/tests

- [ ] Run the complete new test slice: `pytest tests/test_evidence_workspace*.py -v`.
- [ ] Run relevant existing tests: `pytest tests/test_evidence_gatherer.py tests/test_clinical_trials.py tests/test_knowledge_graph.py -v`.
- [ ] Run `ruff check src/med_research/pipeline/evidence_workspace tests/test_evidence_workspace*.py`.
- [ ] Run `ruff format --check` on the new package/tests.
- [ ] Spawn a code reviewer to inspect the implementation, provenance guarantees, failure isolation, and safety wording.
- [ ] Fix any verified review findings and rerun affected tests/lint.
- [ ] Report exact verification results and list any unrelated pre-existing working-tree changes left untouched.
