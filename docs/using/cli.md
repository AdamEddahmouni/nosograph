---
title: CLI
description: Command-line reference for validating registries, building evidence, and running NosoGraph pipelines locally.
---

# CLI

Canonical command: `nosograph` (legacy alias `med-research`).

```text
nosograph --help
```

Task-oriented groups:

| Task | Examples |
|------|----------|
| Explore / list | `diseases`, `modules` |
| Validate | `disease validate`, `disease validate-batch`, `disease coverage`, `disease corpus-status` |
| Sources | `biomed sync`, `biomed init` |
| Analyze | pipeline subcommands (`kg`, `repurpose`, …) |
| Web | `serve` |

Use `nosograph <command> --help` for flags. Compatibility notes stay below the primary flow: Python import remains `med_research`.
