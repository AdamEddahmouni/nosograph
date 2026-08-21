"""System API router — health checks, platform stats, disease registry."""

import logging
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Any

import redis
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from med_research.diseases.base import Disease
from med_research.diseases.identifiers import CI_VALIDATED_DISEASES
from med_research.pipeline.gateway import pipeline_gateway
from med_research.web.config import CELERY_BROKER_URL, WORKSPACE_DB_PATH
from med_research.web.dependencies import (
    get_candidates,
    get_kg_drugs,
    get_kg_genes,
    get_kg_pathways,
    get_knowledge_graph,
)
from med_research.web.disease_params import resolve_optional_query_disease
from med_research.web.models import (
    CoverageSummary,
    DiseaseInfo,
    DiseasesResponse,
    HealthResponse,
    PipelineModulesResponse,
    PlatformStats,
    ReadyResponse,
)

router = APIRouter(tags=["System"])
logger = logging.getLogger(__name__)


@router.get("/api/health", response_model=HealthResponse)
async def health() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": version("med-research"),
        "timestamp": datetime.now().isoformat(),
    }


def _check_redis() -> dict[str, str]:
    try:
        client = redis.Redis.from_url(
            CELERY_BROKER_URL,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )
        client.ping()
        return {"status": "ok"}
    except (redis.RedisError, OSError, ConnectionError) as exc:
        return {"status": "error", "detail": str(exc)}


def _check_celery() -> dict[str, str]:
    try:
        from med_research.web.tasks.analysis_tasks import celery_app

        conn = celery_app.connection()
        conn.ensure_connection(max_retries=1, timeout=1.0)
        conn.release()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _check_workspace_db() -> dict[str, str]:
    db_path = Path(WORKSPACE_DB_PATH)
    if not db_path.exists():
        return {"status": "degraded", "detail": f"Database not found at {db_path}"}
    if not db_path.is_file():
        return {"status": "error", "detail": f"Workspace path is not a file: {db_path}"}
    try:
        db_path.stat()
        return {"status": "ok"}
    except OSError as exc:
        return {"status": "error", "detail": str(exc)}


def _check_knowledge_graph() -> dict[str, str]:
    try:
        graph = get_knowledge_graph()
        if graph.number_of_nodes() == 0:
            return {"status": "degraded", "detail": "Knowledge graph has no nodes"}
        return {"status": "ok"}
    except Exception as exc:
        logger.warning("Readiness KG check failed: %s", exc)
        return {"status": "error", "detail": str(exc)}


@router.get("/api/ready", response_model=ReadyResponse)
async def ready() -> JSONResponse | dict[str, Any]:
    """Readiness probe — verifies Redis, Celery, workspace DB, and KG preload."""
    components = {
        "redis": _check_redis(),
        "celery": _check_celery(),
        "workspace_db": _check_workspace_db(),
        "knowledge_graph": _check_knowledge_graph(),
    }
    overall = "ok"
    if any(component["status"] == "error" for component in components.values()):
        overall = "error"
    elif any(component["status"] == "degraded" for component in components.values()):
        overall = "degraded"

    payload = {
        "status": overall,
        "version": version("med-research"),
        "timestamp": datetime.now().isoformat(),
        "components": components,
    }
    status_code = 200 if overall == "ok" else 503
    return JSONResponse(status_code=status_code, content=payload)


_DISEASE_REGISTRY_CACHE: dict[str, Any] = {"time": 0.0, "response": None}


def invalidate_system_disease_cache() -> None:
    _DISEASE_REGISTRY_CACHE["time"] = 0.0
    _DISEASE_REGISTRY_CACHE["response"] = None


