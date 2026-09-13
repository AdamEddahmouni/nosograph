---
description: Running the local NosoGraph dashboard — Condition Explorer, Evidence Workspace, corpus health, and comparison in one web interface.
---

# Web interface

Start `nosograph serve` (after sourcing `.env`) or Docker `full` profile and open http://127.0.0.1:8000. **This is not GitHub Pages.** The dashboard includes Condition Explorer, Evidence Workspace, corpus health, comparison, and module runners.

Title and branding: **NosoGraph**. Research-use notice appears in the footer. Satellite pages (PGx, matching, ADMET, spatial, agent) include a concise research/operator disclaimer.

The dashboard has a skip-to-content link, named logo, and `:focus-visible` styles (do not regress those). Playwright still needs to cover keyboard/screen-reader flows.

OpenAPI UI: `/api/docs` when enabled (follows `DEBUG` / `OPENAPI_ENABLED`).
