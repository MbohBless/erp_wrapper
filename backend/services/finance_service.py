"""Finance business logic: receivables/payables summary + financial statements."""

from datetime import date

from repositories.finance_repository import FinanceRepository
from schemas.finance import FinanceSummary


class FinanceService:
    def __init__(self, repo: FinanceRepository) -> None:
        self.repo = repo

    async def get_summary(self) -> FinanceSummary:
        return await self.repo.get_summary(date.today())

    async def income_statement(
        self,
        company: str,
        fiscal_year: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        periodicity: str = "Yearly",
    ) -> dict:
        return await self.repo.income_statement(
            company=company,
            fiscal_year=fiscal_year,
            from_date=from_date,
            to_date=to_date,
            periodicity=periodicity,
        )

    async def balance_sheet(
        self,
        company: str,
        fiscal_year: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        periodicity: str = "Yearly",
    ) -> dict:
        return await self.repo.balance_sheet(
            company=company,
            fiscal_year=fiscal_year,
            from_date=from_date,
            to_date=to_date,
            periodicity=periodicity,
        )
