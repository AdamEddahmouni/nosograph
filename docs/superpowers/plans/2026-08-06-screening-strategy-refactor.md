# Disease-Aware Virtual Screening Strategy Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace SLE-shaped virtual-screening assumptions with validated, provenance-carrying strategies for all seven disease modules while preserving existing screening APIs.

**Architecture:** Add a focused `screening_strategy.py` module containing a validated immutable strategy contract, deterministic fingerprinting, strategy resolution, and strategy-driven scoring helpers. `screening.py` keeps its current public functions but delegates target complementarity, reference similarity, novelty, and composite weighting through the resolved strategy. Each disease config declares an explicit strategy using its existing pathways, genes, and drugs; no efficacy claims or external biomedical values are invented.

**Tech Stack:** Python dataclasses, existing disease config loader, JSON knowledge-graph data, pytest, existing FastAPI/Celery/dashboard integration.

## Global Constraints

- Preserve public signatures for `build_compound_library`, `compute_target_complementarity`, `compute_similarity_score`, `compute_novelty_score`, `compute_composite_score`, and `screen_compounds`; optional `disease_id` parameters remain backwards compatible.
- Never fall back from a known non-SLE disease to SLE strategy data, SLE candidate data, or SLE vocabulary.
- Scores remain bounded from 0.0 through 10.0 and remain computational prioritization heuristics, not efficacy claims.
- Existing unrelated working-tree changes must not be overwritten, staged, or committed.
- Screening coverage must remain blocked for missing or malformed strategies and ready only when the strategy contract validates.

---

### Task 1: Add the validated strategy contract

**Files:**
- Create: `src/med_research/pipeline/virtual_screening/screening_strategy.py`
- Test: `tests/test_virtual_screening_strategy.py`

**Interfaces:**
- Produces `ScreeningStrategy`, `strategy_for_disease(disease_id)`, `validate_strategy(strategy)`, and `strategy_fingerprint(strategy)`.
- `ScreeningStrategy` fields: `strategy_id`, `disease_id`, `pathway_keywords`, `mechanism_keywords`, `reference_drug_ids`, `weights`, `source`, `curated_inputs`, `inferred_inputs`, `limitations`.
- `strategy_for_disease` raises `ValueError` for unknown or malformed strategy configuration; it must not substitute SLE.

- [x] **Step 1: Write failing contract tests**

```python
def test_strategy_for_each_disease_is_valid():
    for disease_id in ("sle", "ra", "ms", "ss", "ssc", "t1d", "ibd"):
        strategy = strategy_for_disease(disease_id)
        assert strategy.disease_id == disease_id
        assert strategy.pathway_keywords
        assert strategy.mechanism_keywords
        assert strategy.weights
        assert abs(sum(strategy.weights.values()) - 1.0) < 1e-9


def test_unknown_disease_never_uses_sle_strategy():
    with pytest.raises(ValueError):
        strategy_for_disease("not-a-disease")


def test_strategy_fingerprint_is_deterministic():
    strategy = strategy_for_disease("ibd")
    assert strategy_fingerprint(strategy) == strategy_fingerprint(strategy)
    assert len(strategy_fingerprint(strategy)) == 64
```

- [x] **Step 2: Run the focused tests and verify the expected import/configuration failure**

Run: `PYTHONPATH=src python -m pytest tests/test_virtual_screening_strategy.py -q`

Expected: FAIL because the strategy module and config contract do not yet exist.

- [x] **Step 3: Implement the contract**

Use a frozen dataclass. Require non-empty disease ID, strategy ID, pathway and mechanism vocabularies, normalized weights summing to 1, and a non-empty source. Resolve the strategy from `Disease(disease_id).get_screening_profile()`, copy only active-disease configuration, and compute a SHA-256 fingerprint over canonical JSON.

- [x] **Step 4: Run the focused tests**

Run: `PYTHONPATH=src python -m pytest tests/test_virtual_screening_strategy.py -q`

Expected: The tests pass once the seven configs are added in Task 2; until then, the implementation should fail clearly with missing strategy configuration rather than use SLE.

---

### Task 2: Add explicit strategies to all seven disease configs

**Files:**
- Modify: `src/med_research/diseases/sle/config.py`
- Modify: `src/med_research/diseases/ra/config.py`
- Modify: `src/med_research/diseases/ms/config.py`
- Modify: `src/med_research/diseases/ss/config.py`
- Modify: `src/med_research/diseases/ssc/config.py`
- Modify: `src/med_research/diseases/t1d/config.py`
- Modify: `src/med_research/diseases/ibd/config.py`
- Modify: `src/med_research/diseases/base.py`
- Modify: `src/med_research/diseases/coverage_report.py`
- Test: `tests/test_multidisease_coverage.py`

