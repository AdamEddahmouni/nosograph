# Provenance Model

## Schema

Provenance metadata follows **schema version 1.0** (`pipeline/provenance.py`).

## Fields

| Field | Description |
|-------|-------------|
| `schema_version` | Provenance schema ID |
| `run_id` | Optional run identifier |
| `disease_id` | Disease context |
| `module` | Pipeline module name |
| `package_version` | Installed package version |
| `sources` | Sorted source identifiers |
| `query` | Retrieval query string |
| `filters` | Applied filters |
| `cache_or_live` | Data freshness mode |
| `model` | LLM model if used |
| `scoring` | Scoring parameters |
| `fingerprint` | SHA-256 hash (20 hex chars) of stable inputs |
| `generated_at` | UTC ISO-8601 timestamp |

## Fingerprint algorithm

1. Normalize inputs to JSON-safe structures
2. Strip volatile keys (`run_id`, timestamps, …)
3. Sort keys, compact JSON serialize
4. SHA-256, truncate to 20 hex characters

## Usage

Every major pipeline module and evidence adapter should attach provenance to outputs for reproducibility audits.

## Separation from coverage

**Provenance** answers: *what sources and inputs produced this output?*  
**Coverage** answers: *did this disease have enough curated inputs for this module?*

A run can have complete provenance while reporting `limited_coverage`.

## Package version note

`package_version()` reads distribution metadata for `med-research`. After NosoGraph rebrand, display name may differ while import path remains `med_research`.

## Limitations

- Fingerprints are deterministic for identical inputs but do not capture non-deterministic LLM outputs unless model + prompt are in stable inputs
- External API content can change between runs (documented as live retrieval)
