"""Biomarker Discovery Module.

Cross-module integration engine: correlates gene expression signatures
with predicted treatment responses across all 5 scoring platforms
to identify the most predictive biomarkers for lupus therapy selection.
"""

from med_research.pipeline.biomarker_discovery.discover import compute_biomarker_matrix
from med_research.pipeline.biomarker_discovery.report import generate_html_report

__all__ = ["compute_biomarker_matrix", "generate_html_report"]
