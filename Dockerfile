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

EXPOSE 8080

# Default: show help for the unified CLI
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
