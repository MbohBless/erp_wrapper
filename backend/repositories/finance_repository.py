"""Finance data-access: receivables/payables from invoices + report passthrough."""

from datetime import date

from integrations.erpnext import (
    ERPNextClient,
    get_balance_sheet,
    get_income_statement,
)
from schemas.finance import FinanceSummary, OutstandingItem
from utils.mapping import to_float as _num


class FinanceRepository:
    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def get_summary(self, as_of: date, limit: int = 8) -> FinanceSummary:
        sales = await self.client.list_documents(
            "Sales Invoice",
            fields=["name", "customer", "outstanding_amount", "due_date"],
            filters=[["docstatus", "=", 1]],
            limit=500,
            order_by="due_date asc",
        )
        purchases = await self.client.list_documents(
            "Purchase Invoice",
            fields=["name", "supplier", "outstanding_amount", "due_date"],
            filters=[["docstatus", "=", 1]],
            limit=500,
            order_by="due_date asc",
        )

        today = as_of.isoformat()
        r_open = [s for s in sales if _num(s.get("outstanding_amount")) > 0]
        p_open = [p for p in purchases if _num(p.get("outstanding_amount")) > 0]

        receivables = sum(_num(s.get("outstanding_amount")) for s in r_open)
        payables = sum(_num(p.get("outstanding_amount")) for p in p_open)
        overdue = sum(
            _num(s.get("outstanding_amount"))
            for s in r_open
            if s.get("due_date") and s["due_date"] < today
        )

        out_receivables = [
            OutstandingItem(
                party=s.get("customer") or "—",
                reference=s.get("name"),
                due_date=s.get("due_date"),
                amount=_num(s.get("outstanding_amount")),
            )
            for s in r_open
        ][:limit]
        out_payables = [
            OutstandingItem(
                party=p.get("supplier") or "—",
                reference=p.get("name"),
                due_date=p.get("due_date"),
                amount=_num(p.get("outstanding_amount")),
            )
            for p in p_open
        ][:limit]

        return FinanceSummary(
            receivables=receivables,
            payables=payables,
            net_position=receivables - payables,
            overdue_receivables=overdue,
            outstanding_receivables=out_receivables,
            outstanding_payables=out_payables,
        )

    async def income_statement(self, **kwargs) -> dict:
        return await get_income_statement(self.client, **kwargs)

    async def balance_sheet(self, **kwargs) -> dict:
        return await get_balance_sheet(self.client, **kwargs)
