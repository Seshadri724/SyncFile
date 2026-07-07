import datetime
import uuid
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from app.database import Base

class UndoRecord(Base):
    __tablename__ = "undo_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    action_id = Column(String, ForeignKey("action_records.id"), nullable=False)
    backup_path = Column(String, nullable=False)  # Path in the trash folder
    expires_at = Column(DateTime, nullable=False)
    restored = Column(Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "action_id": self.action_id,
            "backup_path": self.backup_path,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "restored": self.restored,
        }
