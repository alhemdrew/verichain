from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.evidence import Evidence
from app.security.crypto import build_manifest, hash_bytes, hash_file, manifest_hash
from app.services.custody_service import CustodyService
from app.services.storage_service import LocalStorageService
from app.services.signature_service import SignatureService
from app.core.config import get_settings

_settings = get_settings()


class EvidenceService:
    STORAGE_ROOT = Path(__file__).resolve().parents[1] / "storage" / "evidence"

    @staticmethod
    def _storage_service() -> LocalStorageService:
        return LocalStorageService(EvidenceService.STORAGE_ROOT)

    @staticmethod
    def _persist_content(evidence_id: str, content: bytes) -> str:
        service = EvidenceService._storage_service()
        return service.store(name=f"{evidence_id}.bin", content=content)

    @staticmethod
    def _content_from_base64(value: str | None) -> bytes | None:
        if value is None:
            return None
        return base64.b64decode(value)

    @staticmethod
    def _effective_evidence_name(original_filename: str, evidence_name: str | None) -> str:
        candidate = (evidence_name or "").strip()
        if candidate:
            return candidate
        return original_filename.strip() or "evidence"

    @staticmethod
    def create_evidence(
        db: Session,
        *,
        case_id: int,
        organization_id: int,
        created_by: int,
        original_filename: str,
        evidence_name: str | None = None,
        evidence_type: str,
        mime_type: str | None,
        file_size: int,
        collection_timestamp: datetime | None,
        description: str | None,
        metadata: dict | None,
        content_base64: str | None = None,
    ) -> Evidence:
        evidence_id = str(uuid.uuid4())
        content = EvidenceService._content_from_base64(content_base64)
        storage_reference = None
        sha256 = None

        if content is not None:
            storage_reference = EvidenceService._persist_content(evidence_id, content)
            sha256 = hash_bytes(content)
            if file_size in (0, None):
                file_size = len(content)

        evidence = Evidence(
            id=evidence_id,
            case_id=case_id,
            organization_id=organization_id,
            original_filename=original_filename,
            evidence_name=EvidenceService._effective_evidence_name(original_filename, evidence_name),
            evidence_type=evidence_type.upper(),
            mime_type=mime_type,
            file_size=file_size,
            collection_timestamp=collection_timestamp,
            created_by=created_by,
            description=description,
            status="CREATED",
            storage_reference=storage_reference,
            sha256=sha256,
            original_sha256=sha256,
            evidence_metadata=metadata or {},
        )
        db.add(evidence)
        db.commit()
        db.refresh(evidence)
        CustodyService.create_event(
            db,
            evidence=evidence,
            actor_id=created_by,
            event_type="CREATED",
            details={
                "original_filename": original_filename,
                "evidence_type": evidence_type,
                "file_size": file_size,
                "description": description,
                "content_present": content is not None,
            },
        )
        # Automatically seal (create manifest and sha256) when content was provided at creation.
        if content is not None:
            try:
                EvidenceService.seal_evidence(db, evidence=evidence)
            except Exception as exc:
                import logging

                logging.exception("Automatic sealing failed during create_evidence: %s", exc)

            # Attempt to sign automatically if sealing succeeded. Signing requires a keypair;
            # generate_or_load_signing_keypair will create one if missing.
            if _settings.verichain_auto_sign:
                try:
                    SignatureService.sign_evidence(db, evidence=evidence, actor_id=created_by)
                except Exception as exc:
                    import logging

                    logging.exception("Automatic signing failed during create_evidence: %s", exc)
        return evidence

    @staticmethod
    def get_file_bytes(evidence: Evidence) -> bytes:
        if not evidence.storage_reference:
            raise FileNotFoundError("Evidence file is not stored")
        return Path(evidence.storage_reference).read_bytes()

    @staticmethod
    def seal_evidence(db: Session, *, evidence: Evidence):
        if not evidence.storage_reference:
            raise ValueError("Evidence is missing an on-disk storage reference")

        # If already sealed, return without creating duplicate SEALED custody event
        if evidence.sealed_at:
            return evidence

        file_bytes = EvidenceService.get_file_bytes(evidence)
        evidence_sha256 = hash_bytes(file_bytes)
        manifest = build_manifest(
            evidence_id=evidence.id,
            case_id=evidence.case_id,
            organization_id=evidence.organization_id,
            original_filename=evidence.original_filename,
            mime_type=evidence.mime_type,
            file_size=evidence.file_size or len(file_bytes),
            collection_timestamp=evidence.collection_timestamp.isoformat() if evidence.collection_timestamp else None,
            collector_id=evidence.created_by,
            sha256=EvidenceService.ensure_lowercase_hex(evidence_sha256),
        )
        manifest_digest = manifest_hash(manifest)

        evidence.sha256 = EvidenceService.ensure_lowercase_hex(evidence_sha256)
        evidence.original_sha256 = EvidenceService.ensure_lowercase_hex(evidence_sha256)
        evidence.manifest_sha256 = EvidenceService.ensure_lowercase_hex(manifest_digest)
        evidence.sealed_at = datetime.now(timezone.utc)
        evidence.seal_version = "sha256-seal-v1"
        evidence.status = "SEALED"
        db.commit()
        db.refresh(evidence)
        CustodyService.create_event(
            db,
            evidence=evidence,
            actor_id=evidence.created_by,
            event_type="SEALED",
            details={
                "sha256": EvidenceService.ensure_lowercase_hex(evidence_sha256),
                "manifest_sha256": EvidenceService.ensure_lowercase_hex(manifest_digest),
                "seal_version": evidence.seal_version,
                "sealed_at": evidence.sealed_at.isoformat() if evidence.sealed_at else None,
            },
        )
        return evidence

    @staticmethod
    def ensure_lowercase_hex(value: str) -> str:
        return value.lower() if value else value

    @staticmethod
    def verify_evidence(evidence: Evidence, *, db: Session | None = None):
        if not evidence.storage_reference:
            raise FileNotFoundError("Evidence file is not stored")
        if not evidence.sha256 and not evidence.original_sha256:
            raise ValueError("Evidence has not been sealed")

        current_bytes = EvidenceService.get_file_bytes(evidence)
        current_sha256 = hash_bytes(current_bytes)
        recorded_sha256 = EvidenceService.ensure_lowercase_hex(evidence.sha256 or evidence.original_sha256)
        match = current_sha256 == recorded_sha256.lower()

        if match:
            evidence.status = "VERIFIED"
        else:
            evidence.status = "SEALED"
        if db is not None:
            db.add(evidence)
            db.commit()
            db.refresh(evidence)

        return {
            "evidence_id": evidence.id,
            "recorded_sha256": recorded_sha256,
            "current_sha256": current_sha256,
            "match": match,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "seal_version": evidence.seal_version or "sha256-seal-v1",
            "status": "INTEGRITY VERIFIED" if match else "INTEGRITY FAILURE",
        }

    @staticmethod
    def list_evidence_for_case(db: Session, *, case_id: int, organization_id: int):
        return (
            db.query(Evidence)
            .filter(Evidence.case_id == case_id, Evidence.organization_id == organization_id)
            .order_by(Evidence.created_at.desc())
            .all()
        )

    @staticmethod
    def get_evidence_for_organization(db: Session, *, evidence_id: str, organization_id: int):
        return (
            db.query(Evidence)
            .filter(Evidence.id == evidence_id, Evidence.organization_id == organization_id)
            .first()
        )

    @staticmethod
    def update_evidence(db: Session, *, evidence: Evidence, patch: dict):
        protected_keys = {"id", "organization_id", "case_id", "created_by", "original_sha256", "sha256", "manifest_sha256", "sealed_at", "seal_version", "storage_reference", "status", "original_filename"}
        for key, value in patch.items():
            if key in protected_keys:
                continue
            if key == "metadata":
                key = "evidence_metadata"
            if key == "evidence_name" and value is not None:
                candidate = str(value).strip()
                setattr(evidence, key, candidate or evidence.original_filename)
                continue
            if hasattr(evidence, key):
                setattr(evidence, key, value)
        db.commit()
        db.refresh(evidence)
        return evidence
