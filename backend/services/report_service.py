"""Assembles report data into branded, digitally-signed PDF documents.

Reuses the existing finance/inventory services for data, renders a professional
letterhead via ``utils.pdf_report`` and signs the result via ``utils.pdf_signing``.
"""

from __future__ import annotations

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from services.finance_service import FinanceService
from services.inventory_service import InventoryService
from utils.pdf_report import Column, ReportDoc, render_report_pdf
from utils.pdf_signing import sign_pdf

_LOW_STOCK_THRESHOLD = 10

REPORT_TITLES = {
    "receivables": "Outstanding Receivables",
    "payables": "Outstanding Payables",
    "current-stock": "Current Stock",
    "low-stock": "Low Stock",
    "income-statement": "Income Statement",
    "balance-sheet": "Balance Sheet",
    "compte-de-resultat": "Compte de Résultat (OHADA)",
    "bilan": "Bilan (OHADA)",
    "flux-de-tresorerie": "Tableau des Flux de Trésorerie (OHADA)",
    "etat-annexe": "État Annexé (OHADA)",
}

_OHADA_KEYS = ("compte-de-resultat", "bilan", "flux-de-tresorerie", "etat-annexe")


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
    ) -> None:
        self.finance = finance
        self.inventory = inventory
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

        if key in ("receivables", "payables"):
            doc = await self._outstanding(key, base_meta)
        elif key in ("current-stock", "low-stock"):
            doc = await self._stock(key, warehouse, base_meta)
        elif key in ("income-statement", "balance-sheet"):
            doc = await self._statement(key, company, fiscal_year, from_date, to_date, base_meta)
        elif key in _OHADA_KEYS:
            doc = await self._ohada(key, company, fiscal_year, from_date, to_date, base_meta)
        else:
            raise HTTPException(status_code=404, detail=f"Unknown report '{key}'")

        location = ", ".join(
            p for p in [self.profile.get("city"), self.profile.get("country")] if p
        ) or "Cameroon"
        org_name = self.profile.get("legal_name") or "EquiMed"

        def _render_and_sign() -> bytes:
            # reportlab + pyHanko are synchronous (pyHanko's signer calls
            # asyncio.run internally), so run off the event loop.
            pdf = render_report_pdf(self.profile, doc)
            return sign_pdf(
                pdf,
                reason=f"Certified {doc.title}",
                location=location,
                org_name=org_name,
            )

        signed = await run_in_threadpool(_render_and_sign)
        filename = f"{key}-{(fiscal_year or '').strip() or 'current'}.pdf".replace(" ", "-")
        return filename, signed

    # ---- builders -------------------------------------------------------
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

    async def _ohada(self, key, company, fiscal_year, from_date, to_date, base_meta) -> ReportDoc:
        if not company:
            raise HTTPException(status_code=422, detail="`company` is required for this report.")
        regime = self.profile.get("ohada_regime") or "Système Normal"
        fn = {
            "compte-de-resultat": self.finance.ohada_income_statement,
            "bilan": self.finance.ohada_balance_sheet,
            "flux-de-tresorerie": self.finance.ohada_cash_flow,
            "etat-annexe": self.finance.ohada_etat_annexe,
        }[key]
        if key in ("compte-de-resultat", "bilan"):
            stmt = await fn(company, fiscal_year, from_date, to_date, regime)
        else:
            stmt = await fn(company, fiscal_year, from_date, to_date)
        meta = list(base_meta)
        meta.append(("Entité", company))
        if key in ("compte-de-resultat", "bilan"):
            meta.append(("Régime", regime))
        if fiscal_year:
            meta.append(("Exercice", fiscal_year))
        elif from_date or to_date:
            meta.append(("Période", f"{from_date or '…'} → {to_date or '…'}"))
        rows: list[list[str]] = []
        indents: list[int] = []
        bold: set[int] = set()
        for i, ln in enumerate(stmt.lines):
            label = (f"{ln.code}  " if ln.code else "") + ln.label
            amount = "" if ln.kind in ("header", "note") else _money(ln.amount, self.currency)
            rows.append([label, amount])
            indents.append(ln.level)
            if ln.kind in ("header", "subtotal", "total"):
                bold.add(i)
        return ReportDoc(
            title=stmt.title,
            subtitle=stmt.subtitle,
            meta=meta,
            columns=[Column("Libellé", width=4.6), Column("Montant (XAF)", align="right", width=1.6)],
            rows=rows,
            indents=indents,
            bold_rows=bold,
            footnote="Présentation OHADA · Système Normal, lignes principales, établie à partir "
            "de la balance SYSCOHADA (les reclassements par solde sont simplifiés).",
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
            subtitle="Prepared from the ERPNext general ledger (SYSCOHADA).",
            meta=meta,
            columns=[Column("Account", width=4.2), Column("Amount", align="right", width=1.8)],
            rows=rows,
            indents=indents,
            bold_rows=bold_rows,
            footnote="Figures are as posted in ERPNext for the selected period.",
        )
