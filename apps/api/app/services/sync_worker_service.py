from __future__ import annotations

import base64
import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any
from urllib import error, request

from sqlalchemy.orm import Session

from app.models.evidence import Evidence
from app.security.crypto import canonical_json
from app.services.local_vault_service import LocalVaultService
from app.services.sync_queue_service import SyncQueueService


class SyncWorkerService:
    @staticmethod
    def _check_connectivity() -> bool:
        try:
            req = request.Request("http://localhost:8000/health", method="GET")
            with request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except Exception:
            return False

    @staticmethod
    def _retryable_http_status(status_code: int | None) -> bool:
        if status_code is None:
            return True
        return status_code in {408, 429, 500, 502, 503, 504}

    @staticmethod
    def _build_api_payload(evidence: Evidence) -> dict:
        original_bytes = LocalVaultService.retrieve_evidence(evidence)
        return {
            "evidence_id": evidence.id,
            "case_id": evidence.case_id,
            "organization_id": evidence.organization_id,
            "original_filename": evidence.original_filename,
            "mime_type": evidence.mime_type,
            "file_size": evidence.file_size,
            "collection_timestamp": evidence.collection_timestamp.isoformat() if evidence.collection_timestamp else None,
            "created_by": evidence.created_by,
            "description": evidence.description,
            "content_base64": base64.b64encode(original_bytes).decode("utf-8"),
            "sha256": evidence.sha256,
            "original_sha256": evidence.original_sha256,
            "manifest_sha256": evidence.manifest_sha256,
            "signature": evidence.signature,
            "signature_algorithm": evidence.signature_algorithm,
            "key_id": evidence.key_id,
            "signature_version": evidence.signature_version,
            "public_key_pem": evidence.public_key_pem,
            "local_case_id": evidence.local_case_id,
            "evidence_metadata": evidence.evidence_metadata,
        }

    @staticmethod
    def _server_accepts_sync(payload: dict, token: str | None) -> tuple[bool, Any, bool, str | None]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            body_bytes = json.dumps(payload).encode("utf-8")
            req = request.Request("http://localhost:8000/sync/evidence", data=body_bytes, headers=headers, method="POST")
            with request.urlopen(req, timeout=10) as response:
                raw_body = response.read()
                body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
                if response.status in {200, 201}:
                    return True, body, False, None
                return False, body, SyncWorkerService._retryable_http_status(response.status), body.get("detail") if isinstance(body, dict) else None
        except error.HTTPError as exc:
            body = {}
            try:
                raw_body = exc.read()
                body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            except Exception:
                body = {}
            detail = body.get("detail") if isinstance(body, dict) else None
            if exc.code in {401, 403}:
                return False, body, False, "AUTHENTICATION_REQUIRED"
            if exc.code == 400 and isinstance(detail, str):
                return False, body, False, detail
            if SyncWorkerService._retryable_http_status(exc.code):
                return False, body, True, detail
            return False, body, False, detail
        except Exception as exc:
            return False, {"error": str(exc)}, True, "NETWORK_ERROR"

    @staticmethod
    def process_due_entries(db: Session, *, token: str | None = None) -> list[str]:
        SyncQueueService.recover_stale_syncing(db)
        entries = SyncQueueService.get_eligible_entries(db)
        processed: list[str] = []
        for entry in entries:
            evidence = db.query(Evidence).filter(Evidence.id == entry.evidence_id).first()
            if evidence is None:
                continue
            if evidence.sync_state == "SYNCED":
                continue
            if entry.state == "SYNCING":
                continue
            if not evidence.storage_reference:
                SyncQueueService.mark_failed(db, evidence, reason="Missing storage reference", retryable=False)
                processed.append(evidence.id)
                continue

            if not SyncWorkerService._check_connectivity():
                SyncQueueService.mark_failed(db, evidence, reason="API unreachable", retryable=True)
                processed.append(evidence.id)
                continue

            if token is None:
                SyncQueueService.mark_failed(db, evidence, reason="AUTHENTICATION_REQUIRED", retryable=False)
                processed.append(evidence.id)
                continue

            try:
                payload = SyncWorkerService._build_api_payload(evidence)
                SyncQueueService.mark_syncing(db, evidence.id)
                accepted, body, retryable, reason = SyncWorkerService._server_accepts_sync(payload, token)
                if accepted:
                    evidence.sync_state = "SYNCED"
                    evidence.not_synced = False
                    evidence.status = "SYNCED"
                    SyncQueueService.mark_synced(db, evidence, last_error=None)
                    processed.append(evidence.id)
                    continue
                if retryable:
                    SyncQueueService.mark_failed(db, evidence, reason=reason or "RETRYABLE_SYNC_FAILURE", retryable=True)
                else:
                    SyncQueueService.mark_failed(db, evidence, reason=reason or "PERMANENT_SYNC_FAILURE", retryable=False)
                processed.append(evidence.id)
            except (FileNotFoundError, ValueError) as exc:
                SyncQueueService.mark_failed(db, evidence, reason=str(exc), retryable=False)
                processed.append(evidence.id)
        return processed

    @staticmethod
    def run_worker_loop(db: Session, *, token: str | None, interval_seconds: int = 10, max_cycles: int | None = None, stop_event: Any | None = None) -> None:
        cycles = 0
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            SyncWorkerService.process_due_entries(db, token=token)
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                break
            time.sleep(interval_seconds)
