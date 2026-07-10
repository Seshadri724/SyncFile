from pydantic import BaseModel
from typing import List, Optional

class PlanItemCreate(BaseModel):
    action_type: str  # copy, move, delete
    file_path: str
    source_id: str
    destination_id: str
    sequence: int = 0

class PlanCreate(BaseModel):
    name: str
    items: List[PlanItemCreate]

class PlanItemResponse(BaseModel):
    id: str
    plan_id: str
    action_type: str
    file_path: str
    source_id: str
    destination_id: str
    status: str
    error_message: Optional[str] = None
    sequence: int
    executed_action_id: Optional[str] = None

    class Config:
        from_attributes = True

class PlanResponse(BaseModel):
    id: str
    name: str
    status: str
    created_at: str
    updated_at: str
    items: List[PlanItemResponse]

    class Config:
        from_attributes = True
