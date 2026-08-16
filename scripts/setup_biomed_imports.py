"""Download ontology artifacts and import MONDO, HPO, and HPOA into the biomed store.

Artifacts are cached under data/biomed/artifacts/ and imported into
data/biomedical.sqlite3 (or BIOMEDICAL_DB_PATH).

Optimized defaults:
  - Parallel artifact downloads
  - Slim MONDO/HPO imports (pipeline-focused, much faster)
  - Batched SQLite writes via ImportService.bulk_import_bundle

Usage:
    python scripts/setup_biomed_imports.py
    python scripts/setup_biomed_imports.py --from-fixtures
    python scripts/setup_biomed_imports.py --full
    python scripts/setup_biomed_imports.py --skip-download
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "data" / "biomed" / "artifacts"
FIXTURES = ROOT / "tests" / "fixtures" / "biomed"
MANIFEST_PATH = ROOT / "data" / "biomed" / "pinned-artifacts.json"

DOWNLOADS = {
    "mondo": {
        "filename": "mondo.json",
        "url": "https://github.com/monarch-initiative/mondo/releases/latest/download/mondo.json",
    },
    "hp": {
        "filename": "hp.json",
        "url": "https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download/hp.json",
    },
    "hpoa": {
        "filename": "phenotype.hpoa.tsv",
        "url": "http://purl.obolibrary.org/obo/hp/hpoa/phenotype.hpoa",
    },
}

FIXTURE_SOURCES = {
    "mondo": FIXTURES / "mondo" / "minimal.json",
    "hp": FIXTURES / "hpo" / "minimal.json",
    "hpoa": FIXTURES / "hpoa" / "minimal.tsv",
}


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _verify_artifact(resource: str, path: Path, manifest: dict, from_fixtures: bool) -> None:
    key = "fixture_checksum" if from_fixtures else "download_checksum"
    expected = manifest["artifacts"][resource][key]
    actual = _sha256(path)
    if actual != expected:
        raise SystemExit(
            f"Checksum mismatch for {resource} ({key}): expected {expected}, got {actual}"
        )
    print(f"  verified {path.name} ({actual})")


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  cached {dest.name} ({dest.stat().st_size // 1024} KB)")
        return

    def _report(block_num: int, block_size: int, total_size: int) -> None:
        if total_size <= 0:
            return
        done = block_num * block_size
        pct = min(100, int(done * 100 / total_size))
        print(f"\r  downloading {dest.name}: {pct}% ({done // 1024} KB)", end="", flush=True)

    print(f"  downloading {url}")
    urllib.request.urlretrieve(url, dest, reporthook=_report)  # noqa: S310
    print(f"\r  saved {dest.name} ({dest.stat().st_size // 1024} KB)          ")


def _download_all(resources: tuple[str, ...], from_fixtures: bool) -> None:
    if from_fixtures:
        return
    jobs = [(DOWNLOADS[r]["url"], ARTIFACTS / DOWNLOADS[r]["filename"]) for r in resources]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_download, url, dest): dest.name for url, dest in jobs}
        for future in as_completed(futures):
            future.result()


def _artifact_path(resource: str, from_fixtures: bool) -> Path:
    if from_fixtures:
        return FIXTURE_SOURCES[resource]
    return ARTIFACTS / DOWNLOADS[resource]["filename"]


def _run_cli(*args: str) -> int:
    cmd = [sys.executable, "-u", "-m", "med_research.cli", *args]
    print(f"\n>> {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and import MONDO/HPO/HPOA biomed artifacts")
    parser.add_argument("--from-fixtures", action="store_true", help="Use minimal test fixtures")
    parser.add_argument("--skip-download", action="store_true", help="Use cached artifacts only")
    parser.add_argument("--skip-init", action="store_true", help="Skip biomed init")
    parser.add_argument("--mondo-only", action="store_true", help="Import MONDO only")
    parser.add_argument("--full", action="store_true", help="Full ontology import (slower, includes hierarchy)")
    parser.add_argument("--no-activate", action="store_true", help="Import without activating snapshots")
    args = parser.parse_args()

    resources = ("mondo",) if args.mondo_only else ("mondo", "hp", "hpoa")
    slim_args = () if args.full else ("--slim",)
    activate_args = ("--no-activate",) if args.no_activate else ()
    manifest = _load_manifest()

    if not args.skip_init:
        if _run_cli("biomed", "init") != 0:
            return 1

    if not args.from_fixtures and not args.skip_download:
        print("Downloading artifacts (parallel)...")
        _download_all(resources, from_fixtures=False)

    for resource in resources:
        artifact = _artifact_path(resource, args.from_fixtures)
        if not artifact.is_file():
            print(f"Missing artifact: {artifact}")
            return 1
        _verify_artifact(resource, artifact, manifest, args.from_fixtures)
        import_args = ["biomed", "import", resource, "--artifact", str(artifact), *slim_args, *activate_args]
        if _run_cli(*import_args) != 0:
            return 1

    if _run_cli("biomed", "snapshots", "list") != 0:
        return 1

    print("\nBiomed import complete.")
    if not args.from_fixtures:
        print("  Re-run ID resolution: python scripts/resolve_registry_ids.py --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
