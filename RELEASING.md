# Releasing NosoGraph

This document describes how to cut a new NosoGraph release. The Python package still publishes as `med-research` during the compatibility period.

## Versioning

We follow [Semantic Versioning](https://semver.org/) on the `2.x` line while the public API stabilizes:

- **Patch** (`2.0.1`): bug fixes, documentation, dependency updates with no API change
- **Minor** (`2.1.0`): backward-compatible features, new disease scaffolds, new optional endpoints
- **Major** (`3.0.0`): breaking CLI, API, or data contract changes

The canonical version lives in [pyproject.toml](pyproject.toml) (`project.version`).

## Release checklist

1. **Update [CHANGELOG.md](CHANGELOG.md)** with a dated entry under `## [X.Y.Z]` including:
   - Summary of user-visible changes
   - Verification commands run (`make lint`, `make test-offline`, etc.)

2. **Bump version** in `pyproject.toml` to match the CHANGELOG heading.

3. **Run verification locally:**

   ```bash
   make lint
   make test-offline
   make lock-check
   python -m med_research.cli disease validate sle --strict
   ```

4. **Commit** the version and changelog updates on `master`.

5. **Tag and push:**

   ```bash
   git tag -a vX.Y.Z -m "med-research vX.Y.Z"
   git push origin master --tags
   ```

6. **Create a GitHub Release** from the tag:
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
