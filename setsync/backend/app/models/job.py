import datetime
import uuid
import json
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from app.database import Base

class TransferJob(Base):
    __tablename__ = "transfer_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_path = Column(String, nullable=False)
    source_id = Column(String, ForeignKey("sources.id"), nullable=False)
    destination_id = Column(String, ForeignKey("sources.id"), nullable=False)
    action_type = Column(String, nullable=False)   # "copy", "move"
    status = Column(String, nullable=False, default="pending") 
    # Status states: "pending", "signatures_ready", "delta_ready", "completed", "failed"
    
    target_signatures = Column(Text, nullable=True) # JSON field mapping Adler to lists of SHA256 and block index
    delta_ops = Column(Text, nullable=True)         # JSON field mapping of computed delta operations list
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "file_path": self.file_path,
            "source_id": self.source_id,
            "destination_id": self.destination_id,
            "action_type": self.action_type,
            "status": self.status,
            "target_signatures": json.loads(self.target_signatures) if self.target_signatures else None,
            "delta_ops": json.loads(self.delta_ops) if self.delta_ops else None,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
