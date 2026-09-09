from datetime import datetime

from pydantic import BaseModel, Field


class CaseCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    status: str = "OPEN"


class CaseUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None


class CaseResponse(BaseModel):
    id: int
    organization_id: int
    name: str
    display_number: int | None = None
    display_id: str | None = None
    description: str | None = None
    status: str
    created_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
