from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class UnifiedFileRow(BaseModel):
    id: str  # identifier (e.g. hash or file_id)
    name: str
    relative_path: str
    size_bytes: int
    hash_sha256: str
    location: str  # "A", "B", "Both", "Conflict"
    path_a: Optional[str] = None
    path_b: Optional[str] = None
    mtime_a: Optional[datetime] = None
    mtime_b: Optional[datetime] = None

class SetSummaryStrip(BaseModel):
    total_files: int
    union_count: int
    intersection_count: int
    only_a_count: int
    only_b_count: int
    conflict_count: int

class SetViewResponse(BaseModel):
    summary: SetSummaryStrip
    files: List[UnifiedFileRow]
