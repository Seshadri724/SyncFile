import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.dependencies import verify_token
from app.models.job import TransferJob
from app.schemas.jobs import SignaturesPayload, DeltaPayload, JobStatusUpdate
from typing import List

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"]
)

@router.get("/poll")
async def poll_jobs(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token)
):
    if not token.startswith("agent:"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only registered agents can poll jobs."
        )
    source_id = token.split(":")[1]
    
    # We find jobs that require action from this agent:
    # 1. As destination and status is "pending" (agent needs to compute signatures)
    # 2. As source and status is "signatures_ready" (agent needs to compute delta)
    # 3. As destination and status is "delta_ready" (agent needs to apply delta)
    stmt = select(TransferJob).where(
        ((TransferJob.destination_id == source_id) & (TransferJob.status.in_(["pending", "delta_ready"]))) |
        ((TransferJob.source_id == source_id) & (TransferJob.status == "signatures_ready"))
    )
    result = await db.execute(stmt)
    jobs = result.scalars().all()
    return [j.to_dict() for j in jobs]

@router.post("/{id}/signatures")
async def upload_signatures(
    id: str,
    payload: SignaturesPayload,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token)
):
    if not token.startswith("agent:"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only registered agents can upload signatures.")
    source_id = token.split(":")[1]

    job = await db.get(TransferJob, id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    if job.destination_id != source_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the destination agent can upload signatures.")

    job.target_signatures = json.dumps(payload.signatures)
    job.status = "signatures_ready"
    await db.commit()
    return {"message": "Signatures uploaded successfully."}

@router.get("/{id}/signatures")
async def download_signatures(
    id: str,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token)
):
    job = await db.get(TransferJob, id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    if not token.startswith("agent:") and token != "master":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access to signatures.")

    if token.startswith("agent:"):
        source_id = token.split(":")[1]
        if job.source_id != source_id and job.destination_id != source_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a participant in this job.")

    if not job.target_signatures:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signatures not yet ready.")

    return json.loads(job.target_signatures)

@router.post("/{id}/delta")
async def upload_delta(
    id: str,
    payload: DeltaPayload,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token)
):
    if not token.startswith("agent:"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only registered agents can upload delta ops.")
    source_id = token.split(":")[1]

    job = await db.get(TransferJob, id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    if job.source_id != source_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the source agent can upload delta ops.")

    # We need to serialize the delta operations. Some items in delta_ops might contain bytes, but since
    # delta payload schema expects JSON-serializable list, the agent encodes bytes as base64 or hex.
    # We store the list directly.
    job.delta_ops = json.dumps(payload.delta_ops)
    job.status = "delta_ready"
    await db.commit()
    return {"message": "Delta ops uploaded successfully."}

@router.get("/{id}/delta")
async def download_delta(
    id: str,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token)
):
    job = await db.get(TransferJob, id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    if not token.startswith("agent:") and token != "master":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access to delta ops.")

    if token.startswith("agent:"):
        source_id = token.split(":")[1]
        if job.source_id != source_id and job.destination_id != source_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a participant in this job.")

    if not job.delta_ops:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Delta ops not yet ready.")

    return json.loads(job.delta_ops)

@router.post("/{id}/status")
async def update_job_status(
    id: str,
    payload: JobStatusUpdate,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(verify_token)
):
    job = await db.get(TransferJob, id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    if token.startswith("agent:"):
        source_id = token.split(":")[1]
        if job.source_id != source_id and job.destination_id != source_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only participants can update status.")

    job.status = payload.status
    if payload.error_message:
        job.error_message = payload.error_message
        
    await db.commit()
    
    # If the job is completed, we can also log to backend action_records for auditing!
    if payload.status in ("completed", "failed"):
        # Let's see: we log it to action_records
        from app.models.action_record import ActionRecord
        # Find if there is already an action_record for this job or create one
        act_stmt = select(ActionRecord).where(ActionRecord.id == job.id)
        act_res = await db.execute(act_stmt)
        act_rec = act_res.scalar_one_or_none()
        if not act_rec:
            act_rec = ActionRecord(
                id=job.id,
                action_type=job.action_type,
                file_path=job.file_path,
                source=job.source_id,
                destination=job.destination_id,
                status=payload.status,
                triggered_by="api",
                error_message=payload.error_message
            )
            db.add(act_rec)
        else:
            act_rec.status = payload.status
            act_rec.error_message = payload.error_message
        await db.commit()

    return {"message": "Job status updated successfully."}
