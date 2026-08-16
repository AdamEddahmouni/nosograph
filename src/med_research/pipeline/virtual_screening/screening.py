"""
Lupus Virtual Drug Screening Engine

Screens compound libraries against lupus protein targets using:
  1. Molecular property scoring (drug-likeness, Lipinski Rule of 5)
  2. Target complementarity (pathway/category matching)
  3. Molecular similarity to known SLE therapeutics
  4. Optional AutoDock Vina molecular docking (if binary available)

Scoring Dimensions (each 0-10, weighted):
  - Binding Affinity Estimate: 30%
  - Drug-likeness: 20%
  - Target Complementarity: 25%
  - Similarity to Known SLE Drugs: 15%
  - Novelty: 10%

Usage:
    python screening.py                          # Full screening
    python screening.py --gene BTK               # Screen against BTK only
    python screening.py --top 15 --export-html    # Top 15 + HTML report
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

try:
    import numpy as np  # noqa: F401

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

import logging
from typing import Any, Mapping, cast

from med_research.diseases.schemas import DrugDict, GeneDict
from med_research.pipeline.knowledge_graph.config import (
    load_drugs as config_load_drugs,
)
from med_research.pipeline.knowledge_graph.config import (
    load_genes as config_load_genes,  # noqa: E402
)
from med_research.pipeline.progress import StandardProgress, _tick, cli_progress  # noqa: E402
from med_research.pipeline.results import (  # noqa: E402
    ScreeningCompound,
    ScreeningResult,
    ScreeningTarget,
)

# The legacy SLE repurposing cache lives beside the pipeline modules.  Keep
# this path scoped to the SLE compatibility branch; non-SLE scoring never
# consults it.
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = Path(__file__).parent / "data"

logger = logging.getLogger(__name__)
# ── Optional RDKit / AutoDock Vina detection ────────────────────────────

RDKIT_AVAILABLE = False
VINA_AVAILABLE = False
_DOCKING_ENGINE: Any = None


def _check_rdkit():
    """Lazy-check if RDKit is installed."""
    global RDKIT_AVAILABLE
    if not RDKIT_AVAILABLE:
        try:
            from rdkit import Chem  # noqa: F401
            from rdkit.Chem import Crippen, Descriptors, Lipinski  # noqa: F401

            RDKIT_AVAILABLE = True
        except ImportError:
            pass
    return RDKIT_AVAILABLE


def _get_docking_engine():
    """Lazy-load the DockingEngine singleton."""
    global _DOCKING_ENGINE
    if _DOCKING_ENGINE is None:
        try:
            from med_research.pipeline.virtual_screening.docking import DockingEngine

            _DOCKING_ENGINE = DockingEngine()
        except ImportError:
            _DOCKING_ENGINE = False
    return _DOCKING_ENGINE if _DOCKING_ENGINE is not False else None


def _compute_rdkit_properties(smiles: str) -> dict:
    """Compute molecular properties from SMILES using RDKit.

    Returns dict with mw, logp, hbd, hba, rotb, tpsa or empty dict on failure.
    """
    if not smiles or not _check_rdkit():
        return {}
    try:
        from rdkit import Chem
        from rdkit.Chem import Crippen, Descriptors, Lipinski

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return {}

        # RDKit re-exports these names from compiled rdMolDescriptors; mypy
        # sees the wrapper modules as bare ModuleType and cannot resolve the
        # attributes, so each access is annotated with the code it trips.
        return {
            "mw": round(Descriptors.MolWt(mol), 1),  # type: ignore[attr-defined]
            "logp": round(Crippen.MolLogP(mol), 2),  # type: ignore[attr-defined]
            "hbd": Lipinski.NumHDonors(mol),  # type: ignore[attr-defined]
            "hba": Lipinski.NumHAcceptors(mol),  # type: ignore[attr-defined]
            "rotb": Lipinski.NumRotatableBonds(mol),  # type: ignore[attr-defined]
            "tpsa": round(Descriptors.TPSA(mol), 1),  # type: ignore[attr-defined]
        }
    except (ValueError, TypeError, RuntimeError, AttributeError) as exc:
        logger.warning("RDKit property computation failed: %s", exc)
        return {}


# ── SMILES strings for KG drugs (real structures) ───────────────────

_DRUG_SMILES = {
    "hydroxychloroquine": "CCN(CCCC(C)NC1=C2C=CC(=CC2=NC=C1)Cl)CCO",
    "prednisone": "CC12CC(=O)C3C(C1CCC2(C(=O)CO)O)CCC4=CC(=O)C=CC34C",
    "mycophenolate": "CC1=C(C(=C(C(=C1OC)C)CC=C(C)C(=O)O)O)OC",
    "cyclophosphamide": "C1CN(P(=O)(OC1)N(CCCl)CCCl)",
    "tacrolimus": "C[C@@H]1C[C@@H]([C@@H]2[C@H](C[C@H]([C@@](O2)(C(=O)C(=O)N3CCCC[C@H]3C(=O)O[C@@H]([C@@H]([C@H](CC(=O)[C@H]([C@@H]([C@H](C[C@H](O1)C)C)/C=C(/C)\\C)O)C)O)C)C)C)O)OC",
    "azathioprine": "CN1C=NC(=C1SC2=NC=NC3=C2NC=N3)[N+](=O)[O-]",
    "baricitinib": "CCS(=O)(=O)CC1=NNC(=C1)C2=C3C=CNC3=NC(=N2)C4=CC=C(C=C4)S(=O)(=O)CC",
    "acalabrutinib": "CC#CC(=O)N1CCC[C@H]1C2=NC(=C3N2C=CC(=N3)C4=CC=C(C=C4)C(=O)N)C5=CC=C(C=C5)F",
    "avacopan": "CC1=CC(=CC(=C1)C(F)(F)F)NC(=O)C2=CC(=CC(=C2)NC(=O)C3=CC=C(C=C3)CN4CCN(CC4)C)C(F)(F)F",
    "cyclosporine": "CC[C@H](C)[C@@H]1NC(=O)[C@H](C)NC(=O)[C@H](C(C)C)NC(=O)[C@](C)(O)NC(=O)[C@@H](C)NC(=O)[C@H](C(C)C)NC(=O)[C@H](CC(C)C)NC(=O)[C@H](C(C)C)NC1=O",
    "dimethyl_fumarate": "COC(=O)/C=C/C(=O)OC",
    "tofacitinib": "C[C@@H]1CCN([C@@H]1C)CC2=CN=C(C=C2)NC3=NC=NC4=C3C=CN4",
    "voclosporin": "CC[C@H](C)[C@@H]1NC(=O)[C@H](C)NC(=O)[C@H](C(C)C)NC(=O)[C@H](CC(C)C)NC(=O)[C@H](C(C)C)NC(=O)[C@H](CC(C)C)NC1=O",
    "deucravacitinib": "CNC(=O)c1nnc(cc1Nc1cccc(c1OC)c1ncn(n1)C)NC(=O)C1CC1",
    "iberdomide": "O=C1CCC(C(=O)N1)N1Cc2c(C1=O)cccc2OCc1ccc(cc1)CN1CCOCC1",
}


def _check_vina():
    """Check if AutoDock Vina binary is on PATH (delegates to docking engine)."""
    global VINA_AVAILABLE
    if not VINA_AVAILABLE:
        engine = _get_docking_engine()
        if engine:
            status = engine.get_status()
            VINA_AVAILABLE = status.get("vina_available", False)
        else:
            vina_path = shutil.which("vina") or shutil.which("vina.exe")
            VINA_AVAILABLE = vina_path is not None
    return VINA_AVAILABLE


# ═══════════════════════════════════════════════════════════════════════
#  Compound Library
# ═══════════════════════════════════════════════════════════════════════

# Estimated molecular properties for each KG drug
# (MW, LogP, HBD, HBA, RotatableBonds, TPSA)
# These are approximate values for demonstration; real screening would
# compute these from SMILES using RDKit.

_DRUG_PROPERTIES = {
    "belimumab": {"mw": 147000, "logp": -10.0, "hbd": 120, "hba": 150, "rotb": 200, "tpsa": 5000},
    "anifrolumab": {"mw": 148000, "logp": -9.5, "hbd": 118, "hba": 148, "rotb": 195, "tpsa": 4900},
    "voclosporin": {"mw": 1215, "logp": 3.8, "hbd": 5, "hba": 14, "rotb": 8, "tpsa": 200},
    "hydroxychloroquine": {"mw": 336, "logp": 3.6, "hbd": 1, "hba": 3, "rotb": 8, "tpsa": 45},
    "mycophenolate": {"mw": 433, "logp": 1.8, "hbd": 2, "hba": 9, "rotb": 8, "tpsa": 125},
    "cyclophosphamide": {"mw": 261, "logp": 0.6, "hbd": 1, "hba": 4, "rotb": 5, "tpsa": 42},
    "rituximab": {"mw": 145000, "logp": -10.5, "hbd": 115, "hba": 145, "rotb": 198, "tpsa": 4800},
    "prednisone": {"mw": 358, "logp": 1.5, "hbd": 1, "hba": 5, "rotb": 2, "tpsa": 74},
    "tacrolimus": {"mw": 804, "logp": 4.3, "hbd": 3, "hba": 12, "rotb": 7, "tpsa": 178},
    "azathioprine": {"mw": 277, "logp": 0.1, "hbd": 0, "hba": 7, "rotb": 3, "tpsa": 101},
    "baricitinib": {"mw": 371, "logp": 1.7, "hbd": 2, "hba": 7, "rotb": 5, "tpsa": 112},
    "obinutuzumab": {
        "mw": 149000,
        "logp": -10.8,
        "hbd": 122,
        "hba": 152,
        "rotb": 202,
        "tpsa": 5100,
    },
    "acalabrutinib": {"mw": 465, "logp": 2.2, "hbd": 2, "hba": 7, "rotb": 5, "tpsa": 102},
    "avacopan": {"mw": 582, "logp": 3.9, "hbd": 2, "hba": 5, "rotb": 6, "tpsa": 78},
    "cyclosporine": {"mw": 1202, "logp": 3.5, "hbd": 5, "hba": 14, "rotb": 7, "tpsa": 195},
    "dimethyl_fumarate": {"mw": 144, "logp": 0.8, "hbd": 0, "hba": 4, "rotb": 4, "tpsa": 52},
    "iscalimab": {"mw": 146000, "logp": -10.2, "hbd": 116, "hba": 146, "rotb": 196, "tpsa": 4950},
    "ravulizumab": {"mw": 148000, "logp": -10.3, "hbd": 119, "hba": 149, "rotb": 199, "tpsa": 4970},
    "rozanolixizumab": {"mw": 50000, "logp": -7.0, "hbd": 70, "hba": 85, "rotb": 80, "tpsa": 3000},
    "tofacitinib": {"mw": 312, "logp": 1.2, "hbd": 1, "hba": 6, "rotb": 4, "tpsa": 89},
    "deucravacitinib": {"mw": 426, "logp": 2.5, "hbd": 2, "hba": 8, "rotb": 6, "tpsa": 120},
    "iberdomide": {"mw": 462, "logp": 2.1, "hbd": 1, "hba": 7, "rotb": 6, "tpsa": 95},
}


def load_kg_genes(disease_id: str = "sle") -> dict[str, GeneDict]:
    """Load gene data indexed by gene ID."""
    data = config_load_genes(disease_id)
    return {g["id"]: g for g in data["genes"]}


def load_kg_drugs(disease_id: str = "sle") -> dict[str, DrugDict]:
    """Load drug data indexed by drug ID."""
    data = config_load_drugs(disease_id)
    return {d["id"]: d for d in data["drugs"]}


def build_compound_library(disease_id: str = "sle") -> list[ScreeningCompound]:
    """Build a compound library from KG drugs with RDKit-computed or estimated properties.

    If RDKit is available, computes MW, LogP, HBD, HBA, RotB, TPSA from SMILES.
    Otherwise falls back to estimated properties for biologics and small molecules.
    """
    drugs = load_kg_drugs(disease_id)
    library: list[ScreeningCompound] = []

    for drug_id, drug_info in drugs.items():
        smiles = _DRUG_SMILES.get(drug_id, "")
        props = _DRUG_PROPERTIES.get(drug_id, {})

        # If RDKit available and we have SMILES, compute real properties (once)
        rdkit_props = {}
        if smiles and _check_rdkit():
            rdkit_props = _compute_rdkit_properties(smiles)
            if rdkit_props:
                props = rdkit_props

        compound: ScreeningCompound = {
            "id": drug_id,
            "name": drug_info["name"],
            "type": drug_info.get("type", ""),
            "target": drug_info.get("target", ""),
            "mechanism": drug_info.get("mechanism", ""),
            "category": drug_info.get("category", ""),
            "smiles": smiles,
            "mw": props.get("mw", 400),
            "logp": props.get("logp", 2.0),
            "hbd": int(props.get("hbd", 2)),
            "hba": int(props.get("hba", 5)),
            "rotb": int(props.get("rotb", 5)),
            "tpsa": props.get("tpsa", 100),
            "rdkit_computed": bool(rdkit_props),
        }
        library.append(compound)

    return library


# ═══════════════════════════════════════════════════════════════════════
#  Lipinski, PAINS, and Vina Helpers
# ═══════════════════════════════════════════════════════════════════════

PAINS_PATTERNS = [
    ("quinone", "Quinone or quinone-methide substructure"),
    ("rhodanine", "Rhodanine core / promiscuous chelator"),
    ("alkyl_halide", "Reactive alkyl halide electrophile"),
    ("curcumin_analogue", "Curcuminoid conjugated enone"),
    ("isothiazolone", "Thiol-reactive isothiazolone"),
]


def evaluate_lipinski_rule_of_five(compound: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate Lipinski Rule of 5 parameters and return violation breakdown."""
    mw = float(compound.get("mw", 400.0))
    logp = float(compound.get("logp", 2.0))
    hbd = int(compound.get("hbd", 2))
    hba = int(compound.get("hba", 5))
    rotatable_bonds = int(compound.get("rotatable_bonds", 5))

    violations: list[str] = []
    if mw > 500.0:
        violations.append(f"MW > 500 ({mw:.1f})")
    if logp > 5.0:
        violations.append(f"LogP > 5.0 ({logp:.1f})")
    if hbd > 5:
        violations.append(f"HBD > 5 ({hbd})")
    if hba > 10:
        violations.append(f"HBA > 10 ({hba})")
    if rotatable_bonds > 10:
        violations.append(f"Rotatable Bonds > 10 ({rotatable_bonds})")

    return {
        "mw": mw,
        "logp": logp,
        "hbd": hbd,
        "hba": hba,
        "rotatable_bonds": rotatable_bonds,
        "violations": violations,
        "num_violations": len(violations),
        "is_drug_like": len(violations) <= 1,
    }


