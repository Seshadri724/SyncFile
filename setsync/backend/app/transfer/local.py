import os
import shutil
import datetime
import aiofiles.os
from typing import Dict, Any
from app.transfer.base import TransferEngine

class LocalTransferEngine(TransferEngine):
    async def copy(self, src: str, dest: str) -> None:
        # Create parent directories if they don't exist
        dest_dir = os.path.dirname(dest)
        os.makedirs(dest_dir, exist_ok=True)
        
        if os.path.exists(dest):
            # Destination exists: perform custom block-level delta sync
            from app.transfer.delta_sync import (
                generate_block_signatures,
                compute_delta,
                apply_delta
            )
            sigs = generate_block_signatures(dest)
            delta = compute_delta(sigs, src)
            
            temp_dest = dest + ".tmp_delta"
            apply_delta(delta, dest, temp_dest)
            shutil.copystat(src, dest)
        else:
            # New file: full copy
            shutil.copy2(src, dest)

    async def move(self, src: str, dest: str) -> None:
        dest_dir = os.path.dirname(dest)
        os.makedirs(dest_dir, exist_ok=True)
        shutil.move(src, dest)

    async def dry_run(self, src: str, dest: str, action_type: str) -> Dict[str, Any]:
        if not os.path.exists(src):
            raise FileNotFoundError(f"Source file not found: {src}")

        src_stat = await aiofiles.os.stat(src)
        src_size = src_stat.st_size
        src_mtime = datetime.datetime.fromtimestamp(src_stat.st_mtime)

        dest_exists = os.path.exists(dest)
        dest_size = None
        dest_mtime = None
        will_overwrite = False

        if dest_exists:
            dest_stat = await aiofiles.os.stat(dest)
            dest_size = dest_stat.st_size
            dest_mtime = datetime.datetime.fromtimestamp(dest_stat.st_mtime)
            will_overwrite = True
            
            # Formulate message
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
            "file_path": src,
            "source": "resolved",
            "destination": "resolved",
            "will_overwrite": will_overwrite,
            "source_size": src_size,
            "dest_size": dest_size,
            "source_mtime": src_mtime.isoformat(),
            "dest_mtime": dest_mtime.isoformat() if dest_mtime else None,
            "message": message,
        }
