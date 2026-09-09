from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.evidence import Evidence
from app.models.share import EvidenceShare
from app.models.user import User

ALLOWED_PERMISSIONS = {"VIEW", "DOWNLOAD", "CREATE_DERIVATIVE"}


class ShareService:
    @staticmethod
    def normalize_permissions(raw_permissions: Any) -> list[str]:
        if raw_permissions is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permissions are required")
        if not isinstance(raw_permissions, list):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permissions must be a list")

        normalized = []
        for item in raw_permissions:
            if not isinstance(item, str):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permissions must be strings")
            value = item.strip().upper()
            if value not in ALLOWED_PERMISSIONS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported permission: {item}")
            if value not in normalized:
                normalized.append(value)

        if not normalized:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one permission is required")

        if "DOWNLOAD" in normalized and "VIEW" not in normalized:
            normalized.insert(0, "VIEW")
        return normalized

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def set_share_status(share: EvidenceShare) -> str:
        now = ShareService._now()
        revoked_at = ShareService._normalize_datetime(share.revoked_at)
        expires_at = ShareService._normalize_datetime(share.expires_at)
        if revoked_at is not None:
            share.revoked_at = revoked_at
            share.status = "REVOKED"
            return share.status
        if expires_at is not None and expires_at <= now:
            share.expires_at = expires_at
            share.status = "EXPIRED"
            return share.status
        if expires_at is not None:
            share.expires_at = expires_at
        share.status = "ACTIVE"
        return share.status

    @staticmethod
    def record_audit(
        db: Session,
        *,
        actor_id: int,
        evidence_id: str,
        share_id: str | None,
        event_type: str,
        result: str,
        details: dict | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=str(uuid.uuid4()),
            actor_id=actor_id,
            evidence_id=evidence_id,
            share_id=share_id,
            event_type=event_type,
            result=result,
            details=details or {},
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def ensure_active_share(db: Session, share: EvidenceShare, *, permission: str) -> Evidence:
        status_name = ShareService.set_share_status(share)
        if status_name != "ACTIVE":
            if status_name == "REVOKED":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Share has been revoked")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Share has expired")

        if permission not in share.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission missing: {permission}")

        evidence = db.query(Evidence).filter(Evidence.id == share.evidence_id).first()
        if evidence is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence no longer exists")
        return evidence

    @staticmethod
    def list_shares_for_recipient(db: Session, current_user: User):
        return (
            db.query(EvidenceShare)
            .filter(EvidenceShare.recipient_user_id == current_user.id)
            .order_by(EvidenceShare.created_at.desc())
            .all()
        )

    @staticmethod
    def list_evidence_shares(db: Session, evidence_id: str):
        return (
            db.query(EvidenceShare)
            .filter(EvidenceShare.evidence_id == evidence_id)
            .order_by(EvidenceShare.created_at.desc())
            .all()
        )
