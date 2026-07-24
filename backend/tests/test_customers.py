"""Integration tests for the Customer module (CRUD + search/filter + RBAC)."""

from tests.conftest import auth_header, login

CUSTOMER = {
    "name": "CHU Yaoundé",
    "customer_group": "All Customer Groups",
    "customer_type": "Company",
    "territory": "All Territories",
    "contact_person": "Dr. Nkeng",
    "phone": "+237699000000",
    "email": "contact@chu-yaounde.cm",
    "address": "Rue Hospitalière, Yaoundé",
    "tax_id": "M081234567",
}


def _create(client, token, **overrides):
    return client.post(
        "/customers", json={**CUSTOMER, **overrides}, headers=auth_header(token)
    )


def test_admin_create_and_get(client, admin_token, fake_erpnext):
    resp = _create(client, admin_token)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] == "CHU Yaoundé"
    assert body["customer_type"] == "Company"

    stored = fake_erpnext.store["CHU Yaoundé"]
    assert stored["customer_name"] == "CHU Yaoundé"
    assert stored["custom_contact_person"] == "Dr. Nkeng"

    got = client.get("/customers/CHU Yaoundé", headers=auth_header(admin_token))
    assert got.status_code == 200
    assert got.json()["email"] == "contact@chu-yaounde.cm"


def test_list_search_and_type_filter(client, admin_token, fake_erpnext):
    _create(client, admin_token, name="Hôpital Général Douala")
    _create(client, admin_token, name="Pharmacie Centrale", customer_type="Individual")

    # search by name (ERPNext "like")
    resp = client.get(
        "/customers", params={"search": "Pharmacie"}, headers=auth_header(admin_token)
    )
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()]
    assert ids == ["Pharmacie Centrale"]

    # filter by type
    resp = client.get(
        "/customers",
        params={"customer_type": "Individual"},
        headers=auth_header(admin_token),
    )
    assert {c["id"] for c in resp.json()} == {"Pharmacie Centrale"}


def test_update_and_delete(client, admin_token, fake_erpnext):
    _create(client, admin_token, name="Edit Co")
    upd = client.put(
        "/customers/Edit Co",
        json={"phone": "+237677000000", "disabled": True},
        headers=auth_header(admin_token),
    )
    assert upd.status_code == 200
    assert upd.json()["phone"] == "+237677000000"
    assert upd.json()["disabled"] is True

    assert (
        client.delete("/customers/Edit Co", headers=auth_header(admin_token)).status_code
        == 204
    )
    assert (
        client.get("/customers/Edit Co", headers=auth_header(admin_token)).status_code
        == 404
    )


def test_duplicate_conflict(client, admin_token, fake_erpnext):
    _create(client, admin_token, name="Dup Co")
    assert _create(client, admin_token, name="Dup Co").status_code == 409


# --- RBAC ---


def test_sales_can_manage_customers(client, make_token, fake_erpnext):
    token = make_token("Sales")
    assert _create(client, token, name="Sales Co").status_code == 201


def test_accountant_can_view_but_not_write(client, admin_token, make_token, fake_erpnext):
    _create(client, admin_token, name="View Co")
    token = make_token("Accountant")
    assert client.get("/customers", headers=auth_header(token)).status_code == 200
    assert _create(client, token, name="Nope Co").status_code == 403


def test_store_keeper_cannot_view(client, make_token, fake_erpnext):
    token = make_token("Store Keeper")
    assert client.get("/customers", headers=auth_header(token)).status_code == 403


def test_unauthenticated_rejected(client, fake_erpnext):
    assert client.get("/customers").status_code == 401
