# Public hosted demo (design)

**Status:** NOT deployed. The FastAPI app is local; a hosted-demo design exists; GitHub Pages is documentation; no public demo URL is deployed.

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

## Next action

`DEMO_MODE` is implemented as a default-off opt-in on this branch. Do not deploy a public instance without a snapshot dataset, abuse budget, and operator authorization. Do not ship an unsafe open proxy.
