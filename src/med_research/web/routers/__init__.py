"""API routers package."""

from med_research.web.routers.adverse_events import router as adverse_events_router
from med_research.web.routers.analysis import router as analysis_router
from med_research.web.routers.bioinformatics import router as bio_router
from med_research.web.routers.biomarker import router as biomarker_router
from med_research.web.routers.car_t import router as cart_router
from med_research.web.routers.cross_disease import router as cross_disease_router
from med_research.web.routers.evidence import router as evidence_router
from med_research.web.routers.export import router as export_router
from med_research.web.routers.expression import router as expression_router
from med_research.web.routers.extractor import router as extractor_router
from med_research.web.routers.kg import router as kg_router
from med_research.web.routers.monitor import router as monitor_router
from med_research.web.routers.repurpose import router as repurpose_router
from med_research.web.routers.semantic import router as semantic_router
from med_research.web.routers.synergy import router as synergy_router
from med_research.web.routers.system import router as system_router

routers = [kg_router, repurpose_router, bio_router, analysis_router, synergy_router, adverse_events_router, expression_router, cart_router, biomarker_router, semantic_router, evidence_router, extractor_router, monitor_router, cross_disease_router, export_router, system_router]