@router.get("/api/system/diseases", response_model=DiseasesResponse)
async def disease_registry() -> DiseasesResponse:
    """List all available diseases (cached with short TTL).

    Scans the diseases/ tree and caches the result for 60s so diseases scaffolded via
    ``med-research disease add`` appear promptly without re-scanning thousands of files per request.
    """
    import json
    import time

    now = time.time()
    if _DISEASE_REGISTRY_CACHE["response"] is not None and (
        now - _DISEASE_REGISTRY_CACHE["time"] < 60.0
    ):
        return _DISEASE_REGISTRY_CACHE["response"]

    from med_research.diseases.base import Disease
    from med_research.diseases.context import (
        _counts_from_status_report,
        _gaps_from_status_report,
        _registry_by_id,
        _tier_from_status_report,
    )
    from med_research.diseases.coverage import coverage_for_disease
    from med_research.diseases.coverage_report import DEFAULT_MODULE_INPUTS
    from med_research.diseases.scaffold import sanitize_id
    from med_research.exceptions import DataValidationError

    catalog = pipeline_gateway.catalog()
    coverage_module_ids = {entry["coverage_module"]: entry["module_id"] for entry in catalog}
    registry_index = _registry_by_id()
    tier_index = _tier_from_status_report()
    gap_index = _gaps_from_status_report()
    counts_index = _counts_from_status_report()

    default_blocked_modules = {
        module: {
            "disease_id": "",
            "module": module,
            "level": "unsupported",
            "status": "blocked",
            "curated_inputs": ["profile", "genes", "drugs", "pathways", "relationships"],
            "missing_inputs": ["profile", "genes", "drugs", "pathways", "relationships"],
            "inferred_inputs": [],
            "warnings": [],
            "limitations": [
                "Core disease data is incomplete; run disease scaffolding or refresh before analysis."
            ],
        }
        for module in DEFAULT_MODULE_INPUTS
    }

    core_diseases = CI_VALIDATED_DISEASES
    diseases = []

    for disease_id in Disease.list_all():
        reg = registry_index.get(sanitize_id(disease_id), {})
        if disease_id not in core_diseases:
            precomputed = counts_index.get(disease_id)
            name = reg.get("name") or reg.get("label") or disease_id.replace("_", " ").title()
            g_cnt = precomputed.get("genes", 0) if precomputed else 0
            d_cnt = precomputed.get("drugs", 0) if precomputed else 0
            p_cnt = precomputed.get("pathways", 0) if precomputed else 0
            t_val = tier_index.get(disease_id, "blocked")
            g_val = gap_index.get(disease_id, [])

            mod_cov = {
                m: {**data, "disease_id": disease_id} for m, data in default_blocked_modules.items()
            }
            core_cov_dict = {
                "disease_id": disease_id,
                "module": "core",
                "level": "unsupported",
                "status": "blocked",
                "curated_inputs": ["profile", "genes", "drugs", "pathways", "relationships"],
                "missing_inputs": ["profile", "genes", "drugs", "pathways", "relationships"],
                "inferred_inputs": [],
                "warnings": [],
                "limitations": [
                    "Core disease data is incomplete; run disease scaffolding or refresh before analysis."
                ],
            }

            diseases.append(
                DiseaseInfo(
                    id=disease_id,
                    name=name,
                    description=reg.get("description", ""),
                    prevalence=reg.get("prevalence", ""),
                    genes=g_cnt,
                    drugs=d_cnt,
                    pathways=p_cnt,
                    mondo_curie=reg.get("mondo_id"),
                    efo_id=reg.get("efo_id"),
                    readiness_tier=t_val,
                    config_gaps=g_val,
                    coverage={
                        "core": core_cov_dict,
                        "modules": mod_cov,
                    },
                )
            )
            continue

        try:
            disease = Disease(disease_id)
            profile = disease.profile
            genes = disease.load_genes()
            drugs = disease.load_drugs()
            pathways = disease.load_pathways()
        except (
            ValueError,
            FileNotFoundError,
            KeyError,
            json.JSONDecodeError,
            OSError,
            DataValidationError,
        ):
            try:
                disease = Disease(disease_id)
                profile = disease.profile
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                continue
            genes = drugs = pathways = {"genes": [], "drugs": [], "pathways": []}

        core_cov = coverage_for_disease(disease_id)
        if core_cov.is_runnable:
            modules_cov = {
                module: pipeline_gateway.coverage(
                    coverage_module_ids[module],
                    disease_id,
                ).to_dict()
                for module in DEFAULT_MODULE_INPUTS
            }
        else:
            core_dict = core_cov.to_dict()
            modules_cov = {
                module: {
                    "disease_id": disease_id,
                    "module": module,
                    "level": "unsupported",
                    "status": "blocked",
                    "curated_inputs": [],
                    "missing_inputs": core_dict.get("missing_inputs", []),
                    "inferred_inputs": [],
                    "warnings": core_dict.get("warnings", []),
                    "limitations": core_dict.get("limitations", []),
                }
                for module in DEFAULT_MODULE_INPUTS
            }

        diseases.append(
            DiseaseInfo(
                id=disease_id,
                name=profile.name,
                description=profile.description,
                prevalence=profile.prevalence,
                genes=len(genes.get("genes", [])),
                drugs=len(drugs.get("drugs", [])),
                pathways=len(pathways.get("pathways", [])),
                mondo_curie=reg.get("mondo_id"),
                efo_id=reg.get("efo_id"),
                readiness_tier=tier_index.get(disease_id),
                config_gaps=gap_index.get(disease_id, []),
                coverage={
                    "core": core_cov.to_dict(),
                    "modules": modules_cov,
                },
            )
        )
    diseases.sort(key=lambda d: d.id)
    resp = DiseasesResponse(count=len(diseases), diseases=diseases)
    _DISEASE_REGISTRY_CACHE["time"] = now
    _DISEASE_REGISTRY_CACHE["response"] = resp
    return resp


