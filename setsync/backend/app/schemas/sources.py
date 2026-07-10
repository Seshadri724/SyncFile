from pydantic import BaseModel
from typing import List, Optional

class SourceRegister(BaseModel):
    name: str
    kind: str = "device"
    roots: List[str] = []

class SourceResponse(BaseModel):
    id: str
    name: str
    kind: str
    roots: List[str]
    status: str

    class Config:
        from_attributes = True

class SourceRegisterResponse(BaseModel):
    source: SourceResponse
    agent_key: str
