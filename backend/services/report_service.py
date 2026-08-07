"""Assembles report data into branded, digitally-signed PDF documents.

Reuses the existing finance/inventory services for data, renders a professional
letterhead via ``utils.pdf_report`` and signs the result via ``utils.pdf_signing``.
"""

from __future__ import annotations

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from services.dashboard_service import DashboardService
from services.finance_service import FinanceService
from services.inventory_service import InventoryService
from utils.pdf_report import Column, ReportDoc, render_report_pdf
from tenancy import current_tenant_or_none
from utils.pdf_signing import sign_pdf

_LOW_STOCK_THRESHOLD = 10

REPORT_TITLES = {
    "receivables": "Outstanding Receivables",
    "payables": "Outstanding Payables",
    "current-stock": "Current Stock",
    "low-stock": "Low Stock",
    "income-statement": "Income Statement",
    "balance-sheet": "Balance Sheet",
    "trial-balance": "Trial Balance",
    "cash-flow": "Cash Flow Statement",
    "dashboard": "Dashboard Summary",
}


def _money(value: float, currency: str) -> str:
    symbol = "FCFA" if currency.upper() in ("XAF", "FCFA") else currency.upper()
    return f"{int(round(value)):,}".replace(",", " ") + f" {symbol}"


def _qty(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}"


