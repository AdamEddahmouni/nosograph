# Evidence-to-Hypothesis Workspace

The Evidence Workspace turns a biomedical question into a provenance-backed dossier for research review. It searches the selected evidence sources, normalizes records, extracts deterministic claims, optionally enriches them with a validated LLM, ranks drugs and targets with explainable heuristics, checks knowledge-graph paths, and renders JSON/HTML exports.

> **Research use only.** The Workspace produces computational prioritization hypotheses. It does not provide medical advice, establish efficacy, or replace study-level scientific, experimental, or clinical review.

## Quick start

### CLI dossier

```bash
python -m med_research.cli workspace \
  --disease sle \
  --question "Find promising JAK/STAT interventions for SLE" \
  --sources pubmed,clinical_trials \
  --candidate-type both \
  --max-evidence 50 \
  --no-llm \
  --json dossier.json \
  --html dossier.html
```

The command prints the run ID and evidence/claim/candidate counts. `--json` and `--html` are optional output paths; the renderer uses the same dossier object for both formats.

### Dashboard

1. Start Redis and a Celery worker if asynchronous jobs are not already running:

   ```bash
   redis-server
   celery -A med_research.web.tasks.analysis_tasks worker --loglevel=info --concurrency=2
   celery -A med_research.web.tasks.analysis_tasks beat --loglevel=info
   ```

2. Start the API and dashboard:

   ```bash
   python -m med_research.cli serve --host 127.0.0.1 --port 8000
   ```

3. Open <http://127.0.0.1:8000/>.
4. Select a disease, enter a question, choose one or more sources, and submit.
5. Watch independent source chips and progress updates. The submit control remains disabled while the job is active, preventing duplicate submissions.
6. Expand a ranked candidate's **Why this ranked?** panel to inspect component scores, supporting/contradictory claims, citation IDs, confidence, and graph-path status.
7. Download the exact JSON dossier or open the generated HTML export.
8. Use history to reopen a saved run, compare two runs, inspect trends, or delete a run.
9. Expand **Researcher review** on any drug or target to add notes, tags, a pinned/rejected decision, a rationale, and what changed your mind. Use **Evidence history** to inspect that candidate across saved runs.
10. Sign in through the Workspace authentication controls. Local development accounts are configured with `LOCAL_AUTH_USERS`; production deployments should use `AUTH_MODE=proxy` behind an identity-aware reverse proxy. Notes and decisions are separated by the server-derived principal.
11. Open the **Evidence graph** to explore candidate → claim → citation/pathway relationships and your researcher-owned review decisions.
12. Download the **Review bundle** for a citation-ready ZIP containing Markdown review notes, a citations CSV, the exact dossier, review metadata, review events, and provenance.
13. Configure an email address or Slack Incoming Webhook in **Review reminders**. New unread reminders are delivered once per channel; failed attempts remain retryable and the latest delivery state is shown beside the settings.
14. Set optional alert thresholds for score drops, rank movement, and evidence-quality changes. A threshold of `0` disables metric-only alerts while preserving the existing new-evidence reminder behavior.
15. Enable **Weekly digest** to summarize the previous completed calendar week, then use **Preview digest** or **Send digest now** to inspect or manually deliver it.

The dashboard uses WebSocket progress when available and falls back to polling `/api/jobs/{job_id}`. `FAILURE`, `ERROR`, and `TIMEOUT` are terminal states: the result area shows a safe error message, `aria-busy` is cleared, and the form can be submitted again. Review reminders are refreshed when the dashboard loads, after a dossier completes, and every 60 seconds. Dashboard API calls use the HttpOnly session cookie and never send a researcher identity header. Alert polling and notification settings saves trigger in-app delivery attempts; email requires the server-side SMTP variables below, while Slack uses a researcher-owned HTTPS Incoming Webhook.

### Notification delivery configuration

