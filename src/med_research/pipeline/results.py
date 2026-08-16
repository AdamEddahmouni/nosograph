"""TypedDict result records for pipeline module engines.

The engine entry points the adapters call (``score_all_drugs``,
``compute_all_scores``, ``compute_synergy``, ``score_candidates``,
``compute_biomarker_matrix``, ``compute_all_correlations``,
``compute_all_metrics``) return these record shapes. Declaring them lets
``make typecheck`` verify the hot path: record builders, engine entry
points, adapters, and the web dispatch seam all agree on the result
contract without changing the runtime dict behavior.

Where a record can legitimately be partial — a fallback branch, a tier
assigned after sorting, or a curated JSON payload with optional fields —
the TypedDict is ``total=False`` so only the guaranteed keys are
required. Consumers that need a key they know is present may still index
it directly; ``.get()`` returns the value type or ``None``.
"""

from __future__ import annotations

from typing import Any, TypeAlias

from pydantic import TypeAdapter
from typing_extensions import TypedDict


class AdverseEventScore(TypedDict):
    """One drug's safety profile score from ``adverse_events.profiler``."""

    drug_id: str
    drug_name: str
    disease_id: str
    disease_symptom_overlap_score: float
    disease_overlap_score: float
    lupus_symptom_overlap_score: float
    severity_burden_score: float
    chronic_use_safety_score: float
    disease_specific_risk_score: float
    dil_risk_score: float
    composite_safety_score: float
    n_disease_overlap_ae: int
    disease_overlap_ae: list[str]
    n_lupus_overlap_ae: int
    lupus_overlap_ae: list[str]
    evidence_grade: str
    profile_source: str
    profile_curated_inputs: list[str]
    profile_inferred_inputs: list[str]
    limitations: list[str]
    black_box_warnings: list[str]
    monitoring_required: str
    n_severe_ae: int


class CarTGeneScore(TypedDict):
    """One gene's CAR-T suitability score from ``car_t_predictor.predictor``."""

    gene_id: str
    gene_name: str
    category: str
    disease_id: str
    function: str
    disease_evidence: str
    lupus_evidence: str
    odds_ratio: float | None
    b_cell_dependency: float
    autoantibody_association: float
    plasma_cell_relevance: float
    cd19_targeting: float
    clinical_evidence: float
    composite_score: float
    tier: str
    recommendation: str


class SynergyPair(TypedDict, total=False):
    """One drug-pair synergy score from ``drug_synergy.engine``.

    ``tier`` is assigned after ranking, so it is not required at
    construction time.
    """

    drug_a_id: str
    drug_a_name: str
    drug_b_id: str
    drug_b_name: str
    target_complementarity: float
    pathway_diversity: float
    mechanism_orthogonality: float
    safety_non_overlap: float
    combined_evidence: float
    composite_score: float
    drug_a_type: str
    drug_b_type: str
    drug_a_mechanism: str
    drug_b_mechanism: str
    drug_a_category: str
    drug_b_category: str
    tier: str


class UntargetedGene(TypedDict):
    """One untargeted gene record from ``drug_repurposing.engine``."""

    id: str
    name: str
    function: str
    lupus_evidence: str
    disease_evidence: str
    odds_ratio: float | None
    category: str
    chromosome: str


class RepurposingCandidate(TypedDict, total=False):
    """One repurposing candidate from ``drug_repurposing.engine``.

    Curated ``candidates.json`` payloads carry a variable field set, so
    every key is optional; the scored fields added by ``score_candidates``
    are guaranteed once scoring completes.
    """

    gene_id: str
    id: str
    drug_name: str
    mechanism: str
    drug_category: str
    development_phase: str
    evidence_level: str
    rationale: str
    status: str
    references: list[str]
    target_similarity_score: float
    pathway_proximity_score: float
    mechanistic_rationale_score: float
    clinical_evidence_score: float
    safety_score: float
    adverse_event_score: float
    novelty_score: float
    kg_pathway_proximity: float
    final_proximity: float
    composite_score: float
    gene_name: str
    gene_category: str
    gene_function: str
    gene_lupus_evidence: str
    gene_disease_evidence: str
    gene_odds_ratio: float | None
    tier: str
    variant_functional_score: float
    variant_details: list[dict[str, Any]]
    tissue_expression_score: float
    top_expressing_tissues: list[dict[str, Any]]
    gtex_tissue_concordance: float


