from app.routers.inventory import router as inventory_router
from app.routers.sets import router as sets_router
from app.routers.actions import router as actions_router
from app.routers.audit import router as audit_router

__all__ = [
    "inventory_router",
    "sets_router",
    "actions_router",
    "audit_router",
]
