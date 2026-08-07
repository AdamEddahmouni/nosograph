# Strict Multi-Disease Coverage Contract

> **Status:** Approved design; implementation pending
> **Date:** 2026-08-06
> **Scope:** Disease-aware pipeline execution, coverage reporting, and validation

## 1. Goal

Make the platform's seven advertised disease modules scientifically honest and operationally consistent. Every disease/module execution must distinguish curated support from inferred or unavailable support, use the requested disease's terms and data, and avoid presenting unsupported analyses as successful results.

The milestone covers SLE, RA, MS, Sjögren's syndrome (SS), systemic sclerosis (SSc), type 1 diabetes (T1D), and inflammatory bowel disease (IBD).

## 2. Strict behavior

The platform uses a conservative policy for missing disease-specific inputs:

- **Full coverage:** required disease-specific inputs are present and the module can run without an incompatible fallback.
- **Partial coverage:** required inputs are present, but optional curated inputs or source support are missing. The module may run only when its output remains interpretable; missing inputs and limitations must be reported.
- **Unsupported:** a required curated input is absent, the disease data contract is invalid, or the module would need an SLE-only/default substitute. The module must return a structured blocked result and must not emit rankings or a successful-looking empty result.

No known disease may silently inherit SLE search terms, signatures, safety profiles, novelty assumptions, or therapy rubrics. Unknown disease IDs remain validation errors.

## 3. Shared coverage contract

Add a reusable coverage model/helper in the disease boundary. The public serialized shape is:

```json
{
  "coverage": {
    "disease_id": "ibd",
    "module": "screening",
    "level": "full | partial | unsupported",
    "status": "ready | limited_coverage | blocked",
    "curated_inputs": ["genes", "drugs", "pathways", "disease_terms"],
    "missing_inputs": [],
    "inferred_inputs": [],
    "warnings": [],
    "limitations": []
  }
}
```

Coverage helpers should:

- Verify the five standard disease data files: `profile.json`, `genes.json`, `drugs.json`, `pathways.json`, and `relationships.json`.
- Validate JSON shape and relationship references where appropriate.
- Inspect module-specific config fields and entity counts.
- Keep the existing `Disease.validate()` compatibility behavior while exposing richer coverage details.
- Provide a module readiness function that returns a coverage object rather than relying on scattered truthiness checks.

Coverage is metadata, not a replacement for source provenance. External-source results and retrieval status remain separate and are included alongside coverage.

## 4. Module rules

### Literature mining

Use the active disease's `PUBMED_QUERIES` and profile name. A known disease with no usable query configuration is unsupported; it must not use `DEFAULT_QUERIES` from SLE. Targeted candidate queries must use the active disease term.

### GWAS

Use the active disease's `GWAS_SEARCH_TERMS`. A known disease with no terms is unsupported. The legacy SLE term constants may remain only as an explicit compatibility fallback for unknown/legacy direct calls, but normal known-disease execution must never select them.

### Enrichment

Build gene lists, pathway matching, and exclusions from the active disease. The existing legacy helper name may remain as a compatibility alias, but output and documentation must be disease-neutral. No disease may be assigned a default SLE pathway rubric when its own data is unavailable.

### Virtual screening

Load the active disease's genes and drugs. Similarity, novelty, and approval interpretations must be scoped to the active disease rather than checking for literal SLE/lupus text. If the active disease lacks enough curated compound/target inputs for an interpretable screen, return `unsupported` with the missing inputs.

### Safety profiling

Use the active disease's symptoms and disease-specific risk configuration. Introduce a disease-neutral accessor for risk data while accepting the legacy configuration key during migration. Do not fall back to SLE symptom lists or SLE adverse-event profiles. If a requested disease has no usable safety curation, return a blocked result instead of zero/default scores.

### Therapy/CAR-T scoring

Use the active disease's `CAR_T_SCORES`. Missing or empty scoring data is unsupported; never substitute a hardcoded SLE rubric. Scores must carry disease ID and coverage metadata. The output must make clear that this is a computational therapy-prioritization heuristic, not efficacy evidence.

### Knowledge graph and IBD verification

All seven disease modules must have the five standard data files. Relationships must parse against the schema and reference existing nodes or the disease profile node as intended. IBD is explicitly included in graph smoke tests.

## 5. Output surfaces

Coverage metadata must be available in:

- Pipeline JSON results and reports.
- CLI summaries, including blocked/limited wording.
- FastAPI response models for affected modules.
- Dashboard module results and disease registry entries.
- A reusable disease/module coverage report containing entity counts, config readiness, curated inputs, inferred inputs, warnings, limitations, and a stable provenance fingerprint.

The dashboard must display badges such as `Full coverage`, `Limited coverage`, and `Unsupported for this disease`. Blocked modules display the reason and remediation (for example, run disease refresh or add curated scoring data) rather than an empty ranking table.

## 6. Tests

Add deterministic, parameterized smoke tests for all seven diseases. Tests must verify:

1. All five data files exist and load.
2. Relationships are schema-valid and reference valid entities.
3. Knowledge graphs build for every disease, including IBD.
4. Literature and GWAS select active disease terms.
5. Enrichment and screening use active disease entities and do not use SLE literals for other diseases.
6. Safety uses active disease symptoms and blocks when safety curation is unavailable.
7. CAR-T never silently falls back to SLE and blocks missing scoring data.
8. Every affected result includes coverage metadata.
9. Unsupported modules do not report `complete`, return rankings, or create misleading zero-filled output.
10. Existing SLE compatibility tests continue to pass.

Network calls must be mocked or fixture-backed. No test should require Redis, Celery, LLM credentials, or live external APIs.

## 7. Error and compatibility policy

- Invalid disease IDs raise the existing validation error.
- Valid but incomplete disease modules return structured blocked/limited coverage results where a module boundary allows a result object; they do not raise generic errors for expected data incompleteness.
- Low-level loaders may still raise for malformed required files, but the module/service boundary must convert expected incompleteness into coverage metadata.
- Existing exported function names and signatures should be preserved where practical. Add optional coverage fields rather than breaking callers.
- Legacy SLE names in docstrings and report labels should be removed or changed to disease-neutral wording in touched modules; unrelated historical documents are not part of this scope.

## 8. Explicit non-goals

- Do not invent new biomedical curation values for diseases that lack them.
- Do not refactor all pipeline modules into a common class hierarchy.
- Do not replace external source provenance with coverage metadata.
- Do not make all seven diseases equally complete by copying SLE data.
- Do not add live network dependencies to deterministic tests.

## 9. Success criteria

The milestone is complete when:

- Every disease can pass the core data/graph smoke workflow.
- Every requested module either produces disease-scoped output with visible coverage or explicitly reports that it is unsupported/limited.
- No known non-SLE run silently uses SLE terms, signatures, safety data, or therapy scoring.
- The dashboard and API expose coverage status.
- The coverage/provenance report explains what is curated, inferred, missing, and limited for each disease/module.
- Targeted and full test suites pass.
