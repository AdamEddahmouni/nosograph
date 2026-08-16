"""ChEMBL and UniProt REST API clients for bioactivity and protein annotations."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .client import fetch_json

logger = logging.getLogger(__name__)

CHEMBL_BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"
UNIPROT_BASE_URL = "https://rest.uniprot.org/uniprotkb"


class ChEMBLClient:
    """Client for querying ChEMBL target bioactivities, mechanisms, and chemical structures."""

    def __init__(self, base_url: str = CHEMBL_BASE_URL) -> None:
        self.base_url = base_url

    def search_target(self, query_term: str) -> Optional[Dict[str, Any]]:
        """Search ChEMBL target by target name or gene symbol."""
        url = f"{self.base_url}/target/search.json"
        try:
            data = fetch_json(url, params={"q": query_term, "limit": 1})
            targets = data.get("targets", [])
            if targets:
                t = targets[0]
                return {
                    "target_chembl_id": t.get("target_chembl_id"),
                    "pref_name": t.get("pref_name"),
                    "target_type": t.get("target_type"),
                    "organism": t.get("organism"),
                }
        except Exception as err:
            logger.warning("Failed ChEMBL target search for %s: %s", query_term, err)
        return None

    def get_target_bioactivities(
        self, target_chembl_id: str, activity_type: str = "IC50", limit: int = 15
    ) -> List[Dict[str, Any]]:
        """Fetch bioactivity measurements (e.g. IC50, Ki, EC50) for a ChEMBL target."""
        url = f"{self.base_url}/activity.json"
        params = {
            "target_chembl_id": target_chembl_id,
            "type": activity_type,
            "relation": "=",
            "limit": limit,
        }
        try:
            data = fetch_json(url, params=params)
            activities = data.get("activities", [])
            results = []
            for act in activities:
                results.append(
                    {
                        "molecule_chembl_id": act.get("molecule_chembl_id"),
                        "molecule_pref_name": act.get("molecule_pref_name"),
                        "activity_type": act.get("standard_type"),
                        "value": act.get("standard_value"),
                        "units": act.get("standard_units"),
                        "relation": act.get("standard_relation"),
                        "pchembl_value": act.get("pchembl_value"),
                    }
                )
            return results
        except Exception as err:
            logger.warning("Failed fetching ChEMBL bioactivities for %s: %s", target_chembl_id, err)
            return []


class UniProtClient:
    """Client for querying UniProtKB protein metadata, annotations, and structural links."""

    def __init__(self, base_url: str = UNIPROT_BASE_URL) -> None:
        self.base_url = base_url

    def get_protein_by_gene(
        self, gene_symbol: str, organism_id: int = 9606
    ) -> Optional[Dict[str, Any]]:
        """Fetch UniProt protein record for human gene symbol."""
        url = f"{self.base_url}/search"
        query = f"gene_exact:{gene_symbol} AND organism_id:{organism_id} AND reviewed:true"
        try:
            data = fetch_json(url, params={"query": query, "format": "json", "size": 1})
            results = data.get("results", [])
            if results:
                entry = results[0]
                primary_accession = entry.get("primaryAccession")
                rec_name = (
                    entry.get("proteinDescription", {})
                    .get("recommendedName", {})
                    .get("fullName", {})
                    .get("value", "")
                )
                comments = entry.get("comments", [])
                func_text = ""
                for c in comments:
                    if c.get("commentType") == "FUNCTION":
                        func_text = " ".join([t.get("value", "") for t in c.get("texts", [])])
                        break

                features = entry.get("features", [])
                domains = [
                    f.get("description", f.get("type"))
                    for f in features
                    if f.get("type") in ("DOMAIN", "REGION", "ACTIVE SITE")
                ]

                return {
                    "accession": primary_accession,
                    "gene_symbol": gene_symbol,
                    "protein_name": rec_name,
                    "function_summary": func_text,
                    "domains": domains[:10],
                    "sequence_length": entry.get("sequence", {}).get("length"),
                }
        except Exception as err:
            logger.warning("Failed UniProt lookup for gene %s: %s", gene_symbol, err)
        return None
