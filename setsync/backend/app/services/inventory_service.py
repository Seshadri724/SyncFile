from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from app.models.file_record import FileRecord
from app.schemas.inventory import InventoryUpload, InventoryDelta
from typing import List, Optional
import datetime

async def handle_inventory_upload(db: AsyncSession, upload: InventoryUpload) -> int:
    try:
        # Delete existing records for this source PC
        await db.execute(delete(FileRecord).where(FileRecord.source_pc == upload.source_pc))
        
        # Insert new records
        for item in upload.files:
            db_item = FileRecord(
                source_pc=upload.source_pc,
                path=item.path,
                relative_path=item.relative_path,
                size_bytes=item.size_bytes,
                mtime=item.mtime,
                hash_sha256=item.hash_sha256,
            )
            db.add(db_item)
        
        await db.commit()
        return len(upload.files)
    except Exception as e:
        await db.rollback()
        raise e

async def handle_inventory_delta(db: AsyncSession, delta: InventoryDelta) -> None:
    try:
        # Search for existing record by relative path on source PC
        stmt = select(FileRecord).where(
            FileRecord.source_pc == delta.source_pc,
            FileRecord.relative_path == delta.file.relative_path
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if delta.action == "delete":
            if existing:
                await db.delete(existing)
        elif delta.action == "upsert":
            if existing:
                existing.path = delta.file.path
                existing.size_bytes = delta.file.size_bytes
                existing.mtime = delta.file.mtime
                existing.hash_sha256 = delta.file.hash_sha256
            else:
                db_item = FileRecord(
                    source_pc=delta.source_pc,
                    path=delta.file.path,
                    relative_path=delta.file.relative_path,
                    size_bytes=delta.file.size_bytes,
                    mtime=delta.file.mtime,
                    hash_sha256=delta.file.hash_sha256
                )
                db.add(db_item)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise e

async def get_all_records(db: AsyncSession, source_pc: Optional[str] = None) -> List[FileRecord]:
    stmt = select(FileRecord)
    if source_pc:
        stmt = stmt.where(FileRecord.source_pc == source_pc)
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_inventory_status(db: AsyncSession):
    # Counts
    stmt_a = select(func.count(FileRecord.id)).where(FileRecord.source_pc == "A")
    stmt_b = select(func.count(FileRecord.id)).where(FileRecord.source_pc == "B")
    
    count_a = (await db.execute(stmt_a)).scalar_one()
    count_b = (await db.execute(stmt_b)).scalar_one()
    
    # Last scan time
    stmt_time_a = select(func.max(FileRecord.scanned_at)).where(FileRecord.source_pc == "A")
    stmt_time_b = select(func.max(FileRecord.scanned_at)).where(FileRecord.source_pc == "B")
    
    time_a = (await db.execute(stmt_time_a)).scalar()
    time_b = (await db.execute(stmt_time_b)).scalar()
    
    return {
        "pc_a_count": count_a,
        "pc_b_count": count_b,
        "pc_a_last_scan": time_a.isoformat() if time_a else None,
        "pc_b_last_scan": time_b.isoformat() if time_b else None,
    }
