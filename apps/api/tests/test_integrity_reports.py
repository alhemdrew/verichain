from pathlib import Path

import app.db.session as session_module
from app.db.session import Base, get_db
from app.main import app
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.user import User
from app.services.derivative_service import DerivativeService
from app.services.offline_evidence_service import OfflineEvidenceService
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


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
        name="Report Case",
        description="Integrity report tests",
        status="OPEN",
        organization_id=organization_id,
        created_by=created_by,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def _client_fixture():
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
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    session_module.SessionLocal = original_session_local


def test_generates_integrity_report_for_valid_evidence():
    client = next(_client_fixture())
    token = register_and_login(client, "ReportOwner", "reportowner@test.com", "StrongPass123!", "Org Report")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="report-ready.bin",
            mime_type="application/octet-stream",
            content=b"report-ready-content",
            description="Ready for reporting",
        )
        evidence_id = evidence.id
        before_hash = evidence.sha256
        before_manifest = evidence.manifest_sha256
        before_signature = evidence.signature
        before_event_count = len(evidence.custody_events)

    response = client.get(f"/evidence/{evidence_id}/integrity-report", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["evidence_id"] == evidence_id
    assert body["verification_status"] == "VERIFIED"
    assert body["cryptographic_integrity"]["sha256_status"] == "verified"
    assert body["manifest_status"] == "verified"
    assert body["signature_status"] == "verified"
    assert body["custody_status"] == "verified"
    assert "Integrity Verified" in body["conclusion"]

    with session_module.SessionLocal() as db:
        row = db.query(Evidence).filter(Evidence.id == evidence_id).one()
        assert row.sha256 == before_hash
        assert row.manifest_sha256 == before_manifest
        assert row.signature == before_signature
        assert len(row.custody_events) == before_event_count


def test_integrity_report_detects_tampered_evidence():
    client = next(_client_fixture())
    token = register_and_login(client, "TamperUser", "tamper@test.com", "StrongPass123!", "Org Tamper")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="tampered.bin",
            mime_type="application/octet-stream",
            content=b"original-bytes",
            description="Will be altered",
        )
        evidence_id = evidence.id
        before_sha = evidence.sha256
        storage_path = Path(evidence.storage_reference)
        storage_path.write_bytes(b"tampered-bytes")

    response = client.get(f"/evidence/{evidence_id}/integrity-report", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verification_status"] == "FAILED"
    assert body["cryptographic_integrity"]["sha256_status"] == "failed"
    assert body["signature_status"] in {"failed", "unavailable"}
    assert "Integrity Verification Failed" in body["conclusion"]

    with session_module.SessionLocal() as db:
        row = db.query(Evidence).filter(Evidence.id == evidence_id).one()
        assert row.sha256 == before_sha
        assert row.manifest_sha256 is not None
        assert row.signature is not None


def test_integrity_report_exposes_derivative_provenance_without_mutating_original():
    client = next(_client_fixture())
    token = register_and_login(client, "DerivativeOwner", "derivativeowner@test.com", "StrongPass123!", "Org Derivative Report")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        parent = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="provenance-source.bin",
            mime_type="application/octet-stream",
            content=b"evidence-with-provenance",
            description="Original with provenance",
        )
        persisted_user = db.query(User).filter(User.id == user["id"]).one()
        derivative = DerivativeService.create_derivative(
            db,
            parent_evidence=parent,
            current_user=persisted_user,
            derivation_type="COPY",
            description="Exact copy for report",
        )
        original_id = parent.id
        derivative_id = derivative.id
        original_sha = parent.sha256
        original_manifest = parent.manifest_sha256

    original_report = client.get(f"/evidence/{original_id}/integrity-report", headers={"Authorization": f"Bearer {token}"})
    assert original_report.status_code == 200, original_report.text
    original_body = original_report.json()
    assert original_body["evidence_id"] == original_id
    assert original_body["verification_status"] == "VERIFIED"
    assert original_body["provenance_status"] == "verified"
    assert original_body["evidence_metadata"]["derivative_count"] >= 1

    derivative_report = client.get(f"/evidence/{derivative_id}/integrity-report", headers={"Authorization": f"Bearer {token}"})
    assert derivative_report.status_code == 200, derivative_report.text
    derivative_body = derivative_report.json()
    assert derivative_body["evidence_id"] == derivative_id
    assert derivative_body["provenance_status"] == "verified"
    assert derivative_body["technical_details"]["provenance"]["parent_evidence_id"] == original_id

    with session_module.SessionLocal() as db:
        row = db.query(Evidence).filter(Evidence.id == original_id).one()
        assert row.sha256 == original_sha
        assert row.manifest_sha256 == original_manifest


def test_integrity_report_requires_same_organization_access():
    client = next(_client_fixture())
    token_a = register_and_login(client, "OrgA", "orga@test.com", "StrongPass123!", "Org A")
    token_b = register_and_login(client, "OrgB", "orgb@test.com", "StrongPass123!", "Org B")
    user_a = client.get("/auth/me", headers={"Authorization": f"Bearer {token_a}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user_a["organization_id"], created_by=user_a["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user_a["organization_id"],
            created_by=user_a["id"],
            original_filename="private.bin",
            mime_type="application/octet-stream",
            content=b"private-content",
        )
        evidence_id = evidence.id

    response = client.get(f"/evidence/{evidence_id}/integrity-report", headers={"Authorization": f"Bearer {token_b}"})
    assert response.status_code == 403, response.text
