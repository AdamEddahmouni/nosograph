"""Base disease class - defines the contract for all disease modules.

Each disease module under diseases/{id}/ provides:
  - data/                              JSON knowledge graph data
  - config.py                          Disease-specific pipeline configuration  
  - scores.py (optional)               Disease-specific scoring tables

The pipeline reads a disease module and runs all computational modules
against it, using the disease config to parameterize disease-specific logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DiseaseProfile:
    """Parsed profile data for a disease."""
    id: str
    name: str
    description: str = ""
    prevalence: str = ""
    female_to_male_ratio: str = ""
    peak_onset: str = ""
    primary_tissue: str = ""
    hallmark_markers: list[str] = field(default_factory=list)
    key_pathways: list[str] = field(default_factory=list)
    kg_node_id: str = ""


class Disease:
    """Represents a single disease with its data, configuration, and scoring tables.

    Usage:
        disease = Disease("sle")
        genes = disease.load_genes()
        drugs = disease.load_drugs()
        symptoms = disease.get_symptoms()
        car_t_scores = disease.get_car_t_scores()
    """

    def __init__(self, disease_id: str) -> None:
        self.disease_id = disease_id
        self._root = self._resolve_root(disease_id)
        self._profile: Optional[DiseaseProfile] = None
        self._config: Optional[dict] = None
        self._scores: Optional[dict] = None

    @staticmethod
    def _resolve_root(disease_id: str) -> Path:
        """Find the diseases directory and resolve this disease's path."""
        import med_research.diseases as diseases_pkg
        root = Path(diseases_pkg.__file__).parent / disease_id
        if not root.exists():
            raise ValueError(
                f"Disease '{disease_id}' not found. Available: {Disease.list_all()}"
            )
        return root

    @property
    def data_dir(self) -> Path:
        return self._root / "data"

    @property
    def profile(self) -> DiseaseProfile:
        if self._profile is None:
            path = self.data_dir / "profile.json"
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._profile = DiseaseProfile(
                id=data.get("id", self.disease_id),
                name=data.get("name", self.disease_id),
                description=data.get("description", ""),
                prevalence=data.get("prevalence", ""),
                female_to_male_ratio=data.get("female_to_male_ratio", ""),
                peak_onset=data.get("peak_onset", ""),
                primary_tissue=data.get("primary_tissue", ""),
                hallmark_markers=data.get("hallmark_markers", []),
                key_pathways=data.get("key_pathways", []),
                kg_node_id=data.get("kg_node_id", data.get("name", "")),
            )
        return self._profile

    def load_json(self, filename: str) -> dict:
        path = self.data_dir / filename
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def load_genes(self) -> dict:
        return self.load_json("genes.json")

    def load_drugs(self) -> dict:
        return self.load_json("drugs.json")

    def load_pathways(self) -> dict:
        return self.load_json("pathways.json")

    def load_relationships(self) -> dict:
        return self.load_json("relationships.json")

    # ── Disease-specific configuration ─────────────────────────────────

    def _load_config(self) -> dict:
        """Load disease_config.py if it exists, else return empty defaults."""
        if self._config is None:
            config_path = self._root / "config.py"
            if config_path.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    f"med_research.diseases.{self.disease_id}.config", str(config_path)
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    self._config = {
                        k: v for k, v in vars(module).items()
                        if not k.startswith("_") and k.isupper()
                    }
                else:
                    self._config = {}
            else:
                self._config = {}
        return self._config

    @property
    def config(self) -> dict:
        return self._load_config()

    def get_symptoms(self) -> list[str]:
        return self.config.get("SYMPTOMS", [])

    def get_car_t_scores(self) -> dict:
        return self.config.get("CAR_T_SCORES", {})

    def get_adverse_event_profile(self) -> dict:
        return self.config.get("ADVERSE_EVENT_PROFILE", {})

    def get_drug_induced_lupus_risk(self) -> dict:
        return self.config.get("DRUG_INDUCED_LUPUS_RISK", {})

    def get_mechanism_categories(self) -> dict:
        return self.config.get("MECHANISM_CATEGORIES", {})

    # ── Static helpers ─────────────────────────────────────────────────

    @staticmethod
    def list_all() -> list[str]:
        import med_research.diseases as diseases_pkg
        root = Path(diseases_pkg.__file__).parent
        return sorted(
            d.name for d in root.iterdir()
            if d.is_dir() and (d / "__init__.py").exists()
            and not d.name.startswith("_") and d.name != "__pycache__"
        )

    @staticmethod
    def discover() -> dict[str, "Disease"]:
        """Discover and instantiate all available diseases."""
        return {did: Disease(did) for did in Disease.list_all()}

    def __repr__(self) -> str:
        return f"Disease({self.disease_id!r}, name={self.profile.name!r})"
