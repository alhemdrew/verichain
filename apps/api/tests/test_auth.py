import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models.user import User


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


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_user(client):
    payload = {"name": "Alice", "email": "alice@example.com", "password": "StrongPass123!", "organization_name": " RCN Labs "}
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_duplicate_registration(client):
    first = {"name": "Alice", "email": "alice@example.com", "password": "StrongPass123!", "organization_name": "RCN Labs"}
    client.post("/auth/register", json=first)
    second = {"name": "Bob", "email": "alice@example.com", "password": "AnotherPass456!"}
    response = client.post("/auth/register", json=second)
    assert response.status_code == 400


def test_failed_login_unknown_user(client):
    response = client.post("/auth/login", json={"email": "missing@example.com", "password": "StrongPass123!"})
    assert response.status_code == 401


def test_login_success(client):
    client.post("/auth/register", json={"name": "Alice", "email": "alice@example.com", "password": "StrongPass123!", "organization_name": "RCN Labs"})
    response = client.post("/auth/login", json={"email": "alice@example.com", "password": "StrongPass123!"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_invalid_password(client):
    client.post("/auth/register", json={"name": "Alice", "email": "alice@example.com", "password": "StrongPass123!"})
    response = client.post("/auth/login", json={"email": "alice@example.com", "password": "WrongPassword!"})
    assert response.status_code == 401


def test_me_requires_auth(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_authenticated(client):
    client.post("/auth/register", json={"name": "Alice", "email": "alice@example.com", "password": "StrongPass123!"})
    token = client.post("/auth/login", json={"email": "alice@example.com", "password": "StrongPass123!"}).json()["access_token"]
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "alice@example.com"


def test_protected_route_requires_auth(client):
    response = client.get("/auth/protected")
    assert response.status_code == 401


def test_protected_route_accepts_valid_token(client):
    client.post("/auth/register", json={"name": "Alice", "email": "alice@example.com", "password": "StrongPass123!"})
    token = client.post("/auth/login", json={"email": "alice@example.com", "password": "StrongPass123!"}).json()["access_token"]
    response = client.get("/auth/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_password_not_stored_plaintext(client):
    import app.db.session as session_module

    raw_password = "StrongPass123!"
    client.post("/auth/register", json={"name": "Alice", "email": "alice@example.com", "password": raw_password})
    user = session_module.SessionLocal().query(User).filter(User.email == "alice@example.com").first()
    assert user is not None
    assert user.password_hash != raw_password
    assert user.password_hash.startswith("$2b$")
