"""Budget business logic: save monthly budget lines, compute budget-vs-actual.

Per-month actuals come from the ERPNext GL, aggregated by SYSCOHADA account
prefix. Class 7 accounts (produits) are income; everything else is expense, so
the actual is taken with the matching sign.
"""

from repositories.budget_repository import BudgetRepository
from schemas.budget import BudgetLineRead, BudgetReport, BudgetSaveIn
from services.finance_service import FinanceService


def _r(x: float) -> float:
    return round(x, 2)


class BudgetService:
    def __init__(self, finance: FinanceService, repo: BudgetRepository) -> None:
        self.finance = finance
        self.repo = repo

    def save(self, data: BudgetSaveIn) -> None:
        self.repo.replace_lines(
            data.fiscal_year,
            [(l.category, l.account_prefix, l.months) for l in data.lines],
        )

    async def report(self, fiscal_year: str) -> BudgetReport:
        lines = self.repo.get_lines(fiscal_year)
        company = await self.finance.default_company()
        monthly = await self.finance.account_monthly(company, fiscal_year) if company else {}

        out: list[BudgetLineRead] = []
        total_budget = total_actual = 0.0
        for category, prefix, months_budget in lines:
            income = prefix[:1] == "7"
            months_actual = [0.0] * 12
            for number, nets in monthly.items():
                if number.startswith(prefix):
                    for i in range(12):
                        months_actual[i] += (-nets[i]) if income else nets[i]
            months_actual = [_r(x) for x in months_actual]
            months_budget = [_r(x) for x in months_budget]
            y_budget = _r(sum(months_budget))
            y_actual = _r(sum(months_actual))
            pct = _r(y_actual / y_budget * 100) if y_budget else 0.0
            out.append(BudgetLineRead(
                category=category, account_prefix=prefix,
                kind="income" if income else "expense",
                months_budget=months_budget, months_actual=months_actual,
                budget=y_budget, actual=y_actual, variance=_r(y_budget - y_actual), pct=pct,
            ))
            total_budget += y_budget
            total_actual += y_actual

        return BudgetReport(fiscal_year=fiscal_year, lines=out,
                            total_budget=_r(total_budget), total_actual=_r(total_actual))
