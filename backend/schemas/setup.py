"""First-time setup schemas (Pydantic v2): opening balances the wizard posts."""

from pydantic import BaseModel, Field


class OpeningItem(BaseModel):
    """An open receivable (invoice) or payable (bill) on the start date."""
    party: str = Field(min_length=1)
    reference: str | None = None
    date: str | None = None
    due_date: str | None = None
    amount: float = Field(gt=0)


class LoanItem(BaseModel):
    lender: str = ""
    kind: str = "took"  # "took" (we borrowed) | "gave" (we lent)
    amount: float = Field(ge=0)
    rate: float | None = None
    end_date: str | None = None


class BudgetItem(BaseModel):
    category: str
    yearly: float = 0


class OpeningBalancesInput(BaseModel):
    start_date: str = Field(min_length=1)
    bank: float = 0
    cash: float = 0
    inventory_value: float = 0
    equipment_value: float = 0
    receivables: list[OpeningItem] = []
    payables: list[OpeningItem] = []
    loans: list[LoanItem] = []
    budgets: list[BudgetItem] = []


class SetupStatus(BaseModel):
    setup_complete: bool
    start_date: str = ""
    opening_ref: str = ""
    posted_at: str | None = None
