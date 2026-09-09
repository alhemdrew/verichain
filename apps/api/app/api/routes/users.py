from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import AuthService
from pydantic import BaseModel
from fastapi import Body

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/search")
def search_users_by_email(
    email: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not assigned to an organization")

    normalized = email.strip().lower()
    users = (
        db.query(User)
        .filter(User.organization_id == current_user.organization_id)
        .filter(User.email.ilike(f"%{normalized}%"))
        .order_by(User.email.asc())
        .all()
    )

    return [
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "organization_id": user.organization_id,
            "status": user.status,
        }
        for user in users
    ]


class ProfileUpdate(BaseModel):
    handle: str | None = None


@router.get("/me")
def get_profile(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "organization_id": current_user.organization_id,
        "investigator_id": current_user.investigator_id,
        "handle": current_user.handle,
        "role": current_user.role,
    }


@router.patch("/me")
def update_profile(payload: ProfileUpdate = Body(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # allow setting handle only; must be unique within organization
    if payload.handle is not None:
        candidate = payload.handle.strip()
        if not candidate:
            raise HTTPException(status_code=400, detail="Handle must not be empty")
        existing = db.query(User).filter(User.organization_id == current_user.organization_id, User.handle == candidate).first()
        if existing and existing.id != current_user.id:
            raise HTTPException(status_code=400, detail="Handle already in use")
        current_user.handle = candidate
        db.add(current_user)
        db.commit()
        db.refresh(current_user)
    return {
        "investigator_id": current_user.investigator_id,
        "handle": current_user.handle,
    }
