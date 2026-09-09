from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IntegrityReportResponse(BaseModel):
    report_id: str
    evidence_id: str
    case_id: int
    generated_at: datetime
    verification_status: str
    evidence_metadata: dict
    cryptographic_integrity: dict
    signature_status: str
    manifest_status: str
    custody_status: str
    synchronization_status: dict
    provenance_status: str
    conclusion: str
    technical_details: dict

    class Config:
        orm_mode = True
        allow_population_by_field_name = True
