"""Tests for the Finance module (summary aggregation, reports, RBAC)."""

from datetime import date

from repositories.finance_repository import FinanceRepository
from tests.fakes import FakeERPNextClient
from services.finance_service import FinanceService
from tests.conftest import auth_header


class FinanceStub:
    """Stands in for ERPNext, honouring the parts finance actually depends on.

    It applies filters and respects limit/start. Both matter: the repository
    pages through anything it is going to sum, and it asks ERPNext to exclude
    settled invoices rather than filtering them in Python. A stub that returned
    everything on every call would let both of those regress unnoticed.
    """

    def __init__(self, data: dict) -> None:
        self.data = data
        self.last_report = None
        #: Every list call, so a test can assert what was asked of ERPNext
        #: rather than only what came back.
        self.calls: list[dict] = []

    async def list_documents(
        self, doctype, fields=None, filters=None, limit=20, start=0, order_by=None
    ):
        self.calls.append({"doctype": doctype, "filters": filters,
                           "limit": limit, "start": start, "order_by": order_by})
        rows = [d for d in self.data.get(doctype, [])
                if FakeERPNextClient._matches(d, filters)]
        return rows[start : start + limit]

    async def get_document(self, doctype, name):
        return {"year_start_date": "2026-01-01", "year_end_date": "2026-12-31"}

    async def run_report(self, report_name, filters=None):
        self.last_report = {"report_name": report_name, "filters": filters or {}}
        return {"report_name": report_name, "result": []}


AS_OF = date(2026, 9, 24)
DATA = {
    "Sales Invoice": [
        {"name": "SI-1", "docstatus": 1, "customer": "CHU Yaoundé", "outstanding_amount": 5000, "due_date": "2026-09-10"},  # overdue
        {"name": "SI-2", "docstatus": 1, "customer": "Clinique", "outstanding_amount": 3000, "due_date": "2026-10-30"},
        {"name": "SI-3", "docstatus": 1, "customer": "Paid Co", "outstanding_amount": 0, "due_date": "2026-09-01"},
    ],
    "Purchase Invoice": [
        {"name": "PI-1", "docstatus": 1, "supplier": "Sanofi", "outstanding_amount": 4000, "due_date": "2026-10-05"},
    ],
}


async def test_summary_totals_and_overdue():
    repo = FinanceRepository(FinanceStub(DATA))
    s = await repo.get_summary(AS_OF)
    assert s.receivables == 8000  # 5000 + 3000 (0 excluded)
    assert s.payables == 4000
    assert s.net_position == 4000
    assert s.overdue_receivables == 5000  # only SI-1 (due before AS_OF)
    assert {r.party for r in s.outstanding_receivables} == {"CHU Yaoundé", "Clinique"}
    assert s.outstanding_payables[0].party == "Sanofi"


async def test_reports_call_correct_erpnext_reports():
    stub = FinanceStub({})
    repo = FinanceRepository(stub)
    await repo.income_statement(company="Equimed", fiscal_year="2026")
    assert stub.last_report["report_name"] == "Profit and Loss Statement"
    await repo.balance_sheet(company="Equimed", fiscal_year="2026")
    assert stub.last_report["report_name"] == "Balance Sheet"


def test_summary_endpoint(client, admin_token):
    from api import deps
    from main import app

    stub = FinanceStub(DATA)
    app.dependency_overrides[deps.get_finance_service] = lambda: FinanceService(
        FinanceRepository(stub)
    )
    try:
        resp = client.get("/finance/summary", headers=auth_header(admin_token))
        assert resp.status_code == 200, resp.text
        assert resp.json()["receivables"] == 8000
    finally:
        app.dependency_overrides.pop(deps.get_finance_service, None)


# --- RBAC ---


def test_accountant_can_view(client, make_token, fake_erpnext):
    token = make_token("Accountant")
    assert client.get("/finance/summary", headers=auth_header(token)).status_code == 200


def test_sales_cannot_view_finance(client, make_token, fake_erpnext):
    token = make_token("Sales")
    assert client.get("/finance/summary", headers=auth_header(token)).status_code == 403


