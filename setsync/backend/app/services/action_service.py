import datetime
import uuid
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from app.config import settings
from app.models.action_record import ActionRecord
from app.models.undo_record import UndoRecord
from app.models.file_record import FileRecord
from app.models.job import TransferJob
from app.services.audit_service import log_action
from typing import Dict, Any, Optional

async def get_dry_run_preview(
    db: AsyncSession,
    relative_path: str,
    source: str,       # source_id
    destination: str,  # destination_id
    action_type: str
) -> Dict[str, Any]:
    # 1. Fetch file record from source database
    src_stmt = select(FileRecord).where(
        FileRecord.source_id == source,
        FileRecord.relative_path == relative_path
    )
    src_result = await db.execute(src_stmt)
    src_rec = src_result.scalar_one_or_none()
    
    if not src_rec:
        raise FileNotFoundError(f"Source file not found in inventory: {relative_path}")

    src_size = src_rec.size_bytes
    src_mtime = src_rec.mtime

    # 2. Fetch file record from destination database (if exists)
    dest_stmt = select(FileRecord).where(
        FileRecord.source_id == destination,
        FileRecord.relative_path == relative_path
    )
    dest_result = await db.execute(dest_stmt)
    dest_rec = dest_result.scalar_one_or_none()

    dest_exists = dest_rec is not None
    dest_size = None
    dest_mtime = None
    will_overwrite = False

    if dest_exists:
        dest_size = dest_rec.size_bytes
        dest_mtime = dest_rec.mtime
        will_overwrite = True
        
        # Formulate age status message
        time_diff = src_mtime - dest_mtime
        if time_diff.total_seconds() > 0:
            age_status = "newer"
        elif time_diff.total_seconds() < 0:
            age_status = "older"
        else:
            age_status = "identical in age"
        
        message = (
            f"Destination file already exists. Overwriting with a file that is "
            f"{age_status} ({src_size} bytes vs {dest_size} bytes)."
        )
    else:
        message = f"File will be copied to destination ({src_size} bytes)."

    return {
        "action_type": action_type,
        "file_path": relative_path,
        "source": source,
        "destination": destination,
        "will_overwrite": will_overwrite,
        "source_size": src_size,
        "dest_size": dest_size,
        "source_mtime": src_mtime.isoformat() if src_mtime else None,
        "dest_mtime": dest_mtime.isoformat() if dest_mtime else None,
        "message": message,
    }

async def execute_action(
    db: AsyncSession,
    relative_path: str,
    source: str,       # source_id
    destination: str,  # destination_id
    action_type: str,  # "copy", "move", "delete"
    triggered_by: str = "ui",
    force: bool = False
) -> ActionRecord:
    # 1. Fetch file record to find metadata (size, hash)
    file_stmt = select(FileRecord).where(
        FileRecord.source_id == source,
        FileRecord.relative_path == relative_path
    )
    file_res = await db.execute(file_stmt)
    file_rec = file_res.scalar_one_or_none()
    if not file_rec:
        raise FileNotFoundError(f"File not found in source inventory: {relative_path}")
        
    # 2. Check duplicate count across OTHER active sources
    dup_stmt = select(func.count(FileRecord.id)).where(
        FileRecord.hash_sha256 == file_rec.hash_sha256,
        FileRecord.source_id != source
    )
    dup_count = (await db.execute(dup_stmt)).scalar_one()
    is_unique = (dup_count < 1)

    # 3. Policy validation check
    from app.services.policy import validate_action_policy
    validate_action_policy(
        relative_path=relative_path,
        action_type=action_type,
        size_bytes=file_rec.size_bytes,
        is_unique=is_unique,
        force=force
    )

    # 1. Generate unique UUID for the action and job
    action_id = str(uuid.uuid4())

    # 2. Create pending ActionRecord for UI & Audit tracking
    action_rec = ActionRecord(
        id=action_id,
        action_type=action_type,
        file_path=relative_path,
        source=source,
        destination=destination,
        status="pending",
        triggered_by=triggered_by
    )
    db.add(action_rec)

    # 3. Create active TransferJob for Agent execution
    job = TransferJob(
        id=action_id,
        file_path=relative_path,
        source_id=source,
        destination_id=destination,
        action_type=action_type,
        status="pending"
    )
    db.add(job)
    await db.commit()
    await db.refresh(action_rec)
    return action_rec

async def undo_action(db: AsyncSession, action_id: str) -> ActionRecord:
    action_rec = await db.get(ActionRecord, action_id)
    if not action_rec:
        raise ValueError("Action not found")
        
    if action_rec.status != "completed":
        raise ValueError(f"Cannot undo action in status: {action_rec.status}")
        
    stmt = select(UndoRecord).where(UndoRecord.action_id == action_id)
    undo_result = await db.execute(stmt)
    undo_rec = undo_result.scalar_one_or_none()
    
    if not undo_rec:
        raise ValueError("Undo record not found")
    if undo_rec.restored:
        raise ValueError("Action already undone")
        
    try:
        undo_audit_id = str(uuid.uuid4())
        undo_audit = ActionRecord(
            id=undo_audit_id,
            action_type="undo",
            file_path=action_rec.file_path,
            source=action_rec.destination,
            destination=action_rec.source,
            status="pending",
            triggered_by=action_rec.triggered_by
        )
        db.add(undo_audit)

        # Create restore TransferJob for destination agent
        if action_rec.action_type == "copy":
            if undo_rec.backup_path:
                job = TransferJob(
                    id=undo_audit_id,
                    file_path=action_rec.file_path,
                    source_id=action_rec.destination,
                    destination_id=action_rec.destination,
                    action_type="restore",
                    status="pending",
                    target_signatures=json.dumps({"backup_path": undo_rec.backup_path})
                )
            else:
                job = TransferJob(
                    id=undo_audit_id,
                    file_path=action_rec.file_path,
                    source_id=action_rec.destination,
                    destination_id=action_rec.destination,
                    action_type="delete",
                    status="pending"
                )
        elif action_rec.action_type == "move":
            job = TransferJob(
                id=undo_audit_id,
                file_path=action_rec.file_path,
                source_id=action_rec.destination,
                destination_id=action_rec.source,
                action_type="move",
                status="pending",
                target_signatures=json.dumps({"backup_path": undo_rec.backup_path})
            )
        else:
            raise ValueError(f"Cannot undo action type: {action_rec.action_type}")
            
        db.add(job)
        undo_rec.restored = True
        action_rec.status = "undone"
        await db.commit()
        await db.refresh(action_rec)
        
    except Exception as e:
        await db.rollback()
        raise e
        
    return action_rec

async def cleanup_trash(db: AsyncSession) -> int:
    now = datetime.datetime.utcnow()
    stmt = select(UndoRecord).where(UndoRecord.expires_at < now)
    result = await db.execute(stmt)
    records = result.scalars().all()
    
    count = 0
    for rec in records:
        await db.delete(rec)
        count += 1
        
    await db.commit()
    return count
