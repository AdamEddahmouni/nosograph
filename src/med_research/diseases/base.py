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
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence, cast

from med_research.diseases.coverage import ModuleCoverage

_ALL_DISEASES_CACHE: Optional[list[str]] = None
_ROOT_CACHE: dict[str, Path] = {}
_CONFIG_CACHE: dict[str, dict[str, Any]] = {}


def invalidate_disease_cache() -> None:
    """Invalidate in-memory disease discovery cache (e.g. after scaffold generation)."""
    global _ALL_DISEASES_CACHE, _ROOT_CACHE, _CONFIG_CACHE
    _ALL_DISEASES_CACHE = None
    _ROOT_CACHE.clear()
    _CONFIG_CACHE.clear()
    try:
        from med_research.diseases.coverage import coverage_for_disease, module_coverage

        clear_cov = getattr(coverage_for_disease, "cache_clear", None)
        if callable(clear_cov):
            clear_cov()
        clear_mod = getattr(module_coverage, "cache_clear", None)
        if callable(clear_mod):
            clear_mod()
    except Exception:
        pass
    try:
        from med_research.diseases.schemas import invalidate_schemas_cache

        invalidate_schemas_cache()
    except Exception:
        pass
    try:
        from med_research.web.routers.system import invalidate_system_disease_cache

        invalidate_system_disease_cache()
    except Exception:
        pass


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
        self._config: Optional[dict[str, Any]] = None
        self._scores: Optional[dict] = None
        self._data_cache: dict[str, Any] = {}

    @staticmethod
    def _resolve_root(disease_id: str) -> Path:
        """Find the diseases directory and resolve this disease's path."""
        cached = _ROOT_CACHE.get(disease_id)
        if cached is not None:
            return cached

        import med_research.diseases as diseases_pkg

        root = Path(diseases_pkg.__file__).parent / disease_id
        if not root.exists():
            raise ValueError(f"Disease '{disease_id}' not found. Available: {Disease.list_all()}")
        _ROOT_CACHE[disease_id] = root
        return root

    @property
    def data_dir(self) -> Path:
        return self._root / "data"

    @property
    def profile(self) -> DiseaseProfile:
        if self._profile is None:
            from med_research.diseases.schemas import (
                DiseaseProfile as ProfileSchema,
            )
            from med_research.diseases.schemas import (
                load_validated_json,
            )

            path = self.data_dir / "profile.json"
            data = load_validated_json(path, ProfileSchema)
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

    def load_json(self, filename: str) -> dict[str, Any]:
        """Load a data file, validating registered KG files against their schema."""
        if filename in self._data_cache:
            return cast(dict[str, Any], self._data_cache[filename])

        from med_research.diseases.schemas import KG_FILE_MODELS, load_validated_json

        path = self.data_dir / filename
        model_class = KG_FILE_MODELS.get(filename)
        if model_class is None:
            with open(path, encoding="utf-8") as f:
                data = cast(dict[str, Any], json.load(f))
        else:
            data = load_validated_json(path, model_class)
        self._data_cache[filename] = data
        return data

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
        if self._config is not None:
            return self._config

        cached_cfg = _CONFIG_CACHE.get(self.disease_id)
        if cached_cfg is not None:
            self._config = cached_cfg
            return self._config

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
                    k: v for k, v in vars(module).items() if not k.startswith("_") and k.isupper()
                }
            else:
                self._config = {}
        else:
            self._config = {}

        _CONFIG_CACHE[self.disease_id] = self._config
        return self._config

    @property
    def config(self) -> dict:
        return self._load_config()

    def get_symptoms(self) -> list[str]:
        return cast(list[str], self.config.get("SYMPTOMS", []))

    def get_car_t_scores(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.config.get("CAR_T_SCORES", {}))

    def get_adverse_event_profile(self) -> dict:
        """Load the active disease's explicit adverse-event profile contract.

        Disease modules own their safety inputs. The legacy shared profile
        database is retained only as a SLE compatibility fallback and is never
        used to make another disease appear covered.
        """
        configured = self.config.get("ADVERSE_EVENT_PROFILE")
        if configured:
            return cast(dict[str, Any], configured)

        disease_path = self.data_dir / "adverse_events.json"
        if disease_path.is_file():
            from med_research.diseases.schemas import AdverseEventsFile, validate_and_load

            payload = validate_and_load(disease_path, AdverseEventsFile)
            if payload is not None:
                return payload
            return {}

        if self.disease_id == "sle":
            profile_path = (
                self._root.parent.parent / "pipeline" / "adverse_events" / "data" / "profiles.json"
            )
            if profile_path.is_file():
                try:
                    payload = json.loads(profile_path.read_text(encoding="utf-8"))
                    return {
                        "schema_version": "legacy",
                        "disease_id": "sle",
                        "source": "legacy_sle_adverse_event_profiles",
                        "profiles": payload.get("profiles", []),
                    }
                except (OSError, ValueError, TypeError):
                    return {}
        return {}

    def get_screening_profile(self) -> dict:
        """Return explicit screening calibration for the active disease.

        Only an explicit disease configuration is valid. Missing profiles are
        intentionally returned as empty so coverage can block the run rather
        than silently borrowing another disease's calibration.
        """
        return cast(dict[str, Any], self.config.get("SCREENING_PROFILE", {}))

    def get_disease_risk_config(self) -> dict:
        """Return disease-specific risk configuration without lupus semantics."""
        return cast(
            dict[str, Any],
            self.config.get("DISEASE_SPECIFIC_RISK")
            or self.config.get("DRUG_INDUCED_LUPUS_RISK", {}),
        )

    def get_drug_induced_lupus_risk(self) -> dict:
        """Compatibility alias for the disease-neutral risk configuration."""
        return self.get_disease_risk_config()

    def coverage(
        self,
        module: str = "core",
        required_inputs: Sequence[str] = (),
        optional_inputs: Sequence[str] = (),
    ) -> ModuleCoverage:
        """Return strict coverage metadata for this disease/module."""
        from med_research.diseases.coverage import module_coverage

        return module_coverage(
            self.disease_id,
            module,
            tuple(required_inputs),
            tuple(optional_inputs),
        )

    def get_display_name(self) -> str:
        """Return the configured display name used in user-facing outputs."""
        return self.config.get("PIPELINE_LABEL") or self.profile.name or self.disease_id

    def get_drug_target_exclusions(self) -> set[str]:
        """Return entities that are assay targets rather than disease genes."""
        configured = self.config.get("DRUG_TARGET_EXCLUSIONS")
        if configured is not None:
            return {str(item) for item in configured}
        return (
            {"CD20", "IMPDH", "Calcineurin", "Glucocorticoid Receptor"}
            if self.disease_id == "sle"
            else set()
        )

    def get_pathway_keywords(self) -> list[str]:
        """Return broad terms used to match enrichment results to KG pathways."""
        configured = self.config.get("PATHWAY_KEYWORDS")
        if configured:
            return list(configured)
        terms = set()
        for pathway in self.load_pathways().get("pathways", []):
            terms.update(str(pathway.get("name", "")).lower().replace("/", " ").split())
        return sorted(term for term in terms if len(term) > 2)

    def get_mechanism_categories(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.config.get("MECHANISM_CATEGORIES", {}))

    def get_trial_query(self) -> str:
        """Return the ClinicalTrials.gov query configured for this disease."""
        return cast(str, self.config.get("TRIAL_QUERY") or self.profile.name or self.disease_id)

    def get_symptom_overlap_terms(self) -> list[str]:
        """Return disease symptoms used for adverse-event overlap scoring."""
        return list(self.get_symptoms())

    def get_disease_evidence(self, entity: dict) -> str:
        """Read disease-neutral evidence without cross-disease fallback leakage."""
        if entity.get("disease_evidence"):
            return cast(str, entity["disease_evidence"])
        # Legacy evidence keys are valid only for the legacy SLE data module.
        if self.disease_id == "sle":
            return cast(str, entity.get("lupus_evidence") or entity.get("sle_evidence", ""))
        return ""

    def get_gwas_search_terms(self) -> list[str]:
        """Return only explicitly curated GWAS Catalog trait terms.

        A missing list is a coverage gap. The profile name is intentionally
        not substituted because a broad display name can produce an
        uninterpretable or cross-disease GWAS query.
        """
        return cast(list[str], list(self.config.get("GWAS_SEARCH_TERMS") or []))

    # ── Static helpers ─────────────────────────────────────────────────

    def validate(self) -> dict:
        """Check that this disease's config is complete for pipeline use.

        Returns a dict of ``{field: status}`` where status is ``"ok"`` or a
        message describing what is missing/empty.
        """
        from med_research.exceptions import MissingDataError, SchemaValidationError

        checks: dict[str, str] = {}
        drug_count = 0
        try:
            drug_count = len(self.load_drugs().get("drugs", []))
        except Exception:
            drug_count = 0

        required = {
            "SYMPTOMS": self.get_symptoms(),
            "PUBMED_QUERIES": self.config.get("PUBMED_QUERIES", []),
            "TRIAL_QUERY": self.config.get("TRIAL_QUERY", ""),
            "GWAS_SEARCH_TERMS": self.config.get("GWAS_SEARCH_TERMS", []),
            "CAR_T_SCORES": self.get_car_t_scores(),
        }
        if drug_count > 0:
            required["DRUG_SAFETY_RISK"] = self.get_disease_risk_config()
        for name, value in required.items():
            if isinstance(value, dict):
                if value and any(value.values()):
                    checks[name] = "ok"
                else:
                    checks[name] = "empty"
            elif isinstance(value, (list, tuple)):
                checks[name] = "ok" if value else "empty"
            else:
                checks[name] = "ok" if value else "missing"

        for data_field, filename in (
            ("genes", "genes.json"),
            ("drugs", "drugs.json"),
            ("pathways", "pathways.json"),
            ("relationships", "relationships.json"),
            ("profile", "profile.json"),
        ):
            try:
                self.load_json(filename)
                checks[data_field] = "ok"
            except MissingDataError:
                checks[data_field] = "missing"
            except SchemaValidationError as exc:
                message = str(exc)
                if len(message) > 100:
                    message = message[:97] + "..."
                checks[data_field] = f"invalid: {message}"

        return checks

    @staticmethod
    def list_all() -> list[str]:
        global _ALL_DISEASES_CACHE
        if _ALL_DISEASES_CACHE is not None:
            return list(_ALL_DISEASES_CACHE)

        import med_research.diseases as diseases_pkg

        root = Path(diseases_pkg.__file__).parent
        from med_research.diseases.registry_quality import is_blocked_slug

        with os.scandir(root) as it:
            result = sorted(
                entry.name
                for entry in it
                if entry.is_dir()
                and not entry.name.startswith("_")
                and entry.name != "__pycache__"
                and os.path.isfile(os.path.join(entry.path, "__init__.py"))
                and not is_blocked_slug(entry.name)
            )
        _ALL_DISEASES_CACHE = result
        return list(result)

    @staticmethod
    def discover() -> dict[str, "Disease"]:
        """Discover and instantiate all available diseases."""
        return {did: Disease(did) for did in Disease.list_all()}

    def __repr__(self) -> str:
        return f"Disease({self.disease_id!r}, name={self.profile.name!r})"
