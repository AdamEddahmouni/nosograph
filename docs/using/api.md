---
title: API
description: Compatibility entry point for the canonical NosoGraph API and operations reference.
---

# API

The full, maintained API and operations guide is the canonical [API reference](../api-reference.md). It covers the local server command, base URLs, authentication boundaries, versioned biomedical endpoints, Compare V2, Evidence Workspace jobs, environment settings, and response models.

This route remains available for existing links. The primary navigation points to the canonical reference rather than maintaining a second endpoint catalog here.

## Quick orientation

- Dashboard: `http://127.0.0.1:8000/`
- Health: `GET /api/health`
- OpenAPI JSON: `GET /api/openapi.json` when OpenAPI is enabled; the current imported app may disable this route
- Versioned biomedical routes: `/api/v1`

Continue to the [API reference](../api-reference.md) for verified invocation examples and current router details.
