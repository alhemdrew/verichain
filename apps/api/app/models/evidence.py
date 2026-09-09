from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(String(64), primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    evidence_name = Column(String(255), nullable=True, default=None)
    evidence_type = Column(String(50), nullable=False, default="OTHER")
    mime_type = Column(String(255), nullable=True)
    file_size = Column(Integer, nullable=False, default=0)
    collection_timestamp = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="CREATED")
    sync_state = Column(String(32), nullable=True, default="LOCAL_ONLY")
    not_synced = Column(Boolean, nullable=False, default=True)
    local_case_id = Column(String(128), nullable=True, index=True)
    storage_reference = Column(String(512), nullable=True)
    vault_object_id = Column(String(128), nullable=True, index=True)
    vault_status = Column(String(32), nullable=True, default="LOCAL_ONLY")
    vault_algorithm = Column(String(32), nullable=True, default="AES-256-GCM")
    vault_version = Column(String(32), nullable=True, default="aesgcm-v1")
    vault_nonce = Column(String(256), nullable=True)
    vault_path = Column(String(512), nullable=True)
    vault_created_at = Column(DateTime(timezone=True), nullable=True)
    vault_updated_at = Column(DateTime(timezone=True), nullable=True)
    sha256 = Column(String(128), nullable=True, index=True)
    original_sha256 = Column(String(128), nullable=True, index=True)
    manifest_sha256 = Column(String(128), nullable=True, index=True)
    sealed_at = Column(DateTime(timezone=True), nullable=True)
    seal_version = Column(String(64), nullable=True, default="sha256-seal-v1")
    signature = Column(String(2048), nullable=True)
    signature_algorithm = Column(String(32), nullable=True, default="ed25519")
    key_id = Column(String(64), nullable=True, index=True)
    signature_version = Column(String(64), nullable=True, default="ed25519-sign-v1")
    signed_at = Column(DateTime(timezone=True), nullable=True)
    public_key_pem = Column(Text, nullable=True)
    evidence_metadata = Column("metadata", JSON, nullable=True)
    archived = Column(Boolean, nullable=False, default=False)

    case = relationship("Case", back_populates="evidence")
    organization = relationship("Organization", back_populates="evidence")
    collector = relationship("User", back_populates="collected_evidence", foreign_keys=[created_by])
    custody_events = relationship("CustodyEvent", back_populates="evidence", cascade="all, delete-orphan")
    sync_queue_entries = relationship("SyncQueueEntry", back_populates="evidence", cascade="all, delete-orphan")
    shares = relationship("EvidenceShare", back_populates="evidence", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="evidence", cascade="all, delete-orphan")
    derived_children = relationship("EvidenceDerivative", foreign_keys="EvidenceDerivative.parent_evidence_id", back_populates="parent_evidence", cascade="all, delete-orphan")
    derived_from = relationship("EvidenceDerivative", foreign_keys="EvidenceDerivative.derivative_evidence_id", back_populates="derivative_evidence", uselist=False)

    def archive(self, db, actor_id: int, reason: str):
        self.archived = True
        db.add(self)
        db.commit()
        db.refresh(self)
        try:
            from app.models.audit import AuditEvent

            audit = AuditEvent(
                id=str(__import__("uuid").uuid4()),
                actor_id=actor_id,
                evidence_id=self.id,
                event_type="EVIDENCE_ARCHIVE",
                result="SUCCESS",
                details={"reason": reason},
            )
            db.add(audit)
            db.commit()
        except Exception:
            pass
