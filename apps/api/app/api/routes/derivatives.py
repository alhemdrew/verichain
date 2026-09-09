from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.evidence import Evidence
from app.models.user import User
from app.services.derivative_service import DerivativeService

router = APIRouter(tags=["derivatives"])


class DerivativeCreateRequest(BaseModel):
    derivation_type: str = Field(default="COPY")
    description: str | None = None


@router.post("/evidence/{evidence_id}/derivatives")
def create_derivative(
    evidence_id: str,
    payload: DerivativeCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to an organization")

    original = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if original is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    if original.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evidence does not belong to your organization")

    derivative = DerivativeService.create_derivative(
        db,
        parent_evidence=original,
        current_user=current_user,
        derivation_type=payload.derivation_type,
        description=payload.description,
    )

    relationship = db.query(__import__("app.models.derivative", fromlist=["EvidenceDerivative"]).EvidenceDerivative).filter(
        __import__("app.models.derivative", fromlist=["EvidenceDerivative"]).EvidenceDerivative.derivative_evidence_id == derivative.id
    ).first()

    return {
        "parent_evidence_id": original.id,
        "derivative_evidence_id": derivative.id,
        "derivation_type": relationship.derivation_type if relationship else "COPY",
        "description": relationship.description if relationship else derivative.description,
        "sha256": derivative.sha256,
        "manifest_sha256": derivative.manifest_sha256,
        "status": derivative.status,
    }


@router.get("/evidence/{evidence_id}/derivatives")
def list_derivatives_for_evidence(
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    if evidence.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evidence does not belong to your organization")

    rows = db.query(__import__("app.models.derivative", fromlist=["EvidenceDerivative"]).EvidenceDerivative).filter(
        __import__("app.models.derivative", fromlist=["EvidenceDerivative"]).EvidenceDerivative.parent_evidence_id == evidence_id
    ).order_by(__import__("app.models.derivative", fromlist=["EvidenceDerivative"]).EvidenceDerivative.created_at.desc()).all()
    return [{
        "id": row.id,
        "parent_evidence_id": row.parent_evidence_id,
        "derivative_evidence_id": row.derivative_evidence_id,
        "derivation_type": row.derivation_type,
        "description": row.description,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    } for row in rows]


@router.get("/evidence/{evidence_id}/provenance")
def get_evidence_provenance(
    evidence_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id).first()
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    if evidence.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Evidence does not belong to your organization")

    return DerivativeService.get_provenance(db, evidence_id=evidence_id)
