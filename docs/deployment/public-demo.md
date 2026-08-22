# Public hosted demo (design)

**Status:** NOT deployed. v2.4.0 still identifies the public hosted demo as future work.

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

Implement `DEMO_MODE` in a dedicated P2-aligned issue; do not ship an unsafe open proxy.
