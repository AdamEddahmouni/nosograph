"""Verify pinned biomedical artifact checksums and active store snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "biomed" / "pinned-artifacts.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_artifact_files(manifest: dict, *, from_fixtures: bool) -> list[str]:
    errors: list[str] = []
    for resource, spec in manifest["artifacts"].items():
        if from_fixtures:
            artifact = ROOT / spec["fixture_path"]
        else:
            artifact = ROOT / "data" / "biomed" / "artifacts" / spec["download_filename"]
        if not artifact.is_file():
            errors.append(f"{resource}: missing artifact {artifact}")
            continue
        actual = _sha256(artifact)
        expected = spec["checksum"]
        if actual != expected:
            errors.append(f"{resource}: checksum mismatch (expected {expected}, got {actual})")
    return errors


def verify_active_snapshots(manifest: dict) -> list[str]:
    from med_research.biomed.repository import BiomedicalRepository
    from med_research.web.config import BIOMEDICAL_DB_PATH

    if not BIOMEDICAL_DB_PATH.is_file():
        return ["biomedical store not initialized"]

    repository = BiomedicalRepository(BIOMEDICAL_DB_PATH)
    errors: list[str] = []
    for resource, spec in manifest["artifacts"].items():
        snapshot = repository.get_active_snapshot(resource)
        if snapshot is None:
            errors.append(f"{resource}: no active snapshot in store")
            continue
        if snapshot.checksum != spec["checksum"]:
            errors.append(
                f"{resource}: active snapshot checksum mismatch "
                f"(expected {spec['checksum']}, got {snapshot.checksum})"
            )
    legacy = repository.get_active_snapshot("legacy-curated")
    if legacy is None:
        errors.append("legacy-curated: no active snapshot in store")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify pinned biomed artifacts and store snapshots")
    parser.add_argument("--from-fixtures", action="store_true", help="Verify fixture files only")
    parser.add_argument("--check-store", action="store_true", help="Verify active DB snapshots")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH, help="Pinned artifact manifest")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    errors = verify_artifact_files(manifest, from_fixtures=args.from_fixtures)
    if args.check_store:
        errors.extend(verify_active_snapshots(manifest))

    if errors:
        print("Biomed verification failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    scope = "fixture artifacts"
    if args.check_store:
        scope = "fixture artifacts and active snapshots"
    print(f"Biomed verification passed ({scope}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
