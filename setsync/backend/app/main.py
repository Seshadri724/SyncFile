from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database import init_db, AsyncSessionLocal
from app.routers import inventory_router, sets_router, actions_router, audit_router
from app.services import purge_old_audit_logs

from app.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables
    await init_db()
    
    # Purge old audit logs (keep 30 days)
    async with AsyncSessionLocal() as session:
        try:
            count = await purge_old_audit_logs(session, max_age_days=30)
            print(f"Startup: Cleaned up {count} expired audit log entries.")
        except Exception as e:
            print(f"Startup audit log cleanup failed: {e}")
    yield

app = FastAPI(
    title="SetSync Core Service API",
    description="Backend service for cross-PC file inventory & set-logic sync",
    version="1.0.0",
    lifespan=lifespan
)

# Parse CORS origins from config
cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

# Enable CORS for frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(inventory_router)
app.include_router(sets_router)
app.include_router(actions_router)
app.include_router(audit_router)

@app.get("/")
def read_root():
    return {"status": "online", "service": "SetSync Core Service"}
