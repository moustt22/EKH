import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import AuditEvent, User

_HIDDEN_DETAIL_KEYS = {"answer", "body", "content", "data", "password", "passage", "snippet", "text"}


def record_audit(
    db: Session,
    *,
    action: str,
    outcome: str,
    actor: User | None = None,
    actor_email: str | None = None,
    resource_type: str = "",
    resource_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    email = actor.email if actor is not None else (actor_email or "")
    event = AuditEvent(
        actor_id=actor.id if actor is not None else None,
        actor_email=email[:320],
        action=action,
        outcome=outcome,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=_detail(metadata or {}),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_audit_events(db: Session, limit: int) -> list[AuditEvent]:
    return list(db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)))


def detail_of(event: AuditEvent) -> dict:
    try:
        parsed = json.loads(event.detail)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _detail(metadata: dict) -> str:
    clean: dict = {}
    for key, value in metadata.items():
        if str(key).lower() in _HIDDEN_DETAIL_KEYS:
            continue
        if isinstance(value, str):
            clean[key] = value[:160]
        elif isinstance(value, list):
            clean[key] = [str(item)[:80] for item in value[:20]]
        elif isinstance(value, (int, float, bool)) or value is None:
            clean[key] = value
        else:
            clean[key] = str(value)[:160]
    return json.dumps(clean)
