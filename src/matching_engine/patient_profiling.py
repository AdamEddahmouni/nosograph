"""Patient profiling utilities for the Clinical Trial Matching Engine.

Defines a Pydantic model for patient feature vectors and a simple synthetic
patient generator that reads a YAML configuration describing distributions for
each feature.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Dict, List

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PatientFeatureVector(BaseModel):
    """Container for patient features used in eligibility evaluation.

    The fields are intentionally generic – the engine only requires the keys to
    exist; the exact semantics are defined by the trial criteria parser.
    """

    model_config = ConfigDict(frozen=True)

    demographic: Dict[str, Any] = Field(default_factory=dict)
    histology: Dict[str, Any] = Field(default_factory=dict)
    biomarkers: Dict[str, float] = Field(default_factory=dict)
    prior_therapies: List[str] = Field(default_factory=list)
    organ_function: Dict[str, float] = Field(default_factory=dict)  # e.g., renal, hepatic

    @field_validator("organ_function", mode="before")
    @classmethod
    def coerce_numeric(cls, v):
        # Ensure numeric values are floats
        if isinstance(v, dict):
            return {k: float(val) for k, val in v.items()}
        return v


class SyntheticPatientGenerator:
    """Generate synthetic patients from a YAML‑driven distribution config.

    The configuration file defines a mapping of feature keys to either a list of
    possible categorical values or a ``{min, max}`` range for numeric values.  An
    example fragment::

        demographic:
          age: {min: 30, max: 80}
          sex: ["male", "female"]
        biomarkers:
          EGFR: {min: 0.0, max: 100.0}
        organ_function:
          creatinine: {min: 0.5, max: 1.5}

    The generator will sample uniformly within numeric ranges and uniformly from
    categorical lists.
    """

    def __init__(self, config_path: Path | str):
        self.config = self._load_config(config_path)

    @staticmethod
    def _load_config(path: Path | str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as fp:
            return yaml.safe_load(fp)

    def _sample_numeric(self, spec: Dict[str, float]) -> float:
        return random.uniform(float(spec["min"]), float(spec["max"]))

    def _sample_categorical(self, choices: List[Any]) -> Any:
        return random.choice(choices)

    def generate(self) -> PatientFeatureVector:
        # Helper to walk the config and produce a dict of sampled values.
        def walk(section: Dict[str, Any]) -> Dict[str, Any]:
            result: Dict[str, Any] = {}
            for key, value in section.items():
                if isinstance(value, dict) and "min" in value and "max" in value:
                    result[key] = self._sample_numeric(value)
                elif isinstance(value, list):
                    result[key] = self._sample_categorical(value)
                elif isinstance(value, dict):
                    # Nested dict – recurse.
                    result[key] = walk(value)
                else:
                    # Fallback – copy as‑is.
                    result[key] = value
            return result

        raw = walk(self.config)
        # Split into the expected top‑level sections.
        return PatientFeatureVector(
            demographic=raw.get("demographic", {}),
            histology=raw.get("histology", {}),
            biomarkers=raw.get("biomarkers", {}),
            prior_therapies=raw.get("prior_therapies", []),
            organ_function=raw.get("organ_function", {}),
        )
