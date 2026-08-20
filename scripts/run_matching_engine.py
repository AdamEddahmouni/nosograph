"""Command‑line interface for the Clinical Trial Matching Engine.

Usage example::

    python scripts/run_matching_engine.py \
        --config-dir src/matching_engine/config \
        --patient-config synthetic_patient.yaml \
        --output json

The script:
1. Loads the synthetic patient generator configuration.
2. Generates a patient vector.
3. Downloads (if needed) and parses trial data.
4. Evaluates eligibility for each trial.
5. Scores and ranks the trials.
6. Prints the ranked list as JSON.
"""

import argparse
import json
from pathlib import Path

from matching_engine.patient_profiling import SyntheticPatientGenerator
from matching_engine.clinical_trials_parser import (
    ClinicalTrialsDownloader,
    get_engine,
    get_session,
    Trial,
    TrialCriteriaParser,
)
from matching_engine.eligibility_engine import EligibilityEngine
from matching_engine.match_scoring import MatchScorer, serialize_ranking


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Clinical Trial Matching Engine")
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("src/matching_engine/config"),
        help="Directory containing configuration files",
    )
    parser.add_argument(
        "--patient-config",
        type=Path,
        required=True,
        help="YAML file describing synthetic patient feature distributions",
    )
    parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="json",
        help="Output format for ranking results",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Force re‑download of ClinicalTrials.gov data",
    )
    args = parser.parse_args()

    # 1. Generate synthetic patient.
    generator = SyntheticPatientGenerator(args.patient_config)
    patient = generator.generate()

    # 2. Prepare DB session.
    engine = get_engine()
    session = get_session(engine)

    # 3. Download and load trial data if necessary.
    downloader = ClinicalTrialsDownloader()
    data_dir = downloader.dest_dir / "AllPublicXML"
    if args.download or not any(data_dir.rglob("*.xml")):
        print("Downloading ClinicalTrials.gov bulk data …")
        downloader.download()
        print("Parsing and loading trials into SQLite …")
        parser = TrialCriteriaParser()
        parser.bulk_load(data_dir, session)
    else:
        # Ensure tables exist.
        Base = Trial.__bases__[0]  # get declarative base
        Base.metadata.create_all(engine)

    # 4. Evaluate eligibility for all trials.
    eligibility_engine = EligibilityEngine(config_path=args.config_dir / "eligibility_config.yaml")
    elig_map = {}
    for trial in session.query(Trial).all():
        result = eligibility_engine.evaluate(patient, trial)
        elig_map[trial.nct_id] = result

    # 5. Score and rank.
    scorer = MatchScorer()
    ranking = scorer.rank_trials(elig_map)

    # 6. Output.
    if args.output == "json":
        print(serialize_ranking(ranking))
    else:
        for entry in ranking:
            print(
                f"{entry['nct_id']}: confidence={entry['confidence']:.3f}, eligible={entry['eligible']}"
            )

if __name__ == "__main__":
    main()
