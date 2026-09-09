from sqlalchemy.orm import Session

from app.models.user import Organization, User
from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_access_token
import hashlib
import secrets


class AuthService:
    @staticmethod
    def register_user(db: Session, *, name: str, email: str, password: str, organization_name: str | None = None):
        existing = db.query(User).filter(User.email == email.lower()).first()
        if existing:
            raise ValueError("User already exists")

        org = None
        if organization_name:
            org = db.query(Organization).filter(Organization.name == organization_name).first()
            if org is None:
                org = Organization(name=organization_name)
                db.add(org)
                db.flush()

        # generate stable investigator id
        investigator_id = f"INV-{hashlib.sha1(email.lower().encode()).hexdigest()[:6].upper()}"
        # ensure uniqueness by appending random suffix if collision
        existing_inv = db.query(User).filter(User.investigator_id == investigator_id).first()
        if existing_inv:
            investigator_id = f"INV-{secrets.token_hex(3).upper()}"

        user = User(
            name=name,
            email=email.lower(),
            password_hash=hash_password(password),
            role="investigator",
            status="active",
            organization_id=org.id if org else None,
            investigator_id=investigator_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def authenticate_user(db: Session, *, email: str, password: str):
        user = db.query(User).filter(User.email == email.lower()).first()
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    def create_token_for_user(user: User) -> str:
        return create_access_token(str(user.id))
