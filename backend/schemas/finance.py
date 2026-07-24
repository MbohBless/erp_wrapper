"""Finance schemas (Pydantic V2): receivables/payables summary + report passthrough."""

from pydantic import BaseModel


class OutstandingItem(BaseModel):
    party: str
    reference: str
    due_date: str | None = None
    amount: float


class FinanceSummary(BaseModel):
    receivables: float
    payables: float
    net_position: float
    overdue_receivables: float
    outstanding_receivables: list[OutstandingItem]
    outstanding_payables: list[OutstandingItem]
