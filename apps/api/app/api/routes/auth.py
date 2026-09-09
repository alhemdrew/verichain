from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import AuthMeResponse, AuthTokenResponse, UserLoginRequest, UserPublic, UserRegisterRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthTokenResponse)
def register_user(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    try:
        user = AuthService.register_user(
            db,
            name=payload.name,
            email=payload.email,
            password=payload.password,
            organization_name=payload.organization_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    token = AuthService.create_token_for_user(user)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login", response_model=AuthTokenResponse)
def login_user(payload: UserLoginRequest, db: Session = Depends(get_db)):
    user = AuthService.authenticate_user(db, email=payload.email, password=payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = AuthService.create_token_for_user(user)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=AuthMeResponse)
def current_user(current_user: User = Depends(get_current_user)):
    user = UserPublic(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
        organization_id=current_user.organization_id,
    )
    return {"user": user}


@router.post("/logout")
def logout_user():
    # Phase 2 uses token-based auth; logout here is a no-op for the stateless prototype.
    return {"status": "logged_out"}


@router.get("/protected")
def protected_endpoint(current_user: User = Depends(get_current_user)):
    return {"status": "ok", "user_id": current_user.id}
