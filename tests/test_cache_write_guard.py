"""Guard against reintroducing legacy flat-file cache writes in pipeline modules."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

LEGACY_CACHE_WRITE = re.compile(
    r"write_text\([^)]*(?:gwas_cache|enrichment_cache|ppi_cache|pubmed_cache|"
    r"evidence_cache|extraction_cache|ct_cache)",
    re.IGNORECASE,
)

pytestmark = pytest.mark.unit




def test_pipeline_modules_do_not_write_legacy_cache_files():
    root = Path(__file__).resolve().parents[1] / "src" / "med_research" / "pipeline"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if "cache.py" in path.name:
            continue
        text = path.read_text(encoding="utf-8")
        if LEGACY_CACHE_WRITE.search(text):
            offenders.append(str(path.relative_to(root.parents[1])))
    assert not offenders, f"Legacy cache dual-writes found: {offenders}"
