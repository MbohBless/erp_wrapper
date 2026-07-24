"""Tests for the Dashboard aggregation + endpoint."""

from datetime import date

from repositories.dashboard_repository import DashboardRepository
from services.dashboard_service import DashboardService
from tests.conftest import auth_header


class DashboardStub:
    """Returns canned lists per DocType (list_documents is all the repo uses)."""

    def __init__(self, data: dict) -> None:
        self.data = data

    async def list_documents(
        self, doctype, fields=None, filters=None, limit=20, start=0, order_by=None
    ):
        return self.data.get(doctype, [])


AS_OF = date(2026, 7, 24)
DATA = {
    "Sales Invoice": [
        {
            "name": "SI-1",
            "customer": "Clinic A",
            "grand_total": 10000,
            "outstanding_amount": 4000,
            "posting_date": "2026-07-24",
        },
        {
            "name": "SI-2",
            "customer": "Clinic B",
            "grand_total": 5000,
            "outstanding_amount": 0,
            "posting_date": "2026-07-23",
        },
    ],
    "Purchase Invoice": [
        {
            "name": "PI-1",
            "supplier": "Acme Medical Ltd",
            "grand_total": 8000,
            "outstanding_amount": 8000,
            "posting_date": "2026-07-22",
        }
    ],
    "Payment Entry": [
        {
            "name": "PE-1",
            "party": "Clinic A",
            "paid_amount": 6000,
            "posting_date": "2026-07-24",
            "payment_type": "Receive",
        }
    ],
    "Bin": [
        {"item_code": "THERMO-001", "warehouse": "Main", "actual_qty": 3, "stock_value": 4500},
        {"item_code": "GLOVE-001", "warehouse": "Main", "actual_qty": 100, "stock_value": 20000},
    ],
}


async def test_summary_totals():
    repo = DashboardRepository(DashboardStub(DATA))
    summary = await repo.get_summary(AS_OF, trend_days=7, low_stock_threshold=10)

    assert summary.revenue_today == 10000
    assert summary.outstanding_customers == 4000
    assert summary.outstanding_suppliers == 8000
    assert summary.inventory_value == 24500
    assert summary.low_stock_count == 1  # THERMO qty 3 <= 10; GLOVE 100 excluded


async def test_summary_trend_and_activity():
    repo = DashboardRepository(DashboardStub(DATA))
    summary = await repo.get_summary(AS_OF, trend_days=7)

    assert len(summary.revenue_trend) == 7
    assert summary.revenue_trend[-1].date == "2026-07-24"
    assert summary.revenue_trend[-1].amount == 10000
    assert summary.revenue_trend[-2].amount == 5000  # 2026-07-23

    # Newest first; two entries fall on 2026-07-24 (SI-1, PE-1).
    assert summary.recent_activity[0].date == "2026-07-24"
    types = {a.type for a in summary.recent_activity}
    assert {"Sales Invoice", "Purchase Invoice", "Payment"} <= types


def test_dashboard_endpoint(client, admin_token):
    from api import deps
    from main import app

    today = date.today().isoformat()
    stub = DashboardStub(
        {
            "Sales Invoice": [
                {
                    "name": "SI",
                    "customer": "C",
                    "grand_total": 1000,
                    "outstanding_amount": 1000,
                    "posting_date": today,
                }
            ],
            "Bin": [],
        }
    )
    app.dependency_overrides[deps.get_dashboard_service] = lambda: DashboardService(
        DashboardRepository(stub)
    )
    try:
        resp = client.get("/dashboard", headers=auth_header(admin_token))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["revenue_today"] == 1000
        assert "revenue_trend" in body and "recent_activity" in body
    finally:
        app.dependency_overrides.pop(deps.get_dashboard_service, None)


def test_dashboard_requires_auth(client):
    assert client.get("/dashboard").status_code == 401
