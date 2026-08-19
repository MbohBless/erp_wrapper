"""A supplied posting_date must actually be honoured by ERPNext.

ERPNext ignores `posting_date` unless `set_posting_time` is also set — it
silently stamps today instead. The API accepted a posting date, passed it
through, and ERPNext dropped it: backdating appeared to work and posted the
document to the wrong period.

Nothing caught it, because the in-memory fake stores whatever it is given and
has no opinion about ERPNext's posting rules. So these tests assert on the
**payload sent to ERPNext**, not on the response — the response looked correct
the whole time it was broken.

Found on a live instance: 22 invoices seeded across a 30-day window all landed
on the same day, which is what a dashboard trend chart made of one spike looks
like.
"""

from tests.conftest import auth_header

BACKDATED = "2026-07-15"


def test_sales_invoice_backdating_sets_set_posting_time(
    client, admin_token, fake_erpnext
):
    resp = client.post(
        "/sales",
        json={
            "customer": "CHU Yaoundé",
            "items": [{"item_code": "THERMO-001", "qty": 1, "rate": 1000}],
            "posting_date": BACKDATED,
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201, resp.text
    stored = fake_erpnext.store[resp.json()["id"]]
    assert stored["posting_date"] == BACKDATED
    assert stored.get("set_posting_time") == 1, (
        "posting_date without set_posting_time is silently ignored by ERPNext"
    )


def test_purchase_invoice_backdating_sets_set_posting_time(
    client, admin_token, fake_erpnext
):
    resp = client.post(
        "/purchases",
        json={
            "supplier": "Mindray",
            "items": [{"item_code": "THERMO-001", "qty": 1, "rate": 800}],
            "posting_date": BACKDATED,
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201, resp.text
    stored = fake_erpnext.store[resp.json()["id"]]
    assert stored["posting_date"] == BACKDATED
    assert stored.get("set_posting_time") == 1


def test_payment_backdating_sets_set_posting_time(client, admin_token, fake_erpnext):
    invoice = client.post(
        "/sales",
        json={
            "customer": "CHU Yaoundé",
            "items": [{"item_code": "THERMO-001", "qty": 1, "rate": 5000}],
        },
        headers=auth_header(admin_token),
    ).json()

    resp = client.post(
        "/payments/receive",
        json={
            "invoice_id": invoice["id"],
            "amount": 5000,
            "posting_date": BACKDATED,
            "mode_of_payment": "Cash",
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code in (200, 201), resp.text
    entries = [
        d for d in fake_erpnext.store.values() if d.get("doctype") == "Payment Entry"
    ]
    assert entries, "no Payment Entry was created"
    assert entries[-1]["posting_date"] == BACKDATED
    assert entries[-1].get("set_posting_time") == 1


def test_omitting_posting_date_does_not_force_a_posting_time(
    client, admin_token, fake_erpnext
):
    """Without an explicit date, ERPNext should apply its own default.

    Setting set_posting_time unconditionally would pin every document to
    whatever timestamp happened to be in the payload, which is a different bug
    in the other direction.
    """
    resp = client.post(
        "/sales",
        json={
            "customer": "CHU Yaoundé",
            "items": [{"item_code": "THERMO-001", "qty": 1, "rate": 1000}],
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201
    stored = fake_erpnext.store[resp.json()["id"]]
    assert "set_posting_time" not in stored
