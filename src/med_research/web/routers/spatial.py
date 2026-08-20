"""FastAPI router for Spatial Transcriptomics analysis and Visium spot visualization."""

from __future__ import annotations

import logging
import math
import random
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from med_research.pipeline.spatial_transcriptomics import (
    compute_morans_i,
    score_ligand_receptor_colocalization,
)

router = APIRouter(prefix="/api/spatial", tags=["Spatial Transcriptomics"])
logger = logging.getLogger(__name__)


class SpotCoordinate(BaseModel):
    barcode: str
    x: float
    y: float
    features: Dict[str, float] = Field(default_factory=dict)


class SpatialAnalysisRequest(BaseModel):
    spots: List[SpotCoordinate] = Field(..., min_length=3, max_length=2000)
    gene: str = Field(default="CD274", description="Target gene for Moran's I autocorrelation")
    ligand_gene: Optional[str] = Field(
        default="CD274", description="Ligand gene for co-localization"
    )
    receptor_gene: Optional[str] = Field(
        default="PDCD1", description="Receptor gene for co-localization"
    )
    radius: float = Field(default=150.0, ge=10.0, le=1000.0)


@router.get("/sample-data")
async def get_sample_spatial_data(
    disease: str = "melanoma",
    num_spots: int = 150,
) -> Dict[str, Any]:
    """Generate synthetic spatial Visium spot grid with realistic tumor-immune margin expression."""
    rng = random.Random(42)
    spots = []

    # 2D Grid with tumor core and infiltrating immune margin
    grid_size = int(math.sqrt(num_spots))
    for i in range(grid_size):
        for j in range(grid_size):
            x = (i + rng.gauss(0, 0.08)) * 30.0 + 50.0
            y = (j + rng.gauss(0, 0.08)) * 30.0 + 50.0
            dist_from_center = math.hypot(x - 200, y - 200)

            # Spatial gradients
            is_tumor = dist_from_center < 90
            is_margin = 70 <= dist_from_center <= 130

            # Gene expressions
            cd274 = round(max(rng.gauss(4.2 if is_margin else 1.1, 0.6), 0.1), 2)  # PD-L1
            pdcd1 = round(max(rng.gauss(3.8 if is_margin else 0.8, 0.5), 0.1), 2)  # PD-1
            braf = round(max(rng.gauss(5.5 if is_tumor else 0.5, 0.8), 0.1), 2)
            cd8a = round(max(rng.gauss(4.0 if is_margin else 0.6, 0.7), 0.1), 2)
            egfr = round(max(rng.gauss(3.5 if is_tumor else 0.9, 0.6), 0.1), 2)

            barcode = f"SPOT-{i:02d}-{j:02d}"
            spots.append(
                {
                    "barcode": barcode,
                    "x": round(x, 2),
                    "y": round(y, 2),
                    "region": "Tumor Core"
                    if is_tumor
                    else ("Invasive Margin" if is_margin else "Normal Stroma"),
                    "features": {
                        "CD274": cd274,
                        "PDCD1": pdcd1,
                        "BRAF": braf,
                        "CD8A": cd8a,
                        "EGFR": egfr,
                    },
                }
            )
            if len(spots) >= num_spots:
                break
        if len(spots) >= num_spots:
            break

    return {
        "disease": disease,
        "spot_count": len(spots),
        "available_genes": ["CD274", "PDCD1", "BRAF", "CD8A", "EGFR"],
        "spots": spots,
    }


@router.post("/analyze")
async def analyze_spatial_dataset(req: SpatialAnalysisRequest) -> Dict[str, Any]:
    """Calculate Moran's I spatial clustering and Ligand-Receptor co-localization."""
    coords = [(s.x, s.y) for s in req.spots]

    # Extract feature values for Moran's I
    values = [s.features.get(req.gene, 0.0) for s in req.spots]
    morans_i = compute_morans_i(coords, values)

    # Calculate Ligand-Receptor co-localization if genes provided
    lr_score = 0.0
    if req.ligand_gene and req.receptor_gene:
        lig_vals = [s.features.get(req.ligand_gene, 0.0) for s in req.spots]
        rec_vals = [s.features.get(req.receptor_gene, 0.0) for s in req.spots]
        lr_score = score_ligand_receptor_colocalization(
            coords, lig_vals, rec_vals, radius=req.radius
        )

    # Determine spatial pattern classification
    if morans_i > 0.4:
        pattern = "Highly Clustered / Spatially Variable"
    elif morans_i > 0.15:
        pattern = "Moderately Clustered"
    elif morans_i > -0.15:
        pattern = "Random / Homogeneous Distribution"
    else:
        pattern = "Dispersed / Regular Pattern"

    return {
        "target_gene": req.gene,
        "morans_i_score": round(morans_i, 4),
        "spatial_pattern": pattern,
        "ligand_receptor_interaction": {
            "ligand": req.ligand_gene,
            "receptor": req.receptor_gene,
            "colocalization_score": round(lr_score, 4),
            "interaction_density": "High (Hotspot Active)" if lr_score > 2.0 else "Low / Baseline",
        },
        "spot_count": len(req.spots),
    }
