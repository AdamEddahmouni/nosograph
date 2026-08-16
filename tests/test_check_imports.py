"""Self-tests for ``scripts/check_imports.py`` — the internal-import audit.

The audit script is the safety net for stale v1->v2 imports, so it is itself
tested: a clean mini-repo must pass, and a mini-repo with the failure modes
the audit exists to catch (dead module, dead name, archived lazy import, dead
re-export) must fail with exit code 1 and precise messages.

Subprocess invocation is intentional here: ``check_imports.py`` is exercised as
an isolated script entrypoint (mirroring CI ``make check-imports``), not via an
in-process import, so exit codes and stdout/stderr match production usage.
"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_imports.py"

CLEAN_FILES = {
    "src/med_research/__init__.py": "",
    "src/med_research/ok.py": "def foo():\n    pass\n",
    "src/med_research/pkg/__init__.py": (
        "from .impl import helper\n"  # relative re-export
        "from med_research.ok import foo\n"  # absolute re-export
    ),
    "src/med_research/pkg/impl.py": "def helper():\n    pass\n",
    "src/med_research/pkg/sub.py": "def sub():\n    pass\n",
    # Legit patterns the audit must NOT flag:
    "src/med_research/good.py": (
        "from med_research.pkg import helper\n"  # relative re-export chain
        "from med_research.pkg import foo\n"  # absolute re-export chain
        "from med_research.pkg import sub\n"  # submodule without re-export
        "from med_research.ok import foo as bar\n"  # alias
        "def lazy():\n"
        "    from med_research.pkg.impl import helper\n"  # lazy import inside a function
        "    return helper\n"
    ),
}

STALE_FILES = {
    "src/med_research/dead_module.py": "from med_research.gone import nope\n",
    "src/med_research/dead_name.py": "from med_research.ok import missing_name\n",
    # Mirrors the archived evidence.report lazy import that was found in the tree:
    "src/med_research/dead_lazy.py": (
        "def make():\n"
        "    from med_research.evidence.report import generate_html_report\n"
        "    return generate_html_report\n"
    ),
    "tests/test_bad.py": "from med_research.pkg import gone_attr\n",
    # A dead name reached through an *absolute* re-export chain (level==0).
    # Keeps the clean re-exports so good.py stays valid, then adds a dead one:
    "src/med_research/pkg/__init__.py": (
        "from .impl import helper\n"
        "from med_research.ok import foo\n"
        "from med_research.ok import missing_name\n"
    ),
    "src/med_research/abs_reexport.py": "from med_research.pkg import missing_name\n",
}

pytestmark = pytest.mark.unit


def build_repo(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def run_audit(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_clean_repo_passes(tmp_path: Path) -> None:
    build_repo(tmp_path, CLEAN_FILES)
    result = run_audit(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no stale references" in result.stdout


def test_stale_imports_are_detected(tmp_path: Path) -> None:
    build_repo(tmp_path, {**CLEAN_FILES, **STALE_FILES})
    result = run_audit(tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    out = result.stdout
    assert "module 'med_research.gone' does not exist" in out
    assert "'missing_name' is not defined in 'med_research.ok'" in out
    assert "module 'med_research.evidence.report' does not exist" in out
    assert "'gone_attr' is not defined in 'med_research.pkg'" in out
    # None of the legit patterns may be flagged:
    assert "good.py" not in out


def test_bad_root_exits_2(tmp_path: Path) -> None:
    result = run_audit(tmp_path / "does-not-exist")
    assert result.returncode == 2
    assert "does not look like a repo root" in result.stderr
