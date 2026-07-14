import os
import json
import shutil
import hashlib
from typing import Optional, List, Tuple, Dict, Any, Protocol
from pathlib import Path

# Local storage staging root path (retained for backward compatibility and default local mode)
STAGING_ROOT = Path("./.setsync_staging").absolute()

class StorageBackend(Protocol):
    def write_metadata(self, org_id: Optional[str], session_id: str, metadata: dict) -> None:
        ...

    def read_metadata(self, org_id: Optional[str], session_id: str) -> Optional[dict]:
        ...

    def write_chunk(self, org_id: Optional[str], session_id: str, index: int, data: bytes) -> None:
        ...

    def read_chunk(self, org_id: Optional[str], session_id: str, index: int) -> Optional[bytes]:
        ...

    def chunk_exists(self, org_id: Optional[str], session_id: str, index: int) -> bool:
        ...

    def delete_session(self, org_id: Optional[str], session_id: str) -> None:
        ...

    def delete_chunk(self, org_id: Optional[str], session_id: str, index: int) -> None:
        ...

    def get_org_usage_bytes(self, org_id: Optional[str]) -> int:
        ...

    def list_sessions(self) -> List[Tuple[Optional[str], str, float]]:
        """Returns list of (org_id, session_id, mtime) for active/completed sessions."""
        ...

    def assemble_chunks(self, org_id: Optional[str], session_id: str, total: int, expected_sha: str, target_path: str) -> bool:
        """Assembles uploaded chunks, verifies SHA256 integrity, saves the final assembled file, and deletes the chunks."""
        ...


class LocalStorageBackend:
    def _get_session_dir(self, org_id: Optional[str], session_id: str) -> Path:
        if org_id:
            return STAGING_ROOT / org_id / session_id
        return STAGING_ROOT / "global" / session_id

    def _get_metadata_path(self, org_id: Optional[str], session_id: str) -> Path:
        return self._get_session_dir(org_id, session_id) / "metadata.json"

    def write_metadata(self, org_id: Optional[str], session_id: str, metadata: dict) -> None:
        session_dir = self._get_session_dir(org_id, session_id)
        os.makedirs(session_dir, exist_ok=True)
        metadata_path = self._get_metadata_path(org_id, session_id)
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)

    def read_metadata(self, org_id: Optional[str], session_id: str) -> Optional[dict]:
        metadata_path = self._get_metadata_path(org_id, session_id)
        if not metadata_path.exists():
            return None
        try:
            with open(metadata_path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def write_chunk(self, org_id: Optional[str], session_id: str, index: int, data: bytes) -> None:
        session_dir = self._get_session_dir(org_id, session_id)
        os.makedirs(session_dir, exist_ok=True)
        chunk_file = session_dir / f"chunk_{index}"
        with open(chunk_file, "wb") as f:
            f.write(data)

    def read_chunk(self, org_id: Optional[str], session_id: str, index: int) -> Optional[bytes]:
        session_dir = self._get_session_dir(org_id, session_id)
        chunk_file = session_dir / f"chunk_{index}"
        
        # 1. Try reading the individual chunk file first
        if chunk_file.exists():
            with open(chunk_file, "rb") as f:
                return f.read()

        # 2. If chunk file does not exist, check if transfer is finalized and slice it
        metadata = self.read_metadata(org_id, session_id)
        if metadata and metadata.get("completed"):
            final_file = session_dir / "finalized_delta.json"
            if final_file.exists():
                chunk_size = metadata.get("chunk_size", 0)
                if chunk_size > 0:
                    start_offset = index * chunk_size
                    with open(final_file, "rb") as f:
                        f.seek(start_offset)
                        return f.read(chunk_size)
        return None

    def chunk_exists(self, org_id: Optional[str], session_id: str, index: int) -> bool:
        session_dir = self._get_session_dir(org_id, session_id)
        chunk_file = session_dir / f"chunk_{index}"
        if chunk_file.exists() and chunk_file.stat().st_size > 0:
            return True

        # Check if finalized
        metadata = self.read_metadata(org_id, session_id)
        if metadata and metadata.get("completed"):
            final_file = session_dir / "finalized_delta.json"
            if final_file.exists():
                total = metadata.get("total_chunks", 0)
                return 0 <= index < total
        return False

    def delete_session(self, org_id: Optional[str], session_id: str) -> None:
        session_dir = self._get_session_dir(org_id, session_id)
        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)

    def delete_chunk(self, org_id: Optional[str], session_id: str, index: int) -> None:
        session_dir = self._get_session_dir(org_id, session_id)
        chunk_file = session_dir / f"chunk_{index}"
        if chunk_file.exists():
            try:
                os.remove(chunk_file)
            except Exception:
                pass

    def get_org_usage_bytes(self, org_id: Optional[str]) -> int:
        org_dir = STAGING_ROOT / (org_id if org_id else "global")
        if not org_dir.exists():
            return 0
        total_size = 0
        for entry in org_dir.rglob("*"):
            if entry.is_file():
                try:
                    total_size += entry.stat().st_size
                except Exception:
                    pass
        return total_size

    def list_sessions(self) -> List[Tuple[Optional[str], str, float]]:
        sessions = []
        if not STAGING_ROOT.exists():
            return sessions
        for metadata_path in STAGING_ROOT.glob("**/metadata.json"):
            try:
                session_dir = metadata_path.parent
                session_id = session_dir.name
                org_dir = session_dir.parent
                org_id = org_dir.name if org_dir != STAGING_ROOT else None
                if org_id == "global":
                    org_id = None
                mtime = metadata_path.stat().st_mtime
                sessions.append((org_id, session_id, mtime))
            except Exception:
                pass
        return sessions

    def assemble_chunks(self, org_id: Optional[str], session_id: str, total: int, expected_sha: str, target_path: str) -> bool:
        session_dir = self._get_session_dir(org_id, session_id)
        
        # Verify chunks exist
        for i in range(total):
            chunk_file = session_dir / f"chunk_{i}"
            if not chunk_file.exists():
                return False

        # Assemble the chunks
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        temp_output_path = target_path + ".tmp"
        sha256_hash = hashlib.sha256()

        try:
            with open(temp_output_path, "wb") as outfile:
                for i in range(total):
                    chunk_file = session_dir / f"chunk_{i}"
                    with open(chunk_file, "rb") as infile:
                        chunk_bytes = infile.read()
                        sha256_hash.update(chunk_bytes)
                        outfile.write(chunk_bytes)

            assembled_sha = sha256_hash.hexdigest()
            if assembled_sha != expected_sha:
                if os.path.exists(temp_output_path):
                    os.remove(temp_output_path)
                return False

            if os.path.exists(target_path):
                os.remove(target_path)
            shutil.move(temp_output_path, target_path)

            # Cleanup chunks to optimize space
            for i in range(total):
                chunk_file = session_dir / f"chunk_{i}"
                if chunk_file.exists():
                    os.remove(chunk_file)
            return True
        except Exception:
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)
            return False


