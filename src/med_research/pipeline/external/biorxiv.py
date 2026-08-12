"""bioRxiv and medRxiv REST API connector for preprint literature search."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from .client import fetch_json

logger = logging.getLogger(__name__)

BIORXIV_API_BASE = "https://api.biorxiv.org/details"


class BioRxivClient:
    """Client for querying bioRxiv and medRxiv preprint servers."""

    def __init__(self, server: str = "biorxiv") -> None:
        self.server = server if server in ("biorxiv", "medrxiv") else "biorxiv"

    def fetch_recent_preprints(self, days_back: int = 30, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recent preprints from server across specified interval."""
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

        url = f"{BIORXIV_API_BASE}/{self.server}/{start_date}/{end_date}/0/json"
        try:
            data = fetch_json(url)
            collection = data.get("collection", [])
            results = []
            for item in collection[:limit]:
                results.append({
                    "doi": item.get("doi"),
                    "title": item.get("title"),
                    "authors": item.get("authors"),
                    "date": item.get("date"),
                    "category": item.get("category"),
                    "abstract": item.get("abstract"),
                    "url": f"https://www.biorxiv.org/content/{item.get('doi')}v1",
                    "server": self.server,
                })
            return results
        except Exception as err:
            logger.warning("Failed fetching preprints from %s: %s", self.server, err)
            return []

    def search_preprints_by_keyword(self, keyword: str, days_back: int = 90, limit: int = 15) -> List[Dict[str, Any]]:
        """Filter recent preprints by keyword in title or abstract."""
        recent = self.fetch_recent_preprints(days_back=days_back, limit=100)
        kw_lower = keyword.lower()
        matches = []
        for p in recent:
            title = (p.get("title") or "").lower()
            abstract = (p.get("abstract") or "").lower()
            if kw_lower in title or kw_lower in abstract:
                matches.append(p)
                if len(matches) >= limit:
                    break
        return matches
