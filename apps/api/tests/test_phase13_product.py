import io

from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.session as session_module
from app.db.session import Base, get_db
from app.main import app
from app.models.case import Case
from app.services.offline_evidence_service import OfflineEvidenceService


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


def _create_local_case(db, organization_id: int, created_by: int):
    case = Case(
        name="Phase 13 Case",
        description="Proof workflow",
        status="OPEN",
        organization_id=organization_id,
        created_by=created_by,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def test_user_lookup_by_email_works_for_same_organization():
    client = next(_client_fixture())
    token = register_and_login(client, "Alpha", "alpha@example.com", "StrongPass123!", "Org Alpha")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="alpha.bin",
            mime_type="application/octet-stream",
            content=b"alpha-content",
        )

    response = client.get("/users/search?email=alpha@example.com", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body[0]["email"] == "alpha@example.com"
    assert body[0]["organization_id"] == user["organization_id"]


def test_report_pdf_generation_returns_real_pdf():
    client = next(_client_fixture())
    token = register_and_login(client, "Beta", "beta@example.com", "StrongPass123!", "Org Beta")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="beta.bin",
            mime_type="application/octet-stream",
            content=b"beta-content",
            description="Report-ready evidence",
        )
        evidence_id = evidence.id

    response = client.get(f"/evidence/{evidence_id}/report.pdf", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")

    reader = PdfReader(io.BytesIO(response.content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "VeriChain Evidence Integrity Report" in text
    assert "beta.bin" in text


def test_report_pdf_supports_summary_and_detailed_modes():
    client = next(_client_fixture())
    token = register_and_login(client, "Theta", "theta@example.com", "StrongPass123!", "Org Theta")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="theta.bin",
            mime_type="application/octet-stream",
            content=b"theta-content",
            description="Detail and summary report generation",
        )
        evidence_id = evidence.id

    for mode in ("summary", "detailed"):
        response = client.get(f"/evidence/{evidence_id}/report.pdf?mode={mode}", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("application/pdf")
        assert response.content.startswith(b"%PDF")

        reader = PdfReader(io.BytesIO(response.content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        assert "VeriChain" in text
        assert "Integrity Check" in text
        assert "Trusted" in text
        assert "theta.bin" in text
        assert mode.title() in text or "SUMMARY" in text or "DETAILED" in text


def test_original_filename_remains_immutable_while_evidence_name_is_editable():
    client = next(_client_fixture())
    token = register_and_login(client, "Gamma", "gamma@example.com", "StrongPass123!", "Org Gamma")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        case_id = case.id
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="WhatsApp Video 2026-09-04 at 14.32.10.mp4",
            mime_type="video/mp4",
            content=b"video-bytes-1234",
            description="Original collection",
        )
        evidence_id = evidence.id
        original_sha = evidence.sha256

    create_response = client.post(
        f"/cases/{case_id}/evidence",
        json={
            "original_filename": "WhatsApp Video 2026-09-04 at 14.32.10.mp4",
            "evidence_name": "Witness A interview recording",
            "evidence_type": "VIDEO",
            "mime_type": "video/mp4",
            "file_size": 16,
            "description": "Initial description",
            "content_base64": "dmVyaWZ5LW1hdGNoLWNvbnRlbnQ=",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["original_filename"] == "WhatsApp Video 2026-09-04 at 14.32.10.mp4"
    assert created["evidence_name"] == "Witness A interview recording"

    patch_response = client.patch(
        f"/evidence/{created['id']}",
        json={"evidence_name": "Main Entrance Incident Video", "description": "Updated description"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_response.status_code == 200, patch_response.text
    patched = patch_response.json()
    assert patched["original_filename"] == "WhatsApp Video 2026-09-04 at 14.32.10.mp4"
    assert patched["evidence_name"] == "Main Entrance Incident Video"
    assert patched["description"] == "Updated description"
    assert patched["sha256"] == created["sha256"]

    download_response = client.get(f"/evidence/{created['id']}/file?download=true", headers={"Authorization": f"Bearer {token}"})
    assert download_response.status_code == 200, download_response.text
    assert download_response.headers["content-disposition"].startswith('attachment; filename="WhatsApp Video 2026-09-04 at 14.32.10.mp4"')

    assert download_response.content == b"verify-match-content"


def test_download_and_presented_file_verification_preserve_sha256():
    client = next(_client_fixture())
    token = register_and_login(client, "Delta", "delta@example.com", "StrongPass123!", "Org Delta")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        content = b"delta-evidence-content-12345"
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="sample.mp4",
            mime_type="video/mp4",
            content=content,
            description="For verification test",
        )
        evidence_id = evidence.id
        expected_sha = evidence.sha256

    original_download = client.get(f"/evidence/{evidence_id}/file?download=true", headers={"Authorization": f"Bearer {token}"})
    assert original_download.status_code == 200, original_download.text
    assert __import__("hashlib").sha256(original_download.content).hexdigest() == expected_sha

    match_response = client.post(
        f"/evidence/{evidence_id}/compare",
        files={"file": ("presented-copy.mp4", b"delta-evidence-content-12345")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert match_response.status_code == 200, match_response.text
    assert match_response.json()["match"] is True

    mismatch_response = client.post(
        f"/evidence/{evidence_id}/compare",
        files={"file": ("tampered-copy.mp4", b"different-content")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert mismatch_response.status_code == 200, mismatch_response.text
    assert mismatch_response.json()["match"] is False


def test_upload_route_round_trips_exact_bytes_without_double_base64_corruption():
    client = next(_client_fixture())
    token = register_and_login(client, "Epsilon", "epsilon@example.com", "StrongPass123!", "Org Epsilon")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        case_id = case.id

    raw_bytes = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x10\x11\x12\x13--binary-corruption-check--"
    upload_response = client.post(
        f"/cases/{case_id}/evidence/upload",
        files={"file": ("binary.bin", raw_bytes, "application/octet-stream")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload_response.status_code == 200, upload_response.text
    created = upload_response.json()

    download_response = client.get(f"/evidence/{created['id']}/file?download=true", headers={"Authorization": f"Bearer {token}"})
    assert download_response.status_code == 200, download_response.text
    assert download_response.content == raw_bytes
    assert download_response.headers["content-disposition"].startswith('attachment; filename="binary.bin"')


def test_successful_verification_marks_evidence_as_verified():
    client = next(_client_fixture())
    token = register_and_login(client, "Zeta", "zeta@example.com", "StrongPass123!", "Org Zeta")
    user = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]

    with session_module.SessionLocal() as db:
        case = _create_local_case(db, organization_id=user["organization_id"], created_by=user["id"])
        evidence = OfflineEvidenceService.create_offline_evidence(
            db,
            case_id=case.id,
            organization_id=user["organization_id"],
            created_by=user["id"],
            original_filename="verified.bin",
            mime_type="application/octet-stream",
            content=b"verified-content",
        )
        evidence_id = evidence.id

    verify_response = client.post(f"/evidence/{evidence_id}/verify", headers={"Authorization": f"Bearer {token}"})
    assert verify_response.status_code == 200, verify_response.text
    assert verify_response.json()["match"] is True

    evidence_response = client.get(f"/evidence/{evidence_id}", headers={"Authorization": f"Bearer {token}"})
    assert evidence_response.status_code == 200, evidence_response.text
    assert evidence_response.json()["status"] == "VERIFIED"
