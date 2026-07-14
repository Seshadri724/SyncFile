import secrets
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.dependencies import verify_token, require_role
from app.models.source import Source
from app.models.file_record import FileRecord
from app.schemas.sources import SourceRegister, SourceResponse, SourceRegisterResponse
from typing import List

router = APIRouter(
    prefix="/sources",
    tags=["sources"]
)

@router.post("/register", response_model=SourceRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_source(
    payload: SourceRegister,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(require_role(["admin"])) # Must be admin
):
    # Only allow registration via the master API_TOKEN or an admin user
    from app.config import settings
    
    # If authenticated via user, inherit their org_id
    org_id = payload.org_id
    if token.startswith("user:"):
        parts = token.split(":")
        user_org_id = parts[3]
        org_id = user_org_id

    agent_key = secrets.token_hex(32)
    key_hash = hashlib.sha256(agent_key.encode("utf-8")).hexdigest()

    new_source = Source(
        name=payload.name,
        kind=payload.kind,
        roots=payload.roots,
        agent_key_hash=key_hash,
        status="online",
        org_id=org_id
    )

    db.add(new_source)
    await db.commit()
    await db.refresh(new_source)

    return SourceRegisterResponse(
        source=SourceResponse.model_validate(new_source),
        agent_key=agent_key
    )

@router.get("", response_model=List[SourceResponse])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token)
):
    stmt = select(Source)
    # If user token, filter by org_id
    if token.startswith("user:"):
        parts = token.split(":")
        user_org_id = parts[3]
        stmt = stmt.where(Source.org_id == user_org_id)
        
    result = await db.execute(stmt)
    sources = result.scalars().all()
    return [SourceResponse.model_validate(s) for s in sources]

@router.post("/{id}/decommission")
async def decommission_source(
    id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(require_role(["admin"])) # Admin only
):
    source = await db.get(Source, id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found.")

    # Org check
    if token.startswith("user:"):
        parts = token.split(":")
        user_org_id = parts[3]
        if source.org_id != user_org_id:
            raise HTTPException(status_code=403, detail="Forbidden: Source belongs to a different organization.")

    # 1. Fetch all files currently present on this source
    files_stmt = select(FileRecord).where(FileRecord.source_id == id)
    files_res = await db.execute(files_stmt)
    source_files = files_res.scalars().all()

    # 2. Check if all files have at least one copy on another device in the same org
    unique_files = []
    for f in source_files:
        # Look for other copies on sources within the same org
        other_copies_stmt = (
            select(FileRecord)
            .join(Source, FileRecord.source_id == Source.id)
            .where(
                FileRecord.hash_sha256 == f.hash_sha256,
                FileRecord.size_bytes == f.size_bytes,
                FileRecord.source_id != id
            )
        )
        if source.org_id:
            other_copies_stmt = other_copies_stmt.where(Source.org_id == source.org_id)

        other_res = await db.execute(other_copies_stmt)
        other_copy = other_res.scalar_one_or_none()
        
        if not other_copy:
            from app.services.encryption import get_tenant_key_from_header, decrypt_deterministic
            tenant_key_hex = getattr(request.state, 'tenant_key', None)
            key = get_tenant_key_from_header(tenant_key_hex, source.org_id)
            unique_files.append({
                "path": decrypt_deterministic(f.path, key),
                "relative_path": decrypt_deterministic(f.relative_path, key),
                "size_bytes": f.size_bytes
            })

    # If any file is unique, block decommissioning
    if unique_files:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Decommission Blocked: Unique files detected",
                "unique_files": unique_files,
                "message": f"Cannot decommission source. {len(unique_files)} files exist ONLY on this device. Backup/sync them first."
            }
        )

    # 3. Perform Decommission
    source.status = "decommissioned"
    
    # Delete all file records associated with this decommissioned source
    from sqlalchemy import delete
    await db.execute(delete(FileRecord).where(FileRecord.source_id == id))
    await db.commit()

    import datetime
    cert = f"""# SetSync Decommission Certificate
**Secure Device Retirement Audit Report**

- **Device Name:** {source.name}
- **Device ID:** {source.id}
- **Retirement Date:** {datetime.datetime.utcnow().isoformat()}
- **Organization ID:** {source.org_id or 'Global'}
- **Safety Status:** VERIFIED SAFE
- **Active Files Removed from Inventory:** {len(source_files)}

---
*Verified & signed by SetSync Governance Engine. All device records safely replicated elsewhere.*
"""

    return {
        "status": "decommissioned",
        "message": f"Source '{source.name}' successfully decommissioned.",
        "certificate": cert
    }

@router.post("/{id}/sync-remote")
async def sync_remote_source(
    id: str,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token)
):
    source = await db.get(Source, id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found.")
    if source.kind != "remote":
        raise HTTPException(status_code=400, detail="Only remote cloud sources can be synced directly via rclone.")

    if not source.roots:
        raise HTTPException(status_code=400, detail="Remote source has no roots configured.")

    from app.services.rclone import list_remote_files
    from app.models.file_record import FileRecord
    from sqlalchemy import delete

    # Clear existing file records for this remote source
    await db.execute(delete(FileRecord).where(FileRecord.source_id == id))
    
    total_records = 0
    for root in source.roots:
        try:
            files = await list_remote_files(root)
            for f in files:
                db_item = FileRecord(
                    source_id=id,
                    path=f["path"],
                    relative_path=f["relative_path"],
                    size_bytes=f["size_bytes"],
                    mtime=f["mtime"],
                    hash_sha256=f["hash_sha256"]
                )
                db.add(db_item)
                total_records += 1
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to scan remote root '{root}': {e}")
            
    await db.commit()
    return {"message": "Remote source synced successfully", "records_ingested": total_records}