Email delivery is opt-in per researcher and uses SMTP configured on the server. Set `ALERT_SMTP_HOST` and the optional `ALERT_SMTP_PORT`, `ALERT_SMTP_USERNAME`, `ALERT_SMTP_PASSWORD`, `ALERT_SMTP_FROM`, and `ALERT_SMTP_USE_TLS` variables. The API never returns Slack webhook URLs, and delivery errors are stored only as bounded operational status text. Slack delivery accepts only `https://hooks.slack.com/...` or `https://hooks.slack-gov.com/...` URLs.

Delivery is idempotent per alert, researcher, and channel. A successful attempt is not repeated; failed attempts are retried on the next alert poll or settings save. Marking an alert read stops future delivery attempts for that alert.

Notification settings also accept `score_drop_threshold` (0–100 score points), `rank_change_threshold` (0–100 positions), `evidence_quality_change_threshold` (0–1 average quality-score units), and `weekly_digest_enabled`. Positive thresholds can create a reminder even when no new evidence ID was added; the alert records the previous/current metric values and trigger reasons. A zero threshold disables that metric-only trigger and retains the baseline reminder for newly linked evidence.

The weekly digest uses the previous completed UTC calendar week (Monday 00:00 through the next Monday 00:00). It includes researcher-owned evidence additions attached to reminders, all currently unread reminders, and append-only review decisions recorded during that period. Each researcher can configure a weekday, local time, and IANA timezone. Celery Beat runs a minute-level dispatcher that queues due researcher deliveries; the per-researcher Celery task retries failed channels with exponential backoff up to five times. Deployments without Beat can call `POST /api/workspace/digest/send` from an external scheduler.

Digest messages include an optional HMAC-signed, eight-day review link when `WORKSPACE_REVIEW_LINK_SECRET` (or `API_KEY`) and `WORKSPACE_PUBLIC_URL` are configured. The link validates its signature and expiry before redirecting to the researcher's dashboard context. Digests with no new evidence, unresolved reminders, or changed decisions are suppressed.

## Request reference

The request body is the `ResearchRequest` model:

| Field | Type | Default | Description |
|---|---|---:|---|
| `disease_id` | string | `sle` | Must be a discovered disease module, such as `sle`, `ra`, `ms`, `ss`, `ssc`, `t1d`, or `ibd`. |
| `question` | string | required | Trimmed natural-language question, 2–500 characters. |
| `sources` | array/string | `pubmed`, `clinical_trials` | Non-empty supported source names. CLI accepts comma-separated text; API accepts a JSON array or compatible comma-separated string. |
| `date_from` | ISO date | `null` | Inclusive earliest source date. |
| `date_to` | ISO date | `null` | Inclusive latest source date. |
| `candidate_type` | `drugs`, `targets`, `both` | `both` | Select ranking output. |
| `max_evidence` | integer 1–200 | `50` | Maximum normalized evidence records retained. |
| `enable_llm` | boolean | `true` | Optional enrichment. Deterministic extraction still runs when LLM enrichment is unavailable. |

Current supported Workspace sources are `pubmed`, `clinical_trials`, `gwas`, and `fda_labels`; the dashboard defaults to PubMed and ClinicalTrials.gov. Source adapters are isolated: one source may fail while other source results and warnings remain in the dossier.

## Dossier contents

`EvidenceDossier` is the canonical result. JSON uses the Pydantic model's JSON-safe representation.

- `schema_version`, `run_id`, `started_at`, and `completed_at`.
- `request`, including disease, question, source selection, filters, candidate type, evidence limit, and LLM setting.
- `search_terms`, generated from the question, disease profile, and disease-specific search configuration.
- `source_statuses`, one item per requested source, with `ok`, `warning`, `error`, or `skipped` status, record count, query terms, retrieval mode, warning, and retrieval timestamp.
- `evidence`, including stable evidence IDs, source-native IDs such as PMIDs/NCTs, canonical URL, snippet, dates, evidence type, quality tier/score/rationale, query context, and retrieval time.
- `claims`, each linked to one or more evidence IDs and citations. Relationships include `supports`, `contradicts`, `associated_with`, `targets`, and `participates_in`.
- `drug_rankings` and `target_rankings`, with score, confidence band, component scores, explanation text, supporting/contradicting claim IDs, citation IDs, and graph explanation IDs.
- `graph_explanations`, with `found` or `no_path_found` status, real path node/relationship labels, and a reason when no path exists.
- `warnings` and `limitations`.
- `manifest.provenance`, including a stable fingerprint over normalized inputs, disease, selected sources, filters, cache/live mode, scoring context, and source counts. Run IDs and timestamps are intentionally excluded from the stable fingerprint.
- `disclaimer`, which is present in JSON and HTML.

