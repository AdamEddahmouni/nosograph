"""CAR-T Response Predictor Module.

Scores all 35 lupus genes for CD19 CAR-T cell therapy suitability
based on B cell dependency, autoantibody association, and pathway relevance.
"""

from car_t_predictor.predictor import compute_all_scores
from car_t_predictor.report import generate_html_report

__all__ = ["compute_all_scores", "generate_html_report"]