def check_pains_alerts(compound_name: str, smiles: str = "") -> dict[str, Any]:
    """Check for Pan-Assay Interference Compound (PAINS) flags."""
    alerts: list[str] = []
    lower_name = compound_name.lower()
    lower_smi = smiles.lower()
    for name_flag, desc in PAINS_PATTERNS:
        if name_flag in lower_name or name_flag in lower_smi:
            alerts.append(desc)
    return {
        "has_pains_alert": len(alerts) > 0,
        "pains_alerts": alerts,
    }


def generate_vina_search_box(
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    size: tuple[float, float, float] = (20.0, 20.0, 20.0),
    exhaustiveness: int = 8,
    num_modes: int = 9,
) -> dict[str, Any]:
    """Generate AutoDock Vina search bounding box configuration."""
    config_text = (
        f"center_x = {center[0]:.1f}\n"
        f"center_y = {center[1]:.1f}\n"
        f"center_z = {center[2]:.1f}\n"
        f"size_x = {size[0]:.1f}\n"
        f"size_y = {size[1]:.1f}\n"
        f"size_z = {size[2]:.1f}\n"
        f"exhaustiveness = {exhaustiveness}\n"
        f"num_modes = {num_modes}\n"
    )
    return {
        "center_x": center[0],
        "center_y": center[1],
        "center_z": center[2],
        "size_x": size[0],
        "size_y": size[1],
        "size_z": size[2],
        "exhaustiveness": exhaustiveness,
        "num_modes": num_modes,
        "config_text": config_text,
    }


