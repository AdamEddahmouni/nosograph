# ── Base ────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ── Dependencies ────────────────────────────────────────────────────────────
FROM base AS deps

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ── Runtime ─────────────────────────────────────────────────────────────────
FROM deps AS runtime

COPY . .

# Build the knowledge graph (pre-compute graph_data.json for the web app)
RUN python knowledge_graph/build_graph.py --export

EXPOSE 8000 8080

# Default: start the web API server
ENTRYPOINT ["python", "-m", "uvicorn", "web_api.main:app"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
