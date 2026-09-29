# Public demo deployment runbook

**Status:** implementation available; hosting requires owner setup. No public
URL is live until a hosted smoke test passes.

The public demo is a single immutable container running the NosoGraph
dashboard + API in `DEMO_MODE` against a fixture-built biomedical snapshot.
It needs **no Redis, no Celery, no Postgres, no worker, and no paid API keys**
for the flagship read-only surfaces.

- Image definition: [`Dockerfile.demo`](https://github.com/AdamEddahmouni/nosograph/blob/master/Dockerfile.demo)
- Local profile: [`docker-compose.demo.yml`](https://github.com/AdamEddahmouni/nosograph/blob/master/docker-compose.demo.yml)
- Design and boundary: [public demo design](superpowers/specs/2026-09-03-public-demo-design.md)

## What the demo exposes

Read-only, snapshot-backed surfaces:

- Home and research-only context pages
- Condition Explorer (search, detail, hierarchy, claims) limited to the
  snapshot's supported diseases
- Evidence Explorer (claim detail, evidence filters, provenance chain)
- Non-persisting Compare preview for 2–5 supported conditions, with
  deterministic JSON/Markdown exports
- Snapshot/source metadata and readiness

Blocked by design (HTTP `403` with `demo_read_only`, WebSocket rejected):
job submission/streaming, workspace writes, admin/cache mutation, live
external connectors, LLM extraction, and persisted comparison runs.

## Prerequisite gate (before any deployment command)

1. Create or sign in to a Heroku account.
2. Confirm the GitHub Student Developer Pack Heroku offer is active (if using
   the student credit).
3. Create the Heroku app (`heroku apps:create <app-name>`).
4. Configure the app config vars:
   - `DEBUG=false`
   - `DEMO_MODE=true`
   - `DEMO_SNAPSHOT_PATH=/app/data/demo/biomedical.sqlite3`
   - `DEMO_SNAPSHOT_MANIFEST=/app/data/demo/biomedical.manifest.json`
   - `CORS_ORIGINS=https://<app-name>.herokuapp.com` (never `*`)
   - `API_KEY=<strong random secret>` (operator secret; never shown to users)
   - `DASHBOARD_CSP_MODE=enforce`
   - `RATE_LIMIT_REQUESTS=60`, `RATE_LIMIT_WINDOW=60`
5. Add `HEROKU_API_KEY` and `HEROKU_APP_NAME` as GitHub repository secrets —
   only as secrets, never in the repository.

## Local demo (no hosting)

```bash
docker build -f Dockerfile.demo -t nosograph-demo .
docker compose -f docker-compose.demo.yml up --build
# open http://localhost:8000
docker compose -f docker-compose.demo.yml down
```

Verify `/api/health` (liveness), `/api/ready` (returns `demo.demo_mode: true`
with the snapshot version), and that a `POST /api/jobs` returns `403
demo_read_only`.

## Heroku deployment

The image is built locally and pushed to the Heroku Container Registry. Use
the manual workflow (requires the two secrets above):

1. GitHub → Actions → **Public demo deploy (manual)** → *Run workflow*.
2. The workflow builds `Dockerfile.demo`, pushes to
   `registry.heroku.com/<app>/web`, releases the `web` process, and smoke
   checks `/api/health`, `/api/ready`, and the Compare preview endpoint.

Manual alternative:

```bash
heroku container:login
docker build -f Dockerfile.demo -t registry.heroku.com/<app>/web .
docker push registry.heroku.com/<app>/web
heroku container:release web --app <app>
```

### Cost boundary (Heroku)

- One **Eco web dyno** for the read-only app. No Redis, no Postgres, no
  worker, no paid API keys.
- Recheck the Student Developer Pack offer and dyno pricing at deployment
  time; provider offers change.
- Shutdown: `heroku apps:destroy --app <app> --confirm <app>` (destroys the
  app and stops billing) or scale to zero with
  `heroku ps:scale web=0 --app <app>`.

## Azure Container Apps (fallback)

If Heroku is unavailable, deploy the same image to Azure Container Apps:

1. `az containerapp up --name nosograph-demo --resource-group <rg> \
   --image nosograph-demo:latest --ingress external --target-port 8000`
   (or push to an Azure Container Registry first).
2. Set the same env vars as the Heroku step, with `CORS_ORIGINS` pointing at
   the public ingress URL and `API_KEY` as an operator secret.
3. Configure **scale-to-zero** (minimum replicas = 0) and one replica max.
4. Cost: see the current Container Apps free grant and per-request pricing;
   monitor credits in the Azure portal. Explicit shutdown:
   `az containerapp delete --name nosograph-demo --resource-group <rg>`.

## Snapshot refresh

The demo dataset is immutable and built at image build time from checked-in
fixtures via `scripts/build_demo_snapshot.py`. To refresh:

1. Update `tests/fixtures/biomed/` (mondo/hpo/hpoa) and re-run
   `python scripts/build_demo_snapshot.py --output /tmp/biomedical.sqlite3`.
2. Verify `tests/web/test_demo_mode.py` and
   `tests/web/test_demo_compare_preview.py` still pass with the new fixtures.
3. Rebuild and redeploy the image; the readiness endpoint exposes the new
   `snapshot_version`.

## Ongoing operations

- **Cost monitoring:** check the provider dashboard weekly; the demo should
  stay near zero cost when idle (scale-to-zero or destroy when unused).
- **Secrets:** `API_KEY` and any provider tokens live only in the platform
  config/secret store; never in the image or repository.
- **Incident response:** the demo is read-only and stateless; recovery is
  rebuild-and-redeploy of the immutable image.