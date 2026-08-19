"""Budget schemas (Pydantic v2): editable monthly lines + budget-vs-actual."""

from pydantic import BaseModel, Field


class BudgetLineIn(BaseModel):
    category: str = Field(min_length=1)
    account_prefix: str = Field(min_length=1)
    months: list[float] = Field(default_factory=lambda: [0.0] * 12)  # Jan..Dec


class BudgetSaveIn(BaseModel):
    fiscal_year: str = Field(min_length=1)
    lines: list[BudgetLineIn] = []


class BudgetLineRead(BaseModel):
    category: str
    account_prefix: str
    kind: str                       # "income" | "expense"
    months_budget: list[float]      # 12 planned amounts
    months_actual: list[float]      # 12 actuals from the ledger
    budget: float                   # yearly total budget
    actual: float                   # yearly total actual
    variance: float                 # budget − actual
    pct: float                      # actual as % of budget


class BudgetReport(BaseModel):
    fiscal_year: str
    lines: list[BudgetLineRead]
    total_budget: float
    total_actual: float
