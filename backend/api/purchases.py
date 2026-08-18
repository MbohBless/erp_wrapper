"""Purchase invoice endpoints with RBAC. Thin controllers — logic in PurchaseService.

Access (Administrator always allowed):
  - view (list/get):  Manager, Accountant, Store Keeper
  - create:           Manager
  - amend (edit):     Manager
"""

from fastapi import APIRouter, Depends, status

from api.deps import get_purchase_service, require_roles
from models.user import Role
from schemas.purchases import (
    PurchaseInvoiceCreate,
    PurchaseInvoiceRead,
    PurchaseInvoiceUpdate,
)
from services.purchase_service import PurchaseService

router = APIRouter(prefix="/purchases", tags=["purchases"])

can_view = require_roles(Role.MANAGER, Role.ACCOUNTANT, Role.STORE_KEEPER)
can_manage = require_roles(Role.MANAGER)
can_amend = require_roles(Role.MANAGER)


@router.get("", response_model=list[PurchaseInvoiceRead], dependencies=[Depends(can_view)])
async def list_purchases(
    search: str | None = None,
    status: str | None = None,
    limit: int = 50,
    start: int = 0,
    service: PurchaseService = Depends(get_purchase_service),
) -> list[PurchaseInvoiceRead]:
    return await service.list(search, status, limit, start)


@router.post(
    "",
    response_model=PurchaseInvoiceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_manage)],
)
async def create_purchase(
    data: PurchaseInvoiceCreate,
    service: PurchaseService = Depends(get_purchase_service),
) -> PurchaseInvoiceRead:
    return await service.create(data)


@router.get(
    "/{bill_id}", response_model=PurchaseInvoiceRead, dependencies=[Depends(can_view)]
)
async def get_purchase(
    bill_id: str,
    service: PurchaseService = Depends(get_purchase_service),
) -> PurchaseInvoiceRead:
    return await service.get(bill_id)


@router.put(
    "/{bill_id}", response_model=PurchaseInvoiceRead, dependencies=[Depends(can_amend)]
)
async def update_purchase(
    bill_id: str,
    data: PurchaseInvoiceUpdate,
    service: PurchaseService = Depends(get_purchase_service),
) -> PurchaseInvoiceRead:
    """Correct a posted bill by cancelling it and re-posting the correction.

    The response is the *replacement*, whose id differs from the one in the path
    ("<bill_id>-1").
    """
    return await service.update(bill_id, data)
