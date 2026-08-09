"""Audit log endpoint. Read-only, Administrator only.

Reading the audit log is itself audited — the middleware records GETs on this
prefix. Who reviewed the trail, and when, is part of the trail.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from api.deps import get_audit_service, require_roles
from models.user import Role
from schemas.audit import AuditEventRead
from services.audit_service import AuditService

router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[Depends(require_roles(Role.ADMINISTRATOR))],
)


@router.get("", response_model=list[AuditEventRead])
def list_events(
    service: AuditService = Depends(get_audit_service),
    actor_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    succeeded: bool | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[AuditEventRead]:
    return service.list(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        succeeded=succeeded,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
