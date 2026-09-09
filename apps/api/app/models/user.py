from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    users = relationship("User", back_populates="organization")
    cases = relationship("Case", back_populates="organization")
    evidence = relationship("Evidence", back_populates="organization")
    custody_events = relationship("CustodyEvent", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    name = Column(String(255), nullable=False)
    # Investigator handle (human-facing), unique per organization
    handle = Column(String(64), nullable=True, index=True)
    # Stable investigator ID for human use
    investigator_id = Column(String(32), nullable=True, unique=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="investigator")
    status = Column(String(50), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    organization = relationship("Organization", back_populates="users")
    created_cases = relationship("Case", back_populates="created_by_user", foreign_keys="Case.created_by")
    collected_evidence = relationship("Evidence", back_populates="collector", foreign_keys="Evidence.created_by")
    custody_events = relationship("CustodyEvent", back_populates="actor", foreign_keys="CustodyEvent.actor_id")
    created_shares = relationship("EvidenceShare", foreign_keys="EvidenceShare.created_by_user_id", back_populates="created_by")
    received_shares = relationship("EvidenceShare", foreign_keys="EvidenceShare.recipient_user_id", back_populates="recipient")
    audit_events = relationship("AuditEvent", foreign_keys="AuditEvent.actor_id", back_populates="actor")
    created_derivatives = relationship("EvidenceDerivative", foreign_keys="EvidenceDerivative.created_by_user_id", back_populates="creator")
