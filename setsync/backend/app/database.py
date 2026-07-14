from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from app.config import settings

if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"timeout": 30.0}
    engine = create_async_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT
    )

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    # Import models here to register them with Base before metadata.create_all
    import app.models.file_record
    import app.models.action_record
    import app.models.undo_record
    import app.models.source
    import app.models.job
    import app.models.plan
    import app.models.tenant
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        from app.services.rls_policies import apply_rls_policies
        await apply_rls_policies(conn)

async def set_tenant_context(session: AsyncSession, org_id: str | None) -> None:
    """Sets the local session variable 'app.current_org_id' in PostgreSQL transaction.
    This value is used by PostgreSQL RLS policies to restrict queries to the tenant's organization.
    No-ops on other database dialects."""
    try:
        bind = session.bind
        if bind and bind.dialect.name == "postgresql":
            val = org_id or ""
            await session.execute(text(f"SET LOCAL app.current_org_id = :org_id"), {"org_id": val})
    except Exception:
        # Prevent failure on un-bound sessions or local dev setups
        pass
