"""CLI entry-point progress contract.

Every engine ``main()`` must thread the shared ``cli_progress`` callback into
the engine functions it calls, so a ``python -m <engine>`` run emits the same
``(step, current, total)`` ticks as the adapter path. Each test invokes the
real ``main()`` (via ``sys.argv``) with the engine functions mocked to raise,
and asserts the calls received ``progress_callback=cli_progress``.
"""

from __future__ import annotations

import importlib
import logging
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from med_research.pipeline.progress import cli_progress


class _EngineCalled(Exception):
    """Raised by mocked engine functions to stop main() at the call site."""


# Each case: argv for main(), plus patch targets.
# A patch entry is (full dotted target, behavior, expect_callback):
#   behavior == "raise"                  -> mock raises _EngineCalled
#   behavior == ("return", value)        -> mock returns value
#   expect_callback                      -> assert call received cli_progress
CLI_MAIN_CASES = [
    {
        "id": "literature_mining",
        "module": "med_research.pipeline.literature_mining.miner",
        "argv": ["--max", "5", "--disease", "sle"],
        "patches": [
            (
                "med_research.pipeline.literature_mining.miner.mine_literature",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "car_t_predictor",
        "module": "med_research.pipeline.car_t_predictor.predictor",
        "argv": ["--top", "5", "--disease", "sle"],
        "patches": [
            (
                "med_research.pipeline.car_t_predictor.predictor.compute_all_scores",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "biomarker_discovery",
        "module": "med_research.pipeline.biomarker_discovery.discover",
        "argv": ["--top", "5", "--disease", "sle"],
        "patches": [
            (
                "med_research.pipeline.biomarker_discovery.discover.compute_biomarker_matrix",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "ppi",
        "module": "med_research.pipeline.bioinformatics.ppi",
        "argv": ["--disease", "sle"],
        "patches": [
            (
                "med_research.pipeline.bioinformatics.ppi.run_ppi_analysis",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "gwas",
        "module": "med_research.pipeline.bioinformatics.gwas",
        "argv": ["--disease", "sle"],
        "patches": [
            (
                "med_research.pipeline.bioinformatics.gwas.run_gwas_analysis",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "enrichment",
        "module": "med_research.pipeline.bioinformatics.enrichment",
        "argv": ["--disease", "sle"],
        "patches": [
            (
                "med_research.pipeline.bioinformatics.enrichment.run_enrichment_analysis",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "adverse_events",
        "module": "med_research.pipeline.adverse_events.profiler",
        "argv": ["--disease", "sle"],
        "patches": [
            (
                "med_research.pipeline.adverse_events.profiler.score_all_drugs",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "knowledge_graph",
        "module": "med_research.pipeline.knowledge_graph.builder",
        "argv": ["--disease", "sle"],
        "patches": [
            (
                "med_research.pipeline.knowledge_graph.builder.build_graph",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "virtual_screening",
        "module": "med_research.pipeline.virtual_screening.screening",
        "argv": ["--disease", "sle", "--top", "3"],
        "patches": [
            (
                "med_research.pipeline.virtual_screening.screening_strategy.strategy_for_disease",
                ("return", None),
                False,
            ),
            (
                "med_research.pipeline.virtual_screening.screening.build_compound_library",
                ("return", []),
                False,
            ),
            (
                "med_research.pipeline.virtual_screening.screening.get_untargeted_genes",
                ("return", []),
                False,
            ),
            (
                "med_research.pipeline.virtual_screening.screening.screen_compounds",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "evidence_monitor",
        "module": "med_research.pipeline.evidence.monitor",
        "argv": ["--snapshot", "--sources", "pubmed", "--max", "3"],
        "patches": [
            (
                "med_research.pipeline.evidence.monitor.take_snapshot",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "evidence_gather",
        "module": "med_research.pipeline.evidence.gatherer",
        "argv": ["--query", "lupus", "--sources", "pubmed", "--max", "3"],
        "patches": [
            (
                "med_research.pipeline.evidence.gatherer.gather_evidence",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "llm_extractor",
        "module": "med_research.pipeline.evidence.extractor",
        "argv": ["--query", "lupus", "--sources", "pubmed", "--max", "3"],
        "patches": [
            (
                "med_research.pipeline.evidence.extractor.extract_all",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "drug_repurposing",
        "module": "med_research.pipeline.drug_repurposing.engine",
        "argv": ["--disease", "sle", "--top", "5"],
        "patches": [
            (
                "med_research.pipeline.drug_repurposing.engine.load_knowledge_graph",
                (
                    "return",
                    SimpleNamespace(number_of_nodes=lambda: 1, number_of_edges=lambda: 1),
                ),
                False,
            ),
            (
                "med_research.pipeline.drug_repurposing.engine.load_genes",
                ("return", []),
                False,
            ),
            (
                "med_research.pipeline.drug_repurposing.engine.load_json",
                ("return", {"repurposing_candidates": []}),
                False,
            ),
            (
                "med_research.pipeline.drug_repurposing.engine.identify_untargeted_genes",
                ("return", []),
                False,
            ),
            (
                "med_research.pipeline.drug_repurposing.engine.score_candidates",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "semantic_search",
        "module": "med_research.pipeline.semantic_search.engine",
        "argv": ["--query", "lupus", "--top", "5", "--disease", "sle"],
        "patches": [
            (
                "med_research.pipeline.semantic_search.engine.SemanticSearchEngine.search",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "gene_expression",
        "module": "med_research.pipeline.gene_expression.correlator",
        "argv": ["--top", "5", "--disease", "sle"],
        "patches": [
            (
                "med_research.pipeline.gene_expression.correlator.compute_all_correlations",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "drug_synergy",
        "module": "med_research.pipeline.drug_synergy.engine",
        "argv": ["--top", "5", "--disease", "sle"],
        "patches": [
            (
                "med_research.pipeline.drug_synergy.engine.compute_synergy",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "ml_predictor",
        "module": "med_research.pipeline.ml_predictor.predictor",
        "argv": ["--disease", "sle", "--top", "5", "--no-shap"],
        "patches": [
            (
                "med_research.pipeline.ml_predictor.predictor.build_graph",
                (
                    "return",
                    SimpleNamespace(number_of_nodes=lambda: 1, number_of_edges=lambda: 1),
                ),
                True,
            ),
            (
                "med_research.pipeline.ml_predictor.predictor.train_and_predict",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "network_pharmacology",
        "module": "med_research.pipeline.network_pharmacology.analyzer",
        "argv": ["--disease", "sle"],
        "patches": [
            (
                "med_research.pipeline.network_pharmacology.analyzer.compute_all_metrics",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "network_pharmacology_centrality",
        "module": "med_research.pipeline.network_pharmacology.analyzer",
        "argv": ["--centrality", "--disease", "sle"],
        "patches": [
            (
                "med_research.pipeline.network_pharmacology.analyzer.load_graph",
                ("return", SimpleNamespace()),
                False,
            ),
            (
                "med_research.pipeline.network_pharmacology.analyzer.compute_centrality",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "network_pharmacology_communities",
        "module": "med_research.pipeline.network_pharmacology.analyzer",
        "argv": ["--communities", "--disease", "sle"],
        "patches": [
            (
                "med_research.pipeline.network_pharmacology.analyzer.load_graph",
                ("return", SimpleNamespace()),
                False,
            ),
            (
                "med_research.pipeline.network_pharmacology.analyzer.compute_communities",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "cross_disease",
        "module": "med_research.pipeline.cross_disease.analyzer",
        "argv": ["--top", "5"],
        "patches": [
            (
                "med_research.pipeline.cross_disease.analyzer.compute_cross_disease_analysis",
                "raise",
                True,
            ),
        ],
    },
    {
        "id": "clinical_trials",
        "module": "med_research.pipeline.clinical_trials.tracker",
        "argv": ["--disease", "sle", "--max", "5"],
        "patches": [
            (
                "med_research.pipeline.clinical_trials.tracker.track_trials",
                "raise",
                True,
            ),
        ],
    },
]


@pytest.mark.parametrize(
    "case", CLI_MAIN_CASES, ids=[case["id"] for case in CLI_MAIN_CASES]
)
def test_engine_main_threads_cli_progress(case: dict, monkeypatch: pytest.MonkeyPatch):
    """Each engine main() passes ``cli_progress`` into the engine functions it calls."""
    module = importlib.import_module(case["module"])
    monkeypatch.setattr(sys, "argv", ["med-research", *case["argv"]])

    mocks: dict[str, MagicMock] = {}
    patchers = []
    for target, behavior, _expect in case["patches"]:
        mock = MagicMock()
        if behavior == "raise":
            mock.side_effect = _EngineCalled
        else:
            mock.return_value = behavior[1]
        mocks[target] = mock
        patchers.append(patch(target, mock))

    for patcher in patchers:
        patcher.start()
    try:
        with pytest.raises(_EngineCalled):
            module.main()
    finally:
        for patcher in patchers:
            patcher.stop()

    for target, _behavior, expect_callback in case["patches"]:
        if not expect_callback:
            continue
        mock = mocks[target]
        assert mock.call_args is not None, f"{case['id']} main never called {target}"
        kwargs = mock.call_args.kwargs
        assert kwargs.get("progress_callback") is cli_progress, (
            f"{case['id']} main must pass the shared cli_progress callback into "
            f"{target}, got {kwargs.get('progress_callback')!r}"
        )


def test_cli_progress_logs_standard_ticks(caplog):
    """cli_progress surfaces (step, current, total) ticks to the console logger."""
    with caplog.at_level(logging.INFO, logger="med_research.pipeline.progress"):
        cli_progress("scoring candidates", 3, 12)
        cli_progress("semantic search", 1, 1)

    assert "scoring candidates (3/12)" in caplog.text
    assert "semantic search" in caplog.text
