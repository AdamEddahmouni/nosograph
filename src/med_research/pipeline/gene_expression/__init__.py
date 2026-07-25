"""Gene Expression Correlation Module.

Connectivity Map-inspired approach: correlates drug mechanisms against
curated SLE gene expression signatures to score reversal potential.

Supports both curated literature signatures and GEO multi-omics integration.
"""

from med_research.pipeline.gene_expression.correlator import compute_all_correlations
from med_research.pipeline.gene_expression.report import generate_html_report
from med_research.pipeline.gene_expression.signature import get_signature

__all__ = ["compute_all_correlations", "generate_html_report", "get_signature"]
