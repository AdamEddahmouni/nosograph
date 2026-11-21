# Public hosted demo (design)

**Status:** implementation available; hosting requires owner setup. `DEMO_MODE`
is implemented with a single-container local profile; **no public URL is
deployed** until a hosted smoke test passes.

## Goals

`demo.nosograph.*` or GitHub Pages cannot host the FastAPI app; use a cheap VM/container later with explicit authorization.

## Architecture (snapshot-first)

- Read-only API + dashboard
- `DEMO_MODE=true`: disable mutating jobs, disable live paid APIs, disable LLM
- Fixture/snapshot dataset (ci_validated diseases), labeled snapshot date
- Rate limits + no unrestricted source fetch
- No secrets in the image; no PHI
- Abuse: reject pipeline fan-out; cap concurrency
- Shutdown: destroy VM / scale to zero

## Cost (order of magnitude)

Single small VM or one container: typically low tens of USD/month if always-on; near-zero if on-demand. Snapshot mode avoids Open Targets/PubMed flood.

## Preload

Showcase `sle`, `ra`, `ad` because they are CI-validated with richer fixtures—not because of popularity alone.

## Implementation status

- `DEMO_MODE` policy, Compare preview, and the fixture snapshot builder are
  implemented and tested (`src/med_research/web/demo_mode.py`,
  `src/med_research/web/demo_snapshot.py`, `scripts/build_demo_snapshot.py`).
- The dashboard renders a demo banner and filters the disease picker to
  supported snapshot diseases.
- One-container local profile: `Dockerfile.demo` + `docker-compose.demo.yml`.
- Browser smoke coverage: `tests/test_demo_browser.py`.
- Deployment runbook (Heroku primary, Azure Container Apps fallback):
  [deployment-demo](../deployment-demo.md).

## Next action

Run the manual [demo-deploy](../deployment-demo.md) workflow once a Heroku
account and repository secrets exist, then confirm `/api/health`, `/api/ready`,
and the Compare preview path on the public URL before sharing it.