"""Verify that setuptools package-data includes key runtime assets."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, distribution
from importlib.resources import files as resource_files

import pytest

PACKAGE_NAME = "med-research"
DISEASE_IDS = ("sle", "ra", "ibd", "ms", "ss", "ssc", "t1d")
KG_FILES = ("genes.json", "drugs.json", "pathways.json", "relationships.json", "profile.json")

pytestmark = pytest.mark.unit




def _package_paths() -> set[str]:
    """Return normalized paths shipped with the distribution."""


    try:
        dist = distribution(PACKAGE_NAME)
    except PackageNotFoundError:
        pytest.skip(f"{PACKAGE_NAME} is not installed")

    if dist.files:
        paths_from_dist = {str(path).replace("\\", "/") for path in dist.files}
        if any(path.startswith("med_research/") for path in paths_from_dist):
            return paths_from_dist

    # Editable installs only record dist-info in metadata; fall back to resources.
    root = resource_files("med_research")
    paths: set[str] = set()

    def _walk(current, prefix: str = "med_research") -> None:
        for item in current.iterdir():
            rel = f"{prefix}/{item.name}"
            if item.is_dir():
                _walk(item, rel)
            else:
                paths.add(rel)

    _walk(root)
    return paths


@pytest.fixture(scope="module")
def packaged_files() -> set[str]:
    return _package_paths()


@pytest.mark.parametrize("disease_id", DISEASE_IDS)
def test_disease_kg_json_packaged(packaged_files, disease_id):
    """Each disease ships core knowledge-graph JSON under package data."""
    for filename in KG_FILES:
        expected = f"med_research/diseases/{disease_id}/data/{filename}"
        assert expected in packaged_files, f"missing packaged file: {expected}"


def test_web_static_index_packaged(packaged_files):
    assert "med_research/web/static/index.html" in packaged_files


def test_web_static_dashboard_js_packaged(packaged_files):
    assert "med_research/web/static/js/dashboard.js" in packaged_files


def test_pipeline_sample_data_packaged(packaged_files):
    """Spot-check that pipeline module data directories are included."""
    samples = (
        "med_research/pipeline/drug_repurposing/data/candidates.json",
        "med_research/pipeline/drug_synergy/data/synergy_results.json",
    )
    for path in samples:
        assert path in packaged_files, f"missing packaged file: {path}"
