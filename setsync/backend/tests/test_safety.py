import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.database import Base
from app.models.file_record import FileRecord
from app.models.source import Source
from app.services.action_service import execute_action
import datetime

@pytest.mark.anyio
async def test_safe_to_delete_policy():
    # 1. Setup in-memory sqlite engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    # 2. Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with AsyncSessionLocal() as db:
        now = datetime.datetime.utcnow()
        
        # Insert Source records
        source_a = Source(id="A", name="PC-A", kind="device", roots=[])
        source_b = Source(id="B", name="PC-B", kind="device", roots=[])
        db.add(source_a)
        db.add(source_b)
        await db.commit()
        
        # 1. Unique file on A
        unique_file = FileRecord(
            source_id="A",
            path="/root_a/unique.txt",
            relative_path="unique.txt",
            size_bytes=100,
            mtime=now,
            hash_sha256="unique_hash_abc"
        )
        db.add(unique_file)
        
        # 2. Duplicate/shared file on A and B
        shared_a = FileRecord(
            source_id="A",
            path="/root_a/shared.txt",
            relative_path="shared.txt",
            size_bytes=200,
            mtime=now,
            hash_sha256="shared_hash_123"
        )
        shared_b = FileRecord(
            source_id="B",
            path="/root_b/shared.txt",
            relative_path="shared.txt",
            size_bytes=200,
            mtime=now,
            hash_sha256="shared_hash_123"
        )
        db.add(shared_a)
        db.add(shared_b)
        await db.commit()
        
        # Test 1: Deleting unique file without force should raise ValueError (Safety Blocked)
        with pytest.raises(ValueError) as excinfo:
            await execute_action(
                db,
                relative_path="unique.txt",
                source="A",
                destination="A",
                action_type="delete",
                force=False
            )
        assert "Safety Block" in str(excinfo.value)
        
        # Test 2: Deleting unique file with force=True should succeed
        action_rec = await execute_action(
            db,
            relative_path="unique.txt",
            source="A",
            destination="A",
            action_type="delete",
            force=True
        )
        assert action_rec.action_type == "delete"
        assert action_rec.status == "pending"
        
        # Test 3: Deleting shared file (exists on B) without force should succeed
        shared_action = await execute_action(
            db,
            relative_path="shared.txt",
            source="A",
            destination="A",
            action_type="delete",
            force=False
        )
        assert shared_action.action_type == "delete"
        assert shared_action.status == "pending"

        await db.close()
    await engine.dispose()
