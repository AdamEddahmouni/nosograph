# Phenopacket export fixtures

All files in this directory are **synthetic**. The identifiers are placeholders
(`MONDO:0000001`, `HP:0000001`-`HP:0000003`) chosen to exercise the export
contract; they are **not** real MONDO or HPO associations and must never be
cited as evidence.

- `valid_input.json` — accepted. Deliberately unsorted phenotypes, one
  contradictory assertion, one missing `hpo_label`/`frequency`, and one source
  reference without `version`/`checksum`, so the determinism, ordering and
  explicit-missingness paths all run.
- `invalid_missing_provenance.json` — rejected. Disease-level evidence with an
  empty `sources` list is not exportable.

These fixtures are read-only inputs; nothing in the test suite writes here.
