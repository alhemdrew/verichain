from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    # organization-scoped, incrementing human-friendly number
    display_number = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="OPEN")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="cases")
    created_by_user = relationship("User", back_populates="created_cases", foreign_keys=[created_by])
    evidence = relationship("Evidence", back_populates="case")

    @property
    def display_id(self) -> str:
        return f"CASE-{(self.display_number or 0):04d}"
