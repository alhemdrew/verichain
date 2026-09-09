import base64
from datetime import datetime, timezone

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
from app.services.local_vault_service import LocalVaultService
from app.services.offline_evidence_service import OfflineEvidenceService
from app.services.sync_queue_service import SyncQueueService


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
        name="Offline Sync Case",
        description="Created locally while offline",
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


def test_offline_evidence_synchronizes_successfully_and_preserves_identity(client):
    token = register_and_login(client, "Sync User", "sync@example.com", "StrongPass123!", "Org Sync")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="sync.bin",
            mime_type="application/octet-stream",
            content=b"sync-payload",
        )
        payload = _sync_payload_for(evidence)

    resp = client.post("/sync/evidence", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["evidence_id"] == evidence.id
    assert body["status"] == "SYNCED"
        
    with session_module.SessionLocal() as db:
        row = db.query(Evidence).filter(Evidence.id == evidence.id).first()
        assert row is not None
        assert row.sha256 == evidence.sha256
        assert row.manifest_sha256 == evidence.manifest_sha256
        assert row.signature == evidence.signature
        assert row.key_id == evidence.key_id
        assert row.sync_state == "SYNCED"
        assert row.not_synced is False


def test_same_offline_evidence_sync_is_idempotent(client):
    token = register_and_login(client, "Idempotent", "idempotent@example.com", "StrongPass123!", "Org Sync")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="idempotent.bin",
            mime_type="application/octet-stream",
            content=b"idempotent-payload",
        )
        payload = _sync_payload_for(evidence)

    first = client.post("/sync/evidence", json=payload, headers={"Authorization": f"Bearer {token}"})
    second = client.post("/sync/evidence", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert first.status_code == 200
    assert second.status_code == 200

    with session_module.SessionLocal() as db:
        rows = db.query(Evidence).filter(Evidence.id == evidence.id).all()
        assert len(rows) == 1


def test_sync_rejects_tampered_uploaded_bytes(client):
    token = register_and_login(client, "Tamper", "tamper@example.com", "StrongPass123!", "Org Sync")
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
            content=b"tamper-me",
        )
        payload = _sync_payload_for(evidence)
        payload["content_base64"] = base64.b64encode(b"tampered-bytes").decode("utf-8")

    resp = client.post("/sync/evidence", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 400, resp.text


def test_sync_rejects_cross_organization_evidence(client):
    token_a = register_and_login(client, "OrgA", "a@example.com", "StrongPass123!", "Org A")
    token_b = register_and_login(client, "OrgB", "b@example.com", "StrongPass123!", "Org B")
    user_a = client.get("/auth/me", headers={"Authorization": f"Bearer {token_a}"}).json()["user"]
    user_b = client.get("/auth/me", headers={"Authorization": f"Bearer {token_b}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user_a["organization_id"], created_by=user_a["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user_a["organization_id"],
            created_by=user_a["id"],
            original_filename="cross.bin",
            mime_type="application/octet-stream",
            content=b"org-cross",
        )
        payload = _sync_payload_for(evidence)
        payload["organization_id"] = user_b["organization_id"]

    resp = client.post("/sync/evidence", json=payload, headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 403, resp.text


def test_sync_queue_persists_across_restart(client):
    token = register_and_login(client, "Queue", "queue@example.com", "StrongPass123!", "Org Queue")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="queue.bin",
            mime_type="application/octet-stream",
            content=b"queue-payload",
        )
        SyncQueueService.enqueue_for_sync(db, evidence)
        queue_id = evidence.id

    with session_module.SessionLocal() as db:
        item = db.query(SyncQueueService.queue_model()).filter(SyncQueueService.queue_model().evidence_id == queue_id).first()
        assert item is not None
        assert item.state == "READY_FOR_SYNC"