def compute_druglikeness(compound: Mapping[str, Any]) -> float:
    """
    Score drug-likeness based on Lipinski's Rule of 5.

    Returns 0-10, where 10 means fully compliant.
    """
    violations = 0.0
    mw = compound.get("mw", 400)
    logp = compound.get("logp", 2.0)
    hbd = compound.get("hbd", 2)
    hba = compound.get("hba", 5)

    if mw > 500 and mw < 1000:
        violations += 0.5
    elif mw >= 1000:
        violations += 2  # biologics get a penalty

    if logp > 5:
        violations += 1
    if hbd > 5:
        violations += 1
    if hba > 10:
        violations += 1

    # Biologics (mAbs) get a separate scale
    if mw > 50000:
        # Biologics have different rules (no Lipinski)
        return 5.0  # neutral — they're valid but not small-molecule

    score = max(0.0, 10.0 - violations * 2.5)
    return round(min(10.0, score), 1)



def compute_target_complementarity(
    compound: Mapping[str, Any],
    gene_info: Mapping[str, Any],
    disease_id: str = "sle",
    strategy: Any = None,
) -> float:
    """Score disease-strategy vocabulary overlap with target biology.

    This remains a bounded heuristic.  The optional strategy argument avoids
    repeatedly resolving configuration inside the screening loop while the
    disease_id default preserves legacy callers.
    """
    if strategy is None:
        from med_research.pipeline.virtual_screening.screening_strategy import strategy_for_disease

        strategy = strategy_for_disease(disease_id)

    def _text(value: object) -> str:
        return " ".join(str(value or "").lower().replace("/", " ").split())

    gene_category = _text(gene_info.get("category"))
    gene_function = _text(gene_info.get("function"))
    gene_name = _text(gene_info.get("name"))
    gene_text = f"{gene_category} {gene_function} {gene_name}"
    drug_text = " ".join(
        _text(compound.get(field)) for field in ("mechanism", "target", "category")
    )

    score = 2.0
    pathway_hits = sum(1 for keyword in strategy.pathway_keywords if _text(keyword) in gene_text)
    mechanism_hits = sum(
        1 for keyword in strategy.mechanism_keywords if _text(keyword) in drug_text
    )
    score += min(pathway_hits * 1.0, 3.0)
    score += min(mechanism_hits * 1.0, 4.0)

    function_words = {word for word in gene_function.split() if len(word) > 4}
    mechanism_words = set(drug_text.split())
    score += min(len(function_words & mechanism_words) * 1.5, 3.0)
    return round(min(10.0, score), 1)