def test_unauthenticated_rejected(client, fake_erpnext):
    assert client.get("/finance/summary").status_code == 401


# --- Totals must cover everything, not one page of it --------------------
#
# These are the tests for the failure that has no symptom: past a capped fetch
# the receivables figure is not visibly truncated, it is just smaller than the
# truth, on the one screen whose whole job is to be believed.


def _open_invoices(n: int, each: float = 1000.0) -> dict:
    return {
        "Sales Invoice": [
            {"name": f"SI-{i}", "docstatus": 1, "customer": f"Client {i}",
             "outstanding_amount": each, "due_date": "2026-10-01"}
            for i in range(n)
        ]
    }


async def test_summary_sums_every_open_invoice_not_just_the_first_page():
    stub = FinanceStub(_open_invoices(12))
    repo = FinanceRepository(stub)
    repo._PAGE = 5  # three pages: 5 + 5 + 2

    s = await repo.get_summary(AS_OF)
    assert s.receivables == 12000, "the total stopped at a page boundary"
    assert len([c for c in stub.calls if c["doctype"] == "Sales Invoice"]) == 3


async def test_summary_asks_erpnext_to_exclude_settled_invoices():
    """Rather than fetching them and dropping them here. Spending the page
    budget on invoices that contribute nothing is what put the cliff within
    reach — and the sort being oldest-due-first meant the rows that fell off
    were the newest, which are the most likely to still be owed."""
    stub = FinanceStub(_open_invoices(1))
    await FinanceRepository(stub).get_summary(AS_OF)

    sent = [c["filters"] for c in stub.calls if c["doctype"] == "Sales Invoice"][0]
    assert ["outstanding_amount", ">", 0] in sent
    assert ["docstatus", "=", 1] in sent


async def test_paged_reads_are_ordered_by_something_unique():
    """Paging a non-total order is not safe. Rows that tie can come back in a
    different order per request, so one is counted twice and another not at all
    — a display glitch in a list, a wrong number in a sum."""
    stub = FinanceStub(_open_invoices(1))
    await FinanceRepository(stub).get_summary(AS_OF)

    for call in stub.calls:
        assert "name" in (call["order_by"] or ""), call


async def test_a_settled_invoice_is_not_counted():
    stub = FinanceStub({
        "Sales Invoice": [
            {"name": "SI-1", "docstatus": 1, "customer": "Owing",
             "outstanding_amount": 4000, "due_date": "2026-10-01"},
            {"name": "SI-2", "docstatus": 1, "customer": "Settled",
             "outstanding_amount": 0, "due_date": "2026-10-01"},
        ]
    })
    s = await FinanceRepository(stub).get_summary(AS_OF)
    assert s.receivables == 4000
    assert [r.party for r in s.outstanding_receivables] == ["Owing"]


async def test_the_aged_ledger_totals_cover_every_page():
    stub = FinanceStub(_open_invoices(9, each=500))
    repo = FinanceRepository(stub)
    repo._PAGE = 4

    led = await repo.receivable_ledger(AS_OF)
    assert len(led.rows) == 9
    assert led.totals.total == 4500


async def test_the_opening_balance_covers_every_prior_entry():
    """Every running balance in the cash book is derived from it, so a short
    read makes the whole statement wrong rather than merely incomplete."""
    stub = FinanceStub({
        "Account": [{"name": "Caisse - QBS", "account_type": "Cash",
                     "is_group": 0, "account_name": "Caisse en francs"}],
        "GL Entry": [
            {"posting_date": "2025-12-01", "account": "Caisse - QBS",
             "debit": 100, "credit": 0, "is_cancelled": 0}
            for _ in range(7)
        ],
    })
    repo = FinanceRepository(stub)
    repo._PAGE = 2  # four pages of prior entries

    book = await repo.cash_book(company=None, from_date="2026-01-01",
                                to_date="2026-12-31")
    assert book.opening == 700, "the opening balance stopped at a page boundary"
