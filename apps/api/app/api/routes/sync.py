from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.user import User
from app.security.crypto import build_manifest, canonical_json, manifest_hash
from app.security.key_manager import current_key_id
from app.services.custody_service import CustodyService
from app.services.local_vault_service import LocalVaultService
from app.services.sync_queue_service import SyncQueueService

router = APIRouter(prefix="/sync", tags=["sync"])


def _validate_evidence_payload(payload: dict, current_user: User, db: Session) -> Evidence:
    evidence_id = payload.get("evidence_id")
    if not evidence_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing evidence_id")

    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offline evidence not found")

    if evidence.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evidence belongs to a different organization")

    if payload.get("organization_id") is not None and int(payload["organization_id"]) != evidence.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization mismatch")

    case_id = payload.get("case_id")
    if case_id is not None:
        case = db.query(Case).filter(Case.id == int(case_id), Case.organization_id == evidence.organization_id).first()
        if case is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found for organization")
        evidence.case_id = int(case_id)
        db.commit()

    content_b64 = payload.get("content_base64")
    if not content_b64:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing original bytes")

    uploaded_bytes = base64.b64decode(content_b64)
    actual_hash = hashlib.sha256(uploaded_bytes).hexdigest()
    if payload.get("sha256") and payload["sha256"].lower() != actual_hash.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded bytes do not match the recorded SHA-256")
    if evidence.sha256 and evidence.sha256.lower() != actual_hash.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Server hash mismatch for uploaded evidence")

    manifest = build_manifest(
        evidence_id=evidence.id,
        case_id=evidence.case_id,
        organization_id=evidence.organization_id,
        original_filename=evidence.original_filename,
        mime_type=evidence.mime_type,
        file_size=evidence.file_size,
        collection_timestamp=evidence.collection_timestamp.isoformat() if evidence.collection_timestamp else None,
        collector_id=evidence.created_by,
        sha256=evidence.sha256 or evidence.original_sha256 or actual_hash,
    )
    expected_manifest_hash = hashlib.sha256(canonical_json(manifest).encode("utf-8")).hexdigest()
    if evidence.manifest_sha256 and evidence.manifest_sha256.lower() != expected_manifest_hash.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Manifest hash mismatch")

    if evidence.signature and evidence.public_key_pem:
        try:
            import base64 as _b64
            from cryptography.hazmat.primitives import serialization
            from cryptography.exceptions import InvalidSignature
            public_key = serialization.load_pem_public_key(evidence.public_key_pem.encode("utf-8"))
            payload_map = {
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
            public_key.verify(_b64.b64decode(evidence.signature), canonical_json(payload_map).encode("utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signature validation failed") from exc

    if evidence.storage_reference:
        local_bytes = LocalVaultService.retrieve_evidence(evidence)
        if hashlib.sha256(local_bytes).hexdigest().lower() != (evidence.sha256 or evidence.original_sha256 or actual_hash).lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vault content hash mismatch")

    return evidence


@router.post("/evidence")
def sync_evidence(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to an organization")

    evidence = _validate_evidence_payload(payload, current_user, db)

    try:
        SyncQueueService.mark_syncing(db, evidence.id)
        evidence.sync_state = "SYNCING"
        evidence.not_synced = True
        db.commit()

        if evidence.storage_reference:
            bytes_from_vault = LocalVaultService.retrieve_evidence(evidence)
            if hashlib.sha256(bytes_from_vault).hexdigest().lower() != (evidence.sha256 or evidence.original_sha256 or "").lower():
                raise ValueError("Local evidence bytes do not match the sealed hash")

        evidence.sync_state = "SYNCED"
        evidence.not_synced = False
        evidence.status = "SYNCED"
        evidence.updated_at = datetime.now(timezone.utc)
        db.commit()
        SyncQueueService.mark_synced(db, evidence)
        return {
            "evidence_id": evidence.id,
            "status": "SYNCED",
            "sync_state": evidence.sync_state,
            "sha256": evidence.sha256,
            "manifest_sha256": evidence.manifest_sha256,
            "signature_valid": True,
            "organization_id": evidence.organization_id,
            "case_id": evidence.case_id,
            "accepted_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        SyncQueueService.mark_failed(db, evidence, reason=str(exc))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
