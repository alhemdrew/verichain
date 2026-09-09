import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.session as session_module
from app.db.session import Base, get_db
from app.main import app
from app.models.case import Case
from app.models.evidence import Evidence
from app.services.derivative_service import DerivativeService
from app.services.local_vault_service import LocalVaultService
from app.services.offline_evidence_service import OfflineEvidenceService


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    original_session_local = session_module.SessionLocal
    session_module.SessionLocal = TestingSessionLocal

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    session_module.SessionLocal = original_session_local


def register_and_login(client, name, email, password, organization_name):
    register_resp = client.post(
        "/auth/register",
        json={
            "name": name,
            "email": email,
            "password": password,
            "organization_name": organization_name,
        },
    )
    assert register_resp.status_code == 200, register_resp.text
    login_resp = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200, login_resp.text
    return login_resp.json()["access_token"]


def _create_local_case(db, organization_id: int, created_by: int):
    case = Case(
        name="Evidence Lifecycle Case",
        description="MVP evidence lifecycle",
        status="OPEN",
        organization_id=organization_id,
        created_by=created_by,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def _sync_payload_for(evidence: Evidence):
    original_bytes = LocalVaultService.retrieve_evidence(evidence)
    return {
        "evidence_id": evidence.id,
        "case_id": evidence.case_id,
        "organization_id": evidence.organization_id,
        "original_filename": evidence.original_filename,
        "mime_type": evidence.mime_type,
        "file_size": evidence.file_size,
        "collection_timestamp": evidence.collection_timestamp.isoformat() if evidence.collection_timestamp else None,
        "created_by": evidence.created_by,
        "description": evidence.description,
        "content_base64": base64.b64encode(original_bytes).decode("utf-8"),
        "sha256": evidence.sha256,
        "original_sha256": evidence.original_sha256,
        "manifest_sha256": evidence.manifest_sha256,
        "signature": evidence.signature,
        "signature_algorithm": evidence.signature_algorithm,
        "key_id": evidence.key_id,
        "signature_version": evidence.signature_version,
        "public_key_pem": evidence.public_key_pem,
        "local_case_id": evidence.local_case_id,
        "evidence_metadata": evidence.evidence_metadata,
    }


def test_phase11_end_to_end_evidence_lifecycle(client):
    token_owner = register_and_login(client, "Owner", "owner@phase11.com", "StrongPass123!", "Org Phase11")
    token_recipient = register_and_login(client, "Recipient", "recipient@phase11.com", "StrongPass123!", "Org Phase11")
    owner = client.get("/auth/me", headers={"Authorization": f"Bearer {token_owner}"}).json()["user"]
    recipient = client.get("/auth/me", headers={"Authorization": f"Bearer {token_recipient}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=owner["organization_id"], created_by=owner["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=owner["organization_id"],
            created_by=owner["id"],
            original_filename="phase11-evidence.bin",
            mime_type="application/octet-stream",
            content=b"phase11-evidence-payload",
            description="Original case evidence",
        )
        evidence_id = evidence.id
        original_bytes = evidence.storage_reference and Path(evidence.storage_reference).read_bytes()
        original_hash = evidence.sha256
        original_manifest = evidence.manifest_sha256
        original_signature = evidence.signature
        original_provenance = evidence.evidence_metadata
        original_custody_count = len(evidence.custody_events)

    verify_before = client.get(f"/evidence/{evidence_id}/integrity-report", headers={"Authorization": f"Bearer {token_owner}"})
    assert verify_before.status_code == 200, verify_before.text
    assert verify_before.json()["verification_status"] == "VERIFIED"

    payload = None
    with session_module.SessionLocal() as db:
        row = db.query(Evidence).filter(Evidence.id == evidence_id).one()
        payload = _sync_payload_for(row)

    sync_resp = client.post("/sync/evidence", json=payload, headers={"Authorization": f"Bearer {token_owner}"})
    assert sync_resp.status_code == 200, sync_resp.text
    assert sync_resp.json()["status"] == "SYNCED"

    share_resp = client.post(
        f"/evidence/{evidence_id}/shares",
        json={"recipient_user_id": recipient["id"], "permissions": ["VIEW", "DOWNLOAD", "CREATE_DERIVATIVE"]},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    assert share_resp.status_code == 200, share_resp.text
    share_id = share_resp.json()["id"]

    shared_view = client.get(f"/shares/{share_id}/evidence", headers={"Authorization": f"Bearer {token_recipient}"})
    assert shared_view.status_code == 200, shared_view.text
    assert shared_view.json()["evidence_id"] == evidence_id

    with session_module.SessionLocal() as db:
        owner_row = db.query(Evidence).filter(Evidence.id == evidence_id).one()
        derivative = DerivativeService.create_derivative(
            db,
            parent_evidence=owner_row,
            current_user=recipient,
            derivation_type="COPY",
            description="Derivative for MVP workflow",
        )
        derivative_id = derivative.id

    provenance_resp = client.get(f"/evidence/{derivative_id}/provenance", headers={"Authorization": f"Bearer {token_owner}"})
    assert provenance_resp.status_code == 200, provenance_resp.text
    assert provenance_resp.json()["parent"]["evidence_id"] == evidence_id

    report_resp = client.get(f"/evidence/{evidence_id}/integrity-report", headers={"Authorization": f"Bearer {token_owner}"})
    assert report_resp.status_code == 200, report_resp.text
    report = report_resp.json()
    assert report["evidence_id"] == evidence_id
    assert report["verification_status"] == "VERIFIED"
    assert report["manifest_status"] == "verified"
    assert report["signature_status"] == "verified"
    assert report["custody_status"] in {"verified", "failed"}
    assert "Integrity Verified" in report["conclusion"]

    with session_module.SessionLocal() as db:
        final_row = db.query(Evidence).filter(Evidence.id == evidence_id).one()
        assert final_row.id == evidence_id
        assert final_row.sha256 == original_hash
        assert final_row.manifest_sha256 == original_manifest
        assert final_row.signature == original_signature
        assert final_row.evidence_metadata == original_provenance
        assert len(final_row.custody_events) >= original_custody_count

    assert original_bytes == Path(final_row.storage_reference).read_bytes()


def test_phase11_detects_integrity_failure_for_tampered_evidence(client):
    token = register_and_login(client, "Verifier", "verifier@phase11.com", "StrongPass123!", "Org Phase11")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="tampered-phase11.bin",
            mime_type="application/octet-stream",
            content=b"before-tamper",
            description="Evidence to tamper",
        )
        evidence_id = evidence.id
        Path(evidence.storage_reference).write_bytes(b"after-tamper")

    response = client.get(f"/evidence/{evidence_id}/integrity-report", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verification_status"] == "FAILED"
    assert body["cryptographic_integrity"]["sha256_status"] == "failed"
    assert "Integrity Verification Failed" in body["conclusion"]
