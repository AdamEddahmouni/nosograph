---
description: What NosoGraph curation tiers L0 through L3 and the reference/CI-validated sets mean, and why tier labels matter for interpretation.
---

# Curation tiers

| Tier | Meaning |
|------|--------|
| L0 | Scaffold gaps (missing KG JSON) |
| L1 | KG present, config incomplete |
| L2 | Strict validation pass (pipeline-ready) |
| L3 | Curated literature consensus (hand-curated gene lists; study accessions not recorded) |
| Reference / CI-validated | Deeper maintained sets |

v0.2.1 public snapshot: **88 L2** and **2 L3** are an **n=500 alphabetical sample**, not full-corpus counts. Consensus membership is **23**. Reference **6**, CI-validated **8**. Full playbook: [disease-curation.md](../disease-curation.md). Counts and regeneration: [coverage](../data/coverage.md).

**What L3 means:** membership in `CURATED_CONSENSUS_DISEASES` and a hand-curated gene list. It is **not** a computed GEO differential-expression analysis. Each gene entry records `source`, `effect_direction`, and `effect_size`, but `study_accessions` is explicitly empty because no study-level accessions were captured. Treat L3 as expert-curated literature consensus, not as reproducible expression evidence.
