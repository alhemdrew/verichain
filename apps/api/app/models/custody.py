from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class CustodyEvent(Base):
    __tablename__ = "custody_events"

    id = Column(String(64), primary_key=True, index=True)
    evidence_id = Column(String(64), ForeignKey("evidence.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    event_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    details = Column(JSON, nullable=True, default=dict)
    previous_event_hash = Column(String(128), nullable=True, index=True)
    event_hash = Column(String(128), nullable=False, index=True)
    event_version = Column(String(64), nullable=False, default="custody-v1")
    event_index = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    evidence = relationship("Evidence", back_populates="custody_events")
    organization = relationship("Organization", back_populates="custody_events")
    actor = relationship("User", back_populates="custody_events", foreign_keys=[actor_id])

    def canonical_payload(self) -> dict:
        event_timestamp = self.event_timestamp
        if isinstance(event_timestamp, datetime) and event_timestamp.tzinfo is not None:
            event_timestamp = event_timestamp.astimezone(timezone.utc)
        if isinstance(event_timestamp, datetime):
            event_timestamp = event_timestamp.replace(tzinfo=None)
        return {
            "event_id": self.id,
            "evidence_id": self.evidence_id,
            "organization_id": self.organization_id,
            "actor_id": self.actor_id,
            "event_type": self.event_type,
            "event_timestamp": event_timestamp.isoformat() if isinstance(event_timestamp, datetime) else None,
            "details": self.details or {},
            "previous_event_hash": self.previous_event_hash,
            "event_version": self.event_version,
        }
