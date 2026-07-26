"""Tests for the accounting endpoints: AR/AP ledgers, cash/bank books,
statements, and payments."""

from datetime import date

from repositories.finance_repository import FinanceRepository
from tests.conftest import auth_header


class FinStub:
    def __init__(self, data=None, report=None, fy=None):
        self.data = data or {}
        self.report = report or {}
        self.fy = fy or {"year_start_date": "2026-01-01", "year_end_date": "2026-12-31"}

    async def list_documents(self, doctype, fields=None, filters=None, limit=20, start=0, order_by=None):
        return self.data.get(doctype, [])

    async def get_document(self, doctype, name):
        return self.fy

    async def run_report(self, report_name, filters=None):
        self.last_filters = filters
        return self.report


AS_OF = date(2026, 9, 24)


async def test_receivable_ledger_aging():
    data = {
        "Sales Invoice": [
            {"name": "SI-1", "customer": "A", "posting_date": "2026-09-20", "due_date": "2026-09-30", "grand_total": 1000, "outstanding_amount": 1000},  # current
            {"name": "SI-2", "customer": "B", "posting_date": "2026-08-01", "due_date": "2026-09-10", "grand_total": 500, "outstanding_amount": 500},   # 14 days -> 1-30
            {"name": "SI-3", "customer": "C", "posting_date": "2026-06-01", "due_date": "2026-06-15", "grand_total": 800, "outstanding_amount": 800},   # 100 days -> 90+
        ]
    }
    repo = FinanceRepository(FinStub(data))
    led = await repo.receivable_ledger(AS_OF)
    assert len(led.rows) == 3
    assert led.totals.current == 1000
    assert led.totals.d30 == 500
    assert led.totals.older == 800
    assert led.totals.total == 2300
    buckets = {r.reference: r.bucket for r in led.rows}
    assert buckets["SI-1"] == "Current" and buckets["SI-3"] == "90+"


async def test_bank_book_running_balance():
    data = {
        "Account": [{"name": "Bank - E"}],
        "GL Entry": [
            {"posting_date": "2026-09-01", "debit": 1000, "credit": 0, "voucher_type": "Payment Entry", "voucher_no": "PE-1"},
            {"posting_date": "2026-09-05", "debit": 0, "credit": 400, "voucher_type": "Payment Entry", "voucher_no": "PE-2"},
        ],
    }
    repo = FinanceRepository(FinStub(data))
    book = await repo.bank_book(company="EquiMed")
    assert book.accounts == ["Bank - E"]
    assert [e.balance for e in book.entries] == [1000, 600]
    assert book.closing == 600
    assert book.total_debit == 1000 and book.total_credit == 400


async def test_income_statement_normalisation():
    report = {
        "result": [
            {"account": "70", "account_name": "Sales", "indent": 1, "total": 3000},
            {"account_name": "Total Income", "indent": 0, "total": 3000},
            "some string row",
        ]
    }
    repo = FinanceRepository(FinStub(report=report))
    stmt = await repo.income_statement("EquiMed", fiscal_year="2026")
    assert stmt.title == "Income Statement"
    assert len(stmt.rows) == 2
    assert stmt.rows[0].account == "Sales" and stmt.rows[0].amount == 3000
    assert stmt.rows[1].is_total is True  # no `account` key -> a total row
    # fiscal-year dates were resolved and passed to the report
    assert repo.client.last_filters["from_fiscal_year"] == "2026"
    assert repo.client.last_filters["period_start_date"] == "2026-01-01"


# --- endpoint RBAC (via the in-memory fake) ---
def test_receivable_endpoint_rbac(client, make_token, fake_erpnext):
    acct = make_token("Accountant")
    assert client.get("/finance/receivable", headers=auth_header(acct)).status_code == 200
    sales = make_token("Sales")
    assert client.get("/finance/receivable", headers=auth_header(sales)).status_code == 403


def test_payment_receive_and_rbac(client, admin_token, make_token, fake_erpnext):
    # Accountant can record a receipt.
    acct = make_token("Accountant")
    resp = client.post("/payments/receive", json={"invoice_id": "SI-X"}, headers=auth_header(acct))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["payment_type"] == "Receive"
    assert body["paid_amount"] == 1000
    # It was submitted in ERPNext.
    assert fake_erpnext.store[body["id"]]["docstatus"] == 1
    # Sales role cannot.
    sales = make_token("Sales")
    assert client.post("/payments/receive", json={"invoice_id": "SI-Y"},
                       headers=auth_header(sales)).status_code == 403


def test_payments_unauthenticated_rejected(client, fake_erpnext):
    assert client.get("/payments").status_code == 401
