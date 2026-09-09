from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.derivative import EvidenceDerivative
from app.models.evidence import Evidence
from app.security.crypto import build_manifest, canonical_json, hash_bytes, manifest_hash
from app.services.custody_service import CustodyService
from app.services.evidence_service import EvidenceService
from app.services.signature_service import SignatureService


class IntegrityReportService:
    @staticmethod
    def _safe_status_key(value: bool | None) -> str:
        if value is True:
            return "verified"
        if value is False:
            return "failed"
        return "unavailable"

    @staticmethod
    def _normalize_verification_status(*statuses: str) -> str:
        relevant = [status for status in statuses if status not in ("", None, "not_applicable")]
        if any(status == "failed" for status in relevant):
            return "FAILED"
        if relevant and all(status == "verified" for status in relevant):
            return "VERIFIED"
        if relevant and any(status == "unavailable" for status in relevant):
            return "INCOMPLETE"
        if not relevant:
            return "NOT AVAILABLE"
        return "INCOMPLETE"

    @staticmethod
    def resolve_verification_state(*statuses: str) -> tuple[str, str]:
        normalized = IntegrityReportService._normalize_verification_status(*statuses)
        if normalized == "VERIFIED":
            return "VERIFIED", "All available integrity checks passed and no required verification inputs failed."
        if normalized == "FAILED":
            return "FAILED", "One or more required integrity checks did not pass, so the evidence is not considered verified."
        if normalized == "INCOMPLETE":
            return "INCOMPLETE", "Some verification inputs were unavailable or incomplete, so VeriChain cannot make a full positive integrity claim."
        return "NOT AVAILABLE", "The required verification artifacts were not available at report generation time."

    @staticmethod
    def _provenance_rows(db: Session, evidence: Evidence):
        parent_link = db.query(EvidenceDerivative).filter(EvidenceDerivative.derivative_evidence_id == evidence.id).first()
        child_links = db.query(EvidenceDerivative).filter(EvidenceDerivative.parent_evidence_id == evidence.id).all()
        parent = None
        if parent_link is not None:
            parent = db.query(Evidence).filter(Evidence.id == parent_link.parent_evidence_id).first()
        children = []
        for row in child_links:
            child = db.query(Evidence).filter(Evidence.id == row.derivative_evidence_id).first()
            if child is not None:
                children.append({
                    "id": child.id,
                    "original_filename": child.original_filename,
                    "sha256": child.sha256,
                    "derivation_type": row.derivation_type,
                    "description": row.description,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                })
        return parent, children

    @staticmethod
    def _evidence_metadata(db: Session, evidence: Evidence) -> dict:
        parent, children = IntegrityReportService._provenance_rows(db, evidence)
        return {
            "evidence_id": evidence.id,
            "case_id": evidence.case_id,
            "organization_id": evidence.organization_id,
            "evidence_name": evidence.evidence_name or evidence.original_filename,
            "original_filename": evidence.original_filename,
            "mime_type": evidence.mime_type,
            "file_size": evidence.file_size,
            "collection_timestamp": evidence.collection_timestamp.isoformat() if evidence.collection_timestamp else None,
            "created_by": evidence.created_by,
            "evidence_status": evidence.status,
            "sync_state": evidence.sync_state,
            "not_synced": evidence.not_synced,
            "is_derivative": bool(parent or evidence.evidence_metadata and evidence.evidence_metadata.get("is_derivative")),
            "parent_evidence_id": parent.id if parent else None,
            "derivative_count": len(children),
            "children": children,
        }

    @staticmethod
    def _manifest_for_evidence(evidence: Evidence) -> dict:
        provenance = evidence.evidence_metadata or {}
        filtered = {}
        if provenance:
            provenance_keys = {"is_derivative", "parent_evidence_id", "parent_case_id", "parent_organization_id", "derivation_type", "description", "created_at"}
            filtered = {key: value for key, value in provenance.items() if key in provenance_keys}
        return build_manifest(
            evidence_id=evidence.id,
            case_id=evidence.case_id,
            organization_id=evidence.organization_id,
            original_filename=evidence.original_filename,
            mime_type=evidence.mime_type,
            file_size=evidence.file_size,
            collection_timestamp=evidence.collection_timestamp.isoformat() if evidence.collection_timestamp else None,
            collector_id=evidence.created_by,
            sha256=evidence.sha256 or evidence.original_sha256 or "",
            extra_fields=filtered,
        )

    @staticmethod
    def verify_integrity(db: Session, evidence: Evidence) -> dict:
        sha_status = "unavailable"
        manifest_status = "unavailable"
        signature_status = "unavailable"
        custody_status = "unavailable"
        provenance_status = "not_applicable"
        sync_status = evidence.sync_state or "UNKNOWN"
        file_verified = False

        if evidence.storage_reference:
            try:
                current_bytes = EvidenceService.get_file_bytes(evidence)
                recorded_sha = evidence.sha256 or evidence.original_sha256
                file_verified = recorded_sha is not None and hash_bytes(current_bytes).lower() == recorded_sha.lower()
                sha_status = "verified" if file_verified else "failed"
            except FileNotFoundError:
                sha_status = "unavailable"

        if evidence.manifest_sha256:
            computed_manifest = manifest_hash(IntegrityReportService._manifest_for_evidence(evidence))
            manifest_status = "verified" if evidence.manifest_sha256.lower() == computed_manifest.lower() else "failed"
        elif evidence.sha256 or evidence.original_sha256:
            manifest_status = "unavailable"

        signature_info = SignatureService.verify_signature(db, evidence=evidence)
        if evidence.signature and evidence.public_key_pem and evidence.signature_algorithm == "ed25519":
            signature_status = "verified" if bool(signature_info.get("signature_valid")) else "failed"
        elif evidence.signature is None:
            signature_status = "unavailable"

        custody_result = CustodyService.verify_chain(db, evidence_id=evidence.id, organization_id=evidence.organization_id)
        if custody_result.get("chain_valid") is True:
            custody_status = "verified"
        elif custody_result.get("chain_valid") is False:
            custody_status = "failed"

        parent_link = db.query(EvidenceDerivative).filter(EvidenceDerivative.derivative_evidence_id == evidence.id).first()
        child_links = db.query(EvidenceDerivative).filter(EvidenceDerivative.parent_evidence_id == evidence.id).all()
        if parent_link or child_links:
            provenance_status = "verified" if parent_link or child_links else "unavailable"
        elif evidence.evidence_metadata and evidence.evidence_metadata.get("is_derivative"):
            provenance_status = "verified"

        verification_status = IntegrityReportService._normalize_verification_status(sha_status, manifest_status, signature_status, custody_status)
        verification_state, state_reason = IntegrityReportService.resolve_verification_state(sha_status, manifest_status, signature_status, custody_status)

        if verification_state == "VERIFIED":
            conclusion = "Integrity Verified: VeriChain verified that the evidence bytes examined are consistent with the cryptographic records created at preservation time. The associated manifest, signature, and custody chain also passed verification. This integrity assessment does not establish that the underlying event represented by the evidence actually occurred."
        elif verification_state == "FAILED":
            conclusion = "Integrity Verification Failed: VeriChain detected a failure in one or more required integrity checks. The report therefore does not support a positive verification claim for the current evidence state."
        elif verification_state == "INCOMPLETE":
            conclusion = "Integrity Verification Incomplete: VeriChain could not complete the full integrity assessment because one or more required verification inputs were unavailable or incomplete. This report therefore makes no positive claim that the evidence is currently unchanged."
        else:
            conclusion = "Integrity Verification Unavailable: No verification artifact was available at report-generation time. VeriChain therefore cannot establish a current cryptographic integrity result for this evidence."

        serialized_children = []
        for child in child_links:
            serialized_children.append({
                "id": child.id,
                "parent_evidence_id": child.parent_evidence_id,
                "derivative_evidence_id": child.derivative_evidence_id,
                "derivation_type": child.derivation_type,
                "description": child.description,
                "created_at": child.created_at.isoformat() if child.created_at else None,
            })

        technical_details = {
            "hash_algorithm": "SHA-256",
            "hash": evidence.sha256 or evidence.original_sha256,
            "manifest_information": {
                "manifest_hash": evidence.manifest_sha256,
                "manifest_version": "sha256-manifest-v1",
                "manifest_valid": manifest_status == "verified",
            },
            "signature_algorithm": evidence.signature_algorithm or "ed25519",
            "signature_verification_result": signature_info,
            "provenance": {
                "parent_evidence_id": parent_link.parent_evidence_id if parent_link else None,
                "derivation_type": parent_link.derivation_type if parent_link else (evidence.evidence_metadata or {}).get("derivation_type"),
                "children": serialized_children,
            },
            "custody_chain_verification_result": custody_result,
            "verification_timestamp": datetime.now(timezone.utc).isoformat(),
            "evidence_id": evidence.id,
            "case_id": evidence.case_id,
            "organization_id": evidence.organization_id,
            "key_id": evidence.key_id,
        }

        current_sha256 = None
        if evidence.storage_reference:
            try:
                current_sha256 = hash_bytes(EvidenceService.get_file_bytes(evidence))
            except FileNotFoundError:
                current_sha256 = None

        return {
            "report_id": str(uuid.uuid4()),
            "evidence_id": evidence.id,
            "case_id": evidence.case_id,
            "generated_at": datetime.now(timezone.utc),
            "verification_status": verification_status,
            "verification_state": verification_state,
            "state_reason": state_reason,
            "evidence_metadata": IntegrityReportService._evidence_metadata(db, evidence),
            # expose explicit sealed/signed/manifest info for report consumers
            "sealed": bool(evidence.sealed_at),
            "sealed_at": evidence.sealed_at.isoformat() if evidence.sealed_at else None,
            "signed": bool(evidence.signature),
            "signed_at": evidence.signed_at.isoformat() if evidence.signed_at else None,
            "manifest_hash": evidence.manifest_sha256,
            "cryptographic_integrity": {
                "sha256_status": sha_status,
                "sha256": evidence.sha256 or evidence.original_sha256,
                "recorded_sha256": evidence.sha256 or evidence.original_sha256,
                "current_sha256": current_sha256,
                "hash_algorithm": "SHA-256",
                "verification_result": file_verified,
            },
            "signature_status": signature_status,
            "manifest_status": manifest_status,
            "custody_status": custody_status,
            "synchronization_status": {
                "state": sync_status,
                "not_synced": bool(evidence.not_synced),
                "status": sync_status,
            },
            "provenance_status": provenance_status,
            "conclusion": conclusion,
            "technical_details": technical_details,
        }

    @staticmethod
    def generate_report(db: Session, evidence: Evidence) -> dict:
        result = IntegrityReportService.verify_integrity(db, evidence)
        return result
