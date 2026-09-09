import base64
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app


@pytest.fixture
def client():
    import app.db.session as session_module

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


def test_case_create_and_get(client):
    token = register_and_login(client, "Alice", "alice@orga.com", "StrongPass123!", "Org A")

    response = client.post(
        "/cases",
        json={"name": "Initial Case", "description": "Evidence intake", "status": "OPEN"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    case = response.json()
    assert case["name"] == "Initial Case"
    assert case["status"] == "OPEN"
    assert case["organization_id"] is not None

    list_response = client.get("/cases", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    assert len(list_response.json()) >= 1

    detail_response = client.get(f"/cases/{case['id']}", headers={"Authorization": f"Bearer {token}"})
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == case["id"]


def test_case_update_and_cross_org_access(client):
    token_a = register_and_login(client, "Alice", "alice@orga.com", "StrongPass123!", "Org A")
    token_b = register_and_login(client, "Bob", "bob@orgb.com", "StrongPass123!", "Org B")

    created = client.post(
        "/cases",
        json={"name": "Org A Case", "description": "Sensitive", "status": "OPEN"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    case_id = created.json()["id"]

    update_resp = client.patch(
        f"/cases/{case_id}",
        json={"name": "Updated Org A Case", "status": "ARCHIVED"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated Org A Case"

    forbidden = client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert forbidden.status_code == 403


def test_evidence_create_and_list(client):
    token = register_and_login(client, "Alice", "alice@orga.com", "StrongPass123!", "Org A")
    case = client.post(
        "/cases",
        json={"name": "Evidence Case", "description": "Case for evidence", "status": "OPEN"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    response = client.post(
        f"/cases/{case['id']}/evidence",
        json={
            "original_filename": "device_image.jpg",
            "evidence_type": "IMAGE",
            "mime_type": "image/jpeg",
            "file_size": 1024,
            "collection_timestamp": "2026-01-15T12:00:00Z",
            "description": "Phone image",
            "metadata": {"device": "iPhone 14"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    evidence = response.json()
    assert evidence["id"]
    assert evidence["status"] == "CREATED"
    assert evidence["organization_id"] == case["organization_id"]

    list_response = client.get(
        f"/cases/{case['id']}/evidence",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) >= 1

    single_response = client.get(f"/evidence/{evidence['id']}", headers={"Authorization": f"Bearer {token}"})
    assert single_response.status_code == 200
    assert single_response.json()["id"] == evidence["id"]


def test_evidence_unauth_and_identity_guardrails(client):
    token_a = register_and_login(client, "Alice", "alice@orga.com", "StrongPass123!", "Org A")
    token_b = register_and_login(client, "Bob", "bob@orgb.com", "StrongPass123!", "Org B")
    case = client.post(
        "/cases",
        json={"name": "Case A", "description": "Case A description", "status": "OPEN"},
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()

    evidence = client.post(
        f"/cases/{case['id']}/evidence",
        json={
            "original_filename": "log.txt",
            "evidence_type": "LOG",
            "mime_type": "text/plain",
            "file_size": 245,
            "collection_timestamp": "2026-01-15T12:00:00Z",
            "description": "Server log",
        },
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()

    unauth = client.get(f"/evidence/{evidence['id']}")
    assert unauth.status_code == 401

    forbidden = client.get(f"/evidence/{evidence['id']}", headers={"Authorization": f"Bearer {token_b}"})
    assert forbidden.status_code == 403

    protected_update = client.patch(
        f"/evidence/{evidence['id']}",
        json={"id": "attacker-id", "organization_id": 999, "original_sha256": "abc123", "description": "modified"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert protected_update.status_code == 200
    assert protected_update.json()["description"] == "modified"
    assert protected_update.json()["id"] != "attacker-id"
    assert protected_update.json()["organization_id"] != 999


def test_evidence_sealing_and_tamper_detection(client):
    token = register_and_login(client, "Alice", "alice@orga.com", "StrongPass123!", "Org A")
    case = client.post(
        "/cases",
        json={"name": "Crypto Case", "description": "Sealing", "status": "OPEN"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    content = b"evidence-sequence\x00\x01\x02\x03\n"
    evidence = client.post(
        f"/cases/{case['id']}/evidence",
        json={
            "original_filename": "sample.bin",
            "evidence_type": "BINARY",
            "mime_type": "application/octet-stream",
            "file_size": len(content),
            "description": "Binary evidence",
            "content_base64": base64.b64encode(content).decode("utf-8"),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert evidence.status_code == 200, evidence.text
    evidence_id = evidence.json()["id"]
    original_hash = hashlib.sha256(content).hexdigest()
    assert evidence.json()["storage_reference"]
    assert evidence.json()["sha256"] == original_hash

    sealed = client.post(
        f"/evidence/{evidence_id}/seal",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert sealed.status_code == 200, sealed.text
    sealed_json = sealed.json()
    assert sealed_json["sha256"] == original_hash
    assert sealed_json["status"] == "SEALED"
    assert sealed_json["manifest_sha256"]
    assert sealed_json["seal_version"]
    assert sealed_json["sealed_at"]

    verified = client.post(
        f"/evidence/{evidence_id}/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["match"] is True
    assert verified.json()["recorded_sha256"] == original_hash
    assert verified.json()["current_sha256"] == original_hash

    evidence_file = Path(evidence.json()["storage_reference"])
    evidence_file.write_bytes(b"tampered-data")

    tampered = client.post(
        f"/evidence/{evidence_id}/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert tampered.status_code == 200, tampered.text
    assert tampered.json()["match"] is False
    assert tampered.json()["recorded_sha256"] == original_hash
    assert tampered.json()["current_sha256"] != original_hash

    refreshed = client.get(f"/evidence/{evidence_id}", headers={"Authorization": f"Bearer {token}"})
    assert refreshed.status_code == 200
    assert refreshed.json()["sha256"] == original_hash
    assert refreshed.json()["status"] == "SEALED"


def test_custody_chain_records_and_verifies_evidence(client):
    token = register_and_login(client, "Alice", "alice@orga.com", "StrongPass123!", "Org A")
    case = client.post(
        "/cases",
        json={"name": "Custody Case", "description": "Chain of custody", "status": "OPEN"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    content = b"custody-evidence"
    evidence = client.post(
        f"/cases/{case['id']}/evidence",
        json={
            "original_filename": "custody.bin",
            "evidence_type": "BINARY",
            "mime_type": "application/octet-stream",
            "file_size": len(content),
            "description": "Custody evidence",
            "content_base64": base64.b64encode(content).decode("utf-8"),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert evidence.status_code == 200, evidence.text
    evidence_id = evidence.json()["id"]

    sealed = client.post(f"/evidence/{evidence_id}/seal", headers={"Authorization": f"Bearer {token}"})
    assert sealed.status_code == 200, sealed.text

    verified = client.post(f"/evidence/{evidence_id}/verify", headers={"Authorization": f"Bearer {token}"})
    assert verified.status_code == 200, verified.text

    create_events = client.get(f"/evidence/{evidence_id}/custody", headers={"Authorization": f"Bearer {token}"})
    assert create_events.status_code == 200, create_events.text
    assert [event["event_type"] for event in create_events.json()][:3] == ["CREATED", "SEALED", "VERIFIED"]

    chain = client.post(f"/evidence/{evidence_id}/custody/verify", headers={"Authorization": f"Bearer {token}"})
    assert chain.status_code == 200, chain.text
    assert chain.json()["chain_valid"] is True
    assert chain.json()["events_checked"] >= 3
    assert chain.json()["last_event"]


def test_custody_tamper_scenarios_and_authorization(client):
    import app.db.session as session_module
    from app.models.custody import CustodyEvent

    token_a = register_and_login(client, "Alice", "alice@orga.com", "StrongPass123!", "Org A")
    token_b = register_and_login(client, "Bob", "bob@orgb.com", "StrongPass123!", "Org B")
    case = client.post(
        "/cases",
        json={"name": "Tamper Case", "description": "Audit", "status": "OPEN"},
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()

    evidence = client.post(
        f"/cases/{case['id']}/evidence",
        json={
            "original_filename": "tamper.bin",
            "evidence_type": "BINARY",
            "mime_type": "application/octet-stream",
            "file_size": 12,
            "description": "Tamper evidence",
            "content_base64": base64.b64encode(b"tamper-me").decode("utf-8"),
        },
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()

    evidence_id = evidence["id"]
    client.post(f"/evidence/{evidence_id}/seal", headers={"Authorization": f"Bearer {token_a}"})
    client.post(f"/evidence/{evidence_id}/verify", headers={"Authorization": f"Bearer {token_a}"})

    unauth = client.get(f"/evidence/{evidence_id}/custody")
    assert unauth.status_code == 401

    forbidden = client.get(f"/evidence/{evidence_id}/custody", headers={"Authorization": f"Bearer {token_b}"})
    assert forbidden.status_code == 403

    valid = client.post(f"/evidence/{evidence_id}/custody/verify", headers={"Authorization": f"Bearer {token_a}"})
    assert valid.status_code == 200
    assert valid.json()["chain_valid"] is True

    with session_module.SessionLocal() as db:
        events = db.query(CustodyEvent).filter(CustodyEvent.evidence_id == evidence_id).order_by(CustodyEvent.event_index.asc()).all()
        assert len(events) >= 3

        target = events[1]
        original_hash = target.event_hash
        target.details = {"tampered": True}
        target.event_hash = original_hash
        db.commit()

        tampered_event = client.post(f"/evidence/{evidence_id}/custody/verify", headers={"Authorization": f"Bearer {token_a}"})
        assert tampered_event.status_code == 200
        assert tampered_event.json()["chain_valid"] is False
        assert tampered_event.json()["failure_reason"] in {"EVENT_HASH_MISMATCH", "PREVIOUS_HASH_MISMATCH"}

    with session_module.SessionLocal() as db:
        events = db.query(CustodyEvent).filter(CustodyEvent.evidence_id == evidence_id).order_by(CustodyEvent.event_index.asc()).all()
        target = events[1]
        target.previous_event_hash = "tampered-previous"
        db.commit()

        tampered_previous = client.post(f"/evidence/{evidence_id}/custody/verify", headers={"Authorization": f"Bearer {token_a}"})
        assert tampered_previous.status_code == 200
        assert tampered_previous.json()["chain_valid"] is False
        assert tampered_previous.json()["failure_reason"] == "PREVIOUS_HASH_MISMATCH"

    with session_module.SessionLocal() as db:
        events = db.query(CustodyEvent).filter(CustodyEvent.evidence_id == evidence_id).order_by(CustodyEvent.event_index.asc()).all()
        target = events[1]
        db.delete(target)
        db.commit()

        removed_event = client.post(f"/evidence/{evidence_id}/custody/verify", headers={"Authorization": f"Bearer {token_a}"})
        assert removed_event.status_code == 200
        assert removed_event.json()["chain_valid"] is False

    with session_module.SessionLocal() as db:
        events = db.query(CustodyEvent).filter(CustodyEvent.evidence_id == evidence_id).order_by(CustodyEvent.event_index.asc()).all()
        if len(events) >= 2:
            first, second = events[0], events[1]
            second.event_index, first.event_index = first.event_index, second.event_index
            db.commit()

        reordered = client.post(f"/evidence/{evidence_id}/custody/verify", headers={"Authorization": f"Bearer {token_a}"})
        assert reordered.status_code == 200
        assert reordered.json()["chain_valid"] is False

    # verify the API exposes no mutation surface for custody rows
    mutation_attempt = client.patch(
        f"/evidence/{evidence_id}/custody/1",
        json={"event_hash": "abc"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert mutation_attempt.status_code in {404, 405}

    delete_attempt = client.delete(
        f"/evidence/{evidence_id}/custody/1",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert delete_attempt.status_code in {404, 405}


def test_evidence_signature_lifecycle_and_tamper_security(client):
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    import app.db.session as session_module
    from app.models.evidence import Evidence

    token_a = register_and_login(client, "Alice", "alice@orga.com", "StrongPass123!", "Org A")
    token_b = register_and_login(client, "Bob", "bob@orgb.com", "StrongPass123!", "Org B")
    case = client.post(
        "/cases",
        json={"name": "Signature Case", "description": "Crypto identity", "status": "OPEN"},
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()

    content = b"signature-evidence"
    evidence = client.post(
        f"/cases/{case['id']}/evidence",
        json={
            "original_filename": "signed.bin",
            "evidence_type": "BINARY",
            "mime_type": "application/octet-stream",
            "file_size": len(content),
            "description": "Signed evidence",
            "content_base64": base64.b64encode(content).decode("utf-8"),
        },
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()
    evidence_id = evidence["id"]

    sealed = client.post(f"/evidence/{evidence_id}/seal", headers={"Authorization": f"Bearer {token_a}"})
    assert sealed.status_code == 200, sealed.text

    signed = client.post(f"/evidence/{evidence_id}/sign", headers={"Authorization": f"Bearer {token_a}"})
    assert signed.status_code == 200, signed.text
    signed_json = signed.json()
    assert signed_json["signature_valid"] is True
    assert signed_json["key_id"]
    assert "private_key" not in signed_json
    assert "private_key_pem" not in signed_json

    custody = client.get(f"/evidence/{evidence_id}/custody", headers={"Authorization": f"Bearer {token_a}"})
    assert custody.status_code == 200
    assert any(event["event_type"] == "SIGNED" for event in custody.json())

    valid = client.post(f"/evidence/{evidence_id}/verify-signature", headers={"Authorization": f"Bearer {token_a}"})
    assert valid.status_code == 200, valid.text
    assert valid.json()["signature_valid"] is True
    assert valid.json()["overall_valid"] is True

    unauthorized = client.post(f"/evidence/{evidence_id}/sign", headers={"Authorization": f"Bearer {token_b}"})
    assert unauthorized.status_code == 403

    with session_module.SessionLocal() as db:
        evidence_row = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        assert evidence_row is not None
        original_signature = evidence_row.signature
        original_manifest = evidence_row.manifest_sha256
        original_public_key = evidence_row.public_key_pem
        evidence_row.manifest_sha256 = "00" * 32
        db.commit()

        modified_metadata = client.post(f"/evidence/{evidence_id}/verify-signature", headers={"Authorization": f"Bearer {token_a}"})
        assert modified_metadata.status_code == 200
        assert modified_metadata.json()["signature_valid"] is False
        assert modified_metadata.json()["overall_valid"] is False

        evidence_row.manifest_sha256 = original_manifest
        evidence_row.signature = base64.b64encode(b"tampered-sig").decode("utf-8")
        db.commit()

        modified_signature = client.post(f"/evidence/{evidence_id}/verify-signature", headers={"Authorization": f"Bearer {token_a}"})
        assert modified_signature.status_code == 200
        assert modified_signature.json()["signature_valid"] is False

        evidence_row.signature = original_signature
        wrong_private = ed25519.Ed25519PrivateKey.generate()
        wrong_public = wrong_private.public_key()
        evidence_row.public_key_pem = wrong_public.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        db.commit()

        wrong_key = client.post(f"/evidence/{evidence_id}/verify-signature", headers={"Authorization": f"Bearer {token_a}"})
        assert wrong_key.status_code == 200
        assert wrong_key.json()["signature_valid"] is False

        evidence_row.public_key_pem = original_public_key
        db.commit()

    evidence_file = client.get(f"/evidence/{evidence_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert evidence_file.status_code == 200
    file_path = evidence_file.json()["storage_reference"]
    with open(file_path, "wb") as handle:
        handle.write(b"tampered-bytes")

    tampered_bytes = client.post(f"/evidence/{evidence_id}/verify-signature", headers={"Authorization": f"Bearer {token_a}"})
    assert tampered_bytes.status_code == 200
    assert tampered_bytes.json()["evidence_integrity"] is False
    assert tampered_bytes.json()["signature_valid"] is False
    assert tampered_bytes.json()["overall_valid"] is False
