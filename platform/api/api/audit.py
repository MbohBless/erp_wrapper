"""Audit log endpoints (read-only by design)."""

from fastapi import APIRouter, Depends, Query

from api.deps import any_operator, get_audit_repository
from repositories.audit_repository import AuditRepository
from schemas.audit import AuditEntry

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEntry], dependencies=[Depends(any_operator)])
def list_audit(
    tenant_id: str | None = None,
    action: str | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    repo: AuditRepository = Depends(get_audit_repository),
):
    return repo.list(tenant_id=tenant_id, action=action, skip=skip, limit=limit)