Scores are prioritization heuristics based on support, contradiction, recency, evidence quality, and related signals. They are not probabilities of benefit or safety.

## CLI options

Run `python -m med_research.cli workspace --help` for the live parser. The current options are:

```text
--question / -q QUESTION       Required natural-language question
--disease / -d DISEASE         Disease ID; default sle
--sources SOURCES              Comma-separated sources
--date-from DATE               Earliest date, YYYY-MM-DD
--date-to DATE                 Latest date, YYYY-MM-DD
--candidate-type TYPE          drugs, targets, or both
--max-evidence INTEGER         1–200 records
--no-llm                       Skip optional LLM enrichment
--json PATH                    Write complete JSON dossier
--html PATH                    Write self-contained HTML dossier
```

A live run can access external services through source adapters. For reproducible local development, inject fixture adapters through `run_workspace()` rather than relying on network responses.

## API reference

### Submit a job

`POST /api/jobs/workspace`

Example request:

```json
{
  "disease_id": "ra",
  "question": "Which TNF interventions merit investigation?",
  "sources": ["pubmed", "clinical_trials"],
  "candidate_type": "both",
  "max_evidence": 25,
  "enable_llm": false
}
```

Response:

```json
{
  "job_id": "celery-task-id",
  "status": "PENDING",
  "module": "workspace"
}
```

The endpoint validates the request with `ResearchRequest`, serializes dates and source arrays as JSON, and queues `task_run_workspace`.

### Track progress

- `GET /api/jobs/{job_id}` returns `PENDING`, `STARTED`, `PROGRESS`, `SUCCESS`, or `FAILURE`. Progress responses include a `progress` object; failure responses include `error`; successful responses include `result` with `dossier` and generated `html`.
- `WS /api/jobs/{job_id}/ws` sends state changes every 500 ms, including `PROGRESS`, `SUCCESS`, `FAILURE`, `ERROR`, and a server-generated `TIMEOUT` after 10 minutes.

### Saved runs

The task stores completed dossiers in the SQLite database configured by `WORKSPACE_DB_PATH` (by default, `data/evidence_workspace.sqlite3` relative to the project layout).

