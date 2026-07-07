import datetime
import uuid
import json
from sqlalchemy import Column, String, DateTime, Text
from app.database import Base

class ActionRecord(Base):
    __tablename__ = "action_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    action_type = Column(String, nullable=False)  # "copy", "move", "sync", "undo"
    file_path = Column(String, nullable=False)     # Source relative path
    source = Column(String, nullable=False)        # "A" or "B"
    destination = Column(String, nullable=False)   # "A" or "B"
    status = Column(String, nullable=False)        # "pending", "in_progress", "completed", "failed", "undone"
    triggered_by = Column(String, nullable=False)  # "ui", "cli", "api"
    dry_run_preview = Column(Text, nullable=True)  # JSON-encoded preview payload
    error_message = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "action_type": self.action_type,
            "file_path": self.file_path,
            "source": self.source,
            "destination": self.destination,
            "status": self.status,
            "triggered_by": self.triggered_by,
            "dry_run_preview": json.loads(self.dry_run_preview) if self.dry_run_preview else None,
            "error_message": self.error_message,
        }
