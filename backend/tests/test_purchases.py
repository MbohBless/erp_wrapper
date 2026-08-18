"""Integration tests for the Purchases module (supplier bills: list/create/view + RBAC)."""

from tests.conftest import auth_header

BILL = {
    "supplier": "Acme Medical Ltd",
    "bill_no": "SUP-INV-9",
    "items": [
        {"item_code": "THERMO-001", "qty": 10, "rate": 1500},
        {"item_code": "GLOVE-001", "qty": 50, "rate": 120},
    ],
}


def _create(client, token, **overrides):
    return client.post("/purchases", json={**BILL, **overrides}, headers=auth_header(token))


def test_create_purchase_is_submitted(client, admin_token, fake_erpnext):
    resp = _create(client, admin_token)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["supplier"] == "Acme Medical Ltd"
    assert body["bill_no"] == "SUP-INV-9"
    assert body["items"][0]["amount"] == 15000  # 10 * 1500

    assert fake_erpnext.store[body["id"]]["docstatus"] == 1


def test_list_get_and_search(client, admin_token, fake_erpnext):
    created = _create(client, admin_token, supplier="Sanofi").json()

    listed = client.get("/purchases", headers=auth_header(admin_token))
    assert created["id"] in [b["id"] for b in listed.json()]

    got = client.get(f"/purchases/{created['id']}", headers=auth_header(admin_token))
    assert got.status_code == 200 and got.json()["supplier"] == "Sanofi"

    resp = client.get(
        "/purchases", params={"search": "Sanofi"}, headers=auth_header(admin_token)
    )
    assert {b["supplier"] for b in resp.json()} == {"Sanofi"}


def test_get_missing_404(client, admin_token, fake_erpnext):
    assert client.get("/purchases/NOPE", headers=auth_header(admin_token)).status_code == 404


# --- RBAC ---


def test_manager_can_create(client, make_token, fake_erpnext):
    token = make_token("Manager")
    assert _create(client, token).status_code == 201


def test_store_keeper_can_view_but_not_create(client, admin_token, make_token, fake_erpnext):
    _create(client, admin_token)
    token = make_token("Store Keeper")
    assert client.get("/purchases", headers=auth_header(token)).status_code == 200
    assert _create(client, token).status_code == 403


def test_sales_cannot_view_purchases(client, make_token, fake_erpnext):
    token = make_token("Sales")
    assert client.get("/purchases", headers=auth_header(token)).status_code == 403


def test_unauthenticated_rejected(client, fake_erpnext):
    assert client.get("/purchases").status_code == 401


# --- Amending a posted bill ---------------------------------------------
#
# Same cancel-then-amend as a sales invoice; see test_sales.py for the reasoning
# behind each of these. Both sides of the ledger must behave identically.

AMENDED = {
    "supplier": "Acme Medical Ltd",
    "bill_no": "SUP-INV-9A",
    "items": [{"item_code": "THERMO-001", "qty": 12, "rate": 1450}],
    "remarks": "Supplier reissued the bill with a corrected rate",
}


def _amend(client, token, bill_id, **overrides):
    return client.put(
        f"/purchases/{bill_id}",
        json={**AMENDED, **overrides},
        headers=auth_header(token),
    )


def test_amend_cancels_the_original_and_posts_a_replacement(
    client, admin_token, fake_erpnext
):
    original = _create(client, admin_token).json()["id"]

    resp = _amend(client, admin_token, original)
    assert resp.status_code == 200, resp.text
    replacement = resp.json()["id"]
    assert replacement == f"{original}-1"

    assert fake_erpnext.store[original]["docstatus"] == 2
    posted = fake_erpnext.store[replacement]
    assert posted["docstatus"] == 1
    assert posted["amended_from"] == original
    assert posted["items"] == [{"item_code": "THERMO-001", "qty": 12, "rate": 1450}]
    assert posted["bill_no"] == "SUP-INV-9A"


def test_amend_backdating_sets_posting_time(client, admin_token, fake_erpnext):
    original = _create(client, admin_token).json()["id"]
    new_id = _amend(client, admin_token, original, posting_date="2026-02-09").json()["id"]

    posted = fake_erpnext.store[new_id]
    assert posted["posting_date"] == "2026-02-09"
    assert posted["set_posting_time"] == 1


def test_amend_refused_once_the_supplier_has_been_paid(
    client, admin_token, fake_erpnext
):
    original = _create(client, admin_token).json()["id"]
    fake_erpnext.store[original].update(grand_total=90000, outstanding_amount=30000)

    resp = _amend(client, admin_token, original)
    assert resp.status_code == 409
    assert "60,000 XAF paid" in resp.json()["detail"]
    assert fake_erpnext.store[original]["docstatus"] == 1


def test_amend_refused_on_an_opening_balance(client, admin_token, fake_erpnext):
    original = _create(client, admin_token).json()["id"]
    fake_erpnext.store[original]["is_opening"] = "Yes"

    resp = _amend(client, admin_token, original)
    assert resp.status_code == 409
    assert fake_erpnext.store[original]["docstatus"] == 1


def test_amend_resumes_a_cancel_that_lost_its_replacement(
    client, admin_token, fake_erpnext
):
    original = _create(client, admin_token).json()["id"]
    fake_erpnext.store[original].update(
        grand_total=90000, outstanding_amount=0, docstatus=2, status="Cancelled"
    )

    first = _amend(client, admin_token, original)
    assert first.status_code == 200, first.text
    assert first.json()["id"] == f"{original}-1"

    second = _amend(client, admin_token, original)
    assert second.json()["id"] == f"{original}-1"
    assert f"{original}-2" not in fake_erpnext.store


def test_cancelled_bills_are_not_listed(client, admin_token, fake_erpnext):
    original = _create(client, admin_token, supplier="Mindray").json()["id"]
    replacement = _amend(client, admin_token, original, supplier="Mindray").json()["id"]

    ids = [
        b["id"] for b in client.get("/purchases", headers=auth_header(admin_token)).json()
    ]
    assert replacement in ids
    assert original not in ids


def test_amend_missing_bill_404(client, admin_token, fake_erpnext):
    assert _amend(client, admin_token, "NOPE").status_code == 404


def test_only_manager_and_administrator_may_amend(
    client, admin_token, make_token, fake_erpnext
):
    original = _create(client, admin_token).json()["id"]

    assert _amend(client, make_token("Store Keeper"), original).status_code == 403
    assert _amend(client, make_token("Accountant"), original).status_code == 403
    assert fake_erpnext.store[original]["docstatus"] == 1

    assert _amend(client, make_token("Manager"), original).status_code == 200
