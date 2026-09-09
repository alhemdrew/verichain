import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.session as session_module
from app.db.session import Base, get_db
from app.main import app
from app.models.case import Case
from app.models.sync_queue import SyncQueueEntry
from app.services.offline_evidence_service import OfflineEvidenceService
from app.services.sync_queue_service import SyncQueueService
from app.services.sync_worker_service import SyncWorkerService


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
    yield
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
        name="Worker Case",
        description="Queue worker case",
        status="OPEN",
        organization_id=organization_id,
        created_by=created_by,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def test_worker_discovers_ready_for_sync_and_marks_synced(client, monkeypatch):
    with TestClient(app) as c:
        token = register_and_login(c, "Worker One", "worker1@example.com", "StrongPass123!", "Org Worker")
        user = c.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

        with session_module.SessionLocal() as db:
            case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
            evidence = OfflineEvidenceService.create_offline_evidence(
                db,
                case_id=case.id,
                organization_id=user["organization_id"],
                created_by=user["id"],
                original_filename="worker.bin",
                mime_type="application/octet-stream",
                content=b"worker-payload",
            )
            SyncQueueService.enqueue_for_sync(db, evidence)
            assert evidence.sync_state == "READY_FOR_SYNC"

        def fake_connectivity():
            return True

        def fake_accept(payload, token_value):
            return True, {"evidence_id": payload["evidence_id"], "status": "SYNCED"}, False, None

        monkeypatch.setattr(SyncWorkerService, "_check_connectivity", staticmethod(fake_connectivity))
        monkeypatch.setattr(SyncWorkerService, "_server_accepts_sync", staticmethod(fake_accept))

        with session_module.SessionLocal() as db:
            results = SyncWorkerService.process_due_entries(db, token=token)
            assert results == [evidence.id]
            row = db.query(SyncQueueEntry).filter(SyncQueueEntry.evidence_id == evidence.id).first()
            assert row is not None
            assert row.state == "SYNCED"


def test_worker_recovers_stale_syncing_state(client):
    with TestClient(app) as c:
        token = register_and_login(c, "Worker Two", "worker2@example.com", "StrongPass123!", "Org Worker")
        user = c.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

        with session_module.SessionLocal() as db:
            case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
            evidence = OfflineEvidenceService.create_offline_evidence(
                db,
                case_id=case.id,
                organization_id=user["organization_id"],
                created_by=user["id"],
                original_filename="stale.bin",
                mime_type="application/octet-stream",
                content=b"stale-payload",
            )
            entry = SyncQueueService.enqueue_for_sync(db, evidence)
            entry.state = "SYNCING"
            entry.last_attempt_at = None
            db.commit()
            evidence_id = evidence.id

        with session_module.SessionLocal() as db:
            SyncQueueService.recover_stale_syncing(db)
            recovered = db.query(SyncQueueEntry).filter(SyncQueueEntry.evidence_id == evidence_id).first()
            assert recovered is not None
            assert recovered.state == "READY_FOR_SYNC"


def test_worker_marks_retryable_failures_without_hammering(client, monkeypatch):
    with TestClient(app) as c:
        token = register_and_login(c, "Worker Three", "worker3@example.com", "StrongPass123!", "Org Worker")
        user = c.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

        with session_module.SessionLocal() as db:
            case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
            evidence = OfflineEvidenceService.create_offline_evidence(
                db,
                case_id=case.id,
                organization_id=user["organization_id"],
                created_by=user["id"],
                original_filename="retry.bin",
                mime_type="application/octet-stream",
                content=b"retry-payload",
            )
            SyncQueueService.enqueue_for_sync(db, evidence)
            evidence_id = evidence.id

        monkeypatch.setattr(SyncWorkerService, "_check_connectivity", staticmethod(lambda: False))

        with session_module.SessionLocal() as db:
            SyncWorkerService.process_due_entries(db, token=token)
            row = db.query(SyncQueueEntry).filter(SyncQueueEntry.evidence_id == evidence_id).first()
            assert row is not None
            assert row.state == "SYNC_FAILED"
            assert row.retryable == 1
