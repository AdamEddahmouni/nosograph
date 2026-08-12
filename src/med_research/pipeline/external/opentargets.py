"""Open Targets Platform GraphQL API connector."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .client import fetch_json

logger = logging.getLogger(__name__)

OPENTARGETS_GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"

# Disease symbol to EFO ID mapping for supported disease modules
DISEASE_EFO_MAP = {
    "sle": "EFO_0002690",  # Systemic Lupus Erythematosus
    "ra": "EFO_0000685",   # Rheumatoid Arthritis
    "ms": "EFO_0003885",   # Multiple Sclerosis
    "ss": "EFO_0000600",   # Sjögren's Syndrome
    "ssc": "EFO_0000707",  # Systemic Sclerosis
    "t1d": "EFO_0001359",  # Type 1 Diabetes
    "ibd": "EFO_0003767",  # Inflammatory Bowel Disease
}


class OpenTargetsClient:
    """Client for fetching target validation and disease evidence from Open Targets."""

    def __init__(self, endpoint_url: str = OPENTARGETS_GRAPHQL_URL) -> None:
        self.endpoint_url = endpoint_url

    def query(self, query_str: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute GraphQL query against Open Targets Platform."""
        payload = {"query": query_str, "variables": variables or {}}
        response = fetch_json(self.endpoint_url, body=payload)
        if "errors" in response and response["errors"]:
            msg = f"Open Targets GraphQL error: {response['errors'][0].get('message')}"
            logger.error(msg)
            raise RuntimeError(msg)
        return response.get("data", {})

    def get_target_details(self, target_symbol: str) -> Dict[str, Any]:
        """Retrieve target details by gene symbol (e.g., JAK2, STAT3, TNF)."""
        gql = """
        query TargetDetails($symbol: String!) {
          search(queryString: $symbol, entityNames: ["target"]) {
            hits {
              id
              name
              object {
                ... on Target {
                  id
                  approvedSymbol
                  approvedName
                }
              }
            }
          }
        }
        """
        res = self.query(gql, {"symbol": target_symbol})
        hits = res.get("search", {}).get("hits", [])
        if hits:
            hit = hits[0].get("object", {})
            return {
                "ensembl_id": hit.get("id"),
                "symbol": hit.get("approvedSymbol", target_symbol),
                "name": hit.get("approvedName", ""),
            }
        return {"symbol": target_symbol}

    def get_target_disease_evidence(self, target_ensembl_id: str, disease_efo_id: str) -> Dict[str, Any]:
        """Fetch association score and evidence breakdown for target and disease."""
        gql = """
        query TargetDiseaseAssoc($diseaseId: String!) {
          disease(efoId: $diseaseId) {
            id
            name
            associatedTargets(page: {index: 0, size: 100}) {
              rows {
                target {
                  id
                  approvedSymbol
                }
                score
              }
            }
          }
        }
        """
        try:
            res = self.query(gql, {"diseaseId": disease_efo_id})
            disease_data = res.get("disease") or {}
            rows = disease_data.get("associatedTargets", {}).get("rows", [])
            for row in rows:
                t = row.get("target", {})
                if t.get("id") == target_ensembl_id or t.get("approvedSymbol") == target_ensembl_id:
                    return {
                        "disease_id": disease_efo_id,
                        "disease_name": disease_data.get("name", ""),
                        "overall_score": row.get("score", 0.0),
                    }
        except Exception as err:
            logger.warning("Failed to fetch target disease evidence for %s / %s: %s", target_ensembl_id, disease_efo_id, err)
        return {"disease_id": disease_efo_id, "overall_score": 0.0}

    def search_disease_targets(self, disease_key: str, size: int = 10) -> List[Dict[str, Any]]:
        """Fetch top scored targets for a given disease code or EFO ID."""
        efo_id = DISEASE_EFO_MAP.get(disease_key.lower(), disease_key)
        gql = """
        query TopTargets($diseaseId: String!, $size: Int!) {
          disease(efoId: $diseaseId) {
            id
            name
            associatedTargets(page: {index: 0, size: $size}) {
              rows {
                target {
                  id
                  approvedSymbol
                  approvedName
                }
                score
              }
            }
          }
        }
        """
        res = self.query(gql, {"diseaseId": efo_id, "size": size})
        rows = res.get("disease", {}).get("associatedTargets", {}).get("rows", [])
        results = []
        for r in rows:
            t = r.get("target", {})
            results.append({
                "ensembl_id": t.get("id"),
                "symbol": t.get("approvedSymbol"),
                "name": t.get("approvedName"),
                "association_score": r.get("score", 0.0),
            })
        return results
