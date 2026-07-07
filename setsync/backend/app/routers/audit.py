from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import verify_token
from app.schemas.audit import AuditLogResponse
from app.services.audit_service import get_audit_logs

router = APIRouter(
    prefix="/audit-log",
    tags=["audit-log"],
    dependencies=[Depends(verify_token)]
)

@router.get("", response_model=AuditLogResponse)
async def query_audit_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    try:
        records, total_count = await get_audit_logs(db, limit, offset)
        return AuditLogResponse(
            actions=[r.to_dict() for r in records],
            total_count=total_count
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
