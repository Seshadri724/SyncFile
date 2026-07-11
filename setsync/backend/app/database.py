from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

connect_args = {"timeout": 30.0} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_async_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)
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
