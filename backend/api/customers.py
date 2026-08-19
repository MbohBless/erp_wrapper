"""Customer endpoints with RBAC. Thin controllers — logic lives in CustomerService.

Access policy (Administrator is always allowed):
  - view (list/get):  Manager, Sales, Accountant
  - manage (write):   Manager, Sales
"""

from fastapi import APIRouter, Depends, status

from api.deps import get_customer_service, require_roles
from models.user import Role
from schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["customers"])

can_view = require_roles(Role.MANAGER, Role.SALES, Role.ACCOUNTANT)
can_manage = require_roles(Role.MANAGER, Role.SALES)


@router.get("", response_model=list[CustomerRead], dependencies=[Depends(can_view)])
async def list_customers(
    search: str | None = None,
    customer_type: str | None = None,
    group: str | None = None,
    disabled: bool | None = None,
    limit: int = 50,
    start: int = 0,
    service: CustomerService = Depends(get_customer_service),
) -> list[CustomerRead]:
    return await service.list(search, customer_type, group, disabled, limit, start)


@router.post(
    "",
    response_model=CustomerRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_manage)],
)
async def create_customer(
    data: CustomerCreate,
    service: CustomerService = Depends(get_customer_service),
) -> CustomerRead:
    return await service.create(data)


@router.get(
    "/{customer_id}", response_model=CustomerRead, dependencies=[Depends(can_view)]
)
async def get_customer(
    customer_id: str,
    service: CustomerService = Depends(get_customer_service),
) -> CustomerRead:
    return await service.get(customer_id)


@router.put(
    "/{customer_id}", response_model=CustomerRead, dependencies=[Depends(can_manage)]
)
async def update_customer(
    customer_id: str,
    data: CustomerUpdate,
    service: CustomerService = Depends(get_customer_service),
) -> CustomerRead:
    return await service.update(customer_id, data)


@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(can_manage)],
)
async def delete_customer(
    customer_id: str,
    service: CustomerService = Depends(get_customer_service),
) -> None:
    await service.delete(customer_id)
