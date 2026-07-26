# ── Base ────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ── Dependencies ────────────────────────────────────────────────────────────
FROM base AS deps

COPY requirements.txt pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install -e ".[all]"

# ── Runtime ─────────────────────────────────────────────────────────────────
FROM deps AS runtime

COPY . .

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["python", "-m", "med_research.cli"]
CMD ["serve", "--host", "0.0.0.0"]
