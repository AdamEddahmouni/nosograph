# Zenodo / DOI setup (maintainer)

No DOI exists yet. Do not display a DOI badge until Zenodo mints one.

1. Log in to [Zenodo](https://zenodo.org) with the GitHub account that can admin `AdamEddahmouni/nosograph`.
2. GitHub → Settings → Integrations (or Zenodo GitHub page) → enable the `nosograph` repository.
3. Create a GitHub Release (already true for v2.3.0) or cut the next release after enabling.
4. Verify the deposit: title NosoGraph, version, license Apache-2.0, metadata from CITATION.cff / codemeta.json.
5. Copy the **concept DOI** (all versions) and **version DOI** into CITATION.cff `identifiers:` and the README badge.
6. Re-run `python scripts/check_public_metadata.py`.

This archival is for research software discovery, not a claim of clinical validation.
