import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_email: str
    action: str
    outcome: str
    resource_type: str
    resource_id: uuid.UUID | None
    detail: dict
    created_at: datetime
