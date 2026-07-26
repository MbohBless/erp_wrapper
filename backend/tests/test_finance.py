"""Tests for the Finance module (summary aggregation, reports, RBAC)."""

from datetime import date

from repositories.finance_repository import FinanceRepository
from services.finance_service import FinanceService
from tests.conftest import auth_header


class FinanceStub:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.last_report = None

    async def list_documents(
        self, doctype, fields=None, filters=None, limit=20, start=0, order_by=None
    ):
        return self.data.get(doctype, [])

    async def get_document(self, doctype, name):
        return {"year_start_date": "2026-01-01", "year_end_date": "2026-12-31"}

    async def run_report(self, report_name, filters=None):
        self.last_report = {"report_name": report_name, "filters": filters or {}}
        return {"report_name": report_name, "result": []}


AS_OF = date(2026, 9, 24)
DATA = {
    "Sales Invoice": [
        {"name": "SI-1", "customer": "CHU Yaoundé", "outstanding_amount": 5000, "due_date": "2026-09-10"},  # overdue
        {"name": "SI-2", "customer": "Clinique", "outstanding_amount": 3000, "due_date": "2026-10-30"},
        {"name": "SI-3", "customer": "Paid Co", "outstanding_amount": 0, "due_date": "2026-09-01"},
    ],
    "Purchase Invoice": [
        {"name": "PI-1", "supplier": "Sanofi", "outstanding_amount": 4000, "due_date": "2026-10-05"},
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
