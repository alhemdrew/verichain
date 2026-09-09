from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class SyncQueueEntry(Base):
    __tablename__ = "sync_queue"

    id = Column(String(64), primary_key=True, index=True)
    evidence_id = Column(String(64), ForeignKey("evidence.id"), nullable=False, index=True)
    operation_type = Column(String(32), nullable=False, default="evidence_sync")
    state = Column(String(32), nullable=False, default="READY_FOR_SYNC")
    attempt_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    retryable = Column(Integer, nullable=False, default=1)
    last_error = Column(Text, nullable=True)

    evidence = relationship("Evidence", back_populates="sync_queue_entries")
