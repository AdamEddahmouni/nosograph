# Releasing NosoGraph

This document describes how to cut a new NosoGraph release. The Python package still publishes as `med-research` during the compatibility period.

## Versioning

NosoGraph follows [Semantic Versioning](https://semver.org/) on a pre-1.0 public-alpha line:

- **Patch** (`0.1.1`): backward-compatible fixes, documentation, and dependency updates
- **Minor** (`0.2.0`): features or intentional breaking CLI, API, package, or data-contract changes, with migration notes
- **Stable** (`1.0.0`): supported CLI, API, package naming, and data contracts have explicit compatibility commitments

The historical v2.1.0–v2.4.0 tags predate this deliberate public-alpha baseline. They remain immutable audit records but do not define the current compatibility line.

The canonical version lives in [pyproject.toml](pyproject.toml) (`project.version`).

## Release checklist

1. **Update [CHANGELOG.md](CHANGELOG.md)** with a dated entry under `## [X.Y.Z]` including:
   - Summary of user-visible changes
   - Verification commands run (`make lint`, `make test-offline`, etc.)

2. **Bump version** in `pyproject.toml`, `CITATION.cff`, `codemeta.json`, `src/med_research/__init__.py`, and `docs/generated/public-status.yaml`.
3. **Run `python scripts/check_public_metadata.py`.**

4. **Run verification locally:**

   ```bash
   make lint
   make test-offline
   make lock-check
   python -m med_research.cli disease validate sle --strict
   ```

5. **Commit** the version and changelog updates through a pull request to `master`.

6. **Tag and push:**

   ```bash
   git tag -a vX.Y.Z -m "NosoGraph vX.Y.Z"
   git push origin master --tags
   ```

7. **Create a GitHub Release** from the tag:
   - Title: `vX.Y.Z`
   - Body: copy the CHANGELOG section for that version
   - Attach build artifacts if distributing Docker images

## Docker images (optional)

For container releases, rebuild and tag after the git tag:

```bash
docker build -t med-research:X.Y.Z .
docker tag med-research:X.Y.Z med-research:latest
```

Document any required environment variables in [docs/deployment.md](docs/deployment.md).

## PyPI (not automated)

PyPI publishing is not configured in CI. If distributing via PyPI in the future, add a `publish` workflow triggered on `v*` tags after `make lock-check` and the test suite pass.

## Security releases

For security fixes, follow [SECURITY.md](SECURITY.md): coordinate privately, land the fix on `main`, tag a patch release, and publish a GitHub Security Advisory.
