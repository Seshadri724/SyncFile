import os
import datetime
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.config import settings
from app.models.action_record import ActionRecord
from app.models.undo_record import UndoRecord
from app.models.file_record import FileRecord
from app.transfer import get_transfer_engine
from app.services.audit_service import log_action
from typing import Dict, Any, Optional

def _resolve_paths(relative_path: str, source: str, destination: str):
    src_root = settings.PC_A_ROOT if source == "A" else settings.PC_B_ROOT
    dest_root = settings.PC_A_ROOT if destination == "A" else settings.PC_B_ROOT
    
    src_abs = os.path.abspath(os.path.join(src_root, relative_path))
    dest_abs = os.path.abspath(os.path.join(dest_root, relative_path))
    
    return src_abs, dest_abs

async def get_dry_run_preview(
    relative_path: str,
    source: str,
    destination: str,
    action_type: str
) -> Dict[str, Any]:
    src_abs, dest_abs = _resolve_paths(relative_path, source, destination)
    engine = get_transfer_engine()
    preview = await engine.dry_run(src_abs, dest_abs, action_type)
    
    # Replace absolute paths in the preview message/fields with relative ones for API privacy/cleanliness
    preview["file_path"] = relative_path
    preview["source"] = source
    preview["destination"] = destination
    return preview

async def execute_action(
    db: AsyncSession,
    relative_path: str,
    source: str,
    destination: str,
    action_type: str,  # "copy" or "move"
    triggered_by: str = "ui"
) -> ActionRecord:
    # 1. Create a pending action record
    action_rec = await log_action(
        db,
        action_type=action_type,
        file_path=relative_path,
        source=source,
        destination=destination,
        status="pending",
        triggered_by=triggered_by
    )
    
    src_abs, dest_abs = _resolve_paths(relative_path, source, destination)
    engine = get_transfer_engine()
    
    try:
        # Update state to in_progress
        action_rec.status = "in_progress"
        await db.commit()
        
        # 2. Check if backup is needed (if destination file exists)
        dest_exists = os.path.exists(dest_abs)
        backup_created = False
        backup_path = ""
        
        if dest_exists:
            # Create backup in trash
            os.makedirs(settings.TRASH_DIR, exist_ok=True)
            backup_filename = f"{action_rec.id}_{uuid.uuid4().hex}_{os.path.basename(relative_path)}"
            backup_path = os.path.join(settings.TRASH_DIR, backup_filename)
            # Copy dest to trash
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            await engine.copy(dest_abs, backup_path)
            backup_created = True
            
        # 3. Perform transfer
        if action_type == "copy":
            await engine.copy(src_abs, dest_abs)
        elif action_type == "move":
            await engine.move(src_abs, dest_abs)
        else:
            raise ValueError(f"Unknown action type: {action_type}")
            
        # 4. If backup was created, save UndoRecord
        if backup_created:
            expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=settings.UNDO_RETENTION_DAYS)
            undo_rec = UndoRecord(
                action_id=action_rec.id,
                backup_path=backup_path,
                expires_at=expires_at,
                restored=False
            )
            db.add(undo_rec)
        elif not dest_exists:
            # No backup, but we created a new file, so we still write an UndoRecord
            # with empty backup_path to signify "delete on undo"
            expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=settings.UNDO_RETENTION_DAYS)
            undo_rec = UndoRecord(
                action_id=action_rec.id,
                backup_path="",
                expires_at=expires_at,
                restored=False
            )
            db.add(undo_rec)
            
        action_rec.status = "completed"
        await db.commit()
        
    except Exception as e:
        action_rec.status = "failed"
        action_rec.error_message = str(e)
        await db.commit()
        raise e
        
    return action_rec

async def undo_action(db: AsyncSession, action_id: str) -> ActionRecord:
    # Fetch action
    action_rec = await db.get(ActionRecord, action_id)
    if not action_rec:
        raise ValueError("Action not found")
        
    if action_rec.status != "completed":
        raise ValueError(f"Cannot undo action in status: {action_rec.status}")
        
    # Fetch undo record
    stmt = select(UndoRecord).where(UndoRecord.action_id == action_id)
    undo_result = await db.execute(stmt)
    undo_rec = undo_result.scalar_one_or_none()
    
    if not undo_rec:
        raise ValueError("Undo record not found")
    if undo_rec.restored:
        raise ValueError("Action already undone")
        
    src_abs, dest_abs = _resolve_paths(action_rec.file_path, action_rec.source, action_rec.destination)
    engine = get_transfer_engine()
    
    try:
        # Mark undo in progress / create audit log
        undo_audit = await log_action(
            db,
            action_type="undo",
            file_path=action_rec.file_path,
            source=action_rec.destination,
            destination=action_rec.source,
            status="in_progress",
            triggered_by=action_rec.triggered_by
        )
        
        # Revert operation
        if action_rec.action_type == "copy":
            # If copy:
            if undo_rec.backup_path and os.path.exists(undo_rec.backup_path):
                # Restore overwritten destination file
                await engine.copy(undo_rec.backup_path, dest_abs)
            else:
                # Newly created, so delete it
                if os.path.exists(dest_abs):
                    os.remove(dest_abs)
        elif action_rec.action_type == "move":
            # If move:
            # First, move file back from dest_abs to src_abs
            if os.path.exists(dest_abs):
                await engine.move(dest_abs, src_abs)
            # Second, restore overwritten dest_abs if backup existed
            if undo_rec.backup_path and os.path.exists(undo_rec.backup_path):
                await engine.copy(undo_rec.backup_path, dest_abs)
                
        # Mark undo completed
        undo_rec.restored = True
        action_rec.status = "undone"
        undo_audit.status = "completed"
        await db.commit()
        
    except Exception as e:
        if 'undo_audit' in locals():
            undo_audit.status = "failed"
            undo_audit.error_message = str(e)
            await db.commit()
        raise e
        
    return action_rec

async def cleanup_trash(db: AsyncSession) -> int:
    now = datetime.datetime.utcnow()
    stmt = select(UndoRecord).where(UndoRecord.expires_at < now)
    result = await db.execute(stmt)
    records = result.scalars().all()
    
    count = 0
    for rec in records:
        if rec.backup_path and os.path.exists(rec.backup_path):
            try:
                os.remove(rec.backup_path)
                count += 1
            except Exception:
                pass
        await db.delete(rec)
        
    await db.commit()
    return count
