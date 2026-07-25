"""Gene Expression Correlation API router."""

from fastapi import APIRouter, Query

from med_research.web.models.expression import ExpressionCorrelationResponse
from med_research.web.services.expression_service import run_correlation_analysis

router = APIRouter(tags=["Expression"])


@router.get("/api/expression/correlate", response_model=ExpressionCorrelationResponse)
async def correlate_expression(
    top_n: int = Query(26, ge=1, le=26, description="Number of top drugs to return"),
):
    """Correlate all 26 drugs against the curated SLE gene expression signature.

    Returns scored drugs ranked by composite gene expression reversal score
    across 5 dimensions: signature reversal, target-disease overlap,
    cell type specificity, expression evidence, and directionality.
    """
    result = run_correlation_analysis(top_n=top_n)
    return result
