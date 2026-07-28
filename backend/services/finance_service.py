"""Finance business logic: summary, AR/AP ledgers, cash/bank books, statements."""

from datetime import date

from repositories.finance_repository import FinanceRepository
from schemas.finance import (
    BookResult,
    FinanceSummary,
    LedgerResult,
    StatementResult,
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

    async def default_company(self) -> str:
        return await self.repo.default_company()

    async def account_balances(self, company, fiscal_year=None, from_date=None, to_date=None) -> list[dict]:
        return await self.repo.account_balances(company, fiscal_year, from_date, to_date)

    async def account_monthly(self, company, fiscal_year) -> dict:
        return await self.repo.account_monthly(company, fiscal_year)
