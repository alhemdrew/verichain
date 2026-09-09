from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.case import Case
from app.models.user import User
from app.schemas.case import CaseCreateRequest, CaseResponse, CaseUpdateRequest
from app.services.case_service import CaseService

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseResponse)
def create_case(payload: CaseCreateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User must belong to an organization")
    case = CaseService.create_case(
        db,
        organization_id=current_user.organization_id,
        name=payload.name,
        description=payload.description,
        status=payload.status,
        created_by=current_user.id,
    )
    # include computed display_id
    return case


@router.get("", response_model=list[CaseResponse])
def list_cases(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.organization_id:
        return []
    return CaseService.list_cases_for_organization(db, organization_id=current_user.organization_id)


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(case_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to an organization")

    case = db.query(Case).filter(Case.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if case.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Case does not belong to your organization")
    return case


@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(case_id: int, payload: CaseUpdateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to an organization")

    case = db.query(Case).filter(Case.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if case.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Case does not belong to your organization")

    updated = CaseService.update_case(
        db,
        case=case,
        name=payload.name,
        description=payload.description,
        status=payload.status,
    )
    return updated
