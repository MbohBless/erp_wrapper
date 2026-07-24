"""Dashboard summary schemas (Pydantic V2)."""

from pydantic import BaseModel


class TrendPoint(BaseModel):
    date: str
    amount: float


class ActivityItem(BaseModel):
    type: str  # "Sales Invoice" | "Purchase Invoice" | "Payment"
    reference: str
    party: str | None = None
    amount: float
    date: str | None = None


class DashboardSummary(BaseModel):
    revenue_today: float
    outstanding_customers: float
    outstanding_suppliers: float
    inventory_value: float
    low_stock_count: int
    revenue_trend: list[TrendPoint]
    recent_activity: list[ActivityItem]
