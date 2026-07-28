"""Budget endpoints: editable budget lines + budget-vs-actual report.

Access (Administrator always allowed): Manager, Accountant.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import require_roles
from database import get_db
from integrations.erpnext import ERPNextClient, get_erpnext_client
from models.user import Role
from repositories.budget_repository import BudgetRepository
from repositories.finance_repository import FinanceRepository
from schemas.budget import BudgetReport, BudgetSaveIn
from services.budget_service import BudgetService
from services.finance_service import FinanceService

router = APIRouter(prefix="/budget", tags=["budget"])

can_manage = require_roles(Role.MANAGER, Role.ACCOUNTANT)


def get_budget_service(
    client: ERPNextClient = Depends(get_erpnext_client),
    db: Session = Depends(get_db),
) -> BudgetService:
    return BudgetService(FinanceService(FinanceRepository(client)), BudgetRepository(db))


def _current_fy() -> str:
    return str(datetime.now(timezone.utc).year)


@router.get("", response_model=BudgetReport, dependencies=[Depends(can_manage)])
async def get_budget(
    fiscal_year: str | None = None,
    service: BudgetService = Depends(get_budget_service),
) -> BudgetReport:
    return await service.report(fiscal_year or _current_fy())


@router.put("", response_model=BudgetReport, dependencies=[Depends(can_manage)])
async def save_budget(
    data: BudgetSaveIn,
    service: BudgetService = Depends(get_budget_service),
) -> BudgetReport:
    service.save(data)
    return await service.report(data.fiscal_year)
