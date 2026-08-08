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
    """A dashboard, already filtered for the requesting user's role.

    The money fields are ``None`` — not zero — for roles that may not see them.
    Zero is a legitimate business value ("no revenue today"), so it cannot also
    mean "withheld"; the UI has to be able to tell those apart to decide between
    rendering ``0 XAF`` and hiding the card entirely.

    See ``services/dashboard_service.VISIBLE_FIELDS`` for the policy, and note it
    is applied server-side: the payload for a Store Keeper never contains the
    company's receivables, so hiding the card is presentation, not protection.
    """

    revenue_today: float | None = None
    outstanding_customers: float | None = None
    outstanding_suppliers: float | None = None
    inventory_value: float | None = None
    low_stock_count: int
    revenue_trend: list[TrendPoint] | None = None
    recent_activity: list[ActivityItem] | None = None
    # Item-level detail behind the counts. Empty is a legitimate answer and the
    # UI renders an empty state for it — these panels previously showed
    # hardcoded sample rows, which is indistinguishable from real data to a
    # user looking at their own dashboard.
    low_stock_items: list[LowStockItem] = []
    expiring_batches: list[ExpiringBatch] = []
    # Revenue grouped by ERPNext Customer Group. Previously a hardcoded
    # 52/26/14/8 split, which looked like analysis and was invention.
    revenue_by_segment: list[RevenueSegment] | None = None
    top_customer: RevenueSegment | None = None
