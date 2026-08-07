"""Disease-aware virtual screening strategy contracts.

A strategy describes the curated inputs used by the property-based screening
heuristic.  It is intentionally a transparent configuration boundary: a
ready strategy does not imply experimental binding or clinical efficacy.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

SCORE_DIMENSIONS = (
    "binding_estimate",
    "druglikeness",
    "target_complementarity",
    "similarity_score",
    "novelty_score",
)


@dataclass(frozen=True)
class ScreeningStrategy:
    """Validated configuration for one disease's virtual screening run."""

    strategy_id: str
    disease_id: str
    pathway_keywords: tuple[str, ...]
    mechanism_keywords: tuple[str, ...]
    reference_drug_ids: tuple[str, ...]
    weights: dict[str, float]
    source: str
    curated_inputs: tuple[str, ...]
    inferred_inputs: tuple[str, ...]
    limitations: tuple[str, ...]

    @classmethod
    def from_profile(
        cls,
        disease_id: str,
        profile: Mapping[str, Any],
        available_drug_ids: set[str],
    ) -> "ScreeningStrategy":
        """Build and validate a strategy from an explicit disease config."""
        if not isinstance(profile, Mapping):
            raise ValueError(f"Screening profile for '{disease_id}' must be a mapping")

        strategy = cls(
            strategy_id=str(profile.get("strategy_id", "")),
            disease_id=disease_id,
            pathway_keywords=_as_terms(profile.get("pathway_keywords")),
            mechanism_keywords=_as_terms(profile.get("mechanism_keywords")),
            reference_drug_ids=_as_terms(profile.get("reference_drug_ids")),
            weights={str(k): float(v) for k, v in dict(profile.get("weights", {})).items()},
            source=str(profile.get("source", "")),
            curated_inputs=_as_terms(profile.get("curated_inputs")),
            inferred_inputs=_as_terms(profile.get("inferred_inputs")),
            limitations=_as_terms(profile.get("limitations")),
        )
        validate_strategy(strategy, available_drug_ids=available_drug_ids)
        return strategy

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible provenance representation."""
        return {
            "strategy_id": self.strategy_id,
            "disease_id": self.disease_id,
            "pathway_keywords": list(self.pathway_keywords),
            "mechanism_keywords": list(self.mechanism_keywords),
            "reference_drug_ids": list(self.reference_drug_ids),
            "weights": dict(self.weights),
            "source": self.source,
            "curated_inputs": list(self.curated_inputs),
            "inferred_inputs": list(self.inferred_inputs),
            "limitations": list(self.limitations),
        }


def _as_terms(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        raise ValueError("Screening profile term lists must be sequences")
    return tuple(str(item).strip() for item in value if str(item).strip())


def validate_strategy(
    strategy: ScreeningStrategy,
    *,
    available_drug_ids: set[str] | None = None,
) -> ScreeningStrategy:
    """Validate a strategy and return it for convenient composition."""
    if not strategy.strategy_id:
        raise ValueError("Screening strategy_id must be non-empty")
    if not strategy.disease_id:
        raise ValueError("Screening strategy disease_id must be non-empty")
    if not strategy.pathway_keywords:
        raise ValueError(f"Screening strategy '{strategy.strategy_id}' has no pathway keywords")
    if not strategy.mechanism_keywords:
        raise ValueError(f"Screening strategy '{strategy.strategy_id}' has no mechanism keywords")
    if not strategy.source:
        raise ValueError(f"Screening strategy '{strategy.strategy_id}' has no source")
    if not strategy.reference_drug_ids:
        raise ValueError(f"Screening strategy '{strategy.strategy_id}' has no reference drugs")
    if not strategy.curated_inputs:
        raise ValueError(f"Screening strategy '{strategy.strategy_id}' has no curated inputs")
    if not strategy.inferred_inputs:
        raise ValueError(f"Screening strategy '{strategy.strategy_id}' has no inferred-input declaration")
    if not strategy.limitations:
        raise ValueError(f"Screening strategy '{strategy.strategy_id}' has no limitations")

    if set(strategy.weights) != set(SCORE_DIMENSIONS):
        missing = sorted(set(SCORE_DIMENSIONS) - set(strategy.weights))
        extra = sorted(set(strategy.weights) - set(SCORE_DIMENSIONS))
        raise ValueError(
            f"Screening strategy '{strategy.strategy_id}' weights must contain "
            f"{', '.join(SCORE_DIMENSIONS)}; missing={missing}, extra={extra}"
        )
    if any(value < 0 for value in strategy.weights.values()):
        raise ValueError(f"Screening strategy '{strategy.strategy_id}' weights cannot be negative")
    if abs(sum(strategy.weights.values()) - 1.0) > 1e-9:
        raise ValueError(f"Screening strategy '{strategy.strategy_id}' weights must sum to 1")

    if available_drug_ids is not None:
        unknown = sorted(set(strategy.reference_drug_ids) - set(available_drug_ids))
        if unknown:
            raise ValueError(
                f"Screening strategy '{strategy.strategy_id}' references unavailable drugs: {unknown}"
            )
    return strategy


def strategy_for_disease(disease_id: str = "sle") -> ScreeningStrategy:
    """Resolve only the explicitly configured strategy for ``disease_id``.

    Unknown diseases and missing/malformed profiles fail closed.  In
    particular, no disease can inherit the SLE strategy implicitly.
    """
    from med_research.diseases.base import Disease

    disease = Disease(disease_id)
    profile = disease.get_screening_profile()
    available_drug_ids = {
        str(item.get("id"))
        for item in disease.load_drugs().get("drugs", [])
        if isinstance(item, Mapping) and item.get("id")
    }
    return ScreeningStrategy.from_profile(disease_id, profile, available_drug_ids)


def strategy_fingerprint(strategy: ScreeningStrategy) -> str:
    """Return a deterministic SHA-256 fingerprint for strategy provenance."""
    payload = json.dumps(strategy.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalized_weights(weights: Mapping[str, float] | None) -> dict[str, float]:
    """Validate and normalize a caller-supplied composite weight mapping."""
    if weights is None:
        raise ValueError("weights are required")
    values = {str(k): float(v) for k, v in dict(weights).items()}
    if set(values) != set(SCORE_DIMENSIONS):
        raise ValueError("weights must contain exactly the five screening score dimensions")
    if any(value < 0 for value in values.values()):
        raise ValueError("weights cannot be negative")
    total = sum(values.values())
    if total <= 0:
        raise ValueError("weights must have a positive total")
    return {key: value / total for key, value in values.items()}
