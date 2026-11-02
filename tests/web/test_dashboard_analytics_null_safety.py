"""Static contracts for null-safe biomedical analytics rendering.

The dashboard has no JS test harness, so these checks pin the two distinctions
that the API deliberately preserves and a client can easily destroy:

* ``jaccard_similarity`` is ``null`` when it was not computed and ``0.0`` when
  the store was queried and measured no overlap.
* an uninitialized store carries ``store_state`` instead of an empty finding.

A numeric fallback (``|| 0`` or ``?? 0``) silently turns both into "no shared
biology", which is exactly the scientific misreading the API contract prevents.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

DASHBOARD_JS = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "med_research"
    / "web"
    / "static"
    / "js"
    / "dashboard.js"
).read_text(encoding="utf-8")


def test_shared_mechanisms_does_not_coerce_uncomputed_similarity_to_zero() -> None:
    assert "(res.jaccard_similarity || 0)" not in DASHBOARD_JS
    assert "Number.isFinite(res.jaccard_similarity)" in DASHBOARD_JS
    assert "Jaccard overlap not computed" in DASHBOARD_JS


def test_matrix_cells_distinguish_uncomputed_from_measured_zero() -> None:
    assert "(matrix[rIdx][cIdx] ?? 0)" not in DASHBOARD_JS
    assert "Similarity matrix not computed" in DASHBOARD_JS


def test_analytics_panels_render_store_readiness_instead_of_empty_findings() -> None:
    assert "res.store_state?.status === 'uninitialized'" in DASHBOARD_JS
    assert "data.store_state?.status === 'uninitialized'" in DASHBOARD_JS
    assert "Statistics not computed" in DASHBOARD_JS
    assert "Pathways not computed" in DASHBOARD_JS
