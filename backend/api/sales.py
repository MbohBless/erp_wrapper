"""Sales invoice endpoints with RBAC. Thin controllers — logic in SalesService.

Access (Administrator always allowed):
  - view (list/get):  Manager, Sales, Accountant
  - create:           Manager, Sales
"""

from fastapi import APIRouter, Depends, status

from api.deps import get_sales_service, require_roles
from models.user import Role
from schemas.sales import SalesInvoiceCreate, SalesInvoiceRead
from services.sales_service import SalesService

router = APIRouter(prefix="/sales", tags=["sales"])

can_view = require_roles(Role.MANAGER, Role.SALES, Role.ACCOUNTANT)
can_manage = require_roles(Role.MANAGER, Role.SALES)


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
