from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy import text

from app.api.routes.auth import router as auth_router
from app.api.routes.cases import router as cases_router
from app.api.routes.derivatives import router as derivatives_router
from app.api.routes.evidence import router as evidence_router
from app.api.routes.reports import router as reports_router
from app.api.routes.shares import router as shares_router
from app.api.routes.sync import router as sync_router
from app.api.routes.users import router as users_router
from app.db.session import Base, SessionLocal, engine
from app.models.audit import AuditEvent  # noqa: F401
from app.models.case import Case  # noqa: F401
from app.models.custody import CustodyEvent  # noqa: F401
from app.models.derivative import EvidenceDerivative  # noqa: F401
from app.models.evidence import Evidence  # noqa: F401
from app.models.share import EvidenceShare  # noqa: F401
from app.models.sync_queue import SyncQueueEntry  # noqa: F401
from app.models.user import Organization, User  # noqa: F401
from app.security.passwords import hash_password, verify_password

load_dotenv()


def ensure_demo_accounts() -> None:
    demo_accounts = [
        {"email": "live.user@example.com", "name": "Live User", "password": "Password123!", "organization_name": "Live Org"},
        {"email": "demo@verichain.dev", "name": "Demo Investigator", "password": "Password123!", "organization_name": "VeriChain Demo"},
        {"email": "demo@example.com", "name": "Demo User", "password": "Password123!", "organization_name": "Demo Org"},
    ]

    db = SessionLocal()
    try:
        for account in demo_accounts:
            user = db.query(User).filter(User.email == account["email"].lower()).first()
            org = db.query(Organization).filter(Organization.name == account["organization_name"]).first()
            if org is None:
                org = Organization(name=account["organization_name"])
                db.add(org)
                db.flush()

            if user is None:
                user = User(
                    name=account["name"],
                    email=account["email"].lower(),
                    password_hash=hash_password(account["password"]),
                    role="investigator",
                    status="active",
                    organization_id=org.id,
                )
                db.add(user)
                db.commit()
                continue

            user.name = account["name"]
            user.organization_id = org.id
            user.role = "investigator"
            user.status = "active"
            if not verify_password(account["password"], user.password_hash):
                user.password_hash = hash_password(account["password"])
            db.commit()
    finally:
        db.close()



def ensure_database_compatibility() -> None:
    if not str(engine.url).startswith("sqlite"):
        return

    with engine.begin() as conn:
        columns = conn.execute(text("PRAGMA table_info(evidence)")).fetchall()
        existing = {column[1] for column in columns}
        if "evidence_name" not in existing:
            conn.execute(text("ALTER TABLE evidence ADD COLUMN evidence_name VARCHAR(255)"))
        # users table additions: handle, investigator_id
        columns = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        existing_users = {c[1] for c in columns}
        if "handle" not in existing_users:
            conn.execute(text("ALTER TABLE users ADD COLUMN handle VARCHAR(64)"))
        if "investigator_id" not in existing_users:
            conn.execute(text("ALTER TABLE users ADD COLUMN investigator_id VARCHAR(32)"))

        # cases table additions: display_number
        columns = conn.execute(text("PRAGMA table_info(cases)")).fetchall()
        existing_cases = {c[1] for c in columns}
        if "display_number" not in existing_cases:
            conn.execute(text("ALTER TABLE cases ADD COLUMN display_number INTEGER DEFAULT 0 NOT NULL"))

        # evidence table additions: archived
        columns = conn.execute(text("PRAGMA table_info(evidence)")).fetchall()
        existing_evidence = {c[1] for c in columns}
        if "archived" not in existing_evidence:
            conn.execute(text("ALTER TABLE evidence ADD COLUMN archived INTEGER DEFAULT 0 NOT NULL"))


Base.metadata.create_all(bind=engine)
ensure_database_compatibility()
ensure_demo_accounts()

app = FastAPI(title="VeriChain API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(cases_router)
app.include_router(evidence_router)
app.include_router(derivatives_router)
app.include_router(shares_router)
app.include_router(reports_router)
app.include_router(sync_router)
app.include_router(users_router)


@app.get("/health")
def health():
    return {"status": "ok"}
