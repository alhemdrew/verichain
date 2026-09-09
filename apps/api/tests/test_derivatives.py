import hashlib

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
from app.models.derivative import EvidenceDerivative
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
        name="Derivative Case",
        description="Derivative tests",
        status="OPEN",
        organization_id=organization_id,
        created_by=created_by,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def test_authorized_owner_can_create_copy_derivative(client):
    token_owner = register_and_login(client, "Owner", "owner@deriv.com", "StrongPass123!", "Org Derivative")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token_owner}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="source.bin",
            mime_type="application/octet-stream",
            content=b"original-bytes",
            description="Original evidence",
        )
        original_sha = evidence.sha256
        original_id = evidence.id

    response = client.post(
        f"/evidence/{original_id}/derivatives",
        json={"derivation_type": "COPY", "description": "Exact copy for provenance validation"},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    derivative_id = body["derivative_evidence_id"]
    assert derivative_id != original_id
    assert body["parent_evidence_id"] == original_id
    assert body["derivation_type"] == "COPY"

    with session_module.SessionLocal() as db:
        parent = db.query(Evidence).filter(Evidence.id == original_id).one()
        derivative = db.query(Evidence).filter(Evidence.id == derivative_id).one()
        relationship = db.query(EvidenceDerivative).filter(EvidenceDerivative.derivative_evidence_id == derivative_id).one()

        assert parent.sha256 == original_sha
        assert parent.original_sha256 == original_sha
        assert relationship.parent_evidence_id == original_id
        assert derivative.sha256 == hashlib.sha256(b"original-bytes").hexdigest()
        assert derivative.manifest_sha256
        assert derivative.signature
        assert derivative.custody_events
        assert parent.custody_events


def test_view_only_share_cannot_create_derivative(client):
    token_owner = register_and_login(client, "Owner2", "owner2@deriv.com", "StrongPass123!", "Org Derivative")
    token_recipient = register_and_login(client, "Recipient2", "recipient2@deriv.com", "StrongPass123!", "Org Derivative")
    owner = client.get("/auth/me", headers={"Authorization": f"Bearer {token_owner}"}).json()["user"]
    recipient = client.get("/auth/me", headers={"Authorization": f"Bearer {token_recipient}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=owner["organization_id"], created_by=owner["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=owner["organization_id"],
            created_by=owner["id"],
            original_filename="share.bin",
            mime_type="application/octet-stream",
            content=b"shared-bytes",
        )

    share_resp = client.post(
        f"/evidence/{evidence.id}/shares",
        json={"recipient_user_id": recipient["id"], "permissions": ["VIEW"]},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    assert share_resp.status_code == 200, share_resp.text
    share_id = share_resp.json()["id"]

    derivative_resp = client.post(
        f"/evidence/{evidence.id}/derivatives",
        json={"derivation_type": "COPY", "description": "Should fail"},
        headers={"Authorization": f"Bearer {token_recipient}"},
    )
    assert derivative_resp.status_code == 403, derivative_resp.text

    with session_module.SessionLocal() as db:
        count = db.query(EvidenceDerivative).filter(EvidenceDerivative.parent_evidence_id == evidence.id).count()
        assert count == 0


def test_create_derivative_share_permission_is_required(client):
    token_owner = register_and_login(client, "Owner3", "owner3@deriv.com", "StrongPass123!", "Org Derivative")
    token_recipient = register_and_login(client, "Recipient3", "recipient3@deriv.com", "StrongPass123!", "Org Derivative")
    owner = client.get("/auth/me", headers={"Authorization": f"Bearer {token_owner}"}).json()["user"]
    recipient = client.get("/auth/me", headers={"Authorization": f"Bearer {token_recipient}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=owner["organization_id"], created_by=owner["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=owner["organization_id"],
            created_by=owner["id"],
            original_filename="shared-derivative.bin",
            mime_type="application/octet-stream",
            content=b"payload-for-shared-derivative",
        )

    share_resp = client.post(
        f"/evidence/{evidence.id}/shares",
        json={"recipient_user_id": recipient["id"], "permissions": ["VIEW", "CREATE_DERIVATIVE"]},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    assert share_resp.status_code == 200, share_resp.text

    derivative_resp = client.post(
        f"/evidence/{evidence.id}/derivatives",
        json={"derivation_type": "REDACTION", "description": "Faces blurred for privacy."},
        headers={"Authorization": f"Bearer {token_recipient}"},
    )
    assert derivative_resp.status_code == 200, derivative_resp.text
    assert derivative_resp.json()["parent_evidence_id"] == evidence.id
