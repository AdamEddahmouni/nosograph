# Symptom Coverage Reporting Design

**Status:** Approved for spec; awaiting user review before implementation.

## Goal

Make corpus reports distinguish populated symptom data from empty symptom lists whose cause is unresolved identifier mapping, unavailable local sources, or no annotations in available sources.

## Context

`build_corpus_status()` currently reports `symptom_count`, an aggregate `symptoms_populated`, and (when requested) `symptom_source` set to `config` or `none`. The latter conflates several different reasons an empty `SYMPTOMS` list might occur. Existing non-empty lists may be manually curated or auto-harvested, so reporting must not label all of them “curated.”

The supported local phenotype sources are the active HPOA snapshot in `BIOMEDICAL_DB_PATH` and Open Targets' `disease_phenotype` parquet table. The reporting change must distinguish data presence and local source state, not claim evidence quality. It must not call `DiseaseIdResolver.resolve_entry()` because that path can use a live Open Targets API fallback.

## Design

Add a per-disease `symptom_coverage` field with exactly these states:

- `populated`: the disease module has one or more symptom entries. This does not claim they were manually curated.
- `awaiting_curation`: at least one available local source has phenotype annotations for a resolved disease identifier, but the module's `SYMPTOMS` list is empty.
- `no_source_annotations`: identifiers resolve and at least one relevant local source is available, but available source lookups return no phenotype annotations for the disease.
- `source_unavailable`: no supported local phenotype source needed for lookup is available; report generation must remain offline and must not invoke live APIs to fill the gap.
- `identifier_unresolved`: the local registry/resolver cannot provide a MONDO or EFO identifier with which to query supported phenotype sources.

Keep existing `symptom_count`, `symptoms_populated`, and optional `symptom_source` values (`config` / `none`) unchanged for backwards compatibility. Add an aggregate `symptom_coverage` mapping with a count for every state (including zero counts). Include blocked or failed disease entries in the existing blocked/error reporting; do not count them as one of the five symptom coverage states unless symptom coverage could actually be assessed.

Source annotations are looked up read-only from the local snapshots. Do not write config files or alter disease readiness tiers. Do not contact Open Targets' API during corpus-status reporting. Use identifiers already present in the local disease registry, normalizing their local MONDO/EFO spelling without attempting an online resolution. If both identifiers are absent, use `identifier_unresolved`. For rows with identifiers, a source counts as available only when the HPOA database has an active HPOA snapshot and its required local tables, or the Open Targets bulk store has a readable `disease_phenotype` table. A source lookup failure must not be misreported as “no annotations”: treat that source as unusable, then classify from the remaining available source(s). If no sources remain usable, use `source_unavailable`.

## Data flow

1. Load the module symptom list and preserve existing `symptom_count` behavior.
2. If it is non-empty, classify as `populated` without evaluating source coverage.
3. For an empty list, read its MONDO/EFO identifiers directly from the local registry. If neither is present, classify as `identifier_unresolved`.
4. Check the active local HPOA database and the local Open Targets `disease_phenotype` parquet table independently; do not use broad `OpenTargetsBulkStore.is_available()` because that checks unrelated parquet tables.
5. Query each usable source read-only using its supported disease identifier (HPOA via MONDO; Open Targets via its phenotype-table ID). If any source returns labels, classify as `awaiting_curation`; if at least one source is usable and all return no labels, classify as `no_source_annotations`; if no source is usable, classify as `source_unavailable`.
6. Emit the per-disease state and increment the matching aggregate count.

## Error handling and compatibility

- Preserve existing tier computation, config gap values, and output fields.
- If an optional source's schema/query fails, do not fail the whole corpus report; log at debug level and consider that source unusable for this row.
- Preserve `include_symptom_source` semantics and legacy `symptom_source` strings.
- Source checks and queries must be read-only and local; never modify module config or source data.
- The report adds the new state field and aggregate mapping without changing existing consumers' field names.

## Testing

Use temporary disease/config fixtures and monkeypatched local-source availability/query helpers to cover each state:

1. non-empty symptom list → `populated`;
2. empty symptoms, resolved identifier, available source with labels → `awaiting_curation`;
3. empty symptoms, resolved identifier, available source with no rows → `no_source_annotations`;
4. empty symptoms, resolved identifier, no usable local sources → `source_unavailable`;
5. empty symptoms and unresolved disease identifiers → `identifier_unresolved`.

Also assert that aggregate counts include every state, legacy fields remain unchanged, blocked module handling remains unchanged, and no config writes or network calls occur. Run `tests/test_corpus_status.py`, relevant symptom-harvester tests, `make typecheck`, and the offline test tier.

## Scope boundaries

This work changes reporting only. It does not populate symptoms, alter `SYMPTOMS`, change tier rules, rewrite existing adverse-event files, create a new symptom source, or redesign the harvester.
