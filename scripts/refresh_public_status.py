"""Refresh live counts in docs/generated/public-status.yaml.

Updates full-corpus counts from the current checkout. Does **not** recompute
the n=500 L2/L3 sample (that is a labeled historical sample). Offline test
count is also a labeled snapshot unless --offline-tests is passed.

  python scripts/refresh_public_status.py
  python scripts/refresh_public_status.py --offline-tests
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

STATUS_PATH = ROOT / "docs" / "generated" / "public-status.yaml"


def _count_on_disk_dirs() -> int:
    import med_research.diseases as diseases_pkg

    root = Path(diseases_pkg.__file__).parent
    count = 0
    with os.scandir(root) as it:
        for entry in it:
            if (
                entry.is_dir()
                and not entry.name.startswith("_")
                and entry.name != "__pycache__"
                and os.path.isfile(os.path.join(entry.path, "__init__.py"))
                and os.path.isfile(os.path.join(entry.path, "config.py"))
            ):
                count += 1
    return count


def _offline_test_count() -> int:
    env = os.environ.copy()
    env["PYTEST_ADDOPTS"] = ""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-m",
            "unit and not network and not slow",
            "--collect-only",
            "-q",
            "-n",
            "0",
            "--ignore=tests/test_evidence_workspace_browser.py",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    match = re.search(r"(\d+) tests? collected", proc.stdout + proc.stderr)
    if not match:
        raise SystemExit("could not parse pytest --collect-only output for offline tests")
    return int(match.group(1))


def _replace_metric(text: str, field: str, value: int | str) -> str:
    pattern = rf"(?m)^  {re.escape(field)}:\s*.*$"
    replacement = f"  {field}: {value}"
    updated, n = re.subn(pattern, replacement, text, count=1)
    if n != 1:
        raise SystemExit(f"expected exactly one '{field}' metric line, found {n}")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline-tests",
        action="store_true",
        help="Re-collect the offline pytest selection count (slow).",
    )
    args = parser.parse_args()

    from med_research.diseases.base import Disease
    from med_research.diseases.harvest_registry import harvest_ids
    from med_research.diseases.identifiers import CI_VALIDATED_DISEASES, REFERENCE_DISEASES
    from med_research.pipeline.gene_expression.geo import CURATED_CONSENSUS_DISEASES
    from med_research.pipeline.registry import list_modules

    discoverable = len(Disease.list_all())
    on_disk = _count_on_disk_dirs()
    harvest = len(harvest_ids())
    adapters = len(list_modules())

    text = STATUS_PATH.read_text(encoding="utf-8")
    text = _replace_metric(text, "registry_modules", discoverable)
    text = _replace_metric(text, "discoverable_modules", discoverable)
    text = _replace_metric(text, "on_disk_module_dirs", on_disk)
    text = _replace_metric(text, "harvest_registry_entries", harvest)
    text = _replace_metric(text, "reference_tier", len(REFERENCE_DISEASES))
    text = _replace_metric(text, "ci_validated", len(CI_VALIDATED_DISEASES))
    text = _replace_metric(text, "l3_consensus_membership", len(CURATED_CONSENSUS_DISEASES))
    text = _replace_metric(text, "registered_pipeline_adapters", adapters)
    text = _replace_metric(text, "analysis_pipelines", adapters)
    if args.offline_tests:
        text = _replace_metric(text, "offline_tests", _offline_test_count())
    STATUS_PATH.write_text(text, encoding="utf-8")
    print(
        "updated public-status.yaml: "
        f"discoverable={discoverable} on_disk={on_disk} harvest={harvest} "
        f"adapters={adapters}"
    )
    print("L2/L3 sample values were left unchanged (labeled n=500 sample).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
