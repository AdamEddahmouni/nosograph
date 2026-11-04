---
description: Validating disease modules with nosograph validate commands, and what the strict validation gate does and does not cover.
---

# Validation

```bash
nosograph disease validate sle --strict
nosograph disease validate sle --strict --require-evidence
nosograph disease validate-batch --tier L2 --strict
nosograph disease validate-batch --tier reference --strict --require-evidence
nosograph disease corpus-status
```

`disease validate --all --strict` is **not** a merge gate for the full 10k scaffold registry. Hosted CI validates the original curated eight plus reference-tier checks as documented in release audits.

## Structural validity vs evidence density

`--strict` and `--require-evidence` answer different questions and are reported
separately:

| Contract | Question |
|---|---|
| structural validity (`--strict`) | Can the module be loaded and used by the pipeline? |
| evidence density (`--require-evidence`) | Do its gene, drug, and pathway records carry at least one resolvable identifier? |

A record is **evidenced** only when its `references` list contains a recognised
scheme such as `PMID`, `DOI`, `CLINVAR`, `NCT`, or `CHEMBL`. The record's own
`id` is not counted: an entity identifier says what the record is about, not
what supports the claim. Free-text notes are recorded as `UNCLASSIFIED` and do
not count.

A module passes the evidence gate when at least **80%**
(`EVIDENCE_DENSITY_TARGET`) of its gene, drug, and pathway records are
evidenced. Zero records cannot pass. The aggregate gate requires every measured
module to pass; a structurally valid module can still fail evidence.

Single-module `validate` prints both results. `validate-batch` exposes
`summary.structurally_valid`, `summary.evidenced`, `summary.evidence_density`,
and `summary.evidence_gate_passed`; each entry carries `passed`,
`structurally_valid`, `evidenced`, and its `evidence` block. Use
`--no-evidence` to skip assessment for a structural-only run; the report then
marks evidence as not assessed rather than pretending it passed.

## Reference identifier resolution

Evidence density counts identifiers; this separate check asks whether they
still resolve. It scans every PMID, DOI, and ClinVar ID declared by the
reference and CI-validated modules:

```bash
python scripts/check_reference_identifiers.py --tier both
```

PMIDs and ClinVar IDs are batched through NCBI E-utilities; DOIs use the DOI
Handle API. The command exits `1` if any identifier is dead, or if an upstream
failure prevents a definitive answer after retries. `--json PATH` writes the
per-identifier report with every disease/collection/record location.The hosted `lint` job runs this check, so a dead identifier is merge-blocking.
A separate `Reference identifier audit` workflow also runs it every Monday at
04:00 UTC and on manual dispatch, uploading the JSON report as an artifact.

The check is intentionally online-only and is not part of `make ci-local`,
which must remain offline. Use `make check-references` locally when network
access is available.

## Scoped registry validation

The full registry mixes deeply curated modules with generated Open Targets scaffolds. Validating every module is still useful, but it must not be confused with a curation signal: scaffolds are **expected** to fail strict checks (for example an empty `SYMPTOMS` block), so a non-zero result from the whole corpus is honest, not a regression.

`disease validate --all` accepts the same tier filters as `validate-batch`:

```bash
nosograph disease validate --all --tier ci_validated --strict
nosograph disease validate --all --tier reference --strict
nosograph disease validate --all --tier L2 --strict
```

| `--tier` | Slice |
|---|---|
| `all` | Every discoverable module (default for `validate --all`) |
| `ci_validated` | The eight modules gated on every CI run (`sle`, `ra`, `ms`, `ss`, `ssc`, `t1d`, `ibd`, `ad`) |
| `reference` | The diverse reference set used in tests and docs |
| `L2` / `L3` | Modules whose cached corpus status reports that readiness tier |

`validate-batch` defaults to `--tier reference`, so it stays fast by default.

## Deterministic sampling

Sampling makes the full registry measurable without walking all 10k+ modules in one run:

```bash
nosograph disease validate-batch --tier all --sample 500 --seed 0 --strict \
  --output data/reports/validation_sample.json
```

- Selection is **deterministic**: candidates are ordered by `sha256("{seed}:{disease_id}")` and the first `N` are taken. The same tier/explicit slice, seed, and `N` always select the same modules, across processes, machines, and Python versions. It is a fixed pseudo-random sample, not a fresh random draw per run.
- A different `--seed` selects a different sample.
- `--sample` larger than the available pool means "all candidates"; it is not an error.
- `--sample 0` is legal and validates nothing (useful for wiring and dry runs).
- `--limit` caps the number of modules validated **after** sampling.
- Sampling never promotes, re-tiers, or rewrites a module. It only chooses which modules this run reads.

## Structured output

Both commands can emit a machine-readable report.

| Command | Flag | Default path |
|---|---|---|
| `validate-batch` | `--output PATH` | `data/reports/validation_batch_report.json` |
| `validate --all` | `--json PATH` | none (only written when asked) |

The report contains:

- `summary.total`, `summary.passed`, `summary.failed`, `summary.pass_rate`
- `summary.structurally_valid`, `summary.evidenced`, `summary.evidence_density`, `summary.evidence_gate_passed`
- `summary.sampled`, `summary.sample_size`, `summary.sample_seed`
- `summary.excluded_blocked` — non-disease slugs excluded before validation
- `summary.failure_classes` — counts per failure class (`SCHEMA`, `PROVENANCE`, `MISSING_REQUIRED_DATA`, …)
- `summary.failure_groups` — failing checks grouped by field name, highest count first
- `entries` — per-module `passed` and `failures[]` detail
- `failure_class_definitions` — what each class means

Blocked non-disease slugs (`positive_regulation_of_ovulation`, `sensory_perception_of_sound`, and the test-owned `zz_scaffold_test`) are excluded from the target universe and counted in `excluded_blocked`; they are never reported as validation failures.

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | Every selected module passed |
| `1` | A required contract failed: structural validation under `--strict`, or the evidence-density gate under `--require-evidence` |
| `2` | Usage error, such as `validate` with neither a disease id nor `--all` |

Exit-code semantics are identical whether you use `validate`, `validate --all --json`, or `validate-batch`. `validate-batch` without `--strict` still exits `0` and reports failures in the JSON body, preserving its pre-sampling behaviour.

## Strictness is unchanged

Scoping and sampling change **what is read**, not **what passes**:

- Individual curated modules still gate on `disease validate <id> --strict`.
- Evidence density is additive: `--strict` keeps its existing structural meaning, and `--require-evidence` separately enforces the 80% provenance target.
- A scaffold that fails strict validation still fails; nothing is promoted to L2/L3 by sampling it.
- `NOT_RECORDED` and `KNOWN_ABSENT` remain distinct; validation does not convert missing evidence into a pass.
- Curation tiers (`scaffold`, `L0`–`L3`, `ci_validated`, `blocked`) keep their existing definitions in `med_research.diseases.curation_tiers`.

For the corpus-wide picture without validation cost, use `nosograph disease corpus-status` and see [coverage](../data/coverage.md).
