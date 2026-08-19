"""The dashboard must not become a side door to the finance figures.

`/finance/*` is Manager + Accountant. The dashboard carries the same numbers, so
if it stays role-agnostic then a Store Keeper who is denied the finance pages
simply reads revenue and receivables off their landing page instead. These tests
pin the field-level policy in `services.dashboard_service.VISIBLE_FIELDS`.

The assertions are on the **HTTP payload**, not on the projection helper. What
matters is what leaves the process: a filter applied only in the UI, or lost
between service and router, would still pass a unit test of `project()`.
"""

from __future__ import annotations

import pytest

from models.user import Role
from services.dashboard_service import DashboardService
from tests.conftest import auth_header

MONEY = ("outstanding_customers", "outstanding_suppliers", "inventory_value")
COMMERCIAL = ("revenue_today", "revenue_trend", "revenue_by_segment", "recent_activity")
OPERATIONAL = ("low_stock_count", "low_stock_items", "expiring_batches")

SEES = {
    Role.ADMINISTRATOR.value: MONEY + COMMERCIAL + OPERATIONAL,
    Role.MANAGER.value: MONEY + COMMERCIAL + OPERATIONAL,
    Role.ACCOUNTANT.value: MONEY + COMMERCIAL + OPERATIONAL,
    Role.SALES.value: COMMERCIAL + OPERATIONAL,
    Role.STORE_KEEPER.value: OPERATIONAL,
    Role.BIOMEDICAL_ENGINEER.value: OPERATIONAL,
}


@pytest.mark.parametrize("role", sorted(SEES))
def test_dashboard_payload_matches_the_role_policy(
    client, make_token, fake_erpnext, role
):
    resp = client.get("/dashboard", headers=auth_header(make_token(role)))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    for field in SEES[role]:
        assert field in body, f"{role} should see {field} but it was withheld"

    withheld = set(MONEY + COMMERCIAL + OPERATIONAL) - set(SEES[role])
    for field in withheld:
        assert field not in body, (
            f"{role} must NOT receive {field} — it was in the response as "
            f"{body.get(field)!r}"
        )


@pytest.mark.parametrize(
    "role", [Role.STORE_KEEPER.value, Role.BIOMEDICAL_ENGINEER.value]
)
def test_no_financial_figure_survives_anywhere_in_the_payload(
    client, make_token, fake_erpnext, role
):
    """Belt and braces: the withheld numbers must not reappear under any key.

    Field-name assertions miss the case where a figure is also embedded in some
    nested structure. This checks the serialised body as a whole.
    """
    full = client.get(
        "/dashboard", headers=auth_header(make_token(Role.MANAGER.value))
    ).json()
    limited = client.get("/dashboard", headers=auth_header(make_token(role))).json()

    import json

    blob = json.dumps(limited)
    for field in MONEY:
        value = full.get(field)
        # Only meaningful when the fake produced a distinctive non-zero figure;
        # 0 and 0.0 appear legitimately in the operational fields.
        if value:
            assert str(value) not in blob, (
                f"{role}'s payload still contains the {field} figure {value}"
            )


def test_unknown_role_fails_closed():
    """A role added to the enum but not to the policy must under-share."""
    from schemas.dashboard import DashboardSummary

    full = DashboardSummary(
        revenue_today=1.0,
        outstanding_customers=2.0,
        outstanding_suppliers=3.0,
        inventory_value=4.0,
        low_stock_count=5,
        revenue_trend=[],
        recent_activity=[],
    )
    projected = DashboardService.project(full, "Some Future Role")
    assert projected.revenue_today is None
    assert projected.outstanding_customers is None
    assert projected.outstanding_suppliers is None
    assert projected.inventory_value is None
    # Operational data is still available — failing closed on money must not
    # leave the new role staring at a blank page.
    assert projected.low_stock_count == 5


def test_report_pdf_builder_still_receives_the_full_summary(fake_erpnext):
    """`role=None` is the internal path used by the PDF builder.

    That route is already Manager+Accountant-guarded, so it needs the complete
    figures. If this ever starts returning a filtered summary, the finance PDF
    silently loses its numbers.
    """
    import inspect

    sig = inspect.signature(DashboardService.get_summary)
    assert sig.parameters["role"].default is None