**Interfaces:**
- `Disease.get_screening_profile()` returns the active config’s `SCREENING_PROFILE` dictionary.
- `SCREENING_PROFILE` must provide `strategy_id`, `pathway_keywords`, `mechanism_keywords`, `reference_drug_ids`, `weights`, `source`, `curated_inputs`, `inferred_inputs`, and `limitations`.
- Strategy vocabularies are derived from each disease’s pathway names and known mechanism/category terms; reference IDs must be filtered to IDs present in that disease’s `drugs.json`.

- [x] **Step 1: Add failing coverage assertions**

```python
@pytest.mark.parametrize("disease_id", DISEASES)
def test_screening_strategy_is_full_for_every_disease(disease_id):
    from med_research.diseases.coverage import module_coverage

    result = module_coverage(
        disease_id, "screening", ("genes", "drugs", "pathways", "screening_profile")
    )
    assert result.status == "ready"
    assert result.level == "full"
```

- [x] **Step 2: Run the focused coverage test and verify non-SLE screening is currently blocked**

Run: `PYTHONPATH=src python -m pytest tests/test_multidisease_coverage.py -q`

Expected: The new parametrized screening assertion fails for the six non-SLE diseases because `screening_profile` is missing.

- [x] **Step 3: Add the seven configuration dictionaries**

Use disease pathway names and categories already present in each disease module. Use transparent heuristic weights, initially preserving the existing composite dimensions while allowing disease-specific emphasis. Mark mechanism matching as inferred and include limitations explaining that scores are not experimental binding affinity.

- [x] **Step 4: Remove the SLE-only implicit marker in `Disease.get_screening_profile()`**

Return only explicit configuration. A missing `SCREENING_PROFILE` must return `{}` for every disease, including SLE, unless its config explicitly declares the strategy.

- [x] **Step 5: Run coverage and contract tests**

Run: `PYTHONPATH=src python -m pytest tests/test_multidisease_coverage.py tests/test_virtual_screening_strategy.py -q`

Expected: All seven disease screening coverage checks pass.

---

### Task 3: Refactor scoring to consume the active strategy

**Files:**
- Modify: `src/med_research/pipeline/virtual_screening/screening.py`
- Test: `tests/test_virtual_screening.py`
- Test: `tests/test_virtual_screening_strategy.py`

**Interfaces:**
- Add optional `strategy=None` parameters internally; public wrappers continue accepting existing arguments.
- `compute_target_complementarity(compound, gene_info, disease_id="sle")` resolves the active strategy and uses strategy vocabulary plus gene category/function overlap.
- `compute_similarity_score` uses active-disease reference drugs and active-disease candidate/library metadata; it must not read the shared SLE repurposing candidate file for non-SLE scoring.
- `compute_novelty_score` uses active disease display name and strategy reference IDs.
- `compute_composite_score(scores, weights=None)` accepts optional strategy weights and validates normalized weights.

- [x] **Step 1: Add failing disease-isolation tests**

```python
def test_target_complementarity_uses_active_disease_vocabulary():
    gene = {
        "id": "IL23R",
        "category": "IL-23 / Th17 Axis",
        "function": "mucosal cytokine signaling",
    }
    compound = {"mechanism": "IL-23 / Th17 inhibitor", "target": "IL23R", "category": "IBD therapy"}
    ibd = compute_target_complementarity(compound, gene, disease_id="ibd")
    sle = compute_target_complementarity(compound, gene, disease_id="sle")
    assert ibd > sle


def test_composite_score_accepts_strategy_weights():
    scores = {
        "binding_estimate": 8,
        "druglikeness": 8,
        "target_complementarity": 8,
        "similarity_score": 8,
        "novelty_score": 8,
    }
    assert (
        compute_composite_score(
            scores,
            {
                "binding_estimate": 0.1,
                "druglikeness": 0.1,
                "target_complementarity": 0.5,
                "similarity_score": 0.2,
                "novelty_score": 0.1,
            },
        )
        == 8.0
    )
```

- [x] **Step 2: Run the focused tests and verify the old hardcoded scorer fails the disease-isolation assertion**

Run: `PYTHONPATH=src python -m pytest tests/test_virtual_screening_strategy.py -q`

Expected: FAIL because the current scorer recognizes only its hardcoded SLE category map.

- [x] **Step 3: Implement strategy-driven scorer helpers**

Tokenize case-insensitively, normalize punctuation, score exact and multi-token keyword matches, cap complementarity at 10, and preserve the current function behavior for SLE by placing its existing vocabulary in the explicit SLE strategy.

