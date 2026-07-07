import os
import hashlib
import datetime
from pathlib import Path
from typing import List, Dict, Any
from agent.db import get_cached_file, update_cached_file, update_scanned_time, delete_stale_cache

def calculate_sha256(filepath: Path) -> str:
    """Computes SHA-256 of a file using chunked reads."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def scan_directory(root_dir: str) -> List[Dict[str, Any]]:
    root_path = Path(root_dir).resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Root scan directory does not exist: {root_dir}")

    scan_start = datetime.datetime.utcnow()
    files_list = []
    
    # We will traverse recursively
    for root, dirs, files in os.walk(root_path):
        if len(files_list) >= 10000:
            break
            
        # Skip hidden files/directories by default
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        
        for file in files:
            if len(files_list) >= 10000:
                print("Warning: Max file scan limit of 10000 reached. Stopping scan.")
                break
                
            if file.startswith("."):
                continue
                
            abs_path = Path(root) / file
            abs_path_str = str(abs_path.resolve())
            
            try:
                stat = abs_path.stat()
                size = stat.st_size
                mtime = stat.st_mtime
                
                # Check 10GB file size limit (10 * 1024 * 1024 * 1024 bytes)
                if size > 10737418240:
                    print(f"Warning: Skipping {abs_path_str} (exceeds 10GB size limit)")
                    continue
                
                # Try cache lookup
                cached = get_cached_file(abs_path_str)
                file_hash = None
                
                if cached:
                    cached_size, cached_mtime, cached_hash = cached
                    # Compare size and mtime (allow very small float inaccuracy)
                    if cached_size == size and abs(cached_mtime - mtime) < 0.001:
                        file_hash = cached_hash
                        # Just update the scanned time stamp so it doesn't get swept
                        update_scanned_time(abs_path_str, scan_start)
                        
                if not file_hash:
                    # Calculate new hash
                    file_hash = calculate_sha256(abs_path)
                    update_cached_file(abs_path_str, size, mtime, file_hash, scan_start)
                
                # Relativize path
                relative_path = os.path.relpath(abs_path_str, root_path)
                # Normalize relative path separators to forward slashes for cross-platform matching
                relative_path_normalized = relative_path.replace(os.path.sep, "/")
                
                files_list.append({
                    "path": abs_path_str,
                    "relative_path": relative_path_normalized,
                    "size_bytes": size,
                    "mtime": datetime.datetime.fromtimestamp(mtime).isoformat(),
                    "hash_sha256": file_hash
                })
                
            except (PermissionError, FileNotFoundError):
                # Log or handle unreadable files gracefully
                print(f"Warning: Skipping file due to permission/access error: {abs_path_str}")
                continue
            except Exception as e:
                print(f"Error scanning file {abs_path_str}: {e}")
                continue

    # Cleanup stale entries in database cache
    delete_stale_cache(scan_start)
    return files_list
