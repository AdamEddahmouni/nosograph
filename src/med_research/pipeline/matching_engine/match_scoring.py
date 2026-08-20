"""Match scoring utilities for the Clinical Trial Matching Engine.

The :class:`MatchScorer` aggregates the output of :class:`EligibilityEngine`
with optional location‑based distance weighting.  For the MVP we only use the
penalty ``score`` returned by the eligibility engine and transform it into a
confidence value between 0 and 1 (higher is better).

If geographic coordinates are provided for both the patient and trial sites the
distance penalty (in kilometers) can be added – it is multiplied by a configurable
weight (default ``0.01``) so that each 100 km adds ``1.0`` penalty points.
"""

from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Tuple

from .eligibility_engine import EligibilityResult


def _km_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in kilometers between two latitude/longitude points."""
    R = 6371.0  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class MatchScorer:
    """Combine eligibility results with optional location distance.

    Parameters
    ----------
    distance_weight: float, optional
        Weight applied to distance (km) when adding to the penalty score.  The
        default of ``0.01`` means each 100 km adds ``1`` penalty point.
    """

    def __init__(self, distance_weight: float = 0.01):
        self.distance_weight = distance_weight

    def score_trial(
        self,
        eligibility: EligibilityResult,
        patient_location: Optional[Tuple[float, float]] = None,
        trial_locations: Optional[List[Tuple[float, float]]] = None,
    ) -> Dict[str, Any]:
        """Return a dict with ranking information for a single trial.

        ``patient_location`` and ``trial_locations`` are ``(lat, lon)`` tuples.
        If either is missing the distance component is omitted.
        """
        total_score = eligibility.score
        distance_km = None
        if patient_location and trial_locations:
            # Use the minimum distance to any site.
            distances = [
                _km_distance(patient_location[0], patient_location[1], lat, lon)
                for lat, lon in trial_locations
            ]
            distance_km = min(distances)
            total_score += distance_km * self.distance_weight
        # Transform penalty score into a confidence between 0 and 1.
        # Simple formula: confidence = 1 / (1 + total_score)
        confidence = 1.0 / (1.0 + total_score)
        return {
            "eligible": eligibility.eligible,
            "penalty_score": total_score,
            "confidence": confidence,
            "distance_km": distance_km,
            "details": eligibility.details,
        }

    def rank_trials(
        self,
        eligibility_map: Dict[str, EligibilityResult],
        patient_location: Optional[Tuple[float, float]] = None,
        trial_site_map: Optional[Dict[str, List[Tuple[float, float]]]] = None,
    ) -> List[Dict[str, Any]]:
        """Rank multiple trials.

        ``eligibility_map`` maps ``nct_id`` → ``EligibilityResult``.
        ``trial_site_map`` (optional) maps ``nct_id`` → list of site coordinates.
        Returns a list sorted by descending ``confidence``.
        """
        ranked = []
        for nct_id, elig in eligibility_map.items():
            sites = trial_site_map.get(nct_id) if trial_site_map else None
            scored = self.score_trial(elig, patient_location, sites)
            scored["nct_id"] = nct_id
            ranked.append(scored)
        ranked.sort(key=lambda x: x["confidence"], reverse=True)
        return ranked


# Helper to serialize the ranking result to JSON for the CLI.
def serialize_ranking(ranking: List[Dict[str, Any]]) -> str:
    return json.dumps(ranking, indent=2, default=str)