class ReportService:
    def __init__(
        self,
        finance: FinanceService,
        inventory: InventoryService,
        profile: dict,
        dashboard: DashboardService | None = None,
    ) -> None:
        self.finance = finance
        self.inventory = inventory
        self.dashboard = dashboard
        self.profile = profile
        self.currency = profile.get("currency") or "XAF"

    async def generate_pdf(
        self,
        key: str,
        *,
        company: str | None = None,
        fiscal_year: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        warehouse: str | None = None,
        generated_by: str = "",
        generated_at: str = "",
    ) -> tuple[str, bytes]:
        base_meta: list[tuple[str, str]] = []
        if generated_at:
            base_meta.append(("Generated", generated_at))
        if generated_by:
            base_meta.append(("By", generated_by))

        if key == "dashboard":
            doc = await self._dashboard(base_meta)
        elif key in ("receivables", "payables"):
            doc = await self._outstanding(key, base_meta)
        elif key in ("current-stock", "low-stock"):
            doc = await self._stock(key, warehouse, base_meta)
        elif key in ("income-statement", "balance-sheet"):
            doc = await self._statement(key, company, fiscal_year, from_date, to_date, base_meta)
        elif key == "trial-balance":
            doc = await self._trial_balance(company, fiscal_year, from_date, to_date, base_meta)
        elif key == "cash-flow":
            doc = await self._cash_flow(company, fiscal_year, from_date, to_date, base_meta)
        else:
            raise HTTPException(status_code=404, detail=f"Unknown report '{key}'")

        location = ", ".join(
            p for p in [self.profile.get("city"), self.profile.get("country")] if p
        ) or "Cameroon"
        # Signing identity comes from the tenant's own legal name — never a
        # product default, and never shared between tenants.
        org_name = (
            self.profile.get("legal_name")
            or self.profile.get("display_name")
            or "Reporting"
        )
        tenant_id = current_tenant_or_none()
        tenant_id = tenant_id.id if tenant_id else "default"

        def _render_and_sign() -> bytes:
            # reportlab + pyHanko are synchronous (pyHanko's signer calls
            # asyncio.run internally), so run off the event loop.
            pdf = render_report_pdf(self.profile, doc)
            return sign_pdf(
                pdf,
                reason=f"Certified {doc.title}",
                location=location,
                org_name=org_name,
                tenant_id=tenant_id,
            )

        signed = await run_in_threadpool(_render_and_sign)
        filename = f"{key}-{(fiscal_year or '').strip() or 'current'}.pdf".replace(" ", "-")
        return filename, signed

    # ---- builders -------------------------------------------------------
    async def _dashboard(self, base_meta) -> ReportDoc:
        if self.dashboard is None:
            raise HTTPException(status_code=500, detail="Dashboard data is unavailable.")
        s = await self.dashboard.get_summary()
        cur = self.currency
        rows: list[list[str]] = [
            ["Revenue today", _money(s.revenue_today, cur)],
            ["Outstanding — customers", _money(s.outstanding_customers, cur)],
            ["Outstanding — suppliers", _money(s.outstanding_suppliers, cur)],
            ["Inventory value", _money(s.inventory_value, cur)],
            ["Low-stock items", str(s.low_stock_count)],
        ]
        bold: set[int] = set()
        if s.recent_activity:
            rows.append(["Recent activity", ""])
            bold.add(len(rows) - 1)
            for a in s.recent_activity[:12]:
                label = f"{a.type} {a.reference}" + (f" · {a.party}" if a.party else "")
                rows.append([label, _money(a.amount, cur)])
        return ReportDoc(
            title=REPORT_TITLES["dashboard"],
            subtitle="Key figures as at the generation date.",
            meta=base_meta,
            columns=[Column("Item", width=4.2), Column("Amount", align="right", width=1.8)],
            rows=rows,
            bold_rows=bold,
            footnote="Aggregated from ERPNext invoices, payments and stock at generation time.",
        )

    async def _outstanding(self, key: str, base_meta) -> ReportDoc:
        summary = await self.finance.get_summary()
        if key == "receivables":
            items, total, party_label = summary.outstanding_receivables, summary.receivables, "Customer"
        else:
            items, total, party_label = summary.outstanding_payables, summary.payables, "Supplier"
        rows = [
            [it.party, it.reference, it.due_date or "—", _money(it.amount, self.currency)]
            for it in items
        ]
        return ReportDoc(
            title=REPORT_TITLES[key],
            subtitle=f"{len(rows)} open item(s) as at the generation date.",
            meta=base_meta,
            columns=[
                Column(party_label, width=2.6),
                Column("Reference", width=2.0),
                Column("Due date", width=1.4),
                Column("Amount", align="right", width=1.6),
            ],
            rows=rows,
            total_label="Total",
            total_value=_money(total, self.currency),
            footnote="Amounts reflect unpaid balances recorded in ERPNext at generation time.",
        )

    async def _stock(self, key: str, warehouse: str | None, base_meta) -> ReportDoc:
        levels = await self.inventory.get_stock_levels(warehouse=warehouse)
        if key == "low-stock":
            levels = [s for s in levels if s.actual_qty <= _LOW_STOCK_THRESHOLD]
        meta = list(base_meta)
        if warehouse:
            meta.append(("Warehouse", warehouse))
        rows = [[s.item_code, s.warehouse, _qty(s.actual_qty)] for s in levels]
        subtitle = (
            f"Items at or below {_LOW_STOCK_THRESHOLD} units."
            if key == "low-stock"
            else "On-hand quantities per item and warehouse."
        )
        return ReportDoc(
            title=REPORT_TITLES[key],
            subtitle=subtitle,
            meta=meta,
            columns=[
                Column("Product", width=2.8),
                Column("Warehouse", width=2.4),
                Column("On-hand qty", align="right", width=1.4),
            ],
            rows=rows,
            footnote="Source: ERPNext Bin (actual quantity).",
        )

    async def _statement(self, key, company, fiscal_year, from_date, to_date, base_meta) -> ReportDoc:
        if not company:
            raise HTTPException(status_code=422, detail="`company` is required for this report.")
        fn = self.finance.income_statement if key == "income-statement" else self.finance.balance_sheet
        result = await fn(company, fiscal_year, from_date, to_date, "Yearly")
        meta = list(base_meta)
        meta.append(("Company", company))
        if fiscal_year:
            meta.append(("Fiscal year", fiscal_year))
        elif from_date or to_date:
            meta.append(("Period", f"{from_date or '…'} → {to_date or '…'}"))
        rows = [[r.account, _money(r.amount, self.currency)] for r in result.rows]
        indents = [r.indent for r in result.rows]
        bold_rows = {i for i, r in enumerate(result.rows) if r.is_total}
        return ReportDoc(
            title=result.title or REPORT_TITLES[key],
            subtitle="Prepared from the ERPNext general ledger.",
            meta=meta,
            columns=[Column("Account", width=4.2), Column("Amount", align="right", width=1.8)],
            rows=rows,
            indents=indents,
            bold_rows=bold_rows,
            footnote="Figures are as posted in ERPNext for the selected period.",
        )

    async def _period_meta(self, company, fiscal_year, from_date, to_date, base_meta) -> list:
        if not company:
            raise HTTPException(status_code=422, detail="`company` is required for this report.")
        meta = list(base_meta)
        meta.append(("Company", company))
        if fiscal_year:
            meta.append(("Fiscal year", fiscal_year))
        elif from_date or to_date:
            meta.append(("Period", f"{from_date or '…'} → {to_date or '…'}"))
        return meta

    async def _trial_balance(self, company, fiscal_year, from_date, to_date, base_meta) -> ReportDoc:
        meta = await self._period_meta(company, fiscal_year, from_date, to_date, base_meta)
        tb = await self.finance.trial_balance(company, fiscal_year, from_date, to_date)
        cur = self.currency
        rows = [[r.account, _money(r.debit, cur), _money(r.credit, cur)] for r in tb.rows]
        rows.append(["Total", _money(tb.total_debit, cur), _money(tb.total_credit, cur)])
        return ReportDoc(
            title=REPORT_TITLES["trial-balance"],
            subtitle="Closing debit and credit balance for every ledger account.",
            meta=meta,
            columns=[
                Column("Account", width=3.6),
                Column("Debit", align="right", width=1.4),
                Column("Credit", align="right", width=1.4),
            ],
            rows=rows,
            bold_rows={len(rows) - 1},
            footnote="Closing balances from the ERPNext Trial Balance for the selected period.",
        )

    async def _cash_flow(self, company, fiscal_year, from_date, to_date, base_meta) -> ReportDoc:
        meta = await self._period_meta(company, fiscal_year, from_date, to_date, base_meta)
        cf = await self.finance.cash_flow(company, fiscal_year, from_date, to_date)
        cur = self.currency
        rows: list[list[str]] = [["Opening cash & bank balance", _money(cf.opening, cur)]]
        bold: set[int] = {0}
        rows.append(["Cash received", ""])
        bold.add(len(rows) - 1)
        for line in cf.inflows:
            rows.append([f"    {line.label}", _money(line.amount, cur)])
        rows.append(["Total received", _money(cf.total_in, cur)])
        bold.add(len(rows) - 1)
        rows.append(["Cash paid out", ""])
        bold.add(len(rows) - 1)
        for line in cf.outflows:
            rows.append([f"    {line.label}", _money(line.amount, cur)])
        rows.append(["Total paid", _money(cf.total_out, cur)])
        bold.add(len(rows) - 1)
        rows.append(["Net cash movement", _money(cf.net_change, cur)])
        bold.add(len(rows) - 1)
        rows.append(["Closing cash & bank balance", _money(cf.closing, cur)])
        bold.add(len(rows) - 1)
        return ReportDoc(
            title=REPORT_TITLES["cash-flow"],
            subtitle="Direct-method cash movement over the period (cash & bank).",
            meta=meta,
            columns=[Column("Item", width=4.6), Column("Amount", align="right", width=1.8)],
            rows=rows,
            bold_rows=bold,
            footnote="Built from cash and bank ledger movements posted in ERPNext.",
        )
