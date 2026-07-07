from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class FileScanItem(BaseModel):
    path: str
    relative_path: str
    size_bytes: int
    mtime: datetime
    hash_sha256: str

class InventoryUpload(BaseModel):
    source_pc: str  # "A" or "B"
    files: List[FileScanItem]

class InventoryStatusResponse(BaseModel):
    pc_a_count: int
    pc_b_count: int
    pc_a_last_scan: Optional[str] = None
    pc_b_last_scan: Optional[str] = None

class InventoryDelta(BaseModel):
    source_pc: str  # "A" or "B"
    action: str     # "upsert" or "delete"
    file: FileScanItem
