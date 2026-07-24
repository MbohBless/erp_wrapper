"""Maintenance ticket endpoints with RBAC. Thin controllers — logic in MaintenanceService.

Access (Administrator always allowed):
  - view (list/get):  Manager, Biomedical Engineer, Sales
  - manage (write):   Manager, Biomedical Engineer
"""

from fastapi import APIRouter, Depends, status

from api.deps import get_maintenance_service, require_roles
from models.user import Role
from schemas.maintenance import (
    CompleteRequest,
    MaintenanceCreate,
    MaintenanceRead,
    MaintenanceUpdate,
)
from services.maintenance_service import MaintenanceService

router = APIRouter(prefix="/maintenance", tags=["maintenance"])

can_view = require_roles(Role.MANAGER, Role.BIOMEDICAL_ENGINEER, Role.SALES)
can_manage = require_roles(Role.MANAGER, Role.BIOMEDICAL_ENGINEER)


@router.get("", response_model=list[MaintenanceRead], dependencies=[Depends(can_view)])
async def list_tickets(
    search: str | None = None,
    status: str | None = None,
    engineer: str | None = None,
    limit: int = 50,
    start: int = 0,
    service: MaintenanceService = Depends(get_maintenance_service),
) -> list[MaintenanceRead]:
    return await service.list(search, status, engineer, limit, start)


@router.post(
    "",
    response_model=MaintenanceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_manage)],
)
async def create_ticket(
    data: MaintenanceCreate,
    service: MaintenanceService = Depends(get_maintenance_service),
) -> MaintenanceRead:
    return await service.create(data)


@router.get(
    "/{ticket_id}", response_model=MaintenanceRead, dependencies=[Depends(can_view)]
)
async def get_ticket(
    ticket_id: str,
    service: MaintenanceService = Depends(get_maintenance_service),
) -> MaintenanceRead:
    return await service.get(ticket_id)


@router.put(
    "/{ticket_id}", response_model=MaintenanceRead, dependencies=[Depends(can_manage)]
)
async def update_ticket(
    ticket_id: str,
    data: MaintenanceUpdate,
    service: MaintenanceService = Depends(get_maintenance_service),
) -> MaintenanceRead:
    return await service.update(ticket_id, data)


@router.post(
    "/{ticket_id}/complete",
    response_model=MaintenanceRead,
    dependencies=[Depends(can_manage)],
)
async def complete_ticket(
    ticket_id: str,
    data: CompleteRequest,
    service: MaintenanceService = Depends(get_maintenance_service),
) -> MaintenanceRead:
    return await service.complete(ticket_id, data)


@router.delete(
    "/{ticket_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(can_manage)],
)
async def delete_ticket(
    ticket_id: str,
    service: MaintenanceService = Depends(get_maintenance_service),
) -> None:
    await service.delete(ticket_id)
