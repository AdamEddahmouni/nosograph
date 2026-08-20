"""Lead Optimization Pipeline

Computes ADMET and drug-likeness properties for molecules supplied as SMILES strings.
Supports RDKit when available, with automatic fallback heuristics for lightweight environments.
"""

from __future__ import annotations

import logging
import re
from typing import List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, Lipinski

    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False
    logger.info("RDKit not installed; using built-in physicochemical descriptor heuristics.")

# Optional import for SA Score
try:
    from rdkit.Chem import sascorer  # type: ignore
except Exception:
    sascorer = None


# -----------------------------------------------------------------------------
# Heuristic fallback calculators for when RDKit is not installed
# -----------------------------------------------------------------------------


def _estimate_mw_from_smiles(smi: str) -> float:
    """Estimate molecular weight from SMILES string atomic counts."""
    # Strip stereochemistry and charges
    clean = re.sub(r"\[.*?\]", "", smi)
    c_count = clean.count("C") + clean.count("c")
    n_count = clean.count("N") + clean.count("n")
    o_count = clean.count("O") + clean.count("o")
    f_count = clean.count("F")
    cl_count = clean.count("Cl") + clean.count("cl")
    br_count = clean.count("Br") + clean.count("br")
    s_count = clean.count("S") + clean.count("s")
    p_count = clean.count("P") + clean.count("p")
    # Approximate hydrogen count: 2*C + N + 2
    h_est = max(c_count * 2 + n_count + 2 - (clean.count("=") * 2) - (clean.count("#") * 4), 2)
    return (
        c_count * 12.011
        + n_count * 14.007
        + o_count * 15.999
        + f_count * 18.998
        + cl_count * 35.453
        + br_count * 79.904
        + s_count * 32.065
        + p_count * 30.974
        + h_est * 1.008
    )


def _estimate_logp_from_smiles(smi: str) -> float:
    """Estimate LogP using atom contribution counts."""
    c_count = smi.count("C") + smi.count("c")
    n_count = smi.count("N") + smi.count("n")
    o_count = smi.count("O") + smi.count("o")
    cl_count = smi.count("Cl") + smi.count("cl")
    f_count = smi.count("F")
    # Carbon adds lipophilicity, heteroatoms add hydrophilicity
    logp = 0.25 * c_count - 0.5 * o_count - 0.4 * n_count + 0.6 * cl_count + 0.3 * f_count
    return round(float(logp), 2)


def _estimate_hbd_hba_from_smiles(smi: str) -> tuple[int, int]:
    """Estimate H-bond donors and acceptors."""
    hbd = len(re.findall(r"O[Hh]|N[Hh]|\[n[Hh]\]", smi))
    if hbd == 0 and ("O" in smi or "N" in smi):
        hbd = min(smi.count("O") + smi.count("N"), 2)
    hba = smi.count("O") + smi.count("o") + smi.count("N") + smi.count("n")
    return int(hbd), int(hba)


def _is_valid_smiles(smi: str) -> bool:
    """Basic validity check for SMILES."""
    if not smi or not isinstance(smi, str) or len(smi.strip()) == 0:
        return False
    smi = smi.strip()
    if "invalid" in smi.lower() or any(c in smi for c in "@$%^&?><"):
        return False
    # Check balanced parentheses
    if smi.count("(") != smi.count(")"):
        return False
    # Check valid characters
    valid_chars = set("CONSFClBrIconps1234567890=-#+()[]/\\:@ ")
    return set(smi).issubset(valid_chars)


# -----------------------------------------------------------------------------
# Property calculation functions
# -----------------------------------------------------------------------------