class BiomarkerRow(TypedDict, total=False):
    """One gene's cross-module biomarker score from ``biomarker_discovery``.

    ``map_gene_to_modules`` fills the per-module fields and
    ``score_biomarker`` appends the weighted dimensions; both layers are
    represented so either producer is valid on its own.
    """

    gene_id: str
    gene_name: str
    category: str
    function: str
    lupus_evidence: str
    odds_ratio: float | None
    expression_avg: float
    expression_max: float
    targeting_drugs: int
    cart_score: float
    cart_tier: str
    repurpose_avg: float
    repurpose_max: float
    repurpose_count: int
    safety_avg: float
    n_modules: int
    cross_module_mean: float
    consistency: float
    cross_module_consistency: float
    expression_predictiveness: float
    cart_alignment: float
    druggability: float
    biomarker_novelty: float
    composite_score: float
    best_modality: str
    best_modality_score: float
    tier: str


class ExpressionCorrelation(TypedDict, total=False):
    """One drug's expression-reversal score from ``gene_expression.correlator``.

    The failure fallback records only ``drug_id``/``drug_name``/
    ``composite_score``/``tier``, so the dimension fields are optional.
    """

    drug_id: str
    drug_name: str
    category: str
    type: str
    mechanism: str
    signature_reversal: float
    target_disease_overlap: float
    cell_type_specificity: float
    expression_evidence: float
    directionality: float
    composite_score: float
    tier: str


class GraphMetrics(TypedDict):
    """Graph-level topology metrics from ``network_pharmacology``."""

    n_nodes: int
    n_edges: int
    density: float
    n_components: int
    diameter: int
    avg_shortest_path: float
    avg_clustering: float
    assortativity: float


class CentralityEntry(TypedDict):
    """One node's centrality ranking row."""

    node_id: str
    score: float
    label: str
    type: str


class BridgeNode(TypedDict):
    """One bridge node (top betweenness) row."""

    node_id: str
    betweenness: float
    type: str
    label: str


class CommunityInfo(TypedDict):
    """One detected community."""

    id: int
    size: int
    dominant_type: str
    node_ids: list[str]
    node_labels: list[str]
    type_distribution: dict[str, int]


class CommunitiesResult(TypedDict):
    """Community-detection output."""

    communities: list[CommunityInfo]
    modularity: float
    n_communities: int
    algorithm: str


class NetworkCentralityResult(TypedDict):
    """One centrality metric response from ``network_pharmacology``."""

    metric: str
    nodes: list[CentralityEntry]
    total_nodes: int


class NetworkAnalysis(TypedDict, total=False):
    """Combined network-pharmacology output.

    A blocked run returns only ``coverage``/``status``, so the analysis
    sections are optional.
    """

    graph_metrics: GraphMetrics
    centrality: dict[str, list[CentralityEntry]]
    bridge_nodes: list[BridgeNode]
    communities: CommunitiesResult
    disease_id: str
    coverage: dict[str, object]
    status: str


# ── Bioinformatics (GWAS / enrichment / PPI) ────────────────────────────


class GwasResult(TypedDict, total=False):
    """Combined GWAS annotation output from ``bioinformatics.gwas``.

    A blocked run returns only ``coverage``/``status`` with empty payloads.
    """

    coverage: dict[str, Any]
    status: str
    gwas_results: dict[str, Any]
    crossref: dict[str, Any]


class EnrichmentResult(TypedDict, total=False):
    """Pathway-enrichment output from ``bioinformatics.enrichment``."""

    coverage: dict[str, Any]
    status: str
    gene_list: list[Any]
    enrichment_results: dict[str, Any]
    kg_pathway_matches: dict[str, Any]


class PpiResult(TypedDict, total=False):
    """PPI network + hub-score output from ``bioinformatics.ppi``."""

    coverage: dict[str, Any]
    status: str
    hub_scores: list[dict[str, Any]]
    crossref: dict[str, Any]
    graph: dict[str, Any]
    confidence: float


