"""FastAPI router for In Silico Lead Optimization and ADMET screening."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from lead_opt.pipeline import _calc_descriptors, run_batch_analysis

router = APIRouter(prefix="/api/lead-opt", tags=["Lead Optimization"])
logger = logging.getLogger(__name__)


class SingleMoleculeRequest(BaseModel):
    smiles: str = Field(
        ...,
        description="SMILES string of candidate compound",
        examples=["CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"],
    )
    compound_name: Optional[str] = Field(default=None, description="Optional compound label")


class BatchMoleculesRequest(BaseModel):
    smiles_list: List[str] = Field(
        ..., min_length=1, max_length=500, description="List of SMILES strings"
    )


@router.post("/analyze")
async def analyze_molecule(req: SingleMoleculeRequest) -> Dict[str, Any]:
    """Calculate multi-parameter ADMET descriptors and lead-likeness for a single molecule."""
    props = _calc_descriptors(req.smiles)
    if props is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid SMILES string: '{req.smiles}' could not be parsed.",
        )

    # Compute a composite Drug-Likeness Score (0 - 100)
    score = 100.0
    if not props.get("lipinski_pass", False):
        score -= 25.0
    if props.get("cyp3a4_inhibit", False):
        score -= 15.0
    if props.get("cyp2d6_inhibit", False):
        score -= 15.0
    if props.get("herg_risk", False):
        score -= 25.0

    sa = props.get("sa_score")
    if sa and sa > 5.0:
        score -= (sa - 5.0) * 4.0

    score = max(round(score, 1), 0.0)

    return {
        "smiles": req.smiles,
        "compound_name": req.compound_name or "Compound",
        "composite_score": score,
        "properties": props,
        "admet_radar": {
            "Lipophilicity (LogP)": min(max(props.get("logp", 0) / 5.0, 0.0), 1.0),
            "Size (MW)": min(max(props.get("mw", 0) / 500.0, 0.0), 1.0),
            "Polar Surface / HBA": min(max(props.get("hba", 0) / 10.0, 0.0), 1.0),
            "H-Bond Donors": min(max(props.get("hbd", 0) / 5.0, 0.0), 1.0),
            "BBB Permeability": 1.0 if props.get("bbb_pass") else 0.2,
            "Safety (Low Toxicity)": 0.2
            if (props.get("herg_risk") or props.get("cyp3a4_inhibit"))
            else 0.9,
        },
    }


@router.post("/batch-screen")
async def batch_screen(req: BatchMoleculesRequest) -> Dict[str, Any]:
    """Batch screen multiple molecules and return ranked candidates with ADMET metrics."""
    df = run_batch_analysis(req.smiles_list)
    records = df.to_dict(orient="records")

    # Calculate composite score for each
    scored_records = []
    for r in records:
        if r.get("mw") is None or str(r.get("mw")) == "nan":
            scored_records.append({"smiles": r.get("smiles"), "status": "failed_parsing"})
            continue

        score = 100.0
        if not r.get("lipinski_pass", False):
            score -= 25.0
        if r.get("cyp3a4_inhibit", False):
            score -= 15.0
        if r.get("cyp2d6_inhibit", False):
            score -= 15.0
        if r.get("herg_risk", False):
            score -= 25.0
        sa = r.get("sa_score")
        if sa and sa > 5.0:
            score -= (sa - 5.0) * 4.0

        r["composite_score"] = max(round(score, 1), 0.0)
        scored_records.append(r)

    # Sort valid candidates by score descending
    valid = [r for r in scored_records if "composite_score" in r]
    valid.sort(key=lambda x: x["composite_score"], reverse=True)
    failed = [r for r in scored_records if "composite_score" not in r]

    return {
        "total_screened": len(req.smiles_list),
        "passed_count": len(valid),
        "failed_count": len(failed),
        "ranked_candidates": valid,
        "failed_candidates": failed,
    }
