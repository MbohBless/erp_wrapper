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


def test_accountant_can_add_and_edit_but_not_delete(
    client, admin_token, make_token, fake_erpnext
):
    """The Accountant raises the invoices here, so a first-time buyer must not
    stall the sale. Deleting is a different thing: a customer carries invoices
    and a ledger history behind them."""
    token = make_token("Accountant")
    assert client.get("/customers", headers=auth_header(token)).status_code == 200

    created = _create(client, token, name="Clinique Nouvelle")
    assert created.status_code == 201, created.text
    cid = created.json()["id"]

    edited = client.put(f"/customers/{cid}", json={"phone": "+237 655 00 00 00"},
                        headers=auth_header(token))
    assert edited.status_code == 200, edited.text

    assert client.delete(f"/customers/{cid}", headers=auth_header(token)).status_code == 403


def test_store_keeper_cannot_view(client, make_token, fake_erpnext):
    token = make_token("Store Keeper")
    assert client.get("/customers", headers=auth_header(token)).status_code == 403


def test_unauthenticated_rejected(client, fake_erpnext):
    assert client.get("/customers").status_code == 401


# --- The active/disabled filter belongs to ERPNext, not to the page ------


def _disabled_ids(client, token, **params):
    from urllib.parse import urlencode
    resp = client.get("/customers?" + urlencode(params), headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    return [c["id"] for c in resp.json()]


def test_disabled_filter_is_applied_by_erpnext(client, admin_token, fake_erpnext):
    """Once the list is paged, filtering the fetched rows here would only ever
    filter the page in front of the user — every match on the other pages would
    silently disappear."""
    live = client.post("/customers", json={"name": "Live Clinic"},
                       headers=auth_header(admin_token)).json()["id"]
    gone = client.post("/customers", json={"name": "Closed Clinic"},
                       headers=auth_header(admin_token)).json()["id"]
    client.put(f"/customers/{gone}", json={"disabled": True},
               headers=auth_header(admin_token))

    assert live in _disabled_ids(client, admin_token, disabled=False)
    assert gone not in _disabled_ids(client, admin_token, disabled=False)
    assert gone in _disabled_ids(client, admin_token, disabled=True)
    assert live not in _disabled_ids(client, admin_token, disabled=True)

    both = _disabled_ids(client, admin_token)
    assert {live, gone} <= set(both), "omitting the filter should show both"


def test_paging_customers_covers_each_exactly_once(client, admin_token, fake_erpnext):
    made = {client.post("/customers", json={"name": f"Clinique {i}"},
                        headers=auth_header(admin_token)).json()["id"]
            for i in range(7)}

    size, seen, page = 3, [], 0
    while page < 10:
        batch = client.get("/customers", params={"limit": size + 1, "start": page * size},
                           headers=auth_header(admin_token)).json()
        seen.extend(c["id"] for c in batch[:size])
        if len(batch) <= size:
            break
        page += 1
    else:
        raise AssertionError("paging never reached the end — is `start` ignored?")

    assert len(seen) == len(set(seen)), "a customer appeared on two pages"
    assert made <= set(seen), "a customer never appeared on any page"
