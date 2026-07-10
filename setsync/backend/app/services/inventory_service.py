from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from app.models.file_record import FileRecord
from app.models.source import Source
from app.schemas.inventory import InventoryUpload, InventoryDelta
from typing import List, Optional
import datetime

async def handle_inventory_upload(db: AsyncSession, upload: InventoryUpload) -> int:
    try:
        # Delete existing records for this source
        await db.execute(delete(FileRecord).where(FileRecord.source_id == upload.source_id))
        
        # Insert new records
        for item in upload.files:
            db_item = FileRecord(
                source_id=upload.source_id,
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
        # Search for existing record by relative path on source
        stmt = select(FileRecord).where(
            FileRecord.source_id == delta.source_id,
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
                    source_id=delta.source_id,
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

async def get_all_records(db: AsyncSession, source_id: Optional[str] = None) -> List[FileRecord]:
    stmt = select(FileRecord)
    if source_id:
        stmt = stmt.where(FileRecord.source_id == source_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_inventory_status(db: AsyncSession):
    # Query all active sources
    result = await db.execute(select(Source))
    sources = result.scalars().all()
    
    source_statuses = []
    for s in sources:
        # Get count of file records for this source
        count_stmt = select(func.count(FileRecord.id)).where(FileRecord.source_id == s.id)
        count = (await db.execute(count_stmt)).scalar_one()
        
        # Get max scanned_at
        max_scan_stmt = select(func.max(FileRecord.scanned_at)).where(FileRecord.source_id == s.id)
        max_scan = (await db.execute(max_scan_stmt)).scalar()
        
        source_statuses.append({
            "source_id": s.id,
            "name": s.name,
            "count": count,
            "last_scan": max_scan.isoformat() if max_scan else None
        })
        
    return {"sources": source_statuses}
