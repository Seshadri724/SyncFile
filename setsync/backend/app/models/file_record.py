import datetime
import uuid
from sqlalchemy import Column, String, Integer, DateTime, UniqueConstraint, Index, ForeignKey
from app.database import Base

class FileRecord(Base):
    __tablename__ = "file_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id = Column(String, ForeignKey("sources.id"), nullable=False)
    path = Column(String, nullable=False)        # Absolute path
    relative_path = Column(String, nullable=False) # Normalized path relative to root
    size_bytes = Column(Integer, nullable=False)
    mtime = Column(DateTime, nullable=False)
    hash_sha256 = Column(String, nullable=False)
    scanned_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('source_id', 'relative_path', name='_source_id_relative_path_uc'),
        Index('idx_file_records_hash', 'source_id', 'hash_sha256'),
        Index('idx_file_records_path', 'source_id', 'relative_path'),
        Index('idx_file_records_hash_sha256', 'hash_sha256'),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "source_id": self.source_id,
            "path": self.path,
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "mtime": self.mtime.isoformat() if self.mtime else None,
            "hash_sha256": self.hash_sha256,
            "scanned_at": self.scanned_at.isoformat() if self.scanned_at else None,
        }
