from pydantic import BaseModel
from typing import List, Optional

class DuplicateFileEntry(BaseModel):
    id: str
    source_id: str
    source_name: str
    path: str
    relative_path: str
    size_bytes: int
    mtime: str

class DuplicateGroup(BaseModel):
    hash_sha256: str
    size_bytes: int
    files: List[DuplicateFileEntry]

class DuplicateAnalysisResponse(BaseModel):
    total_groups: int
    total_duplicate_files: int
    space_reclaimable_bytes: int
    groups: List[DuplicateGroup]

class StaleOrphanEntry(BaseModel):
    id: str
    source_id: str
    source_name: str
    path: str
    relative_path: str
    size_bytes: int
    mtime: str
    age_days: int