def compute_similarity_score(
    compound: Mapping[str, Any],
    gene_info: Mapping[str, Any],
    disease_id: str = "sle",
    strategy: Any = None,
) -> float:
    """
    Estimate molecular similarity to known drugs for this disease/target.

    Based on the active disease's reference drugs, property similarity, and
    mechanism overlap. The shared legacy candidate file is consulted only for
    backwards-compatible SLE calls; non-SLE scoring is strictly disease-scoped.
    """
    if strategy is None:
        from med_research.pipeline.virtual_screening.screening_strategy import strategy_for_disease

        strategy = strategy_for_disease(disease_id)

    # Find known drugs targeting this gene or pathway
    gene_id = gene_info.get("id", "")
    if disease_id == "sle":
        # Preserve the legacy SLE candidate behavior for existing callers;
        # non-SLE diseases never read this shared SLE-only dataset.
        try:
            candidates_data = json.loads(
                (PROJECT_ROOT / "drug_repurposing" / "data" / "candidates.json").read_text(
                    encoding="utf-8"
                )
            )
            existing_candidates = candidates_data.get("repurposing_candidates", [])
        except (FileNotFoundError, json.JSONDecodeError):
            existing_candidates = []
        same_gene_candidates = [
            {
                "name": c.get("drug_name", ""),
                "category": c.get("drug_category", ""),
            }
            for c in existing_candidates
            if c.get("gene_id") == gene_id
        ]
    else:
        # A direct score without a compound ID cannot match a curated
        # reference, so remain neutral without reading any catalog.
        if not compound.get("id"):
            return 3.0
        # Compare only against the active disease's curated reference library.
        # The shared SLE candidate cache is never read in this branch.
        active_drugs = load_kg_drugs(disease_id)
        same_gene_candidates = [
            dict(drug)
            for drug_id, drug in active_drugs.items()
            if drug_id in strategy.reference_drug_ids
            and gene_id
            and gene_id.lower()
            in " ".join(
                str(drug.get(field, "")) for field in ("target", "mechanism", "category")
            ).lower()
        ]

    if not same_gene_candidates:
        return 3.0  # no known reference — neutral

    # Higher score if this compound is one of the candidates
    compound_name = compound.get("name", "").lower()
    for c in same_gene_candidates:
        if c.get("name", "").lower().split("(")[0].strip() in compound_name:
            return 8.0  # this compound IS a known candidate for this gene

    # Compound type similarity
    compound_category = compound.get("category", "").lower()
    for c in same_gene_candidates:
        candidate_cat = c.get("category", "").lower()
        # Simple category overlap
        if compound_category and candidate_cat:
            cat_words_a = set(compound_category.split())
            cat_words_b = set(candidate_cat.split())
            overlap = len(cat_words_a & cat_words_b)
            if overlap > 0:
                return min(5.0 + overlap * 1.5, 10.0)

    return 3.0


