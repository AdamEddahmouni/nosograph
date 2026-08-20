"""FastAPI router for Agentic Target Hypothesis & Literature Synthesis."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from med_research.pipeline.agent.hypothesis_agent import TargetHypothesisAgent

router = APIRouter(prefix="/api/agent", tags=["Target Hypothesis Agent"])
logger = logging.getLogger(__name__)


class TargetHypothesisRequest(BaseModel):
    disease_id: str = Field(default="melanoma", description="Disease identifier")
    gene_symbol: str = Field(default="BRAF", description="Target gene symbol")


class ChatQueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query for the scientific agent")
    disease_id: Optional[str] = Field(default=None)


@router.post("/hypothesis/generate")
async def generate_target_hypothesis(req: TargetHypothesisRequest) -> Dict[str, Any]:
    """Generate structured target hypothesis with multi-omics, pathway, and pharmacological synthesis."""
    try:
        agent = TargetHypothesisAgent(req.disease_id)
        hypothesis = agent.evaluate_target(req.gene_symbol)
        return {
            "status": "success",
            "hypothesis": hypothesis.to_dict(),
        }
    except Exception as e:
        logger.exception("Failed to generate target hypothesis: %s", e)
        raise HTTPException(status_code=500, detail=f"Hypothesis generation failed: {str(e)}") from e


@router.post("/chat")
async def agent_chat_query(req: ChatQueryRequest) -> Dict[str, Any]:
    """Interactive reasoning endpoint answering translational biology and drug discovery questions."""
    q_lower = req.query.lower()
    disease = req.disease_id or "melanoma"

    agent = TargetHypothesisAgent(disease)

    # Extract potential gene mentioned or fallback
    common_genes = ["BRAF", "EGFR", "KRAS", "PDCD1", "CD274", "IDH1", "CTLA4", "KIT", "CDK4", "MET"]
    found_gene = next((g for g in common_genes if g.lower() in q_lower), "BRAF")

    hyp = agent.evaluate_target(found_gene)

    response_text = (
        f"**Target Analysis for {found_gene} in {hyp.disease_name} (Confidence: {int(hyp.overall_confidence*100)}%)**:\n\n"
        f"{hyp.mechanism_of_action_hypothesis}\n\n"
        f"**Key Evidence Points:**\n" +
        "\n".join([f"- {ev.description} (*{ev.source_type}*)" for ev in hyp.supporting_evidence]) +
        f"\n\n**Druggability & Feasibility:** {hyp.druggability_assessment['tractability_small_molecule']} tractability for small molecules. "
        f"Recommended primary screening assay: {hyp.recommended_assays[0]}"
    )

    return {
        "query": req.query,
        "disease_id": disease,
        "target_analyzed": found_gene,
        "answer": response_text,
        "structured_hypothesis": hyp.to_dict(),
    }
