import datetime
import uuid
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Source(Base):
    __tablename__ = "sources"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    kind = Column(String, nullable=False)            # "device" or "remote"
    roots = Column(JSON, nullable=False, default=list) # e.g. ["/path/to/folder"]
    agent_key_hash = Column(String, nullable=True)   # SHA256 hashed secret token for auth
    last_seen_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String, default="online")        # "online" or "offline"
    org_id = Column(String, ForeignKey("organizations.id"), nullable=True)

    org = relationship("Organization", back_populates="sources")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "roots": self.roots,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "status": self.status,
            "org_id": self.org_id,
        }
