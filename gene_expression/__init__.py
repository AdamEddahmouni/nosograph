"""Gene Expression Correlation Module.

Connectivity Map-inspired approach: correlates drug mechanisms against
curated SLE gene expression signatures to score reversal potential.
"""

from gene_expression.correlator import compute_all_correlations
from gene_expression.report import generate_html_report

__all__ = ["compute_all_correlations", "generate_html_report"]
