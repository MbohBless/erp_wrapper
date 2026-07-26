"""Finance endpoints with RBAC. Thin controllers — logic in FinanceService.

Access (Administrator always allowed): Manager, Accountant.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_finance_service, require_roles
from database import get_db
from models.user import Role
from repositories.company_repository import CompanyRepository
from schemas.finance import (
    BookResult,
    FinanceSummary,
    LedgerResult,
    StatementResult,
)
from schemas.ohada import OhadaStatement
from services.finance_service import FinanceService

router = APIRouter(prefix="/finance", tags=["finance"])

can_view = require_roles(Role.MANAGER, Role.ACCOUNTANT)


def _default_regime(db: Session = Depends(get_db)) -> str:
    """The OHADA regime stored on the company profile (query param overrides)."""
    return CompanyRepository(db).get().ohada_regime


@router.get("/summary", response_model=FinanceSummary, dependencies=[Depends(can_view)])
async def finance_summary(service: FinanceService = Depends(get_finance_service)) -> FinanceSummary:
    return await service.get_summary()


@router.get("/receivable", response_model=LedgerResult, dependencies=[Depends(can_view)])
async def receivable_ledger(service: FinanceService = Depends(get_finance_service)) -> LedgerResult:
    return await service.receivable_ledger()


@router.get("/payable", response_model=LedgerResult, dependencies=[Depends(can_view)])
async def payable_ledger(service: FinanceService = Depends(get_finance_service)) -> LedgerResult:
    return await service.payable_ledger()


@router.get("/cash-book", response_model=BookResult, dependencies=[Depends(can_view)])
async def cash_book(
    company: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    service: FinanceService = Depends(get_finance_service),
) -> BookResult:
    return await service.cash_book(company, from_date, to_date)


@router.get("/bank-book", response_model=BookResult, dependencies=[Depends(can_view)])
async def bank_book(
    company: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    service: FinanceService = Depends(get_finance_service),
) -> BookResult:
    return await service.bank_book(company, from_date, to_date)


@router.get(
    "/reports/income-statement", response_model=StatementResult, dependencies=[Depends(can_view)]
)
async def income_statement(
    company: str,
    fiscal_year: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    periodicity: str = "Yearly",
    service: FinanceService = Depends(get_finance_service),
) -> StatementResult:
    return await service.income_statement(company, fiscal_year, from_date, to_date, periodicity)


@router.get(
    "/reports/balance-sheet", response_model=StatementResult, dependencies=[Depends(can_view)]
)
async def balance_sheet(
    company: str,
    fiscal_year: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    periodicity: str = "Yearly",
    service: FinanceService = Depends(get_finance_service),
) -> StatementResult:
    return await service.balance_sheet(company, fiscal_year, from_date, to_date, periodicity)


@router.get(
    "/reports/ohada/compte-de-resultat",
    response_model=OhadaStatement,
    dependencies=[Depends(can_view)],
)
async def ohada_income_statement(
    company: str,
    fiscal_year: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    regime: str | None = None,
    default_regime: str = Depends(_default_regime),
    service: FinanceService = Depends(get_finance_service),
) -> OhadaStatement:
    """OHADA — Compte de résultat (regime from the company profile unless overridden)."""
    return await service.ohada_income_statement(
        company, fiscal_year, from_date, to_date, regime or default_regime
    )


@router.get(
    "/reports/ohada/bilan",
    response_model=OhadaStatement,
    dependencies=[Depends(can_view)],
)
async def ohada_balance_sheet(
    company: str,
    fiscal_year: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    regime: str | None = None,
    default_regime: str = Depends(_default_regime),
    service: FinanceService = Depends(get_finance_service),
) -> OhadaStatement:
    """OHADA — Bilan (regime from the company profile unless overridden)."""
    return await service.ohada_balance_sheet(
        company, fiscal_year, from_date, to_date, regime or default_regime
    )


@router.get(
    "/reports/ohada/flux-de-tresorerie",
    response_model=OhadaStatement,
    dependencies=[Depends(can_view)],
)
async def ohada_cash_flow(
    company: str,
    fiscal_year: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    service: FinanceService = Depends(get_finance_service),
) -> OhadaStatement:
    """OHADA — Tableau des Flux de Trésorerie (méthode directe)."""
    return await service.ohada_cash_flow(company, fiscal_year, from_date, to_date)


@router.get(
    "/reports/ohada/etat-annexe",
    response_model=OhadaStatement,
    dependencies=[Depends(can_view)],
)
async def ohada_etat_annexe(
    company: str,
    fiscal_year: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    service: FinanceService = Depends(get_finance_service),
) -> OhadaStatement:
    """OHADA — État annexé (notes annexes, principales notes)."""
    return await service.ohada_etat_annexe(company, fiscal_year, from_date, to_date)
