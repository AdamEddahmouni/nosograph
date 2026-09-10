# Public Read-Only Demo Design

**Date:** 2026-09-03
**Status:** Approved design; implementation not started
**Release target:** the next release after v0.2.1, depending on deployment readiness

## Context

NosoGraph v0.2.1 has the core Evidence Explorer and Compare workflows, but no
public hosted instance. The current Docker Compose stack is designed for
self-hosting and includes a web process, Celery workers, Celery Beat, Redis,
mutable workspace history, and live-capable analysis routes. Exposing that full
stack anonymously would create unnecessary cost and an unsafe public job runner.

The first demo should prove NosoGraph's evidence-native product story using a
fixed research snapshot. It must be cloud-hosted because the project owner
cannot run a home machine continuously. Cost and operational overhead should be
kept low, with GitHub Education benefits used where eligible.

## Goals

1. Provide an anonymous, cloud-hosted demonstration of:
   - Condition Explorer
   - Evidence Explorer
   - multi-condition Compare
   - source and snapshot metadata
   - research-only product context
2. Make the demo safe to expose publicly:
   - no anonymous mutation
   - no live paid or rate-sensitive source fetches
   - no LLM calls
   - no unrestricted Celery job submission
3. Make the dataset and output reproducible:
   - immutable snapshot-backed data
   - visible snapshot date and provenance
   - deterministic comparison preview
4. Keep the deployment portable across Heroku and Azure Container Apps.

## Non-goals

- Public hosting of the full dashboard or all analysis modules.
- Anonymous Evidence Workspace submissions, reviews, alerts, or saved runs.
- Live Open Targets, PubMed, ClinicalTrials.gov, or other external fetches.
- LLM extraction or agent execution.
- Persistent user accounts, billing, or PHI.
- A production SLA or a promise of complete biomedical coverage.

## Product boundary

The demo exposes a small, allow-listed product surface:

- Home and About pages.
- Atlas navigation limited to CI-validated/reference snapshot diseases.
- Condition search, condition detail, hierarchy, and claims.
- Evidence Explorer claim detail, evidence filters, related claims, and
  provenance chain.
- Non-persisting Compare preview for two to five supported conditions.
- Read-only snapshot/source metadata and export of the preview result.

The demo does not expose job submission, job status/streaming, workspace writes,
admin lifecycle operations, notification delivery, live connectors, LLM
extraction, or cache administration. Existing routes should remain available
for normal self-hosted mode; the restriction applies only when
`DEMO_MODE=true`.

## Architecture

### Demo mode boundary

Add a centrally configured `DEMO_MODE` setting and enforce it before route
handlers run. The policy must be deny-by-default for mutation-capable
operations, rather than relying only on the presence of an API key.

In demo mode:

- All job submission and streaming routes are unavailable.
- Workspace submission, review, notification, alert, and delete operations are
  unavailable.
- Disease admin prune/restore operations and cache administration are
  unavailable.
- Live external source and LLM operations are unavailable.
- The existing production requirement for `API_KEY` when `DEBUG=false` remains
  in effect; the key is an operator secret and is never sent to public users.
- Public reads use same-origin CORS settings and remain subject to rate limits.

The implementation should return a stable, documented `403` policy response
with a machine-readable `demo_read_only` error code for blocked API operations.
This must be consistent across all blocked route families and tested as part of
the public contract.

### Compare preview

The current canonical Compare V2 `POST` path creates a persisted research run.
That path must not be used by the public demo. Add an explicit non-persisting
preview service/route for demo use, such as
`POST /api/v1/nosograph/comparisons/preview`, which:

- validates two to five condition CURIEs and selected dimensions;
- reads only the immutable biomedical snapshot;
- returns the same comparison fields and research disclaimer, with
  `run_id: null` and `preview: true` instead of a persisted run identifier;
- does not create a `ResearchRun` or modify SQLite;
- supports deterministic JSON and Markdown preview exports by repeating the
  same validated request; exports do not require a saved run identifier.

