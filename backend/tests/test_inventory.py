"""Integration tests for the Inventory module (warehouses, batches, stock,
goods received/issued) + RBAC, against a fake ERPNext."""

from tests.conftest import auth_header


# ----------------------------------------------------------------- Warehouses
def test_warehouse_crud(client, admin_token, fake_erpnext):
    resp = client.post(
        "/inventory/warehouses",
        json={"name": "Main Store", "is_group": False},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["id"] == "Main Store"
    assert fake_erpnext.store["Main Store"]["warehouse_name"] == "Main Store"

    assert (
        client.get(
            "/inventory/warehouses/Main Store", headers=auth_header(admin_token)
        ).status_code
        == 200
    )
    upd = client.put(
        "/inventory/warehouses/Main Store",
        json={"disabled": True},
        headers=auth_header(admin_token),
    )
    assert upd.status_code == 200 and upd.json()["disabled"] is True

    assert (
        client.delete(
            "/inventory/warehouses/Main Store", headers=auth_header(admin_token)
        ).status_code
        == 204
    )
    assert (
        client.get(
            "/inventory/warehouses/Main Store", headers=auth_header(admin_token)
        ).status_code
        == 404
    )


# -------------------------------------------------------------------- Batches
def test_batch_create_with_expiry(client, admin_token, fake_erpnext):
    resp = client.post(
        "/inventory/batches",
        json={
            "batch_id": "BATCH-001",
            "item_code": "THERMO-001",
            "expiry_date": "2027-01-31",
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["id"] == "BATCH-001"
    assert body["expiry_date"] == "2027-01-31"
    # Domain -> ERPNext field mapping.
    stored = fake_erpnext.store["BATCH-001"]
    assert stored["item"] == "THERMO-001"
    assert stored["expiry_date"] == "2027-01-31"

    got = client.get(
        "/inventory/batches/BATCH-001", headers=auth_header(admin_token)
    )
    assert got.status_code == 200
    assert got.json()["item_code"] == "THERMO-001"


def test_batch_duplicate_conflict(client, admin_token, fake_erpnext):
    body = {"batch_id": "DUP-B", "item_code": "THERMO-001"}
    assert (
        client.post(
            "/inventory/batches", json=body, headers=auth_header(admin_token)
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/inventory/batches", json=body, headers=auth_header(admin_token)
        ).status_code
        == 409
    )


# ---------------------------------------------------------------- Stock levels
def test_stock_levels(client, admin_token, fake_erpnext):
    fake_erpnext.store["bin-1"] = {
        "item_code": "THERMO-001",
        "warehouse": "Main Store",
        "actual_qty": 25,
        "projected_qty": 25,
    }
    fake_erpnext.store["bin-2"] = {
        "item_code": "GLOVE-001",
        "warehouse": "Main Store",
        "actual_qty": 100,
    }
    resp = client.get("/inventory/stock", headers=auth_header(admin_token))
    assert resp.status_code == 200
    rows = {r["item_code"]: r for r in resp.json()}
    assert rows["THERMO-001"]["actual_qty"] == 25
    assert rows["GLOVE-001"]["warehouse"] == "Main Store"


# ------------------------------------------------------------ Goods movements
def test_goods_received(client, admin_token, fake_erpnext):
    resp = client.post(
        "/inventory/receive",
        json={
            "warehouse": "Main Store",
            "items": [
                {
                    "item_code": "THERMO-001",
                    "qty": 10,
                    "batch_no": "BATCH-001",
                    "rate": 1500,
                }
            ],
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["stock_entry_type"] == "Material Receipt"
    assert body["items"][0]["item_code"] == "THERMO-001"
    assert body["items"][0]["warehouse"] == "Main Store"

    stored = fake_erpnext.store[body["id"]]
    assert stored["docstatus"] == 1  # submitted
    assert stored["to_warehouse"] == "Main Store"
    assert stored["items"][0]["t_warehouse"] == "Main Store"
    assert stored["items"][0]["basic_rate"] == 1500


def test_goods_issued(client, admin_token, fake_erpnext):
    resp = client.post(
        "/inventory/issue",
        json={
            "warehouse": "Main Store",
            "items": [{"item_code": "THERMO-001", "qty": 3}],
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["stock_entry_type"] == "Material Issue"
    stored = fake_erpnext.store[body["id"]]
    assert stored["docstatus"] == 1
    assert stored["from_warehouse"] == "Main Store"
    assert stored["items"][0]["s_warehouse"] == "Main Store"


def test_receive_requires_items(client, admin_token, fake_erpnext):
    resp = client.post(
        "/inventory/receive",
        json={"warehouse": "Main Store", "items": []},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 422  # min_length=1


# ------------------------------------------------------------------- RBAC
def test_store_keeper_can_receive(client, make_token, fake_erpnext):
    token = make_token("Store Keeper")
    resp = client.post(
        "/inventory/receive",
        json={
            "warehouse": "Main Store",
            "items": [{"item_code": "THERMO-001", "qty": 5}],
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201


def test_sales_can_view_stock_but_not_receive(client, make_token, fake_erpnext):
    token = make_token("Sales")
    assert client.get("/inventory/stock", headers=auth_header(token)).status_code == 200
    resp = client.post(
        "/inventory/receive",
        json={
            "warehouse": "Main Store",
            "items": [{"item_code": "THERMO-001", "qty": 5}],
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 403


def test_accountant_cannot_manage_warehouse(client, make_token, fake_erpnext):
    token = make_token("Accountant")
    assert client.get(
        "/inventory/warehouses", headers=auth_header(token)
    ).status_code == 200
    resp = client.post(
        "/inventory/warehouses",
        json={"name": "Nope"},
        headers=auth_header(token),
    )
    assert resp.status_code == 403


def test_unauthenticated_rejected(client, fake_erpnext):
    assert client.get("/inventory/stock").status_code == 401
    assert client.get("/inventory/warehouses").status_code == 401
