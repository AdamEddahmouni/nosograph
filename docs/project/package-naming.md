# Package naming strategy

| Era | Brand | CLI | Install | Import |
|-----|-------|-----|---------|--------|
| v0.x (public alpha) | NosoGraph | `nosograph` | `med-research` | `med_research` |
| Future major | NosoGraph | `nosograph` | planned `nosograph` | planned `nosograph` + shim |

Do not publish a package merely for branding. Confirm PyPI name availability before promising `pip install nosograph`.

**Unresolved compatibility:** v0.x keeps dual names (`nosograph` CLI; `med-research` / `med_research` install and import). ROADMAP lists a PyPI package rename before v1.0; older governance copy cited v3.0. The sunset version is not decided — do not treat either timeline as a committed cutoff.
