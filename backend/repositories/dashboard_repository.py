"""Dashboard aggregation, reading from several ERPNext DocTypes.

Read-only: totals and recent activity assembled in Python from ERPNext lists.
"""

from datetime import date, timedelta

from integrations.erpnext import ERPNextClient
from schemas.dashboard import (
    ActivityItem,
    DashboardSummary,
    ExpiringBatch,
    LowStockItem,
    RevenueSegment,
    TrendPoint,
)
from utils.mapping import to_float as _num


class DashboardRepository:
    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def _revenue_segments(
        self, sales: list[dict], top_n: int = 4
    ) -> tuple[list[RevenueSegment], RevenueSegment | None]:
        """Split revenue across ERPNext Customer Groups, plus the top customer.

        Everything beyond `top_n` groups is folded into "Other" rather than
        dropped, so the percentages always add up to what was actually invoiced.
        """
        by_customer: dict[str, float] = {}
        for s in sales:
            name = s.get("customer")
            if name:
                by_customer[name] = by_customer.get(name, 0.0) + _num(s.get("grand_total"))
        total = sum(by_customer.values())
        if not by_customer or total <= 0:
            return [], None

        groups: dict[str, str] = {}
        try:
            docs = await self.client.list_documents(
                "Customer",
                fields=["name", "customer_group"],
                filters=[["name", "in", sorted(by_customer)]],
                limit=len(by_customer),
            )
            groups = {d.get("name"): d.get("customer_group") for d in docs if d.get("name")}
        except Exception:  # noqa: BLE001 - fall back to one bucket, never fail the dashboard
            groups = {}

        by_group: dict[str, float] = {}
        for customer, amount in by_customer.items():
            label = groups.get(customer) or "Ungrouped"
            by_group[label] = by_group.get(label, 0.0) + amount

        ordered = sorted(by_group.items(), key=lambda kv: kv[1], reverse=True)
        head, tail = ordered[:top_n], ordered[top_n:]
        if tail:
            head.append(("Other", sum(amount for _, amount in tail)))

        segments = [
            RevenueSegment(label=label, amount=amount, pct=round(amount / total * 100, 1))
            for label, amount in head
        ]
        best_name, best_amount = max(by_customer.items(), key=lambda kv: kv[1])
        top = RevenueSegment(
            label=best_name,
            amount=best_amount,
            pct=round(best_amount / total * 100, 1),
        )
        return segments, top

    async def _item_names(self, item_codes: list[str]) -> dict[str, str]:
        """Map item codes to display names. Best-effort: a failed lookup costs
        a nicer label, not the dashboard."""
        if not item_codes:
            return {}
        try:
            docs = await self.client.list_documents(
                "Item",
                fields=["name", "item_name"],
                filters=[["name", "in", item_codes]],
                limit=len(item_codes),
            )
        except Exception:  # noqa: BLE001 - the panel degrades to codes only
            return {}
        return {d.get("name"): d.get("item_name") for d in docs if d.get("name")}

    async def get_summary(
        self,
        as_of: date,
        trend_days: int = 7,
        low_stock_threshold: float = 10,
        recent_limit: int = 8,
        expiry_horizon_days: int = 180,
        panel_limit: int = 5,
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
        # Batches expiring within the horizon, soonest first. Filtered in
        # ERPNext rather than in Python so a large catalogue does not have to
        # cross the wire just to be discarded.
        horizon = (as_of + timedelta(days=expiry_horizon_days)).isoformat()
        batches = await self.client.list_documents(
            "Batch",
            fields=["name", "batch_id", "item", "expiry_date", "batch_qty"],
            filters=[
                ["expiry_date", "is", "set"],
                ["expiry_date", "<=", horizon],
                ["expiry_date", ">=", as_of.isoformat()],
            ],
            limit=100,
            order_by="expiry_date asc",
        )

        today = as_of.isoformat()
        revenue_today = sum(
            _num(s.get("grand_total")) for s in sales if s.get("posting_date") == today
        )
        outstanding_customers = sum(_num(s.get("outstanding_amount")) for s in sales)
        outstanding_suppliers = sum(_num(p.get("outstanding_amount")) for p in purchases)
        inventory_value = sum(_num(b.get("stock_value")) for b in bins)
        low_bins = [
            b for b in bins if _num(b.get("actual_qty")) <= low_stock_threshold
        ]
        low_stock_count = len(low_bins)

        # Resolve item names for just the rows the panels will show — one
        # lookup for the union, rather than N calls or none at all.
        shown_bins = sorted(low_bins, key=lambda b: _num(b.get("actual_qty")))[:panel_limit]
        shown_batches = batches[:panel_limit]
        item_codes = {b.get("item_code") for b in shown_bins if b.get("item_code")}
        item_codes |= {b.get("item") for b in shown_batches if b.get("item")}
        names = await self._item_names(sorted(c for c in item_codes if c))

        low_stock_items = [
            LowStockItem(
                item_code=b.get("item_code") or "",
                item_name=names.get(b.get("item_code")),
                warehouse=b.get("warehouse") or "",
                actual_qty=_num(b.get("actual_qty")),
                threshold=low_stock_threshold,
            )
            for b in shown_bins
        ]

        expiring_batches = [
            ExpiringBatch(
                batch_id=b.get("batch_id") or b.get("name") or "",
                item_code=b.get("item") or "",
                item_name=names.get(b.get("item")),
                qty=_num(b.get("batch_qty")) if b.get("batch_qty") is not None else None,
                expiry_date=b.get("expiry_date"),
                days_left=(date.fromisoformat(b["expiry_date"]) - as_of).days,
            )
            for b in shown_batches
            if b.get("expiry_date")
        ]

        # Revenue by customer group, and the single biggest customer. Both are
        # derived from submitted invoices — no invented splits.
        revenue_by_segment, top_customer = await self._revenue_segments(sales)

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
            low_stock_items=low_stock_items,
            expiring_batches=expiring_batches,
            revenue_by_segment=revenue_by_segment,
            top_customer=top_customer,
        )
