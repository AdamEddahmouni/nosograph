# ── Base ────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ── Dependencies ────────────────────────────────────────────────────────────
FROM base AS deps

COPY requirements-lock.txt pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install -r requirements-lock.txt

# ── Runtime ─────────────────────────────────────────────────────────────────
FROM deps AS runtime

COPY . .
RUN pip install --no-deps -e .

ARG DOCKER_SKIP_DISEASE_VALIDATE=0
RUN if [ "$DOCKER_SKIP_DISEASE_VALIDATE" != "1" ]; then \
      python -m med_research.cli disease validate --all --strict; \
    fi

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

ENTRYPOINT ["python", "-m", "med_research.cli"]
CMD ["serve", "--host", "0.0.0.0"]
