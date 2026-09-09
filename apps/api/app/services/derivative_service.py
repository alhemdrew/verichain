from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.derivative import EvidenceDerivative
from app.models.evidence import Evidence
from app.models.share import EvidenceShare
from app.models.user import User
from app.security.crypto import build_manifest, canonical_json, hash_bytes, manifest_hash
from app.services.custody_service import CustodyService
from app.services.evidence_service import EvidenceService
from app.services.local_vault_service import LocalVaultService
from app.services.signature_service import SignatureService
from app.services.storage_service import LocalStorageService

ALLOWED_DERIVATION_TYPES = {"COPY", "REDACTION", "BLUR", "CROP", "TRIM", "TRANSCODE", "ANNOTATION", "OTHER"}


class DerivativeService:
    @staticmethod
    def _user_value(current_user: User | dict, field: str, default=None):
        if isinstance(current_user, dict):
            return current_user.get(field, default)
        return getattr(current_user, field, default)

    @staticmethod
    def normalize_derivation_type(raw_value: str | None) -> str:
        value = (raw_value or "COPY").strip().upper()
        if value not in ALLOWED_DERIVATION_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported derivation type: {raw_value}",
            )
        return value

    @staticmethod
    def can_create_derivative(db: Session, *, current_user: User | dict, evidence: Evidence) -> bool:
        user_org_id = DerivativeService._user_value(current_user, "organization_id")
        user_id = DerivativeService._user_value(current_user, "id")

        if evidence.organization_id != user_org_id:
            return False
        if evidence.created_by == user_id:
            return True

        shares = (
            db.query(EvidenceShare)
            .filter(EvidenceShare.evidence_id == evidence.id, EvidenceShare.recipient_user_id == user_id)
            .all()
        )
        for share in shares:
            ShareService = __import__("app.services.share_service", fromlist=["ShareService"]).ShareService
            status_name = ShareService.set_share_status(share)
            if status_name != "ACTIVE":
                continue
            if "CREATE_DERIVATIVE" in (share.permissions or []):
                return True
        return False

    @staticmethod
    def build_provenance_metadata(*, parent_evidence: Evidence, derivation_type: str, description: str | None) -> dict:
        return {
            "is_derivative": True,
            "parent_evidence_id": parent_evidence.id,
            "parent_case_id": parent_evidence.case_id,
            "parent_organization_id": parent_evidence.organization_id,
            "derivation_type": derivation_type,
            "description": description,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def create_derivative(
        db: Session,
        *,
        parent_evidence: Evidence,
        current_user: User,
        derivation_type: str,
        description: str | None,
    ) -> Evidence:
        derivation_name = DerivativeService.normalize_derivation_type(derivation_type)
        if not DerivativeService.can_create_derivative(db, current_user=current_user, evidence=parent_evidence):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not authorized to create derivatives")

        actor_id = DerivativeService._user_value(current_user, "id")
        original_bytes = EvidenceService.get_file_bytes(parent_evidence)
        derivative_id = str(uuid.uuid4())
        derivative_storage = LocalStorageService(Path(__file__).resolve().parents[1] / "storage" / "evidence")
        storage_reference = derivative_storage.store(name=f"{derivative_id}.bin", content=original_bytes)
        derivative_sha256 = hash_bytes(original_bytes)

        provenance = DerivativeService.build_provenance_metadata(
            parent_evidence=parent_evidence,
            derivation_type=derivation_name,
            description=description,
        )

        base_name = parent_evidence.original_filename
        suffix = Path(base_name).suffix
        stem = Path(base_name).stem
        derivative_filename = f"{stem}-derivative{suffix or '.bin'}"

        evidence = Evidence(
            id=derivative_id,
            case_id=parent_evidence.case_id,
            organization_id=parent_evidence.organization_id,
            original_filename=derivative_filename,
            evidence_type=derivation_name,
            mime_type=parent_evidence.mime_type,
            file_size=len(original_bytes),
            collection_timestamp=parent_evidence.collection_timestamp,
            created_by=actor_id,
            description=description or f"Derived from {parent_evidence.id} using {derivation_name}",
            status="CREATED",
            sync_state="LOCAL_ONLY",
            not_synced=True,
            local_case_id=parent_evidence.local_case_id,
            storage_reference=storage_reference,
            sha256=derivative_sha256,
            original_sha256=derivative_sha256,
            evidence_metadata=provenance,
        )
        db.add(evidence)
        db.commit()
        db.refresh(evidence)

        CustodyService.create_event(
            db,
            evidence=evidence,
            actor_id=actor_id,
            event_type="CREATED",
            details={
                "parent_evidence_id": parent_evidence.id,
                "derivation_type": derivation_name,
                "description": description,
                "source": "derivative",
            },
        )

        manifest = build_manifest(
            evidence_id=evidence.id,
            case_id=evidence.case_id,
            organization_id=evidence.organization_id,
            original_filename=evidence.original_filename,
            mime_type=evidence.mime_type,
            file_size=evidence.file_size,
            collection_timestamp=evidence.collection_timestamp.isoformat() if evidence.collection_timestamp else None,
            collector_id=evidence.created_by,
            sha256=evidence.sha256,
            extra_fields=provenance,
        )
        evidence.manifest_sha256 = manifest_hash(manifest)
        evidence.sealed_at = datetime.now(timezone.utc)
        evidence.seal_version = "sha256-seal-v1"
        evidence.status = "SEALED"
        db.commit()
        db.refresh(evidence)

        CustodyService.create_event(
            db,
            evidence=evidence,
            actor_id=actor_id,
            event_type="SEALED",
            details={
                "sha256": evidence.sha256,
                "manifest_sha256": evidence.manifest_sha256,
                "seal_version": evidence.seal_version,
            },
        )

        SignatureService.sign_evidence(db, evidence=evidence, actor_id=actor_id)
        LocalVaultService.store_evidence(db, evidence, plaintext=original_bytes)
        evidence.sync_state = "LOCAL_ONLY"
        evidence.not_synced = True
        db.commit()
        db.refresh(evidence)

        relation = EvidenceDerivative(
            id=f"derivative-{uuid.uuid4().hex}",
            parent_evidence_id=parent_evidence.id,
            derivative_evidence_id=evidence.id,
            created_by_user_id=actor_id,
            derivation_type=derivation_name,
            description=description,
        )
        db.add(relation)
        db.commit()
        db.refresh(relation)

        audit_event = AuditEvent(
            id=str(uuid.uuid4()),
            actor_id=actor_id,
            evidence_id=evidence.id,
            share_id=None,
            event_type="DERIVATIVE_CREATED",
            result="SUCCESS",
            details={
                "parent_evidence_id": parent_evidence.id,
                "derivation_type": derivation_name,
                "sha256": evidence.sha256,
            },
        )
        db.add(audit_event)
        db.commit()

        return evidence

    @staticmethod
    def get_provenance(db: Session, *, evidence_id: str):
        parent_link = db.query(EvidenceDerivative).filter(EvidenceDerivative.derivative_evidence_id == evidence_id).first()
        child_links = db.query(EvidenceDerivative).filter(EvidenceDerivative.parent_evidence_id == evidence_id).all()

        parent = None
        if parent_link is not None:
            parent = db.query(Evidence).filter(Evidence.id == parent_link.parent_evidence_id).first()

        children = []
        for link in child_links:
            child = db.query(Evidence).filter(Evidence.id == link.derivative_evidence_id).first()
            if child is not None:
                children.append({
                    "id": child.id,
                    "original_filename": child.original_filename,
                    "sha256": child.sha256,
                    "derivation_type": link.derivation_type,
                    "description": link.description,
                    "created_at": link.created_at.isoformat() if link.created_at else None,
                })

        return {
            "evidence_id": evidence_id,
            "parent": {
                "evidence_id": parent.id,
                "original_filename": parent.original_filename,
                "sha256": parent.sha256,
            } if parent else None,
            "children": children,
        }
