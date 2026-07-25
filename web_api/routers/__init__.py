"""API routers package."""

from web_api.routers.adverse_events import router as adverse_events_router
from web_api.routers.analysis import router as analysis_router
from web_api.routers.bioinformatics import router as bio_router
from web_api.routers.biomarker import router as biomarker_router
from web_api.routers.car_t import router as cart_router
from web_api.routers.evidence import router as evidence_router
from web_api.routers.expression import router as expression_router
from web_api.routers.extractor import router as extractor_router
from web_api.routers.kg import router as kg_router
from web_api.routers.monitor import router as monitor_router
from web_api.routers.repurpose import router as repurpose_router
from web_api.routers.semantic import router as semantic_router
from web_api.routers.synergy import router as synergy_router
from web_api.routers.system import router as system_router

routers = [kg_router, repurpose_router, bio_router, analysis_router, synergy_router, adverse_events_router, expression_router, cart_router, biomarker_router, semantic_router, evidence_router, extractor_router, monitor_router, system_router]