def compute_binding_estimate(compound: Mapping[str, Any], gene_info: Mapping[str, Any]) -> float:
    """
    Estimate binding affinity based on molecular properties.

    Simplified scoring function inspired by AutoDock Vina's scoring:
    - Steric complementarity (MW fitting)
    - Hydrogen bonding potential
    - Hydrophobic matching (LogP)

    Returns a pseudo-binding score 0-10.
    """
    mw = compound.get("mw", 400)
    logp = compound.get("logp", 2.0)
    hbd = compound.get("hbd", 2)
    hba = compound.get("hba", 5)
    tpsa = compound.get("tpsa", 100)

    score = 5.0  # baseline

    # Large biologics can't be "docked" meaningfully
    if mw > 50000:
        return 3.0

    # MW preference: ideal range 200-600 Da for small molecules
    if 200 <= mw <= 600:
        score += 2.0
    elif 100 <= mw <= 800:
        score += 1.0
    elif mw > 800:
        score -= 1.0

    # LogP: ideal range 1-4
    if 1 <= logp <= 4:
        score += 1.5
    elif 0 <= logp <= 5:
        score += 0.5

    # Hydrogen bonding: balanced HBD/HBA
    if 1 <= hbd <= 4 and 2 <= hba <= 8:
        score += 1.5

    # TPSA: ideal < 140 Å² for oral bioavailability
    if tpsa < 140:
        score += 1.0

    return round(max(0.0, min(10.0, score)), 1)


def compute_novelty_score(
    compound: Mapping[str, Any],
    gene_info: Mapping[str, Any],
    disease_id: str = "sle",
    strategy: Any = None,
) -> float:
    """
    Score how novel this compound-target pairing is.

    Already-approved drugs for the active disease get low novelty.
    Investigational or off-label drugs get high novelty.
    """
    if strategy is None:
        from med_research.pipeline.virtual_screening.screening_strategy import strategy_for_disease

        strategy = strategy_for_disease(disease_id)

    compound_category = compound.get("category", "").lower()

    if "approved" in compound_category or "standard of care" in compound_category:
        from med_research.diseases.base import Disease

        disease_name = Disease(disease_id).profile.name.lower()
        disease_terms = {disease_id.lower(), disease_name}
        if any(term in compound_category for term in disease_terms):
            return 2.0
        return 4.0

    if "investigational" in compound_category or "phase" in compound_category:
        return 8.0

    if "off-label" in compound_category:
        return 7.0

    return 5.0


def compute_composite_score(scores: dict, weights: dict | None = None) -> float:
    """Compute a bounded weighted composite score."""
    if weights is None:
        weights = {
            "binding_estimate": 0.30,
            "druglikeness": 0.20,
            "target_complementarity": 0.25,
            "similarity_score": 0.15,
            "novelty_score": 0.10,
        }
    from med_research.pipeline.virtual_screening.screening_strategy import normalized_weights

    weights = normalized_weights(weights)
    composite = sum(float(scores[key]) * weights[key] for key in weights)
    return round(max(0.0, min(10.0, composite)), 2)


# ═══════════════════════════════════════════════════════════════════════
#  AutoDock Vina Integration (delegates to docking.py)
# ═══════════════════════════════════════════════════════════════════════


