from sqlalchemy import text

from app.db.session import SessionLocal, engine
from app.main import ensure_demo_accounts, ensure_database_compatibility
from app.models.audit import AuditEvent  # noqa: F401
from app.models.case import Case  # noqa: F401
from app.models.custody import CustodyEvent  # noqa: F401
from app.models.derivative import EvidenceDerivative  # noqa: F401
from app.models.evidence import Evidence  # noqa: F401
from app.models.share import EvidenceShare  # noqa: F401
from app.models.sync_queue import SyncQueueEntry  # noqa: F401
from app.models.user import User
from app.services.auth_service import AuthService


def test_demo_credentials_are_bootstrapped():
    ensure_database_compatibility()
    ensure_demo_accounts()
    db = SessionLocal()
    try:
        for email in ["demo@verichain.dev", "demo@example.com", "live.user@example.com"]:
            user = db.query(User).filter(User.email == email.lower()).first()
            assert user is not None, f"Missing seeded user: {email}"
            assert AuthService.authenticate_user(db, email=email, password="Password123!") is not None

        evidence_columns = db.execute(text("PRAGMA table_info(evidence)")).fetchall()
        names = {column[1] for column in evidence_columns}
        assert "evidence_name" in names, "evidence_name column is missing"
    finally:
        db.close()