# ── Clinical trials ─────────────────────────────────────────────────────


class TrialRecord(TypedDict, total=False):
    """One parsed ClinicalTrials.gov trial from ``clinical_trials.tracker``.

    ``moa_category`` and ``kg_matches`` are attached after parsing.
    """

    nct_id: str
    title: str
    summary: str
    status: str
    phases: list[str]
    primary_phase: str
    phase_label: str
    interventions: list[str]
    intervention_types: list[str]
    sponsor_name: str
    sponsor_class: str
    enrollment: int
    start_date: str
    completion_date: str
    why_stopped: str
    conditions: list[str]
    moa_category: str
    kg_matches: dict[str, Any]


class TrialRunResult(TypedDict, total=False):
    """Full clinical-trial tracking output."""

    trials: list[TrialRecord]
    stats: dict[str, Any]
    kg_crossref: dict[str, Any]
    coverage: dict[str, Any]
    status: str


# ── ML target prediction ────────────────────────────────────────────────


class MlPrediction(TypedDict, total=False):
    """One gene's druggability prediction from ``ml_predictor.predictor``."""

    gene_id: str
    gene_name: str
    category: str
    druggability_score: float
    is_targeted: bool
    targeted_by: list[Any]
    odds_ratio: float | None
    degree: int
    pathway_count: int


class MlModelMetrics(TypedDict, total=False):
    """Cross-validation and availability metrics for ML training."""

    cv_roc_auc_mean: float
    cv_roc_auc_std: float
    n_genes: int
    n_targeted: int
    n_untargeted: int
    xgboost_available: bool
    shap_available: bool


class MlPredictionResult(TypedDict, total=False):
    """Full ML target-prediction output.

    A run with no extracted features returns only ``error``.
    """

    predictions: list[MlPrediction]
    top_untargeted: list[MlPrediction]
    feature_importance: dict[str, float]
    shap_summary: list[dict[str, Any]]
    shap_values: list[Any] | None
    feature_names: list[str]
    gene_ids: list[Any]
    model_metrics: MlModelMetrics
    error: str
    coverage: dict[str, Any]


# ── Semantic search ─────────────────────────────────────────────────────


class SemanticHit(TypedDict, total=False):
    """One semantic-search hit from ``semantic_search.engine``."""

    rank: int
    pmid: str
    title: str
    year: str
    journal: str
    similarity: float


class SemanticSearchResult(TypedDict, total=False):
    """Adapter-facing semantic search output."""

    results: list[SemanticHit]
    query: str
    indexed_count: int


# ── Literature mining ───────────────────────────────────────────────────


class LiteratureArticle(TypedDict, total=False):
    """One PubMed article from ``literature_mining.miner``.

    ``kg_matches``/``relevance_score`` are attached during cross-reference.
    """

    pmid: str
    title: str
    abstract: str
    authors: list[str]
    journal: str
    year: str
    publication_types: list[str]
    mesh_terms: list[str]
    kg_matches: dict[str, Any]
    relevance_score: float


class LiteratureResults(TypedDict, total=False):
    """Cross-referenced literature output from ``literature_mining.crossref``."""

    coverage: dict[str, Any]
    status: str
    article_matches: list[LiteratureArticle]
    candidate_support: dict[str, Any]
    gene_coverage: dict[str, Any]
    drug_coverage: dict[str, Any]
    novel_entities: dict[str, Any]
    variant_entities: list[str]
    clinical_entities: list[str]
    statistics_entities: list[str]
    dosage_entities: list[str]
    stats: dict[str, Any]
    extraction_stats: Any


class LiteratureMiningResult(TypedDict, total=False):
    """Adapter-facing literature-mining output (4-tuple unpacked)."""

    results: LiteratureResults
    entities: dict[str, Any]
    candidates: list[Any]
    extraction_stats: Any


# ── Evidence gather / extraction ────────────────────────────────────────


