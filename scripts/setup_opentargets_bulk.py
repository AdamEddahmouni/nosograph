"""Download and index Open Targets parquet subsets for local bulk querying.

Stores data under data/bulk/opentargets/{version}/ and writes
data/bulk/manifest.json.

Usage:
    python scripts/setup_opentargets_bulk.py
    python scripts/setup_opentargets_bulk.py --subset --version 25.03
    python scripts/setup_opentargets_bulk.py --from-fixtures
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import urlopen, urlretrieve

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from med_research.diseases.bulk_store import DEFAULT_VERSION, manifest_path

ROOT = Path(__file__).resolve().parents[1]
BULK_ROOT = ROOT / "data" / "bulk" / "opentargets"
FIXTURES = ROOT / "tests" / "fixtures" / "opentargets"

# Open Targets Platform FTP base (25.03+)
OT_FTP_BASE = "https://ftp.ebi.ac.uk/pub/databases/opentargets/platform/{version}/output"

TABLES = (
    "disease",
    "target",
    "association_overall_direct",
    "known_drug",
    "disease_phenotype",
)

_PARQUET_LINK = re.compile(r'href="([^"]+\.parquet)"', re.IGNORECASE)
_PARQUET_MAGIC = b"PAR1"


def _copy_fixtures(version: str, force: bool) -> Path:
    """Copy test fixtures into the bulk data directory."""
    dest = BULK_ROOT / version
    if dest.exists() and not force:
        print(f"Bulk data already exists at {dest} (use --force to replace)")
        return dest
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(FIXTURES / version, dest)
    return dest


def _write_manifest(version: str, source: str, tables: tuple[str, ...]) -> Path:
    manifest = {
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "tables": list(tables),
        "path": str(BULK_ROOT / version),
    }
    path = manifest_path(BULK_ROOT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def _is_valid_parquet(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 8:
        return False
    with path.open("rb") as handle:
        header = handle.read(4)
        handle.seek(-4, 2)
        footer = handle.read(4)
    return header == _PARQUET_MAGIC and footer == _PARQUET_MAGIC


def _list_parquet_urls(table_url: str) -> list[str]:
    """Parse an Apache directory index and return parquet file URLs."""
    with urlopen(table_url) as response:  # noqa: S310
        page = response.read().decode("utf-8", errors="replace")
    urls: list[str] = []
    for match in _PARQUET_LINK.finditer(page):
        href = html.unescape(match.group(1))
        if not href.endswith(".parquet"):
            continue
        urls.append(urljoin(table_url, href))
    return sorted(set(urls))


def _download_table(version: str, table: str, dest_dir: Path, *, force: bool) -> bool:
    """Download one OT parquet table (single file or partitioned folder)."""
    base = OT_FTP_BASE.format(version=version)
    table_url = f"{base}/{table}/"
    parquet_urls = _list_parquet_urls(table_url)
    if not parquet_urls:
        parquet_urls = [f"{table_url}{table}.parquet"]

    table_dir = dest_dir / table
    if table_dir.exists() and force:
        shutil.rmtree(table_dir)
    table_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    for url in parquet_urls:
        out = table_dir / Path(url).name
        if out.exists() and _is_valid_parquet(out) and not force:
            print(f"  cached {out.name} ({out.stat().st_size // 1024} KB)")
            downloaded += 1
            continue
        print(f"  downloading {url}")
        urlretrieve(url, out)  # noqa: S310
        if _is_valid_parquet(out):
            print(f"  saved {out.name} ({out.stat().st_size // 1024} KB)")
            downloaded += 1
        else:
            out.unlink(missing_ok=True)
            print(f"  invalid parquet skipped: {url}")
    return downloaded > 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup Open Targets bulk parquet store")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="OT platform version")
    parser.add_argument("--subset", action="store_true", help="Use fixture subset (dev/CI)")
    parser.add_argument(
        "--from-fixtures",
        action="store_true",
        help="Copy tests/fixtures/opentargets into data/bulk/",
    )
    parser.add_argument("--force", action="store_true", help="Replace existing data")
    parser.add_argument("--dry-run", action="store_true", help="Show plan only")
    args = parser.parse_args()

    version = args.version
    dest = BULK_ROOT / version

    if args.dry_run:
        print(f"Would setup bulk store at {dest}")
        print(f"Manifest: {manifest_path(BULK_ROOT)}")
        return 0

    if args.from_fixtures or args.subset:
        fixture_version_dir = FIXTURES / version
        if not fixture_version_dir.is_dir():
            print(f"Fixtures not found at {fixture_version_dir}")
            print("Run: python tests/fixtures/opentargets/build_fixtures.py")
            return 1
        _copy_fixtures(version, args.force)
        manifest = _write_manifest(version, "fixtures", TABLES)
        print(f"Copied fixtures to {dest}")
        print(f"Manifest written: {manifest}")
        return 0

    dest.mkdir(parents=True, exist_ok=True)
    ok_tables = []
    for table in TABLES:
        if _download_table(version, table, dest, force=args.force):
            ok_tables.append(table)
    if len(ok_tables) < 3:
        print(
            "Download incomplete — use --from-fixtures for offline dev, "
            "or download parquet manually from Open Targets FTP."
        )
        return 1
    manifest = _write_manifest(version, "ftp", tuple(ok_tables))
    print(f"Manifest written: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
