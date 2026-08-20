"""Top-level package for the Clinical Trial Matching Engine.

Provides a simple façade to run the matching pipeline.
"""

from .clinical_trials_parser import ClinicalTrialsDownloader, Trial, TrialCriteriaParser
from .eligibility_engine import EligibilityEngine
from .match_scoring import MatchScorer
from .patient_profiling import PatientFeatureVector, SyntheticPatientGenerator

__all__ = [
    "SyntheticPatientGenerator",
    "PatientFeatureVector",
    "ClinicalTrialsDownloader",
    "TrialCriteriaParser",
    "Trial",
    "EligibilityEngine",
    "MatchScorer",
]
