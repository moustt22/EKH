from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.roles import RoleName
from app.database.models import User
from app.database.session import get_db
from app.schemas.audit import AuditEventOut
from app.services.audit import detail_of, list_audit_events

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventOut])
def get_audit(
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(require_roles(RoleName.ADMINISTRATOR.value)),
    db: Session = Depends(get_db),
) -> list[AuditEventOut]:
    return [
        AuditEventOut(
            id=event.id,
            actor_id=event.actor_id,
            actor_email=event.actor_email,
            action=event.action,
            outcome=event.outcome,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            detail=detail_of(event),
            created_at=event.created_at,
        )
        for event in list_audit_events(db, limit)
    ]
