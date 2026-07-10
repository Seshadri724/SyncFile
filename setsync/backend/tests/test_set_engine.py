import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.database import Base
from app.models.file_record import FileRecord
from app.models.source import Source
from app.services.set_engine import get_computed_sets_from_db, get_summary_from_db
import datetime

@pytest.mark.anyio
async def test_compute_sets_db():
    # 1. Setup in-memory sqlite engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    # 2. Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # 3. Open session and insert mock records
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with AsyncSessionLocal() as db:
        now = datetime.datetime.utcnow()
        
        # Insert Source records first to satisfy FK constraint
        source_a = Source(id="A-UUID", name="PC-A", kind="device", roots=[])
        source_b = Source(id="B-UUID", name="PC-B", kind="device", roots=[])
        db.add(source_a)
        db.add(source_b)
        await db.commit()

        source_x = "A-UUID"
        source_y = "B-UUID"
        
        # Identical file on A and B (Intersection)
        db.add(FileRecord(source_id=source_x, path="/root_a/shared.txt", relative_path="shared.txt", size_bytes=100, mtime=now, hash_sha256="hash_shared"))
        db.add(FileRecord(source_id=source_y, path="/root_b/shared.txt", relative_path="shared.txt", size_bytes=100, mtime=now, hash_sha256="hash_shared"))
        
        # Conflict (same path, different hash)
        db.add(FileRecord(source_id=source_x, path="/root_a/conflict.txt", relative_path="conflict.txt", size_bytes=200, mtime=now, hash_sha256="hash_a"))
        db.add(FileRecord(source_id=source_y, path="/root_b/conflict.txt", relative_path="conflict.txt", size_bytes=250, mtime=now, hash_sha256="hash_b"))
        
        # Only on PC A
        db.add(FileRecord(source_id=source_x, path="/root_a/only_a.txt", relative_path="only_a.txt", size_bytes=300, mtime=now, hash_sha256="hash_only_a"))
        
        # Only on PC B
        db.add(FileRecord(source_id=source_y, path="/root_b/only_b.txt", relative_path="only_b.txt", size_bytes=400, mtime=now, hash_sha256="hash_only_b"))
        
        # Cross-reference match (different path, same hash)
        db.add(FileRecord(source_id=source_x, path="/root_a/diff_path_a.txt", relative_path="diff_path_a.txt", size_bytes=500, mtime=now, hash_sha256="hash_cross"))
        db.add(FileRecord(source_id=source_y, path="/root_b/diff_path_b.txt", relative_path="diff_path_b.txt", size_bytes=500, mtime=now, hash_sha256="hash_cross"))
        
        await db.commit()
        
        # 4. Fetch computed sets from db
        union_rows = await get_computed_sets_from_db(db, source_x, source_y, "union")
        intersection_rows = await get_computed_sets_from_db(db, source_x, source_y, "intersection")
        conflict_rows = await get_computed_sets_from_db(db, source_x, source_y, "conflicts")
        only_a_rows = await get_computed_sets_from_db(db, source_x, source_y, "only_a")
        only_b_rows = await get_computed_sets_from_db(db, source_x, source_y, "only_b")
        
        summary = await get_summary_from_db(db, source_x, source_y)
        
        # 5. Assertions
        assert len(union_rows) == 5
        assert summary.union_count == 5
        assert len(intersection_rows) == 2  # shared.txt + cross-matched
        assert summary.intersection_count == 2
        assert len(conflict_rows) == 1      # conflict.txt
        assert summary.conflict_count == 1
        assert len(only_a_rows) == 1        # only_a.txt
        assert summary.only_a_count == 1
        assert len(only_b_rows) == 1        # only_b.txt
        assert summary.only_b_count == 1
        
        # Verify details
        shared = next(r for r in union_rows if r.relative_path == "shared.txt")
        assert shared.location == "Both"
        assert shared.size_bytes == 100
        
        conflict = next(r for r in union_rows if r.relative_path == "conflict.txt")
        assert conflict.location == "Conflict"
        assert conflict.size_bytes == 200
        
        # Clean up database
        await db.close()
    await engine.dispose()
