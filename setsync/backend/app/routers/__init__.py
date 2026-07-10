from app.routers.inventory import router as inventory_router
from app.routers.sets import router as sets_router
from app.routers.actions import router as actions_router
from app.routers.audit import router as audit_router
from app.routers.sources import router as sources_router
from app.routers.jobs import router as jobs_router
from app.routers.analysis import router as analysis_router

__all__ = [
    "inventory_router",
    "sets_router",
    "actions_router",
    "audit_router",
    "sources_router",
    "jobs_router",
    "analysis_router",
]
