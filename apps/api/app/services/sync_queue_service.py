from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.evidence import Evidence
from app.models.sync_queue import SyncQueueEntry


class SyncQueueService:
    @staticmethod
    def queue_model():
        return SyncQueueEntry

    @staticmethod
    def _next_retry_time(attempt_count: int) -> datetime:
        delay_seconds = min(15 * (2 ** max(attempt_count - 1, 0)), 300)
        return datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)

    @staticmethod
    def enqueue_for_sync(db: Session, evidence: Evidence) -> SyncQueueEntry:
        existing = (
            db.query(SyncQueueEntry)
            .filter(SyncQueueEntry.evidence_id == evidence.id)
            .order_by(SyncQueueEntry.created_at.desc())
            .first()
        )
        if existing and existing.state in {"READY_FOR_SYNC", "SYNCING", "SYNC_FAILED"}:
            return existing

        entry = SyncQueueEntry(
            id=str(uuid.uuid4()),
            evidence_id=evidence.id,
            operation_type="evidence_sync",
            state="READY_FOR_SYNC",
            attempt_count=0,
            next_retry_at=datetime.now(timezone.utc),
            retryable=1,
            last_error=None,
            last_attempt_at=None,
        )
        db.add(entry)
        evidence.sync_state = "READY_FOR_SYNC"
        evidence.not_synced = True
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def get_eligible_entries(db: Session):
        now = datetime.now(timezone.utc)
        return (
            db.query(SyncQueueEntry)
            .filter(SyncQueueEntry.state.in_(["READY_FOR_SYNC", "SYNC_FAILED"]))
            .filter((SyncQueueEntry.next_retry_at.is_(None)) | (SyncQueueEntry.next_retry_at <= now))
            .order_by(SyncQueueEntry.created_at.asc())
            .all()
        )

    @staticmethod
    def recover_stale_syncing(db: Session) -> None:
        threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
        stale = (
            db.query(SyncQueueEntry)
            .filter(
                SyncQueueEntry.state == "SYNCING",
                or_(
                    SyncQueueEntry.last_attempt_at.is_(None),
                    SyncQueueEntry.last_attempt_at <= threshold,
                ),
            )
            .all()
        )
        for entry in stale:
            entry.state = "READY_FOR_SYNC"
            entry.next_retry_at = datetime.now(timezone.utc)
            entry.retryable = 1
            entry.last_error = "Recovered after stale syncing state"
        db.commit()

    @staticmethod
    def mark_syncing(db: Session, evidence_id: str) -> None:
        entry = db.query(SyncQueueEntry).filter(SyncQueueEntry.evidence_id == evidence_id).order_by(SyncQueueEntry.created_at.desc()).first()
        if entry is None:
            return
        entry.state = "SYNCING"
        entry.attempt_count += 1
        entry.last_attempt_at = datetime.now(timezone.utc)
        entry.updated_at = datetime.now(timezone.utc)
        db.commit()

    @staticmethod
    def mark_synced(db: Session, evidence: Evidence, *, last_error: str | None = None) -> None:
        evidence.sync_state = "SYNCED"
        evidence.not_synced = False
        evidence.status = "SYNCED"
        entry = db.query(SyncQueueEntry).filter(SyncQueueEntry.evidence_id == evidence.id).order_by(SyncQueueEntry.created_at.desc()).first()
        if entry is not None:
            entry.state = "SYNCED"
            entry.last_error = last_error
            entry.next_retry_at = None
            entry.retryable = 0
            entry.updated_at = datetime.now(timezone.utc)
        db.commit()

    @staticmethod
    def mark_failed(db: Session, evidence: Evidence, *, reason: str, retryable: bool) -> None:
        evidence.sync_state = "SYNC_FAILED"
        evidence.not_synced = True
        entry = db.query(SyncQueueEntry).filter(SyncQueueEntry.evidence_id == evidence.id).order_by(SyncQueueEntry.created_at.desc()).first()
        if entry is not None:
            entry.state = "SYNC_FAILED"
            entry.last_error = reason
            entry.retryable = 1 if retryable else 0
            entry.next_retry_at = None if not retryable else SyncQueueService._next_retry_time(entry.attempt_count)
            entry.updated_at = datetime.now(timezone.utc)
        db.commit()

    @staticmethod
    def mark_retry_ready(db: Session, evidence_id: str) -> None:
        entry = db.query(SyncQueueEntry).filter(SyncQueueEntry.evidence_id == evidence_id).order_by(SyncQueueEntry.created_at.desc()).first()
        if entry is not None:
            entry.state = "READY_FOR_SYNC"
            entry.next_retry_at = datetime.now(timezone.utc)
            entry.updated_at = datetime.now(timezone.utc)
            db.commit()
