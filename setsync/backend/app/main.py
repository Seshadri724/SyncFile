from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import time
import gzip
from app.database import init_db, AsyncSessionLocal
from app.routers import (
    inventory_router, sets_router, actions_router, audit_router,
    sources_router, jobs_router, analysis_router, query_router,
    plans_router, semantic_router, auth_router
)
from app.services import purge_old_audit_logs
from app.config import settings
from app.services.logger import setup_logging, logger

# Initialize structured logging before other imports trigger loggers
setup_logging()

# Initialize Sentry SDK for error/exception tracking
if settings.SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )
    logger.info("telemetry_initialized", service="sentry")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables
    await init_db()
    
    # Purge old audit logs (keep 30 days)
    async with AsyncSessionLocal() as session:
        try:
            count = await purge_old_audit_logs(session, max_age_days=30)
            logger.info("audit_logs_purged", count=count)
        except Exception as e:
            logger.error("audit_logs_purge_failed", error=str(e))
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

# Gzip request decompression middleware
@app.middleware("http")
async def decompress_gzip_requests(request: Request, call_next):
    if request.headers.get("content-encoding") == "gzip":
        try:
            body = await request.body()
            decompressed_body = gzip.decompress(body)
            async def receive():
                return {"type": "http.request", "body": decompressed_body, "more_body": False}
            request._receive = receive
        except Exception as e:
            logger.warning("gzip_decompression_failed", error=str(e))
    return await call_next(request)

# HTTP request-response logging middleware for latency telemetry
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    method = request.method
    path = request.url.path
    client_host = request.client.host if request.client else "unknown"
    
    response = await call_next(request)
    
    duration_ms = round((time.time() - start_time) * 1000, 2)
    status_code = response.status_code
    
    logger.info(
        "request_telemetry",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration_ms,
        client_host=client_host
    )
    
    response.headers["X-Response-Time-Ms"] = str(duration_ms)
    return response

# Include Routers
app.include_router(inventory_router)
app.include_router(sets_router)
app.include_router(actions_router)
app.include_router(audit_router)
app.include_router(sources_router)
app.include_router(jobs_router)
app.include_router(analysis_router)
app.include_router(query_router)
app.include_router(plans_router)
app.include_router(semantic_router)
app.include_router(auth_router)

@app.get("/")
def read_root():
    return {"status": "online", "service": "SetSync Core Service"}
