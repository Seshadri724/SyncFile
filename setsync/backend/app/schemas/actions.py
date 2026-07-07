from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

class ActionRequest(BaseModel):
    file_path: str  # Relative path of the file to act upon
    source: str     # "A" or "B"
    destination: str # "A" or "B"
    triggered_by: Optional[str] = "ui"

class ActionResponse(BaseModel):
    id: str
    timestamp: datetime
    action_type: str
    file_path: str
    source: str
    destination: str
    status: str
    triggered_by: str
    dry_run_preview: Optional[Any] = None
    error_message: Optional[str] = None

class DryRunResponse(BaseModel):
    action_type: str
    file_path: str
    source: str
    destination: str
    will_overwrite: bool
    source_size: int
    dest_size: Optional[int] = None
    source_mtime: str
    dest_mtime: Optional[str] = None
    message: str
