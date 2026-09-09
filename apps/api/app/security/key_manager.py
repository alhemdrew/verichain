from __future__ import annotations

import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

KEYS_DIR = Path(__file__).resolve().parents[1] / "storage" / "keys"
PRIVATE_KEY_PATH = KEYS_DIR / "verichain_signing_private_key.pem"
PUBLIC_KEY_PATH = KEYS_DIR / "verichain_signing_public_key.pem"


def _ensure_key_dir() -> None:
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(KEYS_DIR, 0o700)


def generate_or_load_signing_keypair() -> tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey, str]:
    _ensure_key_dir()

    if PRIVATE_KEY_PATH.exists() and PUBLIC_KEY_PATH.exists():
        private_key = serialization.load_pem_private_key(PRIVATE_KEY_PATH.read_bytes(), password=None)
        public_key = serialization.load_pem_public_key(PUBLIC_KEY_PATH.read_bytes())
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        key_id = hashlib.sha256(public_bytes).hexdigest()[:16]
        return private_key, public_key, key_id

    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    PRIVATE_KEY_PATH.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    PUBLIC_KEY_PATH.write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    os.chmod(PRIVATE_KEY_PATH, 0o600)
    os.chmod(PUBLIC_KEY_PATH, 0o644)

    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = hashlib.sha256(public_bytes).hexdigest()[:16]
    return private_key, public_key, key_id


def current_public_key_pem() -> str:
    _, public_key, _ = generate_or_load_signing_keypair()
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def current_key_id() -> str:
    _, _, key_id = generate_or_load_signing_keypair()
    return key_id
