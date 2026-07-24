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