def get_vina_status() -> str:
    """Get a human-readable Vina availability status."""
    engine = _get_docking_engine()
    if engine:
        try:
            from med_research.pipeline.virtual_screening.docking import get_vina_status_text

            return get_vina_status_text()
        except ImportError:
            pass
    if _check_vina():
        vina_path = shutil.which("vina") or shutil.which("vina.exe")
        return f"active ({vina_path})"
    return "not available (install AutoDock Vina for molecular docking)"


# ═══════════════════════════════════════════════════════════════════════
#  Screening Pipeline
# ═══════════════════════════════════════════════════════════════════════


def screen_compounds(
    target_genes: list | None = None,
    compound_library: list[ScreeningCompound] | None = None,
    top_n: int = 15,
    use_vina: bool = False,
    disease_id: str = "sle",
    progress_callback: StandardProgress | None = None,
) -> ScreeningResult:
    """
    Run virtual screening of all compounds against all target genes.

    Args:
        target_genes: List of gene IDs to screen against (None = all untargeted)
        compound_library: Pre-built compound library (None = auto-build)
        top_n: Number of top results per target
        use_vina: Attempt AutoDock Vina docking
        disease_id: Disease whose KG genes/drugs are screened.

    Returns:
        dict with screening_results, targets, library, stats
    """
    from med_research.diseases.coverage import module_coverage

    coverage = module_coverage(
        disease_id,
        "screening",
        ("genes", "drugs", "pathways", "screening_profile"),
    )
    try:
        from med_research.pipeline.virtual_screening.screening_strategy import (
            strategy_fingerprint,
            strategy_for_disease,
        )

        strategy = strategy_for_disease(disease_id)
        strategy_id = strategy.strategy_id
        strategy_hash = strategy_fingerprint(strategy)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        coverage = coverage.__class__(
            disease_id=disease_id,
            module="screening",
            level="unsupported",
            status="blocked",
            curated_inputs=list(coverage.curated_inputs),
            missing_inputs=["screening_profile"],
            limitations=[f"Screening strategy is invalid: {exc}"],
        )
        strategy = None
        strategy_id = ""
        strategy_hash = ""
    if not coverage.is_runnable:
        return cast(
            ScreeningResult,
            {
                "results_per_target": {},
                "all_results": [],
                "target_genes": [],
                "compound_library": [],
                "coverage": coverage.to_dict(),
                "status": "blocked",
                "disease_id": disease_id,
                "strategy_id": strategy_id,
                "strategy_fingerprint": strategy_hash,
                "strategy_limitations": list(strategy.limitations) if strategy else [],
                "stats": {
                    "targets_screened": 0,
                    "compounds_screened": 0,
                    "total_pairings": 0,
                    "tier1_count": 0,
                    "tier2_count": 0,
                    "vina_available": False,
                    "rdkit_available": _check_rdkit(),
                    "vina_status": get_vina_status(),
                },
            },
        )

    assert strategy is not None  # strategy failures are captured by the coverage gate above

    if compound_library is None:
        compound_library = build_compound_library(disease_id)

    all_genes = load_kg_genes(disease_id)
    untargeted_genes = get_untargeted_genes(disease_id)

    if target_genes:
        gene_ids = [g for g in target_genes if g in all_genes]
    else:
        gene_ids = [g["id"] for g in untargeted_genes]

    if not gene_ids:
        gene_ids = [g["id"] for g in untargeted_genes[:5]]

    results_per_target = {}
    all_scored = []

    for gene_idx, gene_id in enumerate(gene_ids, 1):
        _tick(progress_callback, "screening compounds", gene_idx, len(gene_ids))
        gene_info = all_genes.get(gene_id, {"id": gene_id, "name": gene_id})
        scored_compounds = []

        for compound in compound_library:
            scores = {
                "binding_estimate": compute_binding_estimate(compound, gene_info),
                "druglikeness": compute_druglikeness(compound),
                "target_complementarity": compute_target_complementarity(
                    compound, gene_info, disease_id, strategy
                ),
                "similarity_score": compute_similarity_score(
                    compound, gene_info, disease_id, strategy
                ),
                "novelty_score": compute_novelty_score(compound, gene_info, disease_id, strategy),
            }
            composite = compute_composite_score(scores, strategy.weights)

            result: dict[str, Any] = {
                **cast(dict[str, Any], compound),
                **scores,
                "composite_score": composite,
                "gene_id": gene_id,
                "gene_name": gene_info.get("name", gene_id),
                "gene_category": gene_info.get("category", ""),
                "disease_id": disease_id,
                "strategy_id": strategy_id,
                "strategy_fingerprint": strategy_hash,
            }

            # Assign tier
            if composite >= 7.5:
                result["tier"] = "🔴 Tier 1 — Strong Candidate"
            elif composite >= 6.5:
                result["tier"] = "🟠 Tier 2 — Promising"
            elif composite >= 5.0:
                result["tier"] = "🟡 Tier 3 — Possible"
            else:
                result["tier"] = "🟢 Tier 4 — Low Priority"

            scored_compounds.append(result)
            all_scored.append(result)

        # Vina docking (optional) — uses real docking engine
        vina_results = {}
        if use_vina and _check_vina():
            engine = _get_docking_engine()
            if engine:
                from med_research.pipeline.virtual_screening.docking import (
                    compute_real_binding_score,
                )

                # Pre-filter top candidates by property scores
                scored_compounds.sort(key=lambda x: x["composite_score"], reverse=True)
                top_for_docking = scored_compounds[: min(5, len(scored_compounds))]

                logger.info(
                    f"   🧬 Running Vina docking for {gene_info.get('name', gene_id)} "
                    f"({len(top_for_docking)} top compounds)..."
                )

                # Prepare receptor and ligands on-demand
                rec_paths = engine.prepare_all_targets()
                lig_paths = engine.prepare_all_ligands(compound_library)

                dock_results = engine.dock_target(
                    gene_id=gene_id,
                    ligand_ids=[c["id"] for c in top_for_docking],
                    receptor_paths=rec_paths,
                    ligand_paths=lig_paths,
                    max_workers=2,
                )

                # Merge real docking scores into scored compounds
                for hit in top_for_docking:
                    real_score = compute_real_binding_score(hit, gene_id, dock_results)
                    if real_score is not None:
                        # Replace property-based binding estimate with real score
                        hit["binding_estimate"] = real_score
                        hit["vina_docked"] = True
                        hit["vina_best_kcal"] = dock_results.get(hit["id"], {}).get("best_score")
                        # Recompute composite with real binding score
                        hit["composite_score"] = compute_composite_score(
                            {
                                "binding_estimate": real_score,
                                "druglikeness": hit["druglikeness"],
                                "target_complementarity": hit["target_complementarity"],
                                "similarity_score": hit["similarity_score"],
                                "novelty_score": hit["novelty_score"],
                            },
                            strategy.weights,
                        )
                        # Reassign tier
                        if hit["composite_score"] >= 7.5:
                            hit["tier"] = "🔴 Tier 1 — Strong Candidate"
                        elif hit["composite_score"] >= 6.5:
                            hit["tier"] = "🟠 Tier 2 — Promising"
                        elif hit["composite_score"] >= 5.0:
                            hit["tier"] = "🟡 Tier 3 — Possible"
                        else:
                            hit["tier"] = "🟢 Tier 4 — Low Priority"

                vina_results = dock_results

        # Sort and take top N
        scored_compounds.sort(key=lambda x: x["composite_score"], reverse=True)
        results_per_target[gene_id] = {
            "gene_info": gene_info,
            "top_compounds": scored_compounds[:top_n],
            "vina_results": vina_results,
            "total_screened": len(compound_library),
            "mean_score": round(
                sum(c["composite_score"] for c in scored_compounds) / len(scored_compounds), 2
            )
            if scored_compounds
            else 0,
        }

    all_scored.sort(key=lambda x: x["composite_score"], reverse=True)

    # Stats
    n_tier1 = sum(1 for c in all_scored if c["tier"].startswith("🔴"))
    n_tier2 = sum(1 for c in all_scored if c["tier"].startswith("🟠"))
    n_vina_docked = sum(1 for c in all_scored if c.get("vina_docked"))

    return cast(
        ScreeningResult,
        {
            "results_per_target": results_per_target,
            "all_results": all_scored,
            "target_genes": gene_ids,
            "compound_library": compound_library,
            "coverage": coverage.to_dict(),
            "status": "ready" if coverage.level == "full" else "limited_coverage",
            "disease_id": disease_id,
            "strategy_id": strategy_id,
            "strategy_fingerprint": strategy_hash,
            "strategy_limitations": list(strategy.limitations),
            "stats": {
                "targets_screened": len(gene_ids),
                "compounds_screened": len(compound_library),
                "total_pairings": len(all_scored),
                "tier1_count": n_tier1,
                "tier2_count": n_tier2,
                "vina_docked_count": n_vina_docked,
                "vina_available": _check_vina(),
                "rdkit_available": _check_rdkit(),
                "vina_status": get_vina_status(),
            },
        },
    )


