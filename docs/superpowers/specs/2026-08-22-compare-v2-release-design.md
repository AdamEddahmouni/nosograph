# Compare V2 v0.2.0 release design

## Objective

Ship Milestone 1 as NosoGraph v0.2.0 through the protected GitHub workflow, with the audited Compare V2 implementation complete, reproducible, accessible, and traceable from browser interactions to persisted evidence.

## Release shape

Use one milestone pull request from the existing Compare branch into `master`. This keeps the implementation, remediation, release notes, and canonical version metadata reviewable as one coherent compatibility change. Required checks must pass on the pull request before merge. The signed `v0.2.0` tag and GitHub release are created from the resulting merge commit, not from the feature branch.

Direct pushes to `master`, force pushes, bypassed hooks, and tags on pre-merge commits are out of scope.

## Result compatibility

Compare result persistence needs a contract boundary independent of the user-selected inputs. Add a stable result-schema version to the persisted comparison payload and to the research-run fingerprint inputs. A request executed against an older result contract must create a new deterministic run instead of replaying a payload that lacks condition labels, entity labels, or evidence links. Historical runs remain readable with conservative fallbacks; they are not mutated or recomputed against newer snapshots.

The public Compare algorithm remains `nosograph-compare-v2` version `2.0.0` because v0.2.0 is its first public product release. Result-schema evolution and biomedical comparison-semantics evolution are versioned separately.

## Evidence traceability

When positive and negated assertions coexist, the state remains `PRESENT` and the structured conflict warning remains authoritative. The entity row must preserve both positive and negated claim identifiers in deterministic order so Evidence Explorer can inspect every assertion responsible for the conflict. Non-conflicting rows continue to expose the exact claims that establish their state.

## Product and accessibility remediation

The shared, distinct, and missing-data panels receive semantic headings and accessible section names. Comparison tables use scoped headers, and numeric coverage columns use tabular numerals. Existing tab keyboard behavior, responsive layout, explicit `KNOWN_ABSENT` versus `NOT_RECORDED` presentation, and export links remain unchanged.

## Test strategy

Each behavioral fix starts with a focused failing regression test:

- A result-schema change must produce a different deterministic run fingerprint while identical contract/input combinations replay the same run.
- A conflicting entity must expose both its positive and negated claims.
- Static dashboard checks must enforce panel headings, scoped table headers, and numeric styling.

Add one Playwright scenario that loads the dashboard from the actual FastAPI application and completes a comparison through the live HTTP endpoint. The browser may use a deterministic temporary biomedical repository, but it must not intercept or synthesize the Compare request or response. Existing mocked browser tests remain valuable for detailed product-state and download assertions.

Verification consists of focused Compare/API/export/browser tests, the complete offline test gate, Ruff lint and format checks, import-boundary checks, public metadata checks, documentation build, lock verification, and the hosted required checks after push and after merge.

## Release metadata

Update canonical current-version surfaces to v0.2.0: package metadata, runtime version, CodeMeta, citation metadata, README and documentation status pages, roadmap, changelog, and a dedicated release-notes document. Preserve historical v0.1.0 release records and its version DOI. Until Zenodo creates a v0.2.0 record, use the all-versions concept DOI where citation metadata requires a DOI and do not invent a version DOI.

Release notes must describe the five comparison dimensions, deterministic two-to-five-condition cohorts, missingness semantics, curation warnings, Evidence Explorer drill-down, JSON/Markdown exports, compatibility expectations, known limitations, and exact verification commands.

## Failure handling

If local verification fails, stop the release sequence and fix the root cause before committing. If pull-request checks fail, inspect and repair them on the same branch. If merge succeeds but post-merge checks fail, do not tag. If tag signing or GitHub release creation fails, leave the verified merge intact and report the release as incomplete rather than publishing an unsigned or mismatched artifact.
