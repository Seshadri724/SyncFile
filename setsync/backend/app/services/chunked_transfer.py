import os
import json
import hashlib
from typing import Optional, Dict, Any
from pathlib import Path
from app.services.storage_backend import get_storage_backend, STAGING_ROOT

def ensure_staging_dir():
    os.makedirs(STAGING_ROOT, exist_ok=True)

def get_session_dir(session_id: str, org_id: Optional[str] = None) -> Path:
    if org_id:
        return STAGING_ROOT / org_id / session_id
    return STAGING_ROOT / "global" / session_id

def init_chunked_upload(
    session_id: str,
    total_chunks: int,
    chunk_size: int,
    file_sha256: str,
    file_path: str,
    org_id: Optional[str] = None
) -> Dict[str, Any]:
    backend = get_storage_backend()
    metadata = {
        "session_id": session_id,
        "total_chunks": total_chunks,
        "chunk_size": chunk_size,
        "file_sha256": file_sha256,
        "file_path": file_path,
        "completed": False
    }
    backend.write_metadata(org_id, session_id, metadata)
    return metadata

def get_session_info(session_id: str, org_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    backend = get_storage_backend()
    metadata = backend.read_metadata(org_id, session_id)
    if not metadata:
        return None
        
    # Scan to see which chunks exist
    received_chunks = []
    total = metadata.get("total_chunks", 0)
    for i in range(total):
        if backend.chunk_exists(org_id, session_id, i):
            received_chunks.append(i)
            
    metadata["received_chunks"] = received_chunks
    return metadata

def receive_chunk(
    session_id: str,
    chunk_index: int,
    chunk_data: bytes,
    chunk_sha256: str,
    org_id: Optional[str] = None
) -> bool:
    backend = get_storage_backend()
    metadata = backend.read_metadata(org_id, session_id)
    if not metadata:
        return False
        
    actual_sha = hashlib.sha256(chunk_data).hexdigest()
    if actual_sha != chunk_sha256:
        return False
        
    backend.write_chunk(org_id, session_id, chunk_index, chunk_data)
    return True

def finalize_upload(session_id: str, target_output_path: str, org_id: Optional[str] = None) -> bool:
    backend = get_storage_backend()
    metadata = backend.read_metadata(org_id, session_id)
    if not metadata:
        return False
        
    total_chunks = metadata.get("total_chunks", 0)
    expected_sha = metadata.get("file_sha256")
    
    success = backend.assemble_chunks(org_id, session_id, total_chunks, expected_sha, target_output_path)
    if success:
        metadata["completed"] = True
        backend.write_metadata(org_id, session_id, metadata)
        return True
    return False
