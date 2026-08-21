"""Public metadata consistency."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_metadata() -> None:
    subprocess.check_call(
        [sys.executable, str(ROOT / "scripts" / "check_public_metadata.py")],
        cwd=ROOT,
    )
