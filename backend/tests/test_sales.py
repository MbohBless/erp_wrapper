"""Integration tests for the Sales module (invoices: list/create/view + RBAC)."""

from tests.conftest import auth_header

INVOICE = {
    "customer": "CHU Yaoundé",
    "items": [
        {"item_code": "THERMO-001", "qty": 2, "rate": 2500},
        {"item_code": "GLOVE-001", "qty": 10, "rate": 300},
    ],
}


def _create(client, token, **overrides):
    return client.post("/sales", json={**INVOICE, **overrides}, headers=auth_header(token))


def test_create_invoice_is_submitted(client, admin_token, fake_erpnext):
    resp = _create(client, admin_token)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["customer"] == "CHU Yaoundé"
    assert len(body["items"]) == 2
    assert body["items"][0]["amount"] == 5000  # 2 * 2500

    stored = fake_erpnext.store[body["id"]]
    assert stored["docstatus"] == 1  # posted to the ledger


def test_list_and_get_invoice(client, admin_token, fake_erpnext):
    created = _create(client, admin_token, customer="Hôpital Général Douala").json()

    listed = client.get("/sales", headers=auth_header(admin_token))
    assert listed.status_code == 200
    assert created["id"] in [i["id"] for i in listed.json()]

    got = client.get(f"/sales/{created['id']}", headers=auth_header(admin_token))
    assert got.status_code == 200
    assert got.json()["customer"] == "Hôpital Général Douala"


def test_search_by_customer(client, admin_token, fake_erpnext):
    _create(client, admin_token, customer="Pharmacie Centrale")
    _create(client, admin_token, customer="Clinique du Littoral")
    resp = client.get(
        "/sales", params={"search": "Pharmacie"}, headers=auth_header(admin_token)
    )
    assert {i["customer"] for i in resp.json()} == {"Pharmacie Centrale"}


def test_get_missing_invoice_404(client, admin_token, fake_erpnext):
    assert client.get("/sales/NOPE", headers=auth_header(admin_token)).status_code == 404


# --- RBAC ---


def test_sales_role_can_create(client, make_token, fake_erpnext):
    token = make_token("Sales")
    assert _create(client, token).status_code == 201


def test_accountant_can_view_but_not_create(client, admin_token, make_token, fake_erpnext):
    _create(client, admin_token)
    token = make_token("Accountant")
    assert client.get("/sales", headers=auth_header(token)).status_code == 200
    assert _create(client, token).status_code == 403


def test_store_keeper_cannot_view(client, make_token, fake_erpnext):
    token = make_token("Store Keeper")
    assert client.get("/sales", headers=auth_header(token)).status_code == 403


def test_unauthenticated_rejected(client, fake_erpnext):
    assert client.get("/sales").status_code == 401
