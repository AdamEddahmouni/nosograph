# Evidence Explorer

**Status:** PUBLIC_ALPHA · included in v0.1.0

Evidence Explorer is a read-only research surface that shows **why NosoGraph holds a claim** — from the claim itself through supporting, contradictory, and inconclusive evidence, provenance, and original source metadata.

## What is a claim?

A **claim** is a structured biomedical statement in the knowledge graph, such as:

- a condition **associated with** a gene or phenotype
- a treatment **indicated for** a condition
- a mechanism **linked to** a pathway

Claims are **associations**, not proof of causation. The exact relationship type appears on each claim row.

## How do I open Evidence Explorer?

1. Open the NosoGraph dashboard (`/`).
2. Click **Evidence** in the top navigation, or **Evidence Explorer** in the hero quick actions.
3. Or open a condition in **Conditions**, pick a claim, and click **Open in Evidence Explorer**.

**Deep link:** `?claim_id={uuid}#evidence-explorer` — shareable URLs reload the same claim.

## Evidence directions

| Label | Meaning |
|-------|---------|
| **SUPPORTS** | Evidence in the dataset supports the claim |
| **CONTRADICTS** | Evidence disagrees with the claim |
| **INCONCLUSIVE** | Mixed or insufficient evidence in the dataset |
| **UNASSERTED** | No directional evidence recorded |

Supporting evidence does **not** mean contradictory evidence is absent — check each group separately.

## Evidence quality badges

Quality dimensions describe **context**, not a single confidence score. Missing metadata shows as **unknown** — absence is not treated as low quality.

| Dimension | Examples |
|-----------|----------|
| **Species** | human, animal, in vitro, computational, unknown |
| **Study design** | RCT, cohort, review, unknown |
| **Origin** | curated, imported, generated, unknown |
| **Human review** | none, community, expert, unknown |

**UNKNOWN** means the field was not recorded or could not be derived conservatively from stored metadata.

## Provenance

The provenance timeline shows how data reached the graph:

```text
source snapshot → normalized record → ingestion → graph claim
```

Incomplete chains are shown honestly — NosoGraph does not invent missing stages.

## Original sources

Each evidence row links to source metadata (PubMed ID, trial registry, ontology record, etc.). Use **View source** when a URL or external identifier is available.

## Filters

Filter evidence by direction, species context, and sort order. Filter state is reflected in the URL so refresh and back/forward navigation preserve your view.

## API export

Use the **JSON/API** link on a loaded claim to open the underlying `/api/v1/claims/{id}` response, or call the API directly. The evidence list is paginated:

`GET /api/v1/claims/{claim_id}/evidence?limit=50&offset=0`

## Research disclaimer

NosoGraph is for **research use only**. Associations are not causation. Not medical advice.

Architecture details: [Evidence Explorer architecture](../architecture/evidence-explorer.md).
