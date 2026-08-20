"""Eligibility engine for the Clinical Trial Matching Engine.

The engine receives a :class:`PatientFeatureVector` and a :class:`Trial`
object (with parsed ``inclusion_rules`` / ``exclusion_rules``).  Each rule is a
dictionary as produced by :class:`TrialCriteriaParser`.  The engine evaluates
the rules deterministically and produces:

* ``eligible`` – ``True`` if no exclusion rule fails and all required inclusion
  rules are satisfied.
* ``score`` – a numeric penalty score (lower is better).  The score is the sum
  of weighted penalties defined in ``eligibility_config.yaml``.

The configuration file maps rule ``type`` to a ``weight`` (default 1.0).  Users
can override the file by passing a custom path to the engine.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict

from .clinical_trials_parser import Trial
from .patient_profiling import PatientFeatureVector


class EligibilityResult(BaseModel):
    eligible: bool
    score: float
    details: List[Dict[str, Any]]  # each rule evaluation record

    model_config = ConfigDict(frozen=True)


class EligibilityEngine:
    """Core deterministic evaluator for trial eligibility.

    The engine loads a simple YAML config specifying per‑rule weights.  Example::

        age: 1.0
        biomarker: 2.0
        organ: 1.5

    If a rule type is not present in the config, a default weight of ``1.0`` is
    used.
    """

    DEFAULT_CONFIG = {
        "age": 1.0,
        "biomarker": 1.0,
        "organ": 1.0,
    }

    def __init__(self, config_path: Path | str | None = None):
        self.weights = self._load_config(config_path)

    @staticmethod
    def _load_config(path: Path | str | None) -> Dict[str, float]:
        if not path:
            return EligibilityEngine.DEFAULT_CONFIG.copy()
        cfg_path = Path(path)
        if not cfg_path.is_file():
            # Fallback to defaults if file missing.
            return EligibilityEngine.DEFAULT_CONFIG.copy()
        import yaml

        with open(cfg_path, "r", encoding="utf-8") as fp:
            raw = yaml.safe_load(fp) or {}
        # Ensure numeric weights.
        return {k: float(v) for k, v in raw.items()}

    @staticmethod
    def _load_rules(rules_text: str) -> List[Dict[str, Any]]:
        # Rules are stored as stringified list of dicts; safely evaluate.
        try:
            return ast.literal_eval(rules_text)  # type: ignore[arg-type]
        except Exception:
            # If parsing fails, return empty list – the engine will treat as no rules.
            return []

    def evaluate(self, patient: PatientFeatureVector, trial: Trial) -> EligibilityResult:
        # Load rules.
        inc_rules = self._load_rules(trial.inclusion_rules or "[]")
        exc_rules = self._load_rules(trial.exclusion_rules or "[]")
        details: List[Dict[str, Any]] = []
        penalty = 0.0
        eligible = True

        # Helper to fetch a numeric feature from patient.
        def get_feature(section: str, key: str, default=None):
            return getattr(patient, section, {}).get(key, default)

        # Process inclusion rules – missing required criteria incurs penalty.
        for rule in inc_rules:
            rtype = rule.get("type")
            weight = self.weights.get(rtype, 1.0)
            passed = True
            if rtype == "age":
                age = get_feature("demographic", "age")
                passed = False if age is None else rule["min"] <= age <= rule["max"]
            elif rtype == "biomarker":
                val = get_feature("biomarkers", rule["name"].upper())
                if val is None:
                    passed = False
                else:
                    op = rule["operator"]
                    if op == ">=":
                        passed = val >= rule["value"]
                    elif op == "<=":
                        passed = val <= rule["value"]
                    elif op == ">":
                        passed = val > rule["value"]
                    elif op == "<":
                        passed = val < rule["value"]
                    else:
                        passed = val == rule["value"]
            elif rtype == "organ":
                val = get_feature("organ_function", rule["name"].lower())
                if val is None:
                    passed = False
                else:
                    op = rule["operator"]
                    if op == ">=":
                        passed = val >= rule["value"]
                    elif op == "<=":
                        passed = val <= rule["value"]
                    elif op == ">":
                        passed = val > rule["value"]
                    elif op == "<":
                        passed = val < rule["value"]
                    else:
                        passed = val == rule["value"]
            else:
                # Unknown rule type – ignore but count as no penalty.
                passed = True

            if not passed:
                penalty += weight
                details.append({"rule": rule, "passed": False, "weight": weight})
            else:
                details.append({"rule": rule, "passed": True, "weight": 0})

        # Process exclusion rules – any failure makes patient ineligible immediately.
        for rule in exc_rules:
            rtype = rule.get("type")
            weight = self.weights.get(rtype, 1.0)
            failed = False
            if rtype == "age":
                age = get_feature("demographic", "age")
                if age is not None and not (rule["min"] <= age <= rule["max"]):
                    failed = True
            elif rtype == "biomarker":
                val = get_feature("biomarkers", rule["name"].upper())
                if val is not None:
                    op = rule["operator"]
                    if (
                        (op == ">=" and val < rule["value"])
                        or (op == "<=" and val > rule["value"])
                        or (op == ">" and val <= rule["value"])
                        or (op == "<" and val >= rule["value"])
                        or (op == "=" and val != rule["value"])
                    ):
                        failed = True
            elif rtype == "organ":
                val = get_feature("organ_function", rule["name"].lower())
                if val is not None:
                    op = rule["operator"]
                    if (
                        (op == ">=" and val < rule["value"])
                        or (op == "<=" and val > rule["value"])
                        or (op == ">" and val <= rule["value"])
                        or (op == "<" and val >= rule["value"])
                        or (op == "=" and val != rule["value"])
                    ):
                        failed = True

            # Unknown types are ignored.
            if failed:
                eligible = False
                penalty += weight
                details.append({"exclusion_rule": rule, "failed": True, "weight": weight})
            else:
                details.append({"exclusion_rule": rule, "failed": False, "weight": 0})

        return EligibilityResult(eligible=eligible, score=penalty, details=details)
