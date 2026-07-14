import os
import shutil
import pytest
import datetime
import json
from pathlib import Path
from app.database import AsyncSessionLocal
from app.models.job import TransferJob
from app.services.chunked_transfer import STAGING_ROOT
from app.services.cleanup import clean_orphaned_sessions, utc_now_naive

@pytest.mark.anyio
async def test_session_cleanup():
    # Setup directories
    os.makedirs(STAGING_ROOT, exist_ok=True)
    
    org_expired_id = "test-org-expired"
    org_fresh_id = "test-org-fresh"
    
    # 1. Create an expired session (30 hours old) inside expired org folder
    expired_session_id = "test-expired-session-123"
    expired_dir = STAGING_ROOT / org_expired_id / expired_session_id
    os.makedirs(expired_dir, exist_ok=True)
    
    expired_metadata = {
        "session_id": expired_session_id,
        "total_chunks": 3,
        "chunk_size": 1024,
        "file_sha256": "fake-sha-expired",
        "file_path": "expired.txt",
        "completed": False
    }
    
    expired_meta_path = expired_dir / "metadata.json"
    with open(expired_meta_path, "w") as f:
        json.dump(expired_metadata, f)
        
    # Set modification time to 30 hours ago
    past_timestamp = (datetime.datetime.now() - datetime.timedelta(hours=30)).timestamp()
    os.utime(expired_meta_path, (past_timestamp, past_timestamp))
    os.utime(expired_dir, (past_timestamp, past_timestamp))
    
    # Open DB session and register
    async with AsyncSessionLocal() as db_session:
        # Register in DB with timestamp in the past
        past_datetime = utc_now_naive() - datetime.timedelta(hours=30)
        expired_job = TransferJob(
            id=expired_session_id,
            file_path="expired.txt",
            source_id="dummy-src",
            destination_id="dummy-dst",
            action_type="copy",
            status="pending",
            transfer_session_id=expired_session_id,
            timestamp=past_datetime
        )
        db_session.add(expired_job)
        await db_session.commit()
    
    # 2. Create a fresh session (1 hour old) inside fresh org folder
    fresh_session_id = "test-fresh-session-456"
    fresh_dir = STAGING_ROOT / org_fresh_id / fresh_session_id
    os.makedirs(fresh_dir, exist_ok=True)
    
    fresh_metadata = {
        "session_id": fresh_session_id,
        "total_chunks": 3,
        "chunk_size": 1024,
        "file_sha256": "fake-sha-fresh",
        "file_path": "fresh.txt",
        "completed": False
    }
    
    fresh_meta_path = fresh_dir / "metadata.json"
    with open(fresh_meta_path, "w") as f:
        json.dump(fresh_metadata, f)
        
    async with AsyncSessionLocal() as db_session:
        # Register in DB with fresh timestamp
        fresh_job = TransferJob(
            id=fresh_session_id,
            file_path="fresh.txt",
            source_id="dummy-src",
            destination_id="dummy-dst",
            action_type="copy",
            status="pending",
            transfer_session_id=fresh_session_id,
            timestamp=utc_now_naive()
        )
        db_session.add(fresh_job)
        await db_session.commit()
    
    # Run the cleanup logic
    await clean_orphaned_sessions()
    
    # Assertions
    # The expired session should be deleted from disk
    assert not expired_dir.exists(), "Expired session directory was not pruned from disk"
    
    # The empty expired organization parent directory should be removed
    assert not (STAGING_ROOT / org_expired_id).exists(), "Empty organization staging directory was not cleaned up"
    
    # The fresh session should still exist on disk
    assert fresh_dir.exists(), "Fresh session directory was incorrectly pruned from disk"
    assert (STAGING_ROOT / org_fresh_id).exists()
    
    # Clean up test directories
    if (STAGING_ROOT / org_fresh_id).exists():
        shutil.rmtree(STAGING_ROOT / org_fresh_id, ignore_errors=True)