def get_untargeted_genes(disease_id: str = "sle") -> list[ScreeningTarget]:
    """Identify genes with no direct targeted therapy in a disease's KG."""
    try:
        from med_research.pipeline.knowledge_graph.builder import build_graph

        G = build_graph(disease_id)

        targeted = set()
        for _u, v, d in G.edges(data=True):
            if d.get("type") == "TARGETS" and G.nodes[v].get("type") == "gene":
                targeted.add(v)

        all_genes = load_kg_genes(disease_id)
        untargeted = []
        for gene_id, gene_info in all_genes.items():
            if gene_id not in targeted:
                untargeted.append(
                    {
                        "id": gene_id,
                        "name": gene_info["name"],
                        "category": gene_info.get("category", ""),
                        "function": gene_info.get("function", ""),
                    }
                )

        # Exclude assay targets only when the active disease explicitly marks
        # them as non-disease genes.
        from med_research.diseases.base import Disease

        excluded = Disease(disease_id).get_drug_target_exclusions()
        untargeted = [g for g in untargeted if g["id"] not in excluded]

        return cast(list[ScreeningTarget], untargeted)
    except (FileNotFoundError, OSError, KeyError, TypeError, AttributeError, ValueError) as exc:
        logger.warning("Could not load KG for untargeted gene detection: %s", exc)
        return cast(list[ScreeningTarget], [])


