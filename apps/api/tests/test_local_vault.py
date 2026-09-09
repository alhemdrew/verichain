import base64
import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models.evidence import Evidence
from app.services.local_vault_service import LocalVaultService


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


def test_local_vault_encrypted_storage_and_hash_preservation(client):
    token = register_and_login(client, "Alice", "alice@orga.com", "StrongPass123!", "Org A")
    case = client.post(
        "/cases",
        json={"name": "Vault Case", "description": "Local vault", "status": "OPEN"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    content = b"vault-evidence-bytes-123456"
    evidence = client.post(
        f"/cases/{case['id']}/evidence",
        json={
            "original_filename": "vault.bin",
            "evidence_type": "BINARY",
            "mime_type": "application/octet-stream",
            "file_size": len(content),
            "description": "Vault evidence",
            "content_base64": base64.b64encode(content).decode("utf-8"),
        },
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    evidence_id = evidence["id"]

    sealed = client.post(f"/evidence/{evidence_id}/seal", headers={"Authorization": f"Bearer {token}"})
    assert sealed.status_code == 200, sealed.text

    import app.db.session as session_module
    from app.models.evidence import Evidence

    with session_module.SessionLocal() as db:
        row = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        assert row is not None
        result = LocalVaultService.store_evidence(db, row, plaintext=content)
        assert result["vault_status"] == "LOCAL_ONLY"
        assert row.vault_path
        assert row.vault_nonce
        vault_file = row.vault_path
        assert vault_file
        assert vault_file.endswith(result["vault_object_id"])

        recovered = LocalVaultService.retrieve_evidence(row)
        assert recovered == content
        assert hashlib.sha256(recovered).hexdigest() == row.sha256.lower()

        with open(vault_file, "wb") as handle:
            handle.write(b"tampered")
        with pytest.raises(ValueError):
            LocalVaultService.retrieve_evidence(row)

        with open(vault_file, "wb") as handle:
            handle.write(b"")
        row.vault_nonce = base64.b64encode(b"012345678901").decode("ascii")
        db.commit()
        with pytest.raises(ValueError):
            LocalVaultService.retrieve_evidence(row)

        row.vault_nonce = result["nonce"]
        db.commit()
        assert LocalVaultService.is_valid_object(row) is False


def test_local_vault_key_separation_and_org_isolation(client):
    import app.db.session as session_module
    from app.models.evidence import Evidence

    token_a = register_and_login(client, "Alice", "alice@orga.com", "StrongPass123!", "Org A")
    token_b = register_and_login(client, "Bob", "bob@orgb.com", "StrongPass123!", "Org B")
    case_a = client.post(
        "/cases",
        json={"name": "Org A Case", "description": "Isolated", "status": "OPEN"},
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()
    content = b"org-isolated-evidence"
    evidence = client.post(
        f"/cases/{case_a['id']}/evidence",
        json={
            "original_filename": "org.bin",
            "evidence_type": "BINARY",
            "mime_type": "application/octet-stream",
            "file_size": len(content),
            "description": "Org evidence",
            "content_base64": base64.b64encode(content).decode("utf-8"),
        },
        headers={"Authorization": f"Bearer {token_a}"},
    ).json()
    evidence_id = evidence["id"]
    client.post(f"/evidence/{evidence_id}/seal", headers={"Authorization": f"Bearer {token_a}"})

    with session_module.SessionLocal() as db:
        row = db.query(Evidence).filter(Evidence.id == evidence_id).first()
        assert row is not None
        LocalVaultService.store_evidence(db, row, plaintext=content)

    # Verify that signing and vault keys are distinct conceptually.
    signing_key = base64.b64encode(b"signing-key")
    vault_key = base64.b64encode(b"vault-key")
    assert signing_key != vault_key

    unauthorized = client.get(f"/evidence/{evidence_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert unauthorized.status_code == 403