@router.get("/api/system/corpus-status")
async def corpus_status(
    tier: str | None = Query(None, description="Optional tier filter (L3, L2, L1, L0, blocked)"),
    gap: str | None = Query(None, description="Optional config gap filter"),
    search: str | None = Query(None, description="Search by disease ID or name"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("disease_id", description="Sort field"),
    sort_desc: bool = Query(False, description="Sort descending"),
) -> dict[str, Any]:
    """Return corpus readiness tier aggregate and filterable disease completeness from the batch report."""
    from med_research.diseases.corpus_status import DEFAULT_STATUS_PATH, load_status_report

    report = load_status_report(DEFAULT_STATUS_PATH)
    if not report:
        from med_research.diseases.corpus_status import build_corpus_status

        report = build_corpus_status(limit=50, include_symptom_source=False)
    aggregate = report.get("aggregate", {})
    gap_counts: dict[str, int] = {}
    per_disease = report.get("per_disease", [])
    for row in per_disease:
        for g in row.get("config_gaps", []):
            gap_counts[g] = gap_counts.get(g, 0) + 1
    top_gaps = sorted(gap_counts.items(), key=lambda item: item[1], reverse=True)[:10]

    filtered = per_disease
    if tier:
        target_tier = tier.strip().lower()
        filtered = [r for r in filtered if str(r.get("tier", "")).lower() == target_tier]
    if gap:
        target_gap = gap.strip()
        filtered = [r for r in filtered if target_gap in r.get("config_gaps", [])]
    if search:
        s = search.strip().lower()
        filtered = [
            r
            for r in filtered
            if s in str(r.get("disease_id", "")).lower() or s in str(r.get("name", "")).lower()
        ]

    # Sort
    valid_sort_keys = {
        "disease_id",
        "name",
        "tier",
        "gene_count",
        "drug_count",
        "pathway_count",
        "symptom_count",
    }
    key = sort_by if sort_by in valid_sort_keys else "disease_id"

    def get_sort_val(item: dict[str, Any]) -> Any:
        val = item.get(key)
        if val is None:
            return "" if isinstance(key, str) else 0
        return val

    filtered.sort(key=get_sort_val, reverse=sort_desc)
    total_matching = len(filtered)
    paginated = filtered[offset : offset + limit]

    return {
        "aggregate": aggregate,
        "top_config_gaps": [{"field": k, "count": v} for k, v in top_gaps],
        "report_path": str(DEFAULT_STATUS_PATH),
        "total_matching": total_matching,
        "limit": limit,
        "offset": offset,
        "diseases": paginated,
    }


ResolvedDisease = Annotated[str, Depends(resolve_optional_query_disease)]


@router.get("/api/system/modules", response_model=PipelineModulesResponse)
async def pipeline_modules(
    disease: ResolvedDisease,
) -> dict[str, Any]:
    """List registered pipeline modules with per-disease coverage metadata."""
    modules = []
    for metadata in pipeline_gateway.catalog():
        coverage = pipeline_gateway.coverage(metadata["module_id"], disease)
        modules.append({**metadata, "coverage": coverage.to_dict()})

    return {
        "count": len(modules),
        "disease_id": disease,
        "modules": modules,
    }


@router.get("/api/system/cache/stats")
async def cache_stats() -> dict[str, Any]:
    """Return cache namespace statistics (auth-protected when API_KEY is set)."""
    from med_research.cache import CacheManager

    return CacheManager().stats()


@router.delete("/api/system/cache")
@router.delete("/api/system/cache/{namespace}")
async def cache_clear(namespace: str | None = None) -> dict[str, Any]:
    """Clear one cache namespace or all namespaces (auth-protected when API_KEY is set)."""
    from med_research.cache import CacheManager

    removed = CacheManager().clear(namespace=namespace)
    return {"removed": removed, "namespace": namespace}


def _disease_display_name(disease_id: str) -> str:
    try:
        return Disease(disease_id).profile.name
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return disease_id


def _coverage_summary_for_disease(disease_id: str) -> CoverageSummary:
    counts = {"full": 0, "partial": 0, "unsupported": 0}
    for metadata in pipeline_gateway.catalog():
        level = pipeline_gateway.coverage(metadata["module_id"], disease_id).level
        if level in counts:
            counts[level] += 1
    return CoverageSummary(**counts)


@router.get("/api/stats", response_model=PlatformStats)
async def platform_stats(
    disease: ResolvedDisease,
) -> dict[str, Any]:
    """Get platform statistics for a specific disease."""
    G = get_knowledge_graph(disease)
    genes = get_kg_genes(disease)
    drugs = get_kg_drugs(disease)
    pathways = get_kg_pathways(disease)
    candidates = get_candidates(disease)

    return {
        "disease_id": disease,
        "disease_name": _disease_display_name(disease),
        "kg_nodes": G.number_of_nodes(),
        "kg_edges": G.number_of_edges(),
        "genes": len(genes),
        "drugs": len(drugs),
        "pathways": len(pathways),
        "candidates": len(candidates),
        "modules": len(pipeline_gateway.catalog()),
        "diseases": len(Disease.list_all()),
        "coverage_summary": _coverage_summary_for_disease(disease).model_dump(),
    }
