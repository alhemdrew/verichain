from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from sqlalchemy.orm import Session

from app.models.evidence import Evidence
from app.security.crypto import build_manifest, canonical_json, hash_bytes, manifest_hash
from app.security.key_manager import current_key_id, generate_or_load_signing_keypair
from app.services.custody_service import CustodyService
from app.services.local_vault_service import LocalVaultService
from app.services.storage_service import LocalStorageService


class OfflineEvidenceService:
    STORAGE_ROOT = Path(__file__).resolve().parents[1] / "storage" / "evidence"

    @staticmethod
    def generate_local_evidence_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _storage_service() -> LocalStorageService:
        return LocalStorageService(OfflineEvidenceService.STORAGE_ROOT)

    @staticmethod
    def _persist_content(evidence_id: str, content: bytes) -> str:
        return OfflineEvidenceService._storage_service().store(name=f"{evidence_id}.bin", content=content)

    @staticmethod
    def create_offline_evidence(
        db: Session,
        *,
        case_id: int,
        organization_id: int,
        created_by: int,
        original_filename: str,
        mime_type: str | None,
        content: bytes,
        description: str | None = None,
        evidence_type: str = "OTHER",
        file_size: int | None = None,
        collection_timestamp: datetime | None = None,
        local_case_id: str | None = None,
    ) -> Evidence:
        if not isinstance(content, (bytes, bytearray)):
            content = bytes(content)
        content_bytes = bytes(content)
        evidence_id = OfflineEvidenceService.generate_local_evidence_id()
        storage_reference = OfflineEvidenceService._persist_content(evidence_id, content_bytes)
        file_size = len(content_bytes) if file_size is None else file_size
        sha256 = hash_bytes(content_bytes)

        evidence = Evidence(
            id=evidence_id,
            case_id=case_id,
            organization_id=organization_id,
            original_filename=original_filename,
            evidence_name=original_filename,
            evidence_type=evidence_type.upper(),
            mime_type=mime_type,
            file_size=file_size,
            collection_timestamp=collection_timestamp,
            created_by=created_by,
            description=description,
            status="DRAFT",
            sync_state="LOCAL_ONLY",
            not_synced=True,
            local_case_id=local_case_id or f"local-case-{case_id}",
            storage_reference=storage_reference,
            sha256=sha256,
            original_sha256=sha256,
            evidence_metadata={
                "offline": True,
                "source": "local",
                "sync_state": "LOCAL_ONLY",
                "not_synced": True,
            },
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
                "offline": True,
                "source": "local",
                "original_filename": original_filename,
                "mime_type": mime_type,
                "file_size": file_size,
                "local_case_id": evidence.local_case_id,
            },
        )

        manifest = build_manifest(
            evidence_id=evidence.id,
            case_id=evidence.case_id,
            organization_id=evidence.organization_id,
            original_filename=evidence.original_filename,
            mime_type=evidence.mime_type,
            file_size=evidence.file_size or file_size,
            collection_timestamp=evidence.collection_timestamp.isoformat() if evidence.collection_timestamp else None,
            collector_id=evidence.created_by,
            sha256=sha256,
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
            actor_id=created_by,
            event_type="SEALED",
            details={
                "sha256": sha256,
                "manifest_sha256": evidence.manifest_sha256,
                "seal_version": evidence.seal_version,
            },
        )

        private_key, public_key, key_id = generate_or_load_signing_keypair()
        payload = {
            "evidence_id": evidence.id,
            "case_id": evidence.case_id,
            "organization_id": evidence.organization_id,
            "filename": evidence.original_filename,
            "mime_type": evidence.mime_type,
            "file_size": evidence.file_size,
            "collection_timestamp": evidence.collection_timestamp.isoformat() if evidence.collection_timestamp else None,
            "collector_id": evidence.created_by,
            "sha256": evidence.sha256,
            "manifest_sha256": evidence.manifest_sha256,
            "seal_version": evidence.seal_version,
            "key_id": key_id,
            "signature_version": "ed25519-sign-v1",
        }
        payload_json = canonical_json(payload)
        signature_bytes = private_key.sign(payload_json.encode("utf-8"))
        evidence.signature = base64.b64encode(signature_bytes).decode("utf-8")
        evidence.signature_algorithm = "ed25519"
        evidence.key_id = key_id
        evidence.signature_version = "ed25519-sign-v1"
        evidence.signed_at = datetime.now(timezone.utc)
        evidence.public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        evidence.status = "SIGNED"
        db.commit()
        db.refresh(evidence)

        CustodyService.create_event(
            db,
            evidence=evidence,
            actor_id=created_by,
            event_type="SIGNED",
            details={
                "key_id": key_id,
                "signature_algorithm": "ed25519",
                "signature_version": "ed25519-sign-v1",
            },
        )

        LocalVaultService.store_evidence(db, evidence, plaintext=content_bytes)
        evidence.sync_state = "LOCAL_ONLY"
        evidence.not_synced = True
        evidence.status = "READY_FOR_SYNC"
        db.commit()
        db.refresh(evidence)
        return evidence

    @staticmethod
    def verify_offline_evidence(db: Session, evidence: Evidence) -> dict:
        if not evidence.storage_reference:
            raise ValueError("Evidence has no storage reference")

        try:
            decrypted = LocalVaultService.retrieve_evidence(evidence)
            local_integrity = hashlib.sha256(decrypted).hexdigest() == (evidence.sha256 or evidence.original_sha256 or "").lower()
        except (FileNotFoundError, ValueError):
            local_integrity = False
            decrypted = None

        if decrypted is not None and evidence.storage_reference:
            current_bytes = Path(evidence.storage_reference).read_bytes()
            current_sha256 = hashlib.sha256(current_bytes).hexdigest()
            local_integrity = local_integrity and current_sha256 == (evidence.sha256 or evidence.original_sha256 or "").lower()

        manifest = build_manifest(
            evidence_id=evidence.id,
            case_id=evidence.case_id,
            organization_id=evidence.organization_id,
            original_filename=evidence.original_filename,
            mime_type=evidence.mime_type,
            file_size=evidence.file_size,
            collection_timestamp=evidence.collection_timestamp.isoformat() if evidence.collection_timestamp else None,
            collector_id=evidence.created_by,
            sha256=evidence.sha256 or evidence.original_sha256 or "",
            extra_fields=evidence.evidence_metadata or {},
        )
        manifest_valid = bool(evidence.manifest_sha256) and evidence.manifest_sha256 == manifest_hash(manifest)

        signature_valid = False
        if local_integrity and manifest_valid and evidence.signature and evidence.public_key_pem and evidence.signature_algorithm == "ed25519":
            try:
                public_key = serialization.load_pem_public_key(evidence.public_key_pem.encode("utf-8"))
                payload = {
                    "evidence_id": evidence.id,
                    "case_id": evidence.case_id,
                    "organization_id": evidence.organization_id,
                    "filename": evidence.original_filename,
                    "mime_type": evidence.mime_type,
                    "file_size": evidence.file_size,
                    "collection_timestamp": evidence.collection_timestamp.isoformat() if evidence.collection_timestamp else None,
                    "collector_id": evidence.created_by,
                    "sha256": evidence.sha256,
                    "manifest_sha256": evidence.manifest_sha256,
                    "seal_version": evidence.seal_version,
                    "key_id": evidence.key_id or current_key_id(),
                    "signature_version": evidence.signature_version or "ed25519-sign-v1",
                }
                public_key.verify(base64.b64decode(evidence.signature), canonical_json(payload).encode("utf-8"))
                signature_valid = True
            except (TypeError, ValueError, InvalidSignature):
                signature_valid = False

        custody_result = CustodyService.verify_chain(
            db,
            evidence_id=evidence.id,
            organization_id=evidence.organization_id,
        )
        custody_valid = bool(custody_result["chain_valid"])
        overall_valid = local_integrity and manifest_valid and signature_valid and custody_valid

        return {
            "evidence_id": evidence.id,
            "local_integrity": local_integrity,
            "manifest_valid": manifest_valid,
            "signature_valid": signature_valid,
            "custody_valid": custody_valid,
            "overall_valid": overall_valid,
            "server_sync": "NOT_SYNCED",
            "status": "LOCAL INTEGRITY VERIFIED" if overall_valid else "LOCAL INTEGRITY FAILED",
            "custody": custody_result,
        }
