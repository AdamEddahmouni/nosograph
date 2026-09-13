"""Harvest catalog vs on-disk module drift (CI).

Thin wrapper around ``python scripts/reconcile_harvest_registry.py --check``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    raise SystemExit(
        subprocess.call(
            [sys.executable, str(ROOT / "scripts" / "reconcile_harvest_registry.py"), "--check"],
            cwd=ROOT,
        )
    )


if __name__ == "__main__":
    main()
