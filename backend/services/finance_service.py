"""Finance business logic: summary, AR/AP ledgers, cash/bank books, statements."""

from datetime import date

from repositories.finance_repository import FinanceRepository
from schemas.finance import (
    BookResult,
    FinanceSummary,
    LedgerResult,
    StatementResult,
)
from schemas.ohada import OhadaStatement
from services.ohada_service import (
    bilan,
    compte_de_resultat,
    etat_annexe,
    tableau_flux,
)


class FinanceService:
    def __init__(self, repo: FinanceRepository) -> None:
        self.repo = repo

    async def get_summary(self) -> FinanceSummary:
        return await self.repo.get_summary(date.today())

    async def receivable_ledger(self) -> LedgerResult:
        return await self.repo.receivable_ledger(date.today())

    async def payable_ledger(self) -> LedgerResult:
        return await self.repo.payable_ledger(date.today())

    async def cash_book(
        self, company: str | None = None, from_date: str | None = None, to_date: str | None = None
    ) -> BookResult:
        return await self.repo.cash_book(company, from_date, to_date)

    async def bank_book(
        self, company: str | None = None, from_date: str | None = None, to_date: str | None = None
    ) -> BookResult:
        return await self.repo.bank_book(company, from_date, to_date)

    async def income_statement(
        self, company: str, fiscal_year=None, from_date=None, to_date=None, periodicity="Yearly"
    ) -> StatementResult:
        return await self.repo.income_statement(company, fiscal_year, from_date, to_date, periodicity)

    async def balance_sheet(
        self, company: str, fiscal_year=None, from_date=None, to_date=None, periodicity="Yearly"
    ) -> StatementResult:
        return await self.repo.balance_sheet(company, fiscal_year, from_date, to_date, periodicity)

    # ---- OHADA / SYSCOHADA statutory statements ----
    async def ohada_income_statement(
        self, company: str, fiscal_year=None, from_date=None, to_date=None, regime=None
    ) -> OhadaStatement:
        accounts = await self.repo.trial_balance(company, fiscal_year, from_date, to_date)
        return compte_de_resultat(accounts, fiscal_year, regime)

    async def ohada_balance_sheet(
        self, company: str, fiscal_year=None, from_date=None, to_date=None, regime=None
    ) -> OhadaStatement:
        accounts = await self.repo.trial_balance(company, fiscal_year, from_date, to_date)
        return bilan(accounts, fiscal_year, regime)

    async def ohada_cash_flow(
        self, company: str, fiscal_year=None, from_date=None, to_date=None, regime=None
    ) -> OhadaStatement:
        book = await self.repo.treasury_book(company, fiscal_year, from_date, to_date)
        return tableau_flux(book, fiscal_year)

    async def ohada_etat_annexe(
        self, company: str, fiscal_year=None, from_date=None, to_date=None, regime=None
    ) -> OhadaStatement:
        accounts = await self.repo.trial_balance(company, fiscal_year, from_date, to_date)
        return etat_annexe(accounts, fiscal_year)
