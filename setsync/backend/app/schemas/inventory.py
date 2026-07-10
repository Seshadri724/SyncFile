from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class FileScanItem(BaseModel):
    path: str
    relative_path: str
    size_bytes: int
    mtime: datetime
    hash_sha256: str
    image_hash: Optional[str] = None

class InventoryUpload(BaseModel):
    source_id: str
    files: List[FileScanItem]

class SourceStatus(BaseModel):
    source_id: str
    name: str
    count: int
    last_scan: Optional[str] = None

class InventoryStatusResponse(BaseModel):
    sources: List[SourceStatus]

class InventoryDelta(BaseModel):
    source_id: str
    action: str     # "upsert" or "delete"
    file: FileScanItem
