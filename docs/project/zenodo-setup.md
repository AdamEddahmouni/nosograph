# Zenodo / DOI setup (maintainer)

No DOI exists yet. Do not display a DOI badge until Zenodo mints one.

1. Log in to [Zenodo](https://zenodo.org) with the GitHub account that can admin `AdamEddahmouni/nosograph`.
2. GitHub → Settings → Integrations (or Zenodo GitHub page) → enable the `nosograph` repository.
3. Create the v0.1.0 GitHub Release only after enabling the repository so Zenodo receives the release event.
4. Verify the deposit: title NosoGraph, version, license Apache-2.0, metadata from CITATION.cff / codemeta.json.
5. Copy the **concept DOI** (all versions) and **version DOI** into CITATION.cff `identifiers:` and the README badge.
6. Re-run `python scripts/check_public_metadata.py`.

This archival is for research software discovery, not a claim of clinical validation.
