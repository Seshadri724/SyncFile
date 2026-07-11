from pydantic import BaseModel
from typing import List, Optional

class SourceRegister(BaseModel):
    name: str
    kind: str = "device"
    roots: List[str] = []
    org_id: Optional[str] = None

class SourceResponse(BaseModel):
    id: str
    name: str
    kind: str
    roots: List[str]
    status: str
    org_id: Optional[str] = None

    class Config:
        from_attributes = True

class SourceRegisterResponse(BaseModel):
    source: SourceResponse
    agent_key: str