The preview response gets a dedicated response model rather than weakening the
persisted `NosoGraphCompareV2ResultView` contract. The existing persisted
Compare API remains unchanged outside demo mode.


### Snapshot dataset

Build the demo image with a fixed biomedical SQLite snapshot generated from
checked-in MONDO/HPO/HPOA fixtures and the supported CI-validated/reference
disease modules. The exact snapshot version/date must be exposed through the
system metadata and dashboard UI.

The runtime should not require writable application data. If a framework or
library needs temporary files, use an explicitly isolated temporary directory
and ensure those writes cannot alter the source snapshot or become user data.
No live source connector may be used to fill missing data at request time.

### Deployment shape

The application should run as one web container for the first demo. Celery,
Celery Beat, Redis, external databases, and paid API credentials are not
required by the flagship read-only path.

Deployment order:

1. Implement and test the portable demo mode locally using a dedicated
   production-like Compose profile.
2. Deploy the immutable image to Heroku first if the GitHub Student Developer
   Pack offer is active.
3. Keep Azure Container Apps as the fallback or later deployment target.

Heroku is preferred for the first deployment because a single Eco web dyno is
lower overhead than configuring an Azure environment and is suitable for an
immutable, read-only snapshot. Azure remains attractive for more control and
scale: Azure for Students currently advertises a USD 100 credit for 12 months,
and Container Apps advertises monthly free grants for compute and requests.
Provider offers and prices must be rechecked at deployment time.

The container must honor the platform-injected `PORT`, set `DEBUG=false`,
configure the public `CORS_ORIGINS`, set a strong operator `API_KEY`, and use
strict CSP/security headers. Deployment documentation must include a cost
monitoring and shutdown procedure.

## Error handling and safety

- Blocked demo operations return a stable policy response without revealing
  implementation details.
- Missing snapshot data produces an explicit unavailable/insufficient-data
  response, never a live fallback.
- Startup fails clearly when the immutable snapshot is missing or invalid.
- `/api/health` remains a liveness check; `/api/ready` reports demo readiness
  without requiring Celery or Redis when demo mode is enabled.
- Rate-limit responses remain bounded and user-readable.
- All demo responses retain research-only disclaimers and curation/missingness
  labels.
- No secrets, tokens, PHI, or mutable local databases are baked into the image.

## Testing and acceptance criteria

### Unit and API tests

- `DEMO_MODE` configuration is parsed and exposed correctly.
- Every blocked route family is covered, including jobs, workspace writes,
  admin mutation, alerts/notifications, live extraction, and cache mutation.
- Allowed Condition Explorer, Evidence Explorer, source, snapshot, and system
  reads continue to work.
- Compare preview returns the canonical result semantics without creating a
  research run or changing SQLite.
- Preview export output is deterministic and contains the snapshot metadata and
  disclaimer.
- No-network tests prove that demo requests do not invoke live connectors.
- Startup/readiness behavior is covered with Redis and Celery unavailable.

### Browser and deployment tests

- A browser smoke test opens the public home page, searches for a supported
  condition, opens a claim, filters evidence, opens provenance, runs a
  two-condition preview, and downloads/inspects an export.
- The UI visibly identifies demo mode, fixed snapshot date, curation tier, and
  research-only status.
- The image starts with production settings and the injected `PORT`.
- A demo profile can be built without secrets and without network access after
  dependencies are installed.
- Heroku deployment smoke checks `/api/health`, `/api/ready`, the home page,
  and the preview path.

### Definition of done

The first demo is ready when:

1. An anonymous user can complete the flagship Explorer → evidence → provenance
   and Compare preview workflows.
2. All public writes and live calls are blocked and covered by tests.
3. The snapshot is immutable, labeled, reproducible, and validated at startup.
4. The demo runs as one low-cost cloud container without Redis or Celery.
5. Deployment, cost limits, shutdown, and snapshot-refresh instructions are
   documented.
6. The offline suite, relevant API tests, and browser smoke tests pass.

