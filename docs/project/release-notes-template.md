# Release notes template

Use for GitHub Releases. Do not rewrite historical tags.

```markdown
# NosoGraph vX.Y.Z

**Maturity:** Public Alpha — research use only; not production clinical software.

## What NosoGraph is
Disease Intelligence. Connected. Open-source research software for connecting disease knowledge, evidence, and provenance across biomedical sources.

## What changed
- …

## Why this release matters
- …

## Major capabilities
- …

## How to try it
See README Quick start (Docker `full` profile or `nosograph` CLI).

## Breaking changes and migration
Omit this section when there are none. Otherwise:
- State exactly what changed and who is affected — an `/api/v1` route, a CLI flag, a
  configuration file, an environment variable, or a serialized data format.
- Give the migration step with a before/after example.
- Link the migration or upgrade guide when one exists.

## Security notes
Omit when there are none. Describe impact and the required upgrade action; never publish
exploit instructions or embargoed details before coordinated disclosure (see SECURITY.md).

## Validation
Link the release audit. Do not show all-green if a gate is informational/failing.

## Known limitations
- Public alpha; package name `med-research`; no hosted demo unless shipped.

## Compatibility
- CLI `nosograph`; import `med_research`.

## Full changelog
Link CHANGELOG.md section.
```
