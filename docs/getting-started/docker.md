---
title: Docker
description: Run the NosoGraph dashboard with Docker Compose using the full profile.
---

# Docker

```bash
git clone https://github.com/AdamEddahmouni/nosograph.git
cd nosograph
cp .env.example .env
docker compose --profile full up --build
```

Dashboard: http://localhost:8000

The `web`, `worker`, and `beat` services are behind Compose profile **`full`**. `docker compose up` without that profile will not start the dashboard.

Local evaluation builds pass `DOCKER_SKIP_DISEASE_VALIDATE=1` so image build does not run strict validation across 10,407 modules (that gate is expected to fail on scaffolds). This does **not** disable API keys or production `DEBUG=false` rules.

Image name remains `med-research:latest` for compatibility.

Production hardening: [deployment](../developers/deployment.md)
