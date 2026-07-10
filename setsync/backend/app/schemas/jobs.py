from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class SignaturesPayload(BaseModel):
    signatures: Dict[str, Any]  # serialized Adler signatures mapping

class DeltaPayload(BaseModel):
    delta_ops: List[Any]        # list of delta operations (copy, data)

class JobStatusUpdate(BaseModel):
    status: str                 # "completed", "failed", "in_progress"
    error_message: Optional[str] = None
