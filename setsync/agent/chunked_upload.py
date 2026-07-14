import os
import time
import requests
import hashlib
from typing import Dict, Any, List
from agent.config import get_agent_config
from agent.uploader import get_auth_headers

DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024  # 4MB

from pathlib import Path
from agent.scanner import calculate_sha256

def get_file_sha256(filepath: str) -> str:
    return calculate_sha256(Path(filepath))

def chunked_upload_file(
    filepath: str,
    session_id: str,
    target_rel_path: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE
) -> bool:
    core_url = get_agent_config("core_url", "http://localhost:8000")
    file_size = os.path.getsize(filepath)
    
    total_chunks = (file_size + chunk_size - 1) // chunk_size
    if total_chunks == 0:
        total_chunks = 1  # Even empty file has at least 1 chunk
        
    file_sha256 = get_file_sha256(filepath)
    
    # 1. Initialize upload session
    init_url = f"{core_url.rstrip('/')}/transfer/init"
    payload = {
        "session_id": session_id,
        "total_chunks": total_chunks,
        "chunk_size": chunk_size,
        "file_sha256": file_sha256,
        "file_path": target_rel_path
    }
    
    headers = get_auth_headers()
    response = requests.post(init_url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    
    # Check if some chunks are already uploaded (resume support)
    status_url = f"{core_url.rstrip('/')}/transfer/{session_id}"
    res = requests.get(status_url, headers=headers, timeout=15)
    already_received = []
    if res.status_code == 200:
        already_received = res.json().get("received_chunks", [])
        
    # 2. Upload each chunk
    with open(filepath, "rb") as f:
        for index in range(total_chunks):
            # Skip if already uploaded
            if index in already_received:
                f.seek((index + 1) * chunk_size)
                continue
                
            f.seek(index * chunk_size)
            chunk_data = f.read(chunk_size)
            chunk_sha256 = hashlib.sha256(chunk_data).hexdigest()
            
            chunk_url = f"{core_url.rstrip('/')}/transfer/{session_id}/chunk/{index}"
            chunk_headers = get_auth_headers()
            chunk_headers["X-Chunk-SHA256"] = chunk_sha256
            chunk_headers["Content-Type"] = "application/octet-stream"
            
            # Retry mechanism
            success = False
            for attempt in range(3):
                try:
                    res = requests.post(
                        chunk_url,
                        data=chunk_data,
                        headers=chunk_headers,
                        timeout=60
                    )
                    if res.status_code == 200:
                        success = True
                        break
                except Exception as e:
                    print(f"    [Retry {attempt+1}/3] Error uploading chunk {index}: {e}")
                    
                time.sleep(2 ** attempt)
                
            if not success:
                print(f"Failed to upload chunk {index} after 3 attempts.")
                return False
                
    # 3. Finalize upload
    finalize_url = f"{core_url.rstrip('/')}/transfer/{session_id}/finalize"
    res = requests.post(finalize_url, headers=headers, timeout=30)
    res.raise_for_status()
    return True

def chunked_download_file(
    session_id: str,
    output_filepath: str
) -> bool:
    core_url = get_agent_config("core_url", "http://localhost:8000")
    headers = get_auth_headers()
    
    # 1. Get session status
    status_url = f"{core_url.rstrip('/')}/transfer/{session_id}"
    res = requests.get(status_url, headers=headers, timeout=15)
    res.raise_for_status()
    info = res.json()
    
    total_chunks = info.get("total_chunks", 0)
    expected_sha = info.get("file_sha256")
    
    # Create temp directory for downloading chunks
    temp_dir = os.path.dirname(output_filepath)
    os.makedirs(temp_dir, exist_ok=True)
    temp_out_path = output_filepath + ".download"
    
    try:
        with open(temp_out_path, "wb") as out_f:
            for index in range(total_chunks):
                chunk_url = f"{core_url.rstrip('/')}/transfer/{session_id}/chunk/{index}"
                
                success = False
                chunk_data = b""
                for attempt in range(3):
                    try:
                        res = requests.get(chunk_url, headers=headers, timeout=60)
                        if res.status_code == 200:
                            chunk_data = res.content
                            # Verify SHA256 of downloaded chunk
                            received_sha = res.headers.get("X-Chunk-SHA256")
                            actual_sha = hashlib.sha256(chunk_data).hexdigest()
                            if received_sha == actual_sha:
                                success = True
                                break
                            else:
                                print(f"    [Retry {attempt+1}/3] Chunk {index} hash mismatch")
                    except Exception as e:
                        print(f"    [Retry {attempt+1}/3] Error downloading chunk {index}: {e}")
                        
                    time.sleep(2 ** attempt)
                    
                if not success:
                    print(f"Failed to download chunk {index} after 3 attempts.")
                    if os.path.exists(temp_out_path):
                        os.remove(temp_out_path)
                    return False
                    
                out_f.write(chunk_data)
                
        # Verify complete file hash
        file_sha256 = get_file_sha256(temp_out_path)
        if file_sha256 != expected_sha:
            print("Final downloaded file hash verification failed.")
            if os.path.exists(temp_out_path):
                os.remove(temp_out_path)
            return False
            
        # Move to final destination
        if os.path.exists(output_filepath):
            os.remove(output_filepath)
        os.rename(temp_out_path, output_filepath)
        return True
    except Exception as e:
        print(f"Error during chunked download: {e}")
        if os.path.exists(temp_out_path):
            os.remove(temp_out_path)
        return False