class EvidenceGatherResult(TypedDict, total=False):
    """Aggregated multi-source evidence output from ``evidence.gatherer``."""

    query: str
    sources_searched: list[str]
    total_results: int
    elapsed_seconds: float
    results_by_source: dict[str, Any]
    crossref: dict[str, Any]
    all_results: list[dict[str, Any]]
    generated_at: str
    coverage: dict[str, Any]
    status: str


class EvidenceExtractionResult(TypedDict, total=False):
    """LLM evidence-extraction output from ``evidence.extractor``."""

    query: str
    model: str
    total_extracted: int
    successful_extractions: int
    elapsed_seconds: float
    extractions: list[dict[str, Any]]
    stats: dict[str, Any]
    coverage: dict[str, Any]
    status: str
    error: str
    generated_at: str


# ── Virtual screening ───────────────────────────────────────────────────


class ScreeningTarget(TypedDict):
    """One untargeted gene candidate from ``virtual_screening.screening``."""

    id: str
    name: str
    category: str
    function: str


class ScreeningCompound(TypedDict, total=False):
    """One compound-library entry from ``virtual_screening.screening``."""

    id: str
    name: str
    type: str
    target: str
    mechanism: str
    category: str
    smiles: str
    mw: float
    logp: float
    hbd: int
    hba: int
    rotb: int
    tpsa: float
    rdkit_computed: bool


class ScreeningHit(TypedDict, total=False):
    """One scored compound--target pairing.

    The library fields are merged with the five scoring dimensions;
    ``tier`` and the ``vina_*`` fields are attached after scoring/docking.
    """

    id: str
    name: str
    type: str
    target: str
    mechanism: str
    category: str
    smiles: str
    mw: float
    logp: float
    hbd: int
    hba: int
    rotb: int
    tpsa: float
    rdkit_computed: bool
    binding_estimate: float
    druglikeness: float
    target_complementarity: float
    similarity_score: float
    novelty_score: float
    composite_score: float
    gene_id: str
    gene_name: str
    gene_category: str
    disease_id: str
    strategy_id: str
    strategy_fingerprint: str
    tier: str
    vina_docked: bool
    vina_best_kcal: float


class ScreeningTargetResult(TypedDict):
    """One target's screening block inside ``results_per_target``."""

    gene_info: dict[str, Any]
    top_compounds: list[ScreeningHit]
    vina_results: dict[str, Any]
    total_screened: int
    mean_score: float


class ScreeningStats(TypedDict, total=False):
    """Aggregate screening statistics; the blocked branch omits docking counts."""

    targets_screened: int
    compounds_screened: int
    total_pairings: int
    tier1_count: int
    tier2_count: int
    vina_docked_count: int
    vina_available: bool
    rdkit_available: bool
    vina_status: str


class ScreeningResult(TypedDict, total=False):
    """Adapter-facing virtual-screening output from ``screen_compounds``.

    A blocked run returns only ``coverage``/``status``/``disease_id`` with
    empty payloads.
    """

    results_per_target: dict[str, ScreeningTargetResult]
    all_results: list[ScreeningHit]
    target_genes: list[str]
    compound_library: list[ScreeningCompound]
    coverage: dict[str, Any]
    status: str
    disease_id: str
    strategy_id: str
    strategy_fingerprint: str
    strategy_limitations: list[str]
    stats: ScreeningStats


class UntargetedGenesResult(TypedDict):
    """The ``operation=untargeted_genes`` variant of the screening adapter."""

    untargeted_genes: list[ScreeningTarget]


# ── Cross-disease and monitoring ────────────────────────────────────────


class CrossDiseaseResult(TypedDict, total=False):
    """Full cross-disease comparison output."""

    disease_summary: dict[str, Any]
    shared_genes: Any
    shared_drugs: Any
    shared_pathways: Any
    disease_similarity: Any
    multi_disease_drugs: list[Any]
    cross_disease_repurposing: list[Any]
    total_diseases: int
    coverage: dict[str, Any]
    status: str


class ComparativeModulesResult(TypedDict, total=False):
    """Stacked biomarker/expression/synergy comparison output."""

    diseases: list[Any]
    modules: dict[str, Any]


