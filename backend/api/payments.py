"""Payment endpoints with RBAC. Thin controllers — logic in PaymentService.

Access (Administrator always allowed): Manager, Accountant.
"""

from fastapi import APIRouter, Depends, status

from api.deps import get_payment_service, require_roles
from models.user import Role
from schemas.payments import PaymentPay, PaymentRead, PaymentReceive
from services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])

can_view = require_roles(Role.MANAGER, Role.ACCOUNTANT)
can_manage = require_roles(Role.MANAGER, Role.ACCOUNTANT)


@router.get("", response_model=list[PaymentRead], dependencies=[Depends(can_view)])
async def list_payments(
    limit: int = 50,
    start: int = 0,
    service: PaymentService = Depends(get_payment_service),
) -> list[PaymentRead]:
    return await service.list(limit, start)


@router.post(
    "/receive",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_manage)],
)
async def receive_payment(
    data: PaymentReceive,
    service: PaymentService = Depends(get_payment_service),
) -> PaymentRead:
    return await service.receive(data)


@router.post(
    "/pay",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(can_manage)],
)
async def make_payment(
    data: PaymentPay,
    service: PaymentService = Depends(get_payment_service),
) -> PaymentRead:
    return await service.pay(data)