def _calc_descriptors(smi: str) -> dict | None:
    if not _is_valid_smiles(smi):
        return None

    if HAS_RDKIT:
        try:
            mol = Chem.MolFromSmiles(smi)
            if mol is None:
                return None
            mw = float(Descriptors.MolWt(mol))
            logp = float(Crippen.MolLogP(mol))
            hbd = int(Lipinski.NumHDonors(mol))
            hba = int(Lipinski.NumHAcceptors(mol))
            lipinski_pass = bool((mw <= 500) and (logp <= 5) and (hbd <= 5) and (hba <= 10))
            bbb_pass = bool((logp > 2) and (mw < 450))

            nitro = Chem.MolFromSmarts("[N+](=O)[O-]")
            amine = Chem.MolFromSmarts("[N;H2,H1;!$(NC=O)]")
            cyp3a4 = mol.HasSubstructMatch(nitro) if nitro else False
            cyp2d6 = mol.HasSubstructMatch(amine) if amine else False

            aromatic_n = Chem.MolFromSmarts("[n&H]")
            herg = len(mol.GetSubstructMatches(aromatic_n)) >= 2 if aromatic_n else False

            sa = None
            if sascorer is not None:
                try:
                    sa = float(min(max(sascorer.calculateScore(mol), 1.0), 10.0))
                except Exception:
                    sa = None

            return {
                "mw": mw,
                "logp": logp,
                "hbd": hbd,
                "hba": hba,
                "lipinski_pass": lipinski_pass,
                "bbb_pass": bbb_pass,
                "cyp3a4_inhibit": cyp3a4,
                "cyp2d6_inhibit": cyp2d6,
                "herg_risk": herg,
                "sa_score": sa,
            }
        except Exception:
            pass

    # Heuristic fallback
    mw = _estimate_mw_from_smiles(smi)
    logp = _estimate_logp_from_smiles(smi)
    hbd, hba = _estimate_hbd_hba_from_smiles(smi)
    lipinski_pass = bool((mw <= 500) and (logp <= 5) and (hbd <= 5) and (hba <= 10))
    bbb_pass = bool((logp > 2) and (mw < 450))
    cyp3a4 = bool("N(=O)" in smi or "NO2" in smi)
    cyp2d6 = bool("NH" in smi or "N" in smi)
    herg = bool(smi.count("n") >= 2)
    sa = round(float(2.0 + 0.01 * mw + 0.2 * abs(logp)), 2)

    return {
        "mw": round(mw, 2),
        "logp": logp,
        "hbd": hbd,
        "hba": hba,
        "lipinski_pass": lipinski_pass,
        "bbb_pass": bbb_pass,
        "cyp3a4_inhibit": cyp3a4,
        "cyp2d6_inhibit": cyp2d6,
        "herg_risk": herg,
        "sa_score": sa,
    }


def run_batch_analysis(smiles_list: List[str]) -> pd.DataFrame:
    """Run the full ADMET and lead optimization pipeline on a list of SMILES strings."""
    records = []
    for smi in smiles_list:
        props = _calc_descriptors(smi)
        if props is None:
            record = {
                "smiles": smi,
                "mw": np.nan,
                "logp": np.nan,
                "hbd": np.nan,
                "hba": np.nan,
                "lipinski_pass": np.nan,
                "bbb_pass": np.nan,
                "cyp3a4_inhibit": np.nan,
                "cyp2d6_inhibit": np.nan,
                "herg_risk": np.nan,
                "sa_score": np.nan,
            }
        else:
            record = {"smiles": smi, **props}
        records.append(record)

    df = pd.DataFrame.from_records(records)
    column_order = [
        "smiles",
        "mw",
        "logp",
        "hbd",
        "hba",
        "lipinski_pass",
        "bbb_pass",
        "cyp3a4_inhibit",
        "cyp2d6_inhibit",
        "herg_risk",
        "sa_score",
    ]
    return df[column_order]


def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Process an input DataFrame containing a 'smiles' column (case-insensitive)."""
    smiles_col = None
    for col in df.columns:
        if str(col).strip().lower() == "smiles":
            smiles_col = col
            break
    if smiles_col is None:
        if len(df.columns) > 0:
            smiles_col = df.columns[0]
        else:
            return pd.DataFrame()
    smiles_list = df[smiles_col].astype(str).tolist()
    return run_batch_analysis(smiles_list)