class EvidenceMonitorResult(TypedDict, total=False):
    """Evidence-monitor snapshot or snapshot-diff output."""

    snapshot: dict[str, Any]
    diff: dict[str, Any]
    prev_snapshot: dict[str, Any]
    curr_snapshot: dict[str, Any]


# Public collection/result aliases used by adapters and dispatch.
AdverseEventResults: TypeAlias = list[AdverseEventScore]
BiomarkerResults: TypeAlias = list[BiomarkerRow]
CarTResults: TypeAlias = list[CarTGeneScore]
ExpressionResults: TypeAlias = list[ExpressionCorrelation]
RepurposingResults: TypeAlias = list[RepurposingCandidate]
SynergyResults: TypeAlias = list[SynergyPair]
NetworkModuleResult: TypeAlias = NetworkAnalysis | NetworkCentralityResult | CommunitiesResult
VirtualScreeningResult: TypeAlias = ScreeningResult | UntargetedGenesResult


# ── Knowledge graph ─────────────────────────────────────────────────────


class KgBuildResult(TypedDict, total=False):
    """Knowledge-graph build output with coverage metadata."""

    graph: Any
    coverage: dict[str, Any]
    status: str


# ── Web service response envelopes ───────────────────────────────────────


class ModuleServiceResponse(TypedDict, total=False):
    """Common coverage/status envelope for registry-backed web services."""

    coverage: dict[str, Any]
    status: str


class CarTAnalysisResponse(ModuleServiceResponse):
    """``car_t_service.run_cart_analysis`` payload."""

    genes: list[CarTGeneScore]
    total_genes: int
    avg_score: float
    tier1_count: int
    tier2_count: int
    tier3_count: int


class RepurposingAnalysisResponse(ModuleServiceResponse):
    """``repurpose_service.run_repurposing`` payload."""

    candidates: list[RepurposingCandidate]
    total: int
    tier1_count: int
    tier2_count: int
    avg_score: float
    top_n: int


class GeneRepurposingResponse(TypedDict, total=False):
    """``repurpose_service.get_gene_repurposing`` payload."""

    gene_id: str
    gene_name: str
    gene_category: str
    gene_function: str
    disease_evidence: str
    disease_id: str
    odds_ratio: float | None
    candidates: list[RepurposingCandidate]
    best_score: float
    count: int


class BiomarkerAnalysisResponse(ModuleServiceResponse):
    """``biomarker_service.run_biomarker_analysis`` payload."""

    biomarkers: list[BiomarkerRow]
    total_genes: int
    avg_score: float
    tier1_count: int
    tier2_count: int


class ExpressionAnalysisResponse(ModuleServiceResponse):
    """``expression_service.run_correlation_analysis`` payload."""

    drugs: list[ExpressionCorrelation]
    total_drugs: int
    avg_score: float
    tier1_count: int
    tier2_count: int
    tier3_count: int


class SemanticSearchResponse(ModuleServiceResponse):
    """``semantic_service.run_semantic_search`` payload."""

    query: str
    results: list[SemanticHit]
    total_results: int
    indexed_articles: int


class SynergyAnalysisResponse(ModuleServiceResponse):
    """``synergy_service.run_synergy`` payload."""

    pairs: list[SynergyPair]
    total_pairs: int
    tier1_count: int
    tier2_count: int
    tier3_count: int
    avg_score: float
    max_score: float


class MultiOmicsItem(TypedDict, total=False):
    gene_id: str
    gene_name: str
    dominant_cell_type: str
    scrna_enrichment: float
    gwas_risk_weight: float
    bulk_concordance: float
    composite_score: float
    tier: str


class MultiOmicsResult(TypedDict, total=False):
    disease_id: str
    targets: list[MultiOmicsItem]
    top_target: str
    cell_types_analyzed: list[str]
    total_genes: int


class Structure3DItem(TypedDict, total=False):
    gene_id: str
    gene_name: str
    uniprot_id: str
    plddt_score: float
    confidence_category: str
    plddt_breakdown: dict[str, float]
    domain_boundaries: list[str]
    active_site_residues: list[str]
    pocket_volume_A3: float
    docking_readiness_score: float
    pdb_id: str
    alphafold_cif_url: str
    alphafold_pae_url: str
    druggability_tier: str


