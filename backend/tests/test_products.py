"""Integration tests for the Product module (CRUD + RBAC), against a fake ERPNext."""

from tests.conftest import auth_header

PRODUCT = {
    "name": "Digital Thermometer",
    "sku": "THERMO-001",
    "barcode": "6001234567890",
    "category": "All Item Groups",
    "manufacturer": "Acme",
    "purchase_price": 1500.0,
    "selling_price": 2500.0,
    "unit": "Nos",
    "image": "/files/thermo.png",
}


def _create(client, token, **overrides):
    payload = {**PRODUCT, **overrides}
    return client.post("/products", json=payload, headers=auth_header(token))


def test_admin_create_and_get_product(client, admin_token, fake_erpnext):
    resp = _create(client, admin_token)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] == "THERMO-001"
    assert body["sku"] == "THERMO-001"
    assert body["name"] == "Digital Thermometer"
    assert body["selling_price"] == 2500.0

    got = client.get("/products/THERMO-001", headers=auth_header(admin_token))
    assert got.status_code == 200
    assert got.json()["manufacturer"] == "Acme"


def test_field_mapping_to_erpnext(client, admin_token, fake_erpnext):
    _create(client, admin_token, sku="MAP-1")
    stored = fake_erpnext.store["MAP-1"]
    assert stored["item_code"] == "MAP-1"
    assert stored["item_name"] == "Digital Thermometer"
    assert stored["item_group"] == "All Item Groups"
    assert stored["stock_uom"] == "Nos"
    assert stored["custom_barcode"] == "6001234567890"
    assert stored["custom_manufacturer"] == "Acme"
    assert stored["custom_purchase_price"] == 1500.0
    assert stored["custom_selling_price"] == 2500.0
    assert stored["disabled"] == 0


def test_list_products(client, admin_token, fake_erpnext):
    _create(client, admin_token, sku="P-A")
    _create(client, admin_token, sku="P-B")
    resp = client.get("/products", headers=auth_header(admin_token))
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert {"P-A", "P-B"} <= ids


def test_list_search_and_category_filter(client, admin_token, fake_erpnext):
    _create(client, admin_token, name="Digital Thermometer", sku="TH-1")
    _create(client, admin_token, name="Nitrile Gloves", sku="GL-1", category="Consumables")

    resp = client.get(
        "/products", params={"search": "Glove"}, headers=auth_header(admin_token)
    )
    assert [p["id"] for p in resp.json()] == ["GL-1"]

    resp = client.get(
        "/products",
        params={"category": "Consumables"},
        headers=auth_header(admin_token),
    )
    assert {p["id"] for p in resp.json()} == {"GL-1"}


def test_duplicate_product_conflict(client, admin_token, fake_erpnext):
    _create(client, admin_token, sku="DUP-1")
    assert _create(client, admin_token, sku="DUP-1").status_code == 409


def test_update_and_disable_product(client, admin_token, fake_erpnext):
    _create(client, admin_token, sku="UPD-1")
    resp = client.put(
        "/products/UPD-1",
        json={"selling_price": 3000.0, "disabled": True},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["selling_price"] == 3000.0
    assert resp.json()["disabled"] is True
    assert fake_erpnext.store["UPD-1"]["custom_selling_price"] == 3000.0
    assert fake_erpnext.store["UPD-1"]["disabled"] == 1


def test_delete_product(client, admin_token, fake_erpnext):
    _create(client, admin_token, sku="DEL-1")
    assert (
        client.delete("/products/DEL-1", headers=auth_header(admin_token)).status_code
        == 204
    )
    assert (
        client.get("/products/DEL-1", headers=auth_header(admin_token)).status_code
        == 404
    )


def test_get_missing_product_404(client, admin_token, fake_erpnext):
    assert (
        client.get("/products/nope", headers=auth_header(admin_token)).status_code
        == 404
    )


# --- RBAC ---


def test_manager_can_manage(client, make_token, fake_erpnext):
    token = make_token("Manager")
    assert _create(client, token, sku="MGR-1").status_code == 201


def test_sales_can_view_but_not_write(client, admin_token, make_token, fake_erpnext):
    _create(client, admin_token, sku="SEE-1")
    token = make_token("Sales")
    assert client.get("/products", headers=auth_header(token)).status_code == 200
    assert client.get("/products/SEE-1", headers=auth_header(token)).status_code == 200
    assert _create(client, token, sku="NO-1").status_code == 403


def test_unauthenticated_rejected(client, fake_erpnext):
    assert client.get("/products").status_code == 401
