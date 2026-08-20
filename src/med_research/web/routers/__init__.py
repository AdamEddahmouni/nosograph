"""API routers package — grouped by domain."""

from med_research.web.api.pgx import router as pgx_router
from med_research.web.routers.adverse_events import router as adverse_events_router
from med_research.web.routers.agent import router as agent_router
from med_research.web.routers.analysis import router as analysis_router
from med_research.web.routers.auth import router as auth_router
from med_research.web.routers.bioinformatics import router as bio_router
from med_research.web.routers.biomarker import router as biomarker_router
from med_research.web.routers.biomed_analytics import (
    router as biomed_analytics_router,
)
from med_research.web.routers.car_t import router as cart_router
from med_research.web.routers.cross_disease import router as cross_disease_router
from med_research.web.routers.disease_admin import router as disease_admin_router
from med_research.web.routers.dossier import router as dossier_router
from med_research.web.routers.evidence import router as evidence_router
from med_research.web.routers.export import router as export_router
from med_research.web.routers.expression import router as expression_router
from med_research.web.routers.extractor import router as extractor_router
from med_research.web.routers.jobs import router as jobs_router
from med_research.web.routers.kg import router as kg_router
from med_research.web.routers.lead_opt import router as lead_opt_router
from med_research.web.routers.monitor import router as monitor_router
from med_research.web.routers.patient_matching import router as patient_matching_router
from med_research.web.routers.repurpose import router as repurpose_router
from med_research.web.routers.semantic import router as semantic_router
from med_research.web.routers.spatial import router as spatial_router
from med_research.web.routers.stream import router as stream_router
from med_research.web.routers.synergy import router as synergy_router
from med_research.web.routers.system import router as system_router
from med_research.web.routers.universal import router as universal_router
from med_research.web.routers.workspace import router as workspace_router

routers = [
    # Knowledge graph
    kg_router,
    # Drug discovery & scoring
    repurpose_router,
    synergy_router,
    adverse_events_router,
    expression_router,
    cart_router,
    biomarker_router,
    lead_opt_router,
    # Bioinformatics & analysis
    bio_router,
    analysis_router,
    spatial_router,
    # Evidence, search & agent
    semantic_router,
    evidence_router,
    extractor_router,
    monitor_router,
    agent_router,
    # Cross-disease & administration
    cross_disease_router,
    disease_admin_router,
    export_router,
    # Platform, clinical matching & workspace
    auth_router,
    system_router,
    workspace_router,
    jobs_router,
    stream_router,
    universal_router,
    dossier_router,
    pgx_router,
    patient_matching_router,
    biomed_analytics_router,
]