class Structure3DResult(TypedDict, total=False):
    disease_id: str
    structures: list[Structure3DItem]
    high_confidence_count: int
    mean_plddt: float
    total_structures: int


class AdmetItem(TypedDict, total=False):
    drug_id: str
    drug_name: str
    herg_inhibition_risk: str
    bbb_permeability: str
    cyp_inhibition_profile: list[str]
    lipinski_violations: int
    composite_safety_score: float
    tier: str


class AdmetResult(TypedDict, total=False):
    disease_id: str
    profiles: list[AdmetItem]
    safe_candidate_count: int
    total_drugs: int


class CrisprItem(TypedDict, total=False):
    gene_id: str
    gene_name: str
    loef_score: float
    pli_score: float
    grna_specificity_score: float
    delivery_accessibility: str
    crispr_priority_score: float
    feasibility_tier: str


class CrisprResult(TypedDict, total=False):
    disease_id: str
    candidates: list[CrisprItem]
    high_priority_count: int
    total_genes: int


# Raw adapter payload contracts. The knowledge graph and Workspace are excluded
# because they already have concrete NetworkX/Pydantic models at their seams.
RESULT_CONTRACTS: dict[str, Any] = {
    "adverse_events": AdverseEventResults,
    "biomarker_discovery": BiomarkerResults,
    "car_t_predictor": CarTResults,
    "clinical_trials": TrialRunResult,
    "cross_disease": CrossDiseaseResult | ComparativeModulesResult,
    "drug_repurposing": RepurposingResults,
    "drug_synergy": SynergyResults,
    "evidence_gather": EvidenceGatherResult,
    "evidence_monitor": EvidenceMonitorResult,
    "gene_expression": ExpressionResults,
    "gwas": GwasResult,
    "enrichment": EnrichmentResult,
    "literature_mining": LiteratureMiningResult,
    "llm_extractor": EvidenceExtractionResult,
    "ml_predictor": MlPredictionResult,
    "network_pharmacology": NetworkModuleResult,
    "ppi": PpiResult,
    "semantic_search": SemanticSearchResult,
    "virtual_screening": VirtualScreeningResult,
    "multi_omics": MultiOmicsResult,
    "structure_3d": Structure3DResult,
    "admet": AdmetResult,
    "crispr": CrisprResult,
}


_ADAPTER_CACHE: dict[str, TypeAdapter[Any]] = {
    module_id: TypeAdapter(contract) for module_id, contract in RESULT_CONTRACTS.items()
}


def result_contract_name(module_id: str) -> str:
    """Return a stable display name for a module's raw result contract."""
    contract = RESULT_CONTRACTS.get(module_id)
    fallback = "".join(part.capitalize() for part in module_id.split("_")) + "Result"
    if contract is None:
        return fallback
    name = getattr(contract, "__name__", None)
    if isinstance(name, str):
        return name
    return fallback


def result_contract_schema(module_id: str) -> dict[str, Any]:
    """Return a JSON-schema-shaped description for a module result contract."""
    adapter = _ADAPTER_CACHE.get(module_id)
    if adapter is None:
        contract = RESULT_CONTRACTS.get(module_id)
        if contract is None:
            return {
                "title": result_contract_name(module_id),
                "type": "object",
                "description": "Concrete adapter result; no TypedDict contract is registered.",
            }
        adapter = TypeAdapter(contract)
        _ADAPTER_CACHE[module_id] = adapter
    return adapter.json_schema()


def validate_result_contract(module_id: str, data: Any) -> Any:
    """Validate and normalize one raw adapter payload at the dispatch boundary.

    FastAPI validates transformed service responses separately through each
    route's ``response_model``. This validation protects the shared raw result
    seam before CLI, web, Celery, or report consumers can diverge.
    """
    adapter = _ADAPTER_CACHE.get(module_id)
    if adapter is None:
        contract = RESULT_CONTRACTS.get(module_id)
        if contract is None:
            return data
        adapter = TypeAdapter(contract)
        _ADAPTER_CACHE[module_id] = adapter
    adapter.validate_python(data)
    return data
