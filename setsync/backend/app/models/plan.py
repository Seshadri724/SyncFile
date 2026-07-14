import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from app.database import Base

class Plan(Base):
    __tablename__ = "plans"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    org_id = Column(String(36), nullable=True, index=True)
    status = Column(String(30), default="draft")  # draft, approved, executing, completed, failed, undone
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    items = relationship("PlanItem", back_populates="plan", cascade="all, delete-orphan", lazy="selectin")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "org_id": self.org_id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "items": [item.to_dict() for item in self.items]
        }

class PlanItem(Base):
    __tablename__ = "plan_items"
    
    id = Column(String(36), primary_key=True, index=True)
    plan_id = Column(String(36), ForeignKey("plans.id"), nullable=False)
    org_id = Column(String(36), nullable=True, index=True)
    action_type = Column(String(20), nullable=False)  # copy, move, delete
    file_path = Column(String(255), nullable=False)
    source_id = Column(String(36), nullable=False)
    destination_id = Column(String(36), nullable=False)
    status = Column(String(30), default="pending")  # pending, completed, failed
    error_message = Column(String(500), nullable=True)
    sequence = Column(Integer, default=0)
    executed_action_id = Column(String(36), nullable=True) # Tracks the generated action UUID
    
    plan = relationship("Plan", back_populates="items")

    def to_dict(self):
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "org_id": self.org_id,
            "action_type": self.action_type,
            "file_path": self.file_path,
            "source_id": self.source_id,
            "destination_id": self.destination_id,
            "status": self.status,
            "error_message": self.error_message,
            "sequence": self.sequence,
            "executed_action_id": self.executed_action_id
        }
