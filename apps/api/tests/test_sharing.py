import base64

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
    resp = client.post(
        "/auth/register",
        json={
            "name": name,
            "email": email,
            "password": password,
            "organization_name": organization_name,
        },
    )
    assert resp.status_code == 200, resp.text
    login = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _create_local_case(db, organization_id: int, created_by: int):
    case = Case(
        name="Share Case",
        description="Share test case",
        status="OPEN",
        organization_id=organization_id,
        created_by=created_by,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def _create_evidence(db, org_id: int, actor_id: int, case_id: int, content: bytes, filename: str = "share.bin"):
    evidence = OfflineEvidenceService.create_offline_evidence(
        db,
        case_id=case_id,
        organization_id=org_id,
        created_by=actor_id,
        original_filename=filename,
        mime_type="application/octet-stream",
        content=content,
    )
    return evidence


def test_authorized_share_creation_allows_view_and_download(client):
    token_owner = register_and_login(client, "Owner", "owner@example.com", "StrongPass123!", "Org A")
    token_recipient = register_and_login(client, "Recipient", "recipient@example.com", "StrongPass123!", "Org A")
    owner_user = client.get("/auth/me", headers={"Authorization": f"Bearer {token_owner}"}).json()["user"]
    recipient_user = client.get("/auth/me", headers={"Authorization": f"Bearer {token_recipient}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=owner_user["organization_id"], created_by=owner_user["id"])
        evidence = _create_evidence(db, owner_user["organization_id"], owner_user["id"], case.id, b"shared-payload")
        evidence_id = evidence.id

    create_share = client.post(
        f"/evidence/{evidence_id}/shares",
        json={"recipient_user_id": recipient_user["id"], "permissions": ["VIEW"]},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    assert create_share.status_code == 200, create_share.text
    share = create_share.json()
    assert share["permissions"] == ["VIEW"]

    view_resp = client.get(f"/shares/{share['id']}/evidence", headers={"Authorization": f"Bearer {token_recipient}"})
    assert view_resp.status_code == 200, view_resp.text
    assert view_resp.json()["evidence_id"] == evidence_id

    no_download = client.get(f"/shares/{share['id']}/download", headers={"Authorization": f"Bearer {token_recipient}"})
    assert no_download.status_code == 403, no_download.text

    grant_download = client.post(
        f"/evidence/{evidence_id}/shares",
        json={"recipient_user_id": recipient_user["id"], "permissions": ["VIEW", "DOWNLOAD"]},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    assert grant_download.status_code == 200, grant_download.text
    share_id = grant_download.json()["id"]

    download_resp = client.get(f"/shares/{share_id}/download", headers={"Authorization": f"Bearer {token_recipient}"})
    assert download_resp.status_code == 200, download_resp.text
    assert download_resp.content == b"shared-payload"


def test_cross_organization_share_is_rejected(client):
    token_owner = register_and_login(client, "OrgA Owner", "owner2@example.com", "StrongPass123!", "Org A")
    token_other_org = register_and_login(client, "OrgB User", "other2@example.com", "StrongPass123!", "Org B")
    owner_user = client.get("/auth/me", headers={"Authorization": f"Bearer {token_owner}"}).json()["user"]
    other_user = client.get("/auth/me", headers={"Authorization": f"Bearer {token_other_org}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=owner_user["organization_id"], created_by=owner_user["id"])
        evidence = _create_evidence(db, owner_user["organization_id"], owner_user["id"], case.id, b"cross-org")
        evidence_id = evidence.id

    resp = client.post(
        f"/evidence/{evidence_id}/shares",
        json={"recipient_user_id": other_user["id"], "permissions": ["VIEW"]},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    assert resp.status_code == 403, resp.text


def test_revoked_and_expired_shares_are_denied(client):
    token_owner = register_and_login(client, "Owner3", "owner3@example.com", "StrongPass123!", "Org A")
    token_recipient = register_and_login(client, "Recipient3", "recipient3@example.com", "StrongPass123!", "Org A")
    owner_user = client.get("/auth/me", headers={"Authorization": f"Bearer {token_owner}"}).json()["user"]
    recipient_user = client.get("/auth/me", headers={"Authorization": f"Bearer {token_recipient}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=owner_user["organization_id"], created_by=owner_user["id"])
        evidence = _create_evidence(db, owner_user["organization_id"], owner_user["id"], case.id, b"expiring")
        evidence_id = evidence.id

    active_expired = client.post(
        f"/evidence/{evidence_id}/shares",
        json={"recipient_user_id": recipient_user["id"], "permissions": ["VIEW", "DOWNLOAD"]},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    assert active_expired.status_code == 200, active_expired.text
    expired_share_id = active_expired.json()["id"]

    with session_module.SessionLocal() as db:
        share = db.query(__import__("app.models.share", fromlist=["EvidenceShare"]).EvidenceShare).filter_by(id=expired_share_id).first()
        assert share is not None
        share.expires_at = __import__("datetime").datetime(2000, 1, 1, tzinfo=__import__("datetime").timezone.utc)
        db.commit()

    expired = client.get(f"/shares/{expired_share_id}/download", headers={"Authorization": f"Bearer {token_recipient}"})
    assert expired.status_code == 403, expired.text

    active = client.post(
        f"/evidence/{evidence_id}/shares",
        json={"recipient_user_id": recipient_user["id"], "permissions": ["VIEW", "DOWNLOAD"]},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    assert active.status_code == 200, active.text
    share_id = active.json()["id"]

    revoke = client.post(f"/shares/{share_id}/revoke", headers={"Authorization": f"Bearer {token_owner}"})
    assert revoke.status_code == 200, revoke.text
    after_revoke = client.get(f"/shares/{share_id}/download", headers={"Authorization": f"Bearer {token_recipient}"})
    assert after_revoke.status_code == 403, after_revoke.text


def test_invalid_permission_is_rejected(client):
    token_owner = register_and_login(client, "Owner4", "owner4@example.com", "StrongPass123!", "Org A")
    token_recipient = register_and_login(client, "Recipient4", "recipient4@example.com", "StrongPass123!", "Org A")
    owner_user = client.get("/auth/me", headers={"Authorization": f"Bearer {token_owner}"}).json()["user"]
    recipient_user = client.get("/auth/me", headers={"Authorization": f"Bearer {token_recipient}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=owner_user["organization_id"], created_by=owner_user["id"])
        evidence = _create_evidence(db, owner_user["organization_id"], owner_user["id"], case.id, b"invalid")
        evidence_id = evidence.id

    resp = client.post(
        f"/evidence/{evidence_id}/shares",
        json={"recipient_user_id": recipient_user["id"], "permissions": ["ADMIN"]},
        headers={"Authorization": f"Bearer {token_owner}"},
    )
    assert resp.status_code == 400, resp.text
