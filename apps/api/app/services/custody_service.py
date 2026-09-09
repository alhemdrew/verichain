from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.custody import CustodyEvent
from app.models.evidence import Evidence
from app.security.crypto import canonical_json, hash_bytes


class CustodyService:
    @staticmethod
    def _canonical_timestamp(value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None).isoformat()

    @staticmethod
    def _event_hash(canonical_event: dict) -> str:
        return hash_bytes(canonical_json(canonical_event).encode("utf-8"))

    @staticmethod
    def create_event(
        db: Session,
        *,
        evidence: Evidence,
        actor_id: int,
        event_type: str,
        details: dict | None = None,
        event_version: str = "custody-v1",
    ) -> CustodyEvent:
        previous_event = (
            db.query(CustodyEvent)
            .filter(CustodyEvent.evidence_id == evidence.id)
            .order_by(CustodyEvent.event_index.asc(), CustodyEvent.created_at.asc())
            .all()
        )
        previous_event = previous_event[-1] if previous_event else None

        previous_hash = previous_event.event_hash if previous_event else None
        event_timestamp = datetime.now(timezone.utc)
        event_id = str(uuid.uuid4())
        payload = {
            "event_id": event_id,
            "evidence_id": evidence.id,
            "organization_id": evidence.organization_id,
            "actor_id": actor_id,
            "event_type": event_type,
            "event_timestamp": CustodyService._canonical_timestamp(event_timestamp),
            "details": details or {},
            "previous_event_hash": previous_hash,
            "event_version": event_version,
        }
        event_hash = CustodyService._event_hash(payload)

        event = CustodyEvent(
            id=event_id,
            evidence_id=evidence.id,
            organization_id=evidence.organization_id,
            actor_id=actor_id,
            event_type=event_type,
            event_timestamp=event_timestamp,
            details=details or {},
            previous_event_hash=previous_hash,
            event_hash=event_hash,
            event_version=event_version,
            event_index=(previous_event.event_index + 1 if previous_event else 0),
        )

        db.add(event)
        db.commit()
        db.refresh(event)
        # Also emit an audit event to tie actor (technical) to display investigator info
        try:
            from app.models.audit import AuditEvent

            audit = AuditEvent(
                id=str(uuid.uuid4()),
                actor_id=actor_id,
                evidence_id=evidence.id,
                event_type=f"CUSTODY_{event_type}",
                result="SUCCESS",
                details={"custody_details": details or {}},
            )
            db.add(audit)
            db.commit()
        except Exception:
            # do not fail custody creation due to audit write errors
            pass
        return event

    @staticmethod
    def get_events_for_evidence(db: Session, *, evidence_id: str, organization_id: int):
        return (
            db.query(CustodyEvent)
            .filter(CustodyEvent.evidence_id == evidence_id, CustodyEvent.organization_id == organization_id)
            .order_by(CustodyEvent.event_index.asc())
            .all()
        )

    @staticmethod
    def verify_chain(db: Session, *, evidence_id: str, organization_id: int):
        events = CustodyService.get_events_for_evidence(db, evidence_id=evidence_id, organization_id=organization_id)
        if not events:
            return {
                "chain_valid": False,
                "events_checked": 0,
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "failure_reason": "NO_CUSTODY_EVENTS",
            }

        expected_previous = None
        for index, event in enumerate(events):
            payload = {
                "event_id": event.id,
                "evidence_id": event.evidence_id,
                "organization_id": event.organization_id,
                "actor_id": event.actor_id,
                "event_type": event.event_type,
                "event_timestamp": CustodyService._canonical_timestamp(event.event_timestamp),
                "details": event.details or {},
                "previous_event_hash": event.previous_event_hash,
                "event_version": event.event_version,
            }
            computed = CustodyService._event_hash(payload)
            if event.previous_event_hash != expected_previous:
                return {
                    "chain_valid": False,
                    "events_checked": index + 1,
                    "first_event": events[0].id,
                    "last_event": event.id,
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                    "failure_reason": "PREVIOUS_HASH_MISMATCH",
                    "problem_event_id": event.id,
                }

            if computed != event.event_hash:
                return {
                    "chain_valid": False,
                    "events_checked": index + 1,
                    "first_event": events[0].id,
                    "last_event": event.id,
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                    "failure_reason": "EVENT_HASH_MISMATCH",
                    "problem_event_id": event.id,
                }

            expected_previous = event.event_hash

        return {
            "chain_valid": True,
            "events_checked": len(events),
            "first_event": events[0].id,
            "last_event": events[-1].id,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "status": "CUSTODY CHAIN VERIFIED",
        }
