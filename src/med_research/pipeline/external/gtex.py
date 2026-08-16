"""GTEx Portal API v2 connector for tissue expression and eQTL data."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .client import fetch_json

logger = logging.getLogger(__name__)

GTEX_API_BASE = "https://gtexportal.org/api/v2"


class GTExClient:
    """Client for querying GTEx tissue expression and quantitative trait loci (eQTLs)."""

    def __init__(self, base_url: str = GTEX_API_BASE) -> None:
        self.base_url = base_url

    def get_gene_info(self, gene_symbol: str) -> Optional[Dict[str, Any]]:
        """Resolve gene symbol to GENCODE ID."""
        url = f"{self.base_url}/reference/gene"
        data = fetch_json(url, params={"geneId": gene_symbol})
        genes = data.get("gene", [])
        if genes:
            return {
                "gencode_id": genes[0].get("gencodeId"),
                "symbol": genes[0].get("geneSymbol"),
                "gene_type": genes[0].get("geneType"),
                "description": genes[0].get("description"),
            }
        return None

    def get_median_tissue_expression(self, gene_symbol: str) -> List[Dict[str, Any]]:
        """Fetch median transcript expression (TPM) across human tissues for a gene."""
        gene_info = self.get_gene_info(gene_symbol)
        gencode_id = gene_info.get("gencode_id") if gene_info else gene_symbol

        url = f"{self.base_url}/expression/medianGeneExpression"
        try:
            data = fetch_json(url, params={"gencodeId": gencode_id})
            expression_rows = data.get("medianGeneExpression", [])
            results = []
            for row in expression_rows:
                results.append(
                    {
                        "tissue_site_detail_id": row.get("tissueSiteDetailId"),
                        "tissue_name": row.get("tissueSiteDetailId", "").replace("_", " ").title(),
                        "median_tpm": row.get("median", 0.0),
                        "unit": "TPM",
                    }
                )
            results.sort(key=lambda x: x["median_tpm"], reverse=True)
            return results
        except Exception as err:
            logger.warning("Failed to fetch GTEx expression for %s: %s", gene_symbol, err)
            return []

    def get_single_tissue_eqtls(
        self, gene_symbol: str, tissue_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch significant eQTL variants for a gene in GTEx tissues."""
        gene_info = self.get_gene_info(gene_symbol)
        gencode_id = gene_info.get("gencode_id") if gene_info else gene_symbol

        url = f"{self.base_url}/association/singleTissueEqtl"
        params: Dict[str, Any] = {"gencodeId": gencode_id, "datasetId": "gtex_v8"}
        if tissue_id:
            params["tissueSiteDetailId"] = tissue_id

        try:
            data = fetch_json(url, params=params)
            eqtls = data.get("singleTissueEqtl", [])
            results = []
            for item in eqtls[:25]:  # Top 25 eQTLs
                results.append(
                    {
                        "variant_id": item.get("variantId"),
                        "rs_id": item.get("snpId"),
                        "gene_symbol": item.get("geneSymbol", gene_symbol),
                        "tissue_id": item.get("tissueSiteDetailId"),
                        "p_value": item.get("pValue"),
                        "nes": item.get("nes"),  # Normalized Effect Size
                    }
                )
            return results
        except Exception as err:
            logger.warning("Failed to fetch GTEx eQTLs for %s: %s", gene_symbol, err)
            return []
