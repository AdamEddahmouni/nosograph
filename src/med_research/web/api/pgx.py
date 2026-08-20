from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from med_research.pipeline.pharmacogenomics.parser import parse_star_allele
from med_research.pipeline.pharmacogenomics.phenotype import (
    dosing_recommendation,
    phenotype_from_alleles,
)

router = APIRouter(prefix="/pgx", tags=["Pharmacogenomics"])


class GenotypeInput(BaseModel):
    """JSON payload mapping gene symbols to a list of star‑allele strings.
    Example:
        {
            "CYP2D6": ["*1", "*4"],
            "CYP2C19": ["*1", "*2"]
        }
    """

    genotypes: Dict[str, List[str]] = Field(..., description="Gene → list of allele identifiers")


class PGxResult(BaseModel):
    gene: str
    phenotype: str
    dosing_guidance: str


@router.post("/evaluate", response_model=List[PGxResult])
def evaluate_pgx(payload: GenotypeInput):
    results: List[PGxResult] = []
    for gene, alleles in payload.genotypes.items():
        try:
            # Validate and normalize via parser (ensures gene exists and alleles are known)
            parsed = parse_star_allele(gene, "/".join(alleles))
            phenotype = phenotype_from_alleles(parsed["gene"], parsed["alleles"])
            guidance = dosing_recommendation(parsed["gene"], phenotype)
            results.append(
                PGxResult(gene=gene.upper(), phenotype=phenotype, dosing_guidance=guidance)
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    return results

