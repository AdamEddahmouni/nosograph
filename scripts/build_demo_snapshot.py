#!/usr/bin/env python3
"""Build a reproducible offline biomedical demo snapshot from checked-in fixtures."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from med_research.demo.snapshot import (
    DEFAULT_DEMO_DB_PATH,
    DEFAULT_FIXTURE_ROOT,
    DemoSnapshotError,
    build_demo_snapshot,
    manifest_path_for,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build an offline fixture-backed biomedical demo snapshot."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_DEMO_DB_PATH,
        help="SQLite database output path",
    )
    parser.add_argument(
        "--fixture-root",
        type=Path,
        default=DEFAULT_FIXTURE_ROOT,
        help="Directory containing mondo/, hpo/, and hpoa/ fixtures",
    )
    args = parser.parse_args(argv)
    try:
        written = build_demo_snapshot(args.output, fixture_root=args.fixture_root)
    except DemoSnapshotError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote demo snapshot to {written}")
    print(f"Wrote manifest to {manifest_path_for(written)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
