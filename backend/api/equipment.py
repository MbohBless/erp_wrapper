"""Equipment endpoints with RBAC. Thin controllers — logic in EquipmentService.

Access (Administrator always allowed):
  - view (list/get):  Manager, Biomedical Engineer, Sales, Store Keeper
  - manage (write):   Manager, Biomedical Engineer
"""

from fastapi import APIRouter, Depends, status

from api.deps import get_equipment_service, require_roles
from models.user import Role
from schemas.equipment import (
    EquipmentCreate,
    EquipmentRead,
    EquipmentUpdate,
    InstallRequest,
)
from services.equipment_service import EquipmentService

router = APIRouter(prefix="/equipment", tags=["equipment"])

can_view = require_roles(
    Role.MANAGER, Role.BIOMEDICAL_ENGINEER, Role.SALES, Role.STORE_KEEPER
)
can_manage = require_roles(Role.MANAGER, Role.BIOMEDICAL_ENGINEER)


@router.get("", response_model=list[EquipmentRead], dependencies=[Depends(can_view)])
async def list_equipment(
    search: str | None = None,
    status: str | None = None,
    customer: str | None = None,
    limit: int = 50,
    start: int = 0,
    service: EquipmentService = Depends(get_equipment_service),
) -> list[EquipmentRead]:
    return await service.list(search, status, customer, limit, start)


@router.post(
    "",
    response_model=EquipmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_manage)],
)
async def register_equipment(
    data: EquipmentCreate,
    service: EquipmentService = Depends(get_equipment_service),
) -> EquipmentRead:
    return await service.create(data)


@router.get(
    "/{equipment_id}", response_model=EquipmentRead, dependencies=[Depends(can_view)]
)
async def get_equipment(
    equipment_id: str,
    service: EquipmentService = Depends(get_equipment_service),
) -> EquipmentRead:
    return await service.get(equipment_id)


@router.put(
    "/{equipment_id}", response_model=EquipmentRead, dependencies=[Depends(can_manage)]
)
async def update_equipment(
    equipment_id: str,
    data: EquipmentUpdate,
    service: EquipmentService = Depends(get_equipment_service),
) -> EquipmentRead:
    return await service.update(equipment_id, data)


@router.post(
    "/{equipment_id}/install",
    response_model=EquipmentRead,
    dependencies=[Depends(can_manage)],
)
async def install_equipment(
    equipment_id: str,
    data: InstallRequest,
    service: EquipmentService = Depends(get_equipment_service),
) -> EquipmentRead:
    return await service.install(equipment_id, data)


@router.delete(
    "/{equipment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(can_manage)],
)
async def delete_equipment(
    equipment_id: str,
    service: EquipmentService = Depends(get_equipment_service),
) -> None:
    await service.delete(equipment_id)
