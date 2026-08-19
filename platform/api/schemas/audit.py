"""Audit log schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_email: str
    action: str
    tenant_id: str
    detail: str
    created_at: datetime
