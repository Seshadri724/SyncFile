import os
import shutil
import pytest
import hashlib
from pathlib import Path
from app.services.storage_backend import LocalStorageBackend, STAGING_ROOT

def test_local_storage_backend_lifecycle():
    backend = LocalStorageBackend()
    
    org_id = "test-backend-org"
    session_id = "test-backend-session"
    
    # Clean any leftover test directory
    backend.delete_session(org_id, session_id)
    
    # 1. Test metadata read/write
    meta = {"session_id": session_id, "total_chunks": 2, "chunk_size": 5, "completed": False}
    backend.write_metadata(org_id, session_id, meta)
    
    read_meta = backend.read_metadata(org_id, session_id)
    assert read_meta is not None
    assert read_meta["total_chunks"] == 2
    assert read_meta["chunk_size"] == 5
    assert read_meta["completed"] is False
    
    # 2. Test chunk read/write/exists
    chunk0 = b"abcde"  # 5 bytes
    chunk1 = b"fgh"    # 3 bytes
    
    backend.write_chunk(org_id, session_id, 0, chunk0)
    backend.write_chunk(org_id, session_id, 1, chunk1)
    
    assert backend.chunk_exists(org_id, session_id, 0) is True
    assert backend.chunk_exists(org_id, session_id, 1) is True
    assert backend.chunk_exists(org_id, session_id, 2) is False
    
    # 3. Test get_org_usage_bytes
    usage = backend.get_org_usage_bytes(org_id)
    # metadata.json (~80-100 bytes) + chunk0 (5 bytes) + chunk1 (3 bytes)
    assert usage > 8
    
    # 4. Test list_sessions
    sessions = backend.list_sessions()
    session_ids = [s[1] for s in sessions]
    assert session_id in session_ids
    
    # 5. Test assemble_chunks with hash check
    expected_full = chunk0 + chunk1  # b"abcdefgh"
    expected_sha = hashlib.sha256(expected_full).hexdigest()
    
    target_path = str(STAGING_ROOT / org_id / session_id / "finalized_delta.json")
    success = backend.assemble_chunks(org_id, session_id, 2, expected_sha, target_path)
    assert success is True
    assert os.path.exists(target_path)
    
    # Update metadata completed status (which the service normally wrapper does)
    meta["completed"] = True
    backend.write_metadata(org_id, session_id, meta)
    
    # After finalization, verify individual chunks are deleted to save space
    session_dir = STAGING_ROOT / org_id / session_id
    assert not (session_dir / "chunk_0").exists()
    assert not (session_dir / "chunk_1").exists()
    
    # 6. Test dynamic chunk slicing from finalized file (crucial for client download compatibility!)
    c0_sliced = backend.read_chunk(org_id, session_id, 0)
    c1_sliced = backend.read_chunk(org_id, session_id, 1)
    
    assert c0_sliced == chunk0
    assert c1_sliced == chunk1
    
    # 7. Test delete_session
    backend.delete_session(org_id, session_id)
    assert not session_dir.exists()
