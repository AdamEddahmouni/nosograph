"""Knowledge Graph configuration and disease-aware data path resolution."""

import json
from pathlib import Path

DATA_ROOT = Path(__file__).parent.parent.parent / "diseases"

KNOWN_DISEASES: dict = {}
_DISEASE_DATA_CACHE: dict = {}


def _discover_diseases() -> dict:
    """Scan diseases/ subdirectories for data/profile.json and build disease registry."""
    diseases = {}
    for child in DATA_ROOT.iterdir():
        if child.is_dir() and (child / "__init__.py").exists():
            data_dir = child / "data"
            profile_path = data_dir / "profile.json"
            if profile_path.exists():
                profile = json.loads(profile_path.read_text(encoding="utf-8"))
                diseases[profile["id"]] = {
                    "id": profile["id"],
                    "name": profile["name"],
                    "data_dir": data_dir,
                    "profile": profile,
                }
    return diseases


def _resolve(disease_id: str = None) -> Path:
    """Resolve the data directory for a disease, defaulting to SLE.

    Returns the Path to the disease-specific data subdirectory, e.g.
    ``diseases/sle/data/``.
    """
    disease_id = disease_id or "sle"
    return DATA_ROOT / disease_id / "data"


def list_diseases() -> dict:
    """Return {disease_id: {id, name, data_dir, profile}, ...} for all known diseases."""
    global KNOWN_DISEASES
    if not KNOWN_DISEASES:
        KNOWN_DISEASES = _discover_diseases()
    return KNOWN_DISEASES


def get_disease_profile(disease_id: str = "sle") -> dict:
    """Return the profile dict for a disease."""
    profile_path = _resolve(disease_id) / "profile.json"
    if profile_path.exists():
        return json.loads(profile_path.read_text(encoding="utf-8"))
    return {"id": disease_id, "name": disease_id}


def load_disease_json(disease_id: str, filename: str) -> dict:
    """Load a JSON data file for a given disease."""
    path = _resolve(disease_id) / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Data file not found: {path}. Do you need to run "
            f"'python main.py kg --disease {disease_id}'?"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_genes(disease_id: str = "sle") -> dict:
    return load_disease_json(disease_id, "genes.json")


def load_drugs(disease_id: str = "sle") -> dict:
    return load_disease_json(disease_id, "drugs.json")


def load_pathways(disease_id: str = "sle") -> dict:
    return load_disease_json(disease_id, "pathways.json")


def load_relationships(disease_id: str = "sle") -> dict:
    return load_disease_json(disease_id, "relationships.json")
