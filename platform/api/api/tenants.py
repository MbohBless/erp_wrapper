"""Tenant registry endpoints — the operator-facing control surface.

Access (see docs/multi-tenancy.md for the full matrix):
  - read:                    Owner, Operator, Support, Billing
  - create/update/provision: Owner, Operator
  - suspend/resume/archive:  Owner, Operator
  - purge:                   Owner
"""

from fastapi import APIRouter, Depends, Query, status

from api.deps import any_operator, can_operate, get_tenant_service, owner_only
from schemas.tenant import (
    ProvisionResult,
    SuspendIn,
    TenantCreate,
    TenantDomainCreate,
    TenantRead,
    TenantSummary,
    TenantUpdate,
)
from services.tenant_service import TenantService

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("", response_model=list[TenantSummary], dependencies=[Depends(any_operator)])
def list_tenants(
    status_filter: str | None = Query(default=None, alias="status"),
    plan_code: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    service: TenantService = Depends(get_tenant_service),
):
    rows = service.list(
        status=status_filter, plan_code=plan_code, search=search, skip=skip, limit=limit
    )
    return [
        TenantSummary(
            id=t.id,
            name=t.name,
            status=t.status,
            plan_code=t.plan_code,
            primary_host=t.primary_host,
            contact_email=t.contact_email,
            created_at=t.created_at,
        )
        for t in rows
    ]


@router.get("/stats", dependencies=[Depends(any_operator)])
def tenant_stats(service: TenantService = Depends(get_tenant_service)) -> dict:
    return service.stats()


@router.get("/{tenant_id}", response_model=TenantRead, dependencies=[Depends(any_operator)])
def get_tenant(
    tenant_id: str, service: TenantService = Depends(get_tenant_service)
) -> TenantRead:
    return service.get(tenant_id)


@router.post(
    "",
    response_model=TenantRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_operate)],
)
def create_tenant(
    data: TenantCreate, service: TenantService = Depends(get_tenant_service)
) -> TenantRead:
    """Register a workspace. It is created ``pending`` and serves no traffic
    until it is provisioned."""
    return service.create(data)


@router.patch(
    "/{tenant_id}", response_model=TenantRead, dependencies=[Depends(can_operate)]
)
def update_tenant(
    tenant_id: str,
    data: TenantUpdate,
    service: TenantService = Depends(get_tenant_service),
) -> TenantRead:
    return service.update(tenant_id, data)


@router.post(
    "/{tenant_id}/provision",
    response_model=ProvisionResult,
    dependencies=[Depends(can_operate)],
)
async def provision_tenant(
    tenant_id: str,
    data: TenantCreate,
    service: TenantService = Depends(get_tenant_service),
) -> ProvisionResult:
    """Create the ERPNext site and the workspace's first administrator."""
    return await service.provision(tenant_id, data)


@router.post(
    "/{tenant_id}/suspend", response_model=TenantRead, dependencies=[Depends(can_operate)]
)
def suspend_tenant(
    tenant_id: str,
    data: SuspendIn,
    service: TenantService = Depends(get_tenant_service),
) -> TenantRead:
    """Cut off access. Takes effect within the tenant app's resolver cache TTL."""
    return service.suspend(tenant_id, data.reason)


@router.post(
    "/{tenant_id}/resume", response_model=TenantRead, dependencies=[Depends(can_operate)]
)
def resume_tenant(
    tenant_id: str, service: TenantService = Depends(get_tenant_service)
) -> TenantRead:
    return service.resume(tenant_id)


@router.post(
    "/{tenant_id}/archive", response_model=TenantRead, dependencies=[Depends(can_operate)]
)
def archive_tenant(
    tenant_id: str, service: TenantService = Depends(get_tenant_service)
) -> TenantRead:
    return service.archive(tenant_id)


@router.delete("/{tenant_id}", dependencies=[Depends(owner_only)])
async def purge_tenant(
    tenant_id: str,
    confirm: str = Query(description="Repeat the workspace id to confirm"),
    service: TenantService = Depends(get_tenant_service),
) -> dict:
    """Destroy a workspace and its data. Archived workspaces only."""
    return await service.purge(tenant_id, confirm)


# --- Domains --------------------------------------------------------------
@router.post(
    "/{tenant_id}/domains", response_model=TenantRead, dependencies=[Depends(can_operate)]
)
def add_domain(
    tenant_id: str,
    data: TenantDomainCreate,
    service: TenantService = Depends(get_tenant_service),
) -> TenantRead:
    return service.add_domain(tenant_id, data.host, data.is_primary)


@router.post(
    "/{tenant_id}/domains/{host}/verify",
    response_model=TenantRead,
    dependencies=[Depends(can_operate)],
)
def verify_domain(
    tenant_id: str, host: str, service: TenantService = Depends(get_tenant_service)
) -> TenantRead:
    """Confirm the domain points at us — required before TLS is issued."""
    return service.verify_domain(tenant_id, host)


@router.delete(
    "/{tenant_id}/domains/{host}",
    response_model=TenantRead,
    dependencies=[Depends(can_operate)],
)
def remove_domain(
    tenant_id: str, host: str, service: TenantService = Depends(get_tenant_service)
) -> TenantRead:
    return service.remove_domain(tenant_id, host)