class R2StorageBackend:
    def __init__(self):
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise ImportError(
                "The 'boto3' package is required to use R2StorageBackend. "
                "Please run `pip install boto3` to use the Cloudflare R2 backend."
            )
        from app.config import settings

        endpoint_url = settings.R2_ENDPOINT_URL
        if not endpoint_url and settings.R2_ACCOUNT_ID:
            endpoint_url = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

        self.bucket = settings.R2_BUCKET_NAME
        self.s3 = boto3.client(
            service_name="s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
            config=Config(signature_version="s3v4")
        )

    def _get_prefix(self, org_id: Optional[str], session_id: str) -> str:
        org_prefix = org_id if org_id else "global"
        return f"{org_prefix}/{session_id}"

    def write_metadata(self, org_id: Optional[str], session_id: str, metadata: dict) -> None:
        prefix = self._get_prefix(org_id, session_id)
        self.s3.put_object(
            Bucket=self.bucket,
            Key=f"{prefix}/metadata.json",
            Body=json.dumps(metadata),
            ContentType="application/json"
        )

    def read_metadata(self, org_id: Optional[str], session_id: str) -> Optional[dict]:
        prefix = self._get_prefix(org_id, session_id)
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=f"{prefix}/metadata.json")
            return json.loads(response["Body"].read().decode("utf-8"))
        except self.s3.exceptions.NoSuchKey:
            return None
        except Exception:
            return None

    def write_chunk(self, org_id: Optional[str], session_id: str, index: int, data: bytes) -> None:
        prefix = self._get_prefix(org_id, session_id)
        self.s3.put_object(
            Bucket=self.bucket,
            Key=f"{prefix}/chunk_{index}",
            Body=data,
            ContentType="application/octet-stream"
        )

    def read_chunk(self, org_id: Optional[str], session_id: str, index: int) -> Optional[bytes]:
        prefix = self._get_prefix(org_id, session_id)
        
        # 1. Try reading the individual chunk first
        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=f"{prefix}/chunk_{index}")
            return response["Body"].read()
        except self.s3.exceptions.NoSuchKey:
            pass

        # 2. Check if finalized and slice range
        metadata = self.read_metadata(org_id, session_id)
        if metadata and metadata.get("completed"):
            chunk_size = metadata.get("chunk_size", 0)
            if chunk_size > 0:
                start_offset = index * chunk_size
                end_offset = start_offset + chunk_size - 1
                try:
                    response = self.s3.get_object(
                        Bucket=self.bucket,
                        Key=f"{prefix}/finalized_delta.json",
                        Range=f"bytes={start_offset}-{end_offset}"
                    )
                    return response["Body"].read()
                except Exception:
                    pass
        return None

    def chunk_exists(self, org_id: Optional[str], session_id: str, index: int) -> bool:
        prefix = self._get_prefix(org_id, session_id)
        try:
            self.s3.head_object(Bucket=self.bucket, Key=f"{prefix}/chunk_{index}")
            return True
        except Exception:
            pass

        metadata = self.read_metadata(org_id, session_id)
        if metadata and metadata.get("completed"):
            try:
                self.s3.head_object(Bucket=self.bucket, Key=f"{prefix}/finalized_delta.json")
                total = metadata.get("total_chunks", 0)
                return 0 <= index < total
            except Exception:
                pass
        return False

    def delete_session(self, org_id: Optional[str], session_id: str) -> None:
        prefix = self._get_prefix(org_id, session_id)
        try:
            # Paginated list of keys to delete
            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                if "Contents" in page:
                    objects = [{"Key": obj["Key"]} for obj in page["Contents"]]
                    self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": objects})
        except Exception:
            pass

    def delete_chunk(self, org_id: Optional[str], session_id: str, index: int) -> None:
        prefix = self._get_prefix(org_id, session_id)
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=f"{prefix}/chunk_{index}")
        except Exception:
            pass

    def get_org_usage_bytes(self, org_id: Optional[str]) -> int:
        org_prefix = org_id if org_id else "global"
        total_size = 0
        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=f"{org_prefix}/"):
                if "Contents" in page:
                    for obj in page["Contents"]:
                        total_size += obj.get("Size", 0)
        except Exception:
            pass
        return total_size

    def list_sessions(self) -> List[Tuple[Optional[str], str, float]]:
        sessions = []
        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket):
                if "Contents" in page:
                    for obj in page["Contents"]:
                        key = obj["Key"]
                        if key.endswith("/metadata.json"):
                            parts = key.split("/")
                            if len(parts) >= 3:
                                org_id = parts[0]
                                if org_id == "global":
                                    org_id = None
                                session_id = parts[1]
                                mtime = obj["LastModified"].timestamp()
                                sessions.append((org_id, session_id, mtime))
        except Exception:
            pass
        return sessions

    def assemble_chunks(self, org_id: Optional[str], session_id: str, total: int, expected_sha: str, target_path: str) -> bool:
        # Download chunks to local temp files, assemble them, verify sha, and upload the finalized file to R2
        prefix = self._get_prefix(org_id, session_id)
        
        # Local workspace temp staging for the duration of finalization assembly
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        temp_output_path = target_path + ".tmp"
        sha256_hash = hashlib.sha256()

        try:
            with open(temp_output_path, "wb") as outfile:
                for i in range(total):
                    # Fetch chunk from R2
                    response = self.s3.get_object(Bucket=self.bucket, Key=f"{prefix}/chunk_{i}")
                    chunk_bytes = response["Body"].read()
                    sha256_hash.update(chunk_bytes)
                    outfile.write(chunk_bytes)

            assembled_sha = sha256_hash.hexdigest()
            if assembled_sha != expected_sha:
                if os.path.exists(temp_output_path):
                    os.remove(temp_output_path)
                return False

            # Copy/move to the server's expected local target path (for delta job lookup or storage)
            if os.path.exists(target_path):
                os.remove(target_path)
            shutil.copy(temp_output_path, target_path)

            # Upload finalized_delta.json back to R2 to enable horizontal scaling retrieval
            with open(temp_output_path, "rb") as final_f:
                self.s3.put_object(
                    Bucket=self.bucket,
                    Key=f"{prefix}/finalized_delta.json",
                    Body=final_f.read(),
                    ContentType="application/json"
                )

            # Clean up temp file
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)

            # Delete separate chunk objects in R2 to free quota space
            objects_to_delete = [{"Key": f"{prefix}/chunk_{i}"} for i in range(total)]
            self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": objects_to_delete})
            return True

        except Exception:
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)
            return False


# Singleton active backend getter
_active_backend: Optional[StorageBackend] = None

def get_storage_backend() -> StorageBackend:
    global _active_backend
    if _active_backend is None:
        from app.config import settings
        if settings.STORAGE_BACKEND == "r2":
            _active_backend = R2StorageBackend()
        else:
            _active_backend = LocalStorageBackend()
    return _active_backend