For similarity, resolve reference drug IDs from the strategy and compare against the active disease compound library; use neutral `3.0` only when no active-disease reference exists, and record that limitation in result metadata rather than silently treating it as evidence.

- [x] **Step 4: Pass strategy weights through `screen_compounds`**

Resolve strategy after coverage validation. Use the strategy for all five dimensions and add `strategy_id`, `strategy_fingerprint`, and `disease_id` to every scored result and the top-level response.

- [x] **Step 5: Run screening regression tests**

Run: `PYTHONPATH=src python -m pytest tests/test_virtual_screening.py tests/test_virtual_screening_strategy.py -q`

Expected: Existing SLE scoring tests and new disease-isolation tests pass.

---

### Task 4: Wire strategy metadata through coverage, service, and reports

**Files:**
- Modify: `src/med_research/pipeline/virtual_screening/report.py`
- Modify: `src/med_research/web/services/shared_services.py`
- Modify: `src/med_research/web/models/shared.py`
- Modify: `src/med_research/web/static/js/dashboard.js`
- Test: `tests/test_multidisease_coverage.py`
- Test: `tests/test_web_api.py`

**Interfaces:**
- Screening top-level results expose `strategy_id`, `strategy_fingerprint`, and `strategy_limitations` alongside `coverage` and `status`.
- API `ScreeningResponse` accepts these fields without breaking existing clients.
- The dashboard shows the strategy identifier/fingerprint in the coverage panel and never renders blocked screening as “Analysis Complete.”

- [x] **Step 1: Add failing metadata assertions**

```python
def test_screening_result_has_strategy_provenance():
    result = screen_compounds(target_genes=[], compound_library=[], disease_id="ibd")
    assert result["strategy_id"] == "ibd-screening-v1"
    assert result["strategy_fingerprint"]
    assert result["coverage"]["status"] == "ready"
```

- [x] **Step 2: Run the test and verify metadata is absent**

Run: `PYTHONPATH=src python -m pytest tests/test_virtual_screening_strategy.py -q`

Expected: FAIL on missing strategy metadata.

- [x] **Step 3: Add metadata to service/model/report/dashboard paths**

Ensure the service forwards the entire screening metadata contract. Render limitations as explicit research caveats, not as efficacy language. Preserve existing result rows and API field defaults.

- [x] **Step 4: Run focused API/static tests**

Run: `PYTHONPATH=src python -m pytest tests/test_multidisease_coverage.py tests/test_web_api.py -q`

Expected: Screening response models and dashboard coverage checks pass when dependencies are installed.

---

### Task 5: Add all-disease screening smoke tests and documentation

**Files:**
- Modify: `tests/test_multidisease_coverage.py`
- Modify: `tests/test_virtual_screening.py`
- Modify: `README.md`
- Modify: `docs/evidence-workspace.md` only if screening coverage terminology is referenced

- [x] **Step 1: Add deterministic smoke tests**

For every disease, build its compound library and call `screen_compounds` against one valid disease gene with a small library fixture. Assert `status == "ready"`, `coverage.level == "full"`, matching disease ID, a non-empty strategy fingerprint, bounded scores, and no `lupus` token in non-SLE strategy vocabulary.

- [x] **Step 2: Run smoke tests**

Run: `PYTHONPATH=src python -m pytest tests/test_virtual_screening.py tests/test_multidisease_coverage.py tests/test_virtual_screening_strategy.py -q`

Expected: All targeted tests pass.

- [x] **Step 3: Update documentation**

Document that virtual screening is strategy-driven, property-based prioritization; list the strategy provenance fields and explain that full coverage means curated strategy inputs exist, not validated efficacy.

---

### Task 6: Review and broad validation

**Files:**
- Review all files changed by Tasks 1–5.

- [x] **Step 1: Run compile and import checks**

Run: `python -m compileall -q src/med_research tests && PYTHONPATH=src python scripts/check_imports.py && git diff --check`

Expected: compilation succeeds, import audit reports no stale references, and diff check is clean for owned changes.

- [x] **Step 2: Run the code review agent**

Review for SLE fallback leakage, weight errors, malformed profiles, API compatibility, and blocked-result rendering.

- [x] **Step 3: Run the complete offline suite**

Run: `PYTHONPATH=src python -m pytest tests/ -m "not slow" -q --tb=short`

Expected: all available offline tests pass. If pytest or project dependencies are unavailable, report the exact environment limitation rather than claiming success.

- [x] **Step 4: Run final disease coverage verification**

Run: `PYTHONPATH=src python -m med_research.cli disease validate --all --strict`

Expected: all seven disease configs validate successfully, and `disease coverage <id>` reports screening as `FULL / ready` for every disease.
