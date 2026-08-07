# Evidence Workspace Dashboard Completion Design

**Date:** 2026-08-06
**Status:** Implemented (historical design record)
**Scope:** Fixture-backed dashboard completion with live adapters preserved

## Goal

Complete the Evidence-to-Hypothesis Workspace as the platform's central workflow: a researcher asks a biomedical question, receives independently reported source outcomes, reviews provenance-backed claims and explainable drug/target rankings, follows graph explanations, and exports a cited JSON/HTML dossier.

## Implemented behavior

- Reliable dashboard submission lifecycle and duplicate-submit prevention.
- Fixture-backed browser and end-to-end verification with no network requirement.
- Independent PubMed and ClinicalTrials.gov source status display.
- “Why this ranked?” explanations using existing ranking components and claim IDs.
- Supporting and contradictory evidence display with citation links.
- Visible run provenance, reproducibility fingerprint, cache/live mode, warnings, and limitations.
- Exact JSON and generated HTML export behavior.
- Escaped dynamic dashboard content and safe citation URLs.
- Disease-aware request payloads and result labels from the selected disease.
- Terminal recovery for `FAILURE`, `ERROR`, and `TIMEOUT`, including re-enabled form controls and cleared `aria-busy` state.

## Scope and non-goals

In scope:

- Reliable dashboard state and duplicate-submit prevention.
- Independent source outcome and failure display.
- Explainable rankings using existing dossier fields.
- Provenance/fingerprint visibility and reproducible exports.
- Saved-run history, compare, and trend controls.
- Fixture-backed browser verification.

Not in scope:

- Removing or replacing live source adapters.
- Requiring Redis, Celery workers, API credentials, or external services in the default test suite.
- Adding a new frontend framework or database migration.
- Changing the ranking algorithm or evidence schema for presentation purposes.
- Implementing authentication or multi-user ownership for saved run history.

## Architecture

The existing `evidence_workspace` contracts and orchestration remain the computation boundary. Python fixture tests inject source adapters and an optional NetworkX graph. The dashboard consumes the JSON-safe task payload returned by `/api/jobs/workspace`; it does not recompute scores or fetch live evidence directly.

A submission moves through `idle → submitting → running → success|failure`. `FAILURE`, `ERROR`, and `TIMEOUT` are terminal failures. The submit control remains disabled from request start until the WebSocket or HTTP polling fallback reaches a terminal state, then becomes available again.

## UI behavior

The result view includes:

- Summary counts and independent status chips for requested sources.
- Run ID, selected disease, question, sources, candidate mode, fingerprint, retrieval mode, warnings, and limitations.
- Candidate cards for drugs and targets with score, confidence band, support/contradiction counts, and expandable explanations.
- Claim sections grouped by supporting and contradicting evidence, with citation metadata and safe links.
- Graph path status, including explicit no-path reasons.
- JSON download and generated HTML open controls.
- Saved-run history, comparison, and trend views.

All API-provided text inserted into HTML is escaped. Citation links are emitted only for HTTP(S) URLs. Failure and timeout messages are handled as untrusted content where applicable.

## Accessibility and motion

The form exposes busy/progress state through ARIA attributes and visible status text. Keyboard users can submit and expand details without pointer-only behavior. Reduced-motion CSS disables non-essential transitions/animations when the user requests reduced motion.

## Testing

The focused suite is network-free:

```bash
python -m pytest tests/test_evidence_workspace*.py -q
python -m pytest tests/test_evidence_workspace_browser.py -q
```

Browser tests cover successful submission, duplicate prevention, WebSocket-to-polling fallback, source/result rendering, exports, and terminal `FAILURE`, `ERROR`, and `TIMEOUT` recovery. The failure tests assert re-enabled controls, cleared `aria-busy`, preserved terminal messages, and escaped malicious error text.
