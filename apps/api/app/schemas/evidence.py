from datetime import datetime

from pydantic import BaseModel, Field


class EvidenceCreateRequest(BaseModel):
    original_filename: str = Field(..., min_length=1, max_length=255)
    evidence_name: str | None = Field(default=None, min_length=1, max_length=255)
    evidence_type: str = "OTHER"
    mime_type: str | None = None
    file_size: int = 0
    collection_timestamp: datetime | None = None
    description: str | None = None
    metadata: dict | None = None
    content_base64: str | None = None


class EvidenceUpdateRequest(BaseModel):
    original_filename: str | None = Field(default=None, min_length=1, max_length=255)
    evidence_name: str | None = Field(default=None, min_length=1, max_length=255)
    evidence_type: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    collection_timestamp: datetime | None = None
    description: str | None = None
    metadata: dict | None = None
    tags: list[str] | None = None
    status: str | None = None


class EvidenceResponse(BaseModel):
    id: str
    case_id: int
    organization_id: int
    original_filename: str
    evidence_name: str | None = None
    evidence_type: str
    mime_type: str | None = None
    file_size: int
    collection_timestamp: datetime | None = None
    created_at: datetime
    updated_at: datetime
    created_by: int
    description: str | None = None
    status: str
    sync_state: str | None = None
    not_synced: bool | None = None
    local_case_id: str | None = None
    storage_reference: str | None = None
    vault_object_id: str | None = None
    vault_status: str | None = None
    vault_algorithm: str | None = None
    vault_version: str | None = None
    vault_nonce: str | None = None
    vault_path: str | None = None
    vault_created_at: datetime | None = None
    vault_updated_at: datetime | None = None
    sha256: str | None = None
    original_sha256: str | None = None
    manifest_sha256: str | None = None
    sealed_at: datetime | None = None
    seal_version: str | None = None
    signature: str | None = None
    signature_algorithm: str | None = None
    key_id: str | None = None
    signature_version: str | None = None
    signed_at: datetime | None = None
    metadata: dict | None = Field(default=None, alias="evidence_metadata")

    class Config:
        orm_mode = True
        allow_population_by_field_name = True
