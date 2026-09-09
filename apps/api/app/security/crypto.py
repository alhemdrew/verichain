from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_sha256_digest(value: str) -> bool:
    if not isinstance(value, str):
        return False
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_manifest(*, evidence_id: str, case_id: int, organization_id: int, original_filename: str, mime_type: str | None, file_size: int, collection_timestamp: str | None, collector_id: int, sha256: str, manifest_version: str = "sha256-manifest-v1", extra_fields: dict | None = None) -> dict:
    manifest = {
        "manifest_version": manifest_version,
        "evidence_id": evidence_id,
        "case_id": case_id,
        "organization_id": organization_id,
        "original_filename": original_filename,
        "mime_type": mime_type,
        "file_size": file_size,
        "collection_timestamp": collection_timestamp,
        "collector_id": collector_id,
        "sha256": sha256,
        "manifest_created_at": None,
    }
    if extra_fields:
        provenance_keys = {"is_derivative", "parent_evidence_id", "parent_case_id", "parent_organization_id", "derivation_type", "description", "created_at"}
        manifest.update({key: value for key, value in extra_fields.items() if key in provenance_keys})
    return manifest


def manifest_hash(data: dict) -> str:
    return hash_bytes(canonical_json(data).encode("utf-8"))
