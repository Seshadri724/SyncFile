import secrets
import hashlib
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.dependencies import verify_token
from app.models.source import Source
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
    token: str = Depends(verify_token) # Must be authenticated using master token
):
    # Only allow registration via the master API_TOKEN
    from app.config import settings
    if token != settings.API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the master API token can be used to register new sources."
        )

    agent_key = secrets.token_hex(32)
    key_hash = hashlib.sha256(agent_key.encode("utf-8")).hexdigest()

    new_source = Source(
        name=payload.name,
        kind=payload.kind,
        roots=payload.roots,
        agent_key_hash=key_hash,
        status="online"
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
    result = await db.execute(select(Source))
    sources = result.scalars().all()
    return [SourceResponse.model_validate(s) for s in sources]

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