| Method | Endpoint | Parameters | Purpose |
|---|---|---|---|
| `GET` | `/api/workspace/alerts` | authenticated session/proxy principal, optional `unread_only`, `limit`, `offset` | List evidence-driven review reminders owned by the researcher and dispatch configured pending notifications. |
| `POST` | `/api/workspace/alerts/{alert_id}/read` | authenticated session/proxy principal | Mark one owned reminder as read. |
| `GET` | `/api/workspace/notifications` | authenticated session/proxy principal | Load owned notification settings and latest email/Slack delivery state; webhook secrets are masked. |
| `PUT` | `/api/workspace/notifications` | authenticated session/proxy principal and JSON settings | Save notification settings, thresholds, weekly digest opt-in/schedule, and attempt pending delivery. Slack URLs must be HTTPS Slack webhook URLs. |
| `GET` | `/api/workspace/digest` | authenticated session/proxy principal | Preview the previous completed calendar week's new evidence, unresolved reminders, and changed decisions. |
| `POST` | `/api/workspace/digest/send` | authenticated session/proxy principal, optional `force=true` | Send the configured digest immediately; scheduled delivery uses Celery Beat. |
| `GET` | `/api/workspace/digest/delivery-history` | authenticated session/proxy principal, optional `limit` | List digest attempts, retry counts, and bounded failure details. |
| `GET` | `/api/workspace/digest/review` | signed `token` | Validate an expiring review link and redirect to the dashboard. |
| `GET` | `/api/workspace/runs` | `limit` 1–200, `offset` ≥ 0 | List run summaries. |
| `GET` | `/api/workspace/runs/{run_id}` | — | Load request, dossier, generated HTML, and status. |
| `DELETE` | `/api/workspace/runs/{run_id}` | — | Delete a saved run and its review history. |
| `GET` | `/api/workspace/runs/{run_id}/reviews` | authenticated session/proxy principal | Load the requesting researcher's candidate notes, tags, decisions, and provenance. |
| `GET` | `/api/workspace/runs/{run_id}/review-events` | authenticated session/proxy principal | Load the requesting researcher's append-only decision history. |
| `GET` | `/api/workspace/runs/{run_id}/graph` | authenticated session/proxy principal | Return graph nodes/edges for candidates, claims, citations, pathways, knowledge-graph paths, and owned decisions. |
| `PUT` | `/api/workspace/runs/{run_id}/reviews` | JSON candidate review + authenticated session/proxy principal | Save an owned pin/reject decision, rationale, notes, tags, and changed-mind record. |
| `GET` | `/api/workspace/runs/{run_id}/review-bundle` | — | Download citation-ready Markdown, CSV, dossier, review, review-event, and provenance files as a ZIP. |
| `GET` | `/api/workspace/candidate-history` | `candidate_id`, `candidate_type`, optional `disease_id` | Track one candidate's scores, ranks, evidence additions/removals, and reviews across runs. |
| `GET` | `/api/workspace/compare` | `left`, `right` run IDs | Compare ranking, evidence, and review changes. |
| `GET` | `/api/workspace/trends` | optional repeated `run_ids`, `limit` 1–100 | Return run summaries, drug/target series, and candidate evidence changes. |

Missing run IDs return HTTP 404 for load, delete, and compare operations.

## Export behavior and safety

- CLI JSON is generated by `dossier_to_json()` and preserves the complete dossier, including native IDs and provenance.
- CLI HTML is generated by `render_html()` and is self-contained, print-friendly, and includes the research-only disclaimer.
- Dashboard JSON downloads the stored dossier object rather than recomputing ranking scores.
- Dashboard HTML opens the generated server-side report rather than rebuilding it in JavaScript.
- Review bundles preserve the exact dossier and stable provenance fingerprint, while `review.md` and `citations.csv` provide a citation-ready human review artifact.
- Dynamic text is HTML-escaped. Citation links are only emitted for HTTP(S) URLs; unsupported schemes are rendered as text.
- Treat downloaded dossiers as research artifacts. They can contain source excerpts and should be handled according to the sensitivity and terms of the source data.

## Failure and limitation semantics

- A source adapter failure is recorded in that source's `SourceStatus` and in `warnings`; other adapters continue.
- No configured adapter produces a `skipped` status and warning.
- Missing LLM credentials, unavailable optional clients, timeouts, quota failures, or invalid LLM output do not discard deterministic claims. The manifest records the LLM status and warnings.
- A missing knowledge-graph node or absent path produces an explicit `no_path_found` explanation. The Workspace never fabricates graph edges from text claims.
- A disease with incomplete required configuration is rejected before evidence work with an `incomplete disease configuration` error. Inspect it with:

  ```bash
  python -m med_research.cli disease validate <disease-id> --strict
  ```

## Deterministic tests

The focused Workspace tests are fixture-backed and do not require Redis, Celery workers, external APIs, or LLM credentials:

```bash
python -m pytest tests/test_evidence_workspace*.py -q
python -m pytest tests/test_evidence_workspace_browser.py -q
```

The browser fixture covers success, duplicate-submit prevention, WebSocket-to-polling fallback, and terminal `FAILURE`, `ERROR`, and `TIMEOUT` recovery, including escaped error messages and restored accessible form state.
