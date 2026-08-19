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
        # Honours limit/start: the repository pages through anything it sums,
        # and a stub that ignored them would hand back a full page forever.
        return self.data.get(doctype, [])[start : start + limit]

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


async def test_trial_balance_skips_groups_and_totals():
    report = {
        "result": [
            {"account": "5211 - Bank", "account_name": "5211 Bank", "closing_debit": 1000, "closing_credit": 0},
            {"account": "4011 - Suppliers", "account_name": "4011 Suppliers", "closing_debit": 0, "closing_credit": 700},
            {"account": "ASSETS", "account_name": "Assets", "is_group": 1, "closing_debit": 1000, "closing_credit": 0},  # group -> skip
            {"account": None, "account_name": "Total", "closing_debit": 1000, "closing_credit": 700},  # grand total -> skip
            {"account": "9999 - Empty", "account_name": "Empty", "closing_debit": 0, "closing_credit": 0},  # nil -> skip
        ]
    }
    repo = FinanceRepository(FinStub(report=report))
    tb = await repo.trial_balance("EquiMed", fiscal_year="2026")
    assert [r.account for r in tb.rows] == ["5211 Bank", "4011 Suppliers"]
    assert tb.total_debit == 1000 and tb.total_credit == 700
    # fiscal year was resolved to a date range for the report
    assert repo.client.last_filters["from_date"] == "2026-01-01"


class CashFlowStub(FinStub):
    """Respects the account_type filter so cash and bank resolve to different
    accounts (the plain FinStub ignores filters and would double-count)."""

    def __init__(self, accounts_by_type, gl):
        super().__init__()
        self.accounts_by_type = accounts_by_type
        self.gl = gl

    async def list_documents(self, doctype, fields=None, filters=None, limit=20, start=0, order_by=None):
        filters = filters or []
        if doctype == "Account":
            atype = next((f[2] for f in filters if f[0] == "account_type"), None)
            return [{"name": n} for n in self.accounts_by_type.get(atype, [])]
        if doctype == "GL Entry":
            if any(f[1] == "<" for f in filters):
                return []  # prior-period opening query
            accts = next((f[2] for f in filters if f[0] == "account"), [])
            return [e for e in self.gl if e["account"] in accts]
        return []


async def test_cash_flow_direct_method():
    gl = [
        {"account": "Caisse", "posting_date": "2026-03-01", "debit": 500, "credit": 0, "voucher_type": "Payment Entry", "voucher_no": "PE-1"},
        {"account": "Banque", "posting_date": "2026-03-02", "debit": 1000, "credit": 0, "voucher_type": "Payment Entry", "voucher_no": "PE-2"},
        {"account": "Banque", "posting_date": "2026-03-05", "debit": 0, "credit": 400, "voucher_type": "Journal Entry", "voucher_no": "JE-1"},
    ]
    repo = FinanceRepository(CashFlowStub({"Cash": ["Caisse"], "Bank": ["Banque"]}, gl))
    cf = await repo.cash_flow(company="EquiMed", fiscal_year="2026")
    assert cf.opening == 0
    assert cf.total_in == 1500  # two Payment Entry inflows, aggregated
    assert cf.total_out == 400
    assert cf.net_change == 1100
    assert cf.closing == 1100
    assert [(l.label, l.amount) for l in cf.inflows] == [("Payment Entry", 1500)]
    assert [(l.label, l.amount) for l in cf.outflows] == [("Journal Entry", 400)]


# --- endpoint RBAC (via the in-memory fake) ---
def test_trial_balance_cash_flow_rbac(client, make_token, fake_erpnext):
    acct = make_token("Accountant")
    assert client.get("/finance/trial-balance?company=EquiMed", headers=auth_header(acct)).status_code == 200
    assert client.get("/finance/cash-flow?company=EquiMed", headers=auth_header(acct)).status_code == 200
    sales = make_token("Sales")
    assert client.get("/finance/trial-balance?company=EquiMed", headers=auth_header(sales)).status_code == 403
    assert client.get("/finance/cash-flow", headers=auth_header(sales)).status_code == 403


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
