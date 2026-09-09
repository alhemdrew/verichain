import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-auth")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_verichain.db")
