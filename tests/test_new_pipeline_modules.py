"""Unit tests for multi_omics, structure_3d, admet, and crispr pipeline modules."""

from __future__ import annotations

from pathlib import Path

import pytest

from med_research.pipeline.admet.adapter import AdmetModule
from med_research.pipeline.admet.engine import analyze_admet
from med_research.pipeline.crispr.adapter import CrisprModule
from med_research.pipeline.crispr.engine import evaluate_crispr_feasibility
from med_research.pipeline.multi_omics.adapter import MultiOmicsModule
from med_research.pipeline.multi_omics.engine import analyze_multi_omics
from med_research.pipeline.registry import get_module, list_modules
from med_research.pipeline.results import validate_result_contract
from med_research.pipeline.structure_3d.adapter import Structure3DModule
from med_research.pipeline.structure_3d.engine import analyze_structure_3d


@pytest.mark.parametrize("module_id", ["multi_omics", "structure_3d", "admet", "crispr"])
def test_new_modules_registered(module_id: str):
    assert module_id in list_modules()
    adapter = get_module(module_id)
    assert adapter.module_id == module_id


def test_multi_omics_engine_and_adapter():
    res = analyze_multi_omics("ad")
    assert res["disease_id"] == "ad"
    assert res["total_genes"] > 0
    assert len(res["targets"]) > 0

    validated = validate_result_contract("multi_omics", res)
    assert validated["disease_id"] == "ad"

    adapter = MultiOmicsModule()
    run_res = adapter.run("ad")
    assert run_res["total_genes"] == res["total_genes"]

    report_path = adapter.report(run_res, "ad")
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "Multi-Omics" in content


def test_structure_3d_engine_and_adapter():
    res = analyze_structure_3d("ad")
    assert res["disease_id"] == "ad"
    assert res["total_structures"] > 0

    validated = validate_result_contract("structure_3d", res)
    assert validated["disease_id"] == "ad"

    adapter = Structure3DModule()
    run_res = adapter.run("ad")
    assert run_res["total_structures"] == res["total_structures"]

    report_path = adapter.report(run_res, "ad")
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "3D Structural Target Docking" in content


def test_admet_engine_and_adapter():
    res = analyze_admet("ad")
    assert res["disease_id"] == "ad"
    assert res["total_drugs"] > 0

    validated = validate_result_contract("admet", res)
    assert validated["disease_id"] == "ad"

    adapter = AdmetModule()
    run_res = adapter.run("ad")
    assert run_res["total_drugs"] == res["total_drugs"]

    report_path = adapter.report(run_res, "ad")
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "ADMET Radar Safety" in content


def test_crispr_engine_and_adapter():
    res = evaluate_crispr_feasibility("ad")
    assert res["disease_id"] == "ad"
    assert res["total_genes"] > 0

    validated = validate_result_contract("crispr", res)
    assert validated["disease_id"] == "ad"

    adapter = CrisprModule()
    run_res = adapter.run("ad")
    assert run_res["total_genes"] == res["total_genes"]

    report_path = adapter.report(run_res, "ad")
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "CRISPR" in content
