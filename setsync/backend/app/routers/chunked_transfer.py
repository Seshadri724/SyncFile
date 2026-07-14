from fastapi import APIRouter, Depends, HTTPException, Header, Request, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import verify_token, get_current_org_id
from app.services.chunked_transfer import (
    init_chunked_upload, get_session_info, receive_chunk, finalize_upload, get_session_dir
)
from app.services.storage_backend import get_storage_backend
from app.config import settings
from app.models.job import TransferJob
from app.models.source import Source
from pydantic import BaseModel
import os
import json
import hashlib

router = APIRouter(
    prefix="/transfer",
    tags=["transfer"]
)

class InitUploadPayload(BaseModel):
    session_id: str
    total_chunks: int
    chunk_size: int
    file_sha256: str
    file_path: str

@router.post("/init")
async def initialize_session(
    payload: InitUploadPayload,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token)
):
    try:
        org_id = get_current_org_id(token)
        
        # Check if there is an associated TransferJob for this session
        job = await db.get(TransferJob, payload.session_id)
        if job:
            job.transfer_session_id = payload.session_id
            await db.commit()
            
        metadata = init_chunked_upload(
            session_id=payload.session_id,
            total_chunks=payload.total_chunks,
            chunk_size=payload.chunk_size,
            file_sha256=payload.file_sha256,
            file_path=payload.file_path,
            org_id=org_id
        )
        return {"message": "Chunked upload session initialized", "metadata": metadata}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/{session_id}")
async def get_session_status(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token)
):
    org_id = get_current_org_id(token)
    
    # Verify access permission and resolve organization subfolder
    resolved_org_id = org_id
    job = await db.get(TransferJob, session_id)
    if job:
        source = await db.get(Source, job.source_id)
        if source:
            if org_id and source.org_id != org_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
            resolved_org_id = source.org_id
            
    info = get_session_info(session_id, resolved_org_id)
    if not info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return info

@router.post("/{session_id}/chunk/{index}")
async def upload_chunk(
    session_id: str,
    index: int,
    request: Request,
    x_chunk_sha256: str = Header(..., alias="X-Chunk-SHA256"),
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token)
):
    org_id = get_current_org_id(token)
    
    # Verify access permission and resolve organization subfolder
    resolved_org_id = org_id
    job = await db.get(TransferJob, session_id)
    if job:
        source = await db.get(Source, job.source_id)
        if source:
            if org_id and source.org_id != org_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
            resolved_org_id = source.org_id

    # Read raw body
    chunk_data = await request.body()
    
    # Enforce staging storage quota (DoS Protection)
    backend = get_storage_backend()
    current_usage = backend.get_org_usage_bytes(resolved_org_id)
    if current_usage + len(chunk_data) > settings.TENANT_STORAGE_QUOTA_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Staging storage quota exceeded for this organization."
        )
    
    success = receive_chunk(
        session_id=session_id,
        chunk_index=index,
        chunk_data=chunk_data,
        chunk_sha256=x_chunk_sha256,
        org_id=resolved_org_id
    )
    
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chunk verification failed or session missing")
        
    return {"message": f"Chunk {index} uploaded and verified successfully"}

@router.get("/{session_id}/chunk/{index}")
async def download_chunk(
    session_id: str,
    index: int,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token)
):
    org_id = get_current_org_id(token)
    
    # Verify access permission and resolve organization subfolder
    resolved_org_id = org_id
    job = await db.get(TransferJob, session_id)
    if job:
        source = await db.get(Source, job.source_id)
        if source:
            if org_id and source.org_id != org_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
            resolved_org_id = source.org_id

    session_dir = get_session_dir(session_id, resolved_org_id)
    chunk_path = session_dir / f"chunk_{index}"
    
    if not chunk_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found")
        
    with open(chunk_path, "rb") as f:
        data = f.read()
        
    # Calculate SHA256 to send in header
    chunk_sha256 = hashlib.sha256(data).hexdigest()
    
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "X-Chunk-SHA256": chunk_sha256,
            "Content-Length": str(len(data))
        }
    )

@router.post("/{session_id}/finalize")
async def finalize_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token)
):
    org_id = get_current_org_id(token)
    
    # Verify access permission and resolve organization subfolder
    resolved_org_id = org_id
    job = await db.get(TransferJob, session_id)
    if job:
        source = await db.get(Source, job.source_id)
        if source:
            if org_id and source.org_id != org_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
            resolved_org_id = source.org_id

    # Determine the target path for finalized file
    session_dir = get_session_dir(session_id, resolved_org_id)
    target_path = str(session_dir / "finalized_delta.json")
    
    success = finalize_upload(session_id, target_path, resolved_org_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Finalization failed: incomplete chunks or hash mismatch")
        
    # Update Job status to delta_ready if exists
    if job:
        job.status = "delta_ready"
        job.delta_ops = json.dumps([["chunked_transfer", session_id]])
        await db.commit()
        
    return {"message": "Upload session finalized successfully", "target_path": target_path}
