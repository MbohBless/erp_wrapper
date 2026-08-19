"""First-time books setup: opening balances.

The wizard exists to record debts outstanding at a cutover. Those invoices were
raised BEFORE the cutover — usually in the previous year — and ERPNext refuses
any posting date outside an active fiscal year. A fresh install has only the
current year, so posting an opening receivable on its original date failed for
exactly the case the wizard is for.

Opening documents therefore post on the START DATE, with the original date kept
in the remark and the due date passed through so ageing still reflects the real
terms.
"""

from __future__ import annotations

import pytest

from tests.conftest import auth_header

START = "2026-01-01"


@pytest.fixture(autouse=True)
def _fresh_books():
    """Clear the books-setup marker before each test.

    Unlike the ERPNext fake, which is rebuilt per test, this row lives in the
    app database and survives the whole session — so the first test to complete
    setup would make every later one fail with 409, and the order of the file
    would decide the result.
    """
    from database import SessionLocal
    from models.books_setup import BooksSetup

    db = SessionLocal()
    try:
        db.query(BooksSetup).delete()
        db.commit()
    finally:
        db.close()
    yield


def _erpnext_ready(fake, company="Quality BioMedicals Sarl", abbr="QBS"):
    """The minimum ERPNext state the wizard needs before it can post.

    A company, the accounts it offsets to, and one stock item to carry the
    opening invoice lines. The fake starts empty; a real install has all of it
    after the setup wizard.
    """
    fake.store[company] = {"doctype": "Company", "name": company, "abbr": abbr}
    for prefix in ("1013", "162", "2413", "3111", "4111", "4011", "521", "571"):
        name = f"{prefix}-Account - {abbr}"
        fake.store[name] = {
            "doctype": "Account", "name": name, "company": company, "is_group": 0,
        }
    fake.store["OPENING-ITEM"] = {
        "doctype": "Item", "name": "OPENING-ITEM", "item_code": "OPENING-ITEM",
        "is_stock_item": 1,
    }


def _with_fiscal_year(fake, name="2026", start="2026-01-01", end="2026-12-31"):
    """A real install always has one; the in-memory fake starts empty.

    The service refuses to post without an active fiscal year covering the start
    date — deliberately, because ERPNext would otherwise reject the documents
    with a message about a date the user never typed.
    """
    fake.store[name] = {
        "doctype": "Fiscal Year", "name": name, "disabled": 0,
        "year_start_date": start, "year_end_date": end,
    }


def _payload(**over):
    body = {
        "start_date": START,
        "bank": 1_000_000,
        "cash": 50_000,
        "receivables": [
            # Deliberately in the PREVIOUS year — the realistic case.
            {"party": "CHU Yaoundé", "reference": "AR-1",
             "date": "2025-12-15", "due_date": "2026-01-31", "amount": 250_000},
        ],
        "payables": [
            {"party": "Mindray", "reference": "AP-1",
             "date": "2025-12-20", "due_date": "2026-02-15", "amount": 180_000},
        ],
    }
    body.update(over)
    return body


def test_opening_invoices_post_on_the_start_date_not_their_original_date(
    client, admin_token, fake_erpnext
):
    _erpnext_ready(fake_erpnext)
    _with_fiscal_year(fake_erpnext)
    resp = client.post("/setup/opening-balances", json=_payload(),
                       headers=auth_header(admin_token))
    assert resp.status_code in (200, 201), resp.text

    invoices = [
        d for d in fake_erpnext.store.values()
        if d.get("doctype") in ("Sales Invoice", "Purchase Invoice")
        and d.get("is_opening") == "Yes"
    ]
    assert invoices, "no opening invoices were posted"
    for inv in invoices:
        assert inv["posting_date"] == START, (
            "opening invoice posted on %s; ERPNext rejects any date outside an "
            "active fiscal year, and a fresh install has only the current year"
            % inv["posting_date"]
        )


def test_the_original_date_and_reference_survive_in_the_remark(
    client, admin_token, fake_erpnext
):
    """Posting on the cutover loses the real date unless it is kept somewhere.

    It is often the only way to tie the entry to the customer's own paperwork.
    """
    _erpnext_ready(fake_erpnext)
    _with_fiscal_year(fake_erpnext)
    client.post("/setup/opening-balances", json=_payload(),
                headers=auth_header(admin_token))
    remarks = " ".join(
        str(d.get("remarks", "")) for d in fake_erpnext.store.values()
        if d.get("is_opening") == "Yes"
    )
    assert "2025-12-15" in remarks
    assert "AR-1" in remarks


def test_due_dates_are_passed_through_so_ageing_stays_correct(
    client, admin_token, fake_erpnext
):
    _erpnext_ready(fake_erpnext)
    _with_fiscal_year(fake_erpnext)
    client.post("/setup/opening-balances", json=_payload(),
                headers=auth_header(admin_token))
    due = {
        d.get("due_date") for d in fake_erpnext.store.values()
        if d.get("is_opening") == "Yes"
    }
    assert "2026-01-31" in due
    assert "2026-02-15" in due


def test_setup_cannot_be_posted_twice(client, admin_token, fake_erpnext):
    """A second post would double the opening ledger."""
    _erpnext_ready(fake_erpnext)
    _with_fiscal_year(fake_erpnext)
    first = client.post("/setup/opening-balances", json=_payload(),
                        headers=auth_header(admin_token))
    assert first.status_code in (200, 201)
    second = client.post("/setup/opening-balances", json=_payload(),
                         headers=auth_header(admin_token))
    assert second.status_code == 409


def test_status_reports_completion(client, admin_token, fake_erpnext):
    _erpnext_ready(fake_erpnext)
    _with_fiscal_year(fake_erpnext)
    before = client.get("/setup/status", headers=auth_header(admin_token)).json()
    assert before["setup_complete"] is False
    client.post("/setup/opening-balances", json=_payload(),
                headers=auth_header(admin_token))
    after = client.get("/setup/status", headers=auth_header(admin_token)).json()
    assert after["setup_complete"] is True
    assert after["start_date"] == START


def test_a_start_date_outside_every_fiscal_year_is_refused_helpfully(
    client, admin_token, fake_erpnext
):
    """ERPNext's own refusal names a date the user never typed.

    The wizard derives posting dates from the start date, so its message points
    at a document date and never mentions creating a fiscal year — which is the
    actual fix.
    """
    _erpnext_ready(fake_erpnext)
    _with_fiscal_year(fake_erpnext, name="2026", start="2026-01-01", end="2026-12-31")
    resp = client.post(
        "/setup/opening-balances",
        json=_payload(start_date="2024-06-01"),
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "2024-06-01" in detail
    assert "fiscal year" in detail.lower()
    assert "2026" in detail, "the message should say which years ARE available"


def test_no_fiscal_year_at_all_is_refused_before_posting(
    client, admin_token, fake_erpnext
):
    resp = client.post("/setup/opening-balances", json=_payload(),
                       headers=auth_header(admin_token))
    assert resp.status_code == 422
    assert "fiscal year" in resp.json()["detail"].lower()
