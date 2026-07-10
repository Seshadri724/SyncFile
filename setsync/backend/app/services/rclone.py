import asyncio
import json
import os
import datetime
from typing import List, Dict, Any

async def run_rclone_cmd(args: List[str]) -> str:
    """Helper to run rclone commands asynchronously and return stdout."""
    # Find rclone executable. In production or user system, it should be in PATH.
    # We can check an optional environment override or default to 'rclone'
    rclone_path = os.getenv("RCLONE_EXECUTABLE", "rclone")
    
    # We pass the path to custom rclone config if specified
    config_path = os.getenv("RCLONE_CONFIG_PATH")
    cmd_args = []
    if config_path:
        cmd_args.extend(["--config", config_path])
    cmd_args.extend(args)
    
    proc = await asyncio.create_subprocess_exec(
        rclone_path,
        *cmd_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        err_msg = stderr.decode().strip()
        raise Exception(f"Rclone failed with code {proc.returncode}: {err_msg}")
        
    return stdout.decode().strip()

async def list_remote_files(remote_path: str) -> List[Dict[str, Any]]:
    """Scan a remote path via rclone lsjson and return standardized file inventory metadata."""
    try:
        # Run rclone lsjson with hashes
        raw_json = await run_rclone_cmd(["lsjson", "--hash", "-R", remote_path])
        items = json.loads(raw_json)
    except Exception as e:
        print(f"lsjson --hash failed: {e}. Trying fallback without hashes.")
        # Fallback to standard lsjson if hashes are not supported by the remote dialect
        raw_json = await run_rclone_cmd(["lsjson", "-R", remote_path])
        items = json.loads(raw_json)
        
    files = []
    for item in items:
        if item.get("IsDir", False):
            continue
            
        path = item.get("Path", "")
        name = item.get("Name", "")
        size = item.get("Size", 0)
        
        # Parse ModTime (e.g. 2026-07-07T12:00:00Z)
        mod_time_str = item.get("ModTime", "")
        mtime = datetime.datetime.utcnow()
        if mod_time_str:
            try:
                # Handle Z / offset formats
                ts = mod_time_str.replace("Z", "+00:00")
                mtime = datetime.datetime.fromisoformat(ts)
            except Exception:
                pass
                
        # Resolve hash
        hashes = item.get("Hashes", {})
        # Check standard hashes: sha256, sha-256, md5, dropbox, quickxor, etc.
        file_hash = None
        for hash_name in ["sha256", "sha-256", "quickxor", "dropbox", "md5"]:
            if hash_name in hashes and hashes[hash_name]:
                file_hash = hashes[hash_name]
                break
                
        # If no hash available, create a deterministic hash from path + size + mtime
        if not file_hash:
            import hashlib
            raw_id = f"{path}:{size}:{mtime.timestamp()}"
            file_hash = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()
            
        files.append({
            "path": f"{remote_path.rstrip('/')}/{path}",
            "relative_path": path,
            "size_bytes": size,
            "mtime": mtime,
            "hash_sha256": file_hash
        })
        
    return files

async def execute_remote_transfer(src_path: str, dest_path: str) -> None:
    """Execute transfer to/from remote cloud remote using rclone copyto."""
    await run_rclone_cmd(["copyto", src_path, dest_path])
