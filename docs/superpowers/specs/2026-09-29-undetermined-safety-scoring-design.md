# Undetermined Safety Scoring Design

## Problem

When a catalog drug has no explicit adverse-event profile and no recognized safety tier, `load_profiles()` currently merges disease-level defaults into that drug. The defaults can set `severity_burden=0` and `chronic_use_safety=10`, producing a deceptively high numeric score (e.g. 9.2/10) even though the drug is in `undetermined_risk` and has no drug-specific evidence.

## Goals

- Do not present an undetermined drug as safe or risky based on fabricated/default numeric values.
- Preserve visibility of every catalog drug and make missing evidence explicit.
- Preserve numeric behavior for profiles with a determinate safety tier.
- Exclude unscored drugs from all numeric summaries and safest/riskiest rankings.
- Keep generated disease profile files unchanged in this implementation.

## Behavior

1. `load_profiles()` continues to materialize a profile for every catalog drug.
2. A drug listed in the active disease's `drug_safety_tiers.undetermined_risk` is marked `score_status="insufficient_evidence"`.
3. Its dimension scores and `composite_safety_score` are `None`; no fallback numeric rating is substituted. Its descriptive adverse-event fields may remain empty when the source data is absent. Provenance and limitations remain attached.
4. Drugs with a determinate tier preserve the existing score calculation and receive `score_status="scored"`.
5. Result contracts and consumers represent nullable scores/status accurately. Summary averages and extrema use only scored results. Include scored and unscored counts. If no scored drugs are available, average/min/max score values are null and rank names are empty; do not use zero as an implied score.
6. CLI, HTML report, and web/UI output display an explicit “Insufficient evidence” status instead of formatting null as a number. Such entries are excluded from ranked best/worst lists.

## Data flow

The disease payload already stores `drug_safety_tiers`; the profile loader will derive the undetermined drug IDs/labels from that disease-local metadata and tag matching catalog records. The scorer will branch on the explicit status before calculating any numeric dimensions. The status then travels with the score result through serialization and the existing service/report boundaries.

No profile generation, risk-rule expansion, evidence harvesting, or disease-specific scientific reclassification is included. In particular, this change prevents false precision; it does not claim that remaining heuristic scores have been clinically validated.

## Testing

- Unit-test status detection for undetermined catalog drugs and confirm all numeric outputs are null.
- Confirm determinate profiles continue to receive numeric scores and `scored` status.
- Confirm summaries exclude unscored entries, count them separately, and return null extrema/average when nothing is scoreable.
- Confirm service, CLI/HTML, and web-facing serialization represent insufficient evidence without formatting a numeric score.
- Run the focused adverse-event, service, report, and API tests plus relevant type checks.

## Scope constraints

- Do not edit or regenerate disease `config.py` or `data/adverse_events.json` files.
- Do not change classification heuristics or assign any conservative substitute score.
- Do not commit or deploy as part of this task.
