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


class LowStockItem(BaseModel):
    item_code: str
    item_name: str | None = None
    warehouse: str
    actual_qty: float
    threshold: float


class ExpiringBatch(BaseModel):
    batch_id: str
    item_code: str
    item_name: str | None = None
    qty: float | None = None
    expiry_date: str
    days_left: int


class RevenueSegment(BaseModel):
    label: str
    amount: float
    pct: float


class DashboardSummary(BaseModel):
    revenue_today: float
    outstanding_customers: float
    outstanding_suppliers: float
    inventory_value: float
    low_stock_count: int
    revenue_trend: list[TrendPoint]
    recent_activity: list[ActivityItem]
    # Item-level detail behind the counts. Empty is a legitimate answer and the
    # UI renders an empty state for it — these panels previously showed
    # hardcoded sample rows, which is indistinguishable from real data to a
    # user looking at their own dashboard.
    low_stock_items: list[LowStockItem] = []
    expiring_batches: list[ExpiringBatch] = []
    # Revenue grouped by ERPNext Customer Group. Previously a hardcoded
    # 52/26/14/8 split, which looked like analysis and was invention.
    revenue_by_segment: list[RevenueSegment] = []
    top_customer: RevenueSegment | None = None
