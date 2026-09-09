from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from sqlalchemy.orm import Session

from app.models.custody import CustodyEvent
from app.models.evidence import Evidence
from app.security.crypto import build_manifest, canonical_json, hash_bytes
from app.security.key_manager import current_key_id, generate_or_load_signing_keypair


class SignatureService:
    @staticmethod
    def build_signing_payload(evidence: Evidence) -> dict:
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
        metadata = evidence.evidence_metadata or {}
        if metadata.get("parent_evidence_id") is not None:
            payload["parent_evidence_id"] = metadata["parent_evidence_id"]
        if metadata.get("derivation_type") is not None:
            payload["derivation_type"] = metadata["derivation_type"]
        if metadata.get("description") is not None:
            payload["description"] = metadata["description"]
        return payload

    @staticmethod
    def sign_evidence(db: Session, *, evidence: Evidence, actor_id: int) -> dict:
        if not evidence.storage_reference:
            raise ValueError("Evidence is missing an on-disk storage reference")
        if not evidence.sha256 or not evidence.manifest_sha256:
            raise ValueError("Evidence must be sealed before signing")

        private_key, public_key, key_id = generate_or_load_signing_keypair()
        payload = SignatureService.build_signing_payload(evidence)
        payload_json = canonical_json(payload)
        signature_bytes = private_key.sign(payload_json.encode("utf-8"))
        signature_b64 = base64.b64encode(signature_bytes).decode("utf-8")
        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        evidence.signature = signature_b64
        evidence.signature_algorithm = "ed25519"
        evidence.key_id = key_id
        evidence.signature_version = "ed25519-sign-v1"
        evidence.signed_at = datetime.now(timezone.utc)
        evidence.public_key_pem = public_key_pem
        db.commit()
        db.refresh(evidence)

        if evidence.custody_events is not None:
            last_event = (
                db.query(CustodyEvent)
                .filter(CustodyEvent.evidence_id == evidence.id)
                .order_by(CustodyEvent.event_index.asc(), CustodyEvent.created_at.asc())
                .all()
            )
            if last_event:
                last_event = last_event[-1]

        from app.services.custody_service import CustodyService
        CustodyService.create_event(
            db,
            evidence=evidence,
            actor_id=actor_id,
            event_type="SIGNED",
            details={
                "key_id": key_id,
                "signature_algorithm": "ed25519",
                "signature_version": "ed25519-sign-v1",
                "signed_at": evidence.signed_at.isoformat() if evidence.signed_at else None,
            },
        )

        return {
            "evidence_id": evidence.id,
            "signature_valid": True,
            "signature_algorithm": evidence.signature_algorithm,
            "key_id": evidence.key_id,
            "signature_version": evidence.signature_version,
            "signed_at": evidence.signed_at.isoformat() if evidence.signed_at else None,
            "public_key_pem": None,
            "status": "SIGNED",
        }

    @staticmethod
    def verify_signature(db: Session, *, evidence: Evidence) -> dict:
        if not evidence.sha256 or not evidence.manifest_sha256:
            return {
                "evidence_integrity": False,
                "manifest_integrity": False,
                "signature_valid": False,
                "custody_chain_valid": False,
                "overall_valid": False,
                "status": "MISSING_SEAL",
            }

        if not evidence.storage_reference:
            return {
                "evidence_integrity": False,
                "manifest_integrity": False,
                "signature_valid": False,
                "custody_chain_valid": False,
                "overall_valid": False,
                "status": "MISSING_STORAGE",
            }

        current_bytes = __import__("pathlib").Path(evidence.storage_reference).read_bytes()
        current_sha256 = hash_bytes(current_bytes)
        evidence_integrity = current_sha256 == evidence.sha256.lower()

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
            manifest_version="sha256-manifest-v1",
            extra_fields=(evidence.evidence_metadata or {}),
        )
        manifest_integrity = evidence.manifest_sha256 == hashlib.sha256(canonical_json(manifest).encode("utf-8")).hexdigest()

        signature_valid = False
        if evidence_integrity and manifest_integrity and evidence.signature and evidence.public_key_pem and evidence.signature_algorithm == "ed25519":
            try:
                public_key = serialization.load_pem_public_key(evidence.public_key_pem.encode("utf-8"))
                payload = SignatureService.build_signing_payload(evidence)
                public_key.verify(
                    base64.b64decode(evidence.signature),
                    canonical_json(payload).encode("utf-8"),
                )
                signature_valid = True
            except (ValueError, TypeError, InvalidSignature):
                signature_valid = False

        from app.services.custody_service import CustodyService
        custody_result = CustodyService.verify_chain(
            db,
            evidence_id=evidence.id,
            organization_id=evidence.organization_id,
        )

        overall_valid = evidence_integrity and manifest_integrity and signature_valid and custody_result["chain_valid"]
        return {
            "evidence_id": evidence.id,
            "evidence_integrity": evidence_integrity,
            "manifest_integrity": manifest_integrity,
            "signature_valid": signature_valid,
            "custody_chain_valid": custody_result["chain_valid"],
            "overall_valid": overall_valid,
            "key_id": evidence.key_id,
            "signature_algorithm": evidence.signature_algorithm,
            "signature_version": evidence.signature_version,
            "status": "VERIFIED" if overall_valid else "COMPROMISED",
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "custody": custody_result,
        }
