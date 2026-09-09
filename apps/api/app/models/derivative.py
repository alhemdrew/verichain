from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class EvidenceDerivative(Base):
    __tablename__ = "evidence_derivatives"

    id = Column(String(64), primary_key=True, index=True)
    parent_evidence_id = Column(String(64), ForeignKey("evidence.id"), nullable=False, index=True)
    derivative_evidence_id = Column(String(64), ForeignKey("evidence.id"), nullable=False, unique=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    derivation_type = Column(String(32), nullable=False, default="COPY", index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    parent_evidence = relationship("Evidence", foreign_keys=[parent_evidence_id], back_populates="derived_children")
    derivative_evidence = relationship("Evidence", foreign_keys=[derivative_evidence_id], back_populates="derived_from")
    creator = relationship("User", foreign_keys=[created_by_user_id], back_populates="created_derivatives")
