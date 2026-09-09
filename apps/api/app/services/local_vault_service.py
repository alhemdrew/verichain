from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.orm import Session

from app.models.evidence import Evidence


class LocalVaultService:
    BASE_DIR = Path(__file__).resolve().parents[1] / "storage" / "vault"
    KEY_PATH = Path(__file__).resolve().parents[1] / "storage" / "keys" / "verichain_vault_key.bin"
    HEADER_VERSION = "aesgcm-v1"

    @staticmethod
    def _ensure_directories() -> None:
        LocalVaultService.BASE_DIR.mkdir(parents=True, exist_ok=True)
        LocalVaultService.KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(LocalVaultService.KEY_PATH.parent, 0o700)

    @staticmethod
    def _derive_vault_key() -> bytes:
        LocalVaultService._ensure_directories()
        if LocalVaultService.KEY_PATH.exists():
            return LocalVaultService.KEY_PATH.read_bytes()

        key = AESGCM.generate_key(bit_length=256)
        LocalVaultService.KEY_PATH.write_bytes(key)
        os.chmod(LocalVaultService.KEY_PATH, 0o600)
        return key

    @staticmethod
    def _vault_dir_for(evidence_id: str) -> Path:
        return LocalVaultService.BASE_DIR / evidence_id[:2] / evidence_id

    @staticmethod
    def _object_path_for(evidence_id: str, object_id: str | None = None) -> Path:
        q = LocalVaultService._vault_dir_for(evidence_id)
        q.mkdir(parents=True, exist_ok=True)
        return q / (object_id or "encrypted_object.bin")

    @staticmethod
    def _load_metadata(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text("utf-8"))
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _write_atomic_bytes(path: Path, data: bytes) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)

    @staticmethod
    def encrypt_evidence_bytes(plaintext: bytes) -> tuple[bytes, str, str]:
        key = LocalVaultService._derive_vault_key()
        nonce = os.urandom(12)
        encrypted = AESGCM(key).encrypt(nonce, plaintext, None)
        return encrypted, base64.b64encode(nonce).decode("ascii"), base64.b64encode(key).decode("ascii")

    @staticmethod
    def decrypt_evidence_bytes(blob: bytes, nonce_b64: str) -> bytes:
        key = LocalVaultService._derive_vault_key()
        nonce = base64.b64decode(nonce_b64.encode("ascii"))
        return AESGCM(key).decrypt(nonce, blob, None)

    @staticmethod
    def store_evidence(db: Session, evidence: Evidence, *, plaintext: bytes) -> dict:
        if not evidence.id:
            raise ValueError("Evidence ID is required")

        original_sha256 = hashlib.sha256(plaintext).hexdigest()
        if evidence.sha256 and evidence.sha256.lower() != original_sha256.lower():
            raise ValueError("Plaintext evidence does not match sealed SHA-256")

        object_id = str(uuid.uuid4())
        encrypted, nonce_b64, _ = LocalVaultService.encrypt_evidence_bytes(plaintext)
        vault_object = LocalVaultService._object_path_for(evidence.id, object_id)
        LocalVaultService._write_atomic_bytes(vault_object, encrypted)

        metadata = {
            "evidence_id": evidence.id,
            "case_id": evidence.case_id,
            "organization_id": evidence.organization_id,
            "original_filename": evidence.original_filename,
            "mime_type": evidence.mime_type,
            "original_file_size": len(plaintext),
            "original_sha256": original_sha256,
            "manifest_sha256": evidence.manifest_sha256,
            "signature": evidence.signature,
            "signature_algorithm": evidence.signature_algorithm,
            "key_id": evidence.key_id,
            "signature_version": evidence.signature_version,
            "vault_object_id": object_id,
            "vault_algorithm": "AES-256-GCM",
            "vault_version": "aesgcm-v1",
            "nonce": nonce_b64,
            "vault_status": "LOCAL_ONLY",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        metadata_path = vault_object.with_suffix(vault_object.suffix + ".json")
        LocalVaultService._write_atomic_bytes(metadata_path, json.dumps(metadata, sort_keys=True).encode("utf-8"))

        evidence.vault_object_id = object_id
        evidence.vault_status = "LOCAL_ONLY"
        evidence.vault_algorithm = "AES-256-GCM"
        evidence.vault_version = "aesgcm-v1"
        evidence.vault_nonce = nonce_b64
        evidence.vault_path = str(vault_object)
        evidence.vault_created_at = datetime.now(timezone.utc)
        evidence.vault_updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(evidence)

        return {
            "evidence_id": evidence.id,
            "vault_object_id": object_id,
            "vault_path": str(vault_object),
            "vault_status": evidence.vault_status,
            "original_sha256": original_sha256,
            "nonce": nonce_b64,
        }

    @staticmethod
    def retrieve_evidence(evidence: Evidence) -> bytes:
        if not evidence.vault_path:
            raise FileNotFoundError("Evidence has no encrypted vault object")

        object_path = Path(evidence.vault_path)
        if not object_path.exists():
            raise FileNotFoundError("Encrypted vault object is missing")

        metadata_path = object_path.with_suffix(object_path.suffix + ".json")
        metadata = LocalVaultService._load_metadata(metadata_path)
        nonce_b64 = metadata.get("nonce") or evidence.vault_nonce
        if not nonce_b64:
            raise ValueError("Encrypted vault object is missing a nonce")

        ciphertext = object_path.read_bytes()
        try:
            plaintext = LocalVaultService.decrypt_evidence_bytes(ciphertext, nonce_b64)
        except (ValueError, InvalidTag):
            raise ValueError("Vault decryption failed: integrity check failed") from None

        computed = hashlib.sha256(plaintext).hexdigest()
        expected = (evidence.sha256 or evidence.original_sha256 or "").lower()
        if expected and computed.lower() != expected.lower():
            raise ValueError("Vault decryption succeeded but the recovered plaintext hash does not match the evidence hash")
        return plaintext

    @staticmethod
    def is_valid_object(evidence: Evidence) -> bool:
        if not evidence.vault_path:
            return False
        object_path = Path(evidence.vault_path)
        if not object_path.exists():
            return False
        try:
            LocalVaultService.retrieve_evidence(evidence)
            return True
        except (FileNotFoundError, ValueError, InvalidTag):
            return False
