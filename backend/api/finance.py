"""Finance endpoints with RBAC. Thin controllers — logic in FinanceService.

Access (Administrator always allowed): Manager, Accountant.
"""

from fastapi import APIRouter, Depends

from api.deps import get_finance_service, require_roles
from models.user import Role
from schemas.finance import FinanceSummary
from services.finance_service import FinanceService

router = APIRouter(prefix="/finance", tags=["finance"])

can_view = require_roles(Role.MANAGER, Role.ACCOUNTANT)


@router.get("/summary", response_model=FinanceSummary, dependencies=[Depends(can_view)])
async def finance_summary(
    service: FinanceService = Depends(get_finance_service),
) -> FinanceSummary:
    return await service.get_summary()


@router.get("/reports/income-statement", dependencies=[Depends(can_view)])
async def income_statement(
    company: str,
    fiscal_year: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    periodicity: str = "Yearly",
    service: FinanceService = Depends(get_finance_service),
) -> dict:
    return await service.income_statement(
        company, fiscal_year, from_date, to_date, periodicity
    )


@router.get("/reports/balance-sheet", dependencies=[Depends(can_view)])
async def balance_sheet(
    company: str,
    fiscal_year: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    periodicity: str = "Yearly",
    service: FinanceService = Depends(get_finance_service),
) -> dict:
    return await service.balance_sheet(
        company, fiscal_year, from_date, to_date, periodicity
    )
