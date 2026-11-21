# Local source reconciliation and completion handoff

This branch contains an inspectable NosoVolution planning corpus, but it cannot authoritatively reconcile offline drives, unpushed branches, earlier generated art files, or ZIP-only material. Do not claim that everything from the source bundles is already in GitHub.

## Required read-only inventory

Find every relevant local source: NosoGraph clones/worktrees/stashes/remotes, NosoVolution Revision 1–5 archives, selected `60490.png` artwork, full 43-column Revision 5 source CSV, 144-experiment source JSON and brand/video assets. Record paths, byte sizes, SHA-256 hashes, copyright/license, provenance and exact version. Inspect newer files before copying.

## Copy rules

- Preserve existing IDs and content, not just titles.
- Compare SHA-256 and source/canonical data semantics before replacement.
- Never overwrite newer or modified repository files; stage a separate `docs/nosovolution/source-import-*` branch or working tree and open a PR.
- The original 43-column CSV should replace only the clearly labeled *source CSV* path; keep the 17-column atlas export and its provenance.
- Add the original `ALL_144_EXPERIMENTS.json` as a separate canonical source and compare against the derived index.
- Do not upload the user-supplied third-party reference video `60504.mp4` or embed it via ZIP unless redistribution rights are documented.
- Pre-publication image assets must be reviewed by the user and checked for third-party rights, AI-generated scientific inaccuracies, originality and private information.
- Avoid committing nested duplicate ZIP archives; source files and checksum manifests are preferable.
- Do not rename the Python distribution/import paths, CLI aliases or repository on this branch.
- Run JSON schema validation, count unique initiative IDs, confirm DAG acyclicity, check references and avoid broken Markdown links.

## Verification report required

A source-coverage matrix with `source_file`, `local_sha256`, `github_path`, `github_blob_sha`, `uploaded`, `reason_omitted`, `rights_reviewed`, `tested`, and `scientific_maturity` columns. No false completion claims or destructive cleanup.

## Director review

Present the changes and missing artifacts before requesting merge or official publication. User approval is required for public-facing claims, clinical interpretation, spending, security-sensitive connector use, and destructive operations.
