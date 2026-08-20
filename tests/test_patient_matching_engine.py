import pytest

from matching_engine.clinical_trials_parser import Trial
from matching_engine.eligibility_engine import EligibilityEngine
from matching_engine.match_scoring import MatchScorer
from matching_engine.patient_profiling import PatientFeatureVector, SyntheticPatientGenerator


@pytest.mark.unit
def test_synthetic_patient_generation(tmp_path):
    config_yaml = tmp_path / "patient.yaml"
    config_yaml.write_text(
        """
demographic:
  age:
    min: 40
    max: 60
  sex: ["female"]
biomarkers:
  EGFR:
    min: 10.0
    max: 50.0
organ_function:
  creatinine:
    min: 0.8
    max: 1.2
""",
        encoding="utf-8",
    )

    generator = SyntheticPatientGenerator(config_yaml)
    patient = generator.generate()
    assert isinstance(patient, PatientFeatureVector)
    assert 40 <= patient.demographic["age"] <= 60
    assert patient.demographic["sex"] == "female"
    assert 10.0 <= patient.biomarkers["EGFR"] <= 50.0


@pytest.mark.unit
def test_eligibility_and_scoring():
    patient = PatientFeatureVector(
        demographic={"age": 45, "sex": "female"},
        histology={"type": "adenocarcinoma"},
        biomarkers={"EGFR": 25.0},
        prior_therapies=["chemotherapy"],
        organ_function={"creatinine": 0.9},
    )

    trial = Trial(
        nct_id="NCT01234567",
        title="Targeted EGFR Study",
        phase="Phase 2",
        status="RECRUITING",
        inclusion_rules=[
            {"type": "age", "field": "demographic.age", "operator": ">=", "value": 18},
            {"type": "biomarker", "field": "biomarkers.EGFR", "operator": ">", "value": 0.0},
        ],
        exclusion_rules=[{"type": "age", "field": "demographic.age", "operator": ">", "value": 75}],
    )

    engine = EligibilityEngine()
    result = engine.evaluate(patient, trial)
    assert result.eligible is True
    assert result.score == 0.0

    scorer = MatchScorer(distance_weight=0.01)
    score_out = scorer.score_trial(
        result, patient_location=(40.7128, -74.0060), trial_locations=[(40.7128, -74.0060)]
    )
    assert score_out["confidence"] >= 0.99
