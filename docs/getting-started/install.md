---
title: Installation
description: Install NosoGraph locally via Docker, pip/editable install, or contributor setup.
---

# Installation

Product name: **NosoGraph**. Canonical CLI: **`nosograph`**. Package/import: **`med-research` / `med_research`** (compatibility).

Supported Python: 3.11 and 3.12.

## Docker evaluation

See [Docker](docker.md).

## Editable install

```bash
git clone https://github.com/AdamEddahmouni/nosograph.git
cd nosograph
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e .
cp .env.example .env
nosograph --help
```

`pip install nosograph` is **not** available yet. Do not assume a PyPI rename has happened.

## Contributor install

```bash
make venv-sync
make ci-local
```

Redis is required for async dashboard jobs and the integration test tier, not for pure CLI unit tests.

Details: [local development](../developers/local.md) and [CONTRIBUTING.md](https://github.com/AdamEddahmouni/nosograph/blob/master/CONTRIBUTING.md).
