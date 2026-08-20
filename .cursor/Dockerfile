FROM python:3.12-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
        python3-venv \
        python3-dev \
        build-essential \
        redis-server \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash ubuntu

USER ubuntu
