import os
import shutil
import asyncio
import datetime
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.job import TransferJob
from app.config import settings
from app.services.storage_backend import get_storage_backend, STAGING_ROOT

# Expiry threshold in hours (default: 24 hours)
CLEANUP_EXPIRY_HOURS = int(os.getenv("SETSYNC_CLEANUP_EXPIRY_HOURS", "24"))

def utc_now_naive():
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)

async def clean_orphaned_sessions():
    """Scan staging backend sessions and SQL database to prune expired chunk sessions."""
    now = utc_now_naive()
    cutoff_time = now - datetime.timedelta(hours=CLEANUP_EXPIRY_HOURS)
    cutoff_timestamp = cutoff_time.timestamp()
    
    # 1. Clean from Database and track session IDs to clean off disk
    db_cleanup_sessions = []
    async with AsyncSessionLocal() as db_session:
        try:
            # Find jobs older than cutoff that are not finalized/completed
            stmt = select(TransferJob).where(
                (TransferJob.status.in_(["pending", "failed"])) & 
                (TransferJob.timestamp < cutoff_time)
            )
            result = await db_session.execute(stmt)
            jobs_to_clean = result.scalars().all()
            
            for job in jobs_to_clean:
                if job.transfer_session_id:
                    db_cleanup_sessions.append(job.transfer_session_id)
                
                # Delete the expired job row
                await db_session.delete(job)
                
            await db_session.commit()
        except Exception as e:
            await db_session.rollback()
            print(f"[Cleanup Daemon] Database error during session cleanup: {e}")

    # 2. Clean backend storage sessions
    backend = get_storage_backend()
    sessions = backend.list_sessions()
    
    for org_id, session_id, mtime in sessions:
        should_delete = False
        
        # Check if it was deleted/expired in database
        if session_id in db_cleanup_sessions:
            should_delete = True
        else:
            if mtime < cutoff_timestamp:
                should_delete = True
                
        if should_delete:
            try:
                backend.delete_session(org_id, session_id)
                print(f"[Cleanup Daemon] Successfully pruned expired session: {session_id}")
            except Exception as e:
                print(f"[Cleanup Daemon] Failed to delete session {session_id}: {e}")
                
    # 3. Clean local empty organization subfolders if using local storage backend
    if settings.STORAGE_BACKEND == "local" and STAGING_ROOT.exists():
        for path in STAGING_ROOT.iterdir():
            if path.is_dir() and path.name != "global":
                try:
                    if not any(path.iterdir()):
                        os.rmdir(path)
                        print(f"[Cleanup Daemon] Removed empty organization staging folder: {path.name}")
                except Exception:
                    pass

async def cleanup_loop():
    """Background task loop that triggers cleanup of orphaned sessions periodically."""
    print("[Cleanup Daemon] Starting periodic session garbage collection daemon...")
    while True:
        try:
            await clean_orphaned_sessions()
        except Exception as e:
            print(f"[Cleanup Daemon] Unexpected error in loop: {e}")
        # Sleep for 1 hour
        await asyncio.sleep(3600)
