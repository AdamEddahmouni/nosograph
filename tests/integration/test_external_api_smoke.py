"""Mocked external-API smoke tests for the PR integration gate.

Uses the ``responses`` library to exercise real HTTP client code paths without
live GWAS Catalog or PubMed calls.
"""

from __future__ import annotations

import re

import pytest
import responses

from med_research.diseases.coverage import module_coverage
from med_research.pipeline.bioinformatics.gwas import GWAS_API
from med_research.pipeline.dispatch import execute_module
from med_research.pipeline.registry import get_module

GWAS_SEARCH_URL = f"{GWAS_API}/studies/search/findByDiseaseTrait"

pytestmark = [pytest.mark.integration]




@pytest.fixture
def gwas_catalog_mocks():
    """Register minimal GWAS Catalog responses for one empty study lookup."""
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(
            responses.GET,
            re.compile(re.escape(GWAS_SEARCH_URL)),
            json={"_embedded": {"studies": []}},
            status=200,
        )
        yield rsps


class TestMockedExternalApiSmoke:
    """PR-gate smoke: real adapter + mocked HTTP, no live APIs."""

    def test_gwas_execute_module_via_responses(
        self,
        gwas_catalog_mocks,
    ):
        module = get_module("gwas")
        coverage = module_coverage("ra", "gwas", module.coverage_inputs())
        assert coverage.status == "ready", coverage.to_dict()

        result = execute_module(
            "gwas",
            "ra",
            use_cache=False,
            max_studies=2,
            resolve_snps=False,
        )

        assert result.success, result.errors
        assert isinstance(result.data, dict)
        assert result.data.get("status") == "ready"
        assert gwas_catalog_mocks.calls, "GWAS adapter should have called the catalog API"
