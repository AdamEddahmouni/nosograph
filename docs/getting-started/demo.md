---
title: Demo
description: How to evaluate NosoGraph locally and the status of a public hosted demo.
---

# Demo

There is **no public hosted demo** in v0.2.1. The FastAPI app is local; a hosted-demo design exists; GitHub Pages is documentation; no public demo URL is deployed.

## Local evaluation

Use [Docker](docker.md) or [installation](install.md). Fixture-backed and snapshot paths are used in CI; live connectors may call public APIs if you enable them.

Label anything fixture-backed as a snapshot. Do not imply live coverage.

## Hosted demo (design)

See [public hosted demo](../deployment/public-demo.md) for the snapshot-first design. A `nosograph demo` command is deferred so it does not collide with the P2 Evidence Explorer work. Track it as a follow-up.