# ═══════════════════════════════════════════════════════════════════════
#  Summary & CLI
# ═══════════════════════════════════════════════════════════════════════


def print_summary(results: Mapping[str, Any]) -> None:
    """Print a summary of virtual screening results."""
    stats = results["stats"]

    if results.get("status") == "blocked":
        coverage = results.get("coverage", {})
        logger.error(
            f"\n❌ Virtual screening blocked: {coverage.get('limitations', ['missing disease-specific strategy'])[0]}"
        )
        return

    logger.info("\n" + "=" * 70)
    logger.info("🔬 VIRTUAL DRUG SCREENING RESULTS")
    logger.info("=" * 70)

    logger.info(f"\n  Targets screened:        {stats['targets_screened']}")
    logger.info(f"  Compounds screened:      {stats['compounds_screened']}")
    logger.info(f"  Total pairings scored:   {stats['total_pairings']}")
    logger.info(f"  Tier 1 candidates:       {stats['tier1_count']} (≥7.5)")
    logger.info(f"  Tier 2 candidates:       {stats['tier2_count']} (6.5-7.4)")
    logger.info(f"  AutoDock Vina:           {stats['vina_status']}")
    logger.info(
        f"  RDKit:                   {'available' if stats['rdkit_available'] else 'not available'}"
    )
    if results.get("strategy_id"):
        logger.info(
            f"  Strategy:                {results['strategy_id']} ({results.get('strategy_fingerprint', '')[:16]}…)"
        )

    # Top results per target
    logger.info("\n  📋 Top compound per target:")
    for gene_id, target_data in sorted(results["results_per_target"].items()):
        gene_name = target_data["gene_info"].get("name", gene_id)
        top = target_data["top_compounds"]
        if top:
            best = top[0]
            logger.info(
                f"    • {gene_name[:45]:<47} "
                f"{best['name'][:30]:<32} "
                f"Score: {best['composite_score']:.1f}"
            )

    # Top 10 overall
    logger.info("\n  🏆 Top 10 overall virtual screening hits:")
    for i, c in enumerate(results["all_results"][:10], 1):
        logger.info(
            f"    {i:2}. {c['name'][:40]:<42} "
            f"→ {c['gene_name'][:25]:<27} "
            f"{c['composite_score']:.1f} ({c['tier'].split('—')[0].strip()})"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Lupus Virtual Drug Screening Engine — Compound library screening"
    )
    parser.add_argument(
        "--gene",
        type=str,
        help="Screen against a specific gene ID (e.g. BTK, TYK2)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=15,
        help="Number of top compounds per target (default: 15)",
    )
    parser.add_argument(
        "--export-html",
        action="store_true",
        help="Generate HTML report",
    )
    parser.add_argument(
        "--use-vina",
        action="store_true",
        help="Run AutoDock Vina docking (requires Vina binary)",
    )
    parser.add_argument(
        "--disease",
        "-d",
        default="sle",
        help="Disease ID (default: sle)",
    )
    args = parser.parse_args()

    logger.info(f"🔄 Building compound library ({args.disease})...")
    from med_research.pipeline.virtual_screening.screening_strategy import strategy_for_disease

    try:
        strategy_for_disease(args.disease)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        logger.error(f"❌ Screening blocked for {args.disease}: {exc}")
        return 1

    library = build_compound_library(args.disease)
    logger.info(f"   {len(library)} compounds loaded")

    logger.info(f"🔄 Identifying untargeted {args.disease} genes...")
    untargeted = get_untargeted_genes(args.disease)
    target_ids = [g["id"] for g in untargeted]
    logger.info(f"   {len(untargeted)} untargeted genes identified")

    if args.gene:
        target_ids = [args.gene]
        logger.info(f"   🎯 Screening against: {args.gene}")

    logger.info("🔄 Running virtual screening...")
    results = screen_compounds(
        target_genes=target_ids,
        compound_library=library,
        top_n=args.top,
        use_vina=args.use_vina,
        disease_id=args.disease,
        progress_callback=cli_progress,
    )

    print_summary(results)

    # Save results
    os.makedirs(DATA_DIR, exist_ok=True)
    output_path = DATA_DIR / "screening_results.json"
    output_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.info(f"\n💾 Results saved to {output_path}")

    if args.export_html:
        from med_research.pipeline.provenance import build_provenance
        from med_research.pipeline.virtual_screening.report import generate_screening_report

        provenance = build_provenance(
            disease_id=args.disease,
            module="virtual_screening",
            sources=["knowledge_graph"],
            cache_or_live="cache",
            scoring={
                "strategy_id": results.get("strategy_id", ""),
                "strategy_fingerprint": results.get("strategy_fingerprint", ""),
            },
        )
        report_path = generate_screening_report(
            results, disease_id=args.disease, provenance=provenance
        )
        logger.info(f"✅ HTML report generated: {report_path}")

    return results


if __name__ == "__main__":
    import sys

    from med_research.cli import main as cli_main

    sys.exit(cli_main() or 0)
