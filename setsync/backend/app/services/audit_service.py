from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.models.action_record import ActionRecord
from typing import List, Optional, Tuple

async def log_action(
    db: AsyncSession,
    action_type: str,
    file_path: str,
    source: str,
    destination: str,
    status: str,
    triggered_by: str,
    dry_run_preview: Optional[str] = None,
    error_message: Optional[str] = None
) -> ActionRecord:
    record = ActionRecord(
        action_type=action_type,
        file_path=file_path,
        source=source,
        destination=destination,
        status=status,
        triggered_by=triggered_by,
        dry_run_preview=dry_run_preview,
        error_message=error_message
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record

async def get_audit_logs(
    db: AsyncSession,
    limit: int = 100,
    offset: int = 0
) -> Tuple[List[ActionRecord], int]:
    stmt = select(ActionRecord).order_by(desc(ActionRecord.timestamp)).offset(offset).limit(limit)
    records = (await db.execute(stmt)).scalars().all()
    
    count_stmt = select(func.count(ActionRecord.id))
    total_count = (await db.execute(count_stmt)).scalar_one()
    
    return list(records), total_count

async def purge_old_audit_logs(db: AsyncSession, max_age_days: int = 30) -> int:
    import datetime
    from sqlalchemy import delete
    try:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=max_age_days)
        stmt = delete(ActionRecord).where(ActionRecord.timestamp < cutoff)
        res = await db.execute(stmt)
        await db.commit()
        return res.rowcount
    except Exception as e:
        await db.rollback()
        raise e
