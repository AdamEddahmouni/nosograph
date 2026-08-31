---
title: Five-minute tutorial
description: Verify a local NosoGraph installation with the SLE reference module, then choose a research or developer path.
---

# Five-minute tutorial

This is a short verification workflow, not a full product manual. It uses the repository-backed SLE module and the canonical `nosograph` CLI. The commands can run without Redis or external source credentials.

## 1. Verify the CLI

From the repository root, confirm the command surface is available:

```bash
nosograph --help
```

## 2. Validate the SLE module

SLE is a reference and CI-validated module used here as a reproducible software example. Validation checks repository structure and readiness; it does not make a medical claim about SLE.

```bash
nosograph disease validate sle --strict
```

A successful run reports that the module passes strict validation. If it fails, inspect the output before continuing; do not treat a partial module as complete evidence.

## 3. Inspect coverage

```bash
nosograph disease coverage sle
```

Use the output to distinguish which fields are present from which are absent in the module. Coverage is not evidence of clinical effectiveness.

## 4. Choose the next surface

For a local dashboard workflow, start the stack using [Docker](docker.md), then open <http://localhost:8000>. The dashboard and Evidence Explorer are local interfaces; there is no public hosted demo.

Researchers can continue with [Evidence Explorer](../using/evidence-explorer.md), then [evidence tracing](../research/evidence-tracing.md), [provenance](../concepts/provenance.md), and [Compare](../using/compare.md).

Developers can continue with the [architecture overview](../architecture/overview.md), [API reference](../api-reference.md), and [local development](../developers/local.md).

## What success means

You have completed this tutorial when the CLI is available and `nosograph disease validate sle --strict` exits successfully. The tutorial does not require a hosted service, an LLM, source synchronization, or a populated Evidence Workspace dossier.
