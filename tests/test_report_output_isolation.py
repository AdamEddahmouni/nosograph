"""Per-worker isolation of generated pipeline reports under pytest-xdist.

The session fixture redirects generated reports to a private temporary root
through ``MED_RESEARCH_REPORT_DIR``. These tests pin both the resolver contract
and every pipeline HTML writer that is expected to honor that override.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from med_research.pipeline.reporting import REPORT_DIR_ENV_VAR, report_output_dir

PIPELINE_ROOT = Path(__file__).resolve().parents[1] / "src" / "med_research" / "pipeline"
MODULE_DIR = PIPELINE_ROOT / "evidence"

pytestmark = pytest.mark.unit


REPORT_WRITERS = [
    ("adverse_events", "adverse_events/report.html"),
    ("admet_adapter", "reports/admet_ad.html"),
    ("biomarker_discovery", "biomarker_discovery/report.html"),
    ("bioinformatics", "bioinformatics/bioinformatics_report.html"),
    ("bioinformatics_ppi", "bioinformatics/data/ppi_interactive.html"),
    ("car_t_predictor", "car_t_predictor/report.html"),
    ("clinical_trials", "clinical_trials/ct_report.html"),
    ("cross_disease", "cross_disease/report.html"),
    ("crispr_adapter", "reports/crispr_ad.html"),
    ("drug_repurposing", "drug_repurposing/report.html"),
    ("drug_synergy", "drug_synergy/report.html"),
    ("evidence_extractor", "evidence/report.html"),
    ("evidence_gatherer", "evidence/report.html"),
    ("evidence_monitor", "evidence/report.html"),
    ("evidence_workspace_adapter", "evidence_workspace/report_sle.html"),
    ("gene_expression", "gene_expression/report.html"),
    ("literature_mining", "literature_mining/literature_report.html"),
    ("ml_predictor", "ml_predictor/ml_report.html"),
    ("multi_omics_adapter", "reports/multi_omics_ad.html"),
    ("network_pharmacology", "network_pharmacology/report.html"),
    ("semantic_search", "semantic_search/report.html"),
    ("structure_3d_adapter", "reports/structure_3d_ad.html"),
    ("virtual_screening", "virtual_screening/screening_report.html"),
]


def test_defaults_to_the_module_directory(monkeypatch, tmp_path):
    """With no override, reports keep landing beside their generator."""
    monkeypatch.delenv(REPORT_DIR_ENV_VAR, raising=False)

    default = tmp_path / "module"

    assert report_output_dir(default) == default
    assert default.is_dir()


def test_honours_the_override_and_creates_it(monkeypatch, tmp_path):
    override = tmp_path / "override" / "nested"
    monkeypatch.setenv(REPORT_DIR_ENV_VAR, str(override))

    assert report_output_dir(tmp_path / "module") == override / "module"
    assert (override / "module").is_dir()


def test_mirrors_the_pipeline_layout_under_the_override(monkeypatch, tmp_path):
    """Two generators in different modules must not resolve to one directory."""
    root = tmp_path / "root"
    monkeypatch.setenv(REPORT_DIR_ENV_VAR, str(root))

    assert report_output_dir(MODULE_DIR) == root / "evidence"
    assert report_output_dir(PIPELINE_ROOT / "cross_disease") == root / "cross_disease"
    # Adapters default to a path outside the package; fall back to its basename.
    assert report_output_dir(Path("dist/reports")) == root / "reports"


def test_suite_redirects_reports_out_of_the_source_tree(report_dir):
    """The session fixture covers every writer, not just opted-in tests."""
    output = report_output_dir(MODULE_DIR).resolve()

    assert output.parent == report_dir.resolve()
    assert output != MODULE_DIR
    assert MODULE_DIR not in output.parents


def test_report_directory_is_worker_scoped(report_dir):
    """Concurrent pytest-xdist workers never share one output directory."""
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")

    assert worker in report_dir.name


def _stub_report_renderers(monkeypatch, module: ModuleType) -> None:
    """Keep output-routing tests focused on the writer, not template contents."""
    from med_research.pipeline import reporting

    def render_stub(*args: Any, **kwargs: Any) -> str:
        return "<!doctype html><html><body>isolated report</body></html>"

    monkeypatch.setattr(reporting, "render_report", render_stub)
    monkeypatch.setattr(module, "render_report", render_stub, raising=False)


def _invoke_report_writer(writer: str, monkeypatch) -> Path:
    """Call one actual HTML writer with the smallest valid result payload."""
    if writer == "adverse_events":
        from med_research.pipeline.adverse_events.profiler import compute_adverse_event_score

        module = importlib.import_module("med_research.pipeline.adverse_events.report")
        _stub_report_renderers(monkeypatch, module)
        profile = {
            "drug_id": "test-drug",
            "drug_name": "Test Drug",
            "lupus_overlap_ae": [],
            "severity_burden": 2,
            "chronic_use_safety": 8,
            "dil_risk": 0,
            "black_box_warnings": [],
            "severe_ae": [],
        }
        return Path(module.generate_html_report([compute_adverse_event_score(profile)]))

    if writer == "admet_adapter":
        module = importlib.import_module("med_research.pipeline.admet.adapter")
        _stub_report_renderers(monkeypatch, module)
        return module.AdmetModule().report({}, "ad", provenance={"module": "admet"})

    if writer == "biomarker_discovery":
        module = importlib.import_module("med_research.pipeline.biomarker_discovery.report")
        _stub_report_renderers(monkeypatch, module)
        return Path(module.generate_html_report([]))

    if writer == "bioinformatics":
        module = importlib.import_module("med_research.pipeline.bioinformatics.report")
        _stub_report_renderers(monkeypatch, module)
        return Path(module.generate_bioinformatics_report())

    if writer == "bioinformatics_ppi":
        module = importlib.import_module("med_research.pipeline.bioinformatics.report")
        monkeypatch.setattr(module, "_run_ppi_communities", lambda graph: {"GENE1": 0, "GENE2": 0})

        class FakeNetwork:
            def __init__(self, **kwargs):
                pass

            def set_options(self, options):
                pass

            def add_node(self, *args, **kwargs):
                pass

            def add_edge(self, *args, **kwargs):
                pass

            def save_graph(self, path):
                Path(path).write_text("<html>ppi network</html>", encoding="utf-8")

        pyvis = ModuleType("pyvis")
        pyvis.__path__ = []  # type: ignore[attr-defined]
        network = ModuleType("pyvis.network")
        network.Network = FakeNetwork  # type: ignore[attr-defined]
        pyvis.network = network  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "pyvis", pyvis)
        monkeypatch.setitem(sys.modules, "pyvis.network", network)
        ppi_graph = {
            "nodes": [{"id": "GENE1"}, {"id": "GENE2"}],
            "edges": [{"source": "GENE1", "target": "GENE2", "score": 0.8}],
        }
        return Path(module._generate_ppi_interactive(ppi_graph, []))

    if writer == "car_t_predictor":
        module = importlib.import_module("med_research.pipeline.car_t_predictor.report")
        _stub_report_renderers(monkeypatch, module)
        return Path(module.generate_html_report([]))

    if writer == "clinical_trials":
        module = importlib.import_module("med_research.pipeline.clinical_trials.report")
        _stub_report_renderers(monkeypatch, module)
        results = {
            "trials": [],
            "stats": {
                "total_trials": 0,
                "kg_matched_trials": 0,
                "total_enrollment": 0,
                "avg_enrollment": 0,
                "statuses": {},
                "phases": {},
                "moas": {},
                "top_sponsors": {},
            },
            "kg_crossref": {
                "gene_hits": {},
                "drug_hits": {},
                "trials_with_matches": [],
                "total_matched": 0,
            },
        }
        return Path(module.generate_ct_report(results))

    if writer == "cross_disease":
        module = importlib.import_module("med_research.pipeline.cross_disease.report")
        _stub_report_renderers(monkeypatch, module)
        results = {
            "disease_summary": {},
            "total_diseases": 0,
            "shared_genes": {"shared_genes": []},
            "shared_drugs": {"shared_drugs": []},
            "shared_pathways": {"shared_pathways": []},
            "multi_disease_drugs": [],
            "disease_similarity": [],
            "cross_disease_repurposing": [],
        }
        return Path(module.generate_html_report(results))

    if writer == "crispr_adapter":
        module = importlib.import_module("med_research.pipeline.crispr.adapter")
        _stub_report_renderers(monkeypatch, module)
        return module.CrisprModule().report({}, "ad", provenance={"module": "crispr"})

    if writer == "drug_repurposing":
        module = importlib.import_module("med_research.pipeline.drug_repurposing.report")
        _stub_report_renderers(monkeypatch, module)
        return Path(module.generate_html_report([], [], {}, None))

    if writer == "drug_synergy":
        module = importlib.import_module("med_research.pipeline.drug_synergy.report")
        _stub_report_renderers(monkeypatch, module)
        return Path(module.generate_html_report([]))

    if writer == "evidence_extractor":
        module = importlib.import_module("med_research.pipeline.evidence.extractor_report")
        _stub_report_renderers(monkeypatch, module)
        return Path(module.generate_html_report({}))

    if writer == "evidence_gatherer":
        module = importlib.import_module("med_research.pipeline.evidence.gatherer_report")
        _stub_report_renderers(monkeypatch, module)
        gathered = {
            "query": "test",
            "total_results": 0,
            "elapsed_seconds": 0,
            "results_by_source": {},
            "all_results": [],
        }
        return Path(module.generate_html_report(gathered))

    if writer == "evidence_monitor":
        module = importlib.import_module("med_research.pipeline.evidence.monitor_report")
        _stub_report_renderers(monkeypatch, module)
        return Path(module.generate_html_report({}, {}, {}))

    if writer == "evidence_workspace_adapter":
        from datetime import datetime, timezone

        from med_research.pipeline.evidence_workspace.schemas import (
            EvidenceDossier,
            ResearchRequest,
        )

        module = importlib.import_module("med_research.pipeline.evidence_workspace.adapter")
        dossier = EvidenceDossier(
            run_id="isolation-test",
            request=ResearchRequest(disease_id="sle", question="test report"),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        return module.EvidenceWorkspaceModule().report(dossier, "sle")

    if writer == "gene_expression":
        module = importlib.import_module("med_research.pipeline.gene_expression.report")
        _stub_report_renderers(monkeypatch, module)
        return Path(module.generate_html_report([]))

    if writer == "literature_mining":
        module = importlib.import_module("med_research.pipeline.literature_mining.report")
        _stub_report_renderers(monkeypatch, module)
        results = {
            "stats": {
                "total_articles": 0,
                "articles_with_matches": 0,
                "genes_found": 0,
                "drugs_found": 0,
                "candidates_supported": 0,
                "spacy_ner": "test",
                "novel_entities_found": 0,
            },
            "candidate_support": {},
            "gene_coverage": {},
            "article_matches": [],
        }
        return Path(module.generate_literature_report(results, {"genes": {}, "drugs": {}}, []))

    if writer == "ml_predictor":
        module = importlib.import_module("med_research.pipeline.ml_predictor.report")
        _stub_report_renderers(monkeypatch, module)
        return Path(module.generate_ml_report({}))

    if writer == "multi_omics_adapter":
        module = importlib.import_module("med_research.pipeline.multi_omics.adapter")
        _stub_report_renderers(monkeypatch, module)
        return module.MultiOmicsModule().report({}, "ad", provenance={"module": "multi_omics"})

    if writer == "network_pharmacology":
        module = importlib.import_module("med_research.pipeline.network_pharmacology.report")
        _stub_report_renderers(monkeypatch, module)
        metrics = {
            "n_nodes": 0,
            "n_edges": 0,
            "density": 0.0,
            "diameter": 0,
            "avg_shortest_path": 0.0,
            "avg_clustering": 0.0,
            "n_components": 0,
            "assortativity": 0.0,
        }
        return Path(module.generate_html_report({"graph_metrics": metrics}))

    if writer == "semantic_search":
        module = importlib.import_module("med_research.pipeline.semantic_search.report")
        _stub_report_renderers(monkeypatch, module)
        return Path(module.generate_semantic_report([], "test query", indexed_count=0))

    if writer == "structure_3d_adapter":
        module = importlib.import_module("med_research.pipeline.structure_3d.adapter")
        _stub_report_renderers(monkeypatch, module)
        return module.Structure3DModule().report({}, "ad", provenance={"module": "structure_3d"})

    if writer == "virtual_screening":
        module = importlib.import_module("med_research.pipeline.virtual_screening.report")
        blocked = {"stats": {}, "status": "blocked", "coverage": {}}
        return Path(module.generate_screening_report(blocked))

    raise AssertionError(f"Unknown report writer: {writer}")


@pytest.mark.parametrize(
    ("writer", "relative_path"), REPORT_WRITERS, ids=[case[0] for case in REPORT_WRITERS]
)
def test_every_html_writer_honours_report_output_override(
    writer: str, relative_path: str, monkeypatch, tmp_path
):
    """Each resolver-backed pipeline HTML writer creates its artifact under the override."""
    override = tmp_path / "reports"
    monkeypatch.setenv(REPORT_DIR_ENV_VAR, str(override))

    artifact = _invoke_report_writer(writer, monkeypatch)

    assert artifact == override / relative_path
    assert artifact.is_file()
