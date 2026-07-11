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

class FleetResponse(BaseModel):
    total_sources: int
    active_sources: int
    offline_sources: int
    total_files: int
    total_bytes: int
    unique_files_count: int
    unique_files_bytes: int

class GovernanceFileEntry(BaseModel):
    id: str
    source_id: str
    source_name: str
    path: str
    relative_path: str
    size_bytes: int
    flag_reason: str

class GovernanceResponse(BaseModel):
    total_flagged_files: int
    flagged_files: List[GovernanceFileEntry]
