from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.user import User
from sqlalchemy import select, func


class CaseService:
    @staticmethod
    def create_case(db: Session, *, organization_id: int, name: str, description: str | None, status: str, created_by: int) -> Case:
        # compute next display_number scoped to organization to maintain human-friendly numbering
        next_number = db.query(func.coalesce(func.max(Case.display_number), 0)).filter(Case.organization_id == organization_id).scalar() or 0
        next_number = int(next_number) + 1

        case = Case(
            organization_id=organization_id,
            name=name,
            description=description,
            status=status.upper(),
            created_by=created_by,
            display_number=next_number,
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        return case

    @staticmethod
    def list_cases_for_organization(db: Session, *, organization_id: int):
        return db.query(Case).filter(Case.organization_id == organization_id).order_by(Case.created_at.desc()).all()

    @staticmethod
    def get_case_for_organization(db: Session, *, case_id: int, organization_id: int):
        return db.query(Case).filter(Case.id == case_id, Case.organization_id == organization_id).first()

    @staticmethod
    def update_case(db: Session, *, case: Case, name: str | None = None, description: str | None = None, status: str | None = None):
        if name is not None:
            case.name = name
        if description is not None:
            case.description = description
        if status is not None:
            case.status = status.upper()
        db.commit()
        db.refresh(case)
        return case
