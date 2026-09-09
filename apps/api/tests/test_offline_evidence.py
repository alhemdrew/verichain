import base64
import hashlib
import uuid

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
        name="Offline Case",
        description="Created locally while offline",
        status="OPEN",
        organization_id=organization_id,
        created_by=created_by,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def test_offline_collection_creates_local_record(client):
    token = register_and_login(client, "Alice", "alice@offline.com", "StrongPass123!", "Org Offline")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]
    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="offline.bin",
            mime_type="application/octet-stream",
            content=b"offline-evidence-bytes",
            description="Created without network",
        )
        assert evidence.id
        assert evidence.status == "READY_FOR_SYNC"
        assert evidence.sync_state == "LOCAL_ONLY"
        assert evidence.not_synced is True
        assert evidence.sha256 == hashlib.sha256(b"offline-evidence-bytes").hexdigest()


def test_offline_collection_uses_uuidv4_identity_and_unique_ids(client):
    token = register_and_login(client, "Alice", "alice2@offline.com", "StrongPass123!", "Org Offline")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]
    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        ids = []
        for index in range(10):
            ev = OfflineEvidenceService.create_offline_evidence(
                db,
                case_id=case.id,
                organization_id=user["organization_id"],
                created_by=user["id"],
                original_filename=f"local-{index}.bin",
                mime_type="application/octet-stream",
                content=f"payload-{index}".encode("utf-8"),
            )
            ids.append(ev.id)
            uuid.UUID(ev.id)
        assert len(set(ids)) == len(ids)


def test_offline_seal_and_signature_are_local_and_valid(client):
    token = register_and_login(client, "Bob", "bob@offline.com", "StrongPass123!", "Org Offline")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]
    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="signed.bin",
            mime_type="application/octet-stream",
            content=b"signed-content",
        )
        verify = OfflineEvidenceService.verify_offline_evidence(db, evidence)
        assert verify["local_integrity"] is True
        assert verify["signature_valid"] is True
        assert verify["custody_valid"] is True
        assert verify["server_sync"] == "NOT_SYNCED"


def test_offline_vault_tampering_is_detected(client):
    token = register_and_login(client, "Cara", "cara@offline.com", "StrongPass123!", "Org Offline")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]
    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="vault.bin",
            mime_type="application/octet-stream",
            content=b"vault-payload",
        )
        vault_path = evidence.vault_path
        with open(vault_path, "wb") as handle:
            handle.write(b"tampered")
        verify = OfflineEvidenceService.verify_offline_evidence(db, evidence)
        assert verify["local_integrity"] is False
        assert verify["overall_valid"] is False


def test_offline_evidence_bytes_tampering_is_detected(client):
    token = register_and_login(client, "Dana", "dana@offline.com", "StrongPass123!", "Org Offline")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]
    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="bytes.bin",
            mime_type="application/octet-stream",
            content=b"exact-bytes",
        )
        path = evidence.storage_reference
        with open(path, "wb") as handle:
            handle.write(b"modified-content")
        verify = OfflineEvidenceService.verify_offline_evidence(db, evidence)
        assert verify["local_integrity"] is False
        assert verify["signature_valid"] is False


def test_offline_signed_metadata_tampering_breaks_signature(client):
    token = register_and_login(client, "Erin", "erin@offline.com", "StrongPass123!", "Org Offline")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]
    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="metadata.bin",
            mime_type="application/octet-stream",
            content=b"metadata-payload",
        )
        evidence.original_filename = "tampered-name"
        db.commit()
        verify = OfflineEvidenceService.verify_offline_evidence(db, evidence)
        assert verify["signature_valid"] is False


def test_offline_custody_tampering_breaks_chain(client):
    token = register_and_login(client, "Frank", "frank@offline.com", "StrongPass123!", "Org Offline")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]
    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="custody.bin",
            mime_type="application/octet-stream",
            content=b"custody-payload",
        )
        from app.models.custody import CustodyEvent
        event = db.query(CustodyEvent).filter(CustodyEvent.evidence_id == evidence.id).order_by(CustodyEvent.event_index.asc()).first()
        event.event_hash = "tampered"
        db.commit()
        verify = OfflineEvidenceService.verify_offline_evidence(db, evidence)
        assert verify["custody_valid"] is False


def test_offline_evidence_persists_across_restart(client):
    token = register_and_login(client, "Grace", "grace@offline.com", "StrongPass123!", "Org Offline")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]
    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="restart.bin",
            mime_type="application/octet-stream",
            content=b"persisted-bytes",
        )
        evidence_id = evidence.id

    with session_module.SessionLocal() as db:
        row = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        assert row is not None
        verify = OfflineEvidenceService.verify_offline_evidence(db, row)
        assert verify["overall_valid"] is True


def test_offline_creation_is_independent_of_network_access(client, monkeypatch):
    token = register_and_login(client, "Heidi", "heidi@offline.com", "StrongPass123!", "Org Offline")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

    def fail_network(*args, **kwargs):
        raise AssertionError("Network access should not be used for offline evidence creation")

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fail_network)

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="offline-no-network.bin",
            mime_type="application/octet-stream",
            content=b"no-network",
        )
        assert evidence.id


def test_offline_evidence_uses_local_case_reference(client):
    token = register_and_login(client, "Ivan", "ivan@offline.com", "StrongPass123!", "Org Offline")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]
    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="case-ref.bin",
            mime_type="application/octet-stream",
            content=b"local-case-ref",
            local_case_id="case-local-uuid-123",
        )
        assert evidence.local_case_id == "case-local-uuid-123"
        assert evidence.case_id == case.id
        
