from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from app.models.file_record import FileRecord
from app.models.source import Source
from app.schemas.inventory import InventoryUpload, InventoryDelta
from typing import List, Optional
import datetime
from app.services.encryption import get_tenant_key_from_header, encrypt_deterministic

async def handle_inventory_upload(db: AsyncSession, upload: InventoryUpload, org_id: Optional[str] = None, tenant_key_hex: Optional[str] = None) -> int:
    try:
        # Delete existing records for this source
        await db.execute(delete(FileRecord).where(FileRecord.source_id == upload.source_id))
        
        # Derive key — client-provided key takes priority (zero-knowledge)
        key = get_tenant_key_from_header(tenant_key_hex, org_id)
        
        # Insert new records
        for item in upload.files:
            db_item = FileRecord(
                source_id=upload.source_id,
                path=encrypt_deterministic(item.path, key),
                relative_path=encrypt_deterministic(item.relative_path, key),
                size_bytes=item.size_bytes,
                mtime=item.mtime,
                hash_sha256=item.hash_sha256,
                image_hash=item.image_hash,
                org_id=org_id,
            )
            db.add(db_item)
        
        await db.commit()
        return len(upload.files)
    except Exception as e:
        await db.rollback()
        raise e

async def handle_inventory_delta(db: AsyncSession, delta: InventoryDelta, org_id: Optional[str] = None, tenant_key_hex: Optional[str] = None) -> None:
    try:
        key = get_tenant_key_from_header(tenant_key_hex, org_id)
        encrypted_rel_path = encrypt_deterministic(delta.file.relative_path, key)
        
        # Search for existing record by encrypted relative path on source
        stmt = select(FileRecord).where(
            FileRecord.source_id == delta.source_id,
            FileRecord.relative_path == encrypted_rel_path
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if delta.action == "delete":
            if existing:
                await db.delete(existing)
        elif delta.action == "upsert":
            if existing:
                existing.path = encrypt_deterministic(delta.file.path, key)
                existing.size_bytes = delta.file.size_bytes
                existing.mtime = delta.file.mtime
                existing.hash_sha256 = delta.file.hash_sha256
                existing.image_hash = delta.file.image_hash
            else:
                db_item = FileRecord(
                    source_id=delta.source_id,
                    path=encrypt_deterministic(delta.file.path, key),
                    relative_path=encrypted_rel_path,
                    size_bytes=delta.file.size_bytes,
                    mtime=delta.file.mtime,
                    hash_sha256=delta.file.hash_sha256,
                    image_hash=delta.file.image_hash,
                    org_id=org_id,
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
