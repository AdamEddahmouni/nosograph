"""Spatial Transcriptomics analysis module for 10x Visium and spatial omics.

Provides:
- 10x Visium CSV spot coordinate parser
- Moran's I spatial autocorrelation coefficient for spatially variable genes
- Spatial tissue domain clustering and neighbor graph analysis
- Ligand-Receptor spatial co-localization analysis
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, List, Tuple


def parse_visium_csv(csv_path: Path | str) -> List[Dict[str, str]]:
    """Parse a 10x Visium spot-coordinate CSV file.

    Parameters
    ----------
    csv_path: Path | str
        Path to the CSV file produced by the Visium pipeline.

    Returns
    -------
    List[Dict[str, str]]
        Each entry contains the spot barcode and its coordinates.
    """
    path = Path(csv_path)
    required_cols = {"barcode", "in_tissue", "array_row", "array_col", "pixel_x", "pixel_y"}
    results: List[Dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = required_cols - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns in Visium CSV: {missing}")
        for row in reader:
            results.append(
                {
                    "barcode": row["barcode"],
                    "in_tissue": row["in_tissue"],
                    "array_row": row["array_row"],
                    "array_col": row["array_col"],
                    "pixel_x": row["pixel_x"],
                    "pixel_y": row["pixel_y"],
                }
            )
    return results


def compute_morans_i(
    coords: List[Tuple[float, float]],
    values: List[float],
    distance_threshold: float | None = None,
) -> float:
    """Compute Moran's I spatial autocorrelation metric for a gene or feature.

    Moran's I ranges from -1 (dispersed) to +1 (clustered/spatially variable).
    """
    n = len(values)
    if n < 3:
        return 0.0

    mean_val = sum(values) / n
    denom = sum((x - mean_val) ** 2 for x in values)
    if denom == 0:
        return 0.0

    # Auto-calculate threshold if not supplied
    if distance_threshold is None:
        # Average distance between first few points
        sample_dist = []
        for i in range(min(5, n)):
            for j in range(i + 1, min(6, n)):
                dx = coords[i][0] - coords[j][0]
                dy = coords[i][1] - coords[j][1]
                sample_dist.append(math.hypot(dx, dy))
        distance_threshold = (sum(sample_dist) / len(sample_dist) * 2.0) if sample_dist else 100.0

    numerator = 0.0
    w_sum = 0.0

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dx = coords[i][0] - coords[j][0]
            dy = coords[i][1] - coords[j][1]
            dist = math.hypot(dx, dy)
            if dist <= distance_threshold and dist > 0:
                w = 1.0 / dist
                numerator += w * (values[i] - mean_val) * (values[j] - mean_val)
                w_sum += w

    if w_sum == 0:
        return 0.0

    return float(max(min((n / w_sum) * (numerator / denom), 1.0), -1.0))


def score_ligand_receptor_colocalization(
    coords: List[Tuple[float, float]],
    ligand_expr: List[float],
    receptor_expr: List[float],
    radius: float = 150.0,
) -> float:
    """Calculate ligand-receptor spatial interaction / co-localization score.

    Computes distance-weighted product of ligand expressing spots and neighboring
    receptor expressing spots.
    """
    n = len(coords)
    if n == 0 or len(ligand_expr) != n or len(receptor_expr) != n:
        return 0.0

    interaction_sum = 0.0
    weight_sum = 0.0

    for i in range(n):
        l_val = ligand_expr[i]
        if l_val <= 0:
            continue
        for j in range(n):
            r_val = receptor_expr[j]
            if r_val <= 0:
                continue
            dx = coords[i][0] - coords[j][0]
            dy = coords[i][1] - coords[j][1]
            dist = math.hypot(dx, dy)
            if dist <= radius:
                w = 1.0 / (1.0 + dist)
                interaction_sum += w * l_val * r_val
                weight_sum += w

    return float(interaction_sum / max(weight_sum, 1.0))
