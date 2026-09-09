from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.evidence import Evidence
from app.models.share import EvidenceShare
from app.models.user import User
from app.services.share_service import ShareService

router = APIRouter(tags=["sharing"])


class ShareCreateRequest(BaseModel):
    recipient_user_id: int
    permissions: list[str] = Field(default_factory=lambda: ["VIEW"])
    expires_at: datetime | None = None


class ShareResponse(BaseModel):
    id: str
    evidence_id: str
    recipient_user_id: int
    created_by_user_id: int
    permissions: list[str]
    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    status: str

    class Config:
        orm_mode = True


@router.get("/evidence/{evidence_id}/shares")
def list_evidence_shares(evidence_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    if evidence.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evidence does not belong to your organization")
    shares = ShareService.list_evidence_shares(db, evidence_id)
    return [{
        "id": share.id,
        "evidence_id": share.evidence_id,
        "recipient_user_id": share.recipient_user_id,
        "created_by_user_id": share.created_by_user_id,
        "permissions": share.permissions,
        "created_at": share.created_at,
        "expires_at": share.expires_at,
        "revoked_at": share.revoked_at,
        "status": ShareService.set_share_status(share),
    } for share in shares]


@router.post("/evidence/{evidence_id}/shares", response_model=ShareResponse)
def create_evidence_share(
    evidence_id: str,
    payload: ShareCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to an organization")

    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    if evidence.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evidence does not belong to your organization")

    recipient = db.query(User).filter(User.id == payload.recipient_user_id).first()
    if recipient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient user not found")
    if recipient.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Recipient must belong to the same organization")

    if payload.expires_at is not None and payload.expires_at.tzinfo is None:
        payload.expires_at = payload.expires_at.replace(tzinfo=timezone.utc)
    if payload.expires_at is not None and payload.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Expiration must be in the future")

    permissions = ShareService.normalize_permissions(payload.permissions)
    share = EvidenceShare(
        id=f"share-{__import__('uuid').uuid4().hex}",
        evidence_id=evidence.id,
        recipient_user_id=recipient.id,
        created_by_user_id=current_user.id,
        permissions=permissions,
        expires_at=payload.expires_at,
        revoked_at=None,
        status="ACTIVE",
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    ShareService.record_audit(
        db,
        actor_id=current_user.id,
        evidence_id=evidence.id,
        share_id=share.id,
        event_type="SHARE_CREATED",
        result="SUCCESS",
        details={"recipient_user_id": recipient.id, "permissions": permissions},
    )
    return share


@router.get("/shares")
def list_shared_with_me(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    shares = ShareService.list_shares_for_recipient(db, current_user)
    result = []
    for share in shares:
        evidence = db.query(Evidence).filter(Evidence.id == share.evidence_id).first()
        result.append({
            "id": share.id,
            "evidence_id": share.evidence_id,
            "case_id": evidence.case_id if evidence else None,
            "original_filename": evidence.original_filename if evidence else None,
            "created_by_user_id": share.created_by_user_id,
            "permissions": share.permissions,
            "expires_at": share.expires_at,
            "revoked_at": share.revoked_at,
            "status": ShareService.set_share_status(share),
        })
    return result


@router.get("/shares/{share_id}")
def get_share(share_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    share = db.query(EvidenceShare).filter(EvidenceShare.id == share_id).first()
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    if share.recipient_user_id != current_user.id and share.created_by_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted to access this share")
    status_name = ShareService.set_share_status(share)
    return {
        "id": share.id,
        "evidence_id": share.evidence_id,
        "recipient_user_id": share.recipient_user_id,
        "created_by_user_id": share.created_by_user_id,
        "permissions": share.permissions,
        "created_at": share.created_at,
        "expires_at": share.expires_at,
        "revoked_at": share.revoked_at,
        "status": status_name,
    }


@router.get("/shares/{share_id}/evidence")
def get_shared_evidence(share_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    share = db.query(EvidenceShare).filter(EvidenceShare.id == share_id).first()
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    if share.recipient_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not the recipient of this share")
    evidence = ShareService.ensure_active_share(db, share, permission="VIEW")
    ShareService.record_audit(
        db,
        actor_id=current_user.id,
        evidence_id=evidence.id,
        share_id=share.id,
        event_type="SHARE_VIEWED",
        result="SUCCESS",
        details={"permissions": share.permissions},
    )
    return {
        "evidence_id": evidence.id,
        "case_id": evidence.case_id,
        "organization_id": evidence.organization_id,
        "original_filename": evidence.original_filename,
        "mime_type": evidence.mime_type,
        "file_size": evidence.file_size,
        "collection_timestamp": evidence.collection_timestamp,
        "created_by": evidence.created_by,
        "sha256": evidence.sha256,
        "manifest_sha256": evidence.manifest_sha256,
        "status": evidence.status,
        "signature": evidence.signature,
        "key_id": evidence.key_id,
        "synced": not evidence.not_synced,
    }


@router.get("/shares/{share_id}/download")
def download_shared_evidence(share_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    share = db.query(EvidenceShare).filter(EvidenceShare.id == share_id).first()
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    if share.recipient_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not the recipient of this share")
    evidence = ShareService.ensure_active_share(db, share, permission="DOWNLOAD")
    if not evidence.storage_reference:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence file is not stored")

    content = __import__("pathlib").Path(evidence.storage_reference).read_bytes()
    sha256 = __import__("hashlib").sha256(content).hexdigest()
    ShareService.record_audit(
        db,
        actor_id=current_user.id,
        evidence_id=evidence.id,
        share_id=share.id,
        event_type="EVIDENCE_DOWNLOADED",
        result="SUCCESS",
        details={"sha256": sha256},
    )
    return Response(
        content=content,
        media_type=evidence.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{evidence.original_filename}"',
            "X-VeriChain-Evidence-ID": evidence.id,
            "X-VeriChain-SHA256": sha256,
        },
    )


@router.post("/shares/{share_id}/revoke")
def revoke_share(share_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    share = db.query(EvidenceShare).filter(EvidenceShare.id == share_id).first()
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    evidence = db.query(Evidence).filter(Evidence.id == share.evidence_id).first()
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence no longer exists")
    if share.created_by_user_id != current_user.id and evidence.created_by != current_user.id and evidence.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to revoke this share")

    if share.revoked_at is None:
        share.revoked_at = datetime.now(timezone.utc)
        share.status = "REVOKED"
        db.commit()
    ShareService.record_audit(
        db,
        actor_id=current_user.id,
        evidence_id=evidence.id,
        share_id=share.id,
        event_type="SHARE_REVOKED",
        result="SUCCESS",
        details={"revoked_at": share.revoked_at.isoformat() if share.revoked_at else None},
    )
    return {
        "share_id": share.id,
        "status": "REVOKED",
        "revoked_at": share.revoked_at.isoformat() if share.revoked_at else None,
    }
