"""Sales invoice endpoints with RBAC. Thin controllers — logic in SalesService.

Access (Administrator always allowed):
  - view (list/get):  Manager, Sales, Accountant
  - create:           Manager, Sales, Accountant
  - amend (edit):     Manager

Amending is narrower than creating on purpose: it cancels a posted invoice and
re-posts it under a new number, which moves money that is already in the ledger.
"""

from fastapi import APIRouter, Depends, status

from api.deps import get_sales_service, require_roles
from models.user import Role
from schemas.sales import SalesInvoiceCreate, SalesInvoiceRead, SalesInvoiceUpdate
from services.sales_service import SalesService

router = APIRouter(prefix="/sales", tags=["sales"])

can_view = require_roles(Role.MANAGER, Role.SALES, Role.ACCOUNTANT)
can_manage = require_roles(Role.MANAGER, Role.SALES, Role.ACCOUNTANT)
can_amend = require_roles(Role.MANAGER)


@router.get("", response_model=list[SalesInvoiceRead], dependencies=[Depends(can_view)])
async def list_invoices(
    search: str | None = None,
    status: str | None = None,
    limit: int = 50,
    start: int = 0,
    service: SalesService = Depends(get_sales_service),
) -> list[SalesInvoiceRead]:
    return await service.list(search, status, limit, start)


@router.post(
    "",
    response_model=SalesInvoiceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_manage)],
)
async def create_invoice(
    data: SalesInvoiceCreate,
    service: SalesService = Depends(get_sales_service),
) -> SalesInvoiceRead:
    return await service.create(data)


@router.get(
    "/{invoice_id}", response_model=SalesInvoiceRead, dependencies=[Depends(can_view)]
)
async def get_invoice(
    invoice_id: str,
    service: SalesService = Depends(get_sales_service),
) -> SalesInvoiceRead:
    return await service.get(invoice_id)


@router.put(
    "/{invoice_id}", response_model=SalesInvoiceRead, dependencies=[Depends(can_amend)]
)
async def update_invoice(
    invoice_id: str,
    data: SalesInvoiceUpdate,
    service: SalesService = Depends(get_sales_service),
) -> SalesInvoiceRead:
    """Correct a posted invoice by cancelling it and re-posting the correction.

    The response is the *replacement*, which has a different id from the one in
    the path ("<invoice_id>-1"). Clients must read the id back rather than
    assume the invoice they edited is the invoice they now hold.
    """
    return await service.update(invoice_id, data)
