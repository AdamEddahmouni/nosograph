"""Shared fixtures for evidence gatherer HTTP mocking."""

from __future__ import annotations

import re

import pytest
import responses

EUROPE_PMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
DAILYMED_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"

EUROPE_PMC_FIXTURE = {
    "resultList": {
        "result": [
            {
                "title": "B cell depletion in systemic lupus erythematosus",
                "journalTitle": "Lupus Science & Medicine",
                "source": "MED",
                "pubYear": "2024",
                "id": "PMC888001",
                "abstractText": "Belimumab and rituximab outcomes in SLE.",
                "authorString": "Chen L, Patel R",
                "citedByCount": 8,
            },
            {
                "title": "JAK inhibition in autoimmune disease",
                "journalTitle": "Annals of the Rheumatic Diseases",
                "source": "MED",
                "pubYear": "2023",
                "id": "PMC888002",
                "abstractText": "Baricitinib safety profile.",
                "authorString": "Jones K",
                "citedByCount": 15,
            },
        ]
    }
}

FDA_FIXTURE = {
    "data": [
        {
            "title": "BELIMUMAB (belimumab) injection",
            "setid": "fda-set-belimumab",
            "updated_date": "20231201",
        }
    ]
}


@pytest.fixture
def evidence_http_mocks(monkeypatch):
    """Patch gatherer HTTP to requests and register ``responses`` fixtures."""
    import requests

    from med_research.pipeline.evidence import gatherer

    def api_get(url: str, timeout: int = 15):
        response = requests.get(
            url,
            headers={"User-Agent": "MedResearchTests/2.0"},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

    monkeypatch.setattr(gatherer, "api_get", api_get)

    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses.GET,
            re.compile(re.escape(EUROPE_PMC_URL)),
            json=EUROPE_PMC_FIXTURE,
            status=200,
        )
        rsps.add(
            responses.GET,
            re.compile(re.escape(DAILYMED_URL)),
            json=FDA_FIXTURE,
            status=200,
        )
        yield rsps
