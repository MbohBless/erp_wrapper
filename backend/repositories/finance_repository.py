"""Finance data-access: summary, aged AR/AP ledgers, cash/bank books, statements.

All read from ERPNext (invoices, GL entries, query reports) through ERPNextClient.
"""

import logging
import re
from datetime import date, datetime

from integrations.erpnext import ERPNextClient
from schemas.finance import (
    AgingBuckets,
    BookEntry,
    BookResult,
    CashFlowLine,
    CashFlowResult,
    FinanceSummary,
    LedgerResult,
    LedgerRow,
    OutstandingItem,
    StatementLine,
    StatementResult,
    TrialBalanceResult,
    TrialBalanceRow,
)
from utils.mapping import to_float as _num


def _parse(d: str | None) -> date | None:
    if not d:
        return None
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _bucket(age: int) -> str:
    if age <= 0:
        return "Current"
    if age <= 30:
        return "1-30"
    if age <= 60:
        return "31-60"
    if age <= 90:
        return "61-90"
    return "90+"


log = logging.getLogger("equimed.finance")


class FinanceRepository:
    #: Rows per request when reading a set that is going to be *summed*. Small
    #: enough not to hand ERPNext an enormous query, large enough that ordinary
    #: volumes finish in one round trip.
    _PAGE = 500
    #: Runaway guard, not a limit anyone should reach. Hitting it is logged —
    #: see _fetch_all for why that matters more than the number itself.
    _CEILING = 50_000

    def __init__(self, client: ERPNextClient) -> None:
        self.client = client

    async def _fetch_all(
        self,
        doctype: str,
        *,
        fields: list[str],
        filters: list | None = None,
        order_by: str | None = None,
    ) -> list[dict]:
        """Every matching row, a page at a time.

        A single capped request is the wrong shape for anything that gets
        summed. Past the cap the total is not visibly truncated — it is simply
        *wrong*, by an amount nobody can see, on a page whose entire job is to
        be trusted. Receivables read low, and the rows dropped are whichever the
        sort put last.

        `name` is appended to the ordering because paging a non-total order is
        not safe: rows that tie can be returned in a different order per
        request, so one gets counted twice and another not at all. For a list
        that is a display glitch; for a sum it is a wrong number.
        """
        order = order_by or "name asc"
        if "name" not in order:
            order = f"{order}, name asc"

        out: list[dict] = []
        start = 0
        while start < self._CEILING:
            batch = await self.client.list_documents(
                doctype, fields=fields, filters=filters,
                limit=self._PAGE, start=start, order_by=order,
            )
            out.extend(batch)
            if len(batch) < self._PAGE:
                return out
            start += self._PAGE

        # Reaching here means the figures below are computed on a subset. Say so
        # loudly: a silently short total is the failure this method exists to
        # prevent, and swallowing it here would reintroduce it one level down.
        log.warning(
            "finance: %s hit the %d-row ceiling; totals are computed on a "
            "subset and will read low", doctype, self._CEILING,
        )
        return out

    # ------------------------------------------------------------ summary
    async def get_summary(self, as_of: date, limit: int = 8) -> FinanceSummary:
        # `outstanding_amount > 0` is applied by ERPNext, not in Python below.
        # Fetching every submitted invoice to discard the settled ones spends
        # the budget on rows that contribute nothing — and because the sort is
        # oldest-due-first, the ones that fell off the end were the newest,
        # which are exactly the ones most likely to be unpaid.
        unpaid = [["docstatus", "=", 1], ["outstanding_amount", ">", 0]]
        sales = await self._fetch_all(
            "Sales Invoice",
            fields=["name", "customer", "outstanding_amount", "due_date"],
            filters=unpaid, order_by="due_date asc",
        )
        purchases = await self._fetch_all(
            "Purchase Invoice",
            fields=["name", "supplier", "outstanding_amount", "due_date"],
            filters=unpaid, order_by="due_date asc",
        )
        today = as_of.isoformat()
        r_open = [s for s in sales if _num(s.get("outstanding_amount")) > 0]
        p_open = [p for p in purchases if _num(p.get("outstanding_amount")) > 0]
        receivables = sum(_num(s.get("outstanding_amount")) for s in r_open)
        payables = sum(_num(p.get("outstanding_amount")) for p in p_open)
        overdue = sum(_num(s.get("outstanding_amount")) for s in r_open
                      if s.get("due_date") and s["due_date"] < today)
        out_r = [OutstandingItem(party=s.get("customer") or "—", reference=s.get("name"),
                                 due_date=s.get("due_date"), amount=_num(s.get("outstanding_amount")))
                 for s in r_open][:limit]
        out_p = [OutstandingItem(party=p.get("supplier") or "—", reference=p.get("name"),
                                 due_date=p.get("due_date"), amount=_num(p.get("outstanding_amount")))
                 for p in p_open][:limit]
        return FinanceSummary(receivables=receivables, payables=payables,
                              net_position=receivables - payables, overdue_receivables=overdue,
                              outstanding_receivables=out_r, outstanding_payables=out_p)

    # ------------------------------------------------ aged AR / AP ledgers
    async def _ledger(self, doctype: str, party_field: str, as_of: date) -> LedgerResult:
        docs = await self._fetch_all(
            doctype,
            fields=["name", party_field, "posting_date", "due_date",
                    "grand_total", "outstanding_amount"],
            filters=[["docstatus", "=", 1], ["outstanding_amount", ">", 0]],
            order_by="due_date asc",
        )
        rows: list[LedgerRow] = []
        totals = AgingBuckets()
        field_map = {"Current": "current", "1-30": "d30", "31-60": "d60",
                     "61-90": "d90", "90+": "older"}
        for d in docs:
            outstanding = _num(d.get("outstanding_amount"))
            ref_date = _parse(d.get("due_date")) or _parse(d.get("posting_date"))
            age = (as_of - ref_date).days if ref_date else 0
            bucket = _bucket(age)
            rows.append(LedgerRow(party=d.get(party_field) or "—", reference=d.get("name"),
                                  posting_date=d.get("posting_date"), due_date=d.get("due_date"),
                                  grand_total=_num(d.get("grand_total")), outstanding=outstanding,
                                  age_days=max(age, 0), bucket=bucket))
            setattr(totals, field_map[bucket], getattr(totals, field_map[bucket]) + outstanding)
            totals.total += outstanding
        return LedgerResult(rows=rows, totals=totals)

    async def receivable_ledger(self, as_of: date) -> LedgerResult:
        return await self._ledger("Sales Invoice", "customer", as_of)

    async def payable_ledger(self, as_of: date) -> LedgerResult:
        return await self._ledger("Purchase Invoice", "supplier", as_of)

    # ------------------------------------------------- cash / bank books
    async def _accounts(self, account_type: str, company: str | None,
                        name_likes: tuple[str, ...] = ()) -> list[str]:
        base = [["account_type", "=", account_type], ["is_group", "=", 0]]
        if company:
            base.append(["company", "=", company])
        docs = await self.client.list_documents("Account", fields=["name"],
                                                filters=base, limit=50)
        accounts = [d["name"] for d in docs]
        if not accounts and name_likes:
            for like in name_likes:
                f = [["account_name", "like", like], ["is_group", "=", 0]]
                if company:
                    f.append(["company", "=", company])
                for d in await self.client.list_documents("Account", fields=["name"],
                                                          filters=f, limit=30):
                    accounts.append(d["name"])
        return list(dict.fromkeys(accounts))

    async def _book(self, accounts: list[str], from_date: str | None,
                    to_date: str | None) -> BookResult:
        if not accounts:
            return BookResult(accounts=[], opening=0, closing=0,
                              total_debit=0, total_credit=0, entries=[])
        filters: list = [["account", "in", accounts], ["is_cancelled", "=", 0]]
        if from_date:
            filters.append(["posting_date", ">=", from_date])
        if to_date:
            filters.append(["posting_date", "<=", to_date])
        gl = await self._fetch_all(
            "GL Entry",
            fields=["posting_date", "account", "debit", "credit", "voucher_type",
                    "voucher_no", "party", "against", "remarks"],
            filters=filters, order_by="posting_date asc, creation asc",
        )
        opening = 0.0
        if from_date:
            # The opening balance is every prior movement on these accounts.
            # Capped, it is wrong by whatever fell off — and because every
            # running balance in the book below is derived from it, one short
            # read makes the entire statement wrong rather than incomplete.
            prior = await self._fetch_all(
                "GL Entry", fields=["debit", "credit"],
                filters=[["account", "in", accounts], ["is_cancelled", "=", 0],
                         ["posting_date", "<", from_date]],
            )
            opening = sum(_num(e.get("debit")) - _num(e.get("credit")) for e in prior)
        balance = opening
        total_debit = total_credit = 0.0
        entries: list[BookEntry] = []
        for e in gl:
            debit, credit = _num(e.get("debit")), _num(e.get("credit"))
            balance += debit - credit
            total_debit += debit
            total_credit += credit
            entries.append(BookEntry(date=e.get("posting_date"), voucher_type=e.get("voucher_type"),
                                     voucher_no=e.get("voucher_no"), party=e.get("party"),
                                     against=e.get("against"), debit=debit, credit=credit,
                                     balance=balance, remarks=e.get("remarks")))
        return BookResult(accounts=accounts, opening=opening, closing=balance,
                          total_debit=total_debit, total_credit=total_credit, entries=entries)

    async def cash_book(self, company: str | None, from_date=None, to_date=None) -> BookResult:
        # SYSCOHADA doesn't tag an "account_type: Cash"; the actual cash-on-hand
        # accounts are "Caisse en …" (571x). Avoid matching "Caisse de retraite".
        accounts = await self._accounts(
            "Cash", company, name_likes=("%Caisse en%", "%Cash on Hand%", "%Petty Cash%")
        )
        return await self._book(accounts, from_date, to_date)

    async def bank_book(self, company: str | None, from_date=None, to_date=None) -> BookResult:
        accounts = await self._accounts("Bank", company, name_likes=("%Banque%", "%Bank%"))
        return await self._book(accounts, from_date, to_date)

    # ----------------------------------------------- financial statements
    async def _statement(self, report: str, title: str, company: str,
                         fiscal_year: str | None, from_date: str | None,
                         to_date: str | None, periodicity: str) -> StatementResult:
        filters: dict = {"company": company, "periodicity": periodicity}
        if fiscal_year:
            fy = await self.client.get_document("Fiscal Year", fiscal_year)
            filters.update(filter_based_on="Fiscal Year", from_fiscal_year=fiscal_year,
                           to_fiscal_year=fiscal_year,
                           period_start_date=str(fy.get("year_start_date")),
                           period_end_date=str(fy.get("year_end_date")))
        elif from_date and to_date:
            filters.update(filter_based_on="Date Range", period_start_date=from_date,
                           period_end_date=to_date)
        raw = await self.client.run_report(report, filters)
        rows: list[StatementLine] = []
        for r in raw.get("result", []):
            if not isinstance(r, dict):
                continue
            name = r.get("account_name") or r.get("account")
            if not name:
                continue
            amount = r.get("total")
            if amount is None:
                # single-period reports key the value by the period column
                for k, v in r.items():
                    if k not in ("account", "account_name", "indent", "parent_account",
                                 "currency") and isinstance(v, (int, float)):
                        amount = v
                        break
            rows.append(StatementLine(account=str(name), indent=int(r.get("indent") or 0),
                                      amount=_num(amount), is_total=not r.get("account")))
        return StatementResult(title=title, rows=rows)

    async def income_statement(self, company, fiscal_year=None, from_date=None,
                               to_date=None, periodicity="Yearly") -> StatementResult:
        return await self._statement("Profit and Loss Statement", "Income Statement",
                                     company, fiscal_year, from_date, to_date, periodicity)

    async def balance_sheet(self, company, fiscal_year=None, from_date=None,
                            to_date=None, periodicity="Yearly") -> StatementResult:
        return await self._statement("Balance Sheet", "Balance Sheet",
                                     company, fiscal_year, from_date, to_date, periodicity)

    # ------------------------------------------- trial balance & company
    async def default_company(self) -> str:
        rows = await self.client.list_documents("Company", fields=["name"], limit=1)
        return rows[0]["name"] if rows else ""

    async def account_balances(self, company: str, fiscal_year: str | None = None,
                               from_date: str | None = None, to_date: str | None = None) -> list[dict]:
        """Per-account closing balances (leaf accounts) for the period, from the
        ERPNext Trial Balance. Returns [{number, debit, credit}, ...]."""
        filters: dict = {"company": company}
        if fiscal_year:
            fy = await self.client.get_document("Fiscal Year", fiscal_year)
            filters.update(fiscal_year=fiscal_year,
                           from_date=str(fy.get("year_start_date")),
                           to_date=str(fy.get("year_end_date")))
        elif from_date and to_date:
            filters.update(from_date=from_date, to_date=to_date)
        raw = await self.client.run_report("Trial Balance", filters)
        result = raw.get("result", []) if isinstance(raw, dict) else (raw or [])
        out: list[dict] = []
        for r in result:
            if not isinstance(r, dict):
                continue
            name = str(r.get("account_name") or r.get("account") or "").strip()
            m = re.match(r"\d+", name)
            if not m:
                continue
            debit = r.get("closing_debit")
            credit = r.get("closing_credit")
            if debit is None and credit is None:
                debit, credit = r.get("debit"), r.get("credit")
            out.append({"number": m.group(0), "debit": _num(debit), "credit": _num(credit)})
        return out

    async def account_monthly(self, company: str, fiscal_year: str) -> dict[str, list[float]]:
        """Per-account net movement (debit − credit) for each of the 12 months of
        the fiscal year. Returns {account_number: [m1..m12]}."""
        fy = await self.client.get_document("Fiscal Year", fiscal_year)
        start, end = str(fy.get("year_start_date")), str(fy.get("year_end_date"))
        gl = await self._fetch_all(
            "GL Entry",
            fields=["account", "posting_date", "debit", "credit"],
            filters=[["company", "=", company], ["is_cancelled", "=", 0],
                     ["posting_date", ">=", start], ["posting_date", "<=", end]],
        )
        out: dict[str, list[float]] = {}
        for e in gl:
            m = re.match(r"\d+", str(e.get("account") or ""))
            pd = str(e.get("posting_date") or "")
            if not m or len(pd) < 7:
                continue
            month = int(pd[5:7]) - 1
            if not 0 <= month <= 11:
                continue
            out.setdefault(m.group(0), [0.0] * 12)[month] += _num(e.get("debit")) - _num(e.get("credit"))
        return out

    async def trial_balance(self, company: str, fiscal_year: str | None = None,
                            from_date: str | None = None, to_date: str | None = None) -> TrialBalanceResult:
        """Closing debit/credit for every leaf ledger account, from the ERPNext
        Trial Balance report. Group/total rows are skipped so debits and credits
        each sum without double-counting."""
        filters: dict = {"company": company}
        if fiscal_year:
            fy = await self.client.get_document("Fiscal Year", fiscal_year)
            filters.update(fiscal_year=fiscal_year,
                           from_date=str(fy.get("year_start_date")),
                           to_date=str(fy.get("year_end_date")))
        elif from_date and to_date:
            filters.update(from_date=from_date, to_date=to_date)
        raw = await self.client.run_report("Trial Balance", filters)
        result = raw.get("result", []) if isinstance(raw, dict) else (raw or [])
        rows: list[TrialBalanceRow] = []
        total_debit = total_credit = 0.0
        for r in result:
            if not isinstance(r, dict):
                continue
            if r.get("is_group") or not r.get("account"):
                continue  # skip group subtotals and the grand-total row
            name = str(r.get("account_name") or r.get("account")).strip()
            debit = _num(r.get("closing_debit") if r.get("closing_debit") is not None else r.get("debit"))
            credit = _num(r.get("closing_credit") if r.get("closing_credit") is not None else r.get("credit"))
            if not debit and not credit:
                continue
            rows.append(TrialBalanceRow(account=name, debit=debit, credit=credit))
            total_debit += debit
            total_credit += credit
        return TrialBalanceResult(rows=rows, total_debit=total_debit, total_credit=total_credit)

    async def cash_flow(self, company: str | None = None, fiscal_year: str | None = None,
                        from_date: str | None = None, to_date: str | None = None) -> CashFlowResult:
        """Direct-method statement of cash movement over the period: opening cash
        & bank balance, inflows and outflows grouped by voucher type, and the
        closing balance. Built straight from the cash and bank ledgers."""
        if fiscal_year and not (from_date and to_date):
            fy = await self.client.get_document("Fiscal Year", fiscal_year)
            from_date, to_date = str(fy.get("year_start_date")), str(fy.get("year_end_date"))
        cash = await self.cash_book(company, from_date, to_date)
        bank = await self.bank_book(company, from_date, to_date)
        inflow: dict[str, float] = {}
        outflow: dict[str, float] = {}
        for book in (cash, bank):
            for e in book.entries:
                label = e.voucher_type or "Other"
                if e.debit:
                    inflow[label] = inflow.get(label, 0.0) + e.debit
                if e.credit:
                    outflow[label] = outflow.get(label, 0.0) + e.credit
        inflows = [CashFlowLine(label=k, amount=v)
                   for k, v in sorted(inflow.items(), key=lambda kv: -kv[1])]
        outflows = [CashFlowLine(label=k, amount=v)
                    for k, v in sorted(outflow.items(), key=lambda kv: -kv[1])]
        total_in = sum(line.amount for line in inflows)
        total_out = sum(line.amount for line in outflows)
        return CashFlowResult(
            opening=cash.opening + bank.opening, closing=cash.closing + bank.closing,
            total_in=total_in, total_out=total_out, net_change=total_in - total_out,
            inflows=inflows, outflows=outflows,
        )
