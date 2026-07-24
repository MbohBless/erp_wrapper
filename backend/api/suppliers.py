"""Supplier endpoints with RBAC. Thin controllers — logic lives in SupplierService.

Access policy (Administrator is always allowed):
  - view (list/get):   Manager, Accountant, Store Keeper
  - manage (write):    Manager
"""

from fastapi import APIRouter, Depends, status

from api.deps import get_supplier_service, require_roles
from models.user import Role
from schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate
from services.supplier_service import SupplierService

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

can_view = require_roles(Role.MANAGER, Role.ACCOUNTANT, Role.STORE_KEEPER)
can_manage = require_roles(Role.MANAGER)


@router.get("", response_model=list[SupplierRead], dependencies=[Depends(can_view)])
async def list_suppliers(
    search: str | None = None,
    supplier_type: str | None = None,
    group: str | None = None,
    limit: int = 20,
    start: int = 0,
    service: SupplierService = Depends(get_supplier_service),
) -> list[SupplierRead]:
    return await service.list(search, supplier_type, group, limit, start)


@router.post(
    "",
    response_model=SupplierRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_manage)],
)
async def create_supplier(
    data: SupplierCreate,
    service: SupplierService = Depends(get_supplier_service),
) -> SupplierRead:
    return await service.create(data)


@router.get(
    "/{supplier_id}", response_model=SupplierRead, dependencies=[Depends(can_view)]
)
async def get_supplier(
    supplier_id: str,
    service: SupplierService = Depends(get_supplier_service),
) -> SupplierRead:
    return await service.get(supplier_id)


@router.put(
    "/{supplier_id}", response_model=SupplierRead, dependencies=[Depends(can_manage)]
)
async def update_supplier(
    supplier_id: str,
    data: SupplierUpdate,
    service: SupplierService = Depends(get_supplier_service),
) -> SupplierRead:
    return await service.update(supplier_id, data)


@router.delete(
    "/{supplier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(can_manage)],
)
async def delete_supplier(
    supplier_id: str,
    service: SupplierService = Depends(get_supplier_service),
) -> None:
    await service.delete(supplier_id)
