"""Audit event schemas (Pydantic v2). Read-only: there is no write endpoint.

Events are produced by the audit middleware, never by a client. An API that let
callers write their own audit entries would let them write whatever they liked.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    actor_id: int | None = None
    actor_email: str = ""
    actor_role: str = ""
    action: str
    method: str = ""
    path: str = ""
    resource_type: str = ""
    resource_id: str = ""
    status_code: int = 0
    succeeded: bool = True
    ip_address: str = ""
    request_id: str = ""
