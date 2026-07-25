"""Adverse Event Profiling module for lupus drug safety scoring."""

from adverse_events.profiler import (
    compute_adverse_event_score,
    get_drug_profile,
    get_safety_summary,
    load_profiles,
    score_all_drugs,
)
from adverse_events.report import generate_html_report

__all__ = [
    "compute_adverse_event_score",
    "generate_html_report",
    "get_drug_profile",
    "get_safety_summary",
    "load_profiles",
    "score_all_drugs",
]
