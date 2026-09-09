import hashlib
import base64

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.user import User
from app.schemas.evidence import EvidenceCreateRequest, EvidenceResponse, EvidenceUpdateRequest
from app.services.custody_service import CustodyService
from app.services.evidence_service import EvidenceService
from app.services.local_vault_service import LocalVaultService
from app.services.signature_service import SignatureService
from fastapi import UploadFile, File
import hashlib

router = APIRouter(tags=["evidence"])


@router.post("/cases/{case_id}/evidence", response_model=EvidenceResponse)
def create_evidence(
    case_id: int,
    payload: EvidenceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User must belong to an organization")

    case = db.query(Case).filter(Case.id == case_id, Case.organization_id == current_user.organization_id).first()
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    evidence = EvidenceService.create_evidence(
        db,
        case_id=case_id,
        organization_id=current_user.organization_id,
        created_by=current_user.id,
        original_filename=payload.original_filename,
        evidence_name=getattr(payload, "evidence_name", None),
        evidence_type=payload.evidence_type,
        mime_type=payload.mime_type,
        file_size=payload.file_size,
        collection_timestamp=payload.collection_timestamp,
        description=payload.description,
        metadata=payload.metadata,
        content_base64=getattr(payload, "content_base64", None),
    )
    return evidence


@router.post("/cases/{case_id}/evidence/upload", response_model=EvidenceResponse)
def upload_evidence(
    case_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept a multipart file upload and create an evidence record from raw bytes."""
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User must belong to an organization")

    case = db.query(Case).filter(Case.id == case_id, Case.organization_id == current_user.organization_id).first()
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    # Read streamed upload into memory and persist the original bytes exactly as uploaded.
    content = file.file.read()
    try:
        payload = EvidenceCreateRequest(
            original_filename=file.filename or 'uploaded-evidence',
            evidence_name=file.filename or 'uploaded-evidence',
            evidence_type='BINARY',
            mime_type=file.content_type or 'application/octet-stream',
            file_size=len(content),
            collection_timestamp=None,
            description=None,
            metadata=None,
            content_base64=base64.b64encode(content).decode(),
        )
        evidence = EvidenceService.create_evidence(
            db,
            case_id=case_id,
            organization_id=current_user.organization_id,
            created_by=current_user.id,
            original_filename=payload.original_filename,
            evidence_name=payload.evidence_name,
            evidence_type=payload.evidence_type,
            mime_type=payload.mime_type,
            file_size=payload.file_size,
            collection_timestamp=payload.collection_timestamp,
            description=payload.description,
            metadata=payload.metadata,
            content_base64=payload.content_base64,
        )
        return evidence
    finally:
        try:
            file.file.close()
        except Exception:
            pass



@router.post("/evidence/{evidence_id}/archive")
def archive_evidence(evidence_id: str, reason: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to an organization")

    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    if evidence.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evidence does not belong to your organization")

    evidence.archive(db, actor_id=current_user.id, reason=reason)
    return {"evidence_id": evidence.id, "archived": True}


@router.get("/cases/{case_id}/evidence", response_model=list[EvidenceResponse])
def list_evidence_for_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.organization_id:
        return []

    case = db.query(Case).filter(Case.id == case_id, Case.organization_id == current_user.organization_id).first()
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    return EvidenceService.list_evidence_for_case(db, case_id=case_id, organization_id=current_user.organization_id)


@router.get("/evidence/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(
    evidence_id: str,
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
    return evidence


@router.patch("/evidence/{evidence_id}", response_model=EvidenceResponse)
def update_evidence(
    evidence_id: str,
    payload: EvidenceUpdateRequest,
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

    # Only allow safe mutable metadata to be edited
    patch = payload.dict(exclude_unset=True)
    safe_keys = {"evidence_name", "description", "evidence_metadata"}
    patch = {k: v for k, v in patch.items() if k in safe_keys}
    if "evidence_name" in patch and patch["evidence_name"] is not None:
        patch["evidence_name"] = patch["evidence_name"].strip() or evidence.original_filename
    updated = EvidenceService.update_evidence(db, evidence=evidence, patch=patch)
    # record audit
    try:
        from app.models.audit import AuditEvent

        audit = AuditEvent(
            id=str(__import__("uuid").uuid4()),
            actor_id=current_user.id,
            evidence_id=evidence.id,
            event_type="EVIDENCE_METADATA_UPDATE",
            result="SUCCESS",
            details={"updated_fields": list(patch.keys())},
        )
        db.add(audit)
        db.commit()
    except Exception:
        pass
    return updated


@router.post("/evidence/{evidence_id}/seal")
def seal_evidence(
    evidence_id: str,
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

    sealed = EvidenceService.seal_evidence(db, evidence=evidence)
    return {
        "evidence_id": sealed.id,
        "sha256": sealed.sha256,
        "manifest_sha256": sealed.manifest_sha256,
        "sealed_at": sealed.sealed_at.isoformat() if sealed.sealed_at else None,
        "seal_version": sealed.seal_version,
        "status": sealed.status,
    }


@router.post("/evidence/{evidence_id}/verify")
def verify_evidence(
    evidence_id: str,
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

    result = EvidenceService.verify_evidence(evidence, db=db)
    CustodyService.create_event(
        db,
        evidence=evidence,
        actor_id=current_user.id,
        event_type="VERIFIED" if result["match"] else "VERIFICATION_FAILED",
        details={
            "match": result["match"],
            "recorded_sha256": result["recorded_sha256"],
            "current_sha256": result["current_sha256"],
            "seal_version": result["seal_version"],
            "status": result["status"],
        },
    )
    return result


@router.post("/evidence/{evidence_id}/compare")
def compare_presented_file(
    evidence_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare an uploaded (presented) file to a registered evidence's recorded SHA-256.

    This endpoint streams the upload on the server and computes SHA-256 without
    loading the entire file into memory, then returns a match result. It does
    not modify the registered evidence.
    """
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to an organization")

    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    if evidence.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evidence does not belong to your organization")

    hasher = hashlib.sha256()
    try:
        # UploadFile.file is a SpooledTemporaryFile / file-like. Read in chunks.
        chunk = file.file.read(65536)
        while chunk:
            hasher.update(chunk)
            chunk = file.file.read(65536)
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    presented_sha = hasher.hexdigest()
    recorded_sha = (evidence.sha256 or evidence.original_sha256 or "").lower()
    match = presented_sha.lower() == recorded_sha.lower() if recorded_sha else False

    # Record custody event for presented verification attempt
    CustodyService.create_event(
        db,
        evidence=evidence,
        actor_id=current_user.id,
        event_type="PRESENTED_VERIFIED" if match else "PRESENTED_VERIFICATION_FAILED",
        details={
            "presented_filename": getattr(file, "filename", None),
            "presented_sha256": presented_sha,
            "recorded_sha256": recorded_sha,
            "match": match,
        },
    )

    return {
        "evidence_id": evidence.id,
        "presented_filename": getattr(file, "filename", None),
        "presented_sha256": presented_sha,
        "recorded_sha256": recorded_sha,
        "match": match,
        "status": "VERIFIED MATCH" if match else "NO MATCH",
    }


@router.post("/evidence/{evidence_id}/sign")
def sign_evidence(
    evidence_id: str,
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

    try:
        result = SignatureService.sign_evidence(db, evidence=evidence, actor_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return result


@router.post("/evidence/{evidence_id}/ensure-signed")
def ensure_signed(
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ensure an evidence item is sealed and signed. Best-effort: will create a manifest (seal)
    if missing and then sign using the server keypair. Returns signature metadata on success.
    """
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to an organization")

    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    if evidence.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evidence does not belong to your organization")

    # Ensure sealed
    try:
        if not evidence.manifest_sha256 or not evidence.sealed_at:
            EvidenceService.seal_evidence(db, evidence=evidence)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to seal evidence: {exc}") from exc

    # Ensure signed
    try:
        result = SignatureService.sign_evidence(db, evidence=evidence, actor_id=current_user.id)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc



@router.post("/evidence/{evidence_id}/verify-signature")
def verify_signature(
    evidence_id: str,
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

    result = SignatureService.verify_signature(db, evidence=evidence)
    return result


@router.post("/evidence/{evidence_id}/vault/store")
def store_evidence_in_local_vault(
    evidence_id: str,
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

    try:
        plaintext = EvidenceService.get_file_bytes(evidence)
        result = LocalVaultService.store_evidence(db, evidence, plaintext=plaintext)
        return {
            "evidence_id": evidence.id,
            "vault_object_id": result["vault_object_id"],
            "vault_path": result["vault_path"],
            "vault_status": result["vault_status"],
            "original_sha256": result["original_sha256"],
            "status": "LOCAL_VAULT_STORED",
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/evidence/{evidence_id}/vault/retrieve")
def retrieve_evidence_from_local_vault(
    evidence_id: str,
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

    try:
        plaintext = LocalVaultService.retrieve_evidence(evidence)
        return {
            "evidence_id": evidence.id,
            "vault_status": evidence.vault_status or "LOCAL_ONLY",
            "sha256": hashlib.sha256(plaintext).hexdigest(),
            "status": "LOCAL_VAULT_RETRIEVED",
            "original_bytes_preserved": hashlib.sha256(plaintext).hexdigest() == (evidence.sha256 or evidence.original_sha256 or "").lower(),
        }
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/evidence/{evidence_id}/custody")
def list_evidence_custody(
    evidence_id: str,
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

    events = CustodyService.get_events_for_evidence(db, evidence_id=evidence.id, organization_id=current_user.organization_id)
    return [
        {
            "id": event.id,
            "evidence_id": event.evidence_id,
            "organization_id": event.organization_id,
            "actor_id": event.actor_id,
            "event_type": event.event_type,
            "event_timestamp": event.event_timestamp.isoformat() if event.event_timestamp else None,
            "details": event.details or {},
            "previous_event_hash": event.previous_event_hash,
            "event_hash": event.event_hash,
            "event_version": event.event_version,
            "event_index": event.event_index,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
        for event in events
    ]


@router.get("/evidence/{evidence_id}/file")
def get_evidence_file(
    evidence_id: str,
    download: bool | None = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the stored evidence file bytes for preview or download.

    Query param `download=true` will set a Content-Disposition attachment header.
    """
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to an organization")

    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    if evidence.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evidence does not belong to your organization")

    try:
        content = EvidenceService.get_file_bytes(evidence)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence file not found on disk")

    headers = {}
    if download:
        filename = evidence.original_filename or f"evidence-{evidence.id}"
        safe_name = filename.replace('\\', '_').replace('/', '_')
        ascii_name = ''.join(ch if ch.isalnum() or ch in "._- " else '_' for ch in safe_name)
        headers["Content-Disposition"] = f'attachment; filename="{ascii_name}"'
        if ascii_name != filename:
            from urllib.parse import quote
            headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"

    media_type = evidence.mime_type or "application/octet-stream"
    return Response(content=content, media_type=media_type, headers=headers)


@router.post("/evidence/{evidence_id}/custody/verify")
def verify_evidence_custody(
    evidence_id: str,
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

    return CustodyService.verify_chain(db, evidence_id=evidence.id, organization_id=current_user.organization_id)
