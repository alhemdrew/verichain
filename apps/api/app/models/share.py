from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class EvidenceShare(Base):
    __tablename__ = "evidence_shares"

    id = Column(String(64), primary_key=True, index=True)
    evidence_id = Column(String(64), ForeignKey("evidence.id"), nullable=False, index=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    permissions = Column(JSON, nullable=False, default=lambda: ["VIEW"])
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)
    reason = Column(Text, nullable=True)

    evidence = relationship("Evidence", back_populates="shares")
    recipient = relationship("User", foreign_keys=[recipient_user_id], back_populates="received_shares")
    created_by = relationship("User", foreign_keys=[created_by_user_id], back_populates="created_shares")
    audit_events = relationship("AuditEvent", back_populates="share", cascade="all, delete-orphan")
