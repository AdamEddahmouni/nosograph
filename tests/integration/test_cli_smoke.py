"""End-to-end smoke tests for the unified CLI.

Each test invokes ``python -m med_research.cli <command>`` as a subprocess and
asserts the command exits 0 and emits expected output. This guards against the
stale v1 imports and silent handler failures (e.g. exit 0 with no output) that
have broken the CLI twice since the v2 migration.

Only offline commands are covered here — commands that hit live external APIs
(literature, screening, trials, bioinformatics, ml, semantic, evidence,
extractor, monitor) are excluded so the suite stays fast and hermetic.
"""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent

# (test id, CLI args, expected fragment in stdout)
CLI_SMOKE_COMMANDS = [
    ("diseases", ["diseases"], "Available Diseases"),
    ("modules", ["modules"], "Available Pipeline Modules"),
    ("kg", ["kg", "--disease", "sle"], "Knowledge Graph"),
    ("repurpose", ["repurpose", "--disease", "sle", "--top", "5"], "REPURPOSING"),
    ("synergy", ["synergy", "--top", "5"], "SYNERGY"),
    ("network", ["network"], "NETWORK PHARMACOLOGY"),
    ("expression", ["expression", "--top", "5"], "EXPRESSION"),
    ("cart", ["cart", "--top", "5"], "CAR-T"),
    ("biomarker", ["biomarker", "--top", "5"], "BIOMARKER"),
    ("cross-disease", ["cross-disease", "--top", "5"], "CROSS-DISEASE"),
]

COMMAND_IDS = [name for name, _, _ in CLI_SMOKE_COMMANDS]


@pytest.mark.parametrize("name,args,expected", CLI_SMOKE_COMMANDS, ids=COMMAND_IDS)
def test_cli_command_smoke(name, args, expected):
    """Run an offline CLI command end-to-end and verify it produces output."""
    result = subprocess.run(
        [sys.executable, "-m", "med_research.cli", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, (
        f"`med_research.cli {name}` exited {result.returncode}:\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert expected in result.stdout, (
        f"`med_research.cli {name}` succeeded but produced no expected output "
        f"({expected!r}):\n{result.stdout[:1000]}"
    )
