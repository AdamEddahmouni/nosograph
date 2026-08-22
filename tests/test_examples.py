"""Smoke-run public examples without network."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted((ROOT / "examples").glob("0*.py"))


@pytest.mark.unit
@pytest.mark.parametrize("script", EXAMPLES, ids=lambda p: p.name)
def test_example_script_runs(script: Path) -> None:
    runpy.run_path(str(script), run_name="__main__")
