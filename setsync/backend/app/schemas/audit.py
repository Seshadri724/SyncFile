from pydantic import BaseModel
from typing import List
from app.schemas.actions import ActionResponse

class AuditLogResponse(BaseModel):
    actions: List[ActionResponse]
    total_count: int
