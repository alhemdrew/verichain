from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(64), primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    evidence_id = Column(String(64), ForeignKey("evidence.id"), nullable=False, index=True)
    share_id = Column(String(64), ForeignKey("evidence_shares.id"), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    result = Column(String(32), nullable=False, default="SUCCESS", index=True)
    action_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    details = Column(JSON, nullable=True, default=dict)

    evidence = relationship("Evidence", back_populates="audit_events")
    actor = relationship("User", back_populates="audit_events", foreign_keys=[actor_id])
    share = relationship("EvidenceShare", back_populates="audit_events")

    @property
    def actor_handle(self) -> str | None:
        try:
            return self.actor.handle
        except Exception:
            return None
