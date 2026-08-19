"""Integration tests for the Supplier module (CRUD + RBAC), against a fake ERPNext."""

from tests.conftest import auth_header

SUPPLIER = {
    "name": "Acme Medical Ltd",
    "supplier_group": "All Supplier Groups",
    "supplier_type": "Company",
    "contact_person": "Jane Doe",
    "phone": "+237600000000",
    "email": "contact@acme.cm",
    "address": "123 Rue de la Sante, Douala",
    "lead_time_days": 14,
    "tax_id": "M0123456789",
}


def _create(client, token, **overrides):
    payload = {**SUPPLIER, **overrides}
    return client.post("/suppliers", json=payload, headers=auth_header(token))


def test_admin_create_and_get_supplier(client, admin_token, fake_erpnext):
    resp = _create(client, admin_token)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] == "Acme Medical Ltd"
    assert body["name"] == "Acme Medical Ltd"
    assert body["lead_time_days"] == 14
    assert body["email"] == "contact@acme.cm"

    got = client.get(
        "/suppliers/Acme Medical Ltd", headers=auth_header(admin_token)
    )
    assert got.status_code == 200
    assert got.json()["contact_person"] == "Jane Doe"


def test_field_mapping_to_erpnext(client, admin_token, fake_erpnext):
    _create(client, admin_token, name="Mapping Co")
    stored = fake_erpnext.store["Mapping Co"]
    # Domain fields are translated to ERPNext field names.
    assert stored["supplier_name"] == "Mapping Co"
    assert stored["custom_contact_person"] == "Jane Doe"
    assert stored["custom_lead_time_days"] == 14
    assert stored["custom_email"] == "contact@acme.cm"
    assert stored["disabled"] == 0


def test_list_suppliers(client, admin_token, fake_erpnext):
    _create(client, admin_token, name="Supplier A")
    _create(client, admin_token, name="Supplier B")
    resp = client.get("/suppliers", headers=auth_header(admin_token))
    assert resp.status_code == 200
    ids = {s["id"] for s in resp.json()}
    assert {"Supplier A", "Supplier B"} <= ids


def test_list_search_and_type_filter(client, admin_token, fake_erpnext):
    _create(client, admin_token, name="Sanofi Cameroun")
    _create(client, admin_token, name="Jean Distributeur", supplier_type="Individual")

    resp = client.get(
        "/suppliers", params={"search": "Sanofi"}, headers=auth_header(admin_token)
    )
    assert [s["id"] for s in resp.json()] == ["Sanofi Cameroun"]

    resp = client.get(
        "/suppliers",
        params={"supplier_type": "Individual"},
        headers=auth_header(admin_token),
    )
    assert {s["id"] for s in resp.json()} == {"Jean Distributeur"}


def test_duplicate_supplier_conflict(client, admin_token, fake_erpnext):
    _create(client, admin_token, name="Dup Co")
    resp = _create(client, admin_token, name="Dup Co")
    assert resp.status_code == 409


def test_update_supplier(client, admin_token, fake_erpnext):
    _create(client, admin_token, name="Update Co")
    resp = client.put(
        "/suppliers/Update Co",
        json={"lead_time_days": 30, "disabled": True},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["lead_time_days"] == 30
    assert resp.json()["disabled"] is True
    assert fake_erpnext.store["Update Co"]["custom_lead_time_days"] == 30
    assert fake_erpnext.store["Update Co"]["disabled"] == 1


def test_delete_supplier(client, admin_token, fake_erpnext):
    _create(client, admin_token, name="Delete Co")
    assert (
        client.delete(
            "/suppliers/Delete Co", headers=auth_header(admin_token)
        ).status_code
        == 204
    )
    assert (
        client.get(
            "/suppliers/Delete Co", headers=auth_header(admin_token)
        ).status_code
        == 404
    )


def test_get_missing_supplier_404(client, admin_token, fake_erpnext):
    resp = client.get("/suppliers/Nope", headers=auth_header(admin_token))
    assert resp.status_code == 404


# --- RBAC ---


def test_manager_can_manage(client, make_token, fake_erpnext):
    token = make_token("Manager")
    assert _create(client, token, name="Mgr Co").status_code == 201
    assert (
        client.get("/suppliers/Mgr Co", headers=auth_header(token)).status_code == 200
    )


def test_accountant_cannot_reach_suppliers(client, admin_token, make_token, fake_erpnext):
    """Suppliers are the Manager's to operate. What the Accountant still sees is
    what is *owed* to them — the payables ledger and the statements — which come
    from Finance, not from here."""
    _create(client, admin_token, name="View Co")
    token = make_token("Accountant")
    assert client.get("/suppliers", headers=auth_header(token)).status_code == 403
    assert _create(client, token, name="Acct Co").status_code == 403


def test_sales_cannot_view_suppliers(client, make_token, fake_erpnext):
    token = make_token("Sales")
    assert client.get("/suppliers", headers=auth_header(token)).status_code == 403


def test_unauthenticated_rejected(client, fake_erpnext):
    assert client.get("/suppliers").status_code == 401
