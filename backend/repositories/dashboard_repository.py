"""Dashboard aggregation, reading from several ERPNext DocTypes.

Read-only: totals and recent activity assembled in Python from ERPNext lists.
"""

from datetime import date, timedelta

from integrations.erpnext import ERPNextClient
from schemas.dashboard import ActivityItem, DashboardSummary, TrendPoint
from utils.mapping import to_float as _num


class DashboardRepository:
    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def get_summary(
        self,
        as_of: date,
        trend_days: int = 7,
        low_stock_threshold: float = 10,
        recent_limit: int = 8,
    ) -> DashboardSummary:
        sales = await self.client.list_documents(
            "Sales Invoice",
            fields=["name", "customer", "grand_total", "outstanding_amount", "posting_date"],
            filters=[["docstatus", "=", 1]],
            limit=500,
            order_by="posting_date desc",
        )
        purchases = await self.client.list_documents(
            "Purchase Invoice",
            fields=["name", "supplier", "grand_total", "outstanding_amount", "posting_date"],
            filters=[["docstatus", "=", 1]],
            limit=500,
            order_by="posting_date desc",
        )
        payments = await self.client.list_documents(
            "Payment Entry",
            fields=["name", "party", "paid_amount", "posting_date", "payment_type"],
            filters=[["docstatus", "=", 1]],
            limit=200,
            order_by="posting_date desc",
        )
        bins = await self.client.list_documents(
            "Bin",
            fields=["item_code", "warehouse", "actual_qty", "stock_value"],
            limit=1000,
        )

        today = as_of.isoformat()
        revenue_today = sum(
            _num(s.get("grand_total")) for s in sales if s.get("posting_date") == today
        )
        outstanding_customers = sum(_num(s.get("outstanding_amount")) for s in sales)
        outstanding_suppliers = sum(_num(p.get("outstanding_amount")) for p in purchases)
        inventory_value = sum(_num(b.get("stock_value")) for b in bins)
        low_stock_count = sum(
            1 for b in bins if _num(b.get("actual_qty")) <= low_stock_threshold
        )

        # Revenue trend (oldest -> newest) over the last `trend_days` days.
        days = [
            as_of - timedelta(days=offset) for offset in range(trend_days - 1, -1, -1)
        ]
        trend = [
            TrendPoint(
                date=day.isoformat(),
                amount=sum(
                    _num(s.get("grand_total"))
                    for s in sales
                    if s.get("posting_date") == day.isoformat()
                ),
            )
            for day in days
        ]

        # Recent activity across sales, purchases and payments.
        activity: list[ActivityItem] = []
        for s in sales[:recent_limit]:
            activity.append(
                ActivityItem(
                    type="Sales Invoice",
                    reference=s.get("name"),
                    party=s.get("customer"),
                    amount=_num(s.get("grand_total")),
                    date=s.get("posting_date"),
                )
            )
        for p in purchases[:recent_limit]:
            activity.append(
                ActivityItem(
                    type="Purchase Invoice",
                    reference=p.get("name"),
                    party=p.get("supplier"),
                    amount=_num(p.get("grand_total")),
                    date=p.get("posting_date"),
                )
            )
        for pay in payments[:recent_limit]:
            activity.append(
                ActivityItem(
                    type="Payment",
                    reference=pay.get("name"),
                    party=pay.get("party"),
                    amount=_num(pay.get("paid_amount")),
                    date=pay.get("posting_date"),
                )
            )
        activity.sort(key=lambda a: a.date or "", reverse=True)

        return DashboardSummary(
            revenue_today=revenue_today,
            outstanding_customers=outstanding_customers,
            outstanding_suppliers=outstanding_suppliers,
            inventory_value=inventory_value,
            low_stock_count=low_stock_count,
            revenue_trend=trend,
            recent_activity=activity[:recent_limit],
        )
