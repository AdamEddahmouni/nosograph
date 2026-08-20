"""FastAPI router for Clinical Trial Patient Matching Engine."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from med_research.pipeline.matching_engine.clinical_trials_parser import Trial
from med_research.pipeline.matching_engine.eligibility_engine import EligibilityEngine
from med_research.pipeline.matching_engine.match_scoring import MatchScorer
from med_research.pipeline.matching_engine.patient_profiling import PatientFeatureVector

router = APIRouter(prefix="/api/matching", tags=["Clinical Trial Matching"])
logger = logging.getLogger(__name__)


class PatientVectorInput(BaseModel):
    patient_id: str = Field(default="PT-1001", description="Unique identifier for patient")
    age: int = Field(default=45, ge=0, le=120)
    sex: str = Field(default="female")
    disease: str = Field(default="melanoma")
    stage: str = Field(default="III")
    biomarkers: Dict[str, float] = Field(default_factory=lambda: {"BRAF_V600E": 1.0, "PD_L1": 0.65})
    prior_therapies: List[str] = Field(default_factory=lambda: ["Pembrolizumab"])
    organ_function: Dict[str, float] = Field(
        default_factory=lambda: {"creatinine": 1.0, "alt": 25.0}
    )
    location_lat: float = Field(default=37.7749)
    location_lon: float = Field(default=-122.4194)


class CohortGenerationRequest(BaseModel):
    num_patients: int = Field(default=10, ge=1, le=200)
    disease: str = Field(default="melanoma")
    seed: Optional[int] = None


RESEARCH_ONLY_DISCLAIMER = (
    "Research simulation only. Submit synthetic or de-identified research vectors. "
    "Do not upload protected health information or real patient records. "
    "Rankings are computational hypotheses, not eligibility determinations or care advice."
)


@router.post("/generate-cohort")
async def generate_synthetic_cohort(req: CohortGenerationRequest) -> Dict[str, Any]:
    """Generate synthetic patient vectors with clinical covariates for simulation."""
    import random

    rng = random.Random(req.seed or 42)
    cohort = []

    for i in range(req.num_patients):
        age = rng.randint(35, 78)
        sex = rng.choice(["male", "female"])
        vec = {
            "patient_id": f"SYN-{req.disease[:3].upper()}-{1000 + i}",
            "age": age,
            "sex": sex,
            "disease": req.disease,
            "stage": rng.choice(["II", "III", "IV"]),
            "biomarkers": {
                "BRAF_V600E": 1.0 if rng.random() > 0.4 else 0.0,
                "PD_L1": round(rng.uniform(0.1, 0.95), 2),
                "EGFR": round(rng.uniform(5.0, 45.0), 1),
            },
            "prior_therapies": rng.sample(
                ["Chemotherapy", "Nivolumab", "Ipilimumab", "Pembrolizumab"], k=rng.randint(1, 2)
            ),
            "organ_function": {"creatinine": round(rng.uniform(0.7, 1.4), 2)},
            "location_lat": round(37.7749 + rng.gauss(0, 0.5), 4),
            "location_lon": round(-122.4194 + rng.gauss(0, 0.5), 4),
        }
        cohort.append(vec)

    return {
        "disease": req.disease,
        "count": len(cohort),
        "cohort": cohort,
        "disclaimer": RESEARCH_ONLY_DISCLAIMER,
        "persisted": False,
    }


@router.post("/match")
async def match_patient_to_trials(patient: PatientVectorInput) -> Dict[str, Any]:
    """Evaluate patient vector eligibility and rank matching clinical trials."""
    patient_vec = PatientFeatureVector(
        demographic={"age": patient.age, "sex": patient.sex},
        histology={"type": patient.disease, "stage": patient.stage},
        biomarkers=patient.biomarkers,
        prior_therapies=patient.prior_therapies,
        organ_function=patient.organ_function,
    )

    benchmark_trials = [
        Trial(
            nct_id="NCT04812345",
            title="Immune Checkpoint Blockade & BRAF Inhibition in Cutaneous Melanoma",
            phase="Phase 2",
            status="RECRUITING",
            inclusion_rules=[
                {"type": "age", "field": "demographic.age", "operator": ">=", "value": 18},
                {
                    "type": "biomarker",
                    "field": "biomarkers.BRAF_V600E",
                    "operator": ">",
                    "value": 0.5,
                },
            ],
            exclusion_rules=[
                {"type": "age", "field": "demographic.age", "operator": ">", "value": 80},
            ],
        ),
        Trial(
            nct_id="NCT03987654",
            title="Next-Gen Immunotherapy in Refractory Solid Tumors",
            phase="Phase 1/2",
            status="RECRUITING",
            inclusion_rules=[
                {"type": "age", "field": "demographic.age", "operator": ">=", "value": 18},
            ],
            exclusion_rules=[
                {"type": "age", "field": "demographic.age", "operator": ">", "value": 70},
            ],
        ),
        Trial(
            nct_id="NCT05123987",
            title="Cellular Adoptive Therapy Protocol in Advanced Malignancies",
            phase="Phase 3",
            status="RECRUITING",
            inclusion_rules=[
                {"type": "age", "field": "demographic.age", "operator": ">=", "value": 21},
                {"type": "biomarker", "field": "biomarkers.PD_L1", "operator": ">=", "value": 0.5},
            ],
            exclusion_rules=[
                {"type": "age", "field": "demographic.age", "operator": ">", "value": 65},
            ],
        ),
    ]

    eligibility_engine = EligibilityEngine()
    scorer = MatchScorer(distance_weight=0.01)
    results = []

    patient_loc = (patient.location_lat, patient.location_lon)
    site_locations = {
        "NCT04812345": [(37.7749, -122.4194)],
        "NCT03987654": [(34.0522, -118.2437)],
        "NCT05123987": [(40.7128, -74.0060)],
    }

    for t in benchmark_trials:
        eligibility = eligibility_engine.evaluate(patient_vec, t)
        score_res = scorer.score_trial(
            eligibility,
            patient_location=patient_loc,
            trial_locations=site_locations.get(t.nct_id, [patient_loc]),
        )

        results.append(
            {
                "trial_id": t.nct_id,
                "title": t.title,
                "phase": t.phase,
                "is_eligible": eligibility.eligible,
                "inclusion_reasons": [
                    "Inclusion criteria satisfied" if eligibility.eligible else "Unmet criteria"
                ],
                "exclusion_violations": []
                if eligibility.eligible
                else ["Violates trial criteria boundary"],
                "overall_match_score": round(score_res.get("confidence", 0.0), 3),
                "distance_km": round(score_res.get("distance_km", 0.0), 1),
            }
        )

    results.sort(key=lambda x: (x["is_eligible"], x["overall_match_score"]), reverse=True)

    return {
        "patient_id": patient.patient_id,
        "disease": patient.disease,
        "total_trials_evaluated": len(results),
        "eligible_trials_count": sum(1 for r in results if r["is_eligible"]),
        "matches": results,
        "disclaimer": RESEARCH_ONLY_DISCLAIMER,
        "persisted": False,
    }
