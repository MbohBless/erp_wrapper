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


# --- Panel detail comes from ERPNext, never from placeholders ---------------
# The low-stock and expiring panels used to render hardcoded sample rows
# ("Insulin Glargine 100IU", "Batch MET-7781"), which is indistinguishable from
# real data to someone looking at their own dashboard. These pin the real
# sources and the empty case.

PANEL_DATA = {
    **DATA,
    "Batch": [
        {"name": "B-1", "batch_id": "B-1", "item": "THERMO-001",
         "expiry_date": "2026-08-10", "batch_qty": 40},
        {"name": "B-2", "batch_id": "B-2", "item": "GLOVE-001",
         "expiry_date": "2026-12-01", "batch_qty": 900},
    ],
    "Item": [
        {"name": "THERMO-001", "item_name": "Digital Thermometer"},
        {"name": "GLOVE-001", "item_name": "Nitrile Gloves"},
    ],
    "Customer": [
        {"name": "Clinic A", "customer_group": "Clinics"},
        {"name": "Clinic B", "customer_group": "Hospitals"},
    ],
}


async def _summary(data):
    return await DashboardRepository(DashboardStub(data)).get_summary(AS_OF)


async def test_low_stock_rows_come_from_bins():
    summary = await _summary(PANEL_DATA)
    assert [i.item_code for i in summary.low_stock_items] == ["THERMO-001"]
    item = summary.low_stock_items[0]
    assert item.item_name == "Digital Thermometer"  # resolved, not the raw code
    assert item.actual_qty == 3
    assert item.warehouse == "Main"


async def test_expiring_batches_come_from_batch_doctype():
    summary = await _summary(PANEL_DATA)
    assert [b.batch_id for b in summary.expiring_batches] == ["B-1", "B-2"]
    soonest = summary.expiring_batches[0]
    assert soonest.item_name == "Digital Thermometer"
    assert soonest.days_left == 17  # 2026-07-24 -> 2026-08-10
    assert soonest.qty == 40


async def test_revenue_segments_are_computed_from_invoices():
    summary = await _summary(PANEL_DATA)
    by_label = {s.label: s for s in summary.revenue_by_segment}
    # SI-1 10000 to Clinics, SI-2 5000 to Hospitals -> 66.7 / 33.3 of 15000.
    assert by_label["Clinics"].pct == 66.7
    assert by_label["Hospitals"].pct == 33.3
    assert sum(s.amount for s in summary.revenue_by_segment) == 15000
    assert summary.top_customer.label == "Clinic A"
    assert summary.top_customer.amount == 10000


async def test_panels_are_empty_when_there_is_no_data():
    """An empty workspace shows nothing — not sample rows."""
    summary = await _summary({})
    assert summary.low_stock_items == []
    assert summary.expiring_batches == []
    assert summary.revenue_by_segment == []
    assert summary.top_customer is None


def test_dashboard_endpoint_exposes_the_panel_fields(client, admin_token, fake_erpnext):
    resp = client.get("/dashboard", headers=auth_header(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    for field in ("low_stock_items", "expiring_batches", "revenue_by_segment"):
        assert field in body, f"{field} missing from the dashboard payload"
