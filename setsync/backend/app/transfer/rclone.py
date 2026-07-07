import asyncio
import os
import json
import datetime
from typing import Dict, Any
from app.transfer.base import TransferEngine
from app.config import settings

class RcloneTransferEngine(TransferEngine):
    async def copy(self, src: str, dest: str) -> None:
        cmd = [settings.RCLONE_PATH, "copyto", src, dest]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise Exception(f"rclone copy failed: {stderr.decode().strip()}")

    async def move(self, src: str, dest: str) -> None:
        cmd = [settings.RCLONE_PATH, "moveto", src, dest]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise Exception(f"rclone move failed: {stderr.decode().strip()}")

    async def _get_metadata(self, path: str) -> Dict[str, Any]:
        """Fetch metadata for a path using rclone lsjson."""
        cmd = [settings.RCLONE_PATH, "lsjson", path]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return {}
        try:
            items = json.loads(stdout.decode())
            if items:
                return items[0]
        except Exception:
            pass
        return {}

    async def dry_run(self, src: str, dest: str, action_type: str) -> Dict[str, Any]:
        # Get source metadata
        src_meta = await self._get_metadata(src)
        if not src_meta:
            # Fallback if local path
            if os.path.exists(src):
                stat = os.stat(src)
                src_meta = {
                    "Size": stat.st_size,
                    "ModTime": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat() + "Z"
                }
            else:
                raise FileNotFoundError(f"Source file not found or inaccessible: {src}")

        src_size = src_meta.get("Size", 0)
        src_mtime_str = src_meta.get("ModTime", "")[:19] # trim to seconds
        
        # Get destination metadata
        dest_meta = await self._get_metadata(dest)
        if not dest_meta and os.path.exists(dest):
            stat = os.stat(dest)
            dest_meta = {
                "Size": stat.st_size,
                "ModTime": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat() + "Z"
            }

        dest_exists = bool(dest_meta)
        dest_size = dest_meta.get("Size") if dest_exists else None
        dest_mtime_str = dest_meta.get("ModTime", "")[:19] if dest_exists else None
        will_overwrite = dest_exists

        if dest_exists:
            message = (
                f"Destination file exists. Overwriting ({src_size} bytes vs {dest_size} bytes)."
            )
        else:
            message = f"File will be transferred to destination ({src_size} bytes)."

        return {
            "action_type": action_type,
            "file_path": src,
            "source": "rclone_src",
            "destination": "rclone_dest",
            "will_overwrite": will_overwrite,
            "source_size": src_size,
            "dest_size": dest_size,
            "source_mtime": src_mtime_str,
            "dest_mtime": dest_mtime_str,
            "message": message,
        }
